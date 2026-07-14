/* Site effects — external, fingerprinted, served from 'self' (script-src 'self'),
   so the hash-locked CSP is never touched. Motion-heavy bits respect reduced-motion. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* 1 — Cursor spotlight on Recent Work cards. */
  if (!reduce) {
    document.querySelectorAll(".featured-card").forEach(function (card) {
      card.addEventListener("pointermove", function (e) {
        var r = card.getBoundingClientRect();
        card.style.setProperty("--mx", ((e.clientX - r.left) / r.width * 100) + "%");
        card.style.setProperty("--my", ((e.clientY - r.top) / r.height * 100) + "%");
      });
    });
  }

  /* 2 — Scroll-spy TOC. */
  var tocLinks = document.querySelectorAll(".toc .inner a[href^='#']");
  if (tocLinks.length && "IntersectionObserver" in window) {
    var tmap = {};
    tocLinks.forEach(function (a) {
      var id = decodeURIComponent(a.getAttribute("href").slice(1));
      if (id) tmap[id] = a;
    });
    var heads = Object.keys(tmap).map(function (id) { return document.getElementById(id); }).filter(Boolean);
    if (heads.length) {
      var spy = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          tocLinks.forEach(function (a) { a.classList.remove("active"); });
          if (tmap[en.target.id]) tmap[en.target.id].classList.add("active");
        });
      }, { rootMargin: "0px 0px -78% 0px", threshold: 0 });
      heads.forEach(function (h) { spy.observe(h); });
    }
  }

  /* 3 — Home stat counters. */
  var statWrap = document.querySelector(".home-stats");
  if (statWrap && "IntersectionObserver" in window) {
    var nums = statWrap.querySelectorAll(".stat-num"), counted = false;
    new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (en) {
        if (!en.isIntersecting || counted) return;
        counted = true; obs.disconnect();
        nums.forEach(function (el) {
          var target = parseInt(el.getAttribute("data-target"), 10) || 0;
          if (reduce) { el.textContent = target.toLocaleString(); return; }
          var start = performance.now(), dur = 1300;
          (function tick(now) {
            var p = Math.min((now - start) / dur, 1), e = 1 - Math.pow(1 - p, 3);
            el.textContent = Math.round(target * e).toLocaleString();
            if (p < 1) requestAnimationFrame(tick);
          })(start);
        });
      });
    }, { threshold: 0.4 }).observe(statWrap);
  }

  /* 4 — Konami code. */
  var seq = ["arrowup","arrowup","arrowdown","arrowdown","arrowleft","arrowright","arrowleft","arrowright","b","a"], kpos = 0;
  document.addEventListener("keydown", function (e) {
    var k = (e.key || "").toLowerCase();
    if (k === seq[kpos]) { if (++kpos === seq.length) { kpos = 0; konami(); } }
    else { kpos = (k === seq[0]) ? 1 : 0; }
  });
  function konami() {
    if (document.querySelector(".konami-toast")) return;
    var t = document.createElement("div");
    t.className = "konami-toast"; t.textContent = "⚡ GOD MODE ⚡";
    document.body.appendChild(t);
    if (!reduce) document.body.classList.add("konami-shake");
    setTimeout(function () { t.classList.add("konami-out"); document.body.classList.remove("konami-shake"); }, 2200);
    setTimeout(function () { if (t.parentNode) t.remove(); }, 2900);
  }

  /* 5 — Command palette (Ctrl/Cmd+K, or "/"). */
  (function () {
    var root = document.getElementById("cmdk");
    if (!root) return;
    var input = root.querySelector(".cmdk-input"),
        list = root.querySelector(".cmdk-results"),
        empty = root.querySelector(".cmdk-empty"),
        data = null, items = [], active = -1;
    function open() {
      root.hidden = false; root.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
      input.value = ""; render([]); input.focus();
      if (!data) fetch("/index.json").then(function (r) { return r.json(); })
        .then(function (d) { data = d; }).catch(function () { data = []; });
    }
    function close() {
      root.hidden = true; root.setAttribute("aria-hidden", "true"); document.body.style.overflow = "";
    }
    function search(q) {
      if (!data || !q.trim()) return [];
      var terms = q.toLowerCase().split(/\s+/).filter(Boolean);
      return data.filter(function (it) {
        var hay = (it.title + " " + (it.summary || "")).toLowerCase();
        return terms.every(function (t) { return hay.indexOf(t) !== -1; });
      }).slice(0, 8);
    }
    function setActive(i) { items.forEach(function (a) { a.classList.remove("is-active"); }); active = i; if (items[i]) items[i].classList.add("is-active"); }
    function render(res) {
      list.innerHTML = ""; items = []; active = -1;
      empty.hidden = !(input.value.trim() && res.length === 0);
      res.forEach(function (it, i) {
        var li = document.createElement("li"), a = document.createElement("a");
        a.href = it.permalink; a.className = "cmdk-item"; a.setAttribute("role", "option");
        var s = document.createElement("span"); s.className = "cmdk-item-title"; s.textContent = it.title;
        a.appendChild(s); li.appendChild(a); list.appendChild(li); items.push(a);
        a.addEventListener("mouseenter", function () { setActive(i); });
      });
      if (items.length) setActive(0);
    }
    input.addEventListener("input", function () { render(search(input.value)); });
    document.addEventListener("keydown", function (e) {
      var typing = /^(input|textarea|select)$/i.test(e.target.tagName || "") || e.target.isContentEditable;
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) { e.preventDefault(); open(); return; }
      if (e.key === "/" && !typing && root.hidden) { e.preventDefault(); open(); return; }
      if (root.hidden) return;
      if (e.key === "Escape") close();
      else if (e.key === "ArrowDown") { e.preventDefault(); if (items.length) setActive((active + 1) % items.length); }
      else if (e.key === "ArrowUp") { e.preventDefault(); if (items.length) setActive((active - 1 + items.length) % items.length); }
      else if (e.key === "Enter" && items[active]) window.location.href = items[active].href;
    });
    root.querySelectorAll("[data-cmdk-close]").forEach(function (el) { el.addEventListener("click", close); });
  })();

  /* 6 — Tag filter chips on /posts/. */
  (function () {
    var bar = document.querySelector(".tag-filter");
    if (!bar) return;
    var entries = Array.prototype.slice.call(document.querySelectorAll(".post-entry"));
    bar.addEventListener("click", function (e) {
      var btn = e.target.closest(".tag-chip"); if (!btn) return;
      var tag = btn.getAttribute("data-tag");
      bar.querySelectorAll(".tag-chip").forEach(function (b) { b.classList.toggle("is-active", b === btn); });
      entries.forEach(function (en) {
        var tags = " " + (en.getAttribute("data-tags") || "") + " ";
        en.style.display = (tag === "*" || tags.indexOf(" " + tag + " ") !== -1) ? "" : "none";
      });
    });
  })();

  /* 7 — Hero tagline typewriter. */
  (function () {
    var el = document.querySelector(".hero-tagline-text");
    if (!el) return;
    var words = ["networking", "security", "linux", "self-hosting", "game modding", "shaders", "home labs"];
    if (reduce) { el.textContent = words[0]; return; }
    var wi = 0, ci = 0, del = false;
    (function tick() {
      var w = words[wi]; ci += del ? -1 : 1; el.textContent = w.slice(0, ci);
      var d = del ? 45 : 95;
      if (!del && ci === w.length) { del = true; d = 1400; }
      else if (del && ci === 0) { del = false; wi = (wi + 1) % words.length; d = 350; }
      setTimeout(tick, d);
    })();
  })();

  /* 8 — Achievement toast when you finish an article. */
  (function () {
    var footer = document.querySelector(".post-single .post-footer");
    if (!footer || !("IntersectionObserver" in window)) return;
    var key = "ach-" + location.pathname;
    try { if (sessionStorage.getItem(key)) return; } catch (e) {}
    var done = false;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting || done) return;
        done = true; io.disconnect();
        try { sessionStorage.setItem(key, "1"); } catch (e) {}
        var t = document.createElement("div"); t.className = "achievement-toast";
        var ic = document.createElement("span"); ic.className = "achievement-icon"; ic.textContent = "🏆";
        var bd = document.createElement("span"); bd.className = "achievement-body";
        var h = document.createElement("strong"); h.textContent = "Achievement Unlocked";
        var p = document.createElement("span"); p.textContent = "Finished the article";
        bd.appendChild(h); bd.appendChild(p); t.appendChild(ic); t.appendChild(bd);
        document.body.appendChild(t);
        requestAnimationFrame(function () { t.classList.add("show"); });
        setTimeout(function () { t.classList.remove("show"); }, 4000);
        setTimeout(function () { if (t.parentNode) t.remove(); }, 4600);
      });
    }, { threshold: 0.9 });
    io.observe(footer);
  })();

  /* 9 — Subtle hero parallax (title tracks the pointer). */
  (function () {
    if (reduce) return;
    var hero = document.querySelector(".site-hero");
    if (!hero) return;
    hero.addEventListener("pointermove", function (e) {
      hero.style.setProperty("--px", (e.clientX / window.innerWidth - 0.5).toFixed(3));
      hero.style.setProperty("--py", (e.clientY / window.innerHeight - 0.5).toFixed(3));
    });
  })();

  /* 10 — Image lightbox: click a content image to view it full-size. */
  (function () {
    var imgs = document.querySelectorAll(".post-content img");
    if (!imgs.length) return;
    var box = null;
    function open(src, alt) {
      box = document.createElement("div"); box.className = "lightbox";
      var im = document.createElement("img"); im.src = src; im.alt = alt || "";
      box.appendChild(im); document.body.appendChild(box);
      document.body.style.overflow = "hidden";
      requestAnimationFrame(function () { box.classList.add("show"); });
      box.addEventListener("click", close);
    }
    function close() {
      if (!box) return; box.classList.remove("show"); document.body.style.overflow = "";
      var b = box; box = null; setTimeout(function () { if (b.parentNode) b.remove(); }, 250);
    }
    imgs.forEach(function (img) {
      if (/-logo\.svg$/.test(img.getAttribute("src") || "")) return;
      img.classList.add("zoomable");
      img.addEventListener("click", function () { open(img.currentSrc || img.src, img.alt); });
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && box) close(); });
  })();

  /* 11 — Hovercards: preview internal post links on hover. */
  (function () {
    var links = document.querySelectorAll(".post-content a[href*='/posts/'], .related-posts-list a, .home-featured a");
    if (!links.length) return;
    var data = null, card = null, timer = null;
    function ensureData() {
      if (data) return Promise.resolve(data);
      return fetch("/index.json").then(function (r) { return r.json(); })
        .then(function (d) { data = d; return d; }).catch(function () { data = []; return data; });
    }
    function lookup(href) {
      var path = href.replace(location.origin, "").replace(/\/$/, "");
      return data.find(function (it) {
        var p = it.permalink.replace(location.origin, "").replace(/\/$/, "");
        return p && (p === path || p.endsWith(path) || path.endsWith(p));
      });
    }
    function hide() { if (card) { card.remove(); card = null; } }
    function show(link) {
      ensureData().then(function () {
        var it = lookup(link.getAttribute("href")); if (!it) return;
        hide();
        card = document.createElement("div"); card.className = "hovercard";
        var t = document.createElement("div"); t.className = "hovercard-title"; t.textContent = it.title;
        var s = document.createElement("div"); s.className = "hovercard-summary";
        s.textContent = (it.summary || "").replace(/<[^>]+>/g, "").slice(0, 155);
        card.appendChild(t); card.appendChild(s); document.body.appendChild(card);
        var r = link.getBoundingClientRect();
        var left = Math.min(window.scrollX + r.left, window.scrollX + document.documentElement.clientWidth - 332);
        card.style.top = (window.scrollY + r.bottom + 8) + "px";
        card.style.left = Math.max(12, left) + "px";
        requestAnimationFrame(function () { card.classList.add("show"); });
      });
    }
    links.forEach(function (link) {
      link.addEventListener("mouseenter", function () { timer = setTimeout(function () { show(link); }, 350); });
      link.addEventListener("mouseleave", function () { clearTimeout(timer); hide(); });
    });
  })();

  /* 12 — Matrix digital rain (404 background + "matrix" easter egg). */
  (function () {
    function rain(canvas) {
      var ctx = canvas.getContext("2d");
      var chars = "アイウエオカキクケコサシスセソ0123456789<>{}[]#$%&*ABCDEF".split("");
      var fs = 16, drops = [], raf, running = true;
      function size() {
        canvas.width = canvas.offsetWidth; canvas.height = canvas.offsetHeight;
        var cols = Math.max(1, Math.floor(canvas.width / fs));
        drops = []; for (var i = 0; i < cols; i++) drops[i] = Math.random() * -50;
      }
      function draw() {
        if (!running) return;
        ctx.fillStyle = "rgba(13,13,15,0.08)"; ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#E81A1A"; ctx.font = fs + "px monospace";
        for (var i = 0; i < drops.length; i++) {
          ctx.fillText(chars[Math.floor(Math.random() * chars.length)], i * fs, drops[i] * fs);
          if (drops[i] * fs > canvas.height && Math.random() > 0.975) drops[i] = 0;
          drops[i]++;
        }
        raf = requestAnimationFrame(draw);
      }
      size(); draw();
      window.addEventListener("resize", size);
      return { stop: function () { running = false; cancelAnimationFrame(raf); } };
    }
    var c404 = document.querySelector(".matrix-404");
    if (c404 && !reduce) rain(c404);
    function trigger() {
      if (reduce || document.querySelector(".matrix-overlay")) return;
      var ov = document.createElement("canvas"); ov.className = "matrix-overlay";
      document.body.appendChild(ov); var r = rain(ov);
      setTimeout(function () { ov.classList.add("fade"); }, 4200);
      setTimeout(function () { r.stop(); if (ov.parentNode) ov.remove(); }, 5000);
    }
    window.addEventListener("bb-matrix", trigger);
    var buf = "";
    document.addEventListener("keydown", function (e) {
      if ((e.key || "").length !== 1) return;
      var typing = /^(input|textarea)$/i.test(e.target.tagName || "") || e.target.isContentEditable;
      if (typing) return;
      buf = (buf + e.key.toLowerCase()).slice(-6);
      if (buf.indexOf("matrix") !== -1) { buf = ""; trigger(); }
    });
  })();

  /* 13 — Preloader intro (home page, once per session). */
  (function () {
    var pre = document.getElementById("preloader");
    if (!pre) return;
    var fill = document.getElementById("preloader-fill"), pct = document.getElementById("preloader-pct");
    var seen = false; try { seen = sessionStorage.getItem("bb-loaded"); } catch (e) {}
    if (seen || reduce) { pre.remove(); return; }
    try { sessionStorage.setItem("bb-loaded", "1"); } catch (e) {}
    function done() { pre.classList.add("preloader-out"); setTimeout(function () { if (pre.parentNode) pre.remove(); }, 700); }
    var p = 0;
    var iv = setInterval(function () {
      p += Math.random() * 14 + 5;
      if (p >= 100) { p = 100; clearInterval(iv); setTimeout(done, 350); }
      if (fill) fill.style.width = p + "%";
      if (pct) pct.textContent = Math.floor(p) + "%";
    }, 90);
  })();

  /* 14 — Smooth momentum scrolling (Lenis, self-hosted). Skips touch + reduced-motion. */
  (function () {
    if (reduce || !window.Lenis) return;
    if (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) return;
    var lenis = new window.Lenis({ lerp: 0.1, smoothWheel: true });
    (function raf(t) { lenis.raf(t); requestAnimationFrame(raf); })();
    /* Route in-page anchor clicks through Lenis (capture phase, before the theme's
       own handler) so the TOC / back-to-top still work smoothly. */
    document.addEventListener("click", function (e) {
      var a = e.target.closest && e.target.closest('a[href^="#"]');
      if (!a) return;
      var href = a.getAttribute("href");
      if (!href || href.length < 2) return;
      var target = document.querySelector(href);
      if (!target) return;
      e.preventDefault(); e.stopPropagation();
      lenis.scrollTo(target, { offset: -16 });
    }, true);
  })();

  /* 15 — Magnetic buttons. */
  (function () {
    if (reduce || (window.matchMedia && window.matchMedia("(pointer: coarse)").matches)) return;
    document.querySelectorAll(".home-posts-link, .home-featured-all, .magnetic").forEach(function (el) {
      el.addEventListener("pointermove", function (e) {
        var r = el.getBoundingClientRect();
        el.style.transform = "translate(" + ((e.clientX - r.left - r.width / 2) * 0.3) +
          "px," + ((e.clientY - r.top - r.height / 2) * 0.3) + "px)";
      });
      el.addEventListener("pointerleave", function () { el.style.transform = ""; });
    });
  })();

  /* 16 — Trailing accent cursor glow (in addition to the native cursor). */
  (function () {
    if (reduce || (window.matchMedia && window.matchMedia("(pointer: coarse)").matches)) return;
    var glow = document.createElement("div");
    glow.className = "cursor-glow"; document.body.appendChild(glow);
    var x = 0, y = 0, tx = 0, ty = 0, on = false;
    window.addEventListener("pointermove", function (e) {
      tx = e.clientX; ty = e.clientY;
      if (!on) { on = true; glow.style.opacity = "1"; (function loop() {
        x += (tx - x) * 0.18; y += (ty - y) * 0.18;
        glow.style.transform = "translate(" + x + "px," + y + "px)";
        requestAnimationFrame(loop);
      })(); }
    });
    window.addEventListener("pointerdown", function () { glow.classList.add("cursor-glow-tap"); });
    window.addEventListener("pointerup", function () { glow.classList.remove("cursor-glow-tap"); });
  })();
})();
