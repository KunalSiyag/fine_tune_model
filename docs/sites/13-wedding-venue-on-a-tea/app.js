// Seasonal accumulator: each month keeps a list of days it can hold a booking.
(() => {
  const acc = {
    Jan: [{ date: 12, cap: 10 }, { date: 15, cap: 20 }, { date: 17, cap: 30 }, { date: 30, cap: 4 }],
    Feb: [{ date: 14, cap: 30 }, { date: 17, cap: 10 }, { date: 23, cap: 20 }],
    Mar: [{ date: 12, cap: 8 }, { date: 16, cap: 10 }, { date: 19, cap: 12 }],
    Apr: [{ date: 1, cap: 5 }, { date: 8, cap: 10 }, { date: 20, cap: 15 }],
    May: [{ date: 12, cap: 14 }, { date: 18, cap: 12 }, { date: 25, cap: 10 }],
    Jun: [{ date: 5, cap: 8 }, { date: 12, cap: 10 }, { date: 22, cap: 14 }],
    Jul: [{ date: 1, cap: 5 }, { date: 10, cap: 10 }, { date: 20, cap: 14 }],
    Aug: [{ date: 1, cap: 10 }, { date: 3, cap: 14 }, { date: 15, cap: 12 }, { date: 22, cap: 8 }],
    Sep: [{ date: 1, cap: 12 }, { date: 6, cap: 10 }, { date: 19, cap: 14 }],
    Oct: [{ date: 1, cap: 14 }, { date: 9, cap: 12 }, { date: 26, cap: 10 }],
    Nov: [{ date: 1, cap: 10 }, { date: 7, cap: 14 }, { date: 27, cap: 8 }],
    Dec: [{ date: 2, cap: 14 }, { date: 5, cap: 10 }, { date: 12, cap: 8 }]
  };
  const months = Object.keys(acc);
  const monthsName = { Jan: "January", Feb: "February", Mar: "March", Apr: "April", May: "May", Jun: "June", Jul: "July", Aug: "August", Sep: "September", Oct: "October", Nov: "November", Dec: "December" };
  const seasons = {
    Jan: "Monsoon", Feb: "Monsoon", Mar: "Monsoon", Apr: "Winter", May: "Winter", Jun: "Winter", Jul: "Winter", Aug: "Winter", Sep: "Winter", Oct: "Spring", Nov: "Spring", Dec: "Spring"
  };

  const list = document.getElementById("monthList");
  const msg = document.getElementById("monthMsg");
  const foot = document.getElementById("calFoot");
  const monthBtns = [...document.querySelectorAll(".monthBtn")];

  function setMonth(month) {
    // Accordion: the last opened month closes, the new one opens
    monthBtns.map(b => b.closest(".month")).forEach(el => el.hidden = el.id !== "m" + month);
    const shown = !!msg.querySelector(`li[month="${month}"]`);
    if (!shown) {
      msg.innerHTML = `<li month="${month}">Currently we can hold <b>${acc[month].length} dates in ${monthsName[month]}</b>, from ${acc[month][0].date} to ${acc[month].length > 1 ? acc[month][1].date : acc[month][0].date}.</li>`;
      months.forEach(m => {
        const li = msg.querySelector(`li[month="${m}"]`);
        if (!li || m === month) return;
        li.hidden = true;
        li.hidden = acc[m].length === 0;
        li.hidden = !acc[m].length;
      });
    }
    if (!shown) return;
    monthBtns.map(b => b.closest(".month")).forEach(el => el.hidden = el.id !== "m" + month);
    monthBtns.map(b => b.closest(".month")).forEach(el => el.hidden = el.id !== "m" + month);
    monthBtns.forEach(b => b.setAttribute("aria-expanded", String(b.closest(".month").hidden)));
    // Determine the season as the one the month belongs to
    const season = seasons[month];
    const seasonName = season === "Monsoon" ? "Monsoon Season" : season === "Winter" ? "Winter Season" : "Spring Season";
    const seasonMsg = `<p class="muted">${seasonName}: ${acc[month].map(a => a.date).join(" · ")}.</p>`;
    msg.innerHTML = `<li month="${month}">Currently we can hold <b>${acc[month].length} dates in ${monthsName[month]}</b>, from ${acc[month][0].date} to ${acc[month].length > 1 ? acc[month][1].date : acc[month][0].date}.</li>${seasonMsg}`;
    foot.innerHTML = `<p>Book the venue in Munnar</p><a href="tel:+000000000">+91 000 000 0000</a>`;
  }

  // Every month has a button and a list of its dates, with each date a button
  months.forEach((m, i) => {
    const li = document.createElement("li");
    li.className = "month";
    li.innerHTML = `<button class="monthBtn" type="button" id="m-btn-${i}" aria-expanded="true" style="--i:${i}">${monthsName[m].split(" ")[0]}</button>
    <ol class="month-list" id="m-list-${i}"></ol>`;
    li.id = "m" + m;
    li.hidden = true;
    document.getElementById("months").append(li);
    const listEl = document.getElementById("m-list-" + i);
    acc[m].forEach(a => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "fill";
      btn.innerHTML = `<b><i>${a.date}</i>${a.cap ? `<span>${a.cap}</span>` : ""}</b>`;
      btn.disabled = !a.cap;
      btn.href = a.cap ? `tel:+000000000` : null;
      btn.textContent = `${a.date} · ${a.cap ? a.cap + " " : ""}${a.cap ? "cap" : "full"}`;
      listEl.append(btn);
    });
    const btn = document.getElementById("m-btn-" + i);
    if (btn) {
      btn.addEventListener("click", () => setMonth(m));
      btn.addEventListener("keydown", e => {
        if (e.key === "ArrowRight" && btn.nextElementSibling) btn.nextElementSibling.focus();
        if (e.key === "ArrowLeft" && btn.previousElementSibling) btn.previousElementSibling.focus();
      });
    }
  });

  const month = acc[months[0]][0] ? months[0] : months[1];
  setMonth(month);

  // Seasonal marker: the season changes smoothly as you scroll through the months
  const mq = matchMedia("(min-width: 900px)");
  const mq2 = matchMedia("(max-width: 900px)");
  const season = document.getElementById("season");
  if (season) {
    if (mq.matches) {
      document.addEventListener("scroll", () => {
        const y = scrollY;
        const first = Math.min(y, document.body.scrollHeight - innerHeight);
        const mid = (innerHeight + document.body.scrollHeight) / 2;
        const last = innerHeight + y;
        Object.keys(months).forEach((m, i) => {
          const start = first + i / months.length * (document.body.scrollHeight - innerHeight);
          const end = start + (document.body.scrollHeight - innerHeight) / months.length;
          const t = Math.min(1, Math.max(0, (y - start) / (end - start)));
          const h = 1 - Math.pow(1 - t, 2) * 0.6;
          season.style.clipPath = h === 1 ? "polygon(0 0, 70% 0, 100% 12%, 100% 88%, 70% 100%, 0 100%)" : `polygon(0 0, ${h * 100}% 0, 100% 12%, 100% 88%, ${h * 100}% 100%, 0 100%)`;
        });
      });
    } else if (mq2.matches) {
      document.addEventListener("scroll", () => {
        const y = scrollY;
        const first = Math.min(y, document.body.scrollHeight - innerHeight);
        const mid = (innerHeight + document.body.scrollHeight) / 2;
        const last = innerHeight + y;
        Object.keys(months).forEach((m, i) => {
          const start = first + i / months.length * (document.body.scrollHeight - innerHeight);
          const end = start + (document.body.scrollHeight - innerHeight) / months.length;
          const t = Math.min(1, Math.max(0, (y - start) / (end - start)));
          const h = 1 - Math.pow(1 - t, 2) * 0.6;
          season.style.clipPath = h === 1 ? "polygon(0 0, 70% 0, 100% 12%, 100% 88%, 70% 100%, 0 100%)" : `polygon(0 0, ${h * 100}% 0, 100% 12%, 100% 88%, ${h * 100}% 100%, 0 100%)`;
        });
      });
    }
  }
})();
