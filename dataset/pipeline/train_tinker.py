#!/usr/bin/env python3
"""Fine-tune Qwen3-8B on dataset/out/ with Tinker (LoRA, remote GPUs).

    .venv/bin/python dataset/pipeline/train_tinker.py dry-run             # free: exact tokens + $ budget
    .venv/bin/python dataset/pipeline/train_tinker.py smoke               # ~1 cent: 2 real steps + 1 sample
    .venv/bin/python dataset/pipeline/train_tinker.py sft --name sft-v1
    .venv/bin/python dataset/pipeline/train_tinker.py dpo --name dpo-v1 --init dataset/runs/sft-v1
    .venv/bin/python dataset/pipeline/train_tinker.py sample --from dataset/runs/dpo-v1 --n 8
    .venv/bin/python dataset/pipeline/train_tinker.py sample --base --n 8   # untrained baseline
    .venv/bin/python dataset/pipeline/train_tinker.py sample --from dataset/runs/sft-v1 --prompts dataset/runs/ab/gemma.jsonl

Stages:
  sft     supervised fine-tuning on sft_train.jsonl: loss only on the assistant reply (the files),
          token-mean per record, multiplied by the record's `weight` (tier B = 0.5).
  dpo     preference tuning on dpo_train.jsonl, starting from the SFT weights; chosen = the page,
          rejected = its destyled / off-system / generic twin.
  sample  generate pages for held-out page_from_brief prompts and write their files to
          dataset/runs/<name>/samples/<id>/ so render.py can QA them like the training data.

Records longer than --max-length are dropped, never truncated: a cut-off page would teach the
model to stop mid-file. Runs and checkpoint records live in dataset/runs/ (gitignored).
TINKER_API_KEY is read from the environment or from the repo's .env.
"""
import argparse
import asyncio
import json
import math
import os
import re
import shutil
import sys
import time
from pathlib import Path

import chz
import datasets
import tinker
from tinker_cookbook import checkpoint_utils, cli_utils
from tinker_cookbook.hyperparam_utils import get_lr
from tinker_cookbook.preference import train_dpo
from tinker_cookbook.preference.dpo_datasets import DPODatasetBuilderFromComparisons
from tinker_cookbook.preference.preference_datasets import ComparisonDatasetBuilder
from tinker_cookbook.preference.types import Comparison, LabeledComparison
from tinker_cookbook.renderers import TrainOnWhat, get_renderer
from tinker_cookbook.supervised import train
from tinker_cookbook.supervised.data import SupervisedDatasetFromHFDataset, conversation_to_datum
from tinker_cookbook.supervised.types import ChatDatasetBuilder, ChatDatasetBuilderCommonConfig
from tinker_cookbook.tokenizer_utils import get_tokenizer

ROOT = Path(__file__).resolve().parents[2]
DS = ROOT / "dataset"
OUT = DS / "out"
RUNS = DS / "runs"

MODEL = "Qwen/Qwen3-8B"
RENDERER = "qwen3_disable_thinking"  # empty <think></think>: the page is the whole answer
# $ per million tokens, from https://tinker-docs.thinkingmachines.ai/tinker/models.json (2026-10-17)
PRICE = {"prefill": 0.195, "sample": 0.60, "train": 0.44}
CONTEXT = 32768


def load_env_key():
    if os.environ.get("TINKER_API_KEY"):
        return
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("TINKER_API_KEY="):
                os.environ["TINKER_API_KEY"] = line.split("=", 1)[1].strip().strip("'\"")
                return
    sys.exit("TINKER_API_KEY not set (export it or add it to .env)")


def read_jsonl(path: Path, limit: int | None = None, shortest: bool = False) -> list[dict]:
    rows = [json.loads(l) for l in path.open()]
    if shortest:
        rows.sort(key=lambda r: r["n_tokens_est"])
    return rows[:limit] if limit else rows


def common_config(max_length: int, batch_size: int) -> ChatDatasetBuilderCommonConfig:
    return ChatDatasetBuilderCommonConfig(
        model_name_for_tokenizer=MODEL, renderer_name=RENDERER,
        max_length=max_length, batch_size=batch_size,
        train_on_what=TrainOnWhat.LAST_ASSISTANT_MESSAGE)


