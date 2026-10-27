/* プログラミング：コードを打つとロボットが動く（ステージ）＋ じゆうに書いて動かす（サンドボックス）。 */

// ---------------- ロボットのいる盤面 ----------------
class RoboView {
  constructor(el) {
    this.el = el;
  }

  setup(world) {
    const avail = this.el.clientWidth || 360;
    this.cell = Math.max(26, Math.min(54, Math.floor(avail / world.cols)));
    const cells = [];
    for (let y = 0; y < world.rows; y++) {
      for (let x = 0; x < world.cols; x++) {
        const key = x + "," + y;
        const color = world.cells[key];
        const star = world.stars.has(key) ? '<span class="star">⭐</span>' : "";
        cells.push(`<div class="cell" data-xy="${key}"${color ? ` style="background:${color}"` : ""}>${star}</div>`);
      }
    }
    this.el.innerHTML = `
      <div class="world" style="--cell:${this.cell}px; grid-template-columns:repeat(${world.cols}, var(--cell))">
        ${cells.join("")}
        <div class="robot"><div class="arrow"></div><div class="bot">🤖</div><div class="bubble" hidden></div></div>
      </div>`;
    this.robot = this.el.querySelector(".robot");
    this.arrow = this.el.querySelector(".arrow");
    this.bubble = this.el.querySelector(".bubble");
    this.angle = world.dir * 90;
    this.robot.style.transition = "none";
    this.place(world.x, world.y);
    this.arrow.style.transform = `rotate(${this.angle}deg)`;
    void this.robot.offsetWidth;
    this.robot.style.transition = "";
  }

  place(x, y) {
    this.robot.style.transform = `translate(${x * this.cell}px, ${y * this.cell}px)`;
  }

  cellAt(x, y) {
    return this.el.querySelector(`.cell[data-xy="${x},${y}"]`);
  }

  apply(a) {
    if (a.kind === "move") {
      this.place(a.x, a.y);
      const c = this.cellAt(a.x, a.y);
      if (a.paint && c) c.style.background = a.paint;
      if (a.star && c) {
        const s = c.querySelector(".star");
        if (s) s.classList.add("got");
        UI.sfx.star();
      } else {
        UI.sfx.step();
      }
    } else if (a.kind === "turn") {
      this.angle += a.delta * 90;
      this.arrow.style.transform = `rotate(${this.angle}deg)`;
      UI.sfx.step();
    } else if (a.kind === "paint") {
      const c = this.cellAt(a.x, a.y);
      if (c) {
        c.style.background = a.color;
        c.classList.remove("splash");
        void c.offsetWidth;
        c.classList.add("splash");
      }
    } else if (a.kind === "say") {
      this.bubble.textContent = a.text;
      this.bubble.hidden = false;
      clearTimeout(this.sayTimer);
      this.sayTimer = setTimeout(() => { this.bubble.hidden = true; }, 1800);
    } else if (a.kind === "error") {
      this.robot.classList.remove("bump");
      void this.robot.offsetWidth;
      this.robot.classList.add("bump");
      UI.sfx.error();
    }
  }
}

// 動きのリストを、1つずつ時間をあけて再生する
class Player {
  constructor(view, opts) {
    this.view = view;
    this.delay = opts.delay;
    this.onAction = opts.onAction || (() => {});
    this.onIdle = opts.onIdle || (() => {});
    this.queue = [];
    this.timer = null;
  }

  get busy() {
    return this.timer !== null || this.queue.length > 0;
  }

  push(actions) {
    this.queue.push(...actions);
    if (this.timer === null) this.next();
  }

  next() {
    if (this.delay === 0) {
      while (this.queue.length) this.play(this.queue.shift());
      this.timer = null;
      return this.onIdle();
    }
    const a = this.queue.shift();
    if (!a) {
      this.timer = null;
      return this.onIdle();
    }
    this.play(a);
    const quick = a.kind === "var" || a.kind === "check" || a.kind === "note";
    this.timer = setTimeout(() => this.next(), quick ? this.delay * 0.35 : this.delay);
  }

  play(a) {
    this.view.apply(a);
    this.onAction(a);
  }

