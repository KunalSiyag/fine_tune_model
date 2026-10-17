(() => {
  const form = document.getElementById("form");
  if (!form) return;
  const count = document.getElementById("count");
  if (!count) return;

  const slots = 6;
  let left = slots;
  const dates = ["Oct 12", "Oct 19", "Oct 26"];
  const dateEl = form.querySelector("#date");
  const state = { booking: false, done: false };

  function render() {
    if (count) count.textContent = left === 1 ? "1 slot left" : `${left} slots left`;
    if (state.done) {
      form.classList.remove("in");
      form.setAttribute("aria-hidden", "true");
      document.body.classList.remove("loading");
    }
  }

  function book() {
    const idx = parseInt(dateEl.value, 10);
    const date = dates[idx];
    const pay = form.querySelector("#pay");
    if (!pay) return;
    const receiptEl = document.getElementById("receipt");
    if (receiptEl) receiptEl.hidden = false;

    state.booking = true;
    form.classList.add("in");
    form.setAttribute("aria-hidden", "true");
    document.body.classList.add("loading");

    setTimeout(() => {
      state.booking = false;
      state.done = true;
      form.replaceChildren(
        document.createElement("p"),
        document.createElement("button")
      );
      const text = document.createElement("p");
      text.textContent = `We've booked you for Wheel & Wander on ${date}, 10:00am. See you at the wheel.`;
      text.id = "thanks";
      const again = document.createElement("button");
      again.type = "button";
      again.textContent = "Book another date";
      again.addEventListener("click", () => {
        state.done = false;
        form.replaceChildren(...[...form.children].reverse());
        dateEl.value = "0";
        render();
        form.focus();
        if (count) count.textContent = `${left} slots left`;
        if (receiptEl) receiptEl.hidden = true;
      });
      form.append(text, again);
    }, 700);
  }

  // availability: the booking button reveals the count and lets people book
  form.addEventListener("change", (e) => {
    if (e.target.id !== "date") return;
    if (state.done) return;
    if (count) count.textContent = `${left} slots left`;
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (!dateEl.value || dateEl.value === "0") return;
    if (state.booking || state.done) return;
    if (left <= 0) {
      if (count) count.textContent = "The weekend is full. Join the waitlist.";
      return;
    }
    if (left === 1) {
      const last = count;
      if (last) last.textContent = "One slot left.";
    }
    left--;
    render();
    book();
  });

  // the receipts load into the page as the form fades out
  if (count) count.textContent = `${left} slots left`;
  document.querySelectorAll(".receipt").forEach((r) => r.hidden = true);
})();
