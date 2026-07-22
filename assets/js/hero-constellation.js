/* Hero network constellation — drifting red nodes joined by faint links, drawn
   on a 2D canvas behind the hero title. Reads as deep space + a network graph,
   tying the astronaut hero to the blog's networking/security theme. External +
   fingerprinted (script-src 'self'), so the hash-locked CSP is untouched.
   Reduced-motion: paints one static frame, no animation. Pauses when the hero
   is off-screen or the tab is hidden. */
(function () {
  "use strict";
  var canvas = document.getElementById("hero-constellation");
  if (!canvas) return;
  var hero = canvas.closest(".site-hero");
  if (!hero) return;
  var ctx = canvas.getContext("2d");
  if (!ctx) return;

  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var RED = "232,26,26";       // blog #E81A1A
  var GLOW = "255,72,72";      // brighter core

  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  var W = 0, H = 0, nodes = [], linkDist = 0;

  function nodeCount() {
    // scale with area, capped for performance / visual calm
    var n = Math.round((canvas.offsetWidth * canvas.offsetHeight) / 34000);
    return Math.max(8, Math.min(n, 26));
  }

  function build() {
    W = canvas.offsetWidth; H = canvas.offsetHeight;
    canvas.width = Math.max(1, Math.round(W * dpr));
    canvas.height = Math.max(1, Math.round(H * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    linkDist = Math.min(W, H) * 0.22;
    var count = nodeCount();
    nodes = [];
    for (var i = 0; i < count; i++) {
      nodes.push({
        x: Math.random() * W,
        y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        r: 1.1 + Math.random() * 1.8,
        tw: Math.random() * Math.PI * 2   // twinkle phase
      });
    }
  }

  function draw(now) {
    ctx.clearRect(0, 0, W, H);
    var i, j, a, b;

    // links first, so nodes sit on top
    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      for (j = i + 1; j < nodes.length; j++) {
        b = nodes[j];
        var dx = a.x - b.x, dy = a.y - b.y;
        var d = Math.sqrt(dx * dx + dy * dy);
        if (d < linkDist) {
          var o = (1 - d / linkDist) * 0.5;
          ctx.strokeStyle = "rgba(" + RED + "," + o.toFixed(3) + ")";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }

    // nodes as glowing dots
    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      var tw = 0.6 + 0.4 * Math.sin((now || 0) * 0.001 + a.tw);
      ctx.beginPath();
      ctx.arc(a.x, a.y, a.r + 2.5, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(" + RED + "," + (0.12 * tw).toFixed(3) + ")";  // halo
      ctx.fill();
      ctx.beginPath();
      ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(" + GLOW + "," + (0.85 * tw).toFixed(3) + ")";  // core
      ctx.fill();
    }
  }

  function step(a) {
    a.x += a.vx; a.y += a.vy;
    if (a.x < 0 || a.x > W) a.vx *= -1;
    if (a.y < 0 || a.y > H) a.vy *= -1;
    a.x = Math.max(0, Math.min(W, a.x));
    a.y = Math.max(0, Math.min(H, a.y));
  }

  build();
  window.addEventListener("resize", build);
  hero.classList.add("constellation-on"); // fade the canvas in

  if (reduce) { draw(0); return; }

  var inView = true;
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { inView = en.isIntersecting; });
    }, { threshold: 0.01 }).observe(hero);
  }

  var last = 0;
  (function loop(now) {
    requestAnimationFrame(loop);
    if (document.hidden || !inView) return;
    if (now - last < 33) return;   // ~30fps
    last = now;
    for (var i = 0; i < nodes.length; i++) step(nodes[i]);
    draw(now);
  })(0);
})();