  stop() {
    clearTimeout(this.timer);
    this.timer = null;
    this.queue = [];
  }
}

// コードを色分けする（1文字ごとのクラス名を返す）
function highlightLine(text) {
  const classes = [];
  const re = /("[^"]*"?|'[^']*'?)|(#.*)|(\d+)|([A-Za-z_]\w*)|(\s+)|(.)/g;
  let m;
  while ((m = re.exec(text))) {
    let cls = "op";
    if (m[1]) cls = "str";
    else if (m[2]) cls = "cmt";
    else if (m[3]) cls = "num";
    else if (m[4]) cls = Robo.KEYWORDS.includes(m[4]) ? "kw" : Robo.FUNCS.includes(m[4]) ? "fn" : "var";
    else if (m[5]) cls = "sp";
    for (let i = 0; i < m[0].length; i++) classes.push(cls);
  }
  return classes;
}

function varsHtml(vars) {
  const entries = Object.entries(vars);
  if (!entries.length) return '<span class="muted">（まだ ないよ）</span>';
  return entries.map(([k, v]) => `<span class="var"><b>${UI.esc(k)}</b> = ${UI.esc(v)}</span>`).join("");
}

// ---------------- ステージ（お手本のコードを打つ） ----------------
const STAGES = [
  {
    title: "まえに すすもう",
    learn: "<code>move(3)</code> で 3マス まえに すすむよ。<code>turn_right()</code> で 右を むくよ。",
    code: "move(3)\nturn_right()\nmove(2)",
  },
  {
    title: "色を ぬろう",
    learn: '<code>paint("red")</code> で 足もとのマスに 色を ぬるよ。色の名前は <code>" "</code> で はさむよ。',
    code: 'paint("red")\nmove(1)\npaint("blue")\nmove(1)\npaint("green")',
  },
  {
    title: "くりかえし（for）",
    learn: "<code>for i in range(4):</code> の下の、字下げした行を 4回 くりかえすよ。字下げのスペースは 自動で入るよ！",
    code: "for i in range(4):\n    move(2)\n    turn_right()",
  },
  {
    title: "へんすう（変数）",
    learn: "<code>steps = 2</code> は「steps という 箱に 2 を入れる」という意味。箱の中身は あとから かえられるよ。",
    code: "steps = 2\nmove(steps)\nturn_left()\nsteps = steps + 1\nmove(steps)",
  },
  {
    title: "ペンで かこう",
    learn: '<code>pen("orange")</code> にすると、通ったマスに 色が つくよ。<code>say("...")</code> で ロボットが しゃべる！',
    code: 'pen("orange")\nfor i in range(3):\n    move(2)\n    turn_left()\n    move(1)\n    turn_right()\nsay("yatta!")',
  },
  {
    title: "もし〜なら（if）",
    learn: "<code>if</code> は「もし〜なら」、<code>else</code> は「そうでなければ」。<code>i % 2 == 0</code> は「i が 偶数なら」だよ。",
    code: 'for i in range(6):\n    if i % 2 == 0:\n        paint("pink")\n    else:\n        paint("blue")\n    move(1)',
  },
];

// コードを ためしに動かして、ちょうどいい盤の大きさと ほしの場所を決める
function layoutStage(code) {
  const dry = new Robo.Runner(Robo.makeWorld({ cols: 99, rows: 99, x: 0, y: 0, dir: 1 }), { walls: false });
  const acts = dry.run(Robo.parse(code));
  const pts = [[0, 0]].concat(acts.filter((a) => a.kind === "move").map((a) => [a.x, a.y]));
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const minX = Math.min(...xs), minY = Math.min(...ys);
  const w = Math.max(...xs) - minX + 1, h = Math.max(...ys) - minY + 1;
  const cols = Math.max(8, w + 2), rows = Math.max(5, h + 2);
  const ox = Math.floor((cols - w) / 2) - minX, oy = Math.floor((rows - h) / 2) - minY;
  const stars = [...new Set(dry.moveEnds.map(([x, y]) => `${x + ox},${y + oy}`))].filter((k) => k !== `${ox},${oy}`);
  return { cols, rows, x: ox, y: oy, dir: 1, stars };
}

