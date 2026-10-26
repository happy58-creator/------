/* ひらがな → ローマ字の判定。「si / shi」「tu / tsu」など、どの打ち方でも正解にする。 */
const Kana = (() => {
  // 1文字ずつの打ち方（先頭が画面に出すおすすめの打ち方）
  const SINGLE = {
    あ: ["a"], い: ["i", "yi"], う: ["u", "wu", "whu"], え: ["e"], お: ["o"],
    か: ["ka", "ca"], き: ["ki"], く: ["ku", "cu", "qu"], け: ["ke"], こ: ["ko", "co"],
    さ: ["sa"], し: ["si", "shi", "ci"], す: ["su"], せ: ["se", "ce"], そ: ["so"],
    た: ["ta"], ち: ["ti", "chi"], つ: ["tu", "tsu"], て: ["te"], と: ["to"],
    な: ["na"], に: ["ni"], ぬ: ["nu"], ね: ["ne"], の: ["no"],
    は: ["ha"], ひ: ["hi"], ふ: ["hu", "fu"], へ: ["he"], ほ: ["ho"],
    ま: ["ma"], み: ["mi"], む: ["mu"], め: ["me"], も: ["mo"],
    や: ["ya"], ゆ: ["yu"], よ: ["yo"],
    ら: ["ra"], り: ["ri"], る: ["ru"], れ: ["re"], ろ: ["ro"],
    わ: ["wa"], ゐ: ["wi"], ゑ: ["we"], を: ["wo"],
    が: ["ga"], ぎ: ["gi"], ぐ: ["gu"], げ: ["ge"], ご: ["go"],
    ざ: ["za"], じ: ["zi", "ji"], ず: ["zu"], ぜ: ["ze"], ぞ: ["zo"],
    だ: ["da"], ぢ: ["di"], づ: ["du"], で: ["de"], ど: ["do"],
    ば: ["ba"], び: ["bi"], ぶ: ["bu"], べ: ["be"], ぼ: ["bo"],
    ぱ: ["pa"], ぴ: ["pi"], ぷ: ["pu"], ぺ: ["pe"], ぽ: ["po"],
    ゔ: ["vu"],
    ぁ: ["xa", "la"], ぃ: ["xi", "li"], ぅ: ["xu", "lu"], ぇ: ["xe", "le"], ぉ: ["xo", "lo"],
    ゃ: ["xya", "lya"], ゅ: ["xyu", "lyu"], ょ: ["xyo", "lyo"], ゎ: ["xwa", "lwa"],
    っ: ["xtu", "ltu", "xtsu", "ltsu"],
    ー: ["-"], "、": [","], "。": ["."], "！": ["!"], "？": ["?"], "「": ["["], "」": ["]"],
    "・": ["/"], "〜": ["~"], "～": ["~"],
  };
  // 「き」+「ゃ」→ kya のような組み合わせ
  const YOON_HEAD = {
    き: ["ky"], ぎ: ["gy"], し: ["sy", "sh"], じ: ["zy", "j", "jy"], ち: ["ty", "ch", "cy"], ぢ: ["dy"],
    に: ["ny"], ひ: ["hy"], び: ["by"], ぴ: ["py"], み: ["my"], り: ["ry"],
  };
  const SMALL_VOWEL = { ゃ: "a", ぃ: "i", ゅ: "u", ぇ: "e", ょ: "o" };
  const SPECIAL = {
    ふぁ: ["fa"], ふぃ: ["fi"], ふぇ: ["fe"], ふぉ: ["fo"], ふゅ: ["fyu"],
    てぃ: ["thi"], でぃ: ["dhi"], でゅ: ["dhu"], とぅ: ["twu"], どぅ: ["dwu"],
    うぃ: ["wi"], うぇ: ["we"], うぉ: ["who"], ゔぁ: ["va"], ゔぃ: ["vi"], ゔぇ: ["ve"], ゔぉ: ["vo"],
    つぁ: ["tsa"],
  };
  const ASCII = /^[a-z0-9\-.,!?'"()\[\]:;\/+*=_#&%$@~ ]$/;

  const uniq = (a) => [...new Set(a)];

  function toHiragana(s) {
    return s
      .replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60))
      .replace(/[！-～]/g, (c) => {
        const half = String.fromCharCode(c.charCodeAt(0) - 0xfee0);
        return SINGLE[c] ? c : half; // ！？は日本語の記号として残す
      })
      .replace(/　/g, " ");
  }

  function pairOptions(a, b) {
    const opts = [];
    if (SPECIAL[a + b]) opts.push(...SPECIAL[a + b]);
    if (YOON_HEAD[a] && SMALL_VOWEL[b]) {
      const v = SMALL_VOWEL[b];
      for (const head of YOON_HEAD[a]) {
        if (!head.endsWith("y") && v === "i") continue; // shi や ji は「し」「じ」と同じになるので使わない
        opts.push(head + v);
      }
    }
    if (!opts.length) return null;
    for (const x of SINGLE[a] || []) for (const y of SINGLE[b] || []) opts.push(x + y);
    return uniq(opts);
  }

  // 文章を「打つかたまり」の列にする。変換できない文字（漢字など）があれば null。
  function buildUnits(text) {
    const s = toHiragana(String(text || "")).toLowerCase();
    const units = [];
    for (let i = 0; i < s.length; i++) {
      const c = s[i];
      if (c === " ") continue;
      const pair = i + 1 < s.length ? pairOptions(c, s[i + 1]) : null;
      if (pair) {
        units.push({ kana: c + s[i + 1], opts: pair, end: i + 2 });
        i++;
      } else if (c === "ん") {
        units.push({ kana: c, opts: ["nn", "xn", "n'"], n: true, end: i + 1 });
      } else if (SINGLE[c]) {
        units.push({ kana: c, opts: SINGLE[c].slice(), end: i + 1 });
      } else if (ASCII.test(c)) {
        units.push({ kana: c, opts: [c], end: i + 1 });
      } else {
        return null;
      }
    }
    // 「っ」は つぎの文字の子音を2回打つ（kka）か、xtu / ltu で打つ
    const out = [];
    for (let j = 0; j < units.length; j++) {
      const u = units[j], nx = units[j + 1];
      if (u.kana === "っ" && nx && !nx.n && nx.kana !== "っ") {
        const opts = [];
        for (const o of nx.opts) if (/^[bcdfghjkmpqrstvwyz]/.test(o)) opts.push(o[0] + o);
        for (const a of u.opts) for (const o of nx.opts) opts.push(a + o);
        out.push({ kana: u.kana + nx.kana, opts: uniq(opts), end: nx.end });
        j++;
      } else {
        out.push(u);
      }
    }
    return out;
  }

  // AI がくれたローマ字をそのまま使う（漢字がまざっていたとき用）
  function unitsFromRomaji(romaji) {
    return String(romaji || "").toLowerCase().replace(/\s+/g, "").split("")
      .map((c) => ({ kana: c, opts: [c] }));
  }

  class Matcher {
    constructor(units) {
      this.units = units;
      this.idx = 0;
      this.buf = "";
      this.typed = [];
    }

    get done() {
      return this.idx >= this.units.length;
    }

    // 1キー入力。正しければ true。
    input(k) {
      if (this.done) return false;
      const u = this.units[this.idx];
      const next = this.buf + k;
      const cands = u.opts.filter((o) => o.startsWith(next));
      if (cands.length) {
        this.buf = next;
        if (cands.includes(next) && !cands.some((o) => o.length > next.length)) this.finishUnit();
        return true;
      }
      // 「ん」は、つぎが子音なら n 1回でもOK（nyu などと区別できるとき）
      const nx = this.units[this.idx + 1];
      if (u.n && this.buf === "n" && nx && !"aiueoyn'".includes(k) && nx.opts.some((o) => o.startsWith(k))) {
        this.finishUnit();
        return this.input(k);
      }
      // ほかの打ち方の途中でも、もう1つの打ち方が完成していれば次へ
      if (u.opts.includes(this.buf)) {
        this.finishUnit();
        return this.input(k);
      }
      return false;
    }

    finishUnit() {
      this.typed[this.idx] = this.buf;
      this.idx++;
      this.buf = "";
    }

    guideFor(i) {
      const u = this.units[i], nx = this.units[i + 1];
      if (u.n && this.buf === "") {
        const single = nx && !"aiueoyn".includes(nx.opts[0][0]);
        return single ? "n" : "nn";
      }
      return u.opts[0];
    }

    // 画面に出すローマ字：[打った部分, のこり]
    guide() {
      let done = this.typed.slice(0, this.idx).join("") + this.buf;
      let rest = "";
      if (!this.done) {
        const u = this.units[this.idx];
        const cur = this.buf ? u.opts.find((o) => o.startsWith(this.buf)) : this.guideFor(this.idx);
        rest = cur.slice(this.buf.length);
        for (let i = this.idx + 1; i < this.units.length; i++) {
          const v = this.units[i], nx = this.units[i + 1];
          rest += v.n ? (nx && !"aiueoyn".includes(nx.opts[0][0]) ? "n" : "nn") : v.opts[0];
        }
      }
      return [done, rest];
    }

    // もとの文章の何文字目まで打ち終わったか（漢字まじりでローマ字から作ったときは -1）
    kanaProgress() {
      if (this.units.length && this.units[0].end === undefined) return -1;
      return this.idx ? this.units[this.idx - 1].end : 0;
    }
  }

  return { buildUnits, unitsFromRomaji, Matcher, toHiragana };
})();

if (typeof globalThis !== "undefined") globalThis.Kana = Kana;
