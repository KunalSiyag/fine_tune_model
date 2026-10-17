/* De Reparatie Koffie Utrecht — accordion */
(() => {
  const accs = [...document.querySelectorAll(".faq__acc")];
  if (accs.length === 0) return;

  const setOpen = (acc, open) => {
    acc.hidden = !open;
    if (acc.open === open) return;
    acc.open = open;
  };
  const open = (acc, from) => {
    const next = acc.nextElementSibling;
    const wasOpen = acc.open;
    const openNow = !wasOpen;
    if (from) setOpen(acc, openNow);
    else acc.classList.add("is-open");
    const t = acc.querySelector(".faq__body");
    if (t) t.setAttribute("aria-hidden", String(!openNow));

    if (openNow) {
      t.style.height = t.scrollHeight + "px";
    } else {
      t.style.height = "0px";
    }
    const done = () => {
      setOpen(acc, openNow);
      if (from) acc.classList.remove("is-open");
      t.removeAttribute("aria-hidden");
      if (!openNow) t.style.height = "";
    };
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      done();
      return;
    }
    t.addEventListener("transitionend", () => done(), { once: true });
  };
  accs.forEach((acc) => {
    acc.querySelector(".faq__h").addEventListener("click", () => open(acc));
    acc.addEventListener("click", (e) => {
      if (e.target === acc || e.target.closest(".faq__body")) open(acc, true);
    });
    acc.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        open(acc);
      }
    });
  });
})();