# ---------------------------------------------------------------- datasets
@chz.chz
class WebsiteSFTBuilder(ChatDatasetBuilder):
    """sft_*.jsonl → batches of Datums; over-length records are dropped, weights scaled by `weight`."""
    train_path: str
    eval_path: str | None = None
    eval_limit: int = 24
    limit: int | None = None  # smoke test: the N shortest records
    seed: int = 0

    def record_to_data(self, row: dict) -> list[tinker.Datum]:
        d = conversation_to_datum(row["messages"], self.renderer, None,
                                  TrainOnWhat.LAST_ASSISTANT_MESSAGE, reduction="mean")
        if d.model_input.length > self.common_config.max_length:
            return []
        if row.get("weight", 1.0) != 1.0:
            w = d.loss_fn_inputs["weights"].to_torch() * row["weight"]
            d.loss_fn_inputs["weights"] = tinker.TensorData.from_torch(w)
        return [d]

    def __call__(self):
        rows = read_jsonl(Path(self.train_path), self.limit, shortest=self.limit is not None)
        train_ds = datasets.Dataset.from_list(rows).shuffle(seed=self.seed)
        train_set = SupervisedDatasetFromHFDataset(
            train_ds, batch_size=self.common_config.batch_size, flatmap_fn=self.record_to_data)
        eval_set = None
        if self.eval_path and self.eval_limit:
            ev = datasets.Dataset.from_list(read_jsonl(Path(self.eval_path))).shuffle(seed=self.seed)
            ev = ev.select(range(min(self.eval_limit, len(ev))))
            eval_set = SupervisedDatasetFromHFDataset(ev, batch_size=len(ev), flatmap_fn=self.record_to_data)
        return train_set, eval_set


@chz.chz
class WebsitePairsBuilder(ComparisonDatasetBuilder):
    """dpo_*.jsonl → LabeledComparison (label A = chosen); drops pairs whose longer side won't fit."""
    train_path: str
    max_length: int = CONTEXT
    limit: int | None = None

    def get_train_and_test_datasets(self):
        tok = get_tokenizer(MODEL)

        def fits(r):
            prompt = sum(len(tok.encode(m["content"])) for m in r["prompt"])
            longest = max(len(tok.encode(r[k][0]["content"])) for k in ("chosen", "rejected"))
            return prompt + longest + 64 <= self.max_length  # 64 ≈ chat-template tokens

        rows = [r for r in read_jsonl(Path(self.train_path)) if fits(r)][: self.limit]
        return datasets.Dataset.from_list(rows), None  # no NLL eval: DPO metrics come from training

    def example_to_labeled_comparison(self, example: dict) -> LabeledComparison | None:
        return LabeledComparison(
            comparison=Comparison(prompt_conversation=example["prompt"],
                                  completion_A=example["chosen"], completion_B=example["rejected"]),
            label="A")


