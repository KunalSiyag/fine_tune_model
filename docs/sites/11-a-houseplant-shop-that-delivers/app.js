(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const root = document.documentElement;
  const items = [...document.querySelectorAll(".items > div")];
  const filters = [...document.querySelectorAll("[data-filter]")];
  const tiles = [...document.querySelectorAll(".tile")];

  /* plant finder: accordion with an open state that carries over the page */
  const finder = document.querySelector("#finder");
  if (finder) {
    const first = finder.querySelector(".items > div");
    if (first) {
      const open = first.querySelector("button");
      if (open && open.hasAttribute("aria-expanded")) {
        const id = open.getAttribute("aria-expanded");
        root.classList.add("is-open");
        root.style.setProperty("--open", id);
      }
    }
  }

  /* the care rating filter: select a rating, and only those tiles whose care level matches */
  const filter = (name, value) => {
    root.classList.remove("is-open");
    root.style.setProperty("--open", "");
    const q = `[data-${name}="${value}"]`;
    if (value === "all") {
      document.querySelectorAll(q).forEach((t) => t.classList.remove("is-hidden"));
    } else {
      tiles.forEach((t) => {
        const on = t.matches(q);
        t.classList.toggle("is-hidden", !on);
        const li = t.closest(".tile");
        if (li) li.hidden = !on;
      });
    }
  };
  filters.forEach((f) => f.addEventListener("click", () => {
    filter(f.dataset.filter, f.dataset.value);
  }));

  /* tile clicks open the parent accordion item, which slides the label into place */
  tiles.forEach((t) => t.addEventListener("click", () => {
    const li = t.closest(".tile");
    if (!li) return;
    const btn = li.closest(".items > div").querySelector("button");
    if (btn) {
      const is = btn.getAttribute("aria-expanded") === "true";
      btn.click();
      if (!is) filter(btn.dataset.filter, btn.dataset.value);
    }
  }));
})();
