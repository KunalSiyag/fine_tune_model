(() => {
  const $ = (id) => document.getElementById(id);
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const toast = $("toast");
  toast?.addEventListener("animationend", () => { toast?.classList.remove("is-shown"); });

  /* ---------- tabs: switch pricing + card heights ---------- */
  const tabs = [...document.querySelectorAll(".tab")];
  const cards = [...document.querySelectorAll(".card")];
  const lock = $("lock");
  const form = $("book");
  const grid = $("heroGrid");

  function setActive(tab, card, active = true) {
    tabs.forEach((t) => t.classList.toggle("is-active", t === tab));
    cards.forEach((c) => c.classList.toggle("is-active", c === card));
    card.classList.toggle("is-inactive", !active);
    if (lock) lock.hidden = active;
    if (grid) grid.classList.toggle("is-inactive", active);
  }

  function sync() {
    const daily = tabs[0];
    const monthly = tabs[1];
    setActive(daily, cards[0], lock ? !lock.checked : true);
    setActive(monthly, cards[1], lock ? lock.checked : false);
    if (form) form.querySelector("select").value = lock ? daily.textContent : monthly.textContent;
    if (grid) grid.classList.toggle("is-anim", daily.classList.contains("is-active"));
  }

  if (tabs.length && cards.length && grid) {
    tabs.forEach((tab, i) => {
      tab.addEventListener("click", () => {
        if (!reduce && grid) grid.classList.remove("is-anim");
        tabs.forEach((t) => t.classList.remove("is-active"));
        cards.forEach((c) => c.classList.remove("is-active"));
        setActive(tab, cards[i], true);
        if (lock) lock.checked = tab === tabs[0];
        sync();
      });
    });
  }

  /* ---------- desk SVG: hover → chair + hold ---------- */
  if (!reduce) {
    document.querySelectorAll(".desk").forEach((svg) => {
      const rect = svg.querySelector("rect");
      const path = svg.querySelector("path");
      const isBig = rect.getAttribute("width") > 120;
      svg.addEventListener("mouseenter", () => { svg.classList.add("is-hovered"); });
      svg.addEventListener("mouseleave", () => { svg.classList.remove("is-hovered"); });
      svg.addEventListener("pointerdown", () => { svg.classList.toggle("is-hold"); });
      svg.addEventListener("pointerup", () => { svg.classList.remove("is-hold"); });
      svg.addEventListener("pointercancel", () => { svg.classList.remove("is-hold"); });
      if (isBig) svg.classList.add("is-big");
    });
  }

  /* ---------- directions: accordion ---------- */
  const acc = $("acc");
  if (acc) acc.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const panel = btn.nextElementSibling;
    btn.setAttribute("aria-expanded", btn.getAttribute("aria-expanded") === "false" ? "true" : "false");
    if (panel) panel.hidden = btn.getAttribute("aria-expanded") !== "true";
    const finder = $("finder");
    if (finder) finder.hidden = btn.getAttribute("aria-expanded") === "true";
  });

  /* ---------- booking form, toast ---------- */
  const name = $("name");
  const email = $("email");
  const plan = $("plan");
  const msg = $("msg");
  const book = $("bookBtn");
  const toastText = $("toastText");

  function validate() {
    const valid = { name: true, email: true, plan: true };
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
    if (!name.value.trim()) { name.setAttribute("aria-invalid", "true"); name.setAttribute("aria-describedby", "err-name"); name.focus(); return false; }
    if (!email.value.trim() || !emailPattern.test(email.value)) {
      email.setAttribute("aria-invalid", email.value.trim() ? "true" : "false");
      email.setAttribute("aria-describedby", "err-email");
      email.focus();
      return false;
    }
    if (!plan.value) { plan.setAttribute("aria-invalid", "true"); plan.setAttribute("aria-describedby", "err-plan"); plan.focus(); return false; }
    Object.values(valid).forEach((v) => v && name.removeAttribute("aria-invalid"));
    return true;
  }

  function show(toastText, text, status) {
    toastText.textContent = text;
    toast.classList.add("is-shown");
    toast.hidden = false;
    if (status === "error") toast.classList.remove("is-success");
    else toast.classList.add("is-success");
    setTimeout(() => { toast.classList.remove("is-shown"); }, 4000);
  }

  if (book && name && email && plan && msg) {
    book.disabled = true;
    book.setAttribute("aria-busy", "true");
    book.textContent = "Booking…";
    book.addEventListener("click", () => {
      const fail = !validate();
      if (fail) {
        book.disabled = false;
        book.setAttribute("aria-busy", "false");
        book.textContent = "Reserve Slot";
        show(msg, "Please fill in the missing detail before booking.", "error");
        return;
      }
      const ref = "F-407-" + Math.floor(100000 + Math.random() * 900000);
      const nameText = name.value.trim();
      const emailText = email.value.trim();
      show(msg, `${nameText}, your ${plan.value} desk has been reserved for 3 days from 9:00 AM. Confirmation #${ref}.`, "success");
      book.disabled = true;
      book.setAttribute("aria-busy", "true");
      book.textContent = "Reserving…";
      setTimeout(() => {
        book.disabled = false;
        book.setAttribute("aria-busy", "false");
        book.textContent = "Reserve Slot";
        plan.value = "";
        name.value = "";
        email.value = "";
      }, 2000);
    });
  }
})();
