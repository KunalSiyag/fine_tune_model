(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const parallax = () => !reduce && matchMedia("(min-width: 900px)").matches;

  /* Parallax scroll: cards and buttons lift in sync with the page */
  const faders = [...document.querySelectorAll(".fader")];
  const intro = document.querySelector(".intro");
  const trail = document.querySelector(".top__grid");
  const root = document.documentElement;

  if (parallax()) {
    let lastY = 0;
    const io = new IntersectionObserver(([en]) => {
      if (!en.isIntersecting) { lastY = 0; return; }
      const t = Math.min(1, Math.max(0, (en.boundingClientRect.top + en.boundingClientRect.height / 2) / innerHeight));
      root.style.setProperty("--py", `${(1 - t) * window.innerHeight * 0.3}px`);
      root.style.setProperty("--ease", "cubic-bezier(.165, .84, .44, 1.2)");
    }, { threshold: 0.6 });
    io.observe(document.getElementById("top")); // feature section

    const tick = () => {
      const y = Math.min(window.scrollY, innerHeight) / innerHeight;
      const p = Math.min(1, y * 0.6);
      root.style.setProperty("--py", `${(1 - p) * innerHeight * 0.3}px`);
      if (lastY !== 0) { lastY = 0; root.style.setProperty("--ease", "cubic-bezier(.23, 1, .32, 1)"); }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  /* Split calculator */
  const calc = document.getElementById("calc");
  if (calc) {
    const fmt = (n) => n.toLocaleString("en-GB", { style: "currency", currency: "GBP" });
    const input = calc.querySelector("[data-shared]");
    const output = calc.querySelector(".calc__output");
    let shared = +input.value;

    const update = () => {
      const ind = +input.value;
      const split = (ind - shared) / shared;
      const owe = Math.round(ind * 100) / 100;
      output.innerHTML = `${split.toFixed(4) * 100}% split <b>${fmt(owe)}</b>`;
    };

    input.addEventListener("input", () => {
      const v = +input.value;
      input.value = Math.max(10, Math.min(500, v));
      shared = +input.value;
      update();
    });
    calc.querySelectorAll("input").forEach((el) => el.addEventListener("input", update));
  }

  /* Accordion */
  const accs = [...document.querySelectorAll(".accordion__summary")];
  accs.forEach((sum) => sum.addEventListener("click", () => {
    const open = sum.classList.toggle("accordion__summary--open");
    const panel = sum.nextElementSibling;
    if (open) { sum.setAttribute("aria-expanded", "true"); panel.hidden = false; }
    else { sum.removeAttribute("aria-expanded"); panel.hidden = true; }
  }));

  /* Slight card lift on hover */
  if (!reduce) {
    const hoverable = [...document.querySelectorAll(".feature")];
    hoverable.forEach((el) => el.addEventListener("mouseenter", () => el.classList.add("fader")));
    hoverable.forEach((el) => el.addEventListener("mouseleave", () => el.classList.remove("fader")));
  }

  // Intro fader in on load
  if (intro) intro.classList.add("fader");
  if (trail) trail.classList.add("fader");
})();
