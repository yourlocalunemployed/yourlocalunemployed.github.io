/* Hero WebGL shader — renders the EFT key art live with drifting fog banks,
   mist refraction, depth-weighted pointer parallax, cursor-reactive embers and
   film grain. External + fingerprinted (script-src 'self'), so the hash-locked
   CSP is untouched. Bails silently to the static Ken Burns layer on
   reduced-motion, phones, missing WebGL, shader/link failure, image failure or
   context loss — the canvas only fades in after the first good frame. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canvas = document.getElementById("hero-shader");
  if (!canvas || reduce) return;
  if (window.matchMedia && window.matchMedia("(max-width: 768px)").matches) return; // phones: battery
  var hero = canvas.closest(".site-hero");
  if (!hero) return;

  var gl;
  try { gl = canvas.getContext("webgl", { antialias: false, alpha: false }) || canvas.getContext("experimental-webgl"); } catch (e) {}
  if (!gl) return;

  var vsrc = "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}";
  var fsrc = [
    "precision highp float;",
    "uniform vec2 r;",        // canvas resolution, px
    "uniform float t;",       // seconds
    "uniform sampler2D img;",
    "uniform float ia;",      // image aspect (w/h)
    "uniform vec2 m;",        // pointer, hero-relative uv, y-up, lerped
    "float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}",
    "float noise(vec2 p){vec2 i=floor(p),f=fract(p);vec2 u=f*f*(3.-2.*f);",
    "return mix(mix(hash(i),hash(i+vec2(1,0)),u.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),u.x),u.y);}",
    "float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<4;i++){v+=a*noise(p);p=p*2.03+vec2(17.3,9.1);a*=.5;}return v;}",
    "void main(){",
    "vec2 uv=gl_FragCoord.xy/r;",
    "float ca=r.x/r.y;",
    "vec2 mo=m-.5;",
    /* cover-fit crop of the image, with zoom head-room for drift + parallax */
    "vec2 s=(ca>ia)?vec2(1.,ia/ca):vec2(ca/ia,1.);",
    "float zoom=1.26;",
    /* slow autonomous drift — the shader's Ken Burns */
    "vec2 drift=vec2(sin(t*.031),cos(t*.023))*.012;",
    /* depth-weighted pointer parallax: foreground (bottom) shifts most, sky least,
       and the centre figures are damped so they don't smear */
    "float depth=mix(1.,.25,smoothstep(.15,.85,uv.y));",
    "float cf=.55+.45*smoothstep(.12,.45,length((uv-vec2(.5,.52))*vec2(1.,1.35)));",
    "vec2 par=-mo*.016*depth*cf;",
    /* mist refraction — tiny noise wobble, stronger near the ground */
    "vec2 wob=(vec2(noise(uv*7.+vec2(t*.10,0.)),noise(uv*7.+vec2(0.,t*.08)+31.7))-.5)*.004*(1.1-uv.y);",
    /* bias the crop upward so the game logo at the image's foot stays out of frame */
    "vec2 suv=.5+(uv-.5)*s/zoom+vec2(0.,.07)+drift+par+wob;",
    "vec3 col=texture2D(img,suv).rgb;",
    /* two fog banks: one riding the crane horizon, one hugging the ground */
    "float f1=fbm(uv*vec2(2.6,3.4)+vec2(t*.020,t*.006));",
    "float f2=fbm(uv*vec2(4.2,5.)-vec2(t*.031,-t*.004)+7.7);",
    "float band=smoothstep(.05,.42,uv.y)*(1.-smoothstep(.55,.95,uv.y));",
    "float ground=1.-smoothstep(0.,.35,uv.y);",
    "float fog=band*smoothstep(.35,.85,f1)*.25+ground*smoothstep(.30,.80,f2)*.34;",
    "col=mix(col,vec3(.58,.66,.72),clamp(fog,0.,1.));",
    /* rising embers, two depth layers; they scatter off the pointer and flare near it */
    "vec2 ap=uv*vec2(ca,1.);",
    "vec2 ma=m*vec2(ca,1.);",
    "vec3 ember=vec3(0.);",
    "for(int l=0;l<2;l++){",
    "float fl=float(l);",
    "float sc=7.+fl*5.;",
    "float sp=.030+fl*.022;",
    "vec2 q=ap*sc;",
    "q.y-=t*sp*sc;",
    "q.x+=sin(t*.4+fl*2.1+ap.y*4.)*.35;",
    "vec2 cell=floor(q);",
    "float rn=hash(cell+fl*13.1);",
    "float alive=step(.78,rn);",
    "vec2 pos=vec2(.30+.40*hash(cell+1.7),.30+.40*hash(cell+4.3));",
    "pos+=.10*vec2(sin(t*(1.+rn*2.)+rn*31.),cos(t*(.8+rn)+rn*17.));",
    "vec2 pw=(cell+pos)/sc;",
    "vec2 psp=pw+vec2(0.,t*sp);",       // particle back in screen space for pointer math
    "vec2 dm=psp-ma;",
    "float md=max(length(dm),.001);",
    "pw+=(dm/md)*.045*exp(-md*md*55.);", // pointer pushes embers away
    "vec2 d=q/sc-pw;",
    "float dist=length(d);",
    "float flick=.55+.45*sin(t*(4.+rn*5.)+rn*40.);",
    "float size=.0016+.0022*rn;",
    "float g=alive*flick*exp(-dist*dist/(size*size));",
    "g*=1.+1.5*exp(-md*md*70.);",        // flare near the pointer
    "float halo=alive*flick*exp(-dist*dist/(size*size*14.))*.22;",
    "ember+=(vec3(1.,.42,.10)*g+vec3(1.,.30,.05)*halo)*(.7+.3*fl);",
    "}",
    "col+=ember*.85;",
    /* film grain */
    "col+=(hash(gl_FragCoord.xy+fract(t)*vec2(17.,29.))-.5)*.028;",
    "gl_FragColor=vec4(col,1.);",
    "}"
  ].join("");

  function sh(ty, src) {
    var s = gl.createShader(ty);
    gl.shaderSource(s, src); gl.compileShader(s);
    return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
  }
  var vs = sh(gl.VERTEX_SHADER, vsrc), fs = sh(gl.FRAGMENT_SHADER, fsrc);
  if (!vs || !fs) return;
  var prog = gl.createProgram();
  gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return;
  gl.useProgram(prog);

  var buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
  var loc = gl.getAttribLocation(prog, "p");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

  var uR = gl.getUniformLocation(prog, "r"),
      uT = gl.getUniformLocation(prog, "t"),
      uIa = gl.getUniformLocation(prog, "ia"),
      uM = gl.getUniformLocation(prog, "m");

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    canvas.width = Math.max(1, Math.round(canvas.offsetWidth * dpr));
    canvas.height = Math.max(1, Math.round(canvas.offsetHeight * dpr));
    gl.viewport(0, 0, canvas.width, canvas.height);
  }
  window.addEventListener("resize", resize);

  /* pointer, lerped for weight; released back to centre on leave */
  var mx = 0.5, my = 0.5, tx = 0.5, ty = 0.5;
  hero.addEventListener("pointermove", function (e) {
    var rc = canvas.getBoundingClientRect();
    if (!rc.width || !rc.height) return;
    tx = (e.clientX - rc.left) / rc.width;
    ty = 1 - (e.clientY - rc.top) / rc.height;
  });
  hero.addEventListener("pointerleave", function () { tx = 0.5; ty = 0.5; });

  /* only burn GPU while the hero is actually on screen */
  var inView = true;
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { inView = en.isIntersecting; });
    }, { threshold: 0.01 }).observe(hero);
  }

  var dead = false;
  canvas.addEventListener("webglcontextlost", function (e) {
    e.preventDefault();
    dead = true;
    hero.classList.remove("shader-active"); // static layer takes back over
  });

  var img = new Image();
  img.onload = function () {
    if (dead) return;
    var tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, img);
    gl.uniform1f(uIa, img.naturalWidth / img.naturalHeight);
    gl.uniform1i(gl.getUniformLocation(prog, "img"), 0);
    resize();
    var start = performance.now(), shown = false;
    (function draw(now) {
      if (dead) return;
      requestAnimationFrame(draw);
      if (document.hidden || !inView) return;
      mx += (tx - mx) * 0.06;
      my += (ty - my) * 0.06;
      gl.uniform2f(uR, canvas.width, canvas.height);
      gl.uniform1f(uT, (now - start) / 1000);
      gl.uniform2f(uM, mx, my);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      if (!shown) { shown = true; hero.classList.add("shader-active"); }
    })(start);
  };
  img.src = canvas.getAttribute("data-img") || "";
})();
