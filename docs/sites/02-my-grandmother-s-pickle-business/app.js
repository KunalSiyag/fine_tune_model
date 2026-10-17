(() => {
  const btn = document.querySelector(".ord .btn");

  if (btn && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      if (!entries[0].isIntersecting) btn.style.background = "";
    }, { rootMargin: "0px 0px -8% 0px" });
    io.observe(btn);
  }
})();
