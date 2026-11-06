// ---------------------------------------------------------------------------
// 3D の戦闘画面（Three.js）
//   これまでの画面（#stage の中の背景・敵の絵）は、当たり判定とエフェクトの位置合わせ用に「見えない影」として残す。
//   見た目は Three.js の空間に描き、影の絵の位置と大きさを、毎フレーム 3D の位置に合わせて動かす。
//   こうすると、連打・魔法のねらい・敵の選択・エフェクトの位置（すべて画面の座標で計算している）が、
//   カメラが動いてもそのまま正しく働く。
//   MFX（魔法・必殺技・敵の攻撃のエフェクト）は、出した瞬間の画面の位置を 3D の空間の位置に置きかえて、
//   空間の中で動かす（カメラが回りこむと、奥行きが見える）。
//   Three.js が使えないとき（読みこめない・WebGL がない）は、これまでどおりの 2D の画面のまま動く。
// ---------------------------------------------------------------------------
(function () {
  "use strict";
  const W3D = { on: false };
  window.W3D = W3D;
  const CDN = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const FOV = 50, DC = 10, TAN = Math.tan(FOV * Math.PI / 360);
  const BACK_Z = -24, ALLY_Z = 4;
  const rand = (a, b) => a + Math.random() * (b - a), any = (a) => a[Math.floor(Math.random() * a.length)];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  let T = null, renderer = null, scene = null, camera = null, app = null, stage = null;
  let VW = 1, VH = 1, args = {}, booted = false, started = false;
  const rig = { yaw: 0, pitch: 0, dist: DC, tx: 0, ty: 0, tz: 0 };
  let shakeW = 0, shakeT = 0, clock = 0, last = 0;
  const jobs = [];
  const scenes = [];        // { el, group, foes: [...], back, opacity }
  let allies = [];          // { lv, group, mesh, halo, home, off, ... }

  // ---- Three.js を用意する（同じフォルダの three.min.js。なければ CDN） ----
  function loadThree() {
    if (window.THREE) return Promise.resolve(window.THREE);
    return new Promise((res) => {
      const s = document.createElement("script"); s.src = CDN;
      s.onload = () => res(window.THREE || null); s.onerror = () => res(null);
      document.head.appendChild(s);
    });
  }
  async function boot() {
    if (booted) return W3D.on; booted = true;
    T = await loadThree();
    if (!T) return false;
    try {
      renderer = new T.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    } catch (e) { renderer = null; return false; }
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.outputEncoding = T.sRGBEncoding;
    renderer.setClearColor(0x07060a, 1);
    const cv = renderer.domElement; cv.id = "gl";
    app = document.getElementById("app"); stage = document.getElementById("stage");
    app.insertBefore(cv, app.firstChild);
    const vig = document.createElement("div"); vig.id = "vig3d"; app.insertBefore(vig, stage.nextSibling);
    scene = new T.Scene();
    camera = new T.PerspectiveCamera(FOV, 1, 0.1, 400);
    makeShared();
    FX.init();
    resize();
    addEventListener("resize", () => { resize(); relayout(); });
    // 場面の入れかえ（新しい戦闘・覚醒で姿が変わる）を見張る
    new MutationObserver(() => syncScenes()).observe(stage, { childList: true });
    new MutationObserver((recs) => {
      for (const r of recs) {
        const el = r.target;
        if (r.attributeName === "class" && el.classList && el.classList.contains("struck")) {
          const f = foeOf(el); if (f) f.flashT = clock;
        }
      }
    }).observe(stage, { attributes: true, subtree: true, attributeFilter: ["class"] });
    W3D.on = true; app.classList.add("d3");
    requestAnimationFrame(frame);
    return true;
  }
  function resize() {
    VW = innerWidth; VH = innerHeight;
    renderer.setSize(VW, VH, false);
    camera.aspect = VW / VH; camera.updateProjectionMatrix();
    FX.resize();
  }

  // 画面の位置 ↔ 空間の位置（いつもの位置のカメラ：(0, 0, DC) から -z を見る）
  const kz = (z) => 2 * (DC - z) * TAN / VH;                     // 奥行き z での、1px あたりの長さ
  const homeW = (x, y, z) => new T.Vector3((x - VW / 2) * kz(z), (VH / 2 - y) * kz(z), z);
  // 今のカメラで、画面の点 (x, y) が奥行き z の面と交わるところ
  const _v = () => new T.Vector3();
  function toW(x, y, z = 0) {
    const v = _v().set((x / VW) * 2 - 1, -(y / VH) * 2 + 1, 0.5).unproject(camera);
    const d = v.sub(camera.position).normalize();
    const t = Math.abs(d.z) < 1e-4 ? DC : (z - camera.position.z) / d.z;
    return camera.position.clone().addScaledVector(d, t > 0 ? t : DC);
  }
  const _fw = () => { const f = _v(); camera.getWorldDirection(f); return f; };
  function kAt(p) { const depth = Math.max(0.5, _v().subVectors(p, camera.position).dot(_fw())); return 2 * depth * TAN / VH; }
  function toS(p) { const v = p.clone().project(camera); return { x: (v.x + 1) / 2 * VW, y: (1 - v.y) / 2 * VH, z: v.z }; }
  W3D.toS = (p) => toS(p);

  // ---- 共通の絵 ----
  let TEX = {};
  function canvasTex(w, h, draw) {
    const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h);
    const t = new T.CanvasTexture(c); t.encoding = T.sRGBEncoding; return t;
  }
  function makeShared() {
    TEX.glow = canvasTex(128, 128, (g, w) => {
      const r = g.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
      r.addColorStop(0, "rgba(255,255,255,1)"); r.addColorStop(.3, "rgba(255,255,255,.5)"); r.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = r; g.fillRect(0, 0, w, w);
    });
    TEX.shadow = canvasTex(128, 128, (g, w) => {
      const r = g.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
      r.addColorStop(0, "rgba(0,0,0,.8)"); r.addColorStop(.45, "rgba(0,0,0,.4)"); r.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = r; g.fillRect(0, 0, w, w);
    });
    TEX.void = canvasTex(128, 128, (g, w) => {
      const r = g.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
      r.addColorStop(0, "rgba(0,0,0,1)"); r.addColorStop(.55, "rgba(10,0,25,.95)"); r.addColorStop(.7, "rgba(160,90,255,.8)"); r.addColorStop(1, "rgba(80,0,140,0)");
      g.fillStyle = r; g.fillRect(0, 0, w, w);
    });
  }
  function texFromImg(img) {
    const t = new T.Texture(img); t.encoding = T.sRGBEncoding; t.anisotropy = 4; t.needsUpdate = true; return t;
  }
  // ぼかした絵（1枚絵の敵のうしろ）：小さく縮めてから引きのばす
  function blurTex(img) {
    const c = document.createElement("canvas"), s = 48 / Math.max(img.naturalWidth, img.naturalHeight);
    c.width = Math.max(4, Math.round(img.naturalWidth * s)); c.height = Math.max(4, Math.round(img.naturalHeight * s));
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    const t = new T.CanvasTexture(c); t.encoding = T.sRGBEncoding; return t;
  }
  const loaded = (img) => new Promise((res) => {
    if (!img) return res(null);
    if (img.complete && img.naturalWidth) return res(img);
    img.addEventListener("load", () => res(img), { once: true }); img.addEventListener("error", () => res(null), { once: true });
  });

  // 敵の絵の「中身」が画面のどこに描かれているか（object-fit を考えた範囲）
  function contentRect(img) {
    const r = img.getBoundingClientRect(), nw = img.naturalWidth || 1, nh = img.naturalHeight || 1, cs = getComputedStyle(img);
    const s = cs.objectFit === "cover" ? Math.max(r.width / nw, r.height / nh) : Math.min(r.width / nw, r.height / nh);
    const dw = nw * s, dh = nh * s;
    const pos = cs.objectPosition.split(" ").map((v) => v.endsWith("%") ? parseFloat(v) / 100 : 0.5);
    const fy = img.classList.contains("st-enemy") ? 1 : pos[1];
    return { x: r.left + (r.width - dw) * pos[0], y: r.top + (r.height - dh) * fy, w: dw, h: dh };
  }

  // ---- 場面（背景と敵） ----
  function syncScenes() {
    if (!W3D.on) return;
    const els = [...stage.querySelectorAll(":scope > .st-scene")];
    for (const s of scenes.slice()) if (!els.includes(s.el)) dropScene(s);
    for (const el of els) if (!scenes.some((s) => s.el === el)) addScene(el);
  }
  function dropScene(s) {
    scenes.splice(scenes.indexOf(s), 1);
    scene.remove(s.group);
    s.group.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) { if (o.material.map && o.material.map !== TEX.glow && o.material.map !== TEX.shadow) o.material.map.dispose(); o.material.dispose(); } });
    for (const f of s.foes) { f.el.classList.remove("p3d"); for (const k of ["left", "top", "width", "height"]) f.el.style.removeProperty(k); }
  }
  async function addScene(el) {
    const rec = { el, group: new T.Group(), foes: [], ready: false, kind: sceneKind(el) };
    scenes.push(rec);
    await Promise.all([...el.querySelectorAll("img")].map(loaded));
    if (!scenes.includes(rec)) return;
    layoutScene(rec);
    scene.add(rec.group);
    rec.ready = true;
  }
  function sceneKind(el) {
    for (const k of ["corridor", "prison", "catacomb", "altar", "nebula", "cosmos", "kz"]) if (el.classList.contains(k)) return k;
    return "image";
  }
  function layoutScene(rec) {
    const g = rec.group;
    while (g.children.length) g.remove(g.children[0]);
    for (const f of rec.foes) { f.el.classList.remove("p3d"); for (const k of ["left", "top", "width", "height"]) f.el.style.removeProperty(k); }
    rec.foes = [];
    // 背景：画面いっぱい（cover）より少し大きく、ずっと奥に置く。カメラが回りこんでも端が見えないように
    const bgImg = rec.el.querySelector("img.st-bg") || rec.el.querySelector("img.st-photo-bg");
    if (bgImg && bgImg.naturalWidth) {
      const blur = bgImg.classList.contains("st-photo-bg");
      const d = DC - BACK_Z, vh = 2 * d * TAN, vw = vh * VW / VH, a = bgImg.naturalWidth / bgImg.naturalHeight;
      const needW = vw * 1.15 + 2 * d * Math.tan(0.62) + 10, needH = vh * 1.35 + 2 * d * Math.tan(0.22) + 6;
      const ph = Math.max(needH, needW / a), pw = ph * a;
      const mat = new T.MeshBasicMaterial({ map: blur ? blurTex(bgImg) : texFromImg(bgImg), depthWrite: false, fog: false });
      if (blur) mat.color.setScalar(0.5);
      const m = new T.Mesh(new T.PlaneGeometry(pw, ph), mat); m.position.set(0, 0, BACK_Z); m.renderOrder = -10;
      g.add(m); rec.back = m;
    }
    // 敵：今の画面での位置（CSS で決まる）を、そのまま空間の位置に持ちあげる
    const targets = [...rec.el.querySelectorAll("img.st-target")];
    const n = targets.length;
    targets.forEach((img, i) => {
      if (!img.naturalWidth) return;
      const r = contentRect(img), photo = img.classList.contains("st-photo");
      const z = n === 3 && i === 1 ? 0.8 : 0;
      const tl = homeW(r.x, r.y, z), br = homeW(r.x + r.w, r.y + r.h, z);
      const w = br.x - tl.x, h = tl.y - br.y, c = new T.Vector3((tl.x + br.x) / 2, (tl.y + br.y) / 2, z);
      const tex = texFromImg(img);
      const mat = new T.MeshBasicMaterial({ map: tex, transparent: !photo, alphaTest: photo ? 0 : 0.02, depthWrite: false, side: T.DoubleSide });
      const mesh = new T.Mesh(new T.PlaneGeometry(1, 1), mat); mesh.scale.set(w, h, 1);
      const hold = new T.Group(); hold.position.copy(c); hold.add(mesh); g.add(hold);
      // ねらっている敵：絵の形にそった金色の光
      const gm = new T.ShaderMaterial({
        uniforms: { map: { value: tex }, uOp: { value: 0 }, uCol: { value: new T.Color("#ffe28a") } },
        vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
        fragmentShader: "uniform sampler2D map; uniform float uOp; uniform vec3 uCol; varying vec2 vUv; void main(){ float a = texture2D(map, vUv).a; gl_FragColor = vec4(uCol, a * uOp); }",
        transparent: true, depthWrite: false, blending: T.AdditiveBlending,
      });
      const glow = new T.Mesh(new T.PlaneGeometry(1, 1), gm); glow.scale.set(w * 1.07, h * 1.05, 1); glow.position.z = -0.02; hold.add(glow);
      let shadow = null;
      if (!photo && !img.classList.contains("floating")) {
        shadow = new T.Mesh(new T.PlaneGeometry(1, 1), new T.MeshBasicMaterial({ map: TEX.shadow, transparent: true, depthWrite: false }));
        shadow.rotation.x = -Math.PI / 2; shadow.scale.set(w * 0.55, w * 0.22, 1); shadow.position.set(c.x, br.y + 0.02, z); g.add(shadow);
      }
      rec.foes.push({ el: img, hold, mesh, glow, shadow, base: c.clone(), w, h, z, photo, floating: img.classList.contains("floating"),
                      seed: Math.random() * 10, flashT: -9, deadT: null, op: 1, last: null, gx: 0 });
      img.classList.add("p3d");
    });
    // 場面ごとのまわりの粒（たいまつの火の粉・霧・星など）
    const amb = ambient(rec.kind);
    if (amb) g.add(amb);
    rec.amb = amb;
  }
  function relayout() { for (const s of scenes) if (s.ready) layoutScene(s); layoutAllies(); }
  function foeOf(el) { for (const s of scenes) for (const f of s.foes) if (f.el === el) return f; return null; }
  W3D.foes = () => { const out = []; for (const s of scenes) for (const f of s.foes) out.push(f); return out; };

  // まわりの粒
  function ambient(kind) {
    const P = {
      corridor: { n: 70, c: ["#ffb060", "#ff8030", "#ffd090"], up: 0.35, s: 0.07 },
      prison: { n: 60, c: ["#b8c8ff", "#e0e8ff"], up: 0.08, s: 0.06 },
      catacomb: { n: 60, c: ["#ffcf80", "#c8b0ff"], up: 0.15, s: 0.07 },
      altar: { n: 80, c: ["#c08cff", "#ff8ad8", "#ffd36a"], up: 0.45, s: 0.06 },
      nebula: { n: 140, c: ["#c8b8ff", "#9fd8ff", "#ffffff", "#ffe0b0"], up: 0.03, s: 0.07 },
      cosmos: { n: 160, c: ["#c8b8ff", "#9fd8ff", "#ffffff", "#ffb8e8"], up: 0.03, s: 0.075 },
      kz: { n: 80, c: ["#b8ff9a", "#fff3a0", "#9fffd8"], up: 0.12, s: 0.07 },
      image: { n: 60, c: ["#ffffff", "#ffe8c0"], up: 0.06, s: 0.05 },
    }[kind];
    if (!P) return null;
    const geo = new T.BufferGeometry(), pos = new Float32Array(P.n * 3), col = new Float32Array(P.n * 3);
    for (let i = 0; i < P.n; i++) {
      pos.set([rand(-16, 16), rand(-8, 9), rand(-14, 6)], i * 3);
      const c = new T.Color(any(P.c)); col.set([c.r, c.g, c.b], i * 3);
    }
    geo.setAttribute("position", new T.BufferAttribute(pos, 3)); geo.setAttribute("color", new T.BufferAttribute(col, 3));
    const pts = new T.Points(geo, new T.PointsMaterial({ size: P.s * 2.2, map: TEX.glow, vertexColors: true, transparent: true, opacity: 0.75, blending: T.AdditiveBlending, depthWrite: false }));
    pts.userData = P; pts.renderOrder = 2;
    return pts;
  }

  // ---- 味方（切り抜いた全身の絵を、手前に立てる） ----
  const ALLY_H = 0.34;      // 画面の高さに対する、立ち絵の高さ
  function layoutAllies() {
    if (!W3D.on) return;
    const n = allies.length;
    const off = Math.min(VW * 0.33, 250);
    const xs = n === 1 ? [0.5] : n === 2 ? [0.5 - off / VW * 0.75, 0.5 + off / VW * 0.75] : [0.5, 0.5 - off / VW, 0.5 + off / VW];
    allies.forEach((a, i) => {
      if (!a.img) return;
      const k = kz(ALLY_Z), hW = VH * ALLY_H * k, wW = hW * a.img.naturalWidth / a.img.naturalHeight;
      const feet = homeW(VW * xs[i], VH * 1.0, ALLY_Z);
      a.home = new T.Vector3(feet.x, feet.y, ALLY_Z + (i === 0 && n === 3 ? 0.25 : 0));
      a.mesh.scale.set(wW, hW, 1); a.mesh.position.y = hW / 2;
      a.halo.scale.set(wW * 1.6, hW * 1.15, 1); a.halo.position.y = hW * 0.55;
      a.hW = hW;
    });
  }
  let allyGen = 0;
  function setAllies(list) {
    for (const a of allies) scene.remove(a.group);
    const gen = ++allyGen, cuts = args.member_cuts || {};
    allies = list.map((m) => ({ lv: m.lv, group: new T.Group(), off: new T.Vector3(), hurtT: -9, op: 1, img: null }));
    for (const a of allies) loadAlly(a, cuts[String(a.lv)], gen);
  }
  async function loadAlly(a, uri, gen) {
    if (!uri) return;
    const img = new Image(); img.src = uri; await loaded(img);
    if (gen !== allyGen || !img.naturalWidth) return;
    a.img = img;
    {
      a.mesh = new T.Mesh(new T.PlaneGeometry(1, 1), new T.MeshBasicMaterial({ map: texFromImg(img), transparent: true, alphaTest: 0.03, depthWrite: false, side: T.DoubleSide }));
      a.halo = new T.Sprite(new T.SpriteMaterial({ map: TEX.glow, color: new T.Color("#ffe8a0"), transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false }));
      a.group.add(a.halo); a.group.add(a.mesh); a.halo.renderOrder = 5; a.mesh.renderOrder = 6;
      scene.add(a.group);
    }
    layoutAllies();
  }
  // パーティの状態（倒れた人・今動いている人）を立ち絵に映す
  let partyState = { mi: 0, dead: [] };
  W3D.party = function (members, mi) {
    if (!W3D.on) return;
    const lvs = members.map((m) => m.lv).join(",");
    if (lvs !== allies.map((a) => a.lv).join(",")) setAllies(members.map((m) => ({ lv: m.lv })));
    partyState = { mi, dead: members.map((m) => !!m.dead) };
  };

  // ---- カメラ ----
  function tween(ms, fn, ease) {
    ease = ease || ((k) => k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
    return new Promise((res) => { let t0 = null; jobs.push((now) => { if (t0 === null) t0 = now; const k = ms <= 0 ? 1 : Math.min(1, (now - t0) / ms); fn(ease(k)); if (k >= 1) { res(); return false; } return true; }); });
  }
  let camGen = 0;
  function camTo(o, ms) {
    if (!W3D.on) return Promise.resolve();
    const gen = ++camGen, s = { ...rig };
    const e = { yaw: o.yaw ?? s.yaw, pitch: o.pitch ?? s.pitch, dist: o.dist ?? s.dist, tx: o.tx ?? s.tx, ty: o.ty ?? s.ty, tz: o.tz ?? s.tz };
    if (reduce) ms = Math.min(ms, 200);
    return tween(ms, (k) => { if (gen !== camGen) return; for (const key in e) rig[key] = s[key] + (e[key] - s[key]) * k; });
  }
  W3D.camTo = camTo;
  W3D.home = (ms = 700) => camTo({ yaw: 0, pitch: 0, dist: DC, tx: 0, ty: 0, tz: 0 }, ms);
  W3D.isHome = () => Math.abs(rig.yaw) + Math.abs(rig.pitch) + Math.abs(rig.dist - DC) + Math.abs(rig.tx) + Math.abs(rig.ty) + Math.abs(rig.tz) < 1e-3;
  W3D.shake = (px) => { if (!W3D.on) return; shakeW = Math.max(shakeW, (reduce ? 0.2 : 1) * px * kz(0) * 0.6); };
  function foeWorld(i) {
    const s = scenes.filter((x) => x.ready).slice(-1)[0]; if (!s) return new T.Vector3();
    const f = s.foes[Math.max(0, Math.min(s.foes.length - 1, i || 0))]; if (!f) return new T.Vector3();
    return f.hold.position.clone();
  }
  // ねらっている敵に寄る
  W3D.focusFoe = (i, ms = 600) => { const p = foeWorld(i); return camTo({ tx: p.x * 0.5, ty: p.y * 0.35, tz: 0, dist: DC * 0.74, yaw: clamp(-p.x * 0.04, -0.2, 0.2) + 0.12, pitch: 0.04 }, ms); };
  // 味方（必殺技を使う人）に回りこむ
  W3D.focusAlly = (i, ms = 750) => {
    const a = allies[i]; if (!a || !a.home) return W3D.home(ms);
    const p = a.home.clone().add(new T.Vector3(0, (a.hW || 2) * 0.55, 0));
    const side = a.home.x === 0 ? 1 : Math.sign(a.home.x);
    return camTo({ tx: p.x, ty: p.y, tz: p.z, dist: 4.2, yaw: side * 0.5, pitch: 0.06 }, ms);
  };
  // 魔法の種類ごとのカメラ
  W3D.spellCam = (kind) => {
    if (!W3D.on) return Promise.resolve();
    const p = foeWorld(window.G && G.cur);
    switch (kind) {
      case "lance": case "holy": case "rain": case "meteor":       // 見上げてから、降ってくるものを追う
        return camTo({ pitch: -0.16, dist: DC * 1.05, ty: 1.2, tx: p.x * 0.3, yaw: -0.1 }, 700).then(() => camTo({ pitch: 0.08, ty: p.y * 0.3, dist: DC * 0.86 }, 900));
      case "explosion": case "earth": case "spirits":
        return camTo({ yaw: 0.28, pitch: 0.12, dist: DC * 0.95, tx: p.x * 0.4, ty: p.y * 0.2 }, 900);
      case "thunder":
        return camTo({ pitch: -0.08, dist: DC * 0.9, tx: p.x * 0.4, yaw: -0.15 }, 600);
      default:
        return camTo({ yaw: 0.22, dist: DC * 0.82, tx: p.x * 0.5, ty: p.y * 0.3, pitch: 0.05 }, 750);
    }
  };
  // 味方が敵へ踏みこむ（自分の連打の攻撃）
  W3D.lunge = async (mi, foeIdx) => {
    if (!W3D.on) return;
    const a = allies[mi]; const p = foeWorld(foeIdx);
    const camP = camTo({ tx: p.x * 0.45, ty: p.y * 0.3, dist: DC * 0.72, yaw: (a && a.home ? -Math.sign(a.home.x || 1) : 1) * 0.28, pitch: 0.05 }, 500);
    if (!a || !a.home) return camP;
    const to = new T.Vector3(p.x - a.home.x + (a.home.x > 0 ? 1.2 : -1.2), -0.2, p.z + 1.6 - a.home.z);
    await tween(380, (k) => { a.off.set(to.x * k, Math.sin(k * Math.PI) * 1.4 + to.y * k, to.z * k); }, (k) => 1 - Math.pow(1 - k, 3));
    a.back = true;
  };
  W3D.lungeBack = async (mi) => {
    if (!W3D.on) return;
    const a = allies[mi]; W3D.home(700);
    if (!a) return;
    const from = a.off.clone();
    await tween(450, (k) => { a.off.set(from.x * (1 - k), from.y * (1 - k) + Math.sin(k * Math.PI) * 0.8, from.z * (1 - k)); });
    a.off.set(0, 0, 0); a.back = false;
  };
  // 敵が攻撃で前に出る
  W3D.foeStrike = (i) => {
    if (!W3D.on) return;
    const s = scenes.filter((x) => x.ready).slice(-1)[0]; if (!s) return;
    const f = s.foes[Math.max(0, Math.min(s.foes.length - 1, i || 0))]; if (!f) return;
    f.strikeT = clock; W3D.shake(10);
  };
  W3D._allies = () => allies.map((a) => ({ lv: a.lv, img: !!a.img, home: a.home && a.home.toArray().map((v) => +v.toFixed(2)), op: +a.op.toFixed(2) }));
  W3D.allyHurt = (mi) => { const a = allies[mi]; if (a) a.hurtT = clock; };
  W3D.allyGlow = (mi, on) => { const a = allies[mi]; if (a) a.glowOn = !!on; };

  // ---- 毎フレーム ----
  function frame(now) {
    requestAnimationFrame(frame);
    const dt = Math.max(0, Math.min(0.05, (now - (last || now)) / 1000)); last = now; clock += dt;
    for (let i = jobs.length - 1; i >= 0; i--) if (jobs[i](now) === false) jobs.splice(i, 1);
    const tapping = app.classList.contains("tapping") || document.getElementById("aim")?.classList.contains("on");
    // カメラ（いつもは、ほんの少しゆれる。連打・ねらいの間は止める）
    const sway = tapping || reduce ? 0 : Math.sin(clock * 0.27) * 0.018;
    const quake = stage.classList.contains("quake") ? (stage.classList.contains("hard") ? 0.16 : 0.08) : 0;
    shakeW = Math.max(shakeW * Math.pow(0.02, dt), quake); if (shakeW < 0.002) shakeW = 0;
    const yaw = rig.yaw + sway, pitch = rig.pitch;
    camera.position.set(rig.tx + Math.sin(yaw) * Math.cos(pitch) * rig.dist, rig.ty + Math.sin(pitch) * rig.dist, rig.tz + Math.cos(yaw) * Math.cos(pitch) * rig.dist);
    camera.lookAt(rig.tx, rig.ty, rig.tz);
    if (shakeW > 0) { camera.position.x += rand(-shakeW, shakeW); camera.position.y += rand(-shakeW, shakeW); }
    camera.updateMatrixWorld();
    const camYaw = Math.atan2(camera.position.x - rig.tx, camera.position.z - rig.tz);
    // 敵
    let moved = false;
    for (const s of scenes) {
      if (!s.ready) continue;
      const sop = parseFloat(getComputedStyle(s.el).opacity) || 0;
      s.group.visible = sop > 0.01;
      if (s.back) s.back.material.opacity = sop, s.back.material.transparent = sop < 0.999;
      if (s.amb) { const P = s.amb.userData, a = s.amb.geometry.attributes.position.array;
        for (let i = 0; i < a.length; i += 3) { a[i + 1] += P.up * dt; a[i] += Math.sin(clock * 0.4 + i) * 0.05 * dt; if (a[i + 1] > 9) a[i + 1] = -8; }
        s.amb.geometry.attributes.position.needsUpdate = true; s.amb.material.opacity = 0.75 * sop * (0.75 + 0.25 * Math.sin(clock * 1.7)); }
      for (const f of s.foes) {
        const cl = f.el.classList;
        const dead = cl.contains("dead");
        if (dead && f.deadT === null) { f.deadT = clock; FX.dissolve(f); }
        if (!dead && f.deadT !== null) f.deadT = null;
        const fade = f.deadT === null ? 1 : Math.max(0, 1 - (clock - f.deadT) / 0.8);
        const bob = f.floating ? Math.sin(clock * 1.25 + f.seed) * f.h * 0.016 : 0;
        const gust = cl.contains("gust") ? Math.sin(clock * 5.7) * f.w * 0.22 : 0;
        const st = f.strikeT != null ? clock - f.strikeT : 9;
        const lunge = st < 0.6 ? Math.sin(Math.min(1, st / 0.6) * Math.PI) : 0;
        f.hold.position.set(f.base.x + gust, f.base.y + bob - lunge * 0.3, f.base.z + lunge * 2.6);
        f.hold.rotation.set(0, camYaw, cl.contains("gust") ? Math.sin(clock * 5.7) * 0.07 : 0);
        const fl = clock - f.flashT, struck = fl < 0.45 ? (fl < 0.18 ? 3 : 1 + 2 * (1 - (fl - 0.18) / 0.27)) : 1;
        const hit = cl.contains("hit") ? 1.6 : 1;
        f.mesh.material.color.setScalar(Math.max(struck, hit));
        f.mesh.material.opacity = fade * sop; f.mesh.material.transparent = true;
        f.glow.material.uniforms.uOp.value = cl.contains("sel") && !dead ? (0.55 + 0.25 * Math.sin(clock * 4)) * sop : 0;
        if (f.shadow) { f.shadow.material.opacity = fade * sop; f.shadow.position.x = f.base.x + gust; }
        f.mesh.visible = fade > 0.01;
        // 見えない影の絵を、3D の位置に合わせる（当たり判定・エフェクトの位置合わせ）
        f.hold.updateMatrixWorld();
        let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        for (const [u, v] of [[-.5, -.5], [.5, -.5], [.5, .5], [-.5, .5]]) {
          const p = new T.Vector3(u, v, 0).applyMatrix4(f.mesh.matrixWorld), s2 = toS(p);
          x0 = Math.min(x0, s2.x); x1 = Math.max(x1, s2.x); y0 = Math.min(y0, s2.y); y1 = Math.max(y1, s2.y);
        }
        const key = `${x0.toFixed(1)},${y0.toFixed(1)},${(x1 - x0).toFixed(1)},${(y1 - y0).toFixed(1)}`;
        if (key !== f.last) {
          f.last = key; moved = true;
          const st2 = f.el.style;
          st2.setProperty("left", x0 + "px", "important"); st2.setProperty("top", y0 + "px", "important");
          st2.setProperty("width", (x1 - x0) + "px", "important"); st2.setProperty("height", (y1 - y0) + "px", "important");
        }
      }
    }
    if (moved && window.G && G.multi && typeof window.layoutFoeBars === "function") window.layoutFoeBars();
    // 味方
    allies.forEach((a, i) => {
      if (!a.mesh || !a.home) return;
      const dead = !!partyState.dead[i], act = i === partyState.mi && !dead;
      const hurt = clock - a.hurtT, hk = hurt < 0.5 ? 1 - hurt / 0.5 : 0;
      const want = dead ? 0.38 : tapping && !a.back ? 0.22 : 1;
      a.op += (want - a.op) * Math.min(1, dt * 8);
      a.group.position.set(a.home.x + a.off.x + (hk ? Math.sin(hurt * 60) * 0.06 : 0), a.home.y + a.off.y + Math.sin(clock * 1.6 + i) * 0.03, a.home.z + a.off.z - hk * 0.25);
      a.mesh.rotation.set(0, camYaw, dead ? 0.05 : 0);
      const c = dead ? [0.42, 0.42, 0.46] : hk ? [1 + hk * 1.4, 1 - hk * 0.4, 1 - hk * 0.45] : [1, 1, 1];
      a.mesh.material.color.setRGB(c[0], c[1], c[2]); a.mesh.material.opacity = a.op;
      const hop = (act ? 0.35 + 0.12 * Math.sin(clock * 3) : 0) + (a.glowOn ? 0.6 : 0);
      a.halo.material.opacity += (hop * a.op - a.halo.material.opacity) * Math.min(1, dt * 6);
    });
    FX.update(dt);
    renderer.render(scene, camera);
  }

  // ---- 戦闘の開始（start のあと）。args の切り抜いた立ち絵を覚える ----
  W3D.attach = async function (a) {
    args = a || {};
    const ok = await boot();
    if (!ok) return;
    if (!started) { started = true; }
    rig.yaw = rig.pitch = rig.tx = rig.ty = rig.tz = 0; rig.dist = DC; camGen++;
    syncScenes();
    FX.clear();
  };

  // =========================================================================
  // エフェクト（MFX が出したものを、空間に置きかえて動かす）
  // =========================================================================
  const FX = (() => {
    const MAXP = 5000, MAXR = 60000, MAXS = 12000;
    let glowPts, smokePts, rockPts, ribbon, solid, uScale;
    const parts = [], strokes = [], solids = [], domes = [], voids = [], flyers = [];
    function pointsMat(kind) {
      const frag = {
        glow: "varying vec3 vC; varying float vA; void main(){ vec2 d = gl_PointCoord - .5; float r = length(d) * 2.; if (r > 1.) discard; vec3 c = r < .25 ? mix(vec3(1.), vC, r / .25) : vC; float a = r < .25 ? 1. : 1. - (r - .25) / .75; gl_FragColor = vec4(c, a * vA); }",
        smoke: "varying vec3 vC; varying float vA; void main(){ vec2 d = gl_PointCoord - .5; float r = length(d) * 2.; if (r > 1.) discard; gl_FragColor = vec4(vC, vA * (1. - smoothstep(.7, 1., r))); }",
        rock: "varying vec3 vC; varying float vA; void main(){ vec2 d = gl_PointCoord - .5; if (abs(d.x) * 1.1 + abs(d.y + .04) * .9 > .48) discard; gl_FragColor = vec4(vC * (1. - d.y * .8), vA); }",
      }[kind];
      return new T.ShaderMaterial({
        uniforms: { uScale: { value: 1 } },
        vertexShader: "uniform float uScale; attribute float size; attribute float alpha; attribute vec3 color; varying vec3 vC; varying float vA; void main(){ vC = color; vA = alpha; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = clamp(size * uScale / -mv.z, 1.0, 512.0); gl_Position = projectionMatrix * mv; }",
        fragmentShader: frag, transparent: true, depthWrite: false, depthTest: false,
        blending: kind === "glow" ? T.AdditiveBlending : T.NormalBlending,
      });
    }
    function pointsObj(kind) {
      const g = new T.BufferGeometry();
      g.setAttribute("position", new T.BufferAttribute(new Float32Array(MAXP * 3), 3).setUsage(T.DynamicDrawUsage));
      g.setAttribute("color", new T.BufferAttribute(new Float32Array(MAXP * 3), 3).setUsage(T.DynamicDrawUsage));
      g.setAttribute("size", new T.BufferAttribute(new Float32Array(MAXP), 1).setUsage(T.DynamicDrawUsage));
      g.setAttribute("alpha", new T.BufferAttribute(new Float32Array(MAXP), 1).setUsage(T.DynamicDrawUsage));
      const o = new T.Points(g, pointsMat(kind)); o.frustumCulled = false; o.renderOrder = kind === "glow" ? 30 : 28; o.n = 0;
      scene.add(o); return o;
    }
    function batchObj(add, max) {
      const g = new T.BufferGeometry();
      g.setAttribute("position", new T.BufferAttribute(new Float32Array(max * 3), 3).setUsage(T.DynamicDrawUsage));
      g.setAttribute("color", new T.BufferAttribute(new Float32Array(max * 3), 3).setUsage(T.DynamicDrawUsage));
      g.setAttribute("alpha", new T.BufferAttribute(new Float32Array(max), 1).setUsage(T.DynamicDrawUsage));
      g.setAttribute("edge", new T.BufferAttribute(new Float32Array(max * 2), 2).setUsage(T.DynamicDrawUsage));
      const m = new T.ShaderMaterial({
        vertexShader: "attribute vec3 color; attribute float alpha; attribute vec2 edge; varying vec3 vC; varying float vA; varying vec2 vE; void main(){ vC = color; vA = alpha; vE = edge; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
        fragmentShader: "varying vec3 vC; varying float vA; varying vec2 vE; void main(){ float e = abs(vE.x); float core = 1. - smoothstep(.45, 1., e); float soft = (1. - e) * (1. - e); gl_FragColor = vec4(vC, vA * mix(core, soft, vE.y)); }",
        transparent: true, depthWrite: false, depthTest: false, side: T.DoubleSide,
        blending: add ? T.AdditiveBlending : T.NormalBlending,
      });
      const o = new T.Mesh(g, m); o.frustumCulled = false; o.renderOrder = add ? 29 : 27; o.n = 0; o.max = max;
      scene.add(o); return o;
    }
    function init() {
      WHITE = new T.Color(1, 1, 1); UP = new T.Vector3(0, 1, 0); AX = new T.Vector3(1, 0, 0); AZ = new T.Vector3(0, 0, 1);
      glowPts = pointsObj("glow"); smokePts = pointsObj("smoke"); rockPts = pointsObj("rock");
      ribbon = batchObj(true, MAXR); solid = batchObj(false, MAXS);
    }
    function resize() { uScale = renderer.getDrawingBufferSize(new T.Vector2()).y / (2 * TAN); for (const o of [glowPts, smokePts, rockPts]) if (o) o.material.uniforms.uScale.value = uScale; }
    function clear() { parts.length = strokes.length = solids.length = flyers.length = 0; for (const d of domes) scene.remove(d.mesh); domes.length = 0; for (const v of voids) scene.remove(v.sprite); voids.length = 0; }
    const col = (c) => { const k = new T.Color(); try { k.set(c); } catch (e) { k.set("#ffffff"); } return k; };

    // ---- 粒を足す（空間の位置・速さで） ----
    function addPart(p) { if (parts.length < MAXP) parts.push(p); }
    function burstW(pos, n, o, k) {
      for (let i = 0; i < n; i++) {
        const a = rand(0, Math.PI * 2), s = rand(.2, 1) * (o.spd ?? 300) * k * (o.U ?? 1);
        addPart({ pos: pos.clone(), vel: new T.Vector3(Math.cos(a) * s, -Math.sin(a) * s, rand(-1, 1) * s * 0.6), life: o.life ?? rand(.4, .9), max: o.life ?? .9,
                  size: (o.size ?? 12) * k * (o.U ?? 1), color: col(Array.isArray(o.color) ? any(o.color) : o.color), drag: o.drag ?? 0.9, grav: -(o.grav ?? 0) * k, add: true, shrink: true });
      }
    }
    // 倒れた敵：絵の色の粒になって消える
    function dissolve(f) {
      const k = kz(f.z), n = 70;
      for (let i = 0; i < n; i++) {
        const p = f.hold.position.clone().add(new T.Vector3(rand(-.4, .4) * f.w, rand(-.45, .45) * f.h, rand(-.3, .3)));
        addPart({ pos: p, vel: new T.Vector3(rand(-40, 40) * k, rand(40, 160) * k, rand(-40, 40) * k), life: rand(.7, 1.3), max: 1.3, size: rand(6, 12) * k,
                  color: col(any(["#ffffff", "#ffe8c0", "#c8b8ff"])), drag: 0.96, grav: 0, add: true, shrink: true });
      }
    }
    // ---- MFX の配列から受けとる（画面の座標 → 空間） ----
    function ingest(src) {
      const U = src.U || 400, u = U / 420;
      // 粒
      for (const p of src.parts.splice(0)) {
        const pos = toW(p.x, p.y), k = kAt(pos);
        const spd = Math.hypot(p.vx, p.vy);
        const q = { pos, vel: new T.Vector3(p.vx * k, -p.vy * k, (p.sink || p.orbit) ? 0 : rand(-1, 1) * spd * k * 0.5), life: p.life, max: p.max, size: p.size * k,
                    color: col(p.color), drag: p.drag, grav: -p.grav * k, add: p.add, shrink: p.shrink, grow: p.grow, rock: p.rock, k };
        if (p.sink) q.sink = { p: toW(p.sink.x, p.sink.y), spin: p.sink.spin, slow: (p.sink.slow ?? 380) * k, minD: 14 * k };
        if (p.orbit) { const c = toW(p.orbit.x, p.orbit.y); const d = _v().subVectors(pos, c); q.orbit = { c, w: p.orbit.w, a: Math.atan2(d.y / 0.8, d.x), r: Math.hypot(d.x, d.y / 0.8) }; }
        addPart(q);
      }
      for (const r of src.rings.splice(0)) { const c = toW(r.x, r.y), k = kAt(c); strokes.push({ type: "ring", c, k, r1: r.r1 * k, w: r.w, color: col(r.color), t: r.t, dur: r.dur }); }
      for (const b of src.bolts.splice(0)) { const pts = b.pts.map(([x, y]) => toW(x, y)); strokes.push({ type: "bolt", pts, k: kAt(pts[pts.length - 1]), w: b.w, color: col(b.color), life: b.life, max: b.max }); }
      for (const c of src.cracks.splice(0)) {
        const [x0, y0] = c.pts[0], O = toW(x0, y0), k = kAt(O);
        const floor = nearFeet(y0);
        const pts = c.pts.map(([x, y]) => floor ? new T.Vector3(O.x + (x - x0) * k, O.y + 0.02, O.z + (y - y0) * k * 2.6) : toW(x, y));
        strokes.push({ type: "crack", pts, k, flat: floor, color: col(c.color), t: c.t, dur: c.dur });
      }
      for (const p of src.pillars.splice(0)) { const b = toW(p.x, p.gy), k = kAt(b); const top = toW(p.x, -VH * 0.25).y; strokes.push({ type: "pillar", b, top: Math.max(top, b.y + 4), w: p.w * k, color: col(p.color || "#fff0be"), t: p.t, dur: p.dur }); }
      for (const m of src.circles.splice(0)) { const c = toW(m.x, m.y), k = kAt(c); strokes.push({ type: "circle", c, k, r: m.r * k, color: col(m.color), t: m.t, dur: m.dur }); }
      for (const s of src.slashes.splice(0)) {
        const mx = (s.x1 + s.x2) / 2 - (s.y2 - s.y1) * s.bend, my = (s.y1 + s.y2) / 2 + (s.x2 - s.x1) * s.bend;
        const p1 = toW(s.x1, s.y1), p2 = toW(s.x2, s.y2), pm = toW(mx, my), k = kAt(pm);
        const dz = p1.distanceTo(p2) * 0.22 * rand(-1, 1);       // 斬撃に奥行きのかたむき
        p1.z += dz; p2.z -= dz;
        strokes.push({ type: "slash", p1, p2, pm, k, w: s.w * k, color: col(s.color), t: s.t, dur: s.dur, thorns: s.thorns });
      }
      for (const sp of src.spears.splice(0)) {
        const z = rand(-1.6, 1.6), tip = toW(sp.x, sp.y, z), k = kAt(tip), gy = toW(sp.x, sp.gy, z).y;
        strokes.push({ type: "spear", tip, gy, k, len: sp.len * k, vy: sp.vy * k, tilt: sp.tilt, color: col(sp.color), stuck: 0, life: sp.life, w: 7 * u * k });
      }
      for (const s of src.shards.splice(0)) {
        const pos = toW(s.x, s.y), k = kAt(pos);
        solids.push({ type: "shard", pos, vel: new T.Vector3(s.vx * k, -s.vy * k, rand(-1, 1) * Math.hypot(s.vx, s.vy) * k * .5), r: s.r, vr: s.vr, size: s.size * k, color: col(s.color), life: s.life, max: s.max, g: 900 * k });
      }
      for (const c of src.crystals.splice(0)) {
        const z = rand(-0.8, 0.8), b = toW(c.x, c.gy, z), k = kAt(b);
        solids.push({ type: "crystal", b, h: c.h * k, w: c.w * k, tilt: c.tilt, color: col(c.color), t: c.t, dur: c.dur });
      }
      for (const d of src.domes.splice(0)) {
        const c = toW(d.x, d.y), k = kAt(c);
        const m = new T.Mesh(new T.SphereGeometry(1, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), domeMat(col(d.color)));
        m.position.copy(c); m.renderOrder = 26; scene.add(m);
        domes.push({ mesh: m, r: d.r * k, t: d.t, dur: d.dur });
      }
      for (const o of src.orbs.splice(0)) {
        if (o.fly) {
          const p1 = toW(o.x1, o.y1), p2 = toW(o.x2, o.y2), k = kAt(p2);
          flyers.push({ p1, p2, pos: p1.clone(), arc: rand(1, 2.5), color: col(o.color), t: o.t, dur: o.dur, trail: o.trail, r: o.r * k, done: o.done });
        } else {
          const c = toW(o.x, o.y), k = kAt(c);
          const sp = new T.Sprite(new T.SpriteMaterial({ map: TEX.void, transparent: true, depthWrite: false, depthTest: false })); sp.renderOrder = 31;
          sp.position.copy(c); scene.add(sp);
          voids.push({ sprite: sp, r: o.r * k, grow: o.grow * k, t: o.t, dur: o.dur });
        }
      }
    }
    // 画面の y が、敵の足もとの近くか（ひび割れを地面に描くか）
    function nearFeet(y) {
      for (const f of W3D.foes()) { if (f.photo) continue; const r = f.el.getBoundingClientRect(); if (Math.abs(r.bottom - y) < 60) return true; }
      return false;
    }
    function domeMat(c) {
      return new T.ShaderMaterial({
        uniforms: { uC: { value: c }, uOp: { value: 1 } },
        vertexShader: "varying vec3 vN; varying vec3 vV; void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }",
        fragmentShader: "uniform vec3 uC; uniform float uOp; varying vec3 vN; varying vec3 vV; void main(){ float f = 1. - abs(dot(vN, vV)); gl_FragColor = vec4(uC, uOp * (pow(f, 2.2) * .95 + .05)); }",
        transparent: true, depthWrite: false, depthTest: false, side: T.DoubleSide, blending: T.AdditiveBlending,
      });
    }

    // ---- 線を帯にして描く ----
    let R, S;      // いま書きこんでいる帯（加算）・面（ふつう）
    const camPos = () => camera.position;
    function vtx(B, p, c, a, ex, soft) {
      if (B.n >= B.max) return;
      const i = B.n++, g = B.geometry.attributes;
      g.position.array[i * 3] = p.x; g.position.array[i * 3 + 1] = p.y; g.position.array[i * 3 + 2] = p.z;
      g.color.array[i * 3] = c.r; g.color.array[i * 3 + 1] = c.g; g.color.array[i * 3 + 2] = c.b;
      g.alpha.array[i] = a; g.edge.array[i * 2] = ex; g.edge.array[i * 2 + 1] = soft;
    }
    function quad(B, a, b, c, d, ca, cb, cc, cd, aa, ab, ac, ad, ea, eb, soft) {
      // a-b-c-d の順の四角（a,b が片方の辺、d,c がもう片方）
      vtx(B, a, ca, aa, ea, soft); vtx(B, b, cb, ab, eb, soft); vtx(B, c, cc, ac, eb, soft);
      vtx(B, a, ca, aa, ea, soft); vtx(B, c, cc, ac, eb, soft); vtx(B, d, cd, ad, ea, soft);
    }
    // 折れ線を帯に（n = 面の向き。省くと、カメラのほうを向く）
    function strip(pts, w, color, alpha, soft, n, colors, alphas) {
      if (pts.length < 2) return;
      const sides = pts.map((p, i) => {
        const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
        const t = _v().subVectors(b, a); if (t.lengthSq() < 1e-12) t.set(1, 0, 0); t.normalize();
        const view = n ? n : _v().subVectors(camPos(), p).normalize();
        const s = _v().crossVectors(t, view); if (s.lengthSq() < 1e-12) s.set(0, 1, 0);
        return s.normalize().multiplyScalar(w / 2);
      });
      for (let i = 0; i < pts.length - 1; i++) {
        const p = pts[i], q = pts[i + 1], sp = sides[i], sq = sides[i + 1];
        const cp = colors ? colors[i] : color, cq = colors ? colors[i + 1] : color, ap = alphas ? alphas[i] * alpha : alpha, aq = alphas ? alphas[i + 1] * alpha : alpha;
        quadE(p, q, sp, sq, cp, cq, ap, aq, soft);          // 片側の辺は +1、もう片側は -1（まん中が明るい）
      }
    }
    function quadE(p, q, sp, sq, cp, cq, ap, aq, soft) {
      const a = _v().addVectors(p, sp), b = _v().addVectors(q, sq), c = _v().subVectors(q, sq), d = _v().subVectors(p, sp);
      vtx(R, a, cp, ap, 1, soft); vtx(R, b, cq, aq, 1, soft); vtx(R, c, cq, aq, -1, soft);
      vtx(R, a, cp, ap, 1, soft); vtx(R, c, cq, aq, -1, soft); vtx(R, d, cp, ap, -1, soft);
    }
    // 光る線（まわりのぼんやりした光 ＋ 芯）
    function glowLine(pts, w, color, alpha, n, white) {
      strip(pts, w * 3.2, color, alpha * 0.42, 1, n);
      strip(pts, w, color, alpha, 0, n);
      if (white) strip(pts, w * white, WHITE, alpha, 0, n);
    }
    let WHITE, UP, AX, AZ;            // Three.js を読みこんでから作る（init）
    function circlePts(c, r, a0, a1, n, axisU, axisV) {
      const out = [];
      for (let i = 0; i <= n; i++) { const a = a0 + (a1 - a0) * i / n; out.push(c.clone().addScaledVector(axisU, Math.cos(a) * r).addScaledVector(axisV, Math.sin(a) * r)); }
      return out;
    }
    // 衝撃の輪：カメラに向けて、少し上に傾けた輪（いつもの位置で、楕円 0.62 に見える）
    function ringAxes() {
      const camDir = _v().subVectors(camPos(), new T.Vector3(rig.tx, rig.ty, rig.tz)).normalize();
      const n = _v().copy(camDir).multiplyScalar(0.62).addScaledVector(UP, 0.785).normalize();
      const u = _v().crossVectors(UP, n).normalize(); if (u.lengthSq() < 1e-6) u.copy(AX);
      const v = _v().crossVectors(n, u).normalize();
      return [u, v, n];
    }
    // 粒を1つ、このフレームだけ描く
    const once = [];
    function dot(pos, size, color, alpha) { once.push({ pos, size, color, alpha }); }

    function update(dt) {
      R = ribbon; S = solid; R.n = 0; S.n = 0;
      // 粒
      for (const p of parts) {
        p.life -= dt;
        if (p.sink) {
          const d = _v().subVectors(p.sink.p, p.pos), L = d.length() || 1e-6;
          p.vel.set(d.x / L * p.sink.slow + (-d.y / L) * p.sink.spin * 60 * p.k, d.y / L * p.sink.slow + (d.x / L) * p.sink.spin * 60 * p.k, d.z / L * p.sink.slow);
          if (L < p.sink.minD) p.life = 0;
        }
        if (p.orbit) {
          const o = p.orbit; o.a += o.w * dt; o.r *= 1 - 0.25 * dt;
          p.pos.set(o.c.x + Math.cos(o.a) * o.r, o.c.y + Math.sin(o.a) * o.r * 0.8, o.c.z + Math.sin(o.a) * o.r * 0.6);
          p.vel.set(0, 0, 0);
        }
        const dr = Math.pow(p.drag, dt * 60);
        p.vel.x *= dr; p.vel.z *= dr; p.vel.y = p.vel.y * dr + p.grav * dt;
        p.pos.addScaledVector(p.vel, dt);
      }
      for (let i = parts.length - 1; i >= 0; i--) if (parts[i].life <= 0) parts.splice(i, 1);
      // 線のもの
      for (const s of strokes) drawStroke(s, dt);
      for (let i = strokes.length - 1; i >= 0; i--) if (strokes[i].dead) strokes.splice(i, 1);
      for (const s of solids) drawSolid(s, dt);
      for (let i = solids.length - 1; i >= 0; i--) if (solids[i].dead) solids.splice(i, 1);
      // 飛んでいく光の玉
      for (const o of flyers) {
        o.t += dt; const k = Math.min(1, o.t / o.dur), e = k * k;
        o.pos.lerpVectors(o.p1, o.p2, e); o.pos.z += Math.sin(k * Math.PI) * o.arc;
        if (o.trail) { const s = toS(o.pos); for (let j = 0; j < 3; j++) o.trail(s.x, s.y); }
        dot(o.pos, o.r * 4, o.color, 1); dot(o.pos, o.r * 2, WHITE, 1);
        if (k >= 1) { o.dead = true; if (o.done) { o.done(); o.done = null; } }
      }
      for (let i = flyers.length - 1; i >= 0; i--) if (flyers[i].dead) flyers.splice(i, 1);
      for (const v of voids) { v.t += dt; const k = Math.min(1, v.t / v.dur), r = v.r + (v.grow - v.r) * Math.sin(k * Math.PI); v.sprite.scale.set(r * 3.2, r * 3.2, 1); if (k >= 1) { v.dead = true; scene.remove(v.sprite); v.sprite.material.dispose(); } }
      for (let i = voids.length - 1; i >= 0; i--) if (voids[i].dead) voids.splice(i, 1);
      for (const d of domes) { d.t += dt; const k = Math.min(1, d.t / .4), fade = Math.max(0, 1 - Math.max(0, d.t - d.dur + .5) / .5);
        d.mesh.scale.set(d.r * k, d.r * k * 0.8, d.r * k); d.mesh.material.uniforms.uOp.value = fade * .9;
        if (d.t > d.dur) { d.dead = true; scene.remove(d.mesh); d.mesh.geometry.dispose(); d.mesh.material.dispose(); } }
      for (let i = domes.length - 1; i >= 0; i--) if (domes[i].dead) domes.splice(i, 1);
      // 粒を書きこむ
      fillPoints();
      for (const B of [R, S]) { const g = B.geometry; for (const k in g.attributes) g.attributes[k].needsUpdate = true; g.setDrawRange(0, B.n); }
    }
    function fillPoints() {
      const G3 = glowPts, Sm = smokePts, Rk = rockPts;
      G3.n = Sm.n = Rk.n = 0;
      const put = (O, pos, size, c, a) => {
        if (O.n >= MAXP) return; const i = O.n++, g = O.geometry.attributes;
        g.position.array[i * 3] = pos.x; g.position.array[i * 3 + 1] = pos.y; g.position.array[i * 3 + 2] = pos.z;
        g.color.array[i * 3] = c.r; g.color.array[i * 3 + 1] = c.g; g.color.array[i * 3 + 2] = c.b;
        g.size.array[i] = size; g.alpha.array[i] = a;
      };
      for (const p of parts) {
        const k = Math.max(0, p.life / p.max), s = p.grow ? p.size * (1.6 - k * .6) : p.shrink ? p.size * k : p.size;
        if (p.add) put(G3, p.pos, s * 2, p.color, Math.min(1, k * 1.4));
        else if (p.rock) put(Rk, p.pos, s * 2, p.color, Math.min(1, k * 2));
        else put(Sm, p.pos, s * 2, p.color, k * .45);
      }
      for (const d of once) put(G3, d.pos, d.size, d.color, d.alpha);
      once.length = 0;
      for (const O of [G3, Sm, Rk]) { const g = O.geometry; for (const k in g.attributes) g.attributes[k].needsUpdate = true; g.setDrawRange(0, O.n); }
    }
    function drawStroke(s, dt) {
      switch (s.type) {
        case "ring": {
          s.t += dt; const k = Math.min(1, s.t / s.dur), e = 1 - Math.pow(1 - k, 3), rr = (4 * s.k) + (s.r1 - 4 * s.k) * e;
          const [u, v] = ringAxes();
          glowLine(circlePts(s.c, rr, 0, Math.PI * 2, 48, u, v), (s.w * (1 - k) + 1) * s.k, s.color, 1 - k);
          if (s.t > s.dur) s.dead = true; break;
        }
        case "bolt": {
          s.life -= dt; const a = Math.max(0, s.life / s.max) * (Math.random() < .2 ? .4 : 1);
          strip(s.pts, s.w * 4 * s.k * 2.2, s.color, a * .5, 1); strip(s.pts, s.w * 4 * s.k * .7, s.color, a, 0); strip(s.pts, s.w * s.k, WHITE, a, 0);
          if (s.life <= 0) s.dead = true; break;
        }
        case "crack": {
          s.t += dt; const k = Math.min(1, s.t / .25), fade = Math.max(0, 1 - Math.max(0, s.t - s.dur + .5) / .5);
          const pts = s.pts.slice(0, Math.max(2, Math.ceil(s.pts.length * k)));
          glowLine(pts, 3 * s.k * 1.4, s.color, fade, s.flat ? UP : null);
          if (s.t > s.dur) s.dead = true; break;
        }
        case "pillar": {
          s.t += dt; const k = Math.min(1, s.t / .15), fade = Math.max(0, 1 - Math.max(0, s.t - s.dur * .5) / (s.dur * .5));
          const w = s.w * (0.6 + 0.4 * k) * (1 + Math.sin(s.t * 40) * .04);
          const yTop = s.top, yBot = s.top - (s.top - s.b.y) * k;
          const side = _v().crossVectors(UP, _v().subVectors(camPos(), s.b)).setY(0).normalize();
          const P = (x, y) => new T.Vector3(s.b.x, y, s.b.z).addScaledVector(side, x);
          const xs = [-w / 2, -w * .15, 0, w * .15, w / 2], cs = [s.color, s.color, WHITE, s.color, s.color], as = [0, 1, 1, 1, 0];
          for (let i = 0; i < 4; i++) quad(R, P(xs[i], yTop), P(xs[i + 1], yTop), P(xs[i + 1], yBot), P(xs[i], yBot), cs[i], cs[i + 1], cs[i + 1], cs[i], as[i] * fade, as[i + 1] * fade, as[i + 1] * fade, as[i] * fade, 0, 0, 0);
          dot(new T.Vector3(s.b.x, yBot, s.b.z), w * 2.2, s.color, fade * k);
          if (s.t > s.dur) s.dead = true; break;
        }
        case "circle": {
          s.t += dt; const k = Math.min(1, s.t / .35), fade = Math.max(0, 1 - Math.max(0, s.t - s.dur + .4) / .4), rot = s.t * 1.2;
          const u = new T.Vector3(Math.cos(rot), 0, Math.sin(rot)), v = new T.Vector3(-Math.sin(rot), 0, Math.cos(rot));
          for (const rr of [1, .82, .5]) glowLine(circlePts(s.c, s.r * k * rr, 0, Math.PI * 2 * k, 56, u, v), 3 * s.k, s.color, fade, UP);
          const hex = []; for (let i = 0; i <= 6; i++) { const a = i * Math.PI * 4 / 6 - Math.PI / 2; hex.push(s.c.clone().addScaledVector(u, Math.cos(a) * s.r * .82 * k).addScaledVector(v, Math.sin(a) * s.r * .82 * k)); }
          glowLine(hex, 2.6 * s.k, s.color, fade, UP);
          for (let i = 0; i < 16; i++) { const a = i / 16 * Math.PI * 2; dot(s.c.clone().addScaledVector(u, Math.cos(a) * s.r * .91 * k).addScaledVector(v, Math.sin(a) * s.r * .91 * k), 9 * s.k, s.color, fade * .9); }
          if (s.t > s.dur) s.dead = true; break;
        }
        case "slash": {
          s.t += dt; const k = Math.min(1, s.t / (s.dur * .45)), fade = Math.max(0, 1 - Math.max(0, s.t - s.dur * .45) / (s.dur * .55));
          const q = (t) => new T.Vector3((1 - t) * (1 - t) * s.p1.x + 2 * (1 - t) * t * s.pm.x + t * t * s.p2.x, (1 - t) * (1 - t) * s.p1.y + 2 * (1 - t) * t * s.pm.y + t * t * s.p2.y, (1 - t) * (1 - t) * s.p1.z + 2 * (1 - t) * t * s.pm.z + t * t * s.p2.z);
          const pts = []; for (let i = 0; i <= 20; i++) pts.push(q(i / 20 * k));
          // 先が細く、元が太い三日月の形
          const al = pts.map((_, i) => 0.25 + 0.75 * Math.sin(Math.PI * Math.min(1, (i / 20) * 1.05)));
          strip(pts, s.w * 3, s.color, fade * .45, 1, null, null, al); strip(pts, s.w, s.color, fade, 0, null, null, al); strip(pts, s.w * .35, WHITE, fade, 0, null, null, al);
          if (s.thorns) for (let i = 1; i < 10; i++) { const t = i / 10 * k, p = q(t), sd = (i % 2 ? 1 : -1);
            const tip = p.clone().add(new T.Vector3(sd * s.w * 1.3, s.w * 1.3, 0)); glowLine([p, tip], s.w * .4, s.color, fade); }
          if (s.t > s.dur) s.dead = true; break;
        }
        case "spear": {
          if (!s.stuck) {
            s.tip.y -= s.vy * dt; s.tip.x += Math.sin(s.tilt) * s.vy * dt;
            if (s.tip.y <= s.gy) { s.tip.y = s.gy; s.stuck = 1; burstW(s.tip, 8, { color: s.color, spd: 160, size: 8, life: .4 }, s.k);
              ringStuck(s); }
          } else s.life -= dt;
          const a = Math.max(0, Math.min(1, s.life / .35));
          const tail = s.tip.clone().add(new T.Vector3(-Math.sin(s.tilt) * s.len, Math.cos(s.tilt) * s.len, 0));
          const mid = tail.clone().lerp(s.tip, .6);
          strip([tail, mid, s.tip], s.w * 2.4, s.color, a * .45, 1, null, [s.color, s.color, WHITE], [0, 1, 1]);
          strip([tail, mid, s.tip], s.w, s.color, a, 0, null, [s.color, s.color, WHITE], [0, 1, 1]);
          strip([tail.clone().lerp(s.tip, .4), s.tip], s.w * .32, WHITE, a, 0);
          if (s.stuck) dot(s.tip, s.k * 26, s.color, a);
          if (s.life <= 0) s.dead = true; break;
        }
      }
    }
    // 槍が刺さったところに、地面の小さな光の輪
    function ringStuck(s) { strokes.push({ type: "flatring", c: s.tip.clone(), k: s.k, r1: 30 * s.k, color: s.color, t: 0, dur: .45 }); }
    const _drawStroke = drawStroke;
    drawStroke = function (s, dt) {
      if (s.type === "flatring") {
        s.t += dt; const k = Math.min(1, s.t / s.dur), rr = s.r1 * (0.2 + 0.8 * (1 - Math.pow(1 - k, 3)));
        glowLine(circlePts(s.c, rr, 0, Math.PI * 2, 32, AX, AZ), 3 * s.k, s.color, 1 - k, UP);
        if (s.t > s.dur) s.dead = true; return;
      }
      _drawStroke(s, dt);
    };
    function drawSolid(s, dt) {
      if (s.type === "shard") {
        s.life -= dt; s.vel.y -= s.g * dt; s.pos.addScaledVector(s.vel, dt); s.r += s.vr * dt;
        const a = Math.max(0, s.life / s.max), toCam = _v().subVectors(camPos(), s.pos).normalize();
        const right = _v().crossVectors(UP, toCam).normalize(), up = _v().crossVectors(toCam, right).normalize();
        const c = Math.cos(s.r), sn = Math.sin(s.r);
        const P = (x, y) => s.pos.clone().addScaledVector(right, x * c - y * sn).addScaledVector(up, x * sn + y * c);
        const pts = [P(0, s.size), P(s.size * .45, 0), P(0, -s.size * .8), P(-s.size * .45, 0)];
        const hi = s.color.clone().lerp(WHITE, .5);
        quadS(pts[0], pts[1], pts[2], pts[3], hi, s.color, s.color, s.color, a);
        if (s.life <= 0) s.dead = true;
      } else if (s.type === "crystal") {
        s.t += dt; const k = Math.min(1, s.t / .18), fade = Math.max(0, 1 - Math.max(0, s.t - s.dur + .4) / .4);
        const toCam = _v().subVectors(camPos(), s.b).setY(0).normalize();
        const right = _v().crossVectors(UP, toCam).normalize();
        const c = Math.cos(s.tilt), sn = Math.sin(s.tilt), h = s.h * k;
        const P = (x, y) => s.b.clone().addScaledVector(right, x * c + y * sn).add(new T.Vector3(0, -x * sn * 0 + y * c, 0));
        const tipC = new T.Color("#eafff4"), midC = s.color.clone().lerp(tipC, .7);
        const b1 = P(-s.w / 2, 0), b2 = P(s.w / 2, 0), m1 = P(-s.w * .3, h * .8), m2 = P(s.w * .3, h * .8), tp = P(0, h);
        quadS(b1, b2, m2, m1, s.color, s.color, midC, midC, fade);
        triS(m1, m2, tp, midC, midC, tipC, fade);
        glowLine([P(0, 0), tp], s.w * .12, WHITE, fade * .7);
        dot(P(0, h * .5), s.w * 2.5, s.color, fade * .35);
        if (s.t > s.dur) s.dead = true;
      }
    }
    function quadS(a, b, c, d, ca, cb, cc, cd, al) {
      vtx(S, a, ca, al, 0, 0); vtx(S, b, cb, al, 0, 0); vtx(S, c, cc, al, 0, 0);
      vtx(S, a, ca, al, 0, 0); vtx(S, c, cc, al, 0, 0); vtx(S, d, cd, al, 0, 0);
    }
    function triS(a, b, c, ca, cb, cc, al) { vtx(S, a, ca, al, 0, 0); vtx(S, b, cb, al, 0, 0); vtx(S, c, cc, al, 0, 0); }
    function busy() { return parts.length || strokes.length || solids.length || flyers.length || voids.length || domes.length; }
    return { init, resize, clear, ingest, update, dissolve, busy };
  })();
  W3D.fxIngest = (src) => { if (W3D.on) FX.ingest(src); };
  W3D.fxBusy = () => W3D.on && FX.busy();
})();
