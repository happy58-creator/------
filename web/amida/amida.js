/* 本格あみだくじ。
 *  1. 全員が、順番に すきな たて線(スタート)を えらぶ
 *  2. 真ん中の よこ線は かくれている。下の けっか(順位・あたり)は 見えている
 *  3. 全員 えらびおわったら、かくしを とって、点が うごいて けっかが出る
 */
const COLORS = ["#e74c3c", "#3498db", "#27ae60", "#f39c12", "#9b59b6", "#16a085", "#e67e22", "#34495e"];
const LEVELS = 11; // よこ線を引ける段の数

function genRungs(n, levels) {
  const r = Array.from({ length: levels }, () => Array(n - 1).fill(false));
  for (let l = 0; l < levels; l++) {
    for (let i = 0; i < n - 1; i++) {
      if (Math.random() < 0.45 && !(i > 0 && r[l][i - 1])) r[l][i] = true; // となりあう よこ線は同じ段に作らない
    }
  }
  // どの すき間にも、さいてい 3本は よこ線を入れる（まっすぐ おりるだけに ならないように）
  for (let i = 0; i < n - 1; i++) {
    let count = r.filter((row) => row[i]).length;
    for (let tries = 0; count < 3 && tries < 120; tries++) {
      const l = Math.floor(Math.random() * levels);
      if (!r[l][i] && !(i > 0 && r[l][i - 1]) && !(i < n - 2 && r[l][i + 1])) { r[l][i] = true; count++; }
    }
  }
  return r;
}

function shuffle(a) {
  const b = a.slice();
  for (let i = b.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [b[i], b[j]] = [b[j], b[i]];
  }
  return b;
}

class Amida {
  constructor(root, args) {
    this.root = root;
    this.names = (args.names || []).map(String);
    this.n = this.names.length;
    this.mode = args.mode === "rank" ? "rank" : "lot";
    this.alive = true;
    this.build();
    this.newGame();
    this.onResize = () => this.fit();
    window.addEventListener("resize", this.onResize);
  }

  destroy() {
    this.alive = false;
    window.removeEventListener("resize", this.onResize);
  }

  build() {
    this.root.innerHTML = `
      <div class="am">
        <div class="am-banner" data-r="banner"></div>
        <canvas data-r="cv"></canvas>
        <div class="am-btns">
          <button class="primary" data-r="reveal">🔓 ひみつの よこ線を ひらく！</button>
          <button class="primary" data-r="start">▶ スタート！</button>
          <button data-r="again">🔁 もういちど（新しいあみだ）</button>
        </div>
        <div class="am-result" data-r="result"></div>
      </div>`;
    this.$ = (k) => this.root.querySelector(`[data-r="${k}"]`);
    this.cv = this.$("cv");
    this.ctx = this.cv.getContext("2d");
    this.$("reveal").onclick = () => this.reveal();
    this.$("start").onclick = () => this.run();
    this.$("again").onclick = () => this.newGame();
    this.cv.addEventListener("pointerdown", (e) => this.tap(e));
  }

  newGame() {
    const n = this.n;
    this.state = "pick"; // pick → ready → revealing → revealed → running → done
    this.owner = Array(n).fill(-1); // たて線 → えらんだ人
    this.turn = 0;
    this.rungs = genRungs(n, LEVELS);
    this.labels = this.mode === "rank"
      ? shuffle(Array.from({ length: n }, (_, i) => `${i + 1}位`))
      : shuffle(["あたり🎉", ...Array(n - 1).fill("はずれ")]);
    this.cover = 1; // かくしの 大きさ（1=ぜんぶ かくす, 0=ひらいた）
    this.runStart = 0;
    this.paths = null;
    this.confetti = [];
    this.$("result").innerHTML = "";
    this.fit();
    this.refresh();
    this.loop();
  }

  fit() {
    const w = Math.max(280, Math.min(this.root.clientWidth - 14, 620));
    const h = Math.round(Math.max(380, Math.min(520, w * 0.95)));
    const dpr = window.devicePixelRatio || 1;
    this.W = w;
    this.H = h;
    this.dpr = dpr;
    this.cv.width = Math.round(w * dpr);
    this.cv.height = Math.round(h * dpr);
    this.cv.style.height = h + "px";
    this.side = Math.max(30, w * 0.07);
    this.yTop = 84; // スタートの 丸
    this.yBottom = h - 62; // よこ線の おわり
    this.draw();
    Streamlit.setHeight();
  }

