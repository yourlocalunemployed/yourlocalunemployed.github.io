/* Toy interactive shell for the /terminal/ page. External + fingerprinted,
   served from 'self', so the hash-locked CSP is untouched. All output is built
   with textContent (no innerHTML from user input) — no injection surface. */
(function () {
  "use strict";
  var input = document.getElementById("terminal-input");
  var out = document.getElementById("terminal-output");
  var body = document.getElementById("terminal-body");
  var term = document.getElementById("terminal");
  if (!input || !out) return;

  var history = [], hpos = -1;

  var NEO = [
    "        _____",
    "       /  _  \\   visitor@billsblog",
    "      /  / \\  \\  ------------------",
    "     /  /   \\  \\ OS:    Hugo (static)",
    "    (  (     )  ) Host:  Cloudflare Pages",
    "     \\  \\   /  /  Domain:billsblog.dev (.dev, HTTPS-only)",
    "      \\  \\_/  /   Shell: bash-ish (this toy)",
    "       \\_____/    CPU:   Ryzen 7 7800X3D",
    "                  GPU:   RTX 4090"
  ];

  var COMMANDS = {
    help: function () {
      return ["Available commands:",
        "  help         this list",
        "  whoami       who runs this place",
        "  about        the short version",
        "  projects     what I've built",
        "  posts        go to the writing",
        "  now          what I'm up to",
        "  social       github / linkedin",
        "  neofetch     the obligatory flex",
        "  ls           list sections",
        "  cat <name>   read a section (try: cat about)",
        "  date         current date",
        "  echo <text>  say something",
        "  sudo <cmd>   ...go on then",
        "  clear        wipe the screen"];
    },
    whoami: function () { return ["billal — IT student (networking + cyber security), Debian daily driver, heavy gamer/modder."]; },
    about: function () {
      return ["I document real projects — pfSense labs, network hardening, home-lab observability,",
        "game-mod ports — mostly built with Claude Code on a Debian VM.",
        "Full story:  https://billsblog.dev/about/"];
    },
    projects: function () { return ["A curated index lives at  https://billsblog.dev/projects/", "Type 'posts' for the full feed."]; },
    posts: function () { go("/posts/"); return ["Opening /posts/ …"]; },
    now: function () { go("/now/"); return ["Opening /now/ …"]; },
    social: function () {
      return ["github:   https://github.com/yourlocalunemployed",
              "linkedin: https://www.linkedin.com/in/billal-r-308325242/"];
    },
    neofetch: function () { return NEO.slice(); },
    ls: function () { return ["about   now   posts   projects   social"]; },
    cat: function (args) {
      var map = {
        about: "IT student, networking + security. Builds and documents real labs. See: about",
        now: "Currently: semester break, upskilling in Linux/PowerShell, planning a Pi ad-blocker. See: now",
        social: "github.com/yourlocalunemployed  ·  linkedin.com/in/billal-r-308325242",
        posts: "Run 'posts' to open the feed.",
        projects: "Run 'projects' for the index."
      };
      var name = (args[0] || "").toLowerCase();
      if (!name) return ["usage: cat <name>   (try: cat about)"];
      return map[name] ? [map[name]] : ["cat: " + name + ": No such file. Try 'ls'."];
    },
    date: function () { return [new Date().toString()]; },
    echo: function (args) { return [args.join(" ")]; },
    sudo: function (args) {
      if (!args.length) return ["usage: sudo <command>"];
      return ["[sudo] password for visitor: ", "Nice try. You don't have root here — but I admire the confidence. 😎"];
    },
    clear: function () { out.textContent = ""; return null; },
    hello: function () { return ["hey 👋  type 'help' if you're lost."]; },
    matrix: function () { window.dispatchEvent(new Event("bb-matrix")); return ["Wake up, Neo…"]; }
  };

  function go(path) { setTimeout(function () { window.location.href = path; }, 350); }

  function line(text, cls) {
    var d = document.createElement("div");
    d.className = "terminal-line" + (cls ? " " + cls : "");
    d.textContent = text;
    out.appendChild(d);
  }
  function echoCommand(raw) { line("visitor@billsblog:~$ " + raw, "terminal-echo"); }

  function run(raw) {
    var parts = raw.trim().split(/\s+/);
    var cmd = (parts.shift() || "").toLowerCase();
    if (!cmd) return;
    var fn = COMMANDS[cmd];
    if (!fn) { line("command not found: " + cmd + "   (type 'help')", "terminal-err"); return; }
    var res = fn(parts);
    if (res) res.forEach(function (l) { line(l); });
  }

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      var raw = input.value;
      echoCommand(raw);
      if (raw.trim()) { history.unshift(raw); if (history.length > 50) history.pop(); }
      hpos = -1;
      run(raw);
      input.value = "";
      body.scrollTop = body.scrollHeight;
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (hpos < history.length - 1) { hpos++; input.value = history[hpos]; }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (hpos > 0) { hpos--; input.value = history[hpos]; }
      else { hpos = -1; input.value = ""; }
    }
  });

  term.addEventListener("click", function () { input.focus(); });

  line("billsblog shell — type 'help' to begin.", "terminal-welcome");
  line("");
  input.focus();
})();
