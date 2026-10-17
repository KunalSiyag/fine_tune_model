(() => {
  const list = [...document.querySelectorAll('.acc .list')];
  const items = [...document.querySelectorAll('.book')];
  const slides = [...document.querySelectorAll('.slide')];
  const buttons = [...document.querySelectorAll('.nav button')];
  const nav = document.querySelector('.nav');
  const msg = document.getElementById('msg');
  const form = document.getElementById('form');

  /* ---------- accordion ---------- */
  const accOpen = (h3) => {
    const open = !h3.getAttribute('aria-expanded');
    h3.setAttribute('aria-expanded', open ? 'true' : 'false');
    h3.setAttribute('aria-controls', open ? h3.getAttribute('aria-controls') : '');
    if (open) h3.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };
  list.forEach((group) => {
    const h3 = group.querySelector('.acc h3');
    const items = [...group.querySelectorAll('.book')];
    h3.addEventListener('click', () => accOpen(h3));
    group.addEventListener('keydown', (e) => {
      const focusable = items.filter((b) => !b.hidden);
      let i = focusable.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') i = (i + 1) % focusable.length;
      else if (e.key === 'ArrowUp') i = (i - 1 + focusable.length) % focusable.length;
      else return;
      focusable[i].focus();
      e.preventDefault();
    });
  });
  items.forEach((b) => b.addEventListener('click', () => {
    const h3 = b.closest('.acc').querySelector('h3');
    if (h3) h3.focus();
  }));
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        const h3 = e.target.querySelector('h3');
        if (h3 && e.isIntersecting) accOpen(h3);
      });
    }, { rootMargin: '0px 0px -8% 0px' });
    document.querySelectorAll('.acc').forEach((acc) => io.observe(acc));
  }

  /* ---------- carousel ---------- */
  if (!navigation || !slides.length) return;
  let i = 0;
  slides.forEach((s) => {
    const sky = s.querySelector('.sky');
    if (sky) sky.setAttribute('points', (sky.getAttribute('points') || '0 0 100 85 100 20 0 20').split(' '));
  });
  const next = () => {
    i = (i + 1) % slides.length;
    requestAnimationFrame(() => {
      if (nav) nav.style.transform = `translateX(${-i * 100}%)`;
    });
  };
  buttons.forEach((b) => {
    b.addEventListener('click', () => {
      i = +b.getAttribute('data-dir');
      requestAnimationFrame(() => {
        if (nav) nav.style.transform = `translateX(${-i * 100}%)`;
      });
    });
  });
  slides.forEach((s, n) => {
    const t = s.querySelector('h3');
    if (t) t.textContent = 'Dhaka Text Exchange · ' + t.textContent;
    s.setAttribute('aria-label', t ? 'Slide ' + (n + 1) + ' of ' + slides.length + ': ' + t.textContent + ', Dhaka Text Exchange' : 'Slide ' + (n + 1) + ' of ' + slides.length);
  });
  setInterval(next, 6000);

  /* ---------- footer form ---------- */
  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    const email = form.email.value.trim();
    const subject = form.subject.value.trim();
    const ok = email && subject && msg;
    if (!ok) {
      msg.className = 'msg is-error';
      msg.textContent = ok ? '' : 'Enter email and subject before sending.';
      form.email.setAttribute('aria-invalid', !email ? 'true' : 'false');
      form.subject.setAttribute('aria-invalid', !subject ? 'true' : 'false');
      form.email.focus();
      return;
    }
    const name = email.split('@')[0];
    msg.className = 'msg is-ok';
    msg.textContent = `${name}, thanks for the message. We'll reply to ${email} within 2 working days.`;
    form.email.value = '';
    form.subject.value = '';
  });
})();
