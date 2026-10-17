// Museo Radiofonia Turin — collection navigation, ticket picker, view details modal.
(() => {
  const tick = () => document.getElementById("clock").textContent = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

  /* ---------- view details ---------- */
  const models = [...document.querySelectorAll(".model")];
  const items = [...document.querySelectorAll(".list")];
  const panel = document.getElementById("panel");
  const btnClose = document.getElementById("btnClose");
  const state = { open: false };

  const open = () => {
    state.open = true;
    panel.classList.add("is-open");
    // Guard lookup for items[0]
    if (items.length > 0) {
      panel.setAttribute("aria-label", "View details for " + items[0].dataset.label);
    }
    btnClose.focus();
    tick(); /* start the clock inside the modal */
  };
  const close = () => {
    state.open = false;
    panel.classList.remove("is-open");
    // Guard lookup for items[0]
    if (items.length > 0) {
      items.forEach((li) => li.setAttribute("aria-expanded", String(li === items[0])));
    }
    // Guard lookup for panelRef
    const panelRef = document.getElementById("panelRef");
    if (panelRef) panelRef.setAttribute("aria-expanded", "false");
  };
  const toggle = (li) => {
    const i = li.dataset.model;
    if (panel.dataset.model === i) return close();
    models.forEach((m, k) => {
      if (k === i) {
        m.dataset.state = "active";
        items.forEach((x) => x.hidden = x.dataset.model !== k);
      } else {
        m.dataset.state = "";
        x.hidden = true;
      }
    });
    panel.dataset.model = i;
    // Guard lookup for items[i]
    if (items[i]) {
      items.forEach((x) => x.setAttribute("aria-expanded", String(x === items[i])));
      const panelRef = document.getElementById("panelRef");
      if (panelRef) panelRef.setAttribute("aria-expanded", String(panelRef === items[i]));
    }
    if (state.open) open();
    else open();
  };

  items.forEach((li, i) => {
    const btn = li.querySelector("button");
    if (btn) {
      btn.addEventListener("click", () => toggle(li));
    }
    li.addEventListener("mouseenter", () => { if (!state.open) toggle(li); });
    li.addEventListener("mouseleave", () => { if (state.open) close(); });
  });
  btnClose.addEventListener("click", close);
  btnClose.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { close(); btnClose.focus(); }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.open) { close(); btnClose.focus(); }
  });

  /* ---------- ticket picker ---------- */
  const radios = [...document.querySelectorAll(".tickets__radio input")];
  const total = document.getElementById("total");
  let onSelect = () => {};

  const tell = () => {
    const r = radios.find((x) => x.checked);
    const p = r ? parseFloat(r.getAttribute("data-price")) : 0;
    if (total) {
      total.textContent = "Total " + new Intl.NumberFormat("en-GB", { style: "currency", currency: "EUR" }).format(p);
    }
    onSelect(p);
  };
  radios.forEach((r) => {
    r.addEventListener("change", tell);
    r.addEventListener("focusout", tell);
  });
  document.getElementById("btnBuy")?.addEventListener("click", () => {
    const r = radios.find((x) => x.checked);
    if (!r) return;
    // Guard lookup for ticketText
    const text = document.getElementById("ticketText");
    if (text) {
      text.textContent = "Your " + r.dataset.label + " ticket is ready.";
      text.setAttribute("aria-busy", "true");
      setTimeout(() => {
        text.removeAttribute("aria-busy");
        text.textContent = "Your " + r.dataset.label + " ticket is ready. Pick it up at the kiosk.";
      }, 1200);
    }
  });

  /* ---------- scroll-driven reveal ---------- */
  const list = document.getElementById("list");
  if (list && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -18% 0px" });
    list.querySelectorAll("li.model").forEach((li) => io.observe(li));
  }
})();
