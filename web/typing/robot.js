/* ロボットを動かす「かんたん Python」。for / if / 変数 / リスト / 関数よびだし が使える。 */
const Robo = (() => {
  class CodeError extends Error {
    constructor(msg, line) {
      super(msg);
      this.line = line;
    }
  }

  const COLORS = {
    red: "#ff6b6b", blue: "#4d96ff", green: "#6bcb77", yellow: "#ffd93d", orange: "#ff9f43",
    purple: "#a66cff", pink: "#ff8fcf", black: "#3a2e39", white: "#ffffff", brown: "#a0785a", gray: "#b0a8b0",
    あか: "#ff6b6b", あお: "#4d96ff", みどり: "#6bcb77", きいろ: "#ffd93d", オレンジ: "#ff9f43",
    むらさき: "#a66cff", ピンク: "#ff8fcf", くろ: "#3a2e39", しろ: "#ffffff", ちゃいろ: "#a0785a",
  };
  const DIRS = [[0, -1], [1, 0], [0, 1], [-1, 0]]; // 上・右・下・左
  const FUNCS = ["move", "turn_left", "turn_right", "paint", "pen", "pen_up", "say", "print", "range", "str", "int", "len", "randint"];
  const KEYWORDS = ["for", "in", "if", "elif", "else", "and", "or", "not", "True", "False", "pass"];

  // ---------------- 字句解析 ----------------
  function tokenize(text, line) {
    const toks = [];
    let i = 0;
    while (i < text.length) {
      const c = text[i];
      if (c === " ") { i++; continue; }
      if (c === "#") break;
      if (/[（）＂＝：，＋－＊／［］　”“’‘]/.test(c)) {
        throw new CodeError(`全角（ぜんかく）の「${c}」が入っているよ。日本語入力をオフにして打ちなおしてね`, line);
      }
      if (/\d/.test(c)) {
        let j = i;
        while (j < text.length && /[\d.]/.test(text[j])) j++;
        toks.push({ t: "num", v: Number(text.slice(i, j)) });
        i = j;
        continue;
      }
      if (/[A-Za-z_぀-ヿ一-龯]/.test(c)) {
        let j = i;
        while (j < text.length && /[\w぀-ヿ一-龯]/.test(text[j])) j++;
        toks.push({ t: "name", v: text.slice(i, j) });
        i = j;
        continue;
      }
      if (c === '"' || c === "'") {
        const j = text.indexOf(c, i + 1);
        if (j < 0) throw new CodeError(`文字列の ${c} が とじていないよ（${c}...${c} のように、はさんでね）`, line);
        toks.push({ t: "str", v: text.slice(i + 1, j) });
        i = j + 1;
        continue;
      }
      const two = text.slice(i, i + 2);
      if (["==", "!=", "<=", ">=", "//", "+=", "-=", "*="].includes(two)) {
        toks.push({ t: "op", v: two });
        i += 2;
        continue;
      }
      if ("+-*/%()[],<>=:.".includes(c)) {
        toks.push({ t: "op", v: c });
        i++;
        continue;
      }
      throw new CodeError(`「${c}」は ここでは使えない文字だよ`, line);
    }
    return toks;
  }

  // ---------------- 式の読みとり ----------------
  function parseExpr(toks, line) {
    let p = 0;
    const peek = () => toks[p];
    const isOp = (v) => toks[p] && toks[p].t === "op" && toks[p].v === v;
    const isName = (v) => toks[p] && toks[p].t === "name" && toks[p].v === v;
    const expect = (v, msg) => {
      if (!isOp(v)) throw new CodeError(msg || `「${v}」が たりないよ`, line);
      p++;
    };

    function or() {
      let a = and();
      while (isName("or")) { p++; a = { k: "bin", op: "or", a, b: and() }; }
      return a;
    }
    function and() {
      let a = not();
      while (isName("and")) { p++; a = { k: "bin", op: "and", a, b: not() }; }
      return a;
    }
    function not() {
      if (isName("not")) { p++; return { k: "un", op: "not", a: not() }; }
      return cmp();
    }
    function cmp() {
      let a = add();
      while (peek() && peek().t === "op" && ["==", "!=", "<", ">", "<=", ">="].includes(peek().v)) {
        const op = toks[p++].v;
        a = { k: "bin", op, a, b: add() };
      }
      if (isOp("=")) throw new CodeError("くらべるときは「=」ではなく「==」を使うよ", line);
      return a;
    }
    function add() {
      let a = mul();
      while (isOp("+") || isOp("-")) { const op = toks[p++].v; a = { k: "bin", op, a, b: mul() }; }
      return a;
    }
    function mul() {
      let a = unary();
      while (isOp("*") || isOp("/") || isOp("//") || isOp("%")) { const op = toks[p++].v; a = { k: "bin", op, a, b: unary() }; }
      return a;
    }
    function unary() {
      if (isOp("-")) { p++; return { k: "un", op: "-", a: unary() }; }
      return postfix();
    }
    function postfix() {
      let a = primary();
      for (;;) {
        if (isOp("(")) {
          if (a.k !== "name") throw new CodeError("( の まえには 命令の名前を書いてね", line);
          p++;
          const args = [];
          if (!isOp(")")) {
            for (;;) {
              args.push(or());
              if (isOp(",")) { p++; continue; }
              break;
            }
          }
          expect(")", "かっこ「)」が とじていないよ");
          a = { k: "call", name: a.v, args };
        } else if (isOp("[")) {
          p++;
          const i = or();
          expect("]", "「]」が たりないよ");
          a = { k: "idx", a, i };
        } else if (isOp(".")) {
          throw new CodeError("「.」は このロボットでは使えないよ（robot.move ではなく move と書いてね）", line);
        } else {
          return a;
        }
      }
    }
    function primary() {
      const t = toks[p];
      if (!t) throw new CodeError("式（しき）が とちゅうで おわっているよ", line);
      p++;
      if (t.t === "num") return { k: "num", v: t.v };
      if (t.t === "str") return { k: "str", v: t.v };
      if (t.t === "name") {
        if (["for", "in", "if", "elif", "else", "and", "or", "not"].includes(t.v)) {
          throw new CodeError(`「${t.v}」の 使い方が おかしいよ`, line);
        }
        return { k: "name", v: t.v };
      }
      if (t.v === "(") {
        const e = or();
        expect(")", "かっこ「)」が とじていないよ");
        return e;
      }
      if (t.v === "[") {
        const items = [];
        if (!isOp("]")) {
          for (;;) {
            items.push(or());
            if (isOp(",")) { p++; continue; }
            break;
          }
        }
        expect("]", "「]」が たりないよ");
        return { k: "list", items };
      }
      throw new CodeError(`「${t.v}」が おかしな場所にあるよ`, line);
    }

    const e = or();
    if (p < toks.length) {
      const t = toks[p];
      throw new CodeError(t.v === ")" ? "かっこ「)」が 多すぎるよ" : `「${t.v}」の あたりの書き方が おかしいよ`, line);
    }
    return e;
  }

  // ---------------- 文の読みとり（字下げでブロックを作る） ----------------
  function parse(src) {
    const lines = [];
    String(src).replace(/\t/g, "    ").split("\n").forEach((raw, i) => {
      const text = raw.replace(/\s+$/, "");
      if (!text.trim() || text.trim().startsWith("#")) return;
      if (/^　/.test(text)) throw new CodeError("行のはじめに 全角スペースが入っているよ。半角スペースにしてね", i + 1);
      lines.push({ indent: text.length - text.trimStart().length, text: text.trim(), line: i + 1 });
    });
    if (lines.length && lines[0].indent > 0) throw new CodeError("さいしょの行は 字下げ（スペース）なしで書いてね", lines[0].line);
    let pos = 0;

    function headerExpr(L, toks, from) {
      const last = toks[toks.length - 1];
      if (!last || last.v !== ":") throw new CodeError("行のさいごに「:」（コロン）が たりないよ", L.line);
      if (toks.length - 1 <= from) throw new CodeError("条件（じょうけん）が 書かれていないよ", L.line);
      return parseExpr(toks.slice(from, -1), L.line);
    }

    function body(L, indent) {
      if (pos >= lines.length || lines[pos].indent <= indent) {
        throw new CodeError("「:」の つぎの行は、スペース4つぶん 字下げしてね", L.line);
      }
      return block(lines[pos].indent);
    }

    function ifChain(L, toks, indent) {
      const st = { type: "if", line: L.line, cond: headerExpr(L, toks, 1) };
      st.body = body(L, indent);
      const nx = lines[pos];
      if (nx && nx.indent === indent && /^elif\b/.test(nx.text)) {
        pos++;
        st.orelse = [ifChain(nx, tokenize(nx.text, nx.line), indent)];
      } else if (nx && nx.indent === indent && /^else\s*:?$/.test(nx.text)) {
        pos++;
        if (!nx.text.endsWith(":")) throw new CodeError("else の うしろに「:」が たりないよ", nx.line);
        st.orelse = body(nx, indent);
      }
      st.endLine = lines[pos - 1].line;
      return st;
    }

    function statement(L, indent) {
      const toks = tokenize(L.text, L.line);
      const first = toks[0];
      if (!first) return { type: "pass", line: L.line, endLine: L.line };
      const word = first.t === "name" ? first.v : "";
      if (word === "for") {
        if (!toks[1] || toks[1].t !== "name" || !toks[2] || toks[2].v !== "in") {
          throw new CodeError("for は「for i in range(3):」のように書いてね", L.line);
        }
        const st = { type: "for", line: L.line, name: toks[1].v, iter: headerExpr(L, toks, 3) };
        st.body = body(L, indent);
        st.endLine = lines[pos - 1].line;
        return st;
      }
      if (word === "if") return ifChain(L, toks, indent);
      if (word === "elif" || word === "else") throw new CodeError(`${word} の まえに if が ないよ（字下げも そろえてね）`, L.line);
      if (word === "while") throw new CodeError("while は まだ使えないよ。for を使ってね", L.line);
      if (word === "def") throw new CodeError("def（自分の関数づくり）は まだ使えないよ", L.line);
      if (word === "pass") return { type: "pass", line: L.line, endLine: L.line };
      if (toks.length && toks[toks.length - 1].v === ":") throw new CodeError("「:」は for や if の行の さいごに だけ つけるよ", L.line);
      if (first.t === "name" && toks[1] && ["=", "+=", "-=", "*="].includes(toks[1].v)) {
        if (KEYWORDS.includes(first.v) || FUNCS.includes(first.v)) {
          throw new CodeError(`「${first.v}」は 変数の名前に できないよ`, L.line);
        }
        if (toks.length < 3) throw new CodeError("= の右がわに 値（あたい）を書いてね", L.line);
        return { type: "assign", line: L.line, endLine: L.line, name: first.v, op: toks[1].v, expr: parseExpr(toks.slice(2), L.line) };
      }
      return { type: "expr", line: L.line, endLine: L.line, expr: parseExpr(toks, L.line) };
    }

    function block(indent) {
      const out = [];
      while (pos < lines.length) {
        const L = lines[pos];
        if (L.indent < indent) break;
        if (L.indent > indent) throw new CodeError("字下げ（インデント）が ずれているよ", L.line);
        pos++;
        out.push(statement(L, indent));
      }
      return out;
    }

    const stmts = block(0);
    if (pos < lines.length) throw new CodeError("字下げ（インデント）が ずれているよ", lines[pos].line);
    return stmts;
  }

  // ---------------- 実行 ----------------
  function distance(a, b) {
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i]);
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) {
      for (let j = 1; j <= b.length; j++) {
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      }
    }
    return d[a.length][b.length];
  }

  function suggest(name, choices) {
    let best = null, bestD = 3;
    for (const c of choices) {
      const d = distance(name.toLowerCase(), c.toLowerCase());
      if (d < bestD) { best = c; bestD = d; }
    }
    return best ? `（もしかして「${best}」？）` : "";
  }

  function show(v) {
    if (v === true) return "True";
    if (v === false) return "False";
    if (v === null || v === undefined) return "None";
    if (Array.isArray(v)) return "[" + v.map((x) => (typeof x === "string" ? `'${x}'` : show(x))).join(", ") + "]";
    return String(v);
  }

  // world: { cols, rows, x, y, dir, cells:{}, stars:Set, pen }
  function makeWorld(o) {
    return {
      cols: o.cols, rows: o.rows, x: o.x, y: o.y, dir: o.dir === undefined ? 1 : o.dir,
      cells: { ...(o.cells || {}) }, stars: new Set(o.stars || []), pen: null, got: 0,
    };
  }

  class Runner {
    constructor(world, opts = {}) {
      this.w = world;
      this.walls = opts.walls !== false;
      this.env = {};
      this.actions = [];
      this.moveEnds = [];
      this.steps = 0;
    }

    // stmts を実行して、画面で再生する「動き」のリストを返す（エラーも動きの1つとして入る）
    run(stmts) {
      const start = this.actions.length;
      try {
        this.block(stmts);
      } catch (e) {
        if (!(e instanceof CodeError)) throw e;
        this.actions.push({ kind: "error", msg: e.message, line: e.line });
        this.failed = true;
      }
      return this.actions.slice(start);
    }

    tick(line) {
      if (++this.steps > 5000) throw new CodeError("くりかえしが 多すぎるよ（5000回まで）", line);
    }

    block(stmts) {
      for (const st of stmts) this.stmt(st);
    }

    stmt(st) {
      this.tick(st.line);
      this.line = st.line;
      if (st.type === "pass") return;
      if (st.type === "expr") { this.eval(st.expr, st.line); return; }
      if (st.type === "assign") {
        const v = this.eval(st.expr, st.line);
        if (st.op === "=") this.env[st.name] = v;
        else {
          if (!(st.name in this.env)) throw new CodeError(`「${st.name}」は まだ作っていない変数だよ`, st.line);
          const op = st.op[0];
          this.env[st.name] = this.binary(op, this.env[st.name], v, st.line);
        }
        this.actions.push({ kind: "var", line: st.line, name: st.name, value: show(this.env[st.name]) });
        return;
      }
      if (st.type === "for") {
        const items = this.eval(st.iter, st.line);
        if (!Array.isArray(items) && typeof items !== "string") {
          throw new CodeError("for の in の うしろは range(3) や リスト にしてね", st.line);
        }
        for (const x of items) {
          this.tick(st.line);
          this.env[st.name] = x;
          this.actions.push({ kind: "var", line: st.line, name: st.name, value: show(x) });
          this.block(st.body);
        }
        return;
      }
      if (st.type === "if") {
        const ok = this.truthy(this.eval(st.cond, st.line));
        this.actions.push({ kind: "check", line: st.line, ok });
        if (ok) this.block(st.body);
        else if (st.orelse) this.block(st.orelse);
      }
    }

    truthy(v) {
      if (Array.isArray(v) || typeof v === "string") return v.length > 0;
      return !!v;
    }

    binary(op, a, b, line) {
      const num = (x) => typeof x === "number";
      switch (op) {
        case "+":
          if (num(a) && num(b)) return a + b;
          if (typeof a === "string" && typeof b === "string") return a + b;
          if (Array.isArray(a) && Array.isArray(b)) return a.concat(b);
          throw new CodeError("文字と数字は + で つなげられないよ。str(数字) を使ってね", line);
        case "*":
          if (num(a) && num(b)) return a * b;
          if (typeof a === "string" && num(b)) return a.repeat(Math.max(0, b));
          throw new CodeError("* は 数字どうしで使ってね", line);
        case "-": case "/": case "//": case "%":
          if (!num(a) || !num(b)) throw new CodeError(`${op} は 数字どうしで使ってね`, line);
          if ((op !== "-") && b === 0) throw new CodeError("0 で わることは できないよ", line);
          if (op === "-") return a - b;
          if (op === "/") return a / b;
          if (op === "//") return Math.floor(a / b);
          return ((a % b) + b) % b;
        case "==": return show(a) === show(b) && typeof a === typeof b;
        case "!=": return !(show(a) === show(b) && typeof a === typeof b);
        case "<": return a < b;
        case ">": return a > b;
        case "<=": return a <= b;
        case ">=": return a >= b;
        default: throw new CodeError(`「${op}」は 使えないよ`, line);
      }
    }

    eval(e, line) {
      switch (e.k) {
        case "num": case "str": return e.v;
        case "list": return e.items.map((x) => this.eval(x, line));
        case "name":
          if (e.v === "True") return true;
          if (e.v === "False") return false;
          if (e.v in this.env) return this.env[e.v];
          if (FUNCS.includes(e.v)) throw new CodeError(`${e.v} は命令だよ。うしろに () をつけてね → ${e.v}()`, line);
          throw new CodeError(`「${e.v}」は まだ作っていない名前だよ${suggest(e.v, Object.keys(this.env).concat(FUNCS))}`, line);
        case "un": {
          const v = this.eval(e.a, line);
          if (e.op === "not") return !this.truthy(v);
          if (typeof v !== "number") throw new CodeError("- は 数字に つけてね", line);
          return -v;
        }
        case "bin": {
          if (e.op === "and") { const a = this.eval(e.a, line); return this.truthy(a) ? this.eval(e.b, line) : a; }
          if (e.op === "or") { const a = this.eval(e.a, line); return this.truthy(a) ? a : this.eval(e.b, line); }
          return this.binary(e.op, this.eval(e.a, line), this.eval(e.b, line), line);
        }
        case "idx": {
          const a = this.eval(e.a, line), i = this.eval(e.i, line);
          if (!Array.isArray(a) && typeof a !== "string") throw new CodeError("[ ] は リストや文字に使ってね", line);
          if (typeof i !== "number" || !Number.isInteger(i)) throw new CodeError("[ ] の中は 整数（せいすう）にしてね", line);
          const v = a[i < 0 ? a.length + i : i];
          if (v === undefined) throw new CodeError(`${i}番目は ないよ（0から ${a.length - 1}まで）`, line);
          return v;
        }
        case "call": return this.call(e.name, e.args.map((x) => this.eval(x, line)), line);
        default: throw new CodeError("よくわからない書き方だよ", line);
      }
    }

    color(c, line) {
      if (typeof c !== "string") throw new CodeError('色は "red" のように " " で はさんで書いてね', line);
      const v = COLORS[c] || COLORS[c.toLowerCase()];
      if (!v) throw new CodeError(`「${c}」という色は ないよ。red, blue, green, yellow, orange, purple, pink などが使えるよ`, line);
      return v;
    }

    count(n, line, name) {
      if (n === undefined) return 1;
      if (typeof n !== "number" || !Number.isInteger(n) || n < 0) throw new CodeError(`${name}() の () には 0 いじょうの整数を入れてね`, line);
      if (n > 50) throw new CodeError(`${name}() は 50 までにしてね`, line);
      return n;
    }

    call(name, args, line) {
      const w = this.w;
      const need = (min, max) => {
        if (args.length < min || args.length > max) {
          const how = min === max ? `${min}こ` : `${min}〜${max}こ`;
          throw new CodeError(`${name}() の () の中は ${how} だよ`, line);
        }
      };
      switch (name) {
        case "move": {
          need(0, 1);
          const n = this.count(args[0], line, "move");
          for (let i = 0; i < n; i++) {
            const [dx, dy] = DIRS[w.dir];
            const nx = w.x + dx, ny = w.y + dy;
            if (this.walls && (nx < 0 || ny < 0 || nx >= w.cols || ny >= w.rows)) {
              throw new CodeError("ゴツン！ かべに ぶつかっちゃった。すすむ数を へらしてみよう", line);
            }
            w.x = nx;
            w.y = ny;
            this.tick(line);
            const key = nx + "," + ny;
            let star = false;
            if (w.stars.has(key)) { w.stars.delete(key); w.got++; star = true; }
            if (w.pen) w.cells[key] = w.pen;
            this.actions.push({ kind: "move", line, x: nx, y: ny, star, paint: w.pen });
          }
          this.moveEnds.push([w.x, w.y]);
          return null;
        }
        case "turn_left": case "turn_right":
          need(0, 0);
          w.dir = (w.dir + (name === "turn_left" ? 3 : 1)) % 4;
          this.actions.push({ kind: "turn", line, dir: w.dir, delta: name === "turn_left" ? -1 : 1 });
          return null;
        case "paint": {
          need(0, 1);
          const c = this.color(args.length ? args[0] : "yellow", line);
          w.cells[w.x + "," + w.y] = c;
          this.actions.push({ kind: "paint", line, x: w.x, y: w.y, color: c });
          return null;
        }
        case "pen":
          need(0, 1);
          w.pen = this.color(args.length ? args[0] : "yellow", line);
          w.cells[w.x + "," + w.y] = w.pen;
          this.actions.push({ kind: "paint", line, x: w.x, y: w.y, color: w.pen });
          return null;
        case "pen_up":
          need(0, 0);
          w.pen = null;
          this.actions.push({ kind: "note", line });
          return null;
        case "say":
          need(1, 1);
          this.actions.push({ kind: "say", line, text: show(args[0]) });
          return null;
        case "print":
          this.actions.push({ kind: "print", line, text: args.map(show).join(" ") });
          return null;
        case "range": {
          need(1, 3);
          if (!args.every((a) => Number.isInteger(a))) throw new CodeError("range() の中は 整数にしてね", line);
          const [a, b, s] = args.length === 1 ? [0, args[0], 1] : [args[0], args[1], args[2] || 1];
          if (s === 0) throw new CodeError("range() の 3つめに 0 は使えないよ", line);
          const out = [];
          for (let i = a; s > 0 ? i < b : i > b; i += s) {
            out.push(i);
            if (out.length > 5000) throw new CodeError("range() が 大きすぎるよ", line);
          }
          return out;
        }
        case "str": need(1, 1); return show(args[0]);
        case "int": {
          need(1, 1);
          const v = typeof args[0] === "string" ? Number(args[0]) : args[0];
          if (typeof v !== "number" || Number.isNaN(v)) throw new CodeError("int() で 数字に できなかったよ", line);
          return Math.trunc(v);
        }
        case "len":
          need(1, 1);
          if (!Array.isArray(args[0]) && typeof args[0] !== "string") throw new CodeError("len() は リストや文字に使ってね", line);
          return args[0].length;
        case "randint":
          need(2, 2);
          if (!Number.isInteger(args[0]) || !Number.isInteger(args[1]) || args[0] > args[1]) {
            throw new CodeError("randint(1, 6) のように 小さい数・大きい数の順で書いてね", line);
          }
          return args[0] + Math.floor(Math.random() * (args[1] - args[0] + 1));
        default:
          throw new CodeError(`「${name}」という命令は ないよ${suggest(name, FUNCS)}`, line);
      }
    }
  }

  return { parse, Runner, makeWorld, CodeError, COLORS, FUNCS, KEYWORDS };
})();

if (typeof globalThis !== "undefined") globalThis.Robo = Robo;
