/* 声まわり（ブラウザの機能だけ。AIの回数は使わない）
   Voice.say：英語の読み上げ ／ Rec：録音（WAV）と音声認識をいっしょに ／ Match：お手本と、聞きとれたことばをくらべる */
"use strict";
const Voice = (() => {
  const ok = "speechSynthesis" in window;
  let voices = [];
  const load = () => { try { voices = speechSynthesis.getVoices() || []; } catch (e) { voices = []; } };
  if (ok) { load(); try { speechSynthesis.onvoiceschanged = load; } catch (e) {} }
  function pick() {
    const en = voices.filter(v => /^en[-_]US/i.test(v.lang));
    const pref = ["Samantha", "Google US English", "Ava", "Allison", "Alex", "Microsoft Aria", "Microsoft Jenny"];
    for (const p of pref) { const v = en.find(x => x.name.includes(p)); if (v) return v; }
    return en.find(v => v.localService) || en[0] || voices.find(v => /^en/i.test(v.lang)) || null;
  }
  function say(text, slow, onend) {
    if (!ok) { onend && onend(); return false; }
    try { speechSynthesis.cancel(); } catch (e) {}
    const u = new SpeechSynthesisUtterance(String(text || ""));
    u.lang = "en-US"; const v = pick(); if (v) u.voice = v;
    u.rate = slow ? 0.6 : 0.9; u.pitch = 1;
    u.onend = () => onend && onend(); u.onerror = () => onend && onend();
    speechSynthesis.speak(u);
    return true;
  }
  const stop = () => { try { speechSynthesis.cancel(); } catch (e) {} };
  return { ok, say, stop };
})();

