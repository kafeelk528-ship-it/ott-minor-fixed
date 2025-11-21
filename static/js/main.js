// static/js/main.js - stable animation + safe behaviour

document.addEventListener("DOMContentLoaded", function () {
  console.log("main.js loaded");

  const cards = document.querySelectorAll(".card");

  const revealOnScroll = () => {
    cards.forEach(card => {
      const cardTop = card.getBoundingClientRect().top;
      const windowHeight = window.innerHeight;

      if (cardTop < windowHeight - 50) {
        card.classList.add("show-card");
      } else {
        card.classList.remove("show-card");
      }
    });
  };

  window.addEventListener("scroll", revealOnScroll);
  revealOnScroll(); // run on load
});
