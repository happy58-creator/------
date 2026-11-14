/* 学習ページ共通の小物（計算・英語・プログラミング・漢字・タイピング・国語で同じもの。直すときは全部のフォルダの kit.js を直す） */
"use strict";
const Kit = (() => {
  const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // Python へのたのみごと（nonce つき）。返事（args.reply）が来たら then を呼ぶ
  const waits = {};
  let lastReply = "";
  function ask(v, then) { const nonce = uid(); if (then) waits[nonce] = then; Streamlit.setValue({ ...v, nonce }); return nonce; }
  function takeReply(args) {
    const r = args && args.reply;
    if (r && r.nonce && r.nonce !== lastReply) { lastReply = r.nonce; const f = waits[r.nonce]; delete waits[r.nonce]; if (f) f(r); }
  }
  // 画面（iframe）は縦に長いので、いま見えている所の上の位置
  function visTop() { try { const r = window.frameElement.getBoundingClientRect(); return Math.max(0, -r.top); } catch (e) { return 0; } }
  function visHeight() { try { return window.parent.innerHeight || 700; } catch (e) { return 700; } }
  function top() { window.scrollTo(0, 0); try { window.frameElement && window.frameElement.scrollIntoView({ block: "start" }); } catch (e) {} }
  function placeToast() { document.documentElement.style.setProperty("--tt", visTop() + 10 + "px"); }
  // 表彰状（PDF）：トップの画面のビューアで開く（common.py の「PDFを見る」と同じしくみ）
  function openPdf(b64) {
    try {
      const doc = window.parent.document, b = doc.createElement("button");
      b.dataset.pdf = b64; b.style.display = "none"; doc.body.appendChild(b); b.click(); b.remove();
    } catch (e) {
      const bin = atob(b64), bytes = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      window.open(URL.createObjectURL(new Blob([bytes], { type: "application/pdf" })), "_blank");
    }
  }
  function party() {
    const box = document.createElement("div"); box.className = "party";
    box.style.top = visTop() + "px"; box.style.height = visHeight() + "px";
    for (let k = 0; k < 40; k++) { const i = document.createElement("i"); i.style.left = Math.random() * 100 + "%"; i.style.animationDelay = Math.random() * .6 + "s"; i.style.background = ["#f2b33d", "#e0577f", "#3a5bd9", "#2db56a", "#9b5de5"][k % 5]; box.appendChild(i); }
    document.body.appendChild(box); setTimeout(() => box.remove(), 2600);
  }
  const shuffle = a => { const b = [...a]; for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [b[i], b[j]] = [b[j], b[i]]; } return b; };
  const load = (k, d) => { try { return JSON.parse(sessionStorage.getItem(k) || "null") ?? d; } catch (e) { return d; } };
  const save = (k, v) => { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  return { uid, esc, ask, takeReply, visTop, visHeight, top, placeToast, openPdf, party, shuffle, load, save };
})();
