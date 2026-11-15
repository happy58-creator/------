/* 画面の部品：効果音・キーボード表示・ちょっとした便利関数。 */
const UI = (() => {
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const store = {
    get(key, fallback) {
      try {
        const v = localStorage.getItem(key);
        return v === null ? fallback : JSON.parse(v);
      } catch (e) {
        return fallback;
      }
    },
    set(key, value) {
      try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* 保存できなくても遊べる */ }
    },
  };

  const fmtTime = (sec) => `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, "0")}`;

  // ---------------- 効果音 ----------------
  let audio = null;
  const sound = { on: store.get("kyouzai-sound", true) };
  function tone(freq, dur, type = "sine", vol = 0.1, delay = 0) {
    if (!sound.on) return;
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
    key: () => tone(1400, 0.025, "square", 0.02),
    miss: () => tone(130, 0.16, "sawtooth", 0.06),
    clear: () => [784, 1047].forEach((f, i) => tone(f, 0.12, "triangle", 0.1, i * 0.07)),
    count: () => tone(660, 0.12, "triangle", 0.12),
    go: () => tone(1047, 0.25, "triangle", 0.12),
    finish: () => [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, 0.2, "triangle", 0.11, i * 0.1)),
    step: () => tone(520, 0.05, "triangle", 0.06),
    star: () => [988, 1319].forEach((f, i) => tone(f, 0.12, "triangle", 0.1, i * 0.06)),
    error: () => [300, 200].forEach((f, i) => tone(f, 0.18, "square", 0.05, i * 0.15)),
  };
  function toggleSound() {
    sound.on = !sound.on;
    store.set("kyouzai-sound", sound.on);
    return sound.on;
  }

  // ---------------- キーボード ----------------
  const LAYOUTS = {
    jis: {
      label: "日本語キーボード",
      rows: [
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "^", "¥"],
        ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "@", "["],
        ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";", ":", "]"],
        ["z", "x", "c", "v", "b", "n", "m", ",", ".", "/", "\\"],
      ],
      shift: {
        "!": "1", '"': "2", "#": "3", $: "4", "%": "5", "&": "6", "'": "7", "(": "8", ")": "9",
        "=": "-", "~": "^", "|": "¥", "`": "@", "{": "[", "+": ";", "*": ":", "}": "]",
        "<": ",", ">": ".", "?": "/", _: "\\",
      },
    },
    us: {
      label: "英語キーボード",
      rows: [
        ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "="],
        ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "[", "]", "\\"],
        ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";", "'"],
        ["z", "x", "c", "v", "b", "n", "m", ",", ".", "/"],
      ],
      shift: {
        "~": "`", "!": "1", "@": "2", "#": "3", $: "4", "%": "5", "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
        _: "-", "+": "=", "{": "[", "}": "]", "|": "\\", ":": ";", '"': "'", "<": ",", ">": ".", "?": "/",
      },
    },
  };
  const FINGER = {};
  [["`1qaz", "lp"], ["2wsx", "lr"], ["3edc", "lm"], ["45rtfgvb", "li"], ["67yuhjnm", "ri"], ["8ik,", "rm"], ["9ol.", "rr"]]
    .forEach(([keys, f]) => { for (const k of keys) FINGER[k] = f; });
  const FINGER_NAME = {
    lp: "ひだり小ゆび", lr: "ひだり薬ゆび", lm: "ひだり中ゆび", li: "ひだり人さしゆび",
    ri: "みぎ人さしゆび", rm: "みぎ中ゆび", rr: "みぎ薬ゆび", rp: "みぎ小ゆび", th: "おやゆび",
  };
  const fingerOf = (k) => (k === "space" ? "th" : FINGER[k] || "rp");
  const ROW_INDENT = [0, 1.5, 1.8, 0];

  class Keyboard {
    constructor(el) {
      this.el = el;
      this.layout = store.get("kyouzai-kb", "jis") === "us" ? "us" : "jis";
      this.current = null;
      this.draw();
    }

    draw() {
      const L = LAYOUTS[this.layout];
      const shiftOf = {};
      for (const [ch, base] of Object.entries(L.shift)) if (!/[A-Z]/.test(ch)) shiftOf[base] = ch;
      const key = (k) => {
        const top = shiftOf[k] && !/[a-z]/.test(k) ? `<small>${esc(shiftOf[k])}</small>` : "";
        return `<div class="key f-${fingerOf(k)}" data-k="${esc(k)}">${top}<span>${esc(k.toUpperCase())}</span></div>`;
      };
      const rows = L.rows.map((row, i) => {
        let inner = row.map(key).join("");
        if (i === 2) inner += '<div class="key wide f-rp" data-k="enter"><span>Enter</span></div>';
        if (i === 3) inner = '<div class="key wide f-lp" data-k="shiftL"><span>Shift</span></div>' + inner +
          '<div class="key wide f-rp" data-k="shiftR"><span>Shift</span></div>';
        return `<div class="kb-row" style="padding-left:${ROW_INDENT[i] * 0.5}em">${inner}</div>`;
      });
      rows.push('<div class="kb-row"><div class="key space f-th" data-k="space"><span>スペース</span></div></div>');
      this.el.innerHTML = `<div class="kb">${rows.join("")}</div>
        <div class="kb-foot"><span class="finger" data-role="finger"></span>
        <select data-role="layout"><option value="jis">日本語キーボード</option><option value="us">英語キーボード</option></select></div>`;
      const sel = this.el.querySelector('[data-role="layout"]');
      sel.value = this.layout;
      sel.onchange = () => {
        this.layout = sel.value;
        store.set("kyouzai-kb", this.layout);
        this.draw();
        if (this.current !== null) this.show(this.current);
      };
    }

    // 文字 ch を打つには どのキー（と Shift）を押すか
    locate(ch) {
      const L = LAYOUTS[this.layout];
      if (ch === "\n") return { base: "enter", shift: false };
      if (ch === " ") return { base: "space", shift: false };
      if (/[A-Z]/.test(ch)) return { base: ch.toLowerCase(), shift: true };
      if (L.shift[ch]) return { base: L.shift[ch], shift: true };
      return { base: ch, shift: false };
    }

    show(ch) {
      this.current = ch;
      this.el.querySelectorAll(".key.next").forEach((k) => k.classList.remove("next"));
      const label = this.el.querySelector('[data-role="finger"]');
      if (ch === null || ch === undefined) { label.textContent = ""; return; }
      const { base, shift } = this.locate(ch);
      const keyEl = this.el.querySelector(`.key[data-k="${CSS.escape(base)}"]`);
      if (keyEl) keyEl.classList.add("next");
      const f = fingerOf(base);
      if (shift) {
        const side = f[0] === "l" ? "shiftR" : "shiftL";
        this.el.querySelector(`.key[data-k="${side}"]`).classList.add("next");
      }
      label.textContent = `👆 ${FINGER_NAME[f]}` + (shift ? " ＋ 反対の手でShift" : "");
    }

    flash(ch, ok) {
      const { base } = this.locate(ch);
      const keyEl = this.el.querySelector(`.key[data-k="${CSS.escape(base)}"]`);
      if (!keyEl) return;
      const cls = ok ? "hit" : "bad";
      keyEl.classList.remove(cls);
      void keyEl.offsetWidth; // アニメーションをやり直す
      keyEl.classList.add(cls);
    }

    // 記号の打ち方の説明（「( は Shift ＋ 8」など）
    hint(ch) {
      if (ch === "\n") return "行のおわり：<b>Enter（エンター）</b>キーで次の行へ";
      if (ch === " ") return "<b>スペース</b>キー";
      const { base, shift } = this.locate(ch);
      if (!shift) return `<b>${esc(ch)}</b> のキー`;
      return `<b>${esc(ch)}</b> は <b>Shift ＋ ${esc(base.toUpperCase())}</b>（${LAYOUTS[this.layout].label}）`;
    }
  }

  // Streamlit のページ側でなく、この画面にキー入力が来ているか
  function watchFocus(onBlur, onFocus) {
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", onFocus);
  }

  return { esc, store, fmtTime, sfx, sound, toggleSound, Keyboard, watchFocus };
})();
