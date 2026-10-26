/* チェスのルールと CPU の思考。画面（app.js）と Web Worker の両方から使う。 */
(function (root) {
  "use strict";

  const FILES = "abcdefgh";
  const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
  const VALUE = { p: 100, n: 320, b: 330, r: 500, q: 900, k: 0 };
  const KNIGHT = [[1, 2], [2, 1], [2, -1], [1, -2], [-1, -2], [-2, -1], [-2, 1], [-1, 2]];
  const KING = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
  const DIAG = [[1, 1], [1, -1], [-1, 1], [-1, -1]];
  const ORTH = [[1, 0], [-1, 0], [0, 1], [0, -1]];

  const colorOf = (p) => (p === p.toUpperCase() ? "w" : "b");
  const typeOf = (p) => p.toLowerCase();
  const other = (c) => (c === "w" ? "b" : "w");
  const onBoard = (f, r) => f >= 0 && f < 8 && r >= 0 && r < 8;
  const sqName = (sq) => FILES[sq & 7] + ((sq >> 3) + 1);
  const sqFrom = (name) => FILES.indexOf(name[0]) + (Number(name[1]) - 1) * 8;
  const uci = (m) => sqName(m.from) + sqName(m.to) + (m.promo || "");

  // マス番号は a1=0, b1=1, ... h8=63（rank*8 + file）
  class Game {
    constructor(fen) {
      this.load(fen || START_FEN);
    }

    load(fen) {
      const [placement, turn, castle, ep, half, full] = fen.split(" ");
      this.board = new Array(64).fill(null);
      this.kings = { w: -1, b: -1 };
      placement.split("/").forEach((row, i) => {
        let f = 0;
        for (const ch of row) {
          if (/\d/.test(ch)) { f += Number(ch); continue; }
          const sq = (7 - i) * 8 + f;
          this.board[sq] = ch;
          if (ch === "K") this.kings.w = sq;
          if (ch === "k") this.kings.b = sq;
          f++;
        }
      });
      this.turn = turn || "w";
      const c = castle || "-";
      this.castle = { K: c.includes("K"), Q: c.includes("Q"), k: c.includes("k"), q: c.includes("q") };
      this.ep = ep && ep !== "-" ? sqFrom(ep) : -1;
      this.half = Number(half) || 0;
      this.full = Number(full) || 1;
      this.stack = [];
      this.keys = [this.key()];
    }

    key() {
      const c = this.castle;
      return this.board.map((p) => p || ".").join("") + this.turn +
        (c.K ? "K" : "") + (c.Q ? "Q" : "") + (c.k ? "k" : "") + (c.q ? "q" : "") + this.ep;
    }

    attacked(sq, by) {
      const b = this.board, f = sq & 7, r = sq >> 3;
      const pr = by === "w" ? r - 1 : r + 1, pawn = by === "w" ? "P" : "p";
      for (const df of [-1, 1]) if (onBoard(f + df, pr) && b[pr * 8 + f + df] === pawn) return true;
      const knight = by === "w" ? "N" : "n";
      for (const [df, dr] of KNIGHT) if (onBoard(f + df, r + dr) && b[(r + dr) * 8 + f + df] === knight) return true;
      const king = by === "w" ? "K" : "k";
      for (const [df, dr] of KING) if (onBoard(f + df, r + dr) && b[(r + dr) * 8 + f + df] === king) return true;
      const [bishop, rook, queen] = by === "w" ? ["B", "R", "Q"] : ["b", "r", "q"];
      for (const [dirs, slider] of [[DIAG, bishop], [ORTH, rook]]) {
        for (const [df, dr] of dirs) {
          let ff = f + df, rr = r + dr;
          while (onBoard(ff, rr)) {
            const p = b[rr * 8 + ff];
            if (p) {
              if (p === slider || p === queen) return true;
              break;
            }
            ff += df; rr += dr;
          }
        }
      }
      return false;
    }

    inCheck(color = this.turn) {
      return this.attacked(this.kings[color], other(color));
    }

    // 自分のキングが取られる手もふくむ「ルール上の動き」。capturesOnly なら駒を取る手と成りだけ。
    pseudoMoves(capturesOnly = false) {
      const moves = [], b = this.board, us = this.turn, them = other(us);
      const add = (from, to, piece, captured, flag, promo) =>
        moves.push({ from, to, piece, captured: captured || null, flag: flag || "n", promo: promo || null });

      for (let sq = 0; sq < 64; sq++) {
        const p = b[sq];
        if (!p || colorOf(p) !== us) continue;
        const t = typeOf(p), f = sq & 7, r = sq >> 3;

        if (t === "p") {
          const dir = us === "w" ? 1 : -1, last = us === "w" ? 7 : 0, home = us === "w" ? 1 : 6;
          const pawnTo = (to, cap, flag) => {
            if ((to >> 3) === last) for (const pr of "qrbn") add(sq, to, p, cap, flag, pr);
            else add(sq, to, p, cap, flag);
          };
          const one = sq + 8 * dir;
          if (!b[one]) {
            if (!capturesOnly || (one >> 3) === last) pawnTo(one, null, "n");
            if (!capturesOnly && r === home && !b[one + 8 * dir]) add(sq, one + 8 * dir, p, null, "b");
          }
          for (const df of [-1, 1]) {
            if (!onBoard(f + df, r + dir)) continue;
            const to = sq + 8 * dir + df, target = b[to];
            if (target && colorOf(target) === them) pawnTo(to, target, "c");
            else if (to === this.ep) add(sq, to, p, us === "w" ? "p" : "P", "e");
          }
          continue;
        }

        if (t === "n" || t === "k") {
          for (const [df, dr] of t === "n" ? KNIGHT : KING) {
            if (!onBoard(f + df, r + dr)) continue;
            const to = sq + dr * 8 + df, target = b[to];
            if (!target) { if (!capturesOnly) add(sq, to, p, null, "n"); }
            else if (colorOf(target) === them) add(sq, to, p, target, "c");
          }
          if (t === "k" && !capturesOnly) this.addCastles(sq, p, add);
          continue;
        }

        const dirs = t === "b" ? DIAG : t === "r" ? ORTH : DIAG.concat(ORTH);
        for (const [df, dr] of dirs) {
          let ff = f + df, rr = r + dr;
          while (onBoard(ff, rr)) {
            const to = rr * 8 + ff, target = b[to];
            if (!target) {
              if (!capturesOnly) add(sq, to, p, null, "n");
            } else {
              if (colorOf(target) === them) add(sq, to, p, target, "c");
              break;
            }
            ff += df; rr += dr;
          }
        }
      }
      return moves;
    }

    addCastles(sq, p, add) {
      const b = this.board, us = this.turn, them = other(us);
      const base = us === "w" ? 0 : 56;
      if (sq !== base + 4) return;
      const [kSide, qSide, rook] = us === "w" ? ["K", "Q", "R"] : ["k", "q", "r"];
      if (this.castle[kSide] && b[base + 7] === rook && !b[base + 5] && !b[base + 6] &&
          !this.attacked(base + 4, them) && !this.attacked(base + 5, them) && !this.attacked(base + 6, them)) {
        add(sq, base + 6, p, null, "k");
      }
      if (this.castle[qSide] && b[base] === rook && !b[base + 1] && !b[base + 2] && !b[base + 3] &&
          !this.attacked(base + 4, them) && !this.attacked(base + 3, them) && !this.attacked(base + 2, them)) {
        add(sq, base + 2, p, null, "q");
      }
    }

    make(m) {
      const b = this.board, us = this.turn;
      this.stack.push({ m, castle: { ...this.castle }, ep: this.ep, half: this.half, full: this.full });
      b[m.from] = null;
      if (m.flag === "e") b[m.to + (us === "w" ? -8 : 8)] = null;
      b[m.to] = m.promo ? (us === "w" ? m.promo.toUpperCase() : m.promo) : m.piece;
      if (m.flag === "k") { b[m.to - 1] = b[m.to + 1]; b[m.to + 1] = null; }
      if (m.flag === "q") { b[m.to + 1] = b[m.to - 2]; b[m.to - 2] = null; }
      if (typeOf(m.piece) === "k") {
        this.kings[us] = m.to;
        if (us === "w") this.castle.K = this.castle.Q = false;
        else this.castle.k = this.castle.q = false;
      }
      for (const sq of [m.from, m.to]) {
        if (sq === 0) this.castle.Q = false;
        else if (sq === 7) this.castle.K = false;
        else if (sq === 56) this.castle.q = false;
        else if (sq === 63) this.castle.k = false;
      }
      this.ep = m.flag === "b" ? (m.from + m.to) >> 1 : -1;
      this.half = typeOf(m.piece) === "p" || m.captured ? 0 : this.half + 1;
      if (us === "b") this.full++;
      this.turn = other(us);
    }

    undo() {
      const s = this.stack.pop();
      if (!s) return null;
      const m = s.m, b = this.board, us = other(this.turn);
      this.turn = us;
      b[m.from] = m.piece;
      b[m.to] = m.flag === "e" ? null : m.captured;
      if (m.flag === "e") b[m.to + (us === "w" ? -8 : 8)] = m.captured;
      if (m.flag === "k") { b[m.to + 1] = b[m.to - 1]; b[m.to - 1] = null; }
      if (m.flag === "q") { b[m.to - 2] = b[m.to + 1]; b[m.to + 1] = null; }
      if (typeOf(m.piece) === "k") this.kings[us] = m.from;
      this.castle = s.castle;
      this.ep = s.ep;
      this.half = s.half;
      this.full = s.full;
      return m;
    }

    legalMoves() {
      const us = this.turn;
      return this.pseudoMoves().filter((m) => {
        this.make(m);
        const ok = !this.attacked(this.kings[us], this.turn);
        this.undo();
        return ok;
      });
    }

    findMove(u) {
      return this.legalMoves().find((m) => uci(m) === u) || null;
    }

    // 対局としての1手（千日手の判定用に局面も記録する）
    play(m) {
      const san = this.san(m);
      this.make(m);
      this.keys.push(this.key());
      return san;
    }

    takeBack() {
      if (!this.stack.length) return null;
      this.keys.pop();
      return this.undo();
    }

    san(m) {
      let s;
      if (m.flag === "k") s = "O-O";
      else if (m.flag === "q") s = "O-O-O";
      else {
        const t = typeOf(m.piece), cap = m.captured ? "x" : "";
        if (t === "p") {
          s = (cap ? FILES[m.from & 7] : "") + cap + sqName(m.to) + (m.promo ? "=" + m.promo.toUpperCase() : "");
        } else {
          const rivals = this.legalMoves().filter((o) => o.piece === m.piece && o.to === m.to && o.from !== m.from);
          let dis = "";
          if (rivals.length) {
            const sameFile = rivals.some((o) => (o.from & 7) === (m.from & 7));
            const sameRank = rivals.some((o) => (o.from >> 3) === (m.from >> 3));
            dis = !sameFile ? FILES[m.from & 7] : !sameRank ? String((m.from >> 3) + 1) : sqName(m.from);
          }
          s = t.toUpperCase() + dis + cap + sqName(m.to);
        }
      }
      this.make(m);
      if (this.inCheck()) s += this.legalMoves().length ? "+" : "#";
      this.undo();
      return s;
    }

    insufficient() {
      const rest = this.board.filter((p) => p && typeOf(p) !== "k");
      return rest.length === 0 || (rest.length === 1 && "nb".includes(typeOf(rest[0])));
    }

    status() {
      const moves = this.legalMoves();
      if (!moves.length) {
        return this.inCheck()
          ? { over: true, reason: "checkmate", winner: other(this.turn) }
          : { over: true, reason: "stalemate", winner: null };
      }
      if (this.half >= 100) return { over: true, reason: "fifty", winner: null };
      const now = this.keys[this.keys.length - 1];
      if (this.keys.filter((k) => k === now).length >= 3) return { over: true, reason: "repetition", winner: null };
      if (this.insufficient()) return { over: true, reason: "insufficient", winner: null };
      return { over: false, check: this.inCheck(), moves };
    }
  }

  // ---------------- 形勢判断（白から見た点数） ----------------
  // 駒の位置ごとのボーナス（a8..h8 が先頭、白の向き）
  const PST = {
    p: [0, 0, 0, 0, 0, 0, 0, 0, 50, 50, 50, 50, 50, 50, 50, 50, 10, 10, 20, 30, 30, 20, 10, 10, 5, 5, 10, 25, 25, 10, 5, 5,
      0, 0, 0, 20, 20, 0, 0, 0, 5, -5, -10, 0, 0, -10, -5, 5, 5, 10, 10, -20, -20, 10, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0],
    n: [-50, -40, -30, -30, -30, -30, -40, -50, -40, -20, 0, 0, 0, 0, -20, -40, -30, 0, 10, 15, 15, 10, 0, -30, -30, 5, 15, 20, 20, 15, 5, -30,
      -30, 0, 15, 20, 20, 15, 0, -30, -30, 5, 10, 15, 15, 10, 5, -30, -40, -20, 0, 5, 5, 0, -20, -40, -50, -40, -30, -30, -30, -30, -40, -50],
    b: [-20, -10, -10, -10, -10, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 10, 10, 5, 0, -10, -10, 5, 5, 10, 10, 5, 5, -10,
      -10, 0, 10, 10, 10, 10, 0, -10, -10, 10, 10, 10, 10, 10, 10, -10, -10, 5, 0, 0, 0, 0, 5, -10, -20, -10, -10, -10, -10, -10, -10, -20],
    r: [0, 0, 0, 0, 0, 0, 0, 0, 5, 10, 10, 10, 10, 10, 10, 5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5,
      -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, 0, 0, 0, 5, 5, 0, 0, 0],
    q: [-20, -10, -10, -5, -5, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 5, 5, 5, 0, -10, -5, 0, 5, 5, 5, 5, 0, -5,
      0, 0, 5, 5, 5, 5, 0, -5, -10, 5, 5, 5, 5, 5, 0, -10, -10, 0, 5, 0, 0, 0, 0, -10, -20, -10, -10, -5, -5, -10, -10, -20],
    k: [-30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30,
      -20, -30, -30, -40, -40, -30, -30, -20, -10, -20, -20, -20, -20, -20, -20, -10, 20, 20, 0, 0, 0, 0, 20, 20, 20, 30, 10, 0, 0, 10, 30, 20],
  };
  const KING_END = [-50, -40, -30, -20, -20, -30, -40, -50, -30, -20, -10, 0, 0, -10, -20, -30, -30, -10, 20, 30, 30, 20, -10, -30, -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30, -30, -10, 20, 30, 30, 20, -10, -30, -30, -30, 0, 0, 0, 0, -30, -30, -50, -30, -30, -30, -30, -30, -30, -50];

  function evaluate(g) {
    const b = g.board;
    let material = 0;
    for (const p of b) if (p && "nbrq".includes(typeOf(p))) material += VALUE[typeOf(p)];
    const endgame = material <= 2600;
    let score = 0;
    for (let sq = 0; sq < 64; sq++) {
      const p = b[sq];
      if (!p) continue;
      const t = typeOf(p), white = colorOf(p) === "w";
      const idx = white ? (7 - (sq >> 3)) * 8 + (sq & 7) : sq;
      const table = t === "k" && endgame ? KING_END : PST[t];
      const v = VALUE[t] + table[idx];
      score += white ? v : -v;
    }
    return score;
  }

  // ---------------- CPU の思考（αβ探索） ----------------
  const MATE = 100000;
  const LEVELS = {
    easy: { depth: 1, quiet: false, noise: 250, time: 400 },
    normal: { depth: 2, quiet: true, noise: 40, time: 900 },
    hard: { depth: 4, quiet: true, noise: 0, time: 1200 },
    expert: { depth: 8, quiet: true, noise: 0, time: 2500 },
  };

  function orderMoves(moves) {
    for (const m of moves) {
      m.order = (m.captured ? 10 * VALUE[typeOf(m.captured)] - VALUE[typeOf(m.piece)] + 10000 : 0) + (m.promo ? 8000 : 0);
    }
    return moves.sort((a, b) => b.order - a.order);
  }

  function sideEval(g) {
    return g.turn === "w" ? evaluate(g) : -evaluate(g);
  }

  function quiesce(g, alpha, beta, ctx, left) {
    ctx.nodes++;
    const stand = sideEval(g);
    if (stand >= beta || left <= 0) return stand;
    if (stand > alpha) alpha = stand;
    const us = g.turn;
    for (const m of orderMoves(g.pseudoMoves(true))) {
      g.make(m);
      if (g.attacked(g.kings[us], g.turn)) { g.undo(); continue; }
      const s = -quiesce(g, -beta, -alpha, ctx, left - 1);
      g.undo();
      if (s >= beta) return s;
      if (s > alpha) alpha = s;
    }
    return alpha;
  }

  function negamax(g, depth, alpha, beta, ply, ctx) {
    if ((++ctx.nodes & 1023) === 0 && Date.now() > ctx.deadline) ctx.stop = true;
    if (ctx.stop) return 0;
    if (depth <= 0) return ctx.quiet ? quiesce(g, alpha, beta, ctx, 6) : sideEval(g);
    const us = g.turn;
    let best = -Infinity, legal = 0;
    for (const m of orderMoves(g.pseudoMoves())) {
      g.make(m);
      if (g.attacked(g.kings[us], g.turn)) { g.undo(); continue; }
      legal++;
      const s = -negamax(g, depth - 1, -beta, -alpha, ply + 1, ctx);
      g.undo();
      if (ctx.stop) return 0;
      if (s > best) best = s;
      if (s > alpha) alpha = s;
      if (alpha >= beta) break;
    }
    if (!legal) return g.inCheck() ? -MATE + ply : 0;
    return best;
  }

  // だんだん深く読む。時間切れになったら、最後まで読めた深さの一番いい手を返す。
  function bestMove(g, level) {
    const cfg = LEVELS[level] || LEVELS.normal;
    const ctx = { deadline: Date.now() + cfg.time, nodes: 0, stop: false, quiet: cfg.quiet };
    let roots = orderMoves(g.legalMoves());
    if (!roots.length) return null;
    let best = roots[0], bestScore = 0;
    for (let depth = 1; depth <= cfg.depth; depth++) {
      const scored = [];
      let alpha = -Infinity;
      for (const m of roots) {
        g.make(m);
        // ゆらぎを入れるレベルでは、全部の手を正確に比べるため窓をせばめない
        let s = -negamax(g, depth - 1, -Infinity, cfg.noise ? Infinity : -alpha, 1, ctx);
        g.undo();
        if (ctx.stop) break;
        if (cfg.noise) s += (Math.random() * 2 - 1) * cfg.noise;
        scored.push([s, m]);
        if (s > alpha) alpha = s;
      }
      if ((ctx.stop && depth > 1) || !scored.length) break;
      scored.sort((a, b) => b[0] - a[0]);
      best = scored[0][1];
      bestScore = scored[0][0];
      roots = scored.map((x) => x[1]).concat(roots.filter((m) => !scored.some((x) => x[1] === m)));
      if (Math.abs(bestScore) > MATE - 100 || ctx.stop) break;
    }
    return { move: best, score: bestScore, nodes: ctx.nodes };
  }

  // Web Worker として読み込まれたときは、手を考えて返す係になる
  if (typeof importScripts === "function" && typeof window === "undefined") {
    self.onmessage = (e) => {
      const { moves, level, token } = e.data;
      const g = new Game();
      for (const u of moves) {
        const m = g.findMove(u);
        if (m) g.make(m);
      }
      const r = bestMove(g, level);
      self.postMessage({ token, move: r ? uci(r.move) : null });
    };
  }

  root.ChessEngine = { Game, bestMove, evaluate, colorOf, typeOf, sqName, sqFrom, uci, other };
})(typeof globalThis !== "undefined" ? globalThis : this);
