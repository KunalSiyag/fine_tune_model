// Robot Ascent — fundraiser page: pledge calculator, accordion
(() => {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const NAV = $(".top nav");

  /* ---------- HERO: progress bar segments light up in sequence ---------- */
  const id = $$("[data-s]")[0] || null;
  const BAR = $(".progress");
  if (id && BAR && !reduce) {
    const segs = id.querySelectorAll(".progress__step"), n = segs.length;
    const draw = (t) => {
      const k = Math.min(1, Math.max(0, t / 1.4));
      const p = 1 - Math.pow(1 - k, 1.4);
      const s = Math.round(p * 100);
      if (!s) return;
      BAR.style.setProperty("--p", s);
      const i = Math.floor(s / (n * 10));
      if (segs[i]) segs[i].style.setProperty("--p", s % (n * 10) >= 1 || i === n ? 1 : 0);
      if (i < n - 1) requestAnimationFrame(draw);
    };
    requestAnimationFrame(draw);
  }

  /* ---------- NAV: marked link highlights ---------- */
  if (NAV) NAV.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (!a) return;
    const mark = a.getAttribute("data-marked");
    $$("[data-marked]").forEach((x) => {
      if (x.dataset.marked === mark) x.classList.add("is-marked");
      else x.classList.remove("is-marked");
    });
  });

  /* ---------- PLEDGE CALCULATOR ---------- */
  const form = $("#pledgeForm"), amount = $("#amount"), amountF = $("#amountF");
  if (form && amount && amountF) {
    const sum = () => {
      const v = parseFloat(amount.value.trim()) || 0;
      form.querySelector(".pledge__total").textContent = "$" + v.toFixed(2);
      form.querySelector(".pledge__left").textContent = "$" + (2000 - v).toFixed(2);
      return v;
    };
    amount.addEventListener("input", sum);
    amount.addEventListener("blur", () => { const v = parseFloat(amount.value.trim()) || 0; amount.value = v.toFixed(2); });
    amount.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") e.preventDefault();
    });
    form.addEventListener("submit", (e) => e.preventDefault());

    const tiers = form.querySelectorAll("[data-tier]");
    const setTiers = (v) => {
      tiers.forEach((t) => {
        const n = parseFloat(t.dataset.tier);
        t.hidden = n > v;
        const b = t.querySelector(".tier__btn");
        if (b) {
          b.disabled = v < n;
          b.textContent = "$" + n.toFixed(2) + (!b.dataset.locked ? " — pledge" : "");
        }
      });
    };
    sum();

    const paid = () => Math.min(2000, sum());
    const bar = $("#progressBar");
    if (bar) bar.style.setProperty("--p", (paid() / 2000 * 100).toFixed(1));
    const boxes = form.querySelectorAll(".tier");
    boxes.forEach((b) => {
      const n = parseFloat(b.dataset.tier);
      if (n < paid()) b.classList.add("is-paid");
    });

    const focus = (b) => {
      amount.value = b.dataset.tier;
      amount.select();
      if (finePointer) amount.focus({ preventScroll: true });
      setTiers(parseFloat(b.dataset.tier));
    };
    form.addEventListener("change", () => setTiers(sum()));
    form.addEventListener("focusout", (e) => { const b = e.target.closest(".tier__btn"); if (b) focus(b); });
    boxes.forEach((b) => {
      const btn = b.querySelector(".tier__btn");
      btn.addEventListener("click", () => focus(b));
      const lockBtn = b.querySelector(".tier__btn__lock");
      if (lockBtn) {
        lockBtn.addEventListener("click", (e) => {
          const btn = e.currentTarget.closest(".tier__btn");
          if (!btn) return;
          const n = parseFloat(btn.dataset.tier);
          const paidNow = paid();
          if (paidNow >= n) return;
          btn.setAttribute("data-locked", "");
          btn.textContent = "Locked — $" + n.toFixed(2);
          btn.disabled = true;
          btn.style.backgroundColor = "var(--yellow)";
          btn.style.borderColor = "var(--yellow)";
          focus(b);
        });
      }
    });
  }

  /* ---------- ACCORDION ---------- */
  const acc = $("#faq");
  if (acc) {
    acc.addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      const open = btn.getAttribute("aria-expanded") !== "true";
      btn.setAttribute("aria-expanded", open);
      const p = btn.nextElementSibling;
      if (p) p.hidden = !open;
      if (reduce) return;
      const dir = open ? 1 : -1;
      const root = btn.getRootNode().host || btn;
      btn.animate([{ transform: `translateY(${dir * 6}px) skewY(5deg)` }, { transform: "none" }], { duration: 220, easing: "cubic-bezier(.165, .84, .44, 1)" });
      if (p) p.animate([{ height: open ? "0" : "100%" }, { height: "auto" }], { duration: 280, easing: "cubic-bezier(.23, 1, .32, 1)" });
    });
  }

  /* ---------- REVEAL ---------- */
  if ("IntersectionObserver" in window) {
    document.querySelectorAll("[data-reveal]").forEach((el) => {
      const io = new IntersectionObserver((entries) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return;
          el.classList.add("is-reveal");
          io.disconnect();
        });
      }, { rootMargin: "0px 0px -8% 0px" });
      io.observe(el);
    });
  }
})();
