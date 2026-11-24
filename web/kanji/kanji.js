/* 漢字の書き取り。指やペンで書いた線を、お手本（KanjiVG の書き順）と比べて判定する。
 *
 * 判定するもの：書き順・画数・各画の向き・場所と形（大まかに）。
 * 「とめ・はね・はらい」は、オンのときだけ判定する（お手本の線の終わりの形から種類を決め、書いた線の終わりの動き＝止まったか・向きを変えたか・速く抜いたか と くらべる）。
 * 座標は KanjiVG と同じ 109 x 109 の中で比べる。
 */
const N_PTS = 40; // 線を何点に分けて比べるか
const BOX = 109;

// ---------- 幾何のヘルパー ----------
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

function polyLength(pts) {
  let len = 0;
  for (let i = 1; i < pts.length; i++) len += dist(pts[i - 1], pts[i]);
  return len;
}

/** 線を、長さが等しい間隔の n 点にならべ直す。 */
function resample(pts, n = N_PTS) {
  if (pts.length === 1) return Array.from({ length: n }, () => pts[0].slice());
  const total = polyLength(pts);
  if (total === 0) return Array.from({ length: n }, () => pts[0].slice());
  const step = total / (n - 1);
  const out = [pts[0].slice()];
  let acc = 0;
  let prev = pts[0];
  for (let i = 1; i < pts.length; i++) {
    let cur = pts[i];
    let d = dist(prev, cur);
    while (acc + d >= step && out.length < n) {
      const t = (step - acc) / d;
      const p = [prev[0] + (cur[0] - prev[0]) * t, prev[1] + (cur[1] - prev[1]) * t];
      out.push(p);
      prev = p;
      d = dist(prev, cur);
      acc = 0;
    }
    acc += d;
    prev = cur;
  }
  while (out.length < n) out.push(pts[pts.length - 1].slice());
  return out;
}

const meanDist = (a, b) => a.reduce((s, p, i) => s + dist(p, b[i]), 0) / a.length;
const maxDist = (a, b) => a.reduce((m, p, i) => Math.max(m, dist(p, b[i])), 0);
const centroid = (pts) => [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length];

/** SVG の path 文字列を点列にする（ブラウザーの機能で長さを測る）。 */
let measureSvg = null;
function samplePath(d, n = N_PTS) {
  if (!measureSvg) {
    measureSvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    measureSvg.setAttribute("width", "0");
    measureSvg.setAttribute("height", "0");
    measureSvg.style.position = "absolute";
    document.body.appendChild(measureSvg);
  }
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", d);
  measureSvg.appendChild(path);
  const total = path.getTotalLength();
  const pts = [];
  for (let i = 0; i < n; i++) {
    const p = path.getPointAtLength((total * i) / (n - 1));
    pts.push([p.x, p.y]);
  }
  measureSvg.removeChild(path);
  return { pts, len: total };
}

/** path をおよそ 1 ずつの点にする（線の終わりの形を見るため） */
function densePath(d) {
  samplePath("M0,0", 2);
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", d);
  measureSvg.appendChild(path);
  const L = path.getTotalLength(), n = Math.max(2, Math.round(L) + 1), pts = [];
  for (let i = 0; i < n; i++) { const p = path.getPointAtLength((L * i) / (n - 1)); pts.push([p.x, p.y]); }
  measureSvg.removeChild(path);
  return { pts, len: L };
}
const unitV = (v) => { const l = Math.hypot(v[0], v[1]) || 1; return [v[0] / l, v[1] / l]; };
const cosV = (a, b) => { const u = unitV(a), w = unitV(b); return u[0] * w[0] + u[1] * w[1]; };

/** 線の終わりに「はね」（急に向きを変えた短い部分）があるか。あれば その長さ、なければ 0。pts はおよそ 1 ずつ */
function hookLen(pts, maxS, minS, ang) {
  const n = pts.length, e = pts[n - 1], c = Math.cos((ang * Math.PI) / 180);
  for (let s = Math.ceil(minS); s <= maxS && s + 6 < n; s++) {
    const a = pts[n - 1 - s], b = pts[n - 1 - s - 6];
    if (Math.hypot(e[0] - a[0], e[1] - a[1]) < minS * 0.8) continue;
    if (cosV([a[0] - b[0], a[1] - b[1]], [e[0] - a[0], e[1] - a[1]]) < c) return s;
  }
  return 0;
}

/** お手本の1画の 終わりの種類："tome" / "hane" / "harai" / ""（はっきりしない画は 判定しない） */
function endKind(pts, L) {
  if (L < 12) return "";
  const n = pts.length, e = pts[n - 1], s = pts[0];
  const h = L >= 20 ? hookLen(pts, Math.min(22, L * 0.3), 3, 65) : 0;
  if (h) return unitV([e[0] - pts[n - 1 - h][0], e[1] - pts[n - 1 - h][1]])[1] < 0.2 ? "hane" : "";   // 下へ 折れるのは「はね」ではない（口の 2画目など）
  const v = unitV([e[0] - pts[Math.max(0, n - 7)][0], e[1] - pts[Math.max(0, n - 7)][1]]);
  const ov = [e[0] - s[0], e[1] - s[1]], chord = Math.hypot(ov[0], ov[1]);
  if (v[0] < -0.35 && v[1] > 0.25) return L >= 32 ? "harai" : "";                     // 左はらい（短い点は 判定しない）
  if (L >= 30 && v[0] > 0.6 && v[1] > -0.05 && ov[0] > 0 && ov[1] > 0.45 * ov[0]) return "harai";  // 右はらい（人・大の右の画）
  if (Math.abs(v[1]) < 0.3 && v[0] > 0 && Math.abs(ov[1]) < 0.3 * ov[0] && L < chord * 1.12) return "tome"; // 横画
  return "";
}
const END_NAME = { tome: "とめ", hane: "はね", harai: "はらい" };

