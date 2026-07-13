/* Site effects — loaded as an external, fingerprinted file served from 'self'
   (allowed by script-src 'self'), so it never touches the hash-locked CSP.
   Everything degrades gracefully; motion-heavy bits respect reduced-motion. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* 1 — Cursor spotlight on the Recent Work cards (motion; skip if reduced). */
  if (!reduce) {
    document.querySelectorAll(".featured-card").forEach(function (card) {
      card.addEventListener("pointermove", function (e) {
        var r = card.getBoundingClientRect();
        card.style.setProperty("--mx", ((e.clientX - r.left) / r.width * 100) + "%");
        card.style.setProperty("--my", ((e.clientY - r.top) / r.height * 100) + "%");
      });
    });
  }

  /* 2 — Scroll-spy: highlight the TOC entry for the section you're reading. */
  var tocLinks = document.querySelectorAll(".toc .inner a[href^='#']");
  if (tocLinks.length && "IntersectionObserver" in window) {
    var map = {};
    tocLinks.forEach(function (a) {
      var id = decodeURIComponent(a.getAttribute("href").slice(1));
      if (id) map[id] = a;
    });
    var heads = Object.keys(map)
      .map(function (id) { return document.getElementById(id); })
      .filter(Boolean);
    if (heads.length) {
      var spy = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          tocLinks.forEach(function (a) { a.classList.remove("active"); });
          var a = map[en.target.id];
          if (a) a.classList.add("active");
        });
      }, { rootMargin: "0px 0px -78% 0px", threshold: 0 });
      heads.forEach(function (h) { spy.observe(h); });
    }
  }

  /* 3 — Home stat counters count up when they scroll into view. */
  var statWrap = document.querySelector(".home-stats");
  if (statWrap && "IntersectionObserver" in window) {
    var nums = statWrap.querySelectorAll(".stat-num");
    var counted = false;
    var so = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting || counted) return;
        counted = true;
        nums.forEach(function (el) {
          var target = parseInt(el.getAttribute("data-target"), 10) || 0;
          if (reduce) { el.textContent = target.toLocaleString(); return; }
          var start = performance.now(), dur = 1300;
          (function tick(now) {
            var p = Math.min((now - start) / dur, 1);
            var eased = 1 - Math.pow(1 - p, 3);
            el.textContent = Math.round(target * eased).toLocaleString();
            if (p < 1) requestAnimationFrame(tick);
          })(start);
        });
      });
    }, { threshold: 0.4 });
    so.observe(statWrap);
  }

  /* 4 — Konami code easter egg: up up down down left right left right B A. */
  var seq = ["arrowup", "arrowup", "arrowdown", "arrowdown",
             "arrowleft", "arrowright", "arrowleft", "arrowright", "b", "a"];
  var pos = 0;
  document.addEventListener("keydown", function (e) {
    var k = (e.key || "").toLowerCase();
    if (k === seq[pos]) {
      pos++;
      if (pos === seq.length) { pos = 0; konami(); }
    } else {
      pos = (k === seq[0]) ? 1 : 0;
    }
  });
  function konami() {
    if (document.querySelector(".konami-toast")) return;
    var toast = document.createElement("div");
    toast.className = "konami-toast";
    toast.textContent = "⚡ GOD MODE ⚡";
    document.body.appendChild(toast);
    if (!reduce) document.body.classList.add("konami-shake");
    setTimeout(function () {
      toast.classList.add("konami-out");
      document.body.classList.remove("konami-shake");
    }, 2200);
    setTimeout(function () { if (toast.parentNode) toast.remove(); }, 2900);
  }
})();