class CodeGame {
  constructor(root, args, onDone) {
    this.onDone = onDone;
    this.round = args.round;
    this.stage = 0;
    this.keys = 0;
    this.misses = 0;
    this.perfectStages = 0;
    this.stageMisses = []; // ステージごとのミス回数（PDF・履歴用）
    this.elapsed = 0;
    this.runningSince = 0;
    this.state = "ready";

    root.innerHTML = `
      <div class="game code-game">
        <div class="hud">
          <span class="pill">🗺️ ステージ <b data-r="stageNo">1</b> / ${STAGES.length}</span>
          <span class="pill">⏱ <b data-r="time">0:00</b></span>
          <span class="pill">❌ ミス <b data-r="miss">0</b></span>
          <span class="pill">⭐ <b data-r="stars">0 / 0</b></span>
          <button class="icon" data-r="sound"></button>
        </div>
        <div class="learn"><h3 data-r="title"></h3><p data-r="learn"></p></div>
        <div class="split">
          <div class="codebox"><div class="code" data-r="code"></div></div>
          <div class="side">
            <div data-r="world"></div>
            <div class="vars">📦 へんすう：<span data-r="vars"></span></div>
            <div class="console" data-r="console"></div>
          </div>
        </div>
        <div class="keyhint" data-r="keyhint"></div>
        <div data-r="kb"></div>
        <div class="ime" data-r="ime" hidden>⚠️ 日本語入力が オンに なっているよ！「英数」キーを おしてね</div>
        <div class="overlay" data-r="overlay"></div>
      </div>`;
    this.$ = (name) => root.querySelector(`[data-r="${name}"]`);
    this.kb = new UI.Keyboard(this.$("kb"));
    this.view = new RoboView(this.$("world"));
    this.$("sound").textContent = UI.sound.on ? "🔊" : "🔇";
    this.$("sound").onclick = (e) => { e.currentTarget.textContent = UI.toggleSound() ? "🔊" : "🔇"; };
    this.$("overlay").onclick = () => this.overlayClick();
    window.addEventListener("keydown", (e) => this.onKey(e));
    UI.watchFocus(() => this.pause(), () => {});
    this.timer = setInterval(() => { this.$("time").textContent = UI.fmtTime(this.seconds()); }, 250);
    this.loadStage();
    this.showOverlay(`
      <div class="big">🤖</div>
      <h2>プログラミング・ミッション！</h2>
      <p>本物の Python（パイソン）の書き方で、ロボットに 命令しよう。<br>
      1行 打って <b>Enter</b> を押すと、ロボットが その命令どおりに 動くよ！</p>
      <p class="tip">記号（ " ( ) _ : など）は Shift キーを使うものが多いよ。下のキーボードを見てね</p>
      <button class="primary">ここを クリックして スタート！</button>`);
  }

  showOverlay(html) {
    const o = this.$("overlay");
    o.innerHTML = `<div class="dialog">${html}</div>`;
    o.hidden = false;
  }

  hideOverlay() {
    this.$("overlay").hidden = true;
  }

  overlayClick() {
    window.focus();
    if (this.state === "ready" || this.state === "pause") this.resume();
    else if (this.state === "clear") this.nextStage();
  }

  resume() {
    this.state = "play";
    this.runningSince = performance.now();
    this.hideOverlay();
    this.draw();
    this.checkClear();
  }

  pause() {
    if (this.state !== "play") return;
    this.elapsed += performance.now() - this.runningSince;
    this.state = "pause";
    this.showOverlay(`<div class="big">⏸</div><h2>ひとやすみ中</h2>
      <p>ゲームの画面から はなれたので 止めたよ。</p><button class="primary">クリックして つづける</button>`);
  }

  seconds() {
    return (this.elapsed + (this.state === "play" ? performance.now() - this.runningSince : 0)) / 1000;
  }

