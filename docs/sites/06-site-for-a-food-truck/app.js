(() => {
  const hourEl = document.querySelector(".clock__ones");
  const tensEl = document.querySelector(".clock__tens");
  if (hourEl && tensEl) {
    const now = new Date();
    const hours = now.getHours().toLocaleString("en-IN", { minimumIntegerDigits: 2 });
    tensEl.textContent = hours[0];
    hourEl.textContent = hours[1];
    setInterval(() => {
      const [t, h] = hours.split("");
      tensEl.textContent = t;
      hourEl.textContent = h;
    }, 60000);
  }

  const tabs = [...document.querySelectorAll(".side-panel__tabs button")];
  const cards = document.querySelectorAll(".cards .card");
  const map = document.querySelector("#map");
  const mapLink = document.querySelector("#mapLink");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Set the clock from the current time
  if (hourEl && tensEl) {
    const now = new Date();
    const hours = now.getHours().toLocaleString("en-IN", { minimumIntegerDigits: 2 });
    tensEl.textContent = hours[0];
    hourEl.textContent = hours[1];
    setInterval(() => {
      const [t, h] = hours.split("");
      tensEl.textContent = t;
      hourEl.textContent = h;
    }, 60000);
  }

  if (mapLink && map) {
    mapLink.addEventListener("click", (e) => {
      e.preventDefault();
      map.scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
    });
  }

  const setActive = (tab, focus = false) => {
    tabs.forEach((t) => t.setAttribute("aria-selected", String(t === tab)));
    cards.forEach((c) => c.hidden = c.dataset.tab !== tab.dataset.tab);
    if (!reduce && focus) {
      tab.focus({ preventScroll: true });
    }
  };
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => setActive(tab));
    tab.addEventListener("keydown", (e) => {
      const i = tabs.indexOf(tab);
      let next = null;
      if (e.key === "ArrowRight") next = (i + 1) % tabs.length;
      if (e.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
      if (next !== null) {
        e.preventDefault();
        setActive(tabs[next], true);
      }
    });
  });

  if (!reduce) {
    tabs.forEach((tab) => {
      tab.addEventListener("keydown", (e) => {
        if (e.key === "Home") { e.preventDefault(); setActive(tabs[0], true); }
        if (e.key === "End") { e.preventDefault(); setActive(tabs[tabs.length - 1], true); }
      });
    });
    const cardAnim = (el) => el.animate(
      [{ transform: "translateX(-100%) scale(.92)", opacity: 0 }, { transform: "none", opacity: 1 }],
      { duration: 520, easing: "cubic-bezier(.23,1,.32,1)", delay: 40 }
    );
    tabs.forEach((tab) => {
      const show = () => {
        if (tab.hidden) return;
        cards.forEach((c) => {
          if (c.hidden || c.dataset.tab !== tab.dataset.tab) return;
          cardAnim(c);
        });
        const pin = document.querySelector(`[data-pin="${tab.dataset.tab}"]`);
        if (pin) { pin.animate([{ transform: "scale(1.05)" }, { transform: "none" }], { duration: 400 }); }
      };
      tab.addEventListener("pointerenter", show);
      tab.addEventListener("focus", show);
    });
    setActive(tabs[0], true);
  }
})();
