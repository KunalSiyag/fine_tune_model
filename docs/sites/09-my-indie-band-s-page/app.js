(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fine = matchMedia('(hover: hover) and (pointer: fine)').matches;
  const links = document.querySelectorAll('.ep-links a');
  const listen = document.getElementById('listen');
  const tlist = document.getElementById('tlist');
  const announce = document.getElementById('announce');
  const countdown = document.getElementById('countdown');
  const subscribe = document.getElementById('subscribe');
  const range = document.getElementById('range');
  const status = document.getElementById('status');
  const label = document.getElementById('label');

  if (tlist) {
    tlist.innerHTML = '<div class="tlist"><button type="button" aria-expanded="false"><span aria-hidden="true">01</span><span>Fallout</span><span>02:31</span><p><i>Every signal you gave me was a static storm.</i></p></button><button type="button" aria-expanded="false"><span aria-hidden="true">02</span><span>Electric Waste</span><span>04:19</span><p>Cigarette wrappers in a landfill, burning your name into every page.</p></button><button type="button" aria-expanded="false"><span aria-hidden="true">03</span><span>Neon Sun</span><span>03:08</span><p><i>It rises in my bedroom, never in the sky.</i></p></button><button type="button" aria-expanded="false"><span aria-hidden="true">04</span><span>Static Beach</span><span>02:57</span><p>Fourteen minutes of waves and a single, looping birdcall.</p></button><button type="button" aria-expanded="false"><span aria-hidden="true">05</span><span>Sand in the Speakers</span><span>03:46</span><p><i>We fought in sound. Now it’s all I can hear.</i></p></button></div>';
    const buttons = tlist.querySelectorAll('button');
    buttons.forEach(b => {
      b.addEventListener('click', () => {
        const open = b.getAttribute('aria-expanded') !== 'true';
        b.setAttribute('aria-expanded', String(open));
        buttons.forEach(other => {
          if (other !== b) other.setAttribute('aria-expanded', 'false');
        });
      });
    });
  }

  if (listen && announce && countdown && subscribe && range && status) {
    const count = { days: 0, hours: 0, minutes: 0, seconds: 0 };
    const pad = n => String(n).padStart(2, '0');
    const tick = () => {
      const now = new Date();
      const end = new Date('2026-11-15T00:00:00-05:00');
      const left = end - now;
      if (left <= 0) {
        countdown.hidden = true;
        announce.style.opacity = '1';
        announce.style.pointerEvents = 'auto';
        announce.textContent = 'November EP Drop · 3:02 PM EST';
        announce.querySelector('time').textContent = '2026-11-15';
        announce.querySelector('span').textContent = 'EP out now';
      } else {
        count.days = Math.floor(left / 864e5);
        count.hours = Math.floor((left % 864e5) / 36e5);
        count.minutes = Math.floor((left % 36e5) / 6e1);
        count.seconds = Math.floor((left % 6e1) / 1e3);
        countdown.textContent = `${pad(count.hours)}:${pad(count.minutes)}:${pad(count.seconds)}`;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);

    const AC = window.AudioContext || window.webkitAudioContext;
    let ac = null;
    let source = null;
    function play() {
      if (!ac) try { ac = new AC(); } catch (e) { return; }
      if (ac.state === 'suspended') ac.resume();
      if (source) source.stop();
      source = ac.createBufferSource();
      const noise = ac.createBuffer(2, 44100 * 15, 44100);
      const data = noise.getChannelData(0);
      for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * 0.08; // gallery copy: full-scale white noise turned down
      source.buffer = noise;
      source.connect(ac.destination);
      source.start(0);
    }
    listen.addEventListener('click', () => {
      play();
    });
    listen.setAttribute('aria-pressed', 'false');

    subscribe.addEventListener('submit', e => {
      e.preventDefault();
      subscribe.querySelector('input').disabled = true;
      status.textContent = 'Signal Locked. You’re on the list.';
      status.style.opacity = 1;
      setTimeout(() => {
        status.style.opacity = 0;
        setTimeout(() => { subscribe.querySelector('input').disabled = false; label.hidden = false; }, 450);
      }, 1800);
    });

    if (fine && !reduce) {
      links.forEach(link => link.setAttribute('tabindex', '-1'));
      links.forEach((link, i) => {
        const target = document.querySelector(link.getAttribute('href'));
        link.addEventListener('mouseenter', () => {
          if (!target) return;
          target.setAttribute('style', 'animation:open .45s ease forwards');
          const rect = target.getBoundingClientRect();
          const d = document.documentElement;
          const x = rect.left + rect.width / 2 - d.scrollLeft - d.clientWidth / 2;
          const y = rect.top + rect.height / 2 - d.scrollTop - d.clientHeight / 2;
          target.setAttribute('style', `animation:open .45s ease forwards; transform: translate(${x}px, ${y}px)`);
        });
        link.addEventListener('mouseleave', () => { target.removeAttribute('style'); });
        link.addEventListener('focus', () => { target.setAttribute('style', 'background:rgba(255,255,255,.08);'); });
        link.addEventListener('blur', () => { target.removeAttribute('style'); });
      });
    }
  }
})();
