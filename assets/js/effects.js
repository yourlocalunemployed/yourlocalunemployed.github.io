/* Cursor spotlight for the Recent Work cards.
   Feeds --mx/--my (percentages) to the .featured-card::after radial glow.
   Loaded as an external, fingerprinted file so it stays clear of the
   hash-locked script-src. Setting element.style is a style attribute, which
   the CSP's style-src 'unsafe-inline' already permits. No-ops with no cards. */
(function () {
  "use strict";
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  var cards = document.querySelectorAll(".featured-card");
  cards.forEach(function (card) {
    card.addEventListener("pointermove", function (e) {
      var r = card.getBoundingClientRect();
      card.style.setProperty("--mx", ((e.clientX - r.left) / r.width * 100) + "%");
      card.style.setProperty("--my", ((e.clientY - r.top) / r.height * 100) + "%");
    });
  });
})();