/** 書いた線の 終わりの動き。pts：点、ts：その時刻（ms）、upT：指をはなした時刻 */
function userEnd(pts, ts, upT) {
  const L = polyLength(pts);
  if (L < 6 || pts.length < 3) return { kind: "", L };
  const d = resample(pts, Math.max(8, Math.round(L) + 1));
  const hook = hookLen(d, Math.min(20, L * 0.4), 2.5, 60);
  const dwell = Math.max(0, upT - ts[ts.length - 1]);
  // 終わりの 15%（4 以上）の速さ と 全体の 平均の速さ
  const tail = Math.max(4, L * 0.15);
  let acc = 0, i = pts.length - 1;
  while (i > 0 && acc < tail) { acc += dist(pts[i - 1], pts[i]); i--; }
  const tt = Math.max(8, ts[ts.length - 1] - ts[i]), all = Math.max(16, ts[ts.length - 1] - ts[0]);
  const ratio = (acc / tt) / (L / all);
  return { kind: hook ? "hane" : "", hook, dwell, ratio, L };
}

/** お手本の種類 want に、書いた線 u が 合っているか（指は ぶれるので あまめ）。true / false */
function endOk(want, u) {
  if (!want || !u || u.L < 6) return true;
  if (want === "hane") return u.hook > 0;
  if (want === "harai") return !u.hook && u.dwell < 160 && u.ratio >= 0.45;
  if (want === "tome") return !u.hook && !(u.dwell < 40 && u.ratio >= 1.6);
  return true;
}
const END_TIP = {
  hane: "さいごは 止まらずに、ぴょんと はねよう",
  harai: "さいごは 止まらずに、すっと はらおう",
  tome: "さいごは しっかり 止めてから はなそう",
};

// ---------- 筆っぽく 描く（とめ・はね判定 オンのとき） ----------
/** 書いた線の 終わりの見た目："tome"（止めた）/ "hane"（はねた）/ "harai"（速く抜いた）/ "" */
function userStyle(u) {
  if (!u || u.L < 6) return "";
  if (u.hook) return "hane";
  if (u.dwell >= 100 || u.ratio < 0.6) return "tome";
  if (u.dwell < 60 && u.ratio >= 0.85) return "harai";
  return "";
}

/** 点ごとの太さ（1 が ふつう）。ts があれば 速さで 太さを かえる（ゆっくり＝太い、速い＝細い）。
 *  style で 終わりの形：tome＝さいごを ふくらませる、harai＝先を 細く、hane＝はねの部分を 細く */
function brushWidths(pts, ts, style, hook) {
  const n = pts.length, cum = [0];
  for (let i = 1; i < n; i++) cum.push(cum[i - 1] + dist(pts[i - 1], pts[i]));
  const L = cum[n - 1] || 1;
  let f = pts.map(() => 1);
  if (ts && ts.length === n && n > 2) {
    f = pts.map((_, i) => {
      const a = Math.max(0, i - 2), b = Math.min(n - 1, i + 2), dt = Math.max(4, ts[b] - ts[a]);
      return Math.max(0.6, Math.min(1.3, 1.35 - ((cum[b] - cum[a]) / dt) * 2.6));
    });
    f = f.map((_, i) => { let s = 0, c = 0; for (let j = Math.max(0, i - 3); j <= Math.min(n - 1, i + 3); j++) { s += f[j]; c++; } return s / c; });
  }
  return f.map((w, i) => {
    if (cum[i] < 4) w = Math.max(w, 1.3 - cum[i] * 0.05);                 // 入り：「とん」と 置いて 太め
    const rest = L - cum[i];
    if (style === "harai") { const T = Math.min(Math.max(8, L * 0.4), 32); if (rest < T) w *= 0.12 + 0.88 * Math.pow(rest / T, 0.9); }
    else if (style === "hane") { const T = (hook || 5) + 3; if (rest < T) w *= 0.1 + 0.9 * Math.pow(rest / T, 1.2); }
    else if (style === "tome" && rest < 3.5) w = Math.max(w, 1.55);           // とめ：さいごに ぐっと 止めた ふくらみ
    return w;
  });
}

/** 点 P（描く座標）と 太さ W（描く単位）で、短い線を つないで 描く */
function brushDraw(g, P, W) {
  if (!P.length) return;
  g.lineCap = "round"; g.lineJoin = "round";
  if (P.length === 1) { g.beginPath(); g.arc(P[0][0], P[0][1], W[0] / 2, 0, Math.PI * 2); g.fill(); return; }
  for (let i = 1; i < P.length; i++) {
    g.lineWidth = (W[i - 1] + W[i]) / 2;
    g.beginPath(); g.moveTo(P[i - 1][0], P[i - 1][1]); g.lineTo(P[i][0], P[i][1]); g.stroke();
  }
  const e = P[P.length - 1];                    // とめの ふくらみを まるく
  g.beginPath(); g.arc(e[0], e[1], W[W.length - 1] / 2, 0, Math.PI * 2); g.fill();
}

/** 書いた線の 太さを決める：はねは どこから はねたか（長さ）も いる */
function hookOf(pts) {
  const L = polyLength(pts);
  if (L < 6) return 0;
  return hookLen(resample(pts, Math.max(8, Math.round(L) + 1)), Math.min(20, L * 0.4), 2.5, 60);
}

