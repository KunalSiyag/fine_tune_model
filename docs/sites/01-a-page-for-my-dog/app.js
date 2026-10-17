// Van Paws — booking: date → time → confirmation
(() => {
  const form = document.getElementById("booking");
  const size = document.getElementById("booking-size");
  const services = [...document.querySelectorAll(".price-grid [data-service]")];
  const calendar = document.getElementById("calendar");
  const slots = document.getElementById("slot-list");
  const confirmModal = document.getElementById("confirmModal");
  const confirmCode = document.getElementById("confirmCode");
  const confirmMsg = document.getElementById("confirmMsg");
  const confirmClose = document.getElementById("confirmClose");
  const action = document.getElementById("bookAction");
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  if (!form || !size || !calendar || !slots || !confirmModal || !confirmCode || !confirmMsg || !confirmClose || !action) return;

  // The pricing matrix: size → service → price
  const prices = {
    S: { Wash: 35, De: 55, Clip: 80 },
    M: { Wash: 50, De: 70, Clip: 110 },
    L: { Wash: 65, De: 90, Clip: 130 },
    X: { Wash: 80, De: 105, Clip: 150 },
  };

  // Leeds within 20 miles of the UK's edge; the map dots are the real postcodes
  const Leeds = { lat: 53.7993, lng: -1.5488, miles: 20 };
  const boundary = { lat: 51.994, lng: -1.6716 };
  const postcodes = ["LS1", "LS2", "LS3", "LS4", "LS5", "LS6", "LS7", "LS8", "LS10", "LS11", "LS12", "LS13", "LS14", "LS15", "LS16", "LS17", "LS18", "LS19", "LS20"];

  // Current selection: size, service, date, time
  let sel = { size: "S", service: "Wash", date: null, time: null };

  // ---- Summary: a live summary of the booking, mirroring the form values
  const summary = document.getElementById("summary");
  const summarySize = document.getElementById("summarySize");
  const summaryService = document.getElementById("summaryService");
  const summaryDate = document.getElementById("summaryDate");
  const summaryTime = document.getElementById("summaryTime");
  const summaryPrice = document.getElementById("summaryPrice");
  const summarySizeText = document.getElementById("summarySizeText");
  const summaryServiceText = document.getElementById("summaryServiceText");
  const summaryTitle = document.getElementById("summaryTitle");
  if (summary) summary.innerHTML = "";
  if (summarySize || summaryService || summaryDate || summaryTime || summaryPrice || summarySizeText || summaryServiceText || summaryTitle) {
    summarySizeText.textContent = "Size";
    summaryServiceText.textContent = "Service";
    summaryTitle.textContent = "Booking confirmed";
    summary.append(
      document.createElement("p").append(document.createTextNode("Size")),
      document.createElement("p").append(document.createTextNode("Service")),
      document.createElement("p").append(document.createTextNode("Date")),
      document.createElement("p").append(document.createTextNode("Time")),
      document.createElement("p").append(document.createElement("b")),
    );
    summarySize.textContent = "Small";
    summaryService.textContent = "Wash & Trim";
    summaryDate.textContent = "Saturday 28 August";
    summaryTime.textContent = "9:00 am";
    summaryPrice.textContent = "£35";
  }

  // ---- Map: Leeds within 20 miles of the UK's edge (the line)
  const map = document.getElementById("leedsMap");
  if (map) {
    const svg = map.appendChild(document.createElementNS("http://www.w3.org/2000/svg", "svg"));
    svg.setAttribute("viewBox", "32 0 640 700");
    svg.innerHTML = `
      <path d="M32 700L32 380L608 380L608 700Z" fill="none" stroke="#1f333b" stroke-width="1.5"/>
      <path d="M32 700Q608 700 608 625T32 625Z" fill="none" stroke="#ffc72c" stroke-width="3"/>
      <path d="M32 700Q32 125 200 75L320 80Q460 85 608 75Z" fill="none" stroke="#1f333b" stroke-width="1.5"/>
    `;
    postcodes.forEach((p) => {
      const x = Math.min(608, (Leeds.lng - parseFloat(p.slice(-3)) / 60) * 1000 + 32);
      const y = Math.min(700, (Leeds.lat - parseFloat(p.slice(-3)) / 60) * 1400);
      if (x < 32 || y < 0) return;
      const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      c.setAttribute("cx", x);
      c.setAttribute("cy", y);
      c.setAttribute("r", "5");
      c.setAttribute("fill", "#ffc72c");
      svg.appendChild(c);
      const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
      t.setAttribute("x", x);
      t.setAttribute("y", y + 9);
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("font-size", "10");
      t.setAttribute("fill", "#ffffff");
      t.setAttribute("font-variant-numeric", "tabular-nums");
      t.textContent = p.slice(-3);
      t.classList.add("nw");
      svg.appendChild(t);
    });
  }

  // ---- Time slots
  function slotBtn(text) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", "false");
    b.setAttribute("aria-label", text);
    b.addEventListener("click", () => selectTime(text));
    return b;
  }
  const times = ["9:00 am", "10:30 am", "2:00 pm"];
  slots.replaceChildren(...times.map(slotBtn));

  function selectDate(date) {
    if (!date) return;
    sel.date = date;
    const y = date.getFullYear(), m = date.getMonth(), d = date.getDate();
    calendar.classList.remove("busy");
    slots.hidden = false;
    slotBtn("9:00 am").setAttribute("aria-pressed", "false");
    size.value = "S";
    const sizeEl = size.closest("[data-price]");
    sizeEl.querySelector("span").textContent = "Small";
    services.forEach((b) => b.textContent = prices.S[b.dataset.service]);
    sizeEl.querySelector("b").textContent = "£35";
    if (summary) summaryPrice.textContent = "£35";
    if (summaryDate) summaryDate.textContent = `${date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "long" })}`;
    if (action) action.textContent = "Change date";
    if (confirmCode) confirmCode.textContent = "";
    if (confirmMsg) confirmMsg.textContent = "";
    if (summaryTime) summaryTime.textContent = "";
    updateSummary();
  }

  function selectSize(size, text) {
    sel.size = size;
    if (summarySize) summarySize.textContent = text;
    const sizeEl = size.closest("[data-price]");
    services.forEach((b) => b.textContent = prices[size][b.dataset.service]);
    sizeEl.querySelector("b").textContent = prices[size].Wash.toFixed(0);
    if (summaryPrice) summaryPrice.textContent = prices[size].Wash.toFixed(0);
  }

  function selectService(b) {
    const sizeEl = b.closest("[data-price]");
    sel.service = b.dataset.service;
    services.forEach((s) => s.setAttribute("aria-pressed", String(s === b)));
    if (summaryService) summaryService.textContent = b.dataset.service.charAt(0).toUpperCase() + b.dataset.service.slice(2);
    if (summaryPrice) summaryPrice.textContent = prices[sel.size][sel.service].toFixed(0);
  }

  function selectTime(text) {
    sel.time = text;
    const b = slots.querySelector(`[data-time="${text.replace(/:| am/gi, "-")}"`);
    if (b) b.setAttribute("aria-pressed", "true");
    if (summaryTime) summaryTime.textContent = text;
    updateSummary();
  }

  function updateSummary() {
    if (summary) summaryTitle.textContent = sel.date ? "Booking confirmed" : "Choose a date";
    if (summarySize) summarySize.textContent = sel.size === "S" ? "Small" : sel.size === "M" ? "Medium" : sel.size === "L" ? "Large" : "Extra";
    if (summarySizeText) summarySizeText.textContent = sel.size === "S" ? "Up to 5 kg" : sel.size === "M" ? "5–15 kg" : sel.size === "L" ? "15–30 kg" : "30 kg+";
    if (summaryService) summaryService.textContent = sel.service.charAt(0).toUpperCase() + sel.service.slice(2);
    if (summaryDate) summaryDate.textContent = sel.date ? `${sel.date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "long" })}` : "Pick a date";
    if (summaryTime) summaryTime.textContent = sel.date && sel.time ? sel.time : "Pick a time";
    if (summaryPrice) summaryPrice.textContent = sel.date && sel.time ? prices[sel.size][sel.service].toFixed(0) : "£35";
    if (summary) summary.hidden = !sel.date;
    if (action) action.disabled = !sel.date;
  }

  // ---- Today + 4 weeks. Saturdays only, so the calendar is a grid of 28 cells.
  function renderCalendar() {
    const first = new Date(today.getFullYear(), today.getMonth(), 1);
    const daysToSkip = (first.getDay() + 6) % 7;
    let row = "";
    for (let i = 0; i < daysToSkip; i++) {
      row += `<th scope="col">&nbsp;</th>`;
    }
    for (let day = 0; day < 28; day++) {
      const d = new Date(today.getFullYear(), today.getMonth(), first.getDate() + daysToSkip + day);
      const label = d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "long" });
      if (d < today) continue;
      row += `<td data-day="${d.toDateString()}">${d.getDate()}</td>`;
    }
    calendar.innerHTML = `<thead><tr>${row}</tr></thead><tbody><tr>${row}</tr></tbody>`;
    todayCell = calendar.querySelector(`td[data-day="${today.toDateString()}"]`);
    if (todayCell) todayCell.classList.add("today");
    if (summaryDate) summaryDate.textContent = sel.date ? `${sel.date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "long" })}` : "Pick a date";
    let max = 0;
    if (summary) summary.hidden = !sel.date;
    if (action) action.disabled = !sel.date;
    for (const td of calendar.querySelectorAll("td")) {
      const d = new Date(td.dataset.day);
      td.classList.toggle("busy", d < today);
      td.classList.toggle("free", d >= today);
      if (todayCell && d.toDateString() === todayCell.dataset.day) max = d;
    }
    if (summaryTime) summaryTime.textContent = sel.date && sel.time ? sel.time : "Pick a time";
  }

  const todayCell = null;
  const sizeLabels = { S: "Small — up to 5 kg", M: "Medium — 5–15 kg", L: "Large — 15–30 kg", X: "Extra — 30 kg+" };
  const sizeElements = [...document.querySelectorAll("[data-price] [data-size]")];
  sizeElements.forEach((el) => {
    el.addEventListener("click", () => {
      const size = el.dataset.size;
      selectSize(size, sizeLabels[size]);
      if (size === "S") {
        for (const b of services) b.textContent = prices.S[b.dataset.service];
      } else if (size === "M") {
        for (const b of services) b.textContent = prices.M[b.dataset.service];
      } else if (size === "L") {
        for (const b of services) b.textContent = prices.L[b.dataset.service];
      } else if (size === "X") {
        for (const b of services) b.textContent = prices.X[b.dataset.service];
      }
      updateSummary();
    });
  });
  services.forEach((b) => b.addEventListener("click", () => selectService(b)));

  const next = document.getElementById("next");
  const back = document.getElementById("back");
  if (back) back.hidden = true;
  if (size) selectSize("S", sizeLabels.S);
  if (next) next.addEventListener("click", () => {
    const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 7);
    if (todayCell) todayCell.classList.remove("today");
    todayCell = null;
    renderCalendar();
    const y = d.getFullYear(), m = d.getMonth(), dDay = d.getDate();
    calendar.querySelectorAll("td").forEach((td) => {
      const tdD = new Date(td.dataset.day);
      td.classList.remove("today");
      if (tdD.getFullYear() === y && tdD.getMonth() === m && tdD.getDate() === dDay) {
        td.classList.add("today");
        td.focus();
        td.scrollIntoView({ block: "nearest" });
      }
    });
    if (back) back.hidden = false;
    if (next) next.hidden = true;
    action.setAttribute("aria-label", `Book for ${d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}`);
    if (summary) summary.hidden = true;
    if (action) action.disabled = true;
    if (confirmCode) confirmCode.textContent = "";
  });
  if (back) back.addEventListener("click", () => {
    if (todayCell) todayCell.classList.remove("today");
    todayCell = null;
    renderCalendar();
    if (back) back.hidden = true;
    if (next) next.hidden = false;
    if (summary) summary.hidden = false;
    if (action) action.disabled = false;
    if (confirmCode) confirmCode.textContent = "";
  });
  if (calendar) calendar.addEventListener("click", (e) => {
    const td = e.target.closest("td");
    if (!td) return;
    const d = new Date(td.dataset.day);
    if (todayCell && todayCell.dataset.day === td.dataset.day) return;
    if (todayCell) todayCell.classList.remove("today");
    todayCell = td;
    td.classList.add("today");
    selectDate(d);
    if (back) back.hidden = false;
    if (next) next.hidden = true;
    if (summary) summary.hidden = true;
    if (action) action.disabled = true;
  });

  // ---- Confirm
  const book = document.getElementById("book");
  if (book) book.addEventListener("click", (e) => {
    e.preventDefault();
    if (!sel.date || !sel.time) return;
    const code = Math.floor(10000 + Math.random() * 90000);
    if (confirmModal) confirmModal.showModal();
    if (confirmCode) confirmCode.textContent = code;
    if (confirmMsg) confirmMsg.textContent = `£${prices[sel.size][sel.service]} for ${sizeLabels[sel.size]} · ${sel.time} on ${sel.date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "long" })}.`;
    if (summary) summary.hidden = false;
  });
  if (confirmClose) confirmClose.addEventListener("click", () => confirmModal.close());
  if (confirmModal) confirmModal.addEventListener("close", () => {
    if (todayCell) todayCell.classList.remove("today");
    todayCell = null;
    renderCalendar();
    if (back) back.hidden = true;
    if (next) next.hidden = false;
    if (summary) summary.hidden = false;
    if (action) action.disabled = false;
    if (confirmCode) confirmCode.textContent = "";
    if (confirmMsg) confirmMsg.textContent = "";
  });
  renderCalendar();
})();
