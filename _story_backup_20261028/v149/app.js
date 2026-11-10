"use strict";
// 買い物リストの画面（Vue 3）。画面は 入力・一覧・店舗別・計算・メニュー。
// 教材アプリ（Streamlit）の部品として動く。データは Python から受けとり、保存の操作を Python に送る（家計簿と同じしくみ）。
// 押したらすぐ画面を変えて、保存は後ろで行う。
const { createApp, reactive, computed, nextTick, watch } = Vue;

// ---------- 小さな道具 ----------
const uid = () => Date.now().toString(36).slice(-6) + Math.random().toString(36).slice(2, 6);
const svg = (k, cls) => `<svg class="${cls || "li"}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${CAT_ICON[k] || CAT_ICON.box}</svg>`;
const iconKey = g => { const v = String((g && g["アイコン"]) || ""); return v.startsWith("i:") && CAT_ICON[v.slice(2)] ? v.slice(2) : "box"; };
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const yen = n => "¥" + Math.round(n).toLocaleString("ja-JP");
// 品名をそろえる（全角・半角、カタカナ・ひらがな、空白のちがいを無視）。「玉ねぎ」と「玉ネギ」は同じ
const normName = s => String(s || "").normalize("NFKC").toLowerCase().replace(/\s+/g, "").replace(/[\u30a1-\u30f6]/g, c => String.fromCharCode(c.charCodeAt(0) - 0x60));
// 2点の距離（m）
function meters(a, b) {
  const R = 6371000, r = x => x * Math.PI / 180;
  const dLat = r(b.lat - a.lat), dLng = r(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
const distText = m => m < 1000 ? `${Math.round(m / 10) * 10}m` : `${(m / 1000).toFixed(1)}km`;
const NEAR = 1000;      // 現在地から 1km 以内のお店
const MAYBE = 3000;     // 1km〜3km のお店は「もしかして？」に出す
// 住所から位置をさがす：国土地理院の住所検索（日本の住所に強い）→ 見つからなければ OpenStreetMap（お店の名前でも探せる）
async function geocode(q) {
  const out = [];
  try {
    const r = await fetch("https://msearch.gsi.go.jp/address-search/AddressSearch?q=" + encodeURIComponent(q));
    const j = await r.json();
    for (const f of (j || []).slice(0, 6)) out.push({ title: f.properties.title, lat: f.geometry.coordinates[1], lng: f.geometry.coordinates[0] });
  } catch (e) {}
  if (!out.length) {
    try {
      const r = await fetch("https://nominatim.openstreetmap.org/search?format=json&limit=6&countrycodes=jp&accept-language=ja&q=" + encodeURIComponent(q));
      const j = await r.json();
      for (const f of j || []) out.push({ title: f.display_name, lat: +f.lat, lng: +f.lon });
    } catch (e) {}
  }
  return out;
}
// 現在地をとる（携帯の位置情報）
function locate() {
  return new Promise((ok, ng) => {
    if (!navigator.geolocation) return ng(new Error("この端末では位置情報が使えません"));
    navigator.geolocation.getCurrentPosition(p => ok({ lat: p.coords.latitude, lng: p.coords.longitude, acc: p.coords.accuracy }),
      e => ng(new Error(e.code === 1 ? "位置情報の使用が許可されていません（設定で許可してください）" : "現在地がわかりませんでした")),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 });
  });
}
// 地図（Leaflet）は使うときだけ読む。vendor になければネットから
let leafletP = null;
function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (leafletP) return leafletP;
  const add = (tag, attrs) => new Promise((ok, ng) => { const el = document.createElement(tag); Object.assign(el, attrs); el.onload = ok; el.onerror = ng; document.head.appendChild(el); });
  const css = (href) => add("link", { rel: "stylesheet", href });
  leafletP = css("vendor/leaflet.css").catch(() => css("https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"))
    .then(() => add("script", { src: "vendor/leaflet.js" }).catch(() => add("script", { src: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js" })))
    .then(() => window.L);
  return leafletP;
}

// ---------- Streamlit とのやりとり（ライブラリなしで、決まった形のメッセージを送る） ----------
const SL = {
  send(type, extra) { window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type }, extra), "*"); },
  ready() { this.send("streamlit:componentReady", { apiVersion: 1 }); },
  height() { let h = 800; try { h = window.parent.innerHeight || h; } catch (e) {} this.send("streamlit:setFrameHeight", { height: h }); },
  value(v) { this.send("streamlit:setComponentValue", { value: JSON.parse(JSON.stringify(v)), dataType: "json" }); },   // Vue のデータは、ふつうのデータに写してから送る
};
// ログインの証明（家計簿と同じ置き場所。同じアプリなので家計簿と共通）
const TOKEN = {
  get() {
    let t = "";
    try { t = localStorage.getItem("kb_token") || ""; } catch (e) {}
    if (!t) { try { const m = window.parent.document.cookie.match(/(?:^|; )kb_token=([^;]+)/); if (m) t = decodeURIComponent(m[1]); } catch (e) {} }
    return t;
  },
  set(t) {
    if (!t) return;
    const left = Math.max(0, Math.floor(+t.split(".")[0] - Date.now() / 1000));
    try { localStorage.setItem("kb_token", t); } catch (e) {}
    try { window.parent.document.cookie = `kb_token=${encodeURIComponent(t)}; max-age=${left}; path=/; SameSite=Lax; Secure`; } catch (e) {}
  },
  clear() {
    try { localStorage.removeItem("kb_token"); } catch (e) {}
    try { window.parent.document.cookie = "kb_token=; max-age=0; path=/; SameSite=Lax; Secure"; } catch (e) {}
  },
};

// ===== キーボードが入力欄を隠さないように =====
// キーボードが出ると見える範囲がせまくなる（visualViewport）。フッターを隠して、入力中の欄が見える範囲に入るように画面を動かす
function keyboardHelper(getScroller) {
  const vv = () => { try { return window.parent.visualViewport || window.visualViewport; } catch (e) { return window.visualViewport; } };
  const typing = el => el && (el.tagName === "TEXTAREA" || (el.tagName === "INPUT" && !["date", "checkbox", "radio", "button", "submit"].includes(el.type)));
  function kbHeight() {          // 画面の下からキーボードの上までの高さ（キーボードが出ていなければ 0）
    const v = vv(); if (!v) return 0;
    return Math.max(0, Math.round(window.innerHeight - (v.offsetTop + v.height)));
  }
  function fit() {
    document.documentElement.style.setProperty("--kb", kbHeight() + "px");
    const el = document.activeElement, sc = getScroller();
    if (!typing(el) || !sc) return;
    const strip = document.querySelector(".gstrip"), stripH = strip ? strip.offsetHeight : 0;
    const v = vv(), top = (v ? v.offsetTop : 0) + 12, bottom = (v ? v.offsetTop + v.height : window.innerHeight) - 16 - stripH;
    const r = el.getBoundingClientRect();
    if (r.bottom > bottom) sc.scrollTop += r.bottom - bottom;
    else if (r.top < top) sc.scrollTop -= top - r.top;
  }
  let t1, t2;
  document.addEventListener("focusin", e => {
    if (!typing(e.target)) return;
    document.body.classList.add("kbd");
    clearTimeout(t1); clearTimeout(t2);
    t1 = setTimeout(fit, 320); t2 = setTimeout(fit, 650);        // キーボードが出おわるのを待つ
  });
  document.addEventListener("focusout", () => setTimeout(() => { if (!typing(document.activeElement)) { document.body.classList.remove("kbd"); document.documentElement.style.setProperty("--kb", kbHeight() + "px"); } }, 120));
  const v = vv();
  if (v) { v.addEventListener("resize", fit); v.addEventListener("scroll", fit); }
}

const FOOT = [["入力", "pencil", "input"], ["一覧", "list", "list"], ["店舗別", "store", "stores"], ["計算", "calc", "calc"], ["メニュー", "home", "menu"]];
const ICON_FOOT = { home: '<circle cx="5.5" cy="12" r="1.6" fill="currentColor"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="18.5" cy="12" r="1.6" fill="currentColor"/>' };

const App = {
  setup() {
    const S = reactive({
      phase: "loading", password: false,
      view: "input", items: [], stores: [], genres: [], memory: [], sheets: false, autoGenre: false,
      // 入力
      genre: "", name: "", memo: "", storeId: "", prio: "0",
      // 一覧・店舗別
      listMode: "todo", storeMode: "all", storeSel: "", here: null, hereErr: "", hereBusy: false,
      // 計算
      price: "", qty: "1", lines: [], tax: "込",
      ctab: "cmp", cmp: [], taxIn: "", taxRateT: "8", taxDir: "in",
      // 店舗の登録・ジャンル
      storeDraft: null, genreDraft: null, pickFor: -1, addrQ: "", addrRes: null, addrBusy: false,
      toast: "", toastOn: false, saving: 0, confirm: null,
    });
    try { Object.assign(S, JSON.parse(sessionStorage.getItem("sh_state") || "{}"), { storeDraft: null, genreDraft: null, confirm: null }); } catch (e) {}
    const keep = () => { try { sessionStorage.setItem("sh_state", JSON.stringify({ view: S.view, genre: S.genre, storeId: S.storeId, listMode: S.listMode, storeMode: S.storeMode, storeSel: S.storeSel, lines: S.lines, tax: S.tax, ctab: S.ctab, cmp: S.cmp, taxRateT: S.taxRateT, taxDir: S.taxDir })); } catch (e) {} };

    let tt;
    const toast = m => { S.toast = m; S.toastOn = true; clearTimeout(tt); tt = setTimeout(() => S.toastOn = false, 2200); };

    // ---- 読み込み・保存（保存は Python に送る。届くまでは画面の中で先に変えておく） ----
    const KEY = { 買い物: "items", 店舗: "stores", 買い物ジャンル: "genres", 買い物の記憶: "memory" };
    let QUEUE = [];           // Python にまだ届いていない保存
    let SERVER = null;
    function apply() {        // サーバーのデータ ＋ まだ届いていない保存
      if (!SERVER) return;
      const d = { items: SERVER.items, stores: SERVER.stores, genres: SERVER.genres, memory: SERVER.memory || [] };
      for (const a of QUEUE) d[KEY[a.table]] = a.rows;
      Object.assign(S, d, { sheets: SERVER.sheets, password: SERVER.password });
      if (!S.genre && S.genres[0]) S.genre = S.genres[0]["名前"];
    }
    function save(table, rows) {
      QUEUE = QUEUE.filter(a => a.table !== table);         // 同じ表は、最後のものだけ送る
      QUEUE.push({ id: uid(), type: "save_table", table, rows });
      S[KEY[table]] = rows; S.saving = QUEUE.length;
      SL.value({ queue: QUEUE });
    }
    function logout() { TOKEN.clear(); SL.value({ queue: QUEUE, logout: uid() }); }
    window.addEventListener("message", e => {
      const m = e.data;
      if (!m || m.type !== "streamlit:render") return;
      const args = m.args || {};
      if (args.mode === "probe") {          // ログイン画面の見えない部品：保存した証明を Python に渡すだけ
        if (!window.__probed) { window.__probed = true; SL.value({ token: TOKEN.get() }); }
        return;
      }
      if (args.token) TOKEN.set(args.token);
      SERVER = args.data || SERVER;
      const done = new Set(args.done || []);
      QUEUE = QUEUE.filter(a => !done.has(a.id));
      S.saving = QUEUE.length;
      apply();
      S.phase = "app";
      SL.height();
    });
    window.addEventListener("resize", () => SL.height());

    // ---- 名前で探す道具 ----
    const genreOf = name => S.genres.find(g => g["名前"] === name);
    const gIcon = name => svg(iconKey(genreOf(name)));
    const storeOf = id => S.stores.find(s => s.ID === id);
    const storeName = id => (storeOf(id) || {})["店名"] || "お店未定";
    const sortedGenres = computed(() => [...S.genres].sort((a, b) => (+a["並び"] || 0) - (+b["並び"] || 0)));
    const sortedStores = computed(() => [...S.stores].sort((a, b) => (+a["並び"] || 0) - (+b["並び"] || 0)));
    const todo = computed(() => S.items.filter(i => !i["済"]));

    // ---- 入力 ----
    // ---- 品名とジャンルの組み合わせを覚える（同じ品名を入れたら、前のジャンルを選ぶ。ちがうジャンルで入れたら上書き） ----
    const memOf = name => { const k = normName(name); return k ? S.memory.find(m => m["キー"] === k) : null; };
    function remember(name, genre) {
      const k = normName(name); if (!k) return;
      const old = S.memory.find(m => m["キー"] === k);
      if (old && old["ジャンル"] === genre) return;
      const rows = S.memory.filter(m => m["キー"] !== k);
      rows.push({ キー: k, 品名: name, ジャンル: genre, 更新: new Date().toISOString().slice(0, 10) });
      save("買い物の記憶", rows.slice(-800));
    }
    // ジャンルの帯で、選んだジャンルを真ん中に
    // ---- ダイヤル：真ん中の枠に来たジャンルが選ばれる。真ん中から離れるほど小さく・薄く ----
    let dialLock = 0;        // こちらで動かしている間は、途中のジャンルを選ばない
    function centerGenre(smooth = true) {
      nextTick(() => {
        const strip = document.querySelector(".gstrip .gscroll"), el = strip && strip.querySelector(".gbtn.on");
        if (!strip || !el) return;
        dialLock = Date.now() + (smooth ? 600 : 50);
        strip.scrollTo({ left: el.offsetLeft - (strip.clientWidth - el.offsetWidth) / 2, behavior: smooth ? "smooth" : "auto" });
        requestAnimationFrame(dialLook);
      });
    }
    function dialLook() {            // 見た目（大きさ・うすさ）を、真ん中からの距離で決める
      const strip = document.querySelector(".gstrip .gscroll"); if (!strip) return null;
      const r = strip.getBoundingClientRect(), mid = r.left + r.width / 2;
      let best = null, bd = 1e9;
      for (const el of strip.querySelectorAll(".gbtn")) {
        const e = el.getBoundingClientRect(), d = Math.abs(e.left + e.width / 2 - mid), k = Math.min(1, d / 160);
        el.style.transform = `scale(${(1.28 - k * 0.5).toFixed(3)})`;
        el.style.opacity = (1 - Math.min(1, d / 230) * 0.6).toFixed(3);
        if (d < bd) { bd = d; best = el; }
      }
      return best;
    }
    let dialT = 0;
    function onDial() {              // 回しているあいだも、枠に入ったジャンルをその場で選ぶ（ピンクがすぐ移る）。止まったら、ぴったり真ん中にそろえる
      requestAnimationFrame(() => {
        const best = dialLook(), name = best && best.dataset.g;
        if (name && name !== S.genre && Date.now() >= dialLock) { S.genre = name; S.autoGenre = false; }
        clearTimeout(dialT);
        dialT = setTimeout(() => {
          if (Date.now() < dialLock) return;
          const b = dialLook();
          if (b && b.dataset.g !== S.genre) S.genre = b.dataset.g;
          keep();
          if (b) centerGenre(true);
        }, 140);
      });
    }
    function pickGenre(name) { S.genre = name; S.autoGenre = false; keep(); centerGenre(); }
    watch(() => S.name, name => {
      const m = memOf(name);
      if (m && S.genres.some(g => g["名前"] === m["ジャンル"])) { if (S.genre !== m["ジャンル"] || !S.autoGenre) { S.genre = m["ジャンル"]; S.autoGenre = true; centerGenre(); } }
      else if (S.autoGenre) S.autoGenre = false;
    });
    watch(() => S.view, v => { if (v === "input") centerGenre(false); });
    watch(() => S.phase, v => { if (v === "app" && S.view === "input") centerGenre(false); });
    function addItem() {
      const name = S.name.trim();
      if (!name) { toast("品名を入れてください"); return; }
      remember(name, S.genre || "その他");
      const row = { ID: uid(), 品名: name, ジャンル: S.genre || "その他", メモ: S.memo.trim(), 店舗ID: S.storeId, 済: "", 優先: S.prio === "0" ? "" : S.prio, 登録日時: new Date().toISOString().slice(0, 16).replace("T", " ") };
      save("買い物", [...S.items, row]);
      toast(`追加しました：${name}${S.storeId ? "（" + storeName(S.storeId) + "）" : ""}`);
      S.name = ""; S.memo = ""; S.prio = "0"; S.autoGenre = false;
      nextTick(() => { const el = document.getElementById("nameIn"); if (el) el.focus(); });
    }
    const recent = computed(() => [...S.items].filter(i => !i["済"]).sort((a, b) => String(b["登録日時"]).localeCompare(a["登録日時"])).slice(0, 5));

    // ---- 一覧（ジャンル別） ----
    const byGenre = list => {
      const order = sortedGenres.value.map(g => g["名前"]), o = {};
      for (const it of list) (o[it["ジャンル"] || "その他"] = o[it["ジャンル"] || "その他"] || []).push(it);
      return Object.entries(o).sort((a, b) => (order.indexOf(a[0]) + 999 * (order.indexOf(a[0]) < 0)) - (order.indexOf(b[0]) + 999 * (order.indexOf(b[0]) < 0)));
    };
    // ---- 優先：1＝優先（一覧・店舗別でいちばん上。現在地では別のお店でも出す）、2＝最優先（さらに全ページの上にバナー） ----
    const prio = it => Math.min(2, Math.max(0, +it["優先"] || 0));
    const byPrio = list => [...list].sort((a, b) => prio(b) - prio(a) || String(a["登録日時"]).localeCompare(b["登録日時"]));
    const top2 = computed(() => todo.value.filter(i => prio(i) === 2));
    function cyclePrio(it) {
      const n = (prio(it) + 1) % 3;
      save("買い物", S.items.map(x => x.ID === it.ID ? { ...x, 優先: n ? String(n) : "" } : x));
      toast(n === 2 ? `「${it["品名"]}」を最優先にしました` : n === 1 ? `「${it["品名"]}」を優先にしました` : `「${it["品名"]}」の優先をはずしました`);
    }
    const PRIO_KEY = "__prio";
    const listGroups = computed(() => {
      const list = S.listMode === "todo" ? todo.value : S.items;
      const top = byPrio(list.filter(i => prio(i) && !i["済"]));
      const rest = list.filter(i => !(prio(i) && !i["済"]));
      return (top.length ? [[PRIO_KEY, top]] : []).concat(byGenre(rest));
    });
    function toggle(it) {
      save("買い物", S.items.map(x => x.ID === it.ID ? { ...x, 済: x["済"] ? "" : "1" } : x));
    }
    function removeItem(it) { save("買い物", S.items.filter(x => x.ID !== it.ID)); toast("消しました"); }
    function clearDone() {
      const n = S.items.filter(i => i["済"]).length;
      if (!n) { toast("買ったものはありません"); return; }
      S.confirm = { msg: `買ったもの ${n}件 を一覧から消しますか？`, ok: "消す", fn: () => { save("買い物", S.items.filter(i => !i["済"])); toast("消しました"); } };
    }

    // ---- 店舗別 ----
    async function findHere() {
      S.hereBusy = true; S.hereErr = "";
      try { S.here = await locate(); } catch (e) { S.hereErr = e.message; S.here = null; }
      S.hereBusy = false;
    }
    const nearStores = computed(() => {
      if (!S.here) return [];
      return sortedStores.value.filter(s => s["緯度"] !== "" && s["経度"] !== "")
        .map(s => ({ s, m: meters(S.here, { lat: +s["緯度"], lng: +s["経度"] }) })).sort((a, b) => a.m - b.m);
    });
    // 表示するお店のまとまり：[{ id, name, dist, items }]
    // 優先のもの：全店舗・現在地はぜんぶ（現在地では別のお店のものも出す）。お店を選んでいるときは、そのお店のもの
    // 1km〜3km のお店（もしかして？）
    const maybeGroups = computed(() => S.storeMode !== "here" ? [] : nearStores.value.filter(x => x.m > NEAR && x.m <= MAYBE)
      .map(x => ({ id: x.s.ID, name: x.s["店名"], dist: x.m, items: todo.value.filter(i => !prio(i) && i["店舗ID"] === x.s.ID) })));
    const prioStore = computed(() => byPrio(todo.value.filter(i => prio(i) && (S.storeMode === "here" || !S.storeSel || i["店舗ID"] === S.storeSel))));
    const storeGroups = computed(() => {
      const items = todo.value.filter(i => !prio(i));
      if (S.storeMode === "here") {
        return nearStores.value.filter(x => x.m <= NEAR).map(x => ({ id: x.s.ID, name: x.s["店名"], dist: x.m, items: items.filter(i => i["店舗ID"] === x.s.ID) }));
      }
      const ids = S.storeSel ? [S.storeSel] : [...sortedStores.value.map(s => s.ID), ""];
      return ids.map(id => ({ id, name: storeName(id), dist: null, items: items.filter(i => (i["店舗ID"] || "") === id && (id === "" || storeOf(id))) .concat(id === "" ? items.filter(i => i["店舗ID"] && !storeOf(i["店舗ID"])) : []) }))
        .filter(g => S.storeSel || g.items.length || g.id);
    });
    function setStoreMode(m) { S.storeMode = m; if (m === "here") findHere(); keep(); }

    // ---- 計算 ----
    const taxRate = computed(() => S.tax === "8" ? 1.08 : S.tax === "10" ? 1.1 : 1);
    const calcTotal = computed(() => S.lines.reduce((a, l) => a + l.p * l.q, 0));
    function addLine() {
      const p = Math.round(+String(S.price).replace(/[^0-9.]/g, "")), q = Math.max(1, Math.round(+S.qty || 1));
      if (!p) { toast("金額を入れてください"); return; }
      S.lines.push({ id: uid(), p, q }); S.price = ""; S.qty = "1"; keep();
      nextTick(() => { const el = document.getElementById("priceIn"); if (el) el.focus(); });
    }
    function clearLines() { S.lines = []; keep(); }

    // ---- 比べる（どっちが安い？）：値段 ÷ 量 で、100g・100ml・1個あたりの値段をそろえる ----
    const UNITS = { g: ["g", 1, 100], kg: ["g", 1000, 100], ml: ["ml", 1, 100], L: ["ml", 1000, 100], 個: ["個", 1, 1], 枚: ["枚", 1, 1], 本: ["本", 1, 1], 袋: ["袋", 1, 1], ロール: ["ロール", 1, 1], 回: ["回", 1, 1] };
    const UNIT_LIST = Object.keys(UNITS);
    const LETTERS = "ABCDEFGH";
    const num = v => { const n = parseFloat(String(v ?? "").replace(/[^0-9.]/g, "")); return isFinite(n) ? n : 0; };
    function newCmp(prev) { return { id: uid(), name: "", price: "", amt: "", unit: prev ? ({ kg: "g", L: "ml" }[prev.unit] || prev.unit) : "g", pack: "1", tax: (prev && prev.tax) || "込" }; }
    if (!S.cmp.length) S.cmp = [newCmp(), newCmp()];
    // その行の「基準あたりの値段」（税込にそろえる）。比べられないときは null
    function unitInfo(c) {
      const u = UNITS[c.unit] || UNITS.g, price = num(c.price) * (c.tax === "8" ? 1.08 : c.tax === "10" ? 1.1 : 1), total = num(c.amt) * u[1] * Math.max(1, num(c.pack) || 1);
      if (!price || !total) return null;
      return { base: u[0], per: u[2], v: price / total * u[2], price, total };
    }
    const cmpResult = computed(() => {
      const rows = S.cmp.map((c, i) => ({ c, i, info: unitInfo(c) })).filter(r => r.info);
      const bases = new Set(rows.map(r => r.info.base));
      if (rows.length < 2) return { ok: false, msg: "2つ以上の値段と量を入れると、どれが安いか出ます" };
      if (bases.size > 1) return { ok: false, msg: "単位をそろえてください（g と ml、g と 個 などは比べられません）" };
      const best = rows.reduce((a, b) => b.info.v < a.info.v ? b : a), worst = rows.reduce((a, b) => b.info.v > a.info.v ? b : a);
      return { ok: true, best, worst, rows, diff: worst.info.v - best.info.v, pct: (1 - best.info.v / worst.info.v) * 100 };
    });
    const perText = info => info ? `${info.per === 1 ? "1" + info.base : info.per + info.base}あたり ${info.v < 10 ? info.v.toFixed(2) : info.v < 100 ? info.v.toFixed(1) : Math.round(info.v).toLocaleString()}円` : "—";
    function addCmp() { if (S.cmp.length >= LETTERS.length) return; S.cmp.push(newCmp(S.cmp[S.cmp.length - 1])); keep(); }
    function clearCmp() { S.cmp = [newCmp(), newCmp()]; keep(); }
    const cycleTax = c => { c.tax = c.tax === "込" ? "8" : c.tax === "8" ? "10" : "込"; keep(); };
    const taxLabel = t => t === "込" ? "税込" : `税抜+${t}%`;

    // ---- 税込・税抜 ----
    const taxCalc = computed(() => {
      const p = num(S.taxIn), r = S.taxRateT === "10" ? 0.1 : 0.08;
      if (!p) return null;
      return S.taxDir === "in" ? { from: p, to: Math.floor(p * (1 + r)), tax: Math.floor(p * (1 + r)) - p }      // 税抜 → 税込（1円未満は切りすて）
        : { from: p, to: Math.ceil(p / (1 + r)), tax: p - Math.ceil(p / (1 + r)) };                               // 税込 → 税抜
    });

    // ---- 店舗の登録（店名と位置。位置は現在地か、地図でピン） ----
    let map = null, marker = null;
    function editStore(s) {
      S.storeDraft = s ? { ...s } : { ID: "", 店名: "", 緯度: "", 経度: "", 並び: String(S.stores.length) };
      S.view = "storeEdit"; S.addrQ = ""; S.addrRes = null; keep();
      nextTick(drawMap);
    }
    async function drawMap() {
      const el = document.getElementById("map");
      if (!el) return;
      try {
        const L = await loadLeaflet();
        if (map) { map.remove(); map = null; marker = null; }
        const d = S.storeDraft, has = d["緯度"] !== "" && d["経度"] !== "";
        const center = has ? [+d["緯度"], +d["経度"]] : S.here ? [S.here.lat, S.here.lng] : [35.681, 139.767];
        map = L.map(el, { zoomControl: true, attributionControl: true }).setView(center, has || S.here ? 16 : 12);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
        if (has) marker = L.marker(center, { icon: pinIcon() }).addTo(map);
        map.on("click", e => setPin(e.latlng.lat, e.latlng.lng, false));
      } catch (e) { el.innerHTML = `<div class="empty small">地図を読み込めませんでした。「現在地を使う」で位置を入れてください</div>`; }
    }
    // ピンの絵（Leaflet の画像ファイルを使わず、ピンクのピンを描く）
    const pinIcon = () => L.divIcon({ className: "pin", iconSize: [34, 42], iconAnchor: [17, 40],
      html: '<svg viewBox="0 0 24 30" width="34" height="42"><path d="M12 29s-10-9.4-10-16.5a10 10 0 0 1 20 0C22 19.6 12 29 12 29z" fill="#d9658e" stroke="#fff" stroke-width="2"/><circle cx="12" cy="12.5" r="3.8" fill="#fff"/></svg>' });
    function setPin(lat, lng, move) {
      S.storeDraft["緯度"] = lat.toFixed(6); S.storeDraft["経度"] = lng.toFixed(6);
      if (map && window.L) { if (marker) marker.setLatLng([lat, lng]); else marker = L.marker([lat, lng], { icon: pinIcon() }).addTo(map); if (move) map.setView([lat, lng], 17); }
    }
    async function searchAddr() {
      const q = S.addrQ.trim();
      if (!q) { toast("住所を入れてください"); return; }
      S.addrBusy = true; S.addrRes = null;
      const res = await geocode(q);
      S.addrBusy = false; S.addrRes = res;
      if (res.length === 1) pickAddr(res[0]);
      else if (!res.length) toast("見つかりませんでした。住所を短くするか、地図を押してください");
    }
    function pickAddr(r) {
      setPin(r.lat, r.lng, true); S.addrRes = null;
      if (!String(S.storeDraft["店名"] || "").trim()) { /* 店名はそのまま */ }
      toast("その場所にピンを立てました");
    }
    async function useHere() {
      toast("現在地をさがしています…");
      try { const p = await locate(); S.here = p; setPin(p.lat, p.lng, true); toast("現在地を入れました"); } catch (e) { toast(e.message); }
    }
    function saveStore() {
      const d = S.storeDraft, name = String(d["店名"] || "").trim();
      if (!name) { toast("店名を入れてください"); return; }
      const row = { ...d, 店名: name, ID: d.ID || uid() };
      save("店舗", d.ID ? S.stores.map(s => s.ID === d.ID ? row : s) : [...S.stores, row]);
      toast(d.ID ? "保存しました" : "お店を登録しました"); S.view = "storeList"; S.storeDraft = null;
    }
    function deleteStore() {
      const d = S.storeDraft;
      S.confirm = { msg: `「${esc(d["店名"])}」を消しますか？<br><span class="small muted">このお店の商品は「お店未定」になります</span>`, ok: "消す", fn: () => {
        save("店舗", S.stores.filter(s => s.ID !== d.ID));
        save("買い物", S.items.map(i => i["店舗ID"] === d.ID ? { ...i, 店舗ID: "" } : i));
        if (S.storeSel === d.ID) S.storeSel = "";
        if (S.storeId === d.ID) S.storeId = "";
        S.view = "storeList"; S.storeDraft = null; toast("消しました");
      } };
    }

    // ---- ジャンル（追加・名前・アイコン・並べかえ・削除） ----
    function editGenres() { S.genreDraft = sortedGenres.value.map(g => ({ ...g })); S.view = "genres"; keep(); }
    function gMove(i, d) { const r = S.genreDraft, j = i + d; if (j < 0 || j >= r.length) return; [r[i], r[j]] = [r[j], r[i]]; }
    function gAdd() { S.genreDraft.push({ 名前: "", アイコン: "i:box", 並び: "" }); nextTick(() => { const ins = document.querySelectorAll(".gname"); if (ins.length) ins[ins.length - 1].focus(); }); }
    function gSave() {
      const rows = S.genreDraft.map((g, k) => ({ 名前: String(g["名前"] || "").trim(), アイコン: g["アイコン"] || "i:box", 並び: String(k) })).filter(g => g["名前"]);
      if (!rows.length) { toast("ジャンルを1つ以上入れてください"); return; }
      if (new Set(rows.map(g => g["名前"])).size !== rows.length) { toast("同じ名前のジャンルがあります"); return; }
      save("買い物ジャンル", rows);
      if (!rows.some(g => g["名前"] === S.genre)) S.genre = rows[0]["名前"];
      toast("ジャンルを保存しました"); S.genreDraft = null; S.view = "menu";
    }

    function go(v) {
      if (map) { map.remove(); map = null; marker = null; }
      S.view = v; S.storeDraft = null; S.genreDraft = null; keep(); const sc = document.getElementById("app"); if (sc) sc.scrollTop = 0;
      if (v === "stores" && S.storeMode === "here") findHere();
    }
    const footOn = k => S.view === k || (k === "menu" && !FOOT.some(f => f[2] === S.view));
    const footIcon = k => k === "home" ? `<svg class="li" viewBox="0 0 24 24" fill="none">${ICON_FOOT.home}</svg>` : svg(k);
    function toKakeibo() { SL.value({ queue: QUEUE, go: "kakeibo", gid: uid() }); }     // 家計簿のページへ（ログインはそのまま）

    keyboardHelper(() => document.getElementById("app"));
    SL.ready(); SL.height();
    return { S, svg, gIcon, yen, distText, NEAR, FOOT, footOn, footIcon, sortedGenres, sortedStores, todo, recent, listGroups, storeGroups, nearStores,
      taxRate, calcTotal, storeName, pickGenre, memOf, onDial, MAYBE, maybeGroups, searchAddr, pickAddr, prio, cyclePrio, top2, PRIO_KEY, prioStore, UNIT_LIST, LETTERS, cmpResult, unitInfo, perText, addCmp, clearCmp, cycleTax, taxLabel, taxCalc, iconKey, CAT_ICON,
      logout, addItem, toggle, removeItem, clearDone, setStoreMode, findHere, addLine, clearLines,
      editStore, useHere, saveStore, deleteStore, editGenres, gMove, gAdd, gSave, go, keep, toKakeibo };
  },
  template: `
<div v-if="S.phase === 'loading'" class="loading">読み込み中…</div>

<template v-else>
<div class="wrap">
  <button v-if="top2.length && !['storeEdit', 'genres'].includes(S.view)" class="banner" @click="go('list')">
    <span class="bstar" v-html="svg('star')"></span>
    <span class="btext"><small>最優先 {{ top2.length }}件</small><b>{{ top2.map(i => i['品名']).join('・') }}</b></span><span class="bgo">›</span>
  </button>

  <!-- ===== 入力 ===== -->
  <template v-if="S.view === 'input'">
    <div class="title">買い物リスト</div>
    <div class="card" style="padding:4px 16px">
      <div class="field"><label>品名</label><div class="namebox"><input id="nameIn" v-model="S.name" placeholder="例：たまねぎ" maxlength="40" @keydown.enter.prevent="addItem" autocomplete="off">
        <span v-if="S.autoGenre" class="memtag" v-html="svg(iconKey(sortedGenres.find(g => g['名前'] === S.genre))) + 'いつもの ' + S.genre"></span></div></div>
      <div class="field"><label>メモ</label><input v-model="S.memo" placeholder="任意（例：2個・特売）" maxlength="60"></div>
      <div class="field"><label>優先</label><div class="prios"><button v-for="(l, k) in ['ふつう', '優先', '最優先']" :key="k" class="pchip" :class="['p' + k, { on: S.prio === String(k) }]" @click="S.prio = String(k)">{{ l }}</button></div></div>
    </div>
    <div class="sec" style="margin-top:4px">お店<button class="link" @click="go('storeList')">お店の登録 ›</button></div>
    <div class="chips scroll">
      <button class="chip" :class="{ on: !S.storeId }" @click="S.storeId = ''; keep()">未定</button>
      <button v-for="s in sortedStores" :key="s.ID" class="chip" :class="{ on: S.storeId === s.ID }" @click="S.storeId = s.ID; keep()">{{ s['店名'] }}</button>
    </div>
    <button class="big" @click="addItem">{{ S.genre || 'その他' }} に追加する</button>
    <template v-if="recent.length">
      <div class="sec">最近入れたもの</div>
      <div class="list">
        <div v-for="it in recent" :key="it.ID" class="item">
          <span class="bic" v-html="gIcon(it['ジャンル'])"></span>
          <div class="t"><b>{{ it['品名'] }}</b><span>{{ it['ジャンル'] }}・{{ storeName(it['店舗ID']) }}{{ it['メモ'] ? '・' + it['メモ'] : '' }}</span></div>
          <button class="del" @click="removeItem(it)" aria-label="消す">✕</button>
        </div>
      </div>
    </template>
  </template>

  <!-- ===== 一覧（ジャンル別） ===== -->
  <template v-else-if="S.view === 'list'">
    <div class="title">一覧</div>
    <div class="seg"><button :class="{ on: S.listMode === 'todo' }" @click="S.listMode = 'todo'; keep()">まだ買っていない</button><button :class="{ on: S.listMode === 'all' }" @click="S.listMode = 'all'; keep()">全部</button></div>
    <div class="card count"><div><span>のこり</span><b>{{ todo.length }}</b></div><div><span>買った</span><b>{{ S.items.length - todo.length }}</b></div><div><span>お店未定</span><b>{{ todo.filter(i => !i['店舗ID']).length }}</b></div></div>
    <div v-if="!listGroups.length" class="empty">{{ S.listMode === 'todo' ? '買うものはありません' : 'まだありません' }}</div>
    <template v-for="[g, list] in listGroups" :key="g">
      <div v-if="g === PRIO_KEY" class="day prio"><span class="bic" v-html="svg('star')"></span>優先<b>{{ list.length }}件</b></div>
      <div v-else class="day"><span class="bic" v-html="gIcon(g)"></span>{{ g }}<b>{{ list.length }}件</b></div>
      <div class="list" :class="{ priolist: g === PRIO_KEY }">
        <div v-for="it in list" :key="it.ID" class="item" :class="{ done: it['済'] }" style="grid-template-columns:34px 1fr auto auto">
          <button class="mark" @click="toggle(it)" :aria-label="it['済'] ? 'もどす' : '買った'"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></button>
          <button class="t" style="text-align:left" @click="toggle(it)"><b>{{ it['品名'] }}</b><span>{{ g === PRIO_KEY ? it['ジャンル'] + '・' : '' }}{{ storeName(it['店舗ID']) }}{{ it['メモ'] ? '・' + it['メモ'] : '' }}</span></button>
          <button class="star" :class="'p' + prio(it)" @click="cyclePrio(it)" :aria-label="'優先：' + ['ふつう','優先','最優先'][prio(it)]"><svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" :fill="prio(it) ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg><i v-if="prio(it) === 2">2</i></button>
          <button class="del" @click="removeItem(it)" aria-label="消す">✕</button>
        </div>
      </div>
    </template>
    <button class="btn" style="margin-top:16px" @click="clearDone">買ったものを一覧から消す</button>
    <div class="small muted" style="margin:8px 4px 0">行を押すと「買った」になります（もう一度押すと、もどります）</div>
  </template>

  <!-- ===== 店舗別 ===== -->
  <template v-else-if="S.view === 'stores'">
    <div class="title">店舗別</div>
    <div class="seg"><button :class="{ on: S.storeMode === 'all' }" @click="setStoreMode('all')">全て</button><button :class="{ on: S.storeMode === 'here' }" @click="setStoreMode('here')">現在地</button></div>
    <template v-if="S.storeMode === 'all'">
      <div class="chips scroll" style="margin-bottom:6px">
        <button class="chip" :class="{ on: !S.storeSel }" @click="S.storeSel = ''; keep()">全店舗</button>
        <button v-for="s in sortedStores" :key="s.ID" class="chip" :class="{ on: S.storeSel === s.ID }" @click="S.storeSel = s.ID; keep()">{{ s['店名'] }}</button>
      </div>
      <div v-if="!S.stores.length" class="card small muted">お店がまだありません。<button class="link" @click="editStore(null)">お店を登録 ›</button></div>
    </template>
    <template v-else>
      <div class="card" style="display:flex;align-items:center;gap:10px">
        <span class="bic" v-html="svg('locate')"></span>
        <div style="flex:1;min-width:0" class="small">
          <template v-if="S.hereBusy">現在地をさがしています…</template>
          <template v-else-if="S.hereErr"><span style="color:var(--red)">{{ S.hereErr }}</span></template>
          <template v-else-if="S.here">1km 以内のお店：<b>{{ storeGroups.length }}件</b>　1〜3km：<b>{{ maybeGroups.length }}件</b></template>
        </div>
        <button class="chip" @click="findHere">更新</button>
      </div>
      <div v-if="S.here && !S.hereBusy && !storeGroups.length" class="card small muted">
        1km 以内に登録したお店はありません。<template v-if="nearStores.length && !maybeGroups.length">いちばん近いのは「{{ nearStores[0].s['店名'] }}」（{{ distText(nearStores[0].m) }}）です。</template>
      </div>
    </template>
    <template v-if="prioStore.length">
      <div class="day prio"><span class="bic" v-html="svg('star')"></span>優先{{ S.storeMode === 'here' ? '（どのお店でも）' : '' }}<b>{{ prioStore.length }}件</b></div>
      <div class="list priolist">
        <div v-for="it in prioStore" :key="it.ID" class="item" style="grid-template-columns:34px 1fr auto">
          <button class="mark" @click="toggle(it)"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></button>
          <button class="t" style="text-align:left" @click="toggle(it)"><b>{{ it['品名'] }}</b><span>{{ storeName(it['店舗ID']) }}・{{ it['ジャンル'] }}{{ it['メモ'] ? '・' + it['メモ'] : '' }}</span></button>
          <button class="star" :class="'p' + prio(it)" @click="cyclePrio(it)" :aria-label="'優先：' + ['ふつう','優先','最優先'][prio(it)]"><svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" :fill="prio(it) ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg><i v-if="prio(it) === 2">2</i></button>
        </div>
      </div>
    </template>
    <template v-for="g in storeGroups" :key="g.id">
      <div class="day"><span class="bic" v-html="svg(g.id ? 'store' : 'box')"></span>{{ g.name }}<span v-if="g.dist !== null" class="dist">{{ distText(g.dist) }}</span><b>{{ g.items.length }}件</b></div>
      <div class="list">
        <div v-if="!g.items.length" class="empty small" style="padding:16px 0">このお店で買うものはありません</div>
        <div v-for="it in g.items" :key="it.ID" class="item" :class="{ done: it['済'] }" style="grid-template-columns:34px 1fr auto">
          <button class="mark" @click="toggle(it)"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></button>
          <button class="t" style="text-align:left" @click="toggle(it)"><b>{{ it['品名'] }}</b><span>{{ it['ジャンル'] }}{{ it['メモ'] ? '・' + it['メモ'] : '' }}</span></button>
          <button class="star" :class="'p' + prio(it)" @click="cyclePrio(it)" :aria-label="'優先：' + ['ふつう','優先','最優先'][prio(it)]"><svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" :fill="prio(it) ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg><i v-if="prio(it) === 2">2</i></button>
        </div>
      </div>
    </template>
    <template v-if="maybeGroups.length">
      <div class="sec maybe">もしかして？<span class="small muted">1〜3km のお店</span></div>
      <template v-for="g in maybeGroups" :key="'m' + g.id">
        <div class="day"><span class="bic" v-html="svg('store')"></span>{{ g.name }}<span class="dist">{{ distText(g.dist) }}</span><b>{{ g.items.length }}件</b></div>
        <div class="list maybelist">
          <div v-if="!g.items.length" class="empty small" style="padding:16px 0">このお店で買うものはありません</div>
          <div v-for="it in g.items" :key="it.ID" class="item" style="grid-template-columns:34px 1fr auto">
            <button class="mark" @click="toggle(it)"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></button>
            <button class="t" style="text-align:left" @click="toggle(it)"><b>{{ it['品名'] }}</b><span>{{ it['ジャンル'] }}{{ it['メモ'] ? '・' + it['メモ'] : '' }}</span></button>
            <button class="star" :class="'p' + prio(it)" @click="cyclePrio(it)"><svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg></button>
          </div>
        </div>
      </template>
    </template>
  </template>

  <!-- ===== 計算（比べる・税込・合計） ===== -->
  <template v-else-if="S.view === 'calc'">
    <div class="title">計算</div>
    <div class="seg"><button :class="{ on: S.ctab === 'cmp' }" @click="S.ctab = 'cmp'; keep()">どっちが安い？</button><button :class="{ on: S.ctab === 'tax' }" @click="S.ctab = 'tax'; keep()">税込</button><button :class="{ on: S.ctab === 'sum' }" @click="S.ctab = 'sum'; keep()">合計</button></div>

    <!-- どっちが安い？ -->
    <template v-if="S.ctab === 'cmp'">
      <div class="card cmpres" :class="{ win: cmpResult.ok }">
        <template v-if="cmpResult.ok">
          <div class="small">いちばん安いのは</div>
          <div class="winner"><span class="letter">{{ LETTERS[cmpResult.best.i] }}</span><b>{{ cmpResult.best.c.name || LETTERS[cmpResult.best.i] }}</b></div>
          <div class="small">{{ perText(cmpResult.best.info) }}</div>
          <div class="small" v-if="cmpResult.diff > 0">いちばん高いもの（{{ cmpResult.worst.c.name || LETTERS[cmpResult.worst.i] }}）より <b>{{ Math.round(cmpResult.pct) }}%</b> お得</div>
          <div class="small" v-else>どれも同じ値段です</div>
        </template>
        <div v-else class="small muted">{{ cmpResult.msg }}</div>
      </div>
      <div v-for="(c, i) in S.cmp" :key="c.id" class="card cmprow" :class="{ best: cmpResult.ok && cmpResult.best.i === i }">
        <div class="cmphead"><span class="letter">{{ LETTERS[i] }}</span>
          <input v-model="c.name" @input="keep()" placeholder="名前（任意）" maxlength="20">
          <button class="del" v-if="S.cmp.length > 2" @click="S.cmp.splice(i, 1); keep()">✕</button></div>
        <div class="cmpin">
          <label>値段<div class="unitbox"><input v-model="c.price" @input="keep()" inputmode="decimal" placeholder="0">円</div></label>
          <button class="taxchip" @click="cycleTax(c)">{{ taxLabel(c.tax) }}</button>
        </div>
        <div class="cmpin">
          <label>量<div class="unitbox"><input v-model="c.amt" @input="keep()" inputmode="decimal" placeholder="0">
            <select v-model="c.unit" @change="keep()"><option v-for="u in UNIT_LIST" :key="u">{{ u }}</option></select></div></label>
          <label class="pack">入数<div class="unitbox"><input v-model="c.pack" @input="keep()" inputmode="numeric" placeholder="1">こ</div></label>
        </div>
        <div class="per" :class="{ none: !unitInfo(c) }">{{ perText(unitInfo(c)) }}<span v-if="cmpResult.ok && cmpResult.best.i === i" class="besttag">いちばん安い</span></div>
      </div>
      <div class="row2"><button class="btn" @click="addCmp" :disabled="S.cmp.length >= LETTERS.length">＋ 比べるものを足す</button><button class="btn" @click="clearCmp">ぜんぶ消す</button></div>
      <div class="small muted" style="margin:10px 4px 0">例：A は 298円で 500g、B は 548円で 1kg → 100gあたりで比べます。入数は「3個パック」などのときに入れます。値段の横のボタンで「税込・税抜+8%・税抜+10%」を切りかえると、税込にそろえて比べます</div>
    </template>

    <!-- 税込・税抜 -->
    <template v-else-if="S.ctab === 'tax'">
      <div class="seg" style="margin-bottom:8px"><button :class="{ on: S.taxDir === 'in' }" @click="S.taxDir = 'in'; keep()">税抜 → 税込</button><button :class="{ on: S.taxDir === 'out' }" @click="S.taxDir = 'out'; keep()">税込 → 税抜</button></div>
      <div class="seg"><button :class="{ on: S.taxRateT === '8' }" @click="S.taxRateT = '8'; keep()">8%（食品）</button><button :class="{ on: S.taxRateT === '10' }" @click="S.taxRateT = '10'; keep()">10%（日用品など）</button></div>
      <div class="card">
        <div class="small muted" style="margin-bottom:6px">{{ S.taxDir === 'in' ? '税抜の値段' : '税込の値段' }}</div>
        <div class="unitbox big-in"><input v-model="S.taxIn" @input="keep()" inputmode="numeric" placeholder="0">円</div>
      </div>
      <div class="card taxres" v-if="taxCalc">
        <div class="small muted">{{ S.taxDir === 'in' ? '税込' : '税抜' }}</div>
        <b>{{ yen(taxCalc.to) }}</b>
        <div class="small muted">消費税 {{ yen(taxCalc.tax) }}（{{ S.taxRateT }}%）</div>
      </div>
      <div class="small muted" style="margin:6px 4px 0">1円未満は、税込は切りすて・税抜は切りあげで出しています（お店によって少しちがうことがあります）</div>
    </template>

    <!-- 合計 -->
    <template v-else>
      <div class="seg"><button :class="{ on: S.tax === '込' }" @click="S.tax = '込'; keep()">税込の値段</button><button :class="{ on: S.tax === '8' }" @click="S.tax = '8'; keep()">税抜＋8%</button><button :class="{ on: S.tax === '10' }" @click="S.tax = '10'; keep()">税抜＋10%</button></div>
      <div class="card">
        <div class="calcin">
          <input id="priceIn" v-model="S.price" inputmode="numeric" placeholder="値段" @keydown.enter.prevent="addLine">
          <input v-model="S.qty" inputmode="numeric" placeholder="個数" style="text-align:center">
          <button class="btn pri" @click="addLine">たす</button>
        </div>
      </div>
      <div class="card total"><span>合計（{{ S.lines.reduce((a, l) => a + l.q, 0) }}点）</span><b>{{ yen(calcTotal * taxRate) }}</b></div>
      <div class="list" v-if="S.lines.length">
        <div v-for="(l, i) in S.lines" :key="l.id" class="item" style="grid-template-columns:1fr auto auto">
          <div class="t"><b>{{ yen(l.p) }} × {{ l.q }}</b><span>{{ i + 1 }}つ目</span></div>
          <b>{{ yen(l.p * l.q * taxRate) }}</b>
          <button class="del" @click="S.lines.splice(i, 1); keep()">✕</button>
        </div>
      </div>
      <button v-if="S.lines.length" class="btn" style="margin-top:14px" @click="clearLines">ぜんぶ消す</button>
      <div class="small muted" style="margin:10px 4px 0">かごに入れたものの値段を足していく計算です（保存はしません）</div>
    </template>
  </template>

  <!-- ===== メニュー ===== -->
  <template v-else-if="S.view === 'menu'">
    <div class="title">メニュー</div>
    <div class="tiles">
      <button class="tile" @click="go('storeList')"><span v-html="svg('store')"></span>お店の登録</button>
      <button class="tile" @click="editGenres"><span v-html="svg('tag')"></span>ジャンル</button>
      <button class="tile" @click="toKakeibo"><span v-html="svg('wallet')"></span>家計簿へ</button>
      <button class="tile" @click="clearDone"><span v-html="svg('list')"></span>買ったものを消す</button>
    </div>
    <div class="card small" style="margin-top:14px">{{ S.sheets ? '保存先：Google スプレッドシート（家計簿と同じファイル）' : '⚠️ いまは試し用の保存です（家計簿と同じく、Google スプレッドシートにつなぐと残ります）' }}</div>
    <button v-if="S.password" class="btn danger" @click="logout">ログアウト</button>
  </template>

  <!-- ===== お店の一覧 ===== -->
  <template v-else-if="S.view === 'storeList'">
    <div class="title">お店の登録</div>
    <div class="list" v-if="sortedStores.length">
      <button v-for="s in sortedStores" :key="s.ID" class="item" style="grid-template-columns:34px 1fr auto" @click="editStore(s)">
        <span class="bic" v-html="svg('store')"></span>
        <div class="t"><b>{{ s['店名'] }}</b><span>{{ s['緯度'] !== '' ? '位置あり' : '位置なし（現在地の表示に出ません）' }}</span></div>
        <span class="muted">›</span>
      </button>
    </div>
    <div v-else class="empty">まだありません</div>
    <button class="big" @click="editStore(null)">＋ お店を追加</button>
  </template>

  <!-- ===== お店の追加・編集 ===== -->
  <template v-else-if="S.view === 'storeEdit' && S.storeDraft">
    <div class="title">{{ S.storeDraft.ID ? 'お店を編集' : 'お店を追加' }}</div>
    <div class="card" style="padding:4px 16px">
      <div class="field"><label>店名</label><input v-model="S.storeDraft['店名']" placeholder="例：〇〇スーパー 駅前店" maxlength="30"></div>
    </div>
    <div class="sec" style="margin-top:4px">店舗の位置</div>
    <div class="addr"><input v-model="S.addrQ" placeholder="住所（例：東京都千代田区丸の内1-9-1）" @keydown.enter.prevent="searchAddr"><button class="btn pri" @click="searchAddr" :disabled="S.addrBusy">{{ S.addrBusy ? '…' : '探す' }}</button></div>
    <div class="list addrres" v-if="S.addrRes && S.addrRes.length > 1">
      <button v-for="(r, i) in S.addrRes" :key="i" class="item" style="grid-template-columns:30px 1fr auto" @click="pickAddr(r)"><span class="bic" v-html="svg('pin')"></span><div class="t"><b>{{ r.title }}</b></div><span class="muted">›</span></button>
    </div>
    <button class="btn" style="margin-top:8px" @click="useHere"><span style="display:inline-flex;gap:6px;align-items:center" v-html="svg('locate') + '現在地を使う'"></span></button>
    <div class="small muted" style="margin:8px 4px 0">住所で探す・現在地を使う・下の地図でお店の場所を押す、のどれかで位置を決めます</div>
    <div id="map" class="map"></div>
    <div class="coord"><span v-html="svg('pin')"></span>{{ S.storeDraft['緯度'] !== '' ? S.storeDraft['緯度'] + ', ' + S.storeDraft['経度'] : 'まだ位置がありません（任意）' }}</div>
    <button class="big" @click="saveStore">{{ S.storeDraft.ID ? '保存する' : '登録する' }}</button>
    <div class="row2" style="margin-top:10px"><button class="btn" @click="go('storeList')">もどる</button><button v-if="S.storeDraft.ID" class="btn danger" @click="deleteStore">このお店を消す</button></div>
  </template>

  <!-- ===== ジャンル ===== -->
  <template v-else-if="S.view === 'genres' && S.genreDraft">
    <div class="title">ジャンル</div>
    <div class="small muted" style="margin:0 4px 8px">左のアイコンを押すと、アイコンを選べます。↑↓ で並べかえ</div>
    <div class="list">
      <div v-for="(g, i) in S.genreDraft" :key="i" class="crow">
        <button class="cic" @click="S.pickFor = i" v-html="svg(iconKey(g))"></button>
        <input class="gname" v-model="g['名前']" placeholder="名前" maxlength="10">
        <button @click="gMove(i, -1)">↑</button><button @click="gMove(i, 1)">↓</button><button @click="S.genreDraft.splice(i, 1)">✕</button>
      </div>
    </div>
    <button class="btn" style="margin-top:10px" @click="gAdd">＋ ジャンルを追加</button>
    <div class="row2" style="margin-top:14px"><button class="btn" @click="go('menu')">やめる</button><button class="btn pri" @click="gSave">保存する</button></div>
  </template>

</div>

<!-- ジャンルの帯（入力画面だけ。画面の下、キーボードが出ているときはキーボードのすぐ上に固定。横にスクロール） -->
<div v-if="S.view === 'input'" class="gstrip">
  <button class="gedit" @mousedown.prevent @click="editGenres" aria-label="ジャンルの編集"><span v-html="svg('pencil')"></span></button>
  <div class="gdial">
    <div class="glens"></div>
    <div class="gscroll" @scroll.passive="onDial">
      <button v-for="g in sortedGenres" :key="g['名前']" class="gbtn" :data-g="g['名前']" :class="{ on: S.genre === g['名前'], auto: S.autoGenre && S.genre === g['名前'] }" @mousedown.prevent @click="pickGenre(g['名前'])">
        <span v-html="svg(iconKey(g))"></span><small>{{ g['名前'] }}</small></button>
    </div>
  </div>
  <button class="gadd" @mousedown.prevent @click="addItem"><b>追加</b><small>{{ S.genre }}</small></button>
</div>
<!-- フッター（家計簿と同じ形） -->
<nav class="foot"><button v-for="[l, ic, v] in FOOT" :key="v" :class="{ on: footOn(v) }" @click="go(v)"><span v-html="footIcon(ic === 'home' ? 'home' : ic)"></span>{{ l }}</button></nav>

<!-- アイコン選び -->
<div v-if="S.pickFor >= 0 && S.genreDraft" class="modal" @click.self="S.pickFor = -1"><div class="sheet">
  <div class="title" style="margin-top:0">アイコンをえらぶ</div>
  <div class="ipick"><button v-for="k in Object.keys(CAT_ICON).filter(k => !['store','calc','pin','locate','wallet','logout','pencil','tag','piggy'].includes(k))" :key="k"
    :class="{ on: iconKey(S.genreDraft[S.pickFor]) === k }" @click="S.genreDraft[S.pickFor]['アイコン'] = 'i:' + k; S.pickFor = -1" v-html="svg(k)"></button></div>
  <button class="btn" style="margin-top:14px" @click="S.pickFor = -1">閉じる</button>
</div></div>

<!-- 確認 -->
<div v-if="S.confirm" class="modal" @click.self="S.confirm = null"><div class="sheet center">
  <div style="font-weight:800;font-size:16px;margin:4px 0 16px;text-align:center" v-html="S.confirm.msg"></div>
  <div class="row2"><button class="btn" @click="S.confirm = null">やめる</button><button class="btn pri" style="background:var(--red);border-color:var(--red)" @click="S.confirm.fn(); S.confirm = null">{{ S.confirm.ok }}</button></div>
</div></div>

<div v-if="S.saving" class="sync">保存中…</div>
</template>
<div class="toast" :class="{ show: S.toastOn }">{{ S.toast }}</div>
`,
};
createApp(App).mount("#app");