// ---------- 判定 ----------
/** 書いた線 user(n点) とお手本の1画 ref を比べる。 */
function compare(user, userLen, ref) {
  const fwd = meanDist(user, ref.pts);
  const rev = meanDist(user, [...ref.pts].reverse());
  const worst = maxDist(user, ref.pts);
  let ok, d;
  // 向きのチェック：はじまり→おわりの向きが 大きくちがう（逆向きに書いた）ときは NG
  let dirBad = false;
  if (!ref.dot && ref.len >= 12) {
    const e = ref.pts.length - 1;
    const vr = [ref.pts[e][0] - ref.pts[0][0], ref.pts[e][1] - ref.pts[0][1]];
    const vu = [user[e][0] - user[0][0], user[e][1] - user[0][1]];
    const lr = Math.hypot(vr[0], vr[1]), lu = Math.hypot(vu[0], vu[1]);
    if (lr >= 0.35 * ref.len) dirBad = !(lu > 0 && (vr[0] * vu[0] + vr[1] * vu[1]) / (lr * lu) >= 0.3);
    else dirBad = dist(user[0], ref.pts[0]) > ref.tol * 1.3; // ぐるっと回る線は、はじまりの場所で見る
  }
  if (ref.dot) {
    // 点（ちょん）は、場所が近くて、長すぎなければOK
    d = dist(centroid(user), centroid(ref.pts));
    ok = d <= ref.tol && userLen <= Math.max(26, ref.len * 3);
  } else {
    const ratio = userLen / ref.len;
    d = fwd;
    ok = !dirBad && fwd <= ref.tol && worst <= ref.tol * 2.1 && ratio > 0.4 && ratio < 2.4;
  }
  return { fwd, rev, worst, ok, d, dirBad };
}

/** idx 画目として書いた線が正しいか。「ほかの画のほうが もっと近い」ときは、書き順ちがいとして はじく。 */
function judgeAt(user, userLen, refs, idx) {
  const r = compare(user, userLen, refs[idx]);
  r.closer = -1;
  if (!r.ok) return r;
  let best = r.d * 0.88; // 本命より 1割以上 近い ほかの画があれば、そちらを書いたと みなす
  refs.forEach((o, j) => {
    if (j === idx) return;
    const dj = compare(user, userLen, o).d;
    if (dj < best) { best = dj; r.closer = j; }
  });
  if (r.closer >= 0) r.ok = false;
  return r;
}

/** お手本の各画を、点列にする。tol はゆるさ（お手本の線から どれくらいずれていいか）。 */
function buildRefs(paths, baseTol) {
  return paths.map((d) => {
    const { pts, len } = samplePath(d);
    const dense = densePath(d);
    const end = endKind(dense.pts, dense.len);
    return { pts, len, dot: len < 10, tol: baseTol, end, dense: dense.pts,
             hook: end === "hane" ? hookLen(dense.pts, Math.min(22, dense.len * 0.3), 3, 65) : 0 };
  });
}

// ---------- ゲーム本体 ----------
class KanjiGame {
  constructor(root, args, onDone) {
    this.root = root;
    this.onDone = onDone;
    this.round = args.round;
    this.mode = args.mode || "trace"; // trace=なぞり書き / recall=見て書く / reading=読みから書く
    this.baseTol = args.tol || 20;
    this.th = !!args.tomehane;           // とめ・はね・はらい も判定する
    this.list = (args.kanjis || []).filter((k) => k.s && k.s.length);
    this.q = 0;
    this.results = [];
    this.startedAt = 0;
    this.hintTimer = null;
    this.build();
    this.load();
    window.addEventListener("resize", () => this.fit());
  }

  build() {
    this.root.innerHTML = `
      <div class="kj">
        <div class="kj-top"><span class="kj-pill" data-r="count"></span><span class="kj-pill" data-r="mode"></span></div>
        <div class="kj-bar"><i data-r="bar"></i></div>
        <div class="kj-info" data-r="info"></div>
        <div class="kj-stage"><canvas data-r="cv"></canvas></div>
        <div class="kj-msg info" data-r="msg"></div>
        <div class="kj-btns">
          <button data-r="hint">${Icon.svg("bulb")}ヒント</button>
          <button data-r="clear">↩ この画を かきなおす</button>
          <button data-r="skip">${Icon.svg("eye")}わからない</button>
          <button class="primary" data-r="next" hidden>つぎへ ${Icon.svg("next")}</button>
        </div>
      </div>`;
    this.$ = (n) => this.root.querySelector(`[data-r="${n}"]`);
    this.cv = this.$("cv");
    this.ctx = this.cv.getContext("2d");
    this.$("mode").innerHTML = { trace: Icon.svg("pen") + "なぞり書き", recall: Icon.svg("bulb") + "見て書く", reading: Icon.svg("book") + "読みから書く" }[this.mode];
    this.$("hint").onclick = () => this.hint();
    this.$("clear").onclick = () => this.clearCurrent();
    this.$("skip").onclick = () => this.skip();
    this.$("next").onclick = () => this.next();
    const cv = this.cv;
    cv.addEventListener("pointerdown", (e) => this.down(e));
    cv.addEventListener("pointermove", (e) => this.move(e));
    cv.addEventListener("pointerup", (e) => this.up(e));
    cv.addEventListener("pointercancel", (e) => this.up(e));
    cv.addEventListener("contextmenu", (e) => e.preventDefault());
  }

  fit() {
    const size = Math.max(220, Math.min(this.root.clientWidth - 14, 460));
    const dpr = window.devicePixelRatio || 1;
    this.size = size;
    this.cv.style.width = this.cv.style.height = size + "px";
    this.cv.width = this.cv.height = Math.round(size * dpr);
    this.dpr = dpr;
    this.draw();
    Streamlit.setHeight();
  }

