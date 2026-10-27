/* 漢字の書き取り。指やペンで書いた線を、お手本（KanjiVG の書き順）と比べて判定する。
 *
 * 判定するもの：書き順・画数・各画の向き・場所と形（大まかに）。「とめ・はね・はらい」の細かい判定はしない。
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
    return { pts, len, dot: len < 10, tol: baseTol };
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
          <button data-r="hint">💡 ヒント</button>
          <button data-r="clear">↩ この画を かきなおす</button>
          <button data-r="skip">🙈 わからない</button>
          <button class="primary" data-r="next" hidden>つぎへ ➡️</button>
        </div>
      </div>`;
    this.$ = (n) => this.root.querySelector(`[data-r="${n}"]`);
    this.cv = this.$("cv");
    this.ctx = this.cv.getContext("2d");
    this.$("mode").textContent = { trace: "✏️ なぞり書き", recall: "🧠 見て書く", reading: "📖 読みから書く" }[this.mode];
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
    this.cur = null; // 書いている線
    this.stat = { misses: 0, hints: 0, firstTry: 0, tries: 0, shape: 0, accepted: 0, skipped: false, wrongOrder: 0 };
    this.finished = false;
    this.hintIdx = -1;
    this.hintUsedForStroke = false;
    this.overlay = false;
    this.$("next").hidden = true;
    ["hint", "clear", "skip"].forEach((n) => { this.$(n).hidden = false; });
    this.$("count").textContent = `${this.q + 1} / ${this.list.length} もじめ`;
    this.$("bar").style.width = (this.q / this.list.length) * 100 + "%";
    this.renderInfo();
    this.say("info", `${k.s.length}画の かんじだよ。1画ずつ 書いてみよう！`);
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
      `<div class="read">${parts || "（よみ なし）"}</div>` +
      `<div class="sub">${k.s.length}画　${meaning ? "／ " + meaning : ""}</div>`;
  }

  say(kind, text) {
    const m = this.$("msg");
    m.className = "kj-msg " + kind;
    m.textContent = text;
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
        ctx.strokeStyle = i < this.idx ? "#efe6d6" : "#cfd4dc";
        ctx.lineWidth = 5;
        ctx.stroke(new Path2D(d));
      });
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
      ctx.strokeStyle = "rgba(255,140,0,.9)";
      ctx.lineWidth = 6;
      ctx.stroke(new Path2D(this.k.s[this.hintIdx]));
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
    this.done.forEach((pts) => ink(pts, "#2c3e70"));
    ink(this.cur, "#e67e22");
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
    this.draw();
  }

  move(e) {
    if (!this.cur) return;
    e.preventDefault();
    const events = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
    for (const ev of events.length ? events : [e]) {
      const p = this.pos(ev);
      if (dist(p, this.cur[this.cur.length - 1]) > 0.4) this.cur.push(p);
    }
    this.draw();
  }

  up(e) {
    if (!this.cur) return;
    e.preventDefault();
    const pts = this.cur;
    this.cur = null;
    this.judge(pts);
  }

  // ----- 判定 -----
  judge(pts) {
    const len = polyLength(pts);
    const ref = this.refs[this.idx];
    if (len < 2.5 && !ref.dot) {
      this.draw();
      return this.say("info", "みじかすぎるよ。もうすこし 長く 書いてみよう！");
    }
    const user = resample(pts);
    this.stat.tries++;
    const r = judgeAt(user, len, this.refs, this.idx);
    if (r.ok) return this.accept(pts, r);
    this.reject(user, len, r);
  }

  accept(pts, r) {
    const firstTry = !this.stat.failedThisStroke && this.hintIdx !== this.idx && !this.hintUsedForStroke;
    if (firstTry) this.stat.firstTry++;
    // 形の点（0〜1）：ずれが小さいほど高い
    const shape = Math.max(0, Math.min(1, (this.refs[this.idx].tol - r.fwd) / (this.refs[this.idx].tol * 0.65)));
    this.stat.shape += shape;
    this.stat.accepted++;
    this.done.push(pts);
    this.idx++;
    this.stat.failedThisStroke = false;
    this.hintUsedForStroke = false;
    this.hintIdx = -1;
    this.cv.classList.remove("good");
    void this.cv.offsetWidth;
    this.cv.classList.add("good");
    if (this.idx >= this.refs.length) return this.complete();
    this.say("ok", `⭕ ${this.idx}画目 OK！ つぎは ${this.idx + 1}画目。`);
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
      wrongOrder: this.stat.wrongOrder, skipped: this.stat.skipped, points,
    });
    ["hint", "clear", "skip"].forEach((n) => { this.$(n).hidden = true; });
    const next = this.$("next");
    next.hidden = false;
    next.textContent = this.q + 1 >= this.list.length ? "けっかを 見る 🏆" : "つぎへ ➡️";
    this.renderInfo();
    // 書き終わったら お手本を うすく かさねて、見くらべられるようにする
    this.overlay = !this.stat.skipped;
    this.draw();
  }

  next() {
    if (this.q + 1 >= this.list.length) return this.finish();
    this.q++;
    this.cv.classList.remove("good");
    this.load();
  }

  finish() {
    const time = Math.round((performance.now() - (this.startedAt || performance.now())) / 100) / 10;
    this.root.innerHTML = `<div class="kj kj-final"><div class="big">🏁</div><h2>おつかれさま！</h2><p>けっかを 計算中…</p></div>`;
    Streamlit.setHeight();
    setTimeout(() => this.onDone({ type: "kanji_done", round: this.round, time, results: this.results }), 900);
  }
}