# ---------------------------------------------------------------- dry-run
def token_report(rows, renderer, max_length, pairs=False):
    """Exact token counts with the real chat template. Returns (kept_tokens, kept_rows, dropped)."""
    kept_tok, kept, dropped, loss_tok, lengths = 0, 0, [], 0, []
    for r in rows:
        if pairs:
            seqs = [renderer.build_supervised_example(r["prompt"] + r[k])[0].length for k in ("chosen", "rejected")]
            n = sum(seqs)
            too_long = max(seqs) > max_length
        else:
            mi, w = renderer.build_supervised_example(r["messages"], train_on_what=TrainOnWhat.LAST_ASSISTANT_MESSAGE)
            n, too_long = mi.length, mi.length > max_length
        if too_long:
            dropped.append(r["id"])
            continue
        if not pairs:
            loss_tok += int(w.sum())
        kept, kept_tok = kept + 1, kept_tok + n
        lengths.append(n)
    lengths.sort()
    return {"rows": kept, "tokens": kept_tok, "loss_tokens": loss_tok, "dropped": dropped,
            "p50": lengths[len(lengths) // 2] if lengths else 0, "max": lengths[-1] if lengths else 0}


def show_mask(renderer, tok, row):
    """Print where the loss starts and ends, so you can see the model is only graded on the reply."""
    mi, w = renderer.build_supervised_example(row["messages"], train_on_what=TrainOnWhat.LAST_ASSISTANT_MESSAGE)
    ids = mi.to_ints()
    on = [i for i, x in enumerate(w.tolist()) if x > 0]
    first, last = on[0], on[-1]
    print(f"  record {row['id']}: {len(ids)} tokens, loss on {len(on)} ({len(on) / len(ids):.0%})")
    print(f"  …{tok.decode(ids[first - 12:first])!r}  ← no loss | loss →  {tok.decode(ids[first:first + 12])!r}…")
    print(f"  loss ends with: {tok.decode(ids[last - 8:last + 1])!r}")
    gen = renderer.build_generation_prompt(row["messages"][:-1]).to_ints()
    print(f"  generation prompt ends with: {tok.decode(gen[-12:])!r}")


def cmd_dry_run(args):
    tok = get_tokenizer(MODEL)
    renderer = get_renderer(RENDERER, tok)
    t0 = time.time()
    data = Path(args.data or OUT)
    sft = read_jsonl(data / "sft_train.jsonl")
    print(f"Loss mask check ({RENDERER}):")
    show_mask(renderer, tok, sft[0])

    rep = {"sft_train": token_report(sft, renderer, args.max_length),
           "sft_eval": token_report(read_jsonl(data / "sft_eval.jsonl"), renderer, args.max_length),
           "dpo_train": token_report(read_jsonl(data / "dpo_train.jsonl"), renderer, args.max_length, pairs=True)}
    if args.dpo_limit:  # mirrors WebsitePairsBuilder: first N pairs that fit
        pairs = [r for r in read_jsonl(data / "dpo_train.jsonl") if r["id"] not in set(rep["dpo_train"]["dropped"])]
        rep["dpo_train"] = token_report(pairs[: args.dpo_limit], renderer, args.max_length, pairs=True)
    print(f"\nTokenized everything in {time.time() - t0:.0f}s (max_length={args.max_length})")
    for k, r in rep.items():
        print(f"  {k:10} {r['rows']:5} rows  {r['tokens'] / 1e6:6.2f}M tokens  p50 {r['p50']:6}  "
              f"max {r['max']:6}  dropped {len(r['dropped'])}")
    if rep["sft_train"]["loss_tokens"]:
        print(f"  sft_train loss tokens (the replies): {rep['sft_train']['loss_tokens'] / 1e6:.2f}M")

    s, e, p = rep["sft_train"], rep["sft_eval"], rep["dpo_train"]
    sft_steps = math.ceil(s["rows"] / args.batch_size) * args.epochs
    n_evals = sft_steps // args.eval_every + 1 if args.eval_every else 0
    eval_tok = e["tokens"] * min(args.eval_limit, e["rows"]) / max(e["rows"], 1)
    dpo_steps = math.ceil(p["rows"] / args.dpo_batch_size) * args.dpo_epochs
    sample_prompt = 600 * args.samples  # page_from_brief prompts are short (system + brief)
    cost = {
        "SFT train": s["tokens"] * args.epochs * PRICE["train"],
        "SFT held-out NLL": eval_tok * n_evals * PRICE["prefill"],
        # reference logprobs (prefill) + forward_backward_custom, which runs a forward then a backward
        "DPO train": p["tokens"] * args.dpo_epochs * (2 * PRICE["prefill"] + PRICE["train"]),
        "Sampling": sample_prompt * PRICE["prefill"] + args.samples * args.sample_tokens * PRICE["sample"],
    }
    print(f"\nPlan: SFT {args.epochs} epoch(s) × batch {args.batch_size} = {sft_steps} steps, "
          f"eval {args.eval_limit} records every {args.eval_every} steps; "
          f"DPO {args.dpo_epochs} epoch(s) × batch {args.dpo_batch_size} pairs = {dpo_steps} steps; "
          f"{args.samples} samples × ≤{args.sample_tokens} tokens")
    for k, v in cost.items():
        print(f"  {k:18} ${v / 1e6:7.2f}")
    print(f"  {'TOTAL':18} ${sum(cost.values()) / 1e6:7.2f}   (prices: {PRICE} $/M tokens)")
    print("  DPO assumes the custom-loss forward is billed like prefill; treat it as an upper estimate.")
    if any(r["dropped"] for r in rep.values()):
        print("\nDropped as too long:", sum((r["dropped"] for r in rep.values()), []))


# ---------------------------------------------------------------- training
def run_dir(name: str) -> str:
    return str(RUNS / name)


def cmd_sft(args, smoke=False):
    load_env_key()
    data = Path(getattr(args, "data", None) or OUT)
    init = None
    if getattr(args, "init", None):  # continue from another run's weights (fresh optimizer and schedule)
        init = checkpoint_utils.get_last_checkpoint(str(Path(args.init).resolve()), required_key="state_path")
        if init is None:
            sys.exit(f"no state checkpoint in {args.init}/checkpoints.jsonl")
    builder = WebsiteSFTBuilder(
        common_config=common_config(args.max_length, args.batch_size),
        train_path=str(data / "sft_train.jsonl"),
        eval_path=None if smoke else str(data / "sft_eval.jsonl"),
        eval_limit=args.eval_limit, limit=args.limit, seed=getattr(args, "seed", 0))
    config = train.Config(
        log_path=run_dir(args.name), model_name=MODEL, recipe_name="website_sft",
        renderer_name=RENDERER, dataset_builder=builder,
        load_checkpoint_path=init.state_path if init else None,
        learning_rate=args.lr or get_lr(MODEL), lr_schedule="linear",
        num_epochs=args.epochs, lora_rank=args.rank,
        eval_every=args.eval_every, save_every=args.save_every, max_steps=args.max_steps)
    print(f"SFT {MODEL} lr={config.learning_rate:.2e} rank={args.rank} data={data.name}"
          f"{f' init={init.state_path}' if init else ''} → {config.log_path}")
    cli_utils.check_log_dir(config.log_path, behavior_if_exists="resume" if args.resume else "ask")
    asyncio.run(train.main(config))


def cmd_dpo(args):
    load_env_key()
    init = checkpoint_utils.get_last_checkpoint(str(Path(args.init).resolve()), required_key="state_path")
    if init is None:
        sys.exit(f"no state checkpoint in {args.init}/checkpoints.jsonl")
    builder = DPODatasetBuilderFromComparisons(
        common_config=common_config(args.max_length, args.batch_size),
        comparison_builder=WebsitePairsBuilder(
            train_path=str(OUT / "dpo_train.jsonl"), max_length=args.max_length, limit=args.limit))
    config = train_dpo.Config(
        log_path=run_dir(args.name), model_name=MODEL, recipe_name="website_dpo",
        renderer_name=RENDERER, dataset_builder=builder, load_checkpoint_path=init.state_path,
        learning_rate=args.lr, dpo_beta=args.beta, num_epochs=args.epochs, lora_rank=args.rank,
        save_every=args.save_every, max_steps=args.max_steps)
    print(f"DPO from {init.state_path} lr={args.lr:.1e} beta={args.beta} → {config.log_path}")
    cli_utils.check_log_dir(config.log_path, behavior_if_exists="resume" if args.resume else "ask")
    train_dpo.main(config)


# ---------------------------------------------------------------- sampling
FILE_RE = re.compile(r'<file path="([^"]+)">\n?(.*?)</file>', re.S)


def write_files(reply: str, dest: Path) -> list[str]:
    written = []
    for path, body in FILE_RE.findall(reply):
        target = (dest / path).resolve()
        if not target.is_relative_to(dest.resolve()):  # model output: never write outside dest
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
        written.append(path)
    return written


async def sample_all(client, renderer, rows, max_tokens, temperature, dest, k=1, prefix="", start=0):
    """k > 1 writes candidates to <id>/k1 … <id>/kN for pick_best.py (one request, shared prompt);
    start > 0 numbers them from k{start+1}, to top up an existing set.
    prefix starts the reply for the model, e.g. '<file path="index.html">\\n' to write the page first."""
    async def one(row):
        msgs = row["messages"][:-1] if row["messages"][-1]["role"] == "assistant" else row["messages"]
        prompt = renderer.build_generation_prompt(msgs)
        if prefix:
            prompt = tinker.ModelInput.from_ints(
                prompt.to_ints() + renderer.tokenizer.encode(prefix, add_special_tokens=False))
        res = await client.sample_async(
            prompt=prompt, num_samples=k,
            sampling_params=tinker.SamplingParams(max_tokens=min(max_tokens, CONTEXT - prompt.length),
                                                  temperature=temperature,
                                                  stop=renderer.get_stop_sequences()))
        base = dest / re.sub(r"[^a-z0-9]+", "-", row["id"].lower()).strip("-")
        n_tokens = 0
        for j, seq in enumerate(res.sequences, 1):
            msg, _ = renderer.parse_response(seq.tokens)
            content = prefix + (msg["content"] if isinstance(msg["content"], str) else str(msg["content"]))
            out = base / f"k{start + j}" if k > 1 or start else base
            out.mkdir(parents=True, exist_ok=True)
            (out / "reply.txt").write_text(content)
            src_assets = DS / row.get("source", "-") / "assets"
            if "source" in row and src_assets.is_dir():
                shutil.copytree(src_assets, out / "assets", dirs_exist_ok=True)
            files = write_files(content, out)
            print(f"  {row['id']}{f' k{j}' if k > 1 else ''}: {len(seq.tokens)} tokens, "
                  f"stop={seq.stop_reason}, files={files}")
            n_tokens += len(seq.tokens)
        return n_tokens

    return await asyncio.gather(*[one(r) for r in rows])


def cmd_sample(args):
    load_env_key()
    service = tinker.ServiceClient()
    if args.base:
        client, name = service.create_sampling_client(base_model=MODEL), "base"
    else:
        ckpt = checkpoint_utils.get_last_checkpoint(str(Path(args.src).resolve()), required_key="sampler_path")
        if ckpt is None:
            sys.exit(f"no sampler checkpoint in {args.src}/checkpoints.jsonl")
        client, name = service.create_sampling_client(model_path=ckpt.sampler_path), Path(args.src).name
        print(f"Sampling {ckpt.sampler_path}")
    renderer = get_renderer(RENDERER, get_tokenizer(MODEL))
    if args.prompts:  # e.g. brief_gemma.py --ab output: raw.jsonl / gemma.jsonl
        rows = read_jsonl(Path(args.prompts))
        dest = RUNS / name / f"samples-{args.tag or Path(args.prompts).stem}"
    else:
        seen, rows = set(), []
        for r in read_jsonl(OUT / "sft_eval.jsonl"):
            if r["task"] == "page_from_brief" and r["source"] not in seen:
                seen.add(r["source"])
                rows.append(r)
        dest = RUNS / name / "samples"
    rows = rows[: args.n]
    k = getattr(args, "k", 1)
    tokens = asyncio.run(sample_all(client, renderer, rows, args.max_tokens, args.temperature, dest, k))
    print(f"Wrote {len(rows)}×{k} samples to {dest} ({sum(tokens)} generated tokens, "
          f"≈${sum(tokens) * PRICE['sample'] / 1e6:.2f})")
    renders = (RUNS / name / f"renders-{dest.name.removeprefix('samples-')}").relative_to(ROOT)
    glob_ = f"{dest.relative_to(ROOT)}/*/{'k*/' if k > 1 else ''}index.html"
    print(f"QA them:  python3 dataset/pipeline/render.py --glob '{glob_}' --out {renders}")
    if k > 1:
        print(f"then:     python3 dataset/pipeline/pick_best.py {dest.relative_to(ROOT)} {renders}")


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def shared(p, batch, epochs):
        p.add_argument("--max-length", type=int, default=CONTEXT, help="drop records longer than this")
        p.add_argument("--batch-size", type=int, default=batch)
        p.add_argument("--epochs", type=int, default=epochs)
        p.add_argument("--rank", type=int, default=32, help="LoRA rank")
        p.add_argument("--save-every", type=int, default=20)
        p.add_argument("--max-steps", type=int, default=None)
        p.add_argument("--limit", type=int, default=None, help="use only N records")
        p.add_argument("--resume", action="store_true", help="continue an interrupted run in --name")

    d = sub.add_parser("dry-run", help="tokenize locally, print exact tokens and the $ budget")
    d.add_argument("--max-length", type=int, default=CONTEXT)
    d.add_argument("--data", default=None, help="dataset folder (default dataset/out)")
    d.add_argument("--batch-size", type=int, default=16)
    d.add_argument("--epochs", type=int, default=2)
    d.add_argument("--eval-every", type=int, default=20)
    d.add_argument("--eval-limit", type=int, default=24)
    d.add_argument("--dpo-batch-size", type=int, default=8)
    d.add_argument("--dpo-epochs", type=int, default=1)
    d.add_argument("--dpo-limit", type=int, default=None, help="price only the first N pairs (dpo --limit)")
    d.add_argument("--samples", type=int, default=16)
    d.add_argument("--sample-tokens", type=int, default=16000)

    s = sub.add_parser("sft", help="supervised fine-tuning")
    s.add_argument("--name", required=True)
    shared(s, batch=16, epochs=2)
    s.add_argument("--lr", type=float, default=None, help="default: cookbook get_lr() for the model")
    s.add_argument("--eval-every", type=int, default=20)
    s.add_argument("--eval-limit", type=int, default=24, help="held-out records scored at each eval")
    s.add_argument("--data", default=None, help="dataset folder (default dataset/out)")
    s.add_argument("--init", default=None, help="run dir to continue from (its last state checkpoint)")
    s.add_argument("--seed", type=int, default=0, help="shuffle seed for the training order")

    sm = sub.add_parser("smoke", help="2 steps on the 4 shortest records, then sample once (~1 cent)")
    sm.add_argument("--name", default=f"smoke-{time.strftime('%Y%m%d-%H%M%S')}")

    p = sub.add_parser("dpo", help="preference tuning from an SFT run")
    p.add_argument("--name", required=True)
    p.add_argument("--init", required=True, help="SFT run dir (its last checkpoint is the start point)")
    shared(p, batch=8, epochs=1)
    p.add_argument("--lr", type=float, default=1e-5)
    p.add_argument("--beta", type=float, default=0.1, help="how far DPO may move from the SFT model")

    g = sub.add_parser("sample", help="generate held-out pages for render.py")
    src = g.add_mutually_exclusive_group(required=True)
    src.add_argument("--from", dest="src", help="run dir whose last sampler checkpoint to use")
    src.add_argument("--base", action="store_true", help="the untrained base model")
    g.add_argument("--prompts", help="JSONL of {id, messages} prompts instead of the held-out briefs")
    g.add_argument("--tag", help="output folder suffix (default: the prompts file name)")
    g.add_argument("--k", type=int, default=1, help="candidates per prompt, for pick_best.py")
    g.add_argument("--n", type=int, default=8)
    g.add_argument("--max-tokens", type=int, default=16000)
    g.add_argument("--temperature", type=float, default=0.7)

    args = ap.parse_args()
    if args.cmd == "dry-run":
        cmd_dry_run(args)
    elif args.cmd == "sft":
        cmd_sft(args)
    elif args.cmd == "smoke":
        args = argparse.Namespace(name=args.name, max_length=CONTEXT, batch_size=2, epochs=1, rank=32,
                                  save_every=0, max_steps=2, limit=4, resume=False, lr=None,
                                  eval_every=0, eval_limit=0)
        cmd_sft(args, smoke=True)
        cmd_sample(argparse.Namespace(base=False, src=run_dir(args.name), prompts=None, tag=None, k=1,
                                      n=1, max_tokens=256, temperature=0.7))
    elif args.cmd == "dpo":
        cmd_dpo(args)
    elif args.cmd == "sample":
        cmd_sample(args)


if __name__ == "__main__":
    main()