  loadStage() {
    const st = STAGES[this.stage];
    this.lines = st.code.split("\n");
    this.colors = this.lines.map(highlightLine);
    this.li = 0;
    this.ci = this.indentOf(0);
    this.stmts = Robo.parse(st.code);
    this.nextStmt = 0;
    this.stageMiss = 0;
    this.typedAll = false;
    this.runLine = 0;
    this.vars = {};
    this.output = [];
    this.got = 0;
    const layout = layoutStage(st.code);
    this.totalStars = layout.stars.length;
    this.runner = new Robo.Runner(Robo.makeWorld(layout));
    this.$("stageNo").textContent = this.stage + 1;
    this.$("title").textContent = `ステージ${this.stage + 1}：${st.title}`;
    this.$("learn").innerHTML = st.learn;
    this.view.setup(this.runner.w);
    this.player = new Player(this.view, {
      delay: 320,
      onAction: (a) => this.onAction(a),
      onIdle: () => this.checkClear(),
    });
    this.draw();
  }

  indentOf(li) {
    const line = this.lines[li] || "";
    return line.length - line.trimStart().length;
  }

  expected() {
    if (this.li >= this.lines.length) return null;
    return this.ci < this.lines[this.li].length ? this.lines[this.li][this.ci] : "\n";
  }

  draw() {
    const html = this.lines.map((line, li) => {
      const cls = this.colors[li];
      let chars = "";
      for (let ci = 0; ci < line.length; ci++) {
        const state = li < this.li || (li === this.li && ci < this.ci) ? "done" : li === this.li && ci === this.ci ? "now" : "todo";
        const ch = line[ci] === " " ? "&nbsp;" : UI.esc(line[ci]);
        chars += `<span class="${cls[ci]} ${state}">${ch}</span>`;
      }
      const enterState = li < this.li ? "done" : li === this.li && this.ci >= line.length ? "now" : "todo";
      chars += `<span class="enter ${enterState}">⏎</span>`;
      const lineCls = ["ln", li === this.li ? "typing" : "", li + 1 === this.runLine ? "running" : ""].join(" ");
      return `<div class="${lineCls}"><span class="no">${li + 1}</span><span class="src">${chars}</span></div>`;
    });
    this.$("code").innerHTML = html.join("");
    this.$("miss").textContent = this.misses;
    this.$("stars").textContent = `${this.got} / ${this.totalStars}`;
    this.$("vars").innerHTML = varsHtml(this.vars);
    this.$("console").innerHTML = this.output.length
      ? this.output.map((t) => `<div>${t}</div>`).join("")
      : '<span class="muted">print / say の 出力が ここに 出るよ</span>';
    const exp = this.state === "play" ? this.expected() : null;
    this.kb.show(exp);
    this.$("keyhint").innerHTML = exp === null ? "" : "つぎ：" + this.kb.hint(exp);
  }

  onAction(a) {
    if (a.line) this.runLine = a.line;
    if (a.kind === "var") this.vars[a.name] = a.value;
    if (a.kind === "move" && a.star) this.got++;
    if (a.kind === "say") this.output.push(`🤖「${UI.esc(a.text)}」`);
    if (a.kind === "print") this.output.push(UI.esc(a.text));
    if (a.kind === "error") this.output.push(`<span class="err">⚠️ ${UI.esc(a.msg)}</span>`);
    this.draw();
  }

  onKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "Process" || e.isComposing) {
      this.$("ime").hidden = false;
      return;
    }
    if ([" ", "Enter", "Tab", "'", "/"].includes(e.key)) e.preventDefault();
    if (this.state === "ready" && e.key === " ") return this.resume();
    if (this.state === "pause" && e.key === " ") return this.resume();
    if (this.state === "clear" && (e.key === "Enter" || e.key === " ")) return this.nextStage();
    if (this.state !== "play") return;
    const k = e.key === "Enter" ? "\n" : e.key;
    if (k.length !== 1) return;
    if (/[^\x20-\x7e\n]/.test(k)) {
      this.$("ime").hidden = false;
      return;
    }
    this.$("ime").hidden = true;
    e.preventDefault();
    const exp = this.expected();
    if (exp === null) return;
    if (k === exp) {
      this.keys++;
      UI.sfx.key();
      this.kb.flash(k, true);
      if (k === "\n") this.lineDone();
      else this.ci++;
    } else {
      this.misses++;
      this.stageMiss++;
      UI.sfx.miss();
      this.kb.flash(k, false);
      const box = this.$("code");
      box.classList.remove("shake");
      void box.offsetWidth;
      box.classList.add("shake");
    }
    this.draw();
  }

  // 1行打ちおわったら、そこで完成した命令を実行する（for や if は、ブロックの最後の行まで打ったら実行）
  lineDone() {
    const lineNo = this.li + 1;
    this.li++;
    this.ci = this.indentOf(this.li);
    while (this.nextStmt < this.stmts.length && this.stmts[this.nextStmt].endLine <= lineNo) {
      this.player.push(this.runner.run([this.stmts[this.nextStmt]]));
      this.nextStmt++;
    }
    if (this.li >= this.lines.length) {
      this.typedAll = true;
      this.checkClear();
    }
  }

  checkClear() {
    if (!this.typedAll || this.player.busy || this.state !== "play") return;
    this.elapsed += performance.now() - this.runningSince;
    this.state = "clear";
    this.runLine = 0;
    if (!this.stageMiss) this.perfectStages++;
    this.stageMisses.push(this.stageMiss);
    UI.sfx.finish();
    this.draw();
    const last = this.stage + 1 >= STAGES.length;
    const got = this.runner.w.got;
    setTimeout(() => this.showOverlay(`
      <div class="big">${"⭐".repeat(Math.min(got, 6)) || "🎉"}</div>
      <h2>ステージ${this.stage + 1} クリア！</h2>
      <p>ほし ${got} / ${this.totalStars} こ ゲット！ ${this.stageMiss ? `ミス ${this.stageMiss}回` : "ノーミス！✨"}</p>
      <button class="primary">${last ? "けっかを 見る 🏆" : "つぎの ステージへ ➡️"}</button>
      <p class="tip">Enter キーでも すすめるよ</p>`), 500);
  }

  nextStage() {
    if (this.stage + 1 >= STAGES.length) return this.finish();
    this.stage++;
    this.loadStage();
    this.resume();
  }

  finish() {
    this.state = "done";
    clearInterval(this.timer);
    this.showOverlay(`<div class="big">👑</div><h2>ぜんぶ クリア！</h2><p>けっかを 計算中…</p>`);
    const time = Math.round(this.elapsed / 100) / 10;
    setTimeout(() => this.onDone({
      type: "code_done", round: this.round, time, keys: this.keys, misses: this.misses,
      stages: STAGES.length, perfect: this.perfectStages, stageMisses: this.stageMisses,
    }), 1000);
  }
}

// ---------------- じゆうモード（サンドボックス） ----------------
const SAMPLES = [
  { name: "しかくを かく", code: 'pen("red")\nfor i in range(4):\n    move(3)\n    turn_right()\n' },
  { name: "にじの 線", code: 'colors = ["red", "orange", "yellow", "green", "blue", "purple"]\nfor c in colors:\n    paint(c)\n    move(1)\n' },
  { name: "うずまき", code: 'pen("purple")\nfor n in range(1, 6):\n    move(n)\n    turn_right()\nsay("guru guru!")\n' },
  { name: "しましま（if）", code: 'for i in range(8):\n    if i % 2 == 0:\n        paint("yellow")\n    else:\n        paint("green")\n    move(1)\n' },
  { name: "サイコロ", code: 'n = randint(1, 6)\nsay("dice: " + str(n))\nprint("サイコロの目は", n)\nmove(n)\n' },
];
const SNIPPETS = [
  ["move(1)", "まえに すすむ"], ["turn_left()", "左を むく"], ["turn_right()", "右を むく"],
  ['paint("red")', "色を ぬる"], ['pen("blue")', "ペンを おろす"], ["pen_up()", "ペンを あげる"],
  ['say("hello")', "しゃべる"], ['print("hi")', "出力する"], ["for i in range(4):", "くりかえす"],
  ["if i % 2 == 0:", "もし〜なら"], ["else:", "そうでなければ"], ["randint(1, 6)", "ランダムな数"],
];

