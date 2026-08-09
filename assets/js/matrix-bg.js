/* RAINBOW MATRIX site background — the same rain that runs behind the home lab
 * dashboard (~/homepage/config/custom.js), ported to sit behind this site.
 *
 * Loaded only on pages without a video background (see extend_footer.html), where it
 * replaces the WebGL fbm shader. The parameters are the dashboard's, unchanged, because
 * they were already tuned for a full-screen canvas that must not cost anything:
 *   - ~15fps, not 60
 *   - a 0.65 backing store, upscaled by the browser (0.65^2 = 42% of the pixels)
 *   - no shadowBlur; the upscale supplies the bloom
 *
 * Rules it keeps from the original:
 *   - wrapped so a failure here can never stop the page rendering
 *   - the canvas is aria-hidden and pointer-events:none via CSS, so it can never
 *     swallow a click or reach a screen reader
 *   - stops drawing when the tab is hidden
 *   - honours prefers-reduced-motion by painting one static frame instead of animating
 *
 * Kill switch: append ?norain to the URL, or set localStorage.matrixRain = "off".
 */
(function () {
  "use strict";

  try {
    if (window.__rainbowMatrixBg) return;
    window.__rainbowMatrixBg = true;

    var canvas = document.getElementById("matrix-bg");
    if (!canvas) return;

    var off =
      /[?&]norain\b/.test(window.location.search) ||
      (function () {
        try {
          return window.localStorage.getItem("matrixRain") === "off";
        } catch (e) {
          return false;
        }
      })();
    if (off) return;

    var reduceMotion =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    var GLYPHS =
      "アイウエオカキクケコサシス" +
      "セソタチツテトナニヌネノハ" +
      "ヒフヘホマミムメモヤユヨラ" +
      "リルレロワヲン" +
      "0123456789<>[]{}/\\=+*#$%&@";

    var FONT_SIZE = 18;
    var FRAME_MS = 66;        // ~15fps
    var RENDER_SCALE = 0.65;

    var ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    var width = 0;
    var height = 0;
    var columns = 0;
    var drops = [];
    var speeds = [];
    var hues = [];

    function seed() {
      // Deliberately ignores devicePixelRatio — a sharper canvas buys nothing behind a
      // dark overlay and costs 4x the pixels on a HiDPI screen.
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.max(1, Math.floor(width * RENDER_SCALE));
      canvas.height = Math.max(1, Math.floor(height * RENDER_SCALE));
      canvas.style.width = width + "px";
      canvas.style.height = height + "px";
      ctx.setTransform(RENDER_SCALE, 0, 0, RENDER_SCALE, 0, 0);

      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, width, height);

      columns = Math.max(1, Math.ceil(width / FONT_SIZE));
      drops = new Array(columns);
      speeds = new Array(columns);
      hues = new Array(columns);
      for (var i = 0; i < columns; i++) {
        drops[i] = Math.random() * (height / FONT_SIZE);
        speeds[i] = 0.6 + Math.random() * 0.8;
        // Spread the spectrum across the screen, then let it drift over time.
        hues[i] = ((i / columns) * 360 + Math.random() * 24) % 360;
      }
    }

    function glyph() {
      return GLYPHS.charAt((Math.random() * GLYPHS.length) | 0);
    }

    var drift = 0;

    function draw() {
      // Translucent black over the last frame: this is what leaves the trails.
      ctx.fillStyle = "rgba(0, 0, 0, 0.13)";
      ctx.fillRect(0, 0, width, height);

      ctx.font =
        FONT_SIZE + "px 'JetBrains Mono', 'Noto Sans CJK JP', 'DejaVu Sans Mono', monospace";
      ctx.textBaseline = "top";

      for (var i = 0; i < columns; i++) {
        var x = i * FONT_SIZE;
        // Quantised to the cell grid: a fractional speed would repaint the same cell on
        // consecutive frames and the column turns into a solid bar.
        var y = Math.floor(drops[i]) * FONT_SIZE;
        var h = (hues[i] + drift) % 360;

        ctx.fillStyle = "hsla(" + h + ", 100%, 55%, 0.55)";
        ctx.fillText(glyph(), x, y);

        // Bright head, one cell down.
        ctx.fillStyle = "hsla(" + h + ", 100%, 88%, 0.85)";
        ctx.fillText(glyph(), x, y + FONT_SIZE);

        drops[i] += speeds[i];
        if (y > height && Math.random() > 0.972) {
          drops[i] = -Math.random() * 12;
          speeds[i] = 0.6 + Math.random() * 0.8;
        }
      }

      drift = (drift + 0.35) % 360;
    }

    var last = 0;
    var rafId = null;

    function loop(now) {
      rafId = window.requestAnimationFrame(loop);
      if (document.hidden) return;
      if (now - last < FRAME_MS) return;
      last = now;
      draw();
    }

    function start() {
      seed();

      // Warm-up: the trails are built by fading previous frames, so frame one is almost
      // black. Run a burst synchronously first, otherwise the page loads onto an empty
      // background and the rain fades in a second late.
      for (var n = 0; n < 26; n++) draw();

      if (reduceMotion) return; // static frame only — no rAF loop at all
      if (rafId === null) rafId = window.requestAnimationFrame(loop);
    }

    var resizeTimer = null;
    window.addEventListener("resize", function () {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(function () {
        try {
          seed();
        } catch (e) {
          /* leave the last good frame up */
        }
      }, 200);
    });

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
      start();
    }
  } catch (e) {
    // Deliberately silent in the UI; the page keeps working without rain.
    if (window.console && console.warn) console.warn("[rainbow-matrix] disabled:", e);
  }
})();