const Rec = (() => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  const canRec = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && (window.AudioContext || window.webkitAudioContext));
  let stream = null, ctx = null, src = null, node = null, chunks = [], r = null, on = false, timer = 0;
  let said = "", alts = [], srErr = "", cb = {};
  async function mic() {
    if (stream && stream.getAudioTracks().some(t => t.readyState === "live")) return stream;
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } });
    return stream;
  }
  // 録音と聞きとりを はじめる。cb.text(いまの聞きとり) / cb.end(結果) を呼ぶ
  async function start(maxSec, callbacks) {
    cb = callbacks || {}; said = ""; alts = []; srErr = ""; chunks = [];
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();     // タップのすぐあとに作る（iPhone）
    try { await ctx.resume(); } catch (e) {}
    try { await mic(); } catch (e) { throw new Error("マイクが使えないよ。マイクの使用を「許可」してね"); }
    src = ctx.createMediaStreamSource(stream);
    node = ctx.createScriptProcessor(4096, 1, 1);
    node.onaudioprocess = e => { if (on) chunks.push(new Float32Array(e.inputBuffer.getChannelData(0))); };
    src.connect(node); node.connect(ctx.destination);
    on = true;
    if (SR) {
      try {
        r = new SR(); r.lang = "en-US"; r.interimResults = true; r.maxAlternatives = 3; r.continuous = false;
        r.onresult = e => {
          let fin = "", tmp = "", list = [];
          for (let i = 0; i < e.results.length; i++) {
            const res = e.results[i];
            if (res.isFinal) { fin += res[0].transcript + " "; for (let k = 0; k < res.length; k++) list.push(res[k].transcript); }
            else tmp += res[0].transcript + " ";
          }
          said = (fin + tmp).trim(); if (list.length) alts = list;
          cb.text && cb.text(said);
        };
        r.onerror = e => { srErr = e.error || "error"; };
        r.onend = () => { r = null; if (on) setTimeout(() => on && stop(), 350); };   // 話しおわったら自動でとめる
        r.start();
      } catch (e) { srErr = "start"; r = null; }
    }
    clearTimeout(timer); timer = setTimeout(() => on && stop(), maxSec * 1000);
  }
  function stop() {
    if (!on) return;
    on = false; clearTimeout(timer);
    try { r && r.stop(); } catch (e) {}
    try { src && src.disconnect(); node && node.disconnect(); } catch (e) {}
    const rate = ctx ? ctx.sampleRate : 48000;
    setTimeout(() => {                                    // 最後の聞きとり結果を すこし待つ
      const wav = toWav(chunks, rate);
      cb.end && cb.end({ said, alts: alts.length ? alts : (said ? [said] : []), srErr, wav: wav.b64, url: wav.url, sec: wav.sec });
    }, r ? 500 : 50);
  }
  function release() {                                    // おわったら マイクをはなす（音がもとの大きさにもどる）
    on = false; clearTimeout(timer);
    try { stream && stream.getTracks().forEach(t => t.stop()); } catch (e) {}
    stream = null;
  }
  // 16kHz・モノラル・16bit の WAV（AIに送る）。前後の無音はけずる
  function toWav(list, rate) {
    let n = 0; list.forEach(c => n += c.length);
    const all = new Float32Array(n); let o = 0; list.forEach(c => { all.set(c, o); o += c.length; });
    const th = 0.012; let a = 0, b = all.length - 1;
    while (a < all.length && Math.abs(all[a]) < th) a++;
    while (b > a && Math.abs(all[b]) < th) b--;
    a = Math.max(0, a - rate * 0.25 | 0); b = Math.min(all.length - 1, b + rate * 0.3 | 0);
    const cut = b > a ? all.subarray(a, b + 1) : new Float32Array(0);
    const out = 16000, step = rate / out, len = Math.floor(cut.length / step);
    const pcm = new Int16Array(len);
    for (let i = 0; i < len; i++) {
      const s0 = Math.floor(i * step), s1 = Math.min(cut.length, Math.floor((i + 1) * step));
      let sum = 0; for (let k = s0; k < s1; k++) sum += cut[k];
      const v = Math.max(-1, Math.min(1, sum / Math.max(1, s1 - s0)));
      pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
    }
    const buf = new ArrayBuffer(44 + pcm.length * 2), dv = new DataView(buf);
    const w = (p, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(p + i, s.charCodeAt(i)); };
    w(0, "RIFF"); dv.setUint32(4, 36 + pcm.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
    dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true); dv.setUint32(24, out, true);
    dv.setUint32(28, out * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true); w(36, "data"); dv.setUint32(40, pcm.length * 2, true);
    new Int16Array(buf, 44).set(pcm);
    const bytes = new Uint8Array(buf); let bin = "";
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    const sec = pcm.length / out;
    return { b64: sec > 0.2 ? btoa(bin) : "", url: sec > 0.2 ? URL.createObjectURL(new Blob([buf], { type: "audio/wav" })) : "", sec };
  }
  return { hasSR: !!SR, canRec, start, stop, release, get on() { return on; } };
})();

const Match = (() => {
  const NUM = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"];
  const key = w => { let k = String(w).toLowerCase().replace(/[’‘`]/g, "'").replace(/[^a-z0-9']/g, "").replace(/'/g, ""); if (/^\d+$/.test(k) && +k <= 20) k = NUM[+k]; return k; };
  const words = s => String(s || "").split(/\s+/).filter(Boolean);
  // お手本の1語ずつに、言えたか（ok）をつける。いちばん合っている聞きとり結果をつかう
  function check(target, alts) {
    const T = words(target), tk = T.map(key);
    let best = { pct: -1, ok: tk.map(k => !k), said: "" };
    for (const s of (alts && alts.length ? alts : [""])) {
      const sk = words(s).map(key).filter(Boolean);
      const n = tk.length, m = sk.length, dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
      for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
        dp[i][j] = tk[i] && tk[i] === sk[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
      const ok = new Array(n).fill(false); let i = 0, j = 0;
      while (i < n && j < m) { if (tk[i] && tk[i] === sk[j]) { ok[i] = true; i++; j++; } else if (dp[i + 1][j] >= dp[i][j + 1]) i++; else j++; }
      tk.forEach((k, x) => { if (!k) ok[x] = true; });
      const real = tk.filter(Boolean).length || 1;
      const pct = Math.round(ok.filter((v, x) => v && tk[x]).length * 100 / real);
      if (pct > best.pct) best = { pct, ok, said: s };
    }
    return { pct: Math.max(0, best.pct), said: best.said, words: T.map((w, x) => ({ w, ok: best.ok[x] })) };
  }
  return { check };
})();