class Sandbox {
  constructor(root) {
    this.base = { cols: 12, rows: 7, x: 2, y: 3, dir: 1, stars: [] };
    this.scatterStars();
    root.innerHTML = `
      <div class="game sandbox">
        <div class="hud">
          <label>📚 お手本：<select data-r="sample"><option value="">えらんでね</option>
            ${SAMPLES.map((s, i) => `<option value="${i}">${s.name}</option>`).join("")}</select></label>
          <label>🐢 はやさ：<select data-r="speed">
            <option value="600">ゆっくり</option><option value="300" selected>ふつう</option>
            <option value="100">はやい</option><option value="0">いっしゅん</option></select></label>
          <button class="icon" data-r="sound"></button>
        </div>
        <div class="split">
          <div class="editor">
            <div class="gutter" data-r="gutter"></div>
            <textarea data-r="src" spellcheck="false" autocapitalize="off" autocomplete="off"></textarea>
          </div>
          <div class="side">
            <div data-r="world"></div>
            <div class="vars">⭐ <b data-r="stars"></b>　📦 <span data-r="vars"></span></div>
            <div class="console" data-r="console"></div>
          </div>
        </div>
        <div class="buttons">
          <button class="primary" data-r="run">▶ じっこう（Ctrl+Enter）</button>
          <button data-r="stop">⏹ とめる</button>
          <button data-r="reset">🔄 ロボットを もどす</button>
          <button data-r="shuffle">✨ ほしを ならべなおす</button>
        </div>
        <div class="snippets" data-r="snippets">
          ${SNIPPETS.map(([code, label]) => `<button data-code="${UI.esc(code)}"><code>${UI.esc(code)}</code><small>${label}</small></button>`).join("")}
        </div>
      </div>`;
    this.$ = (name) => root.querySelector(`[data-r="${name}"]`);
    this.src = this.$("src");
    this.src.value = UI.store.get("kyouzai-sandbox-code", SAMPLES[0].code);
    this.view = new RoboView(this.$("world"));
    this.vars = {};
    this.output = [];
    this.errorLine = 0;
    this.runLine = 0;
    this.player = null;

    this.$("sound").textContent = UI.sound.on ? "🔊" : "🔇";
    this.$("sound").onclick = (e) => { e.currentTarget.textContent = UI.toggleSound() ? "🔊" : "🔇"; };
    this.$("sample").onchange = (e) => {
      if (e.target.value === "") return;
      this.src.value = SAMPLES[Number(e.target.value)].code;
      e.target.value = "";
      this.changed();
      this.reset();
    };
    this.$("run").onclick = () => this.run();
    this.$("stop").onclick = () => this.stop();
    this.$("reset").onclick = () => this.reset();
    this.$("shuffle").onclick = () => { this.scatterStars(); this.reset(); };
    this.$("snippets").onclick = (e) => {
      const b = e.target.closest("button");
      if (b) this.insert(b.dataset.code);
    };
    this.src.addEventListener("input", () => this.changed());
    this.src.addEventListener("scroll", () => { this.$("gutter").scrollTop = this.src.scrollTop; });
    this.src.addEventListener("keydown", (e) => this.editorKey(e));
    this.reset();
    this.changed();
  }

  scatterStars() {
    const stars = new Set();
    while (stars.size < 5) {
      const x = Math.floor(Math.random() * this.base.cols), y = Math.floor(Math.random() * this.base.rows);
      if (x !== this.base.x || y !== this.base.y) stars.add(`${x},${y}`);
    }
    this.base.stars = [...stars];
  }

  changed() {
    UI.store.set("kyouzai-sandbox-code", this.src.value);
    this.errorLine = 0;
    this.drawGutter();
  }

  drawGutter() {
    const n = this.src.value.split("\n").length;
    let html = "";
    for (let i = 1; i <= n; i++) {
      const cls = i === this.errorLine ? "err" : i === this.runLine ? "run" : "";
      html += `<div class="${cls}">${i}</div>`;
    }
    this.$("gutter").innerHTML = html;
    this.$("gutter").scrollTop = this.src.scrollTop;
  }

