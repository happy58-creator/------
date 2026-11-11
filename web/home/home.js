/* トップ画面の部品（JavaScript）。mode="footer"：下のメニュー（学習・ゲーム・カレンダー・記録・設定）／mode="calendar"：学習のカレンダー */
(() => {
  const app = document.getElementById("app");
  const nonce = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const ICON = {
    study: '<path d="M3 9.5 12 5l9 4.5-9 4.5-9-4.5Z"/><path d="M7 11.6V16c0 1.4 2.2 2.8 5 2.8s5-1.4 5-2.8v-4.4"/><path d="M21 9.5V15"/>',
    game: '<rect x="2.5" y="7" width="19" height="11" rx="5"/><path d="M7.5 10.5v4M5.5 12.5h4"/><circle cx="15.5" cy="11.5" r="1"/><circle cx="17.8" cy="13.8" r="1"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/><path d="M7.5 13.5h2M11 13.5h2M14.5 13.5h2M7.5 17h2M11 17h2"/>',
    record: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/>',
  };
  const svg = k => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICON[k]}</svg>`;

  // ---- 下のメニュー ----
  function footer(a) {
    const tabs = a.tabs || [];
    document.body.className = "is-footer";
    app.innerHTML = `<nav class="foot">${tabs.map(t => `<button data-k="${t.key}" class="${t.key === a.tab ? "on" : ""}">${svg(t.key)}<span>${esc(t.label)}</span></button>`).join("")}</nav>`;
    app.querySelectorAll("button").forEach(b => b.onclick = () => {
      if (b.classList.contains("on")) return;
      app.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b));
      Streamlit.setValue({ tab: b.dataset.k, nonce: nonce() });
    });
  }

  // ---- カレンダー ----
  // a.ym "2026-11"、a.days { "2026-11-12": [{ t: 教材の短い名前, n: 名前 }] }、a.admin、a.sel（えらんだ日）、a.today
  let cal = null;
  function calendar(a) {
    document.body.className = "is-cal";
    cal = { ...a };
    drawCal();
  }
  function drawCal() {
    const a = cal, [y, m] = a.ym.split("-").map(Number);
    const first = new Date(y, m - 1, 1), start = first.getDay(), days = new Date(y, m, 0).getDate();
    const cells = [];
    for (let i = 0; i < start; i++) cells.push(null);
    for (let d = 1; d <= days; d++) cells.push(d);
    while (cells.length % 7) cells.push(null);
    const pad = n => String(n).padStart(2, "0");
    const MAX = a.admin ? 2 : 3;
    const head = ["日", "月", "火", "水", "木", "金", "土"].map((w, i) => `<div class="wd ${i === 0 ? "sun" : i === 6 ? "sat" : ""}">${w}</div>`).join("");
    const body = cells.map((d, i) => {
      if (!d) return `<div class="cell empty"></div>`;
      const key = `${a.ym}-${pad(d)}`, list = a.days[key] || [], dow = i % 7;
      // 同じ日の同じもの（同じ人・同じ教材）は1つにまとめる
      const uniq = [], seen = new Set();
      for (const e of list) { const k = (a.admin ? e.n + "\u0000" : "") + e.t; if (!seen.has(k)) { seen.add(k); uniq.push(e); } }
      // 管理者：名前（小さく）と教材名を2行で。ふつう：教材名だけ
      const tags = uniq.slice(0, MAX).map(e => a.admin ? `<span class="ev two"><i>${esc(e.n)}</i>${esc(e.t)}</span>` : `<span class="ev">${esc(e.t)}</span>`).join("")
        + (uniq.length > MAX ? `<span class="more">+${uniq.length - MAX}</span>` : "");
      return `<button class="cell ${list.length ? "has" : ""} ${key === a.sel ? "sel" : ""} ${key === a.today ? "today" : ""} ${dow === 0 ? "sun" : dow === 6 ? "sat" : ""}" data-d="${key}"><b>${d}</b>${tags}</button>`;
    }).join("");
    const total = Object.values(a.days).reduce((s, l) => s + l.length, 0);
    app.innerHTML = `<div class="cal">
      <div class="cal-top"><button class="nav" data-m="-1">‹</button><div class="ym"><b>${y}年 ${m}月</b><small>${a.admin ? "みんなの記録" : "あなたの記録"}：${total}件</small></div><button class="nav" data-m="1">›</button></div>
      <div class="grid">${head}${body}</div>
      <div class="hint">日にちを押すと、その日の記録が下に出ます</div></div>`;
    app.querySelectorAll(".nav").forEach(b => b.onclick = () => {
      const d = new Date(y, m - 1 + Number(b.dataset.m), 1);
      Streamlit.setValue({ type: "month", ym: `${d.getFullYear()}-${pad(d.getMonth() + 1)}`, nonce: nonce() });
    });
    app.querySelectorAll(".cell[data-d]").forEach(b => b.onclick = () => {
      cal.sel = b.dataset.d; drawCal();
      Streamlit.setValue({ type: "day", date: b.dataset.d, nonce: nonce() });
    });
  }

  Streamlit.ready(a => (a.mode === "calendar" ? calendar : footer)(a));
})();
