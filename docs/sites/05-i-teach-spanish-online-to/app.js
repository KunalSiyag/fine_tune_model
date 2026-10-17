// Spanish Ascent — package cards, level quiz.
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  /* ---------- swap in the level-results panel ---------- */
  const quizForm = $('#quizForm');
  const resultsPanel = $('#resultsPanel');
  const scoreEl = $('#score');
  const scoreText = $('#scoreText');
  let score = 0;

  function showResults() {
    resultsPanel.hidden = false;
    quizForm.hidden = true;
    quizForm.querySelectorAll('input[type=radio]').forEach((r) => r.disabled = true);
    resultsPanel.classList.remove('quiz__results--hidden');
    resultsPanel.classList.add('quiz__results--active');
    scoreEl.textContent = `${score} / 5`;
    const text = score >= 3 ? 'You’d start at A1.' : 'You’d start at A2.';
    scoreText.textContent = text;
    quizForm.reset();
  }

  function hideResults() {
    resultsPanel.classList.remove('quiz__results--active');
    resultsPanel.classList.add('quiz__results--hidden');
    quizForm.hidden = false;
    quizForm.querySelectorAll('input[type=radio]').forEach((r) => r.disabled = false);
    $$('input[type=radio]').forEach((r) => r.checked = false);
    scoreEl.textContent = '0 / 5';
    scoreText.textContent = 'Correct: 0 / 5';
  }

  if (quizForm && resultsPanel) {
    quizForm.addEventListener('change', () => {
      const correct = $$('input[name=q]:checked', quizForm).map((r) => +r.value).filter((v) => v === 1);
      score = correct.reduce((s, v) => s + v, 0);
      scoreEl.textContent = `${score} / 5`;
      scoreText.textContent = `Correct: ${correct.length} / 5`;
    });
    const btn = $('#nextBtn');
    const startBtn = $('#startHereBtn');
    if (startBtn) startBtn.disabled = false;
    quizForm.addEventListener('submit', (e) => {
      e.preventDefault();
      if (!quizForm.checkValidity()) {
        btn.textContent = 'Try again';
        btn.disabled = false;
        quizForm.querySelector('input:not(:disabled):checked').closest('.quiz__question').scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
        return;
      }
      btn.disabled = true;
      setTimeout(showResults, 350);
      if (startBtn) startBtn.disabled = true;
    });
    btn.addEventListener('click', () => {
      hideResults();
      btn.disabled = false;
      const question = quizForm.querySelector('.quiz__question');
      if (question) question.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
    });
  }

  /* ---------- package cards: rotate each card a little further down the track ---------- */
  const packs = $$('.pack');
  if (packs.length > 0 && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        const p = en.target;
        if (en.isIntersecting) {
          io.unobserve(p);
          p.style.setProperty('--rotate', reduce ? '0deg' : (p.getBoundingClientRect().top < p.offsetHeight ? '0.5deg' : '-0.5deg'));
        }
      });
    }, { threshold: 0.3 });
    packs.forEach((p) => io.observe(p));
  }
})();