  load() {
    const k = this.list[this.q];
    this.k = k;
    this.refs = buildRefs(k.s, this.baseTol);
    this.idx = 0; // 次に書く画
    this.done = []; // 書けた線（点列）
    this.doneInk = []; // 書けた線の 筆の太さ（とめ・はね オンのとき）
    this.ghost = null; // とめ・はねが ちがった線（赤く 少しのあいだ 見せる）
    this.cur = null; // 書いている線
    this.stat = { misses: 0, hints: 0, firstTry: 0, tries: 0, shape: 0, accepted: 0, skipped: false, wrongOrder: 0, endMiss: 0 };
    this.info = [];     // 書けた画ごとの記録（AI先生に わたす「測ったデータ」用）
    this.endTries = 0;  // いまの画で とめ・はねを まちがえた回数
    this.endFail = new Set(); this.endPass = new Set();   // とめ・はねを まちがえた画・1回で できた画（記録して、次に 先に 教える）
    this.finished = false;
    this.hintIdx = -1;
    this.hintUsedForStroke = false;
    this.overlay = false;
    this.$("next").hidden = true;
    ["hint", "clear", "skip"].forEach((n) => { this.$(n).hidden = false; });
    this.$("count").textContent = `${this.q + 1} / ${this.list.length} もじめ`;
    this.$("bar").style.width = (this.q / this.list.length) * 100 + "%";
    this.renderInfo();
    this.say("info", `${k.s.length}画の かんじだよ。1画ずつ 書いてみよう！` + this.endHint(0));
    this.fit();
  }

  renderInfo() {
    const k = this.k;
    const kun = (k.k || []).join("・");
    const on = (k.o || []).join("・");
    const parts = [kun && `くん：${kun}`, on && `おん：${on}`].filter(Boolean).join("　");
    const meaning = (k.m || []).slice(0, 2).join(", ");
    const showKanji = this.mode !== "reading" || this.finished;
    this.$("info").innerHTML =
      (this.mode === "recall" || (this.mode === "reading" && this.finished) ? `<div class="big">${showKanji ? k.c : ""}</div>` : "") +
      (k.sent ? `<div class="sent">${Icon.svg("book")}${k.sent.replace(/【(.+?)】/g, '<b>$1</b>')}</div>` : "") +
      `<div class="read">${parts || "（よみ なし）"}</div>` +
      `<div class="sub">${k.s.length}画　${meaning ? "／ " + meaning : ""}</div>`;
  }

  /** とめ・はね判定がオンのとき：つぎの画の 終わりの形を 教える */
  endHint(i) {
    const e = this.th && this.refs[i] && this.refs[i].end;
    if (e && this.warned(i)) return `（注意！ 前に まちがえた画だよ。${i + 1}画目の さいごは「${END_NAME[e]}」）`;
    return e ? `（${i + 1}画目の さいごは「${END_NAME[e]}」）` : "";
  }
  warned(i) { return (this.k.warn || []).includes(i + 1); }

  say(kind, text) {
    const m = this.$("msg");
    m.className = "kj-msg " + kind;
    m.innerHTML = Icon.html(text);   // 絵文字はアイコンに
  }

  // ----- 描画 -----
  toPx(p) { return [(p[0] * this.size) / BOX, (p[1] * this.size) / BOX]; }

