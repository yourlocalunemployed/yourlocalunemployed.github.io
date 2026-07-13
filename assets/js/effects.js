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
})();