  x(i) { return this.side + (i * (this.W - 2 * this.side)) / (this.n - 1); }
  levelY(l) { return this.yTop + 18 + ((l + 1) * (this.yBottom - this.yTop - 36)) / (LEVELS + 1); }
  color(p) { return COLORS[p % COLORS.length]; }
  nameOf(p) { return this.names[p] || `${p + 1}P`; }

  // ----- 1. スタートを えらぶ -----
  tap(e) {
    if (this.state !== "pick") return;
    const r = this.cv.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * this.W;
    const py = ((e.clientY - r.top) / r.height) * this.H;
    if (py > this.yTop + 36) return;
    let best = -1, bestD = 1e9;
    for (let i = 0; i < this.n; i++) {
      const d = Math.hypot(px - this.x(i), py - 56);
      if (d < bestD) { bestD = d; best = i; }
    }
    if (best < 0 || bestD > Math.max(30, (this.W - 2 * this.side) / (this.n - 1) / 2) || this.owner[best] >= 0) return;
    this.owner[best] = this.turn;
    this.turn++;
    if (this.turn === this.n - 1) { // 最後の人は、のこった1本に 自動で きまる
      const rest = this.owner.findIndex((o) => o < 0);
      this.owner[rest] = this.turn;
      this.turn++;
    }
    if (this.turn >= this.n) this.state = "ready";
    this.refresh();
    this.draw();
  }

  // ----- 2. かくしを ひらく -----
  reveal() {
    if (this.state !== "ready") return;
    this.state = "revealing";
    this.revealStart = performance.now();
    this.refresh();
  }