  draw() {
    const { ctx, size, dpr } = this;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);
    // 田の字の補助線
    ctx.strokeStyle = "#e6d8c3";
    ctx.lineWidth = 1;
    ctx.setLineDash([6, 6]);
    ctx.beginPath();
    ctx.moveTo(size / 2, 0); ctx.lineTo(size / 2, size);
    ctx.moveTo(0, size / 2); ctx.lineTo(size, size / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    const k = size / BOX;
    ctx.save();
    ctx.scale(k, k);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    // お手本（なぞり書きの間・書き終わって かさねるとき）
    const showGuide = this.mode === "trace" && !this.finished;
    if (showGuide) {
      this.k.s.forEach((d, i) => {
        ctx.strokeStyle = ctx.fillStyle = i < this.idx ? "#efe6d6" : "#cfd4dc";
        ctx.lineWidth = 5;
        if (this.th) this.refBrush(ctx, i, 5);
        else ctx.stroke(new Path2D(d));
      });
      // 次に書く画の 終わりの形を 小さな札で
      const nx = this.refs[this.idx];
      if (this.th && nx && nx.end) this.endTag(ctx, nx.dense, (this.warned(this.idx) ? "注意 " : "") + END_NAME[nx.end], this.warned(this.idx) ? "rgba(220,38,38,.95)" : null);
      // 次に書く画の はじまり（●）
      if (this.idx < this.refs.length) {
        const s = this.refs[this.idx].pts[0];
        ctx.fillStyle = "#2ecc71";
        ctx.beginPath(); ctx.arc(s[0], s[1], 3.4, 0, Math.PI * 2); ctx.fill();
      }
    }
    if (this.overlay || (this.finished && this.stat.skipped)) {
      this.k.s.forEach((d) => {
        ctx.strokeStyle = this.stat.skipped ? "#e74c3c" : "rgba(231,76,60,.55)";
        ctx.lineWidth = this.stat.skipped ? 5 : 2.4;
        ctx.stroke(new Path2D(d));
      });
    }
    // ヒント（次に書く画をオレンジで）
    if (this.hintIdx >= 0 && this.hintIdx < this.k.s.length) {
      ctx.strokeStyle = ctx.fillStyle = "rgba(255,140,0,.9)";
      ctx.lineWidth = 6;
      if (this.th) this.refBrush(ctx, this.hintIdx, 6);
      else ctx.stroke(new Path2D(this.k.s[this.hintIdx]));
      const s = this.refs[this.hintIdx].pts[0];
      ctx.fillStyle = "#2ecc71";
      ctx.beginPath(); ctx.arc(s[0], s[1], 4, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();

    // 書いた線
    const ink = (pts, color) => {
      if (!pts || pts.length < 1) return;
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = Math.max(5, size / 40);
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      pts.forEach((p, i) => { const [x, y] = this.toPx(p); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      if (pts.length === 1) { const [x, y] = this.toPx(pts[0]); ctx.arc(x, y, ctx.lineWidth / 2, 0, Math.PI * 2); ctx.fill(); }
      else ctx.stroke();
    };
    if (!this.th) {
      this.done.forEach((pts) => ink(pts, "#2c3e70"));
      ink(this.cur, "#e67e22");
      return;
    }
    // とめ・はね オン：筆っぽく（太さが 変わる）
    const W = Math.max(6, size / 30);
    const brush = (pts, ws, color) => {
      ctx.strokeStyle = ctx.fillStyle = color;
      brushDraw(ctx, pts.map((p) => this.toPx(p)), ws.map((w) => w * W));
    };
    if (this.ghost) {
      brush(this.ghost.pts, this.ghost.ws, "rgba(231,76,60,.75)");
      const [x, y] = this.toPx(this.ghost.pts[this.ghost.pts.length - 1]);
      ctx.strokeStyle = "#e74c3c"; ctx.lineWidth = 2; ctx.setLineDash([4, 3]);
      ctx.beginPath(); ctx.arc(x, y, W * 1.6, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
    }
    this.done.forEach((pts, i) => brush(pts, this.doneInk[i] || pts.map(() => 1), "#1f2533"));
    if (this.cur) brush(this.cur, brushWidths(this.cur, this.curT, ""), "#e67e22");
  }

  /** お手本の i 画目を 筆っぽく（とめは ふくらみ、はね・はらいは 先を 細く）。ctx は 109 の座標 */
  refBrush(ctx, i, base) {
    const r = this.refs[i];
    brushDraw(ctx, r.dense, brushWidths(r.dense, null, r.end, r.hook).map((w) => w * base));
  }

  /** 線の 終わりの そばに 小さな札（「はね」など） */
  endTag(ctx, pts, text, color) {
    ctx.save();
    ctx.font = "bold 5.5px sans-serif";
    // 線の 終わりの 先（線が 進んでいた向きの その先）に 置いて、線に かさならないように
    const e = pts[pts.length - 1], a = pts[Math.max(0, pts.length - 6)], v = unitV([e[0] - a[0], e[1] - a[1]]);
    const w = ctx.measureText(text).width + 4, cx = e[0] + v[0] * (w / 2 + 4), cy = e[1] + v[1] * 8;
    const x = Math.min(BOX - w - 1, Math.max(1, cx - w / 2)), y = Math.min(BOX - 8.5, Math.max(1, cy - 3.75));
    ctx.fillStyle = color || "rgba(255,140,0,.92)";
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, 7.5, 2) : ctx.rect(x, y, w, 7.5); ctx.fill();
    ctx.fillStyle = "#fff"; ctx.fillText(text, x + 2, y + 5.8);
    ctx.restore();
  }

  // ----- 入力 -----
  pos(e) {
    const r = this.cv.getBoundingClientRect();
    return [((e.clientX - r.left) / r.width) * BOX, ((e.clientY - r.top) / r.height) * BOX];
  }

  down(e) {
    if (this.finished) return;
    e.preventDefault();
    this.cv.setPointerCapture(e.pointerId);
    if (!this.startedAt) this.startedAt = performance.now();
    this.hintIdx = -1;
    clearTimeout(this.hintTimer);
    this.cur = [this.pos(e)];
    this.curT = [e.timeStamp];
    this.ghost = null;
    this.draw();
  }

  move(e) {
    if (!this.cur) return;
    e.preventDefault();
    const events = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
    for (const ev of events.length ? events : [e]) {
      const p = this.pos(ev);
      if (dist(p, this.cur[this.cur.length - 1]) > 0.4) { this.cur.push(p); this.curT.push(ev.timeStamp); }
    }
    this.draw();
  }

  up(e) {
    if (!this.cur) return;
    e.preventDefault();
    const pts = this.cur, ts = this.curT;
    this.cur = null;
    this.judge(pts, ts, e.timeStamp);
  }

  // ----- 判定 -----
  judge(pts, ts, upT) {
    const len = polyLength(pts);
    const ref = this.refs[this.idx];
    if (len < 2.5 && !ref.dot) {
      this.draw();
      return this.say("info", "みじかすぎるよ。もうすこし 長く 書いてみよう！");
    }
    const user = resample(pts);
    this.stat.tries++;
    const r = judgeAt(user, len, this.refs, this.idx);
    if (r.ok && this.th && ref.end) {
      const u = userEnd(pts, ts || [], upT || 0);
      r.endOk = endOk(ref.end, u);
      if (!r.endOk && this.endTries < 2) return this.endReject(ref.end, pts, ts, u);
    }
    if (r.ok && this.th) {
      // 筆の太さ：とめ・はねが 合っていれば お手本の形で、ちがえば 書いたとおりの形で 残す
      const u = userEnd(pts, ts || [], upT || 0);
      const style = ref.end && r.endOk !== false ? ref.end : userStyle(u);
      this.doneInk[this.idx] = brushWidths(pts, ts, style, style === "hane" ? (u.hook || hookOf(pts)) : 0);
    }
    if (r.ok) return this.accept(pts, r, user, len);
    this.reject(user, len, r);
  }

  /** 形は合っているが、とめ・はね・はらい が ちがう：もう一回（2回まちがえたら、そのまま通す） */
  endReject(want, pts, ts, u) {
    // 書いた線を 赤で 少しのあいだ 見せる（止まった所は ふくらみ、はねた所は はね で）。終わりに 点線の 丸
    const st = userStyle(u);
    this.ghost = { pts, ws: brushWidths(pts, ts, st, st === "hane" ? u.hook : 0) };
    clearTimeout(this.ghostTimer);
    this.ghostTimer = setTimeout(() => { this.ghost = null; this.draw(); }, 1800);
    this.endTries++;
    this.stat.endMiss++;
    this.endFail.add(this.idx + 1);
    this.stat.failedThisStroke = true;
    const did = { tome: "止まっていたよ", hane: "はねていたよ", harai: "はらっていたよ" }[st];
    this.say("ng", `❌ 形は いいね！ でも ${this.idx + 1}画目は「${END_NAME[want]}」。${did ? "赤い丸の所で " + did + "。" : ""}${END_TIP[want]}。`);
    this.cv.classList.remove("shake");
    void this.cv.offsetWidth;
    this.cv.classList.add("shake");
    this.draw();
  }

  accept(pts, r, user, len) {
    const firstTry = !this.stat.failedThisStroke && this.hintIdx !== this.idx && !this.hintUsedForStroke;
    if (firstTry) this.stat.firstTry++;
    // 形の点（0〜1）：ずれが小さいほど高い
    const shape = Math.max(0, Math.min(1, (this.refs[this.idx].tol - r.fwd) / (this.refs[this.idx].tol * 0.65)));
    this.stat.shape += shape;
    this.stat.accepted++;
    const ref = this.refs[this.idx];
    this.info.push({ i: this.idx, user: user || resample(pts), len: len || polyLength(pts), end: this.th ? ref.end : "",
                     endOk: !(this.th && ref.end) || r.endOk !== false });
    if (this.th && ref.end && this.endTries === 0 && r.endOk !== false) this.endPass.add(this.idx + 1);
    const endMsg = this.th && ref.end ? (r.endOk === false ? `（「${END_NAME[ref.end]}」は つぎ がんばろう）` : `「${END_NAME[ref.end]}」も できたね。`) : "";
    this.endTries = 0;
    this.done.push(pts);
    this.idx++;
    this.stat.failedThisStroke = false;
    this.hintUsedForStroke = false;
    this.hintIdx = -1;
    this.cv.classList.remove("good");
    void this.cv.offsetWidth;
    this.cv.classList.add("good");
    if (this.idx >= this.refs.length) return this.complete();
    this.say("ok", `⭕ ${this.idx}画目 OK！${endMsg} つぎは ${this.idx + 1}画目。` + this.endHint(this.idx));
    this.draw();
  }

  reject(user, len, r) {
    this.stat.misses++;
    this.stat.failedThisStroke = true;
    let msg = "ばしょや 形が ちがうみたい。もう一回 ためしてみよう。";
    const refs = this.refs;
    // どの画と似ているか調べて、くわしく教える
    let later = r.closer > this.idx ? r.closer : -1;
    let earlier = r.closer >= 0 && r.closer < this.idx ? r.closer : -1;
    if (r.closer < 0) {
      const matches = (j) => compare(user, len, refs[j]).ok;
      later = refs.findIndex((_, j) => j > this.idx && matches(j));
      earlier = refs.findIndex((_, j) => j < this.idx && matches(j));
    }
    if (r.dirBad && r.fwd <= refs[this.idx].tol * 1.6) msg = "向きが ぎゃくだよ。はじまりの ●から 書いてみよう。";
    else if (later >= 0) { msg = `その線は ${later + 1}画目みたい。いまは ${this.idx + 1}画目を 書こう。（書き順に ちゅうい！）`; this.stat.wrongOrder++; }
    else if (earlier >= 0) msg = "その線は もう 書いたよ。つぎの 画を 書こう。";
    this.say("ng", "❌ " + msg);
    this.cv.classList.remove("shake");
    void this.cv.offsetWidth;
    this.cv.classList.add("shake");
    this.draw();
    // 2回まちがえたら、次の画を ヒントとして 光らせる（点は ひかない）
    if (this.stat.misses >= 2 && this.hintIdx !== this.idx) this.showHint(false);
  }

  // ----- ボタン -----
  showHint(costly) {
    clearTimeout(this.hintTimer);
    this.hintIdx = this.idx;
    if (costly) { this.stat.hints++; this.hintUsedForStroke = true; }
    this.draw();
    this.hintTimer = setTimeout(() => { this.hintIdx = -1; this.draw(); }, 2600);
  }

  hint() {
    if (this.finished) return;
    this.showHint(true);
    this.say("info", `💡 ${this.idx + 1}画目は オレンジの線だよ。（ヒントを つかうと 点が ちょっと へるよ）`);
  }

  clearCurrent() {
    this.cur = null;
    this.say("info", "もう一度 この画を 書いてみよう。");
    this.draw();
  }

  skip() {
    this.stat.skipped = true;
    this.finishKanji(0);
    this.say("ng", `🙈 ざんねん。正しい書き方（赤い線）を 見て おぼえよう。「${this.k.c}」`);
  }

  complete() {
    const n = this.refs.length;
    const acc = Math.max(0, 6 * (this.stat.firstTry / n) - 1.5 * this.stat.hints);
    const shape = 4 * (this.stat.shape / Math.max(1, this.stat.accepted));
    const points = Math.round((acc + shape) * 10) / 10;
    this.overlay = false;
    this.finishKanji(points);
    const stars = points >= 9 ? "🌟 すごい！ きれいに かけたよ！" : points >= 7 ? "⭐ よくできました！" : "👍 かけたよ！ 次は ミスなしで ねらおう。";
    this.say("ok", `🎉 かんせい！ ${points}点 / 10点　${stars}`);
  }

  finishKanji(points) {
    this.finished = true;
    clearTimeout(this.hintTimer);
    this.hintIdx = -1;
    this.results.push({
      ch: this.k.c, strokes: this.refs.length, misses: this.stat.misses, hints: this.stat.hints,
      wrongOrder: this.stat.wrongOrder, skipped: this.stat.skipped, points, endMiss: this.stat.endMiss,
      endFail: [...this.endFail], endPass: [...this.endPass],
      img: this.stat.skipped ? "" : this.inkImage(),       // 書いた字（けっかの画面に出す）
      cmp: this.stat.skipped ? "" : this.cmpImage(),       // お手本と ならべた画像（AI先生用）
      facts: this.stat.skipped ? [] : this.facts(),        // アプリが 測った データ（AI先生用）
    });
    ["hint", "clear", "skip"].forEach((n) => { this.$(n).hidden = true; });
    const next = this.$("next");
    next.hidden = false;
    next.innerHTML = this.q + 1 >= this.list.length ? "けっかを 見る " + Icon.svg("trophy") : "つぎへ " + Icon.svg("next");
    this.renderInfo();
    // 書き終わったら お手本を うすく かさねて、見くらべられるようにする
    this.overlay = !this.stat.skipped;
    this.draw();
  }

  // 書いた線だけの 小さい画像（白地・黒線・うすい十字線）。JPEG で数KB
  inkImage() {
    try {
      const N = 192, c = document.createElement("canvas"); c.width = c.height = N;
      const g = c.getContext("2d"), k = N / BOX;
      g.fillStyle = "#fff"; g.fillRect(0, 0, N, N);
      g.strokeStyle = "#e3e3e3"; g.lineWidth = 1; g.setLineDash([4, 4]);
      g.beginPath(); g.moveTo(N / 2, 0); g.lineTo(N / 2, N); g.moveTo(0, N / 2); g.lineTo(N, N / 2); g.stroke(); g.setLineDash([]);
      g.strokeStyle = g.fillStyle = "#111"; g.lineWidth = N / 30; g.lineCap = g.lineJoin = "round";
      if (this.th) {         // とめ・はね オン：けっかの絵も 筆っぽく
        this.done.forEach((pts, i) => brushDraw(g, pts.map((p) => [p[0] * k, p[1] * k]), (this.doneInk[i] || pts.map(() => 1)).map((w) => w * N / 26)));
        return c.toDataURL("image/jpeg", .8);
      }
      this.done.forEach(pts => {
        if (!pts || !pts.length) return;
        g.beginPath();
        if (pts.length === 1) { g.arc(pts[0][0] * k, pts[0][1] * k, g.lineWidth / 2, 0, Math.PI * 2); g.fill(); return; }
        pts.forEach((p, i) => i ? g.lineTo(p[0] * k, p[1] * k) : g.moveTo(p[0] * k, p[1] * k));
        g.stroke();
      });
      return c.toDataURL("image/jpeg", .8);
    } catch (e) { return ""; }
  }

  // 左に お手本、右に 書いた字（どちらも 書き順の番号つき）。AI先生が 見くらべるため
  cmpImage() {
    try {
      const N = 192, G = 10, c = document.createElement("canvas"); c.width = N * 2 + G; c.height = N;
      const g = c.getContext("2d"), k = N / BOX;
      g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, N);
      g.fillStyle = "#ccc"; g.fillRect(N + G / 2 - 1, 0, 2, N);
      const panel = (x0, strokes, color, numColor) => {
        g.save(); g.translate(x0, 0);
        g.strokeStyle = "#e3e3e3"; g.lineWidth = 1; g.setLineDash([4, 4]);
        g.beginPath(); g.moveTo(N / 2, 0); g.lineTo(N / 2, N); g.moveTo(0, N / 2); g.lineTo(N, N / 2); g.stroke(); g.setLineDash([]);
        g.lineCap = g.lineJoin = "round";
        strokes.forEach((st, n) => {
          g.strokeStyle = g.fillStyle = color; g.lineWidth = N / 30;
          if (typeof st === "string") { g.save(); g.scale(k, k); g.lineWidth = BOX / 30; g.stroke(new Path2D(st)); g.restore(); }
          else if (st.length === 1) { g.beginPath(); g.arc(st[0][0] * k, st[0][1] * k, g.lineWidth / 2, 0, Math.PI * 2); g.fill(); }
          else { g.beginPath(); st.forEach((p, i) => i ? g.lineTo(p[0] * k, p[1] * k) : g.moveTo(p[0] * k, p[1] * k)); g.stroke(); }
        });
        g.font = "bold 11px sans-serif"; g.fillStyle = numColor;
        strokes.forEach((st, n) => {
          const p = typeof st === "string" ? this.refs[n].pts[0] : st[0];
          g.fillText(String(n + 1), Math.min(N - 10, Math.max(1, p[0] * k - 11)), Math.min(N - 2, Math.max(10, p[1] * k - 3)));
        });
        g.restore();
      };
      panel(0, this.k.s, "#555", "#d33");
      panel(N + G, this.done, "#111", "#16c");
      return c.toDataURL("image/jpeg", .8);
    } catch (e) { return ""; }
  }

  // 書いた線と お手本を 数字で くらべて、わかりやすい ことばにする（大きいずれから 4つまで ＋ よかった画）
  facts() {
    const info = this.info, F = [];
    if (!info.length) return F;
    const box = (P) => {
      let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
      P.forEach(([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); });
      return { w: x1 - x0, h: y1 - y0, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 };
    };
    const U = box(info.flatMap((x) => x.user)), Rb = box(info.flatMap((x) => this.refs[x.i].pts));
    const sw = U.w / Math.max(1, Rb.w), sh = U.h / Math.max(1, Rb.h);
    const wari = (v) => Math.round(v * 10);
    const dirOf = (dx, dy) => {
      const d = Math.hypot(dx, dy) || 1;
      return (Math.abs(dx) > 0.45 * d ? (dx > 0 ? "右" : "左") : "") + (Math.abs(dy) > 0.45 * d ? (dy > 0 ? "下" : "上") : "");
    };
    const big = Rb.w > 15 && Rb.h > 15;
    if (big && (sw < 0.82 || sh < 0.82) && sw < 1.1 && sh < 1.1) F.push({ s: 2 - Math.min(sw, sh), t: `字全体が お手本より 小さい（横${wari(sw)}割・たて${wari(sh)}割）` });
    else if (big && (sw > 1.2 || sh > 1.2) && sw > 0.9 && sh > 0.9) F.push({ s: Math.max(sw, sh), t: `字全体が お手本より 大きい（横${sw.toFixed(1)}倍・たて${sh.toFixed(1)}倍）` });
    else if (big && sw / sh > 1.25) F.push({ s: sw / sh, t: `字が お手本より 横長（たてが みじかめ）` });
    else if (big && sh / sw > 1.25) F.push({ s: sh / sw, t: `字が お手本より たて長（横が せまめ）` });
    const gx = U.cx - Rb.cx, gy = U.cy - Rb.cy;
    if (Math.hypot(gx, gy) > 8) F.push({ s: Math.hypot(gx, gy) / 8, t: `字全体が ます目の中で ${dirOf(gx, gy)}に よっている` });
    // 字の中での 各画：書いた字を お手本の大きさ・位置に 合わせてから くらべる
    const kx = U.w > 15 && Rb.w > 15 ? Rb.w / U.w : 1 / (((sw + sh) / 2) || 1);
    const ky = U.h > 15 && Rb.h > 15 ? Rb.h / U.h : 1 / (((sw + sh) / 2) || 1);
    const norm = (p) => [Rb.cx + (p[0] - U.cx) * kx, Rb.cy + (p[1] - U.cy) * ky];
    const good = [];
    info.forEach((x) => {
      const ref = this.refs[x.i], n = x.i + 1, P = x.user.map(norm);
      const off = [centroid(P)[0] - centroid(ref.pts)[0], centroid(P)[1] - centroid(ref.pts)[1]], od = Math.hypot(off[0], off[1]);
      const ul = polyLength(P), lr = ul / Math.max(1, ref.len);
      const e = ref.pts.length - 1, vr = [ref.pts[e][0] - ref.pts[0][0], ref.pts[e][1] - ref.pts[0][1]], vu = [P[e][0] - P[0][0], P[e][1] - P[0][1]];
      let ang = 0;
      if (!ref.dot && ref.len >= 15 && Math.hypot(vr[0], vr[1]) > ref.len * 0.6) ang = (Math.atan2(vu[1], vu[0]) - Math.atan2(vr[1], vr[0])) * 180 / Math.PI;
      ang = ((ang + 540) % 360) - 180;
      let bad = false;
      if (!ref.dot && od > 7) { F.push({ s: od / 7, t: `${n}画目の 場所が 字の中で ${dirOf(off[0], off[1])}に ずれている` }); bad = true; }
      if (!ref.dot && ref.len >= 12 && lr < 0.75) { F.push({ s: (1 - lr) / 0.25, t: `${n}画目が お手本より 短い（${wari(lr)}割くらい）` }); bad = true; }
      else if (!ref.dot && ref.len >= 12 && lr > 1.3) { F.push({ s: (lr - 1) / 0.3, t: `${n}画目が お手本より 長い（${lr.toFixed(1)}倍くらい）` }); bad = true; }
      if (Math.abs(ang) > 14) {
        const ra = Math.atan2(vr[1], vr[0]) * 180 / Math.PI;
        let t = `${n}画目の 向き・かたむきが お手本と ちがう（${Math.round(Math.abs(ang))}度くらい）`;
        if (Math.abs(ra) < 30) t = ang < 0 ? `${n}画目（横の線）の 右上がりが 強すぎる` : `${n}画目（横の線）が 右下がりに なっている`;
        else if (Math.abs(ra - 90) < 25) t = `${n}画目（たての線）が まっすぐでなく、${ang < 0 ? "右" : "左"}に かたむいている`;
        F.push({ s: Math.abs(ang) / 14, t }); bad = true;
      }
      if (x.end && !x.endOk) { F.push({ s: 2.5, t: `${n}画目の「${END_NAME[x.end]}」が できていない` }); bad = true; }
      if (!bad && od < 4.5 && lr > 0.85 && lr < 1.18 && Math.abs(ang) < 8) good.push(n);
    });
    const out = F.sort((a, b) => b.s - a.s).slice(0, 4).map((f) => f.t);
    const ends = info.filter((x) => x.end && x.endOk).map((x) => `${x.i + 1}画目（${END_NAME[x.end]}）`);
    if (good.length) out.push(`お手本に とても近い画：${good.slice(0, 5).join("・")}画目`);
    if (ends.length) out.push(`できていた とめ・はね・はらい：${ends.slice(0, 4).join("、")}`);
    if (!F.length) out.push("大きな ずれは 見つからなかった");
    return out;
  }

  next() {
    if (this.q + 1 >= this.list.length) return this.finish();
    this.q++;
    this.cv.classList.remove("good");
    this.load();
  }

  finish() {
    const time = Math.round((performance.now() - (this.startedAt || performance.now())) / 100) / 10;
    this.root.innerHTML = `<div class="kj kj-final"><div class="big">${Icon.svg("flag")}</div><h2>おつかれさま！</h2><p>けっかを 計算中…</p></div>`;
    Streamlit.setHeight();
    setTimeout(() => this.onDone({ type: "kanji_done", round: this.round, time, results: this.results }), 900);
  }
}
