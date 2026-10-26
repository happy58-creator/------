/* チェス盤の画面と操作。ルールと CPU は engine.js。 */
(function () {
  "use strict";
  const E = window.ChessEngine;
  const $ = (id) => document.getElementById(id);

  const GLYPH = { k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" };
  const VS = "︎"; // 絵文字ではなく文字として表示させる
  const NAME = { k: "キング", q: "クイーン", r: "ルーク", b: "ビショップ", n: "ナイト", p: "ポーン" };
  const HOW = {
    k: "まわり1マスだけ動ける。とられそう（チェックメイト）になったら負け！",
    q: "たて・よこ・ななめ、どこまでも進める。いちばん強い駒！",
    r: "たて・よこに、どこまでも進める。",
    b: "ななめに、どこまでも進める。",
    n: "L字にジャンプ！ほかの駒をとびこえられるのはナイトだけ。",
    p: "まえに1マス（さいしょは2マスもOK）。駒をとるときは ななめまえ。",
  };
  const LEVELS = { easy: "かんたん", normal: "ふつう", hard: "つよい", expert: "さいきょう" };
  const COLOR = { w: "白", b: "黒" };
  const DRAW_TEXT = {
    stalemate: "ステイルメイト（動ける手がない）で 引き分け！",
    fifty: "50手のあいだ 駒をとらなかったので 引き分け！",
    repetition: "同じ形が3回くりかえされたので 引き分け！",
    insufficient: "チェックメイトできる駒がないので 引き分け！",
  };
  const START_COUNT = { q: 1, r: 2, b: 2, n: 2, p: 8 };
  const POINTS = { q: 9, r: 5, b: 3, n: 3, p: 1 };
  const STORE = "kyouzai-chess-v1";

  const S = {
    game: new E.Game(), sans: [], ucis: [],
    mode: "cpu", color: "w", level: "normal", // いまのゲームの設定
    next: { mode: "cpu", color: "w" }, // 「新しいゲーム」で使う設定
    flipped: false, selected: -1, targets: [], hint: null,
    thinking: false, token: 0, over: null,
    gameId: "", reported: false, sound: true,
  };
  let drag = null;

  const newId = () => "chess-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const isCpuTurn = () => S.mode === "cpu" && S.game.turn !== S.color;
  const canTouch = () => !S.over && !S.thinking && !isCpuTurn();
  const sideName = (c) => (S.mode === "cpu" ? (c === S.color ? `あなた（${COLOR[c]}）` : `CPU（${COLOR[c]}）`) : COLOR[c]);
  const piece = (p, extra = "") => `<span class="pc ${E.colorOf(p)} ${extra}">${GLYPH[E.typeOf(p)]}${VS}</span>`;

  function save() {
    try {
      localStorage.setItem(STORE, JSON.stringify({
        ucis: S.ucis, mode: S.mode, color: S.color, level: S.level, flipped: S.flipped,
        gameId: S.gameId, reported: S.reported, sound: S.sound,
      }));
    } catch (e) { /* 保存できなくても遊べる */ }
  }

  function loadSaved() {
    try { return JSON.parse(localStorage.getItem(STORE) || "null"); } catch (e) { return null; }
  }

  // ---------------- 音 ----------------
  let audio = null;
  function tone(freq, dur, type = "sine", vol = 0.12, delay = 0) {
    if (!S.sound) return;
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      const t = audio.currentTime + delay, o = audio.createOscillator(), g = audio.createGain();
      o.type = type;
      o.frequency.value = freq;
      g.gain.setValueAtTime(vol, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + dur);
      o.connect(g).connect(audio.destination);
      o.start(t);
      o.stop(t + dur);
    } catch (e) { /* 音が出せない環境 */ }
  }
  const sfx = {
    move: () => tone(330, 0.07, "triangle", 0.15),
    capture: () => { tone(196, 0.1, "square", 0.05); tone(392, 0.09, "triangle", 0.12, 0.04); },
    check: () => { tone(660, 0.12, "triangle"); tone(880, 0.16, "triangle", 0.12, 0.1); },
    win: () => [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.22, "triangle", 0.12, i * 0.12)),
    lose: () => [392, 330, 262].forEach((f, i) => tone(f, 0.28, "sine", 0.12, i * 0.18)),
    draw: () => [440, 523].forEach((f, i) => tone(f, 0.18, "sine", 0.1, i * 0.2)),
  };

  // ---------------- CPU（Web Worker で考える。使えなければ画面側で考える） ----------------
  let worker = null, askSeq = 0;
  const pending = new Map();

  function replay(ucis) {
    const g = new E.Game();
    for (const u of ucis) {
      const m = g.findMove(u);
      if (m) g.make(m);
    }
    return g;
  }

  function thinkHere(data) {
    const r = E.bestMove(replay(data.moves), data.level);
    return r ? E.uci(r.move) : null;
  }

  try {
    worker = new Worker("engine.js");
    worker.onmessage = (e) => {
      const job = pending.get(e.data.token);
      pending.delete(e.data.token);
      if (job) job.resolve(e.data.move);
    };
    worker.onerror = () => {
      worker = null;
      pending.forEach((job) => setTimeout(() => job.resolve(thinkHere(job.data)), 30));
      pending.clear();
    };
  } catch (e) {
    worker = null;
  }

  function ask(data) {
    return new Promise((resolve) => {
      if (worker) {
        const token = ++askSeq;
        pending.set(token, { resolve, data });
        worker.postMessage({ ...data, token });
      } else {
        setTimeout(() => resolve(thinkHere(data)), 30);
      }
    });
  }

  function maybeThink() {
    if (S.over || S.thinking || !isCpuTurn()) return;
    S.thinking = true;
    const token = ++S.token, started = Date.now();
    render();
    ask({ moves: S.ucis.slice(), level: S.level }).then((u) => {
      if (token !== S.token) return;
      setTimeout(() => {
        if (token !== S.token) return;
        S.thinking = false;
        const m = u && S.game.findMove(u);
        if (m) commit(m);
        else render();
      }, Math.max(0, 500 - (Date.now() - started)));
    });
  }

  // ---------------- 盤の表示 ----------------
  function fit() {
    const w = $("app").clientWidth;
    // 横に並べられる幅なら、右のパネル（240px）のぶんを空けて盤を大きくする
    const room = w >= 680 ? w - 240 - 16 - 30 : w - 20;
    const sq = Math.max(34, Math.min(64, Math.floor(room / 8)));
    document.documentElement.style.setProperty("--sq", sq + "px");
  }

  function viewPos(sq) {
    const f = sq & 7, r = sq >> 3;
    return S.flipped ? { col: 7 - f, row: r } : { col: f, row: 7 - r };
  }

  function render(animMove) {
    const g = S.game, b = g.board;
    const last = g.stack.length ? g.stack[g.stack.length - 1].m : null;
    const checkSq = g.inCheck() ? g.kings[g.turn] : -1;
    const html = [];
    for (let row = 0; row < 8; row++) {
      for (let col = 0; col < 8; col++) {
        const f = S.flipped ? 7 - col : col, r = S.flipped ? row : 7 - row, sq = r * 8 + f;
        const cls = ["sq", (f + r) % 2 ? "light" : "dark"];
        if (last && (sq === last.from || sq === last.to)) cls.push("last");
        if (sq === S.selected) cls.push("sel");
        if (S.hint && (sq === S.hint.from || sq === S.hint.to)) cls.push("hint");
        if (sq === checkSq) cls.push("check");
        let inner = "";
        if (b[sq]) inner += `<span class="pc ${E.colorOf(b[sq])}" data-sq="${sq}">${GLYPH[E.typeOf(b[sq])]}${VS}</span>`;
        if (S.targets.includes(sq)) inner += b[sq] ? '<span class="ring"></span>' : '<span class="dot"></span>';
        if (row === 7) inner += `<span class="coord file">${"abcdefgh"[f]}</span>`;
        if (col === 0) inner += `<span class="coord rank">${r + 1}</span>`;
        html.push(`<div class="${cls.join(" ")}" data-sq="${sq}">${inner}</div>`);
      }
    }
    $("board").innerHTML = html.join("");
    if (animMove) animate(animMove);
    renderSide();
  }

  function animate(m) {
    const size = $("board").getBoundingClientRect().width / 8;
    const slide = (from, to) => {
      const el = $("board").querySelector(`.pc[data-sq="${to}"]`);
      if (!el || !el.animate) return;
      const a = viewPos(from), z = viewPos(to);
      el.animate(
        [{ transform: `translate(${(a.col - z.col) * size}px, ${(a.row - z.row) * size}px)` }, { transform: "none" }],
        { duration: 220, easing: "cubic-bezier(.2,.8,.3,1)" },
      );
    };
    slide(m.from, m.to);
    if (m.flag === "k") slide(m.to + 1, m.to - 1);
    if (m.flag === "q") slide(m.to - 2, m.to + 1);
  }

  function capturedBy(color) {
    // color が取った駒 = 相手の色で、盤から消えた駒
    const them = E.other(color);
    const out = [];
    for (const t of "qrbnp") {
      const left = S.game.board.filter((p) => p && E.colorOf(p) === them && E.typeOf(p) === t).length;
      for (let i = 0; i < Math.max(0, START_COUNT[t] - left); i++) out.push(them === "w" ? t.toUpperCase() : t);
    }
    return out;
  }

  function renderSide() {
    const g = S.game;
    // 設定バー
    document.querySelectorAll("#modeSeg button").forEach((x) => x.classList.toggle("on", x.dataset.v === S.next.mode));
    document.querySelectorAll("#colorSeg button").forEach((x) => x.classList.toggle("on", x.dataset.v === S.next.color));
    $("colorSeg").hidden = S.next.mode !== "cpu";
    $("levelBox").hidden = S.next.mode !== "cpu";
    $("level").value = S.level;
    const changed = S.next.mode !== S.mode || (S.next.mode === "cpu" && S.next.color !== S.color);
    $("note").hidden = !(changed && S.ucis.length && !S.over);

    // 状況
    const status = $("status");
    status.className = "status";
    if (S.over) {
      status.textContent = resultText().text;
    } else if (S.thinking) {
      status.classList.add("think");
      status.innerHTML = `🤖 CPU（${COLOR[g.turn]}）が考え中<span class="thinking-dots"></span>`;
    } else if (g.inCheck()) {
      status.classList.add("check");
      status.textContent = `⚠️ チェック！ ${sideName(g.turn)}のキングがねらわれているよ`;
    } else {
      status.textContent = `👉 ${sideName(g.turn)}の番だよ`;
    }

    // ボタン
    const playerMoves = S.mode === "cpu" ? S.ucis.length - (S.color === "w" ? 0 : 1) : S.ucis.length;
    $("undoBtn").disabled = playerMoves <= 0;
    $("hintBtn").disabled = !canTouch();
    $("soundBtn").textContent = S.sound ? "🔊 音あり" : "🔇 音なし";

    // 説明
    const ex = $("explain");
    if (S.selected >= 0 && g.board[S.selected]) {
      const p = g.board[S.selected], t = E.typeOf(p);
      ex.innerHTML = `<b>${piece(p)} ${NAME[t]}</b>：${HOW[t]}<br>` +
        (S.targets.length ? `動けるマスは <b>${S.targets.length}か所</b>（●のマス）` : "この駒は いま動けないよ。");
    } else if (!S.hint) {
      ex.textContent = S.over ? "「新しいゲーム」で もう一回あそべるよ。"
        : isCpuTurn() ? "CPUが どこに動かすか 見ていよう。"
          : "動かしたい駒を クリック（ドラッグもOK）してね。";
    }

    // 形勢
    const score = E.evaluate(g);
    const white = Math.max(4, Math.min(96, 50 + score / 15));
    const bottom = S.flipped ? "b" : "w";
    const fill = $("evalFill");
    fill.style.height = (bottom === "w" ? white : 100 - white) + "%";
    fill.style.background = bottom === "w" ? "#fbf7f0" : "#3b3340";
    fill.parentElement.style.background = bottom === "w" ? "#3b3340" : "#fbf7f0";
    const lead = score > 0 ? "w" : "b", size = Math.abs(score);
    $("evalText").textContent = "📊 形勢：" + (size < 60 ? "ほぼ互角（ごかく）"
      : `${sideName(lead)}が ${size < 300 ? "すこし" : size < 800 ? "かなり" : "とても"}有利`);

    // とった駒
    const top = S.flipped ? "w" : "b";
    for (const [id, side] of [["capTop", top], ["capBottom", E.other(top)]]) {
      const mine = capturedBy(side), theirs = capturedBy(E.other(side));
      const sum = (list) => list.reduce((s, p) => s + POINTS[E.typeOf(p)], 0);
      const diff = sum(mine) - sum(theirs);
      $(id).innerHTML = mine.map((p) => piece(p)).join("") + (diff > 0 ? `<span class="lead">+${diff}</span>` : "");
    }

    // 棋譜（駒の記号で表示）
    const rows = [];
    for (let i = 0; i < S.sans.length; i += 2) {
      const fig = (s) => s.replace(/^[KQRBN]/, (c) => GLYPH[c.toLowerCase()] + VS);
      const cell = (j) => (j < S.sans.length
        ? `<span class="mv${j === S.sans.length - 1 ? " now" : ""}">${fig(S.sans[j])}</span>` : "<span></span>");
      rows.push(`<span class="no">${i / 2 + 1}.</span>${cell(i)}${cell(i + 1)}`);
    }
    const list = $("moves");
    list.innerHTML = rows.join("") || '<span class="empty">まだ動かしていないよ</span>';
    list.scrollTop = list.scrollHeight;
  }

  function resultText() {
    const o = S.over;
    if (o.reason === "checkmate") {
      if (S.mode === "pvp") return { emoji: "🏆", text: `チェックメイト！ ${COLOR[o.winner]}の勝ち！`, mood: "win" };
      return o.winner === S.color
        ? { emoji: "🏆", text: "チェックメイト！ あなたの勝ち！🎉", mood: "win" }
        : { emoji: "🤖", text: "チェックメイトされちゃった… CPUの勝ち。もう一回ちょうせんしよう！", mood: "lose" };
    }
    return { emoji: "🤝", text: DRAW_TEXT[o.reason], mood: "draw" };
  }

  // ---------------- 手を指す ----------------
  function select(sq) {
    S.selected = sq;
    S.targets = [...new Set(S.game.legalMoves().filter((m) => m.from === sq).map((m) => m.to))];
    S.hint = null;
    render();
  }

  function clearSelection() {
    S.selected = -1;
    S.targets = [];
  }

  function tryMove(from, to) {
    const ms = S.game.legalMoves().filter((m) => m.from === from && m.to === to);
    if (!ms.length) return;
    if (ms.length > 1) showPromotion(ms);
    else commit(ms[0]);
  }

  function showPromotion(ms) {
    const color = S.game.turn;
    $("promoChoices").innerHTML = "qrbn".split("").map((t) =>
      `<button data-t="${t}">${piece(color === "w" ? t.toUpperCase() : t)}<small>${NAME[t]}</small></button>`).join("");
    $("promo").hidden = false;
    $("promoChoices").onclick = (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      $("promo").hidden = true;
      commit(ms.find((m) => m.promo === btn.dataset.t));
    };
  }

  function commit(m) {
    S.sans.push(S.game.play(m));
    S.ucis.push(E.uci(m));
    clearSelection();
    S.hint = null;
    const st = S.game.status();
    if (!st.over) (S.game.inCheck() ? sfx.check : m.captured ? sfx.capture : sfx.move)();
    render(m);
    save();
    if (st.over) finish(st);
    else maybeThink();
  }

  function finish(st) {
    S.over = st;
    S.thinking = false;
    const r = resultText();
    sfx[r.mood]();
    $("resultEmoji").textContent = r.emoji;
    $("resultText").textContent = r.text;
    setTimeout(() => { if (S.over === st) $("result").hidden = false; }, 450);
    report();
    render();
  }

  function report() {
    if (S.reported) return;
    S.reported = true;
    save();
    const o = S.over;
    Streamlit.setValue({
      type: "game_over",
      id: S.gameId,
      result: o.winner === "w" ? "1-0" : o.winner === "b" ? "0-1" : "1/2-1/2",
      reason: o.reason,
      mode: S.mode === "cpu" ? "1人プレイ（CPU戦）" : "2人プレイ",
      level: S.mode === "cpu" ? LEVELS[S.level] : "-",
      moves: S.ucis.length,
    });
  }

  function takeBackOne() {
    S.game.takeBack();
    S.sans.pop();
    S.ucis.pop();
  }

  function undo() {
    if (!S.ucis.length) return;
    S.token++;
    S.thinking = false;
    const wasOver = !!S.over;
    takeBackOne();
    if (S.mode === "cpu" && S.game.turn !== S.color && S.ucis.length) takeBackOne();
    S.over = null;
    $("result").hidden = true;
    if (wasOver) {
      // 終わったゲームをやり直したら、別のゲームとして記録する
      S.gameId = newId();
      S.reported = false;
    }
    clearSelection();
    S.hint = null;
    save();
    render();
    maybeThink();
  }

  function newGame() {
    S.mode = S.next.mode;
    S.color = S.next.color;
    S.token++;
    S.thinking = false;
    S.game = new E.Game();
    S.sans = [];
    S.ucis = [];
    S.over = null;
    clearSelection();
    S.hint = null;
    S.flipped = S.mode === "cpu" && S.color === "b";
    S.gameId = newId();
    S.reported = false;
    $("result").hidden = true;
    $("promo").hidden = true;
    save();
    render();
    maybeThink();
  }

  function hint() {
    if (!canTouch()) return;
    const btn = $("hintBtn"), at = S.ucis.length;
    btn.disabled = true;
    btn.textContent = "🤔 考え中…";
    ask({ moves: S.ucis.slice(), level: "hard" }).then((u) => {
      btn.textContent = "💡 ヒント";
      if (S.ucis.length !== at || S.over) return render();
      const m = u && S.game.findMove(u);
      if (!m) return render();
      clearSelection();
      S.hint = { from: m.from, to: m.to };
      render();
      $("explain").innerHTML = `💡 <b>ヒント</b>：${piece(m.piece)} ${NAME[E.typeOf(m.piece)]}を ` +
        `<b>${E.sqName(m.from)}</b> から <b>${E.sqName(m.to)}</b> へ 動かしてみよう！`;
    });
  }

  // ---------------- マウス・タッチ操作 ----------------
  function squareAt(x, y) {
    const el = document.elementFromPoint(x, y);
    const sq = el && el.closest(".sq");
    return sq ? Number(sq.dataset.sq) : -1;
  }

  function onDown(e) {
    const el = e.target.closest(".sq");
    if (!el) return;
    const sq = Number(el.dataset.sq);
    if (!canTouch()) {
      if (S.thinking || isCpuTurn()) $("status").classList.add("shake");
      setTimeout(() => $("status").classList.remove("shake"), 450);
      return;
    }
    if (S.selected >= 0 && S.targets.includes(sq)) return tryMove(S.selected, sq);
    const p = S.game.board[sq];
    if (p && E.colorOf(p) === S.game.turn) {
      const wasSelected = S.selected === sq;
      select(sq);
      drag = { sq, x: e.clientX, y: e.clientY, ghost: null, wasSelected };
      try { $("board").setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    } else {
      clearSelection();
      render();
      if (p) $("explain").innerHTML = `それは 相手の駒（${NAME[E.typeOf(p)]}）だよ。`;
    }
  }

  function onMove(e) {
    if (!drag) return;
    if (!drag.ghost && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 5) {
      const pc = $("board").querySelector(`.pc[data-sq="${drag.sq}"]`);
      if (!pc) return;
      drag.ghost = pc.cloneNode(true);
      drag.ghost.classList.add("ghost");
      document.body.appendChild(drag.ghost);
      pc.classList.add("lifted");
    }
    if (drag.ghost) {
      drag.ghost.style.left = e.clientX + "px";
      drag.ghost.style.top = e.clientY + "px";
    }
  }

  function onUp(e) {
    if (!drag) return;
    const d = drag;
    drag = null;
    if (d.ghost) {
      d.ghost.remove();
      const to = squareAt(e.clientX, e.clientY);
      if (S.targets.includes(to)) return tryMove(d.sq, to);
      return render();
    }
    if (d.wasSelected) {
      clearSelection();
      render();
    }
  }

  function onCancel() {
    if (drag && drag.ghost) drag.ghost.remove();
    drag = null;
    render();
  }

  // ---------------- はじめる ----------------
  function restore() {
    const saved = loadSaved();
    if (!saved) return newGame();
    S.mode = saved.mode === "pvp" ? "pvp" : "cpu";
    S.color = saved.color === "b" ? "b" : "w";
    S.level = LEVELS[saved.level] ? saved.level : "normal";
    S.next = { mode: S.mode, color: S.color };
    S.flipped = !!saved.flipped;
    S.sound = saved.sound !== false;
    S.gameId = saved.gameId || newId();
    S.reported = !!saved.reported;
    for (const u of saved.ucis || []) {
      const m = S.game.findMove(u);
      if (!m) break;
      S.sans.push(S.game.play(m));
      S.ucis.push(u);
    }
    const st = S.game.status();
    if (st.over) {
      S.over = st;
      report();
    }
    render();
    maybeThink();
  }

  function init() {
    fit();
    window.addEventListener("resize", () => { fit(); render(); });
    const board = $("board");
    board.addEventListener("pointerdown", onDown);
    board.addEventListener("pointermove", onMove);
    board.addEventListener("pointerup", onUp);
    board.addEventListener("pointercancel", onCancel);

    $("modeSeg").onclick = (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      S.next.mode = b.dataset.v;
      if (!S.ucis.length || S.over) newGame();
      else render();
    };
    $("colorSeg").onclick = (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      S.next.color = b.dataset.v;
      if (!S.ucis.length || S.over) newGame();
      else render();
    };
    $("level").onchange = (e) => { S.level = e.target.value; save(); render(); };
    $("newBtn").onclick = newGame;
    $("againBtn").onclick = newGame;
    $("viewBtn").onclick = () => { $("result").hidden = true; };
    $("promo").onclick = (e) => { if (e.target.id === "promo") { $("promo").hidden = true; render(); } };
    $("undoBtn").onclick = undo;
    $("hintBtn").onclick = hint;
    $("flipBtn").onclick = () => { S.flipped = !S.flipped; save(); render(); };
    $("soundBtn").onclick = () => { S.sound = !S.sound; save(); render(); };
    restore();
  }

  let started = false;
  Streamlit.ready(() => {
    if (started) return;
    started = true;
    init();
  });
})();
