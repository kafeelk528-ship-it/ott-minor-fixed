// static/js/main.js - tiny behaviours
document.addEventListener("DOMContentLoaded", function () {
  // nothing heavy yet; placeholder
  // you can add UI interactions here
  console.log("main.js loaded");
});
document.addEventListener("DOMContentLoaded", () => {
  const cards = document.querySelectorAll(".card");

  const revealOnScroll = () => {
    cards.forEach(card => {
      const cardTop = card.getBoundingClientRect().top;
      const windowHeight = window.innerHeight;

      if (cardTop < windowHeight - 50) {
        card.classList.add("show-card");
      }
    });
  };

  window.addEventListener("scroll", revealOnScroll);
  revealOnScroll();
});