  // Tab でスペース4つ、Enter で字下げを引きつぐ（: のあとは さらに4つ）
  editorKey(e) {
    const ta = this.src;
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      return this.run();
    }
    if (e.isComposing) return;
    if (e.key === "Tab") {
      e.preventDefault();
      return this.insert("    ", false);
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const before = ta.value.slice(0, ta.selectionStart);
      const line = before.slice(before.lastIndexOf("\n") + 1);
      let indent = line.match(/^ */)[0];
      if (/:\s*$/.test(line)) indent += "    ";
      return this.insert("\n" + indent, false);
    }
  }

  insert(text, asLine = true) {
    const ta = this.src;
    const start = ta.selectionStart, end = ta.selectionEnd;
    let t = text;
    if (asLine) {
      const before = ta.value.slice(0, start);
      const line = before.slice(before.lastIndexOf("\n") + 1);
      const indent = line.match(/^ */)[0];
      if (line.trim()) t = "\n" + indent + t;
      if (text.endsWith(":")) t += "\n" + indent + "    ";
    }
    ta.setRangeText(t, start, end, "end");
    ta.focus();
    this.changed();
  }

  stop() {
    if (this.player) this.player.stop();
    this.runLine = 0;
    this.drawGutter();
  }

  reset() {
    this.stop();
    this.world = Robo.makeWorld(this.base);
    this.view.setup(this.world);
    this.vars = {};
    this.output = [];
    this.drawSide();
  }

  drawSide() {
    this.$("stars").textContent = `${this.world.got} / ${this.base.stars.length}`;
    this.$("vars").innerHTML = varsHtml(this.vars);
    this.$("console").innerHTML = this.output.length
      ? this.output.map((t) => `<div>${t}</div>`).join("")
      : '<span class="muted">▶ じっこう を押すと、ロボットが コードどおりに 動くよ</span>';
    const c = this.$("console");
    c.scrollTop = c.scrollHeight;
  }

  run() {
    this.reset();
    this.errorLine = 0;
    let stmts;
    try {
      stmts = Robo.parse(this.src.value);
    } catch (err) {
      if (!(err instanceof Robo.CodeError)) throw err;
      this.output.push(`<span class="err">⚠️ ${err.line}行目：${UI.esc(err.message)}</span>`);
      this.errorLine = err.line;
      UI.sfx.error();
      this.drawGutter();
      return this.drawSide();
    }
    const runner = new Robo.Runner(this.world);
    const actions = runner.run(stmts);
    // 盤面は再生しながら変えるので、画面用には最初の状態を作りなおす
    this.view.setup(Robo.makeWorld(this.base));
    const got = { n: 0 };
    this.player = new Player(this.view, {
      delay: Number(this.$("speed").value),
      onAction: (a) => {
        this.runLine = a.line || 0;
        if (a.kind === "var") this.vars[a.name] = a.value;
        if (a.kind === "move" && a.star) got.n++;
        if (a.kind === "say") this.output.push(`🤖「${UI.esc(a.text)}」`);
        if (a.kind === "print") this.output.push(UI.esc(a.text));
        if (a.kind === "error") {
          this.output.push(`<span class="err">⚠️ ${a.line}行目：${UI.esc(a.msg)}</span>`);
          this.errorLine = a.line;
        }
        this.$("stars").textContent = `${got.n} / ${this.base.stars.length}`;
        this.drawGutter();
        if (a.kind !== "move" && a.kind !== "turn") this.drawSide2(got);
      },
      onIdle: () => {
        this.runLine = 0;
        this.drawGutter();
        if (got.n === this.base.stars.length && got.n > 0) {
          this.output.push("🎉 ほしを ぜんぶ あつめたよ！ すごい！");
          UI.sfx.finish();
        } else if (!runner.failed) {
          this.output.push(`<span class="muted">✅ さいごまで 動いたよ</span>`);
        }
        this.drawSide2(got);
      },
    });
    this.player.push(actions);
  }

  drawSide2(got) {
    this.$("vars").innerHTML = varsHtml(this.vars);
    this.$("console").innerHTML = this.output.map((t) => `<div>${t}</div>`).join("") ||
      '<span class="muted">（出力は まだ ないよ）</span>';
    this.$("stars").textContent = `${got.n} / ${this.base.stars.length}`;
    const c = this.$("console");
    c.scrollTop = c.scrollHeight;
  }
}