  // ----- 3. 点が うごく -----
  run() {
    if (this.state !== "revealed") return;
    this.paths = [];
    let maxLen = 0;
    for (let col = 0; col < this.n; col++) {
      const pts = [[this.x(col), this.yTop]];
      let c = col;
      for (let l = 0; l < LEVELS; l++) {
        const y = this.levelY(l);
        pts.push([this.x(c), y]);
        if (c < this.n - 1 && this.rungs[l][c]) c++;
        else if (c > 0 && this.rungs[l][c - 1]) c--;
        else continue;
        pts.push([this.x(c), y]);
      }
      pts.push([this.x(c), this.yBottom]);
      let len = 0;
      const cum = [0];
      for (let i = 1; i < pts.length; i++) { len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); cum.push(len); }
      this.paths.push({ col, pts, cum, len, end: c, player: this.owner[col], arrived: false });
      maxLen = Math.max(maxLen, len);
    }
    this.speed = Math.max(150, maxLen / 5.5); // 5〜6秒くらいで ぜんいん おわる
    this.runStart = performance.now();
    this.state = "running";
    this.refresh();
  }

  finish() {
    this.state = "done";
    const rows = [];
    this.paths.forEach((p) => rows.push({ player: p.player, label: this.labels[p.end] }));
    let html = "";
    if (this.mode === "rank") {
      rows.sort((a, b) => parseInt(a.label, 10) - parseInt(b.label, 10));
      rows.forEach((r, i) => {
        html += `<div class="am-row ${i === 0 ? "first" : ""}" style="animation-delay:${i * 0.12}s"><span class="rank">${i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : "🏃"} ${r.label}</span><span class="dot" style="background:${this.color(r.player)}"></span><span>${esc(this.nameOf(r.player))}</span></div>`;
      });
    } else {
      rows.sort((a, b) => (b.label.startsWith("あたり") ? 1 : 0) - (a.label.startsWith("あたり") ? 1 : 0));
      rows.forEach((r, i) => {
        const win = r.label.startsWith("あたり");
        html += `<div class="am-row ${win ? "win" : ""}" style="animation-delay:${i * 0.12}s"><span class="rank">${win ? "🎉" : "📁"} ${esc(r.label)}</span><span class="dot" style="background:${this.color(r.player)}"></span><span>${esc(this.nameOf(r.player))}</span></div>`;
      });
    }
    this.$("result").innerHTML = html;
    this.burst();
    this.refresh();
    Streamlit.setHeight();
  }

  burst() {
    for (let i = 0; i < 90; i++) {
      this.confetti.push({
        x: Math.random() * this.W, y: -10 - Math.random() * 120, vx: (Math.random() - 0.5) * 60,
        vy: 90 + Math.random() * 160, r: 3 + Math.random() * 4, c: COLORS[i % COLORS.length], life: 2.8,
      });
    }
  }

  // ----- 画面の文字・ボタン -----
  refresh() {
    const b = this.$("banner");
    const s = this.state;
    if (s === "pick") {
      b.innerHTML = `<span><span style="color:${this.color(this.turn)}">●</span> ${esc(this.nameOf(this.turn))} さんの 番！<small>上の ばんごうを タップして スタートを えらんでね（下の けっかは 見えているよ）</small></span>`;
    } else if (s === "ready") {
      b.innerHTML = `<span>🙌 ぜんいん えらびおわったよ！<small>下の ボタンで 真ん中の ひみつを ひらこう</small></span>`;
    } else if (s === "revealing") {
      b.innerHTML = `<span>👀 ひみつの よこ線が あらわれる…！</span>`;
    } else if (s === "revealed") {
      b.innerHTML = `<span>✨ よこ線が 見えたよ！ <small>スタートを おすと 点が うごくよ</small></span>`;
    } else if (s === "running") {
      b.innerHTML = `<span>🏃 ドキドキ… 点が おりていくよ！</span>`;
    } else {
      b.innerHTML = this.mode === "rank" ? `<span>🏆 けっか はっぴょう！</span>` : `<span>🎊 けっか はっぴょう！</span>`;
    }
    this.$("reveal").hidden = !(s === "ready" || s === "pick");
    this.$("reveal").disabled = s !== "ready";
    this.$("start").hidden = !(s === "revealed" || s === "running");
    this.$("start").disabled = s !== "revealed";
    this.$("again").hidden = s !== "done";
  }

  // ----- 描画 -----
  loop() {
    if (!this.alive) return;
    const now = performance.now();
    if (this.state === "revealing") {
      const t = Math.min(1, (now - this.revealStart) / 1300);
      this.cover = 1 - (1 - Math.pow(1 - t, 3));
      if (t >= 1) { this.cover = 0; this.state = "revealed"; this.refresh(); }
    }
    let animating = ["revealing", "running"].includes(this.state) || this.confetti.length;
    if (this.state === "running") {
      const dist = ((now - this.runStart) / 1000) * this.speed;
      let all = true;
      this.paths.forEach((p) => { if (dist < p.len) all = false; else p.arrived = true; });
      this.dist = dist;
      if (all) this.finish();
    }
    this.draw();
    if (animating || this.state === "pick" || this.state === "ready") requestAnimationFrame(() => this.loop());
    else setTimeout(() => this.alive && this.loop(), 250);
  }

  draw() {
    const { ctx, W, H, dpr } = this;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    const n = this.n;

    // たて線
    ctx.strokeStyle = "#b99b78";
    ctx.lineWidth = 4;
    for (let i = 0; i < n; i++) {
      ctx.beginPath();
      ctx.moveTo(this.x(i), this.yTop);
      ctx.lineTo(this.x(i), this.yBottom);
      ctx.stroke();
    }
    // よこ線（かくしが あるうちは 見えない）
    ctx.strokeStyle = "#8a6a45";
    ctx.lineWidth = 4;
    for (let l = 0; l < LEVELS; l++) {
      for (let i = 0; i < n - 1; i++) {
        if (!this.rungs[l][i]) continue;
        ctx.beginPath();
        ctx.moveTo(this.x(i), this.levelY(l));
        ctx.lineTo(this.x(i + 1), this.levelY(l));
        ctx.stroke();
      }
    }
    // かくし（まくが うえに 上がっていく）
    if (this.cover > 0.001) {
      const top = this.yTop + 26, full = this.yBottom - 26 - top;
      const h = full * this.cover;
      const x0 = this.side * 0.45, w = W - this.side * 0.9;
      const y0 = top + (full - h); // 下から ひらく
      const g = ctx.createLinearGradient(0, y0, 0, y0 + h);
      g.addColorStop(0, "#4a3b6b");
      g.addColorStop(1, "#2e2547");
      ctx.fillStyle = g;
      roundRect(ctx, x0, top, w, h, 14);
      ctx.fill();
      ctx.save();
      ctx.beginPath(); ctx.rect(x0, top, w, h); ctx.clip();
      ctx.fillStyle = "rgba(255,255,255,.14)";
      ctx.font = `900 ${Math.round(W * 0.07)}px "Zen Maru Gothic", sans-serif`;
      ctx.textAlign = "center";
      for (let r = 0; r < 6; r++) for (let c = 0; c < 5; c++) ctx.fillText("？", x0 + ((c + 0.5 + (r % 2) * 0.5) * w) / 5, top + 40 + r * 64);
      ctx.fillStyle = "#fff";
      ctx.font = `900 ${Math.round(W * 0.06)}px "Zen Maru Gothic", sans-serif`;
      ctx.fillText("ひ・み・つ", W / 2, top + full / 2 + 6);
      ctx.restore();
    }

    // うごく点と通ったあと
    if (this.paths && this.state !== "pick") {
      this.paths.forEach((p) => {
        const col = this.color(p.player);
        const d = Math.min(this.dist || 0, p.len);
        ctx.strokeStyle = col;
        ctx.globalAlpha = 0.85;
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(p.pts[0][0], p.pts[0][1]);
        let pos = p.pts[0];
        for (let i = 1; i < p.pts.length; i++) {
          if (p.cum[i] <= d) { ctx.lineTo(p.pts[i][0], p.pts[i][1]); pos = p.pts[i]; }
          else {
            const t = (d - p.cum[i - 1]) / (p.cum[i] - p.cum[i - 1]);
            pos = [p.pts[i - 1][0] + (p.pts[i][0] - p.pts[i - 1][0]) * t, p.pts[i - 1][1] + (p.pts[i][1] - p.pts[i - 1][1]) * t];
            ctx.lineTo(pos[0], pos[1]);
            break;
          }
        }
        ctx.stroke();
        ctx.globalAlpha = 1;
        ctx.fillStyle = col;
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 3;
        ctx.beginPath(); ctx.arc(pos[0], pos[1], 10, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      });
    }

    // 上：スタートの丸（えらぶ）
    ctx.textAlign = "center";
    for (let i = 0; i < n; i++) {
      const owner = this.owner[i];
      const cx = this.x(i), cy = 56;
      const next = this.state === "pick" && owner < 0;
      ctx.beginPath();
      ctx.arc(cx, cy, 19, 0, Math.PI * 2);
      ctx.fillStyle = owner >= 0 ? this.color(owner) : "#fff";
      ctx.fill();
      ctx.lineWidth = next ? 4 : 3;
      ctx.strokeStyle = owner >= 0 ? "#fff" : (next ? this.color(this.turn) : "#c9a27a");
      ctx.stroke();
      if (next) { // 「えらべるよ」の ひかる輪
        ctx.beginPath();
        ctx.arc(cx, cy, 24 + 2 * Math.sin(performance.now() / 250), 0, Math.PI * 2);
        ctx.strokeStyle = this.color(this.turn);
        ctx.globalAlpha = 0.45;
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
      ctx.fillStyle = owner >= 0 ? "#fff" : "#a58c6b";
      ctx.font = `900 ${owner >= 0 ? 15 : 16}px "Zen Maru Gothic", sans-serif`;
      ctx.fillText(owner >= 0 ? clip(this.nameOf(owner), 2) : String(i + 1), cx, cy + 6);
      if (owner >= 0) {
        ctx.fillStyle = this.color(owner);
        ctx.font = `900 ${Math.max(11, Math.min(14, W / n / 5))}px "Zen Maru Gothic", sans-serif`;
        ctx.fillText(clip(this.nameOf(owner), 5), cx, 24);
      }
    }

    // 下：けっか（さいしょから 見える）
    const lw = Math.min(86, (W - 2 * this.side) / (n - 1) - 6);
    for (let i = 0; i < n; i++) {
      const cx = this.x(i), top = this.yBottom + 14;
      let fill = "#fff6e0", stroke = "#d6b57d", text = "#5a4630";
      const arrivedHere = this.paths && this.paths.find((p) => p.end === i && p.arrived);
      if (arrivedHere) { fill = this.color(arrivedHere.player); stroke = "#fff"; text = "#fff"; }
      ctx.fillStyle = fill;
      roundRect(ctx, cx - lw / 2, top, lw, 40, 12);
      ctx.fill();
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.fillStyle = text;
      ctx.font = `900 ${Math.max(13, Math.min(18, lw / 3.2))}px "Zen Maru Gothic", sans-serif`;
      ctx.fillText(this.labels[i], cx, top + 26);
    }

    // 紙ふぶき
    if (this.confetti.length) {
      const dt = 1 / 60;
      this.confetti.forEach((c) => {
        c.x += c.vx * dt; c.y += c.vy * dt; c.life -= dt;
        ctx.globalAlpha = Math.max(0, Math.min(1, c.life));
        ctx.fillStyle = c.c;
        ctx.fillRect(c.x, c.y, c.r * 1.6, c.r);
      });
      ctx.globalAlpha = 1;
      this.confetti = this.confetti.filter((c) => c.life > 0 && c.y < H + 20);
    }
  }
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
const clip = (s, n) => (s.length > n ? s.slice(0, n) : s);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
