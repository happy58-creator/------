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
// 店名・住所から位置をさがす（どれも無料・登録なし）
//   ・店名：OpenStreetMap の検索 2つ（Photon・Nominatim）。現在地の近くを優先して、近い順に並べる
//   ・住所：国土地理院の住所検索（日本の住所に強い。店名を入れると、名前の一部が合う町の名前を出してしまうので、住所らしいときだけ先に出す）
const ADDR_LIKE = /[0-9０-９]|丁目|番地|[都道府県](?!店)|[市区町村郡](?!店)/;
const KIND_JA = { supermarket: "スーパー", convenience: "コンビニ", mall: "ショッピングモール", department_store: "デパート", chemist: "ドラッグストア", pharmacy: "薬局",
  hardware: "ホームセンター", doityourself: "ホームセンター", greengrocer: "八百屋", butcher: "肉屋", bakery: "パン屋", alcohol: "酒屋", variety_store: "雑貨・100円ショップ", general: "お店", wholesale: "業務用" };
async function fetchJson(url, ms) {
  const c = new AbortController(), t = setTimeout(() => c.abort(), ms || 8000);
  try { const r = await fetch(url, { signal: c.signal }); return r.ok ? await r.json() : null; } catch (e) { return null; } finally { clearTimeout(t); }
}
const RANGE = 30000;        // 店名で探すときは、現在地から 30km 以内のお店だけ
function rangeBox(near) {   // 現在地のまわり 30km の四角（[西, 南, 東, 北]）
  const dLat = RANGE / 111000, dLng = RANGE / (111000 * Math.cos(near.lat * Math.PI / 180));
  return [near.lng - dLng, near.lat - dLat, near.lng + dLng, near.lat + dLat];
}
async function searchPhoton(q, near) {
  const bias = near ? `&lat=${near.lat}&lon=${near.lng}&location_bias_scale=0.3&bbox=${rangeBox(near).join(",")}` : "&lat=35.68&lon=139.76&location_bias_scale=0.1";
  const j = await fetchJson("https://photon.komoot.io/api/?limit=30&q=" + encodeURIComponent(q) + bias);
  return ((j && j.features) || []).filter(f => !f.properties.countrycode || f.properties.countrycode === "JP").map(f => {
    const p = f.properties;
    const addr = [p.state, p.county, p.city, p.district, p.locality, p.street, p.housenumber].filter(Boolean).filter((x, i, a) => a.indexOf(x) === i).join(" ");
    return { title: p.name || addr, sub: [KIND_JA[p.osm_value], addr].filter(Boolean).join("・"), lat: f.geometry.coordinates[1], lng: f.geometry.coordinates[0], shop: p.osm_key === "shop" || p.osm_key === "amenity" };
  }).filter(r => r.title);
}
async function searchNominatim(q, near) {
  const b = near && rangeBox(near), box = near ? `&viewbox=${b[0]},${b[3]},${b[2]},${b[1]}&bounded=1` : "";
  const j = await fetchJson("https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=30&countrycodes=jp&accept-language=ja&q=" + encodeURIComponent(q) + box);
  return (j || []).map(f => {
    const a = f.address || {};
    const addr = [a.province || a.state, a.county, a.city || a.town || a.village, a.suburb || a.quarter || a.neighbourhood, a.road].filter(Boolean).join(" ");
    return { title: f.name || String(f.display_name).split(",")[0], sub: [KIND_JA[f.type], addr].filter(Boolean).join("・"), lat: +f.lat, lng: +f.lon, shop: f.category === "shop" || f.category === "amenity" };
  }).filter(r => r.title);
}
async function searchGsi(q) {
  const j = await fetchJson("https://msearch.gsi.go.jp/address-search/AddressSearch?q=" + encodeURIComponent(q));
  return (j || []).slice(0, 6).map(f => ({ title: f.properties.title, sub: "住所", lat: f.geometry.coordinates[1], lng: f.geometry.coordinates[0], addr: true }));
}
const squash = t => String(t || "").normalize("NFKC").replace(/[\s・　]/g, "").toLowerCase();
const prefixLen = (a, b) => { let k = 0; while (k < a.length && k < b.length && a[k] === b[k]) k++; return k; };
const bestScore = (names, title) => Math.max(0, ...names.map(n => nameScore(n, title)));
// お店の名前（店名と別名）。別名は「、」「,」や空白で区切る（例：無印、MUJI）
const storeNames = st => st ? [String(st["店名"] || "").trim(), ...String(st["別名"] || "").split(/[,、，\s　]+/)].filter(Boolean) : [];
// 名前がどれだけ合っているか（入れた文字がぜんぶ名前に入っている＞一部だけ）
function nameScore(q, title) {
  const a = squash(q), b = squash(title);
  if (!a || !b) return 0;
  if (b === a) return 3;
  if (b.includes(a) || a.includes(b)) return 2;
  // 頭の文字が同じ（2文字以上・入れた名前の半分以上）で、そこで地図の名前が区切れているなら、同じお店の候補
  // （例：「無印良品」と「無印 博多」は○。「スーパー大栄」と「スーパーセンタートライアル」は区切れていないので×）
  const t = String(title).normalize("NFKC").toLowerCase().trim(), k = prefixLen(a, t);
  if (k >= 2 && k >= Math.ceil(a.length / 2) && (k === t.length || /[\s　・(（\-]/.test(t[k]))) return 1.6;
  let hit = 0; for (const ch of new Set(a)) if (b.includes(ch)) hit++;
  return hit / new Set(a).size;
}
// near：現在地（わかれば、そのまわり 30km だけ・近い順）。skip：もう登録してある店舗の位置（一覧に出さない）
// alias：お店の別名（店名と同じように探して、同じように合っているか見る）
async function geocode(q, near, skip, alias) {
  const addrLike = ADDR_LIKE.test(q);
  const extra = addrLike ? [] : (alias || []).filter(a => squash(a) !== squash(q)).slice(0, 2);
  const [ph, no, gs, ...ex] = await Promise.all([searchPhoton(q, near), searchNominatim(q, near), addrLike ? searchGsi(q) : Promise.resolve([]), ...extra.map(a => searchPhoton(a, near))]);
  let names = [...ph, ...no, ...ex.flat()];
  if (!names.length && !addrLike) {          // 「〇〇 須恵店」のように細かく入れて見つからないときは、最初のことば（お店の名前）で近くを探す
    const head = q.split(/[\s　]+/)[0].replace(/(本店|支店|[^\s]{1,8}店)$/, "");
    if (head && head !== q) names = [...await searchPhoton(head, near), ...await searchNominatim(head, near)];
  }
  // 同じ場所（100m 以内・同じ名前）は1つにまとめる
  const uniq = [];
  for (const r of names) if (!uniq.some(u => squash(u.title) === squash(r.title) && meters(u, r) < 150)) uniq.push(r);
  for (const r of uniq) { r.score = bestScore([q, ...extra], r.title) + (r.shop ? 0.5 : 0); r.m = near ? meters(near, r) : null; }
  if (near) uniq.splice(0, uniq.length, ...uniq.filter(r => r.m <= RANGE));
  const registered = r => (skip || []).some(b => meters(b, r) < 150);
  const hidden = uniq.filter(registered).length;
  uniq.splice(0, uniq.length, ...uniq.filter(r => !registered(r)));
  // 名前がよく合うものを先に、同じくらいなら近い順。よく合うものがあれば、名前がほとんど合わないもの（近くの学校など）は出さない
  if (uniq.some(r => r.score >= 2)) uniq.splice(0, uniq.length, ...uniq.filter(r => r.score >= 1.5));
  uniq.sort((x, y) => (Math.round(y.score * 2) - Math.round(x.score * 2)) || ((x.m ?? 0) - (y.m ?? 0)));
  let gsi = gs;
  if (!uniq.length && !gsi.length && !addrLike) gsi = await searchGsi(q);        // 何もなければ、住所としても探す
  let out = addrLike ? [...gsi, ...uniq] : [...uniq, ...gsi];          // 住所は 30km をこえても出す（住所で入れたときのため）
  if (near) {                                                          // 現在地がわかれば、ぜんぶ近い順
    for (const r of out) if (r.m == null) r.m = meters(near, r);
    out.sort((x, y) => x.m - y.m);
  }
  out = out.slice(0, 10);
  out.hidden = hidden;
  return out;
}
// 現在地をとる（携帯の位置情報）
function locate(fresh) {
  return new Promise((ok, ng) => {
    if (!navigator.geolocation) return ng(new Error("この端末では位置情報が使えません"));
    navigator.geolocation.getCurrentPosition(p => ok({ lat: p.coords.latitude, lng: p.coords.longitude, acc: p.coords.accuracy }),
      e => ng(new Error(e.code === 1 ? "位置情報の使用が許可されていません（設定で許可してください）" : "現在地がわかりませんでした")),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: fresh ? 0 : 30000 });
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
  // この画面は iframe の中。Streamlit Cloud では、さらに外側にもう1枚ページがあることがある（URL に /~/+/ がないとき）。
  // キーボードで見える範囲がせまくなるのは「いちばん外側のページ」だけなので、そこまでたどって測り、この画面の中の位置に直す
  function outer() {
    let w = window, offY = 0;
    for (let k = 0; k < 6; k++) {
      let p; try { p = w.parent; if (!p || p === w) break; void p.document; } catch (e) { break; }
      const fe = w.frameElement; if (!fe) break;
      offY += fe.getBoundingClientRect().top + (fe.clientTop || 0);
      w = p;
    }
    return { win: w, offY };
  }
  function visible() {          // この画面の中で、いま見えている範囲（上・下）
    const o = outer(), v = o.win.visualViewport;
    let top = 0, bottom = window.innerHeight;
    if (v) { top = v.offsetTop - o.offY; bottom = v.offsetTop + v.height - o.offY; }
    const own = window.visualViewport;          // この画面自身でも測って、せまい方を使う
    if (own) { top = Math.max(top, own.offsetTop); bottom = Math.min(bottom, own.offsetTop + own.height); }
    return { top, bottom };
  }
  const typing = el => el && (el.tagName === "TEXTAREA" || (el.tagName === "INPUT" && !["date", "checkbox", "radio", "button", "submit"].includes(el.type)));
  function kbHeight() {          // 画面の下からキーボードの上までの高さ（キーボードが出ていなければ 0）
    return Math.max(0, Math.round(window.innerHeight - visible().bottom));
  }
  function fit() {
    document.documentElement.style.setProperty("--kb", kbHeight() + "px");
    const el = document.activeElement, sc = getScroller();
    if (!typing(el) || !sc) return;
    const strip = document.querySelector(".gstrip"), stripH = strip ? strip.offsetHeight : 0;
    const v = visible(), top = v.top + 12, bottom = v.bottom - 16 - stripH;
    const r = el.getBoundingClientRect();
    if (r.bottom > bottom) sc.scrollTop += r.bottom - bottom;
    else if (r.top < top) sc.scrollTop -= top - r.top;
  }
  let t1, t2, poll = 0;
  document.addEventListener("focusin", e => {
    if (!typing(e.target)) return;
    document.body.classList.add("kbd");
    clearTimeout(t1); clearTimeout(t2);
    t1 = setTimeout(fit, 320); t2 = setTimeout(fit, 650);        // キーボードが出おわるのを待つ
    // キーボードの大きさが変わったこと（予測変換の行が出る・消えるなど）を知らせてこない端末もあるので、入力中はときどき測りなおす
    clearInterval(poll); let last = -1;
    poll = setInterval(() => {
      if (!typing(document.activeElement)) { clearInterval(poll); return; }
      const h = kbHeight(); if (h !== last) { last = h; fit(); }
    }, 200);
  });
  document.addEventListener("focusout", () => setTimeout(() => { if (!typing(document.activeElement)) { document.body.classList.remove("kbd"); document.documentElement.style.setProperty("--kb", kbHeight() + "px"); } }, 120));
  const seen = new Set();
  for (const v of [outer().win.visualViewport, (() => { try { return window.parent.visualViewport; } catch (e) { return null; } })(), window.visualViewport]) {
    if (!v || seen.has(v)) continue; seen.add(v);
    v.addEventListener("resize", fit); v.addEventListener("scroll", fit);
  }
}

const FOOT = [["入力", "pencil", "input"], ["一覧", "list", "list"], ["店舗別", "store", "stores"], ["計算", "calc", "calc"], ["メニュー", "home", "menu"]];
const ICON_FOOT = { home: '<circle cx="5.5" cy="12" r="1.6" fill="currentColor"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="18.5" cy="12" r="1.6" fill="currentColor"/>' };

const App = {
  setup() {
    const S = reactive({
      phase: "loading", password: false,
      view: "input", items: [], stores: [], branches: [], prices: [], genres: [], memory: [], history: [], sheets: false, autoGenre: false,
      calMonth: "", calDay: "", hereAt: 0, branchDraft: null, suggest: [], dismissed: {},
      // 入力
      genre: "", name: "", memo: "", storeId: "", prio: "0",
      // 一覧・店舗別
      listMode: "todo", storeMode: "all", storeSel: "", here: null, hereErr: "", hereBusy: false,
      // 計算
      price: "", qty: "1", lines: [], tax: "込",
      ctab: "cmp", cmp: [], taxIn: "", priceQ: "", priceSave: null, priceOpen: "", taxRateT: "8", taxDir: "in",
      // 店舗の登録・ジャンル
      storeDraft: null, genreDraft: null, pickFor: -1, addrQ: "", addrRes: null, addrBusy: false,
      toast: "", toastOn: false, saving: 0, confirm: null,
    });
    try { Object.assign(S, JSON.parse(sessionStorage.getItem("sh_state") || "{}"), { storeDraft: null, genreDraft: null, confirm: null }); } catch (e) {}
    const keep = () => { try { sessionStorage.setItem("sh_state", JSON.stringify({ view: S.view, genre: S.genre, storeId: S.storeId, listMode: S.listMode, storeMode: S.storeMode, storeSel: S.storeSel, lines: S.lines, tax: S.tax, ctab: S.ctab, cmp: S.cmp, taxRateT: S.taxRateT, taxDir: S.taxDir })); } catch (e) {} };

    let tt;
    const toast = m => { S.toast = m; S.toastOn = true; clearTimeout(tt); tt = setTimeout(() => S.toastOn = false, 2200); };

    // ---- 読み込み・保存（保存は Python に送る。届くまでは画面の中で先に変えておく） ----
    const KEY = { 買い物: "items", 店舗: "stores", 支店: "branches", 価格記録: "prices", 買い物ジャンル: "genres", 買い物の記憶: "memory", 購入記録: "history" };
    let QUEUE = [];           // Python にまだ届いていない保存
    let SERVER = null;
    function apply() {        // サーバーのデータ ＋ まだ届いていない保存
      if (!SERVER) return;
      const d = { items: SERVER.items, stores: SERVER.stores, branches: SERVER.branches || [], prices: SERVER.prices || [], genres: SERVER.genres, memory: SERVER.memory || [], history: SERVER.history || [] };
      for (const a of QUEUE) d[KEY[a.table]] = a.rows;
      Object.assign(S, d, { sheets: SERVER.sheets, password: SERVER.password });
      if (!S.genre && S.genres[0]) S.genre = S.genres[0]["名前"];
    }
    function save(table, rows) {
      QUEUE = QUEUE.filter(a => a.table !== table);         // 同じ表は、最後のものだけ送る
      QUEUE.push({ id: uid(), type: "save_table", table, rows });
      S[KEY[table]] = rows; S.saving = QUEUE.length;
      clearTimeout(sendTimer);                                // 続けて押したときは、最後に押してから3秒たってまとめて1回送る
      sendTimer = setTimeout(flush, SEND_WAIT);
    }
    const SEND_WAIT = 3000;
    let sendTimer = null;
    let typingSince = 0;
    function flush(force) {                                   // 待っている保存を送る
      clearTimeout(sendTimer); sendTimer = null;
      // 文字を打っているあいだは送らずに待つ（送ると画面が作りなおされて、キーボードや変換がじゃまされることがある）。最大 30 秒
      const el = document.activeElement, busy = el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA");
      if (force !== true && busy && QUEUE.length) {
        if (!typingSince) typingSince = Date.now();
        if (Date.now() - typingSince < 30000) { sendTimer = setTimeout(flush, 1500); return; }
      }
      typingSince = 0;
      if (QUEUE.length) SL.value({ queue: QUEUE });
    }
    document.addEventListener("focusout", () => setTimeout(() => {          // 入力が終わったら、待っていた保存を送る
      const el = document.activeElement;
      if (QUEUE.length && typingSince && !(el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA"))) { clearTimeout(sendTimer); sendTimer = setTimeout(flush, 600); }
    }, 200));
    // 画面を閉じる・ほかのアプリに切りかえるときは、待たずに送る
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") flush(true); });
    window.addEventListener("pagehide", () => flush(true));
    try { parent.addEventListener("pagehide", () => flush(true)); } catch (e) { }
    function logout() { TOKEN.clear(); clearTimeout(sendTimer); SL.value({ queue: QUEUE, logout: uid() }); }
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
    // ---- お店（店名）と店舗（支店）：1つのお店に、いくつも店舗を登録できる（例：無印良品 → イオンモール福岡店・かやの森店）
    // 前の版でお店に直接入れた位置は、そのお店の「名前なしの店舗」として扱う（編集して保存すると、店舗の表に移る）
    const hasPos = x => x && x["緯度"] !== "" && x["経度"] !== "" && x["緯度"] != null;
    const branchesOf = sid => {
      const real = S.branches.filter(b => b["店舗ID"] === sid);
      const st = storeOf(sid);
      return st && hasPos(st) ? [{ ID: "L" + sid, 店舗ID: sid, 支店名: "", 緯度: st["緯度"], 経度: st["経度"], legacy: true }, ...real] : real;
    };
    const fullName = (st, b) => (st ? st["店名"] : "") + (b && b["支店名"] ? " " + b["支店名"] : "");
    const branchLabel = b => b["支店名"] || "（店舗名なし）";
    // お店ごとに、いちばん近い店舗：[{ s, b, m }]（近い順）
    function nearestBranches(p) {
      const out = [];
      for (const st of S.stores) {
        let best = null;
        for (const b of branchesOf(st.ID)) if (hasPos(b)) { const m = meters(p, { lat: +b["緯度"], lng: +b["経度"] }); if (!best || m < best.m) best = { s: st, b, m }; }
        if (best) out.push(best);
      }
      return out.sort((a, b) => a.m - b.m);
    }
    const todo = computed(() => S.items.filter(i => !i["済"]));

    // ---- 入力 ----
    // ---- 品名とジャンルの組み合わせを覚える（同じ品名を入れたら、前のジャンルを選ぶ。ちがうジャンルで入れたら上書き） ----
    const memOf = name => { const k = normName(name); return k ? S.memory.find(m => m["キー"] === k) : null; };
    // はじめから入っている品名（words.js）：[{ 品名, よみ, ジャンル }]
    const WORDS = [];
    for (const [g, list] of Object.entries(window.SH_WORDS || {})) for (const w of list.split(/\s+/).filter(Boolean)) {
      const [n, y] = w.split("|"); WORDS.push({ 品名: n, よみ: normName(y || n), キー: normName(n), ジャンル: g });
    }
    const hasGenre = g => S.genres.some(x => x["名前"] === g);
    const genreFor = name => ((memOf(name) || WORDS.find(w => w.キー === normName(name) || w.よみ === normName(name)) || {})["ジャンル"]) || "";
    const wordOf = name => { const k = normName(name); return k ? WORDS.find(w => (w.キー === k || w.よみ === k) && hasGenre(w.ジャンル)) : null; };
    // 品名の候補：打っている文字で始まるもの（よみでも）を、前に入れたもの → 買ったもの → はじめからの順に
    const cands = computed(() => {
      const q = normName(S.name);
      if (!q) return [];
      const seen = new Set(), out = [];
      const add = (name, genre, from, yomi) => {
        const k = normName(name);
        if (!k || seen.has(k) || k === q) return;
        const y = yomi || k, hit = k.startsWith(q) || y.startsWith(q) ? 0 : (k.includes(q) || y.includes(q)) && q.length >= 2 ? 1 : -1;
        if (hit < 0) return;
        seen.add(k); out.push({ name, genre: hasGenre(genre) ? genre : "", from, hit });
      };
      const wy = n => { const w = WORDS.find(x => x.キー === normName(n)); return w ? w.よみ : ""; };
      for (const m of [...S.memory].reverse()) add(m["品名"], m["ジャンル"], 0, wy(m["品名"]));
      for (const h of [...S.history].reverse()) add(h["品名"], h["ジャンル"], 1, wy(h["品名"]));
      for (const w of WORDS) add(w.品名, w.ジャンル, 2, w.よみ);
      return out.sort((a, b) => a.hit - b.hit || a.from - b.from || a.name.length - b.name.length).slice(0, 12);
    });
    function onName(e) { S.name = e.target.value; }         // 変換中（ひらがなのまま）でも、打つたびに候補とジャンルを変える
    function pickCand(c) {
      S.name = c.name;
      const el = document.getElementById("nameIn");
      if (el) { el.value = c.name; el.focus(); }
      if (c.genre && c.genre !== S.genre) { S.genre = c.genre; S.autoGenre = true; centerGenre(); }
    }
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
        // 真ん中のピンクの枠に重なっている割合（0〜1）。重なるほど、白い文字・透明な背景になって、枠のピンクが見える
        const t = Math.max(0, Math.min(1, 1 - d / 64));
        el.style.transform = `scale(${(1.22 - k * 0.45).toFixed(3)})`;
        el.style.opacity = (1 - Math.min(1, d / 230) * 0.6).toFixed(3);
        el.style.color = `rgb(${Math.round(178 + 77 * t)},${Math.round(77 + 178 * t)},${Math.round(114 + 141 * t)})`;
        el.style.background = `rgba(255,255,255,${(1 - t).toFixed(3)})`;
        el.style.borderColor = `rgba(242,211,222,${(1 - t).toFixed(3)})`;
        el.style.boxShadow = "none";
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
    // 同じ品名を入れたら、前のジャンル（なければ、はじめからの品名のジャンル）を選ぶ。漢字でも、ひらがな・カタカナでも同じ品名とみなす
    watch(() => S.name, name => {
      const m = memOf(name) || (() => { const w = wordOf(name); return w && (memOf(w.品名) || { ジャンル: w.ジャンル }); })();
      if (m && hasGenre(m["ジャンル"])) { if (S.genre !== m["ジャンル"] || !S.autoGenre) { S.genre = m["ジャンル"]; S.autoGenre = true; centerGenre(); } }
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
    // ---- 買った記録（カレンダー）：「買った」にしたときの日時・品名と、そのとき近くにあった登録店（1km 以内）を残す ----
    const BOUGHT_NEAR = 1000;      // 買ったときに、このきょり（m）以内の登録店を「場所」にする（広いお店もあるので 1km）
    const pad2 = n => String(n).padStart(2, "0");
    const nowLocal = () => { const d = new Date(); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`; };
    async function storeHere(it) {         // いまいる登録店 { s, b }（なければ null）
      let p;
      try { p = await locate(true); S.here = p; S.hereAt = Date.now(); } catch (e) { return null; }       // 買ったその時の位置（前の位置は使わない）
      const near = nearestBranches(p).filter(x => x.m <= BOUGHT_NEAR);
      // その品に決めてあるお店の店舗が 1km 以内にあれば、そのお店（同じモールの中の別のお店とまちがえない）。なければ、いちばん近いお店
      return near.find(x => x.s.ID === it["店舗ID"]) || near[0] || null;
    }
    function toggle(it) {
      const done = !it["済"];
      save("買い物", S.items.map(x => x.ID === it.ID ? { ...x, 済: done ? "1" : "" } : x));
      if (done) {
        const rec = { ID: uid(), 日時: nowLocal(), 品ID: it.ID, 品名: it["品名"], ジャンル: it["ジャンル"], 店舗ID: "", 店名: "" };
        save("購入記録", [...S.history, rec]);
        storeHere(it).then(x => {            // 位置がわかったら、お店を書きたす（店名＋店舗名）
          if (!x) return;
          save("購入記録", S.history.map(h => h.ID === rec.ID ? { ...h, 店舗ID: x.s.ID, 店名: fullName(x.s, x.b) } : h));
        });
      } else {                               // 「買った」を取りけしたら、その記録も消す（いちばん新しいもの）
        const last = [...S.history].reverse().find(h => h["品ID"] === it.ID);
        if (last) save("購入記録", S.history.filter(h => h.ID !== last.ID));
      }
    }
    // ---- カレンダー ----
    const ymNow = () => { const d = new Date(); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}`; };
    const calMonth = computed(() => S.calMonth || ymNow());
    const calShift = n => { const [y, m] = calMonth.value.split("-").map(Number), d = new Date(y, m - 1 + n, 1); S.calMonth = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}`; S.calDay = ""; };
    const histByDay = computed(() => {
      const o = {};
      for (const h of S.history) { const day = String(h["日時"]).slice(0, 10); (o[day] = o[day] || []).push(h); }
      for (const k in o) o[k].sort((a, b) => String(b["日時"]).localeCompare(a["日時"]));
      return o;
    });
    const calCells = computed(() => {
      const [y, m] = calMonth.value.split("-").map(Number), first = new Date(y, m - 1, 1), last = new Date(y, m, 0).getDate();
      const weeks = Math.max(5, Math.ceil((first.getDay() + last) / 7)), out = [], today = nowLocal().slice(0, 10);
      for (let k = 0; k < weeks * 7; k++) {
        const d = new Date(y, m - 1, 1 - first.getDay() + k), key = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
        out.push({ key, day: d.getDate(), wd: d.getDay(), out: d.getMonth() !== m - 1, today: key === today, n: (histByDay.value[key] || []).length });
      }
      return out;
    });
    const calList = computed(() => {      // 下の一覧：日を選んでいればその日、なければその月（新しい日から）
      const days = Object.keys(histByDay.value).filter(k => S.calDay ? k === S.calDay : k.startsWith(calMonth.value)).sort().reverse();
      return days.map(k => [k, histByDay.value[k]]);
    });
    const dayLabel = k => { const d = new Date(k.slice(0, 4), +k.slice(5, 7) - 1, +k.slice(8, 10)); return `${d.getMonth() + 1}月${d.getDate()}日（${"日月火水木金土"[d.getDay()]}）`; };
    function removeHist(h) { save("購入記録", S.history.filter(x => x.ID !== h.ID)); toast("記録を消しました"); }
    function removeItem(it) { save("買い物", S.items.filter(x => x.ID !== it.ID)); toast("消しました"); }
    function clearDone() {
      const n = S.items.filter(i => i["済"]).length;
      if (!n) { toast("買ったものはありません"); return; }
      S.confirm = { msg: `買ったもの ${n}件 を一覧から消しますか？`, ok: "消す", fn: () => { save("買い物", S.items.filter(i => !i["済"])); toast("消しました"); } };
    }

    // ---- 店舗別 ----
    async function findHere(fresh) {           // 「更新」を押したときは、前の位置を使わず今の位置をとる
      S.hereBusy = true; S.hereErr = "";
      try { S.here = await locate(fresh === true); S.hereAt = Date.now(); } catch (e) { S.hereErr = e.message; S.here = null; }
      S.hereBusy = false;
      if (S.here) findUnregistered(S.here);
    }
    // ---- 未登録の店舗：買うものがあるお店で、1km 以内に登録した店舗がないとき、地図で同じ名前のお店を近くに探す ----
    // （例：無印良品は「イオンモール福岡店」だけ登録 → かやの森店の近くで「未登録の店舗です。登録しますか？」）
    const SUGGEST_MAX = 5;         // 一度に調べるお店の数（地図の検索の回数をおさえる）
    const looked = {};             // 同じ場所で同じお店を何度も調べない（約100m ごと）
    try { S.dismissed = JSON.parse(localStorage.getItem("sh_dismiss") || "{}"); } catch (e) { }
    const cell = p => `${p.lat.toFixed(3)},${p.lng.toFixed(3)}`;
    async function findUnregistered(p) {
      const want = [...new Set(todo.value.map(i => i["店舗ID"]).filter(Boolean))].map(storeOf).filter(Boolean);
      const near = new Set(nearestBranches(p).filter(x => x.m <= NEAR).map(x => x.s.ID));
      const targets = want.filter(st => !near.has(st.ID)).slice(0, SUGGEST_MAX);
      const found = [];
      await Promise.all(targets.map(async st => {
        const key = st.ID + "@" + cell(p);
        if (!(key in looked)) looked[key] = await nearbyPoi(storeNames(st), p);
        const r = looked[key];
        if (!r) return;
        if (branchesOf(st.ID).some(b => hasPos(b) && meters(r, { lat: +b["緯度"], lng: +b["経度"] }) < 200)) return;     // もう登録してある
        if (S.dismissed[st.ID + "@" + r.lat.toFixed(4) + "," + r.lng.toFixed(4)]) return;
        found.push({ s: st, ...r });
      }));
      S.suggest = found.sort((a, b) => a.m - b.m);
    }
    async function nearbyPoi(names, p) {          // p のまわり 1km で、名前が店名か別名に合うお店（いちばん近いもの）
      const dLat = 0.0095, dLng = 0.0115;
      const lists = await Promise.all(names.slice(0, 3).map(n =>
        fetchJson("https://photon.komoot.io/api/?limit=15&q=" + encodeURIComponent(n) + `&lat=${p.lat}&lon=${p.lng}&bbox=${p.lng - dLng},${p.lat - dLat},${p.lng + dLng},${p.lat + dLat}`)));
      let best = null;
      for (const j of lists) for (const f of (j && j.features) || []) {
        const pr = f.properties || {}, title = pr.name || "";
        if (bestScore(names, title) < 1.5) continue;
        const r = { title, lat: f.geometry.coordinates[1], lng: f.geometry.coordinates[0] };
        r.m = meters(p, r);
        if (r.m <= NEAR && (!best || r.m < best.m)) best = r;
      }
      return best;
    }
    // 地図の名前から、店舗名だけをとり出す（「無印良品 かやの森店」→「かやの森店」、「無印 博多」→「博多」）
    function branchFromTitle(names, title) {
      const a = String(title).normalize("NFKC");
      for (const n0 of [...names].sort((x, y) => y.length - x.length)) {
        const n = String(n0).normalize("NFKC");
        if (a.includes(n)) return a.split(n).join(" ").replace(/[\s　・()（）]+/g, " ").trim();
      }
      for (const n0 of names) {                 // 頭が同じだけのときは、同じ部分をとる
        const k = prefixLen(a, String(n0).normalize("NFKC"));
        if (k >= 2) return a.slice(k).replace(/[\s　・()（）]+/g, " ").trim();
      }
      return a;
    }
    function addSuggest(x) {
      const row = { ID: uid(), 店舗ID: x.s.ID, 支店名: branchFromTitle(storeNames(x.s), x.title), 緯度: x.lat.toFixed(6), 経度: x.lng.toFixed(6) };
      save("支店", [...S.branches, row]);
      S.suggest = S.suggest.filter(y => y !== x);
      toast(`「${fullName(x.s, row)}」を登録しました`);
    }
    function dismissSuggest(x) {
      S.dismissed = { ...S.dismissed, [x.s.ID + "@" + x.lat.toFixed(4) + "," + x.lng.toFixed(4)]: 1 };
      try { localStorage.setItem("sh_dismiss", JSON.stringify(S.dismissed)); } catch (e) { }
      S.suggest = S.suggest.filter(y => y !== x);
    }
    const nearStores = computed(() => S.here ? nearestBranches(S.here) : []);
    // 表示するお店のまとまり：[{ id, name, dist, items }]
    // 優先のもの：全店舗・現在地はぜんぶ（現在地では別のお店のものも出す）。お店を選んでいるときは、そのお店のもの
    // 1km〜3km のお店（もしかして？）
    const maybeGroups = computed(() => S.storeMode !== "here" ? [] : nearStores.value.filter(x => x.m > NEAR && x.m <= MAYBE)
      .map(x => ({ id: x.s.ID, name: fullName(x.s, x.b), dist: x.m, items: todo.value.filter(i => !prio(i) && i["店舗ID"] === x.s.ID) })));
    const prioStore = computed(() => byPrio(todo.value.filter(i => prio(i) && (S.storeMode === "here" || !S.storeSel || i["店舗ID"] === S.storeSel))));
    const storeGroups = computed(() => {
      const items = todo.value.filter(i => !prio(i));
      if (S.storeMode === "here") {
        return nearStores.value.filter(x => x.m <= NEAR).map(x => ({ id: x.s.ID, name: fullName(x.s, x.b), dist: x.m, items: items.filter(i => i["店舗ID"] === x.s.ID) }));
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
    // 単位：[そろえる単位, 何倍か, 何あたりで見せるか]。個・パック・玉などは「1個あたり」（グラムがわからないときはこちら）
    const UNITS = { g: ["g", 1, 100], kg: ["g", 1000, 100], ml: ["ml", 1, 100], L: ["ml", 1000, 100], 個: ["個", 1, 1], パック: ["パック", 1, 1], 玉: ["玉", 1, 1], 本: ["本", 1, 1], 枚: ["枚", 1, 1],
      袋: ["袋", 1, 1], 束: ["束", 1, 1], 切れ: ["切れ", 1, 1], 尾: ["尾", 1, 1], 缶: ["缶", 1, 1], ロール: ["ロール", 1, 1], 回: ["回", 1, 1] };
    const isCount = u => (UNITS[u] || UNITS.g)[2] === 1;
    const UNIT_LIST = Object.keys(UNITS);
    const LETTERS = "ABCDEFGH";
    const num = v => { const n = parseFloat(String(v ?? "").replace(/[^0-9.]/g, "")); return isFinite(n) ? n : 0; };
    function newCmp(prev) { return { id: uid(), name: "", price: "", amt: "", unit: prev ? ({ kg: "g", L: "ml" }[prev.unit] || prev.unit) : "g", pack: "1", tax: (prev && prev.tax) || "込" }; }
    if (!S.cmp.length) S.cmp = [newCmp(), newCmp()];
    // その行の「基準あたりの値段」（税込にそろえる）。比べられないときは null
    function unitInfo(c) {
      // 個・パックなどは、数を空けておくと「1」とみなす（値段だけで比べられる）
      const u = UNITS[c.unit] || UNITS.g, price = num(c.price) * (c.tax === "8" ? 1.08 : c.tax === "10" ? 1.1 : 1);
      const amt = num(c.amt) || (isCount(c.unit) ? 1 : 0), total = amt * u[1] * (isCount(c.unit) ? 1 : Math.max(1, num(c.pack) || 1));
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
    // ---- 値段の記録（お店ごとの最安値）：比べた結果を「品名・お店・1あたりの値段」で残して、別のお店で比べる ----
    const fmtPer = (v, base, per) => `${per === 1 ? "1" + base : per + base}あたり ${v < 10 ? v.toFixed(2) : v < 100 ? v.toFixed(1) : Math.round(v).toLocaleString()}円`;
    const recInfo = r => ({ v: num(r["単価"]), base: r["基準"], per: +r["基準量"] || 1 });
    function nearStoreNow() {             // いま近くにある登録店（10分以内にとった現在地で、1km 以内）
      if (!S.here || Date.now() - (S.hereAt || 0) > 600000) return null;
      const x = nearestBranches(S.here)[0];
      return x && x.m <= NEAR ? x.s : null;
    }
    // その品名の記録を、お店ごとの最安値にまとめる：[{ base, per, list: [{ sid, name, best(記録), n }] }]（そろえる単位ごと・安い順）
    function priceBook(name) {
      const k = normName(name); if (!k) return [];
      const rows = S.prices.filter(r => normName(r["品名"]) === k);
      const byBase = {};
      for (const r of rows) {
        const i = recInfo(r); if (!i.v) continue;
        const g = byBase[i.base] = byBase[i.base] || { base: i.base, per: i.per, stores: {} };
        const key = r["店舗ID"] || ("n:" + r["店名"]), cur = g.stores[key];
        if (!cur) g.stores[key] = { sid: r["店舗ID"], name: (storeOf(r["店舗ID"]) || {})["店名"] || r["店名"] || "お店未定", best: r, n: 1 };
        else { cur.n++; if (i.v < num(cur.best["単価"])) cur.best = r; }
      }
      return Object.values(byBase).map(g => ({ ...g, list: Object.values(g.stores).sort((a, b) => num(a.best["単価"]) - num(b.best["単価"])) }))
        .sort((a, b) => b.list.length - a.list.length);
    }
    // 記録の画面：品名の一覧（打った文字に合うもの。空なら新しい順）
    const priceNames = computed(() => {
      const q = normName(S.priceQ), seen = new Map();
      for (const r of [...S.prices].reverse()) {
        const k = normName(r["品名"]); if (!k || seen.has(k)) continue;
        if (q && !k.includes(q) && !(WORDS.find(w => w.キー === k) || { よみ: "" }).よみ.includes(q)) continue;
        seen.set(k, r["品名"]);
      }
      return [...seen.values()].slice(0, 40);
    });
    // 比べる行の下に出す：その品名の記録の最安（いま入れた値段とくらべて）
    function rowHint(c) {
      const book = priceBook(c.name); if (!book.length) return null;
      const me = unitInfo(c), g = (me && book.find(b => b.base === me.base)) || book[0], top = g.list[0], v = num(top.best["単価"]);
      let vs = "";
      if (me && me.base === g.base) { const d = (me.v / v - 1) * 100; vs = Math.abs(d) < 0.5 ? "記録の最安と同じ" : d > 0 ? `記録の最安より ${Math.round(d)}% 高い` : `記録の最安より ${Math.round(-d)}% 安い`; }
      return { text: `記録の最安：${top.name} ${fmtPer(v, g.base, g.per)}`, vs, cheaper: me && me.base === g.base && me.v < v };
    }
    let lastPriceSid = "";             // 前に記録したお店（近くのお店がわからないときは、これを選んでおく）
    function openSave(c) {                // 比べた行を記録する（お店を選んで保存）
      const info = unitInfo(c);
      if (!info) { toast("値段と量を入れてください"); return; }
      const st = nearStoreNow();
      const ps = S.priceSave = { c, name: c.name || "", sid: st ? st.ID : lastPriceSid, auto: !!st, touched: false };
      // いまの位置をとりなおして、近くのお店を選ぶ（自分でお店を選んだあとは変えない）
      locate().then(p => { S.here = p; S.hereAt = Date.now(); const s2 = nearStoreNow(); if (s2 && S.priceSave === ps && !ps.touched) { ps.sid = s2.ID; ps.auto = true; } }).catch(() => {});
    }
    function savePrice() {
      const ps = S.priceSave, name = String(ps.name || "").trim(), info = unitInfo(ps.c);
      if (!name) { toast("品名を入れてください"); return; }
      if (!info) { toast("値段と量を入れてください"); return; }
      const st = storeOf(ps.sid), c = ps.c;
      const row = { ID: uid(), 品名: name, 店舗ID: ps.sid || "", 店名: st ? st["店名"] : "", 値段: String(Math.round(info.price)), 量: String(num(c.amt) || (isCount(c.unit) ? 1 : "")), 単位: c.unit,
        入数: isCount(c.unit) ? "1" : String(Math.max(1, num(c.pack) || 1)), 単価: String(+info.v.toFixed(3)), 基準: info.base, 基準量: String(info.per), 日付: nowLocal().slice(0, 10) };
      save("価格記録", [...S.prices, row]);
      if (!c.name) c.name = name;
      lastPriceSid = ps.sid; S.priceSave = null;
      toast(`記録しました：${name}（${st ? st["店名"] : "お店未定"}）`); keep();
    }
    function removePrice(r) { save("価格記録", S.prices.filter(x => x.ID !== r.ID)); toast("記録を消しました"); }
    const recDetail = r => `${Number(r["値段"]).toLocaleString()}円・${isCount(r["単位"]) ? (num(r["量"]) > 1 ? r["量"] + r["単位"] : "1" + r["単位"]) : r["量"] + r["単位"] + (num(r["入数"]) > 1 ? "×" + r["入数"] : "")}・${String(r["日付"]).slice(5).replace("-", "/")}`;
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
      S.storeDraft = s ? { 別名: "", ...s } : { ID: "", 店名: "", 別名: "", 緯度: "", 経度: "", 並び: String(S.stores.length) };
      S.view = "storeEdit"; S.branchDraft = null; keep();
    }
    const draftBranches = computed(() => S.storeDraft ? (S.storeDraft.ID ? branchesOf(S.storeDraft.ID) : []) : []);
    function editBranch(b) {                 // 店舗（支店）の追加・編集。位置は店名・住所で探す／現在地／地図のピン
      const d = S.storeDraft, name = String(d["店名"] || "").trim();
      if (!name) { toast("先に店名を入れてください"); return; }
      S.branchDraft = b ? { ...b } : { ID: "", 店舗ID: d.ID, 支店名: "", 緯度: "", 経度: "" };
      S.addrQ = b ? "" : name; S.addrRes = null; S.view = "branchEdit";
      const sc = document.getElementById("app"); if (sc) sc.scrollTop = 0;
      nextTick(drawMap);
    }
    async function drawMap() {
      const el = document.getElementById("map");
      if (!el) return;
      try {
        const L = await loadLeaflet();
        if (map) { map.remove(); map = null; marker = null; }
        const d = S.branchDraft, has = d["緯度"] !== "" && d["経度"] !== "";
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
      S.branchDraft["緯度"] = lat.toFixed(6); S.branchDraft["経度"] = lng.toFixed(6);
      if (map && window.L) { if (marker) marker.setLatLng([lat, lng]); else marker = L.marker([lat, lng], { icon: pinIcon() }).addTo(map); if (move) map.setView([lat, lng], 17); }
    }
    function clearPin() {                       // 登録した位置を消す（お店は「位置なし」になり、現在地の表示に出なくなる）
      S.branchDraft["緯度"] = ""; S.branchDraft["経度"] = "";
      if (marker) { marker.remove(); marker = null; }
      toast("位置を消しました（「決定」で確定）");
    }
    async function searchAddr() {
      const q = S.addrQ.trim();
      if (!q) { toast("店名か住所を入れてください"); return; }
      S.addrBusy = true; S.addrRes = null;
      let near = S.here;
      if (!near) { try { near = S.here = await locate(); } catch (e) { } }     // 現在地の近くを優先して探す（わからなければ全国から）
      // このお店の、もう登録してある店舗（いま編集している店舗はのぞく）は一覧に出さない
      const skip = S.storeDraft && S.storeDraft.ID ? branchesOf(S.storeDraft.ID).filter(b => hasPos(b) && (!S.branchDraft || b.ID !== S.branchDraft.ID)).map(b => ({ lat: +b["緯度"], lng: +b["経度"] })) : [];
      const res = await geocode(q, near, skip, storeNames(S.storeDraft));
      S.addrBusy = false; S.addrRes = res;
      if (res.length === 1) pickAddr(res[0]);
      else if (!res.length && res.hidden) toast("見つかった店舗は、ぜんぶ登録ずみでした");
      else if (!res.length) toast(near ? "30km 以内に見つかりませんでした。店名を短くするか、住所で探すか、地図を押してください" : "見つかりませんでした。店名を短くするか、住所で探すか、地図を押してください");
    }
    function pickAddr(r) {
      setPin(r.lat, r.lng, true); S.addrRes = null;
      if (!String(S.branchDraft["支店名"] || "").trim() && S.storeDraft) {            // 店舗名が空なら、地図の名前から入れる（例：かやの森店）
        const n = branchFromTitle(storeNames(S.storeDraft), r.title);
        if (n && n !== r.title.normalize("NFKC") && !r.addr) S.branchDraft["支店名"] = n;
      }
      toast("その場所にピンを立てました");
    }
    async function useHere() {
      toast("現在地をさがしています…");
      try { const p = await locate(); S.here = p; setPin(p.lat, p.lng, true); toast("現在地を入れました"); } catch (e) { toast(e.message); }
    }
    function storeRow() {                    // 編集中のお店を表に入れる形（新しいお店なら ID をつける）。前の版の位置は消す（店舗の表に移すので）
      const d = S.storeDraft, name = String(d["店名"] || "").trim();
      if (!name) return null;
      if (!d.ID) d.ID = uid();
      return { ...d, 店名: name, 別名: storeNames({ 店名: "", 別名: d["別名"] }).join("、") };
    }
    function putStore(row, clearLegacy) {
      const r = clearLegacy ? { ...row, 緯度: "", 経度: "" } : row;
      save("店舗", S.stores.some(s => s.ID === r.ID) ? S.stores.map(s => s.ID === r.ID ? r : s) : [...S.stores, r]);
      S.storeDraft = { ...S.storeDraft, ...r };
    }
    function saveStore() {
      const isNew = !S.storeDraft.ID || !storeOf(S.storeDraft.ID);
      const row = storeRow();
      if (!row) { toast("店名を入れてください"); return; }
      putStore(row, false);
      toast(isNew ? "お店を登録しました" : "保存しました"); S.view = "storeList"; S.storeDraft = null;
    }
    function saveBranch() {
      const row = storeRow();
      if (!row) { toast("店名を入れてください"); return; }
      const b = S.branchDraft, legacy = String(b.ID).startsWith("L");
      const old = storeOf(row.ID), hadLegacy = hasPos(old);
      let list = S.branches;
      if (hadLegacy && !legacy) list = [...list, { ID: uid(), 店舗ID: row.ID, 支店名: "", 緯度: old["緯度"], 経度: old["経度"] }];   // 前の版の位置も、店舗として残す
      putStore(row, hadLegacy);                                        // お店も保存（新しいお店のときも、ここで登録される）
      const nb = { ID: b.ID && !legacy ? b.ID : uid(), 店舗ID: row.ID, 支店名: String(b["支店名"] || "").trim(), 緯度: b["緯度"], 経度: b["経度"] };
      list = list.some(x => x.ID === nb.ID) ? list.map(x => x.ID === nb.ID ? nb : x) : [...list, nb];
      save("支店", list);
      toast(`「${fullName(row, nb)}」を保存しました`); backToStore();
    }
    function deleteBranch() {
      const b = S.branchDraft, st = storeOf(b["店舗ID"]);
      S.confirm = { msg: `「${esc(fullName(st || S.storeDraft, b))}」を消しますか？`, ok: "消す", fn: () => {
        if (String(b.ID).startsWith("L")) { if (st) putStore(st, true); }
        else save("支店", S.branches.filter(x => x.ID !== b.ID));
        toast("店舗を消しました"); backToStore();
      } };
    }
    function backToStore() {
      if (map) { map.remove(); map = null; marker = null; }
      S.branchDraft = null; S.addrRes = null; S.view = "storeEdit";
    }
    function deleteStore() {
      const d = S.storeDraft;
      S.confirm = { msg: `「${esc(d["店名"])}」を消しますか？<br><span class="small muted">店舗もぜんぶ消えます。このお店の商品は「お店未定」になります</span>`, ok: "消す", fn: () => {
        save("店舗", S.stores.filter(s => s.ID !== d.ID));
        if (S.branches.some(b => b["店舗ID"] === d.ID)) save("支店", S.branches.filter(b => b["店舗ID"] !== d.ID));
        if (S.items.some(i => i["店舗ID"] === d.ID)) save("買い物", S.items.map(i => i["店舗ID"] === d.ID ? { ...i, 店舗ID: "" } : i));
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
      S.view = v; S.storeDraft = null; S.branchDraft = null; S.genreDraft = null; keep(); const sc = document.getElementById("app"); if (sc) sc.scrollTop = 0;
      if (v === "stores" && S.storeMode === "here") findHere();
    }
    const footOn = k => S.view === k || (k === "menu" && !FOOT.some(f => f[2] === S.view));
    const footIcon = k => k === "home" ? `<svg class="li" viewBox="0 0 24 24" fill="none">${ICON_FOOT.home}</svg>` : svg(k);
    function toKakeibo() { clearTimeout(sendTimer); SL.value({ queue: QUEUE, go: "kakeibo", gid: uid() }); }     // 家計簿のページへ（ログインはそのまま）

    keyboardHelper(() => document.getElementById("app"));
    SL.ready(); SL.height();
    return { S, svg, gIcon, yen, distText, NEAR, FOOT, footOn, footIcon, sortedGenres, sortedStores, todo, recent, listGroups, storeGroups, nearStores,
      taxRate, calcTotal, storeName, calMonth, calShift, calCells, calList, dayLabel, removeHist, pickGenre, memOf, onDial, cands, onName, pickCand, MAYBE, maybeGroups, searchAddr, pickAddr, prio, cyclePrio, top2, PRIO_KEY, prioStore, UNIT_LIST, LETTERS, cmpResult, unitInfo, perText, addCmp, clearCmp, isCount, fmtPer, recInfo, priceBook, priceNames, rowHint, openSave, savePrice, removePrice, recDetail, num, normName, genreFor, cycleTax, taxLabel, taxCalc, iconKey, CAT_ICON,
      logout, addItem, toggle, removeItem, clearDone, setStoreMode, findHere, addLine, clearLines,
      editStore, useHere, clearPin, saveStore, editBranch, saveBranch, deleteBranch, backToStore, draftBranches, branchesOf, branchLabel, addSuggest, dismissSuggest, hasPos, storeOf, meters, deleteStore, editGenres, gMove, gAdd, gSave, go, keep, toKakeibo };
  },
  template: `
<div v-if="S.phase === 'loading'" class="loading">読み込み中…</div>

<template v-else>
<div class="wrap">
  <button v-if="top2.length && !['storeEdit', 'branchEdit', 'genres'].includes(S.view)" class="banner" @click="go('list')">
    <span class="bstar" v-html="svg('star')"></span>
    <span class="btext"><small>最優先 {{ top2.length }}件</small><b>{{ top2.map(i => i['品名']).join('・') }}</b></span><span class="bgo">›</span>
  </button>

  <!-- ===== 入力 ===== -->
  <template v-if="S.view === 'input'">
    <div class="title">買い物リスト</div>
    <div class="card" style="padding:4px 16px">
      <div class="field"><label>品名</label><div class="namebox"><input id="nameIn" :value="S.name" @input="onName" @compositionupdate="onName" @compositionend="onName" placeholder="例：たまねぎ" maxlength="40" @keydown.enter.prevent="addItem" autocomplete="off">
        <span v-if="S.autoGenre" class="memtag" v-html="svg(iconKey(sortedGenres.find(g => g['名前'] === S.genre))) + (memOf(S.name) ? 'いつもの ' : '') + S.genre"></span></div></div>
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
        <button class="chip" @click="findHere(true)">更新</button>
      </div>
      <div v-for="x in S.suggest" :key="x.s.ID + x.lat" class="card suggest">
        <div class="sg-t"><span class="bic" v-html="svg('store')"></span><div><b>{{ x.title }}</b><span class="small muted">{{ distText(x.m) }}・{{ x.s['店名'] }}の未登録の店舗です。登録しますか？</span></div></div>
        <div class="row2"><button class="btn" @click="dismissSuggest(x)">今はしない</button><button class="btn pri" @click="addSuggest(x)">登録する</button></div>
      </div>
      <div v-if="S.here && !S.hereBusy && !storeGroups.length" class="card small muted">
        1km 以内に登録したお店はありません。<template v-if="nearStores.length && !maybeGroups.length">いちばん近いのは「{{ nearStores[0].s['店名'] }}{{ nearStores[0].b['支店名'] ? ' ' + nearStores[0].b['支店名'] : '' }}」（{{ distText(nearStores[0].m) }}）です。</template>
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
    <div class="seg"><button :class="{ on: S.ctab === 'cmp' }" @click="S.ctab = 'cmp'; keep()">比べる</button><button :class="{ on: S.ctab === 'rec' }" @click="S.ctab = 'rec'; keep()">記録</button><button :class="{ on: S.ctab === 'tax' }" @click="S.ctab = 'tax'; keep()">税込</button><button :class="{ on: S.ctab === 'sum' }" @click="S.ctab = 'sum'; keep()">合計</button></div>

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
          <input v-model="c.name" @input="keep()" placeholder="品名（記録するときに使います）" maxlength="20">
          <button class="del" v-if="S.cmp.length > 2" @click="S.cmp.splice(i, 1); keep()">✕</button></div>
        <div class="cmpin">
          <label>値段<div class="unitbox"><input v-model="c.price" @input="keep()" inputmode="decimal" placeholder="0">円</div></label>
          <button class="taxchip" @click="cycleTax(c)">{{ taxLabel(c.tax) }}</button>
        </div>
        <div class="cmpin">
          <label>{{ isCount(c.unit) ? '数' : '量' }}<div class="unitbox"><input v-model="c.amt" @input="keep()" inputmode="decimal" :placeholder="isCount(c.unit) ? '1' : '0'">
            <select v-model="c.unit" @change="keep()"><option v-for="u in UNIT_LIST" :key="u">{{ u }}</option></select></div></label>
          <label class="pack" v-if="!isCount(c.unit)">入数<div class="unitbox"><input v-model="c.pack" @input="keep()" inputmode="numeric" placeholder="1">こ</div></label>
        </div>
        <div class="per" :class="{ none: !unitInfo(c) }">{{ perText(unitInfo(c)) }}<span v-if="cmpResult.ok && cmpResult.best.i === i" class="besttag">いちばん安い</span>
          <button v-if="unitInfo(c)" class="recbtn" @click="openSave(c)">記録</button></div>
        <div v-if="rowHint(c)" class="hint" :class="{ good: rowHint(c).cheaper }">{{ rowHint(c).text }}<b v-if="rowHint(c).vs">{{ rowHint(c).vs }}</b></div>
      </div>
      <div class="row2"><button class="btn" @click="addCmp" :disabled="S.cmp.length >= LETTERS.length">＋ 比べるものを足す</button><button class="btn" @click="clearCmp">ぜんぶ消す</button></div>
      <div class="small muted" style="margin:10px 4px 0">例：A は 298円で 500g、B は 548円で 1kg → 100gあたりで比べます。入数は「3個パック」などのときに入れます。グラムがわからないものは、単位を「個」「パック」などにすると、1個あたりで比べます（数を空けると1）。「記録」でお店ごとの値段を残すと、別のお店で比べられます。値段の横のボタンで「税込・税抜+8%・税抜+10%」を切りかえると、税込にそろえて比べます</div>
    </template>

    <!-- 記録（お店ごとの最安値） -->
    <template v-else-if="S.ctab === 'rec'">
      <div class="addr" style="grid-template-columns:1fr"><input v-model="S.priceQ" placeholder="品名で探す（例：豚こま）" @input="S.priceOpen = ''"></div>
      <div v-if="!S.prices.length" class="card small muted" style="margin-top:10px">まだ記録がありません。「比べる」で値段を入れて、行の「記録」を押すと、お店ごとに残ります</div>
      <div v-else-if="!priceNames.length" class="card small muted" style="margin-top:10px">「{{ S.priceQ }}」の記録はありません</div>
      <template v-for="nm in priceNames" :key="nm">
        <div class="day recname" @click="S.priceOpen = S.priceOpen === nm ? '' : nm"><span class="bic" v-html="gIcon(genreFor(nm))"></span>{{ nm }}<span class="muted small" style="margin-left:auto">{{ S.priceOpen === nm ? '閉じる' : 'くわしく' }}</span></div>
        <div v-for="g in priceBook(nm)" :key="nm + g.base" class="list">
          <div class="small muted recbase" v-if="priceBook(nm).length > 1">{{ g.per === 1 ? '1' + g.base : g.per + g.base }}あたりで比べた記録</div>
          <div v-for="(x, k) in g.list" :key="x.sid + x.name" class="item recrow" :class="{ top: k === 0 && g.list.length > 1 }" style="grid-template-columns:1fr auto">
            <div class="t"><b>{{ x.name }}<em v-if="k === 0 && g.list.length > 1" class="besttag">最安</em></b><span>{{ recDetail(x.best) }}{{ x.n > 1 ? '（記録 ' + x.n + '件の最安）' : '' }}</span></div>
            <div class="recv">{{ fmtPer(num(x.best['単価']), g.base, g.per) }}<small v-if="k > 0">+{{ Math.round((num(x.best['単価']) / num(g.list[0].best['単価']) - 1) * 100) }}%</small></div>
          </div>
          <template v-if="S.priceOpen === nm">
            <div v-for="r in S.prices.filter(r => normName(r['品名']) === normName(nm) && recInfo(r).base === g.base).slice().reverse()" :key="r.ID" class="item recall" style="grid-template-columns:1fr auto auto">
              <div class="t"><b>{{ (storeOf(r['店舗ID']) || {})['店名'] || r['店名'] || 'お店未定' }}</b><span>{{ recDetail(r) }}</span></div>
              <div class="recv small">{{ fmtPer(num(r['単価']), g.base, g.per) }}</div>
              <button class="del" @click="removePrice(r)" aria-label="消す">✕</button>
            </div>
          </template>
        </div>
      </template>
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

  <!-- ===== カレンダー（いつ・どこで・何を買ったか） ===== -->
  <template v-else-if="S.view === 'calendar'">
    <div class="title">カレンダー</div>
    <div class="mnav"><button class="arrow" @click="calShift(-1)">‹</button>
      <div class="head">{{ +calMonth.slice(0, 4) }}年{{ +calMonth.slice(5) }}月<small>買ったもの {{ calCells.filter(c => !c.out).reduce((a, c) => a + c.n, 0) }}品</small></div>
      <button class="arrow" @click="calShift(1)">›</button></div>
    <div class="cal">
      <div v-for="(w, i) in '日月火水木金土'" :key="w" class="w" :class="{ sun: i === 0, sat: i === 6 }">{{ w }}</div>
      <button v-for="c in calCells" :key="c.key" class="c" :class="{ out: c.out, today: c.today, pick: S.calDay === c.key, has: c.n }" @click="S.calDay = S.calDay === c.key ? '' : c.key">
        <span class="n" :class="{ sun: c.wd === 0, sat: c.wd === 6 }">{{ c.day }}</span>
        <span v-if="c.n" class="cnt">{{ c.n }}品</span>
      </button>
    </div>
    <div class="sec" v-if="S.calDay">{{ dayLabel(S.calDay) }}<button class="link" @click="S.calDay = ''">月全体を見る</button></div>
    <div v-if="!calList.length" class="empty">{{ S.calDay ? 'この日に買ったものはありません' : 'この月に買ったものはありません' }}</div>
    <template v-for="[k, list] in calList" :key="k">
      <div class="day" v-if="!S.calDay">{{ dayLabel(k) }}<b>{{ list.length }}品</b></div>
      <div class="list">
        <div v-for="h in list" :key="h.ID" class="item" style="grid-template-columns:34px 1fr auto auto">
          <span class="bic" v-html="gIcon(h['ジャンル'])"></span>
          <div class="t"><b>{{ h['品名'] }}</b><span :class="{ noplace: !h['店名'] }"><span v-if="h['店名']" class="place" v-html="svg('pin') + h['店名']"></span><template v-else>場所の記録なし</template></span></div>
          <span class="time">{{ String(h['日時']).slice(11, 16) }}</span>
          <button class="del" @click="removeHist(h)" aria-label="記録を消す">✕</button>
        </div>
      </div>
    </template>
    <div class="small muted" style="margin:10px 4px 0">一覧や店舗別で「買った」にすると、ここに残ります。そのとき 1km 以内に登録したお店があれば、そのお店を場所として記録します</div>
  </template>

  <!-- ===== メニュー ===== -->
  <template v-else-if="S.view === 'menu'">
    <div class="title">メニュー</div>
    <div class="tiles">
      <button class="tile" @click="go('calendar')"><span v-html="svg('calendar')"></span>カレンダー</button>
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
        <div class="t"><b>{{ s['店名'] }}</b><span>{{ branchesOf(s.ID).length ? '店舗 ' + branchesOf(s.ID).length + '件：' + branchesOf(s.ID).map(branchLabel).join('・') : '店舗なし（現在地の表示に出ません）' }}</span></div>
        <span class="muted">›</span>
      </button>
    </div>
    <div v-else class="empty">まだありません</div>
    <button class="big" @click="editStore(null)">＋ お店を追加</button>
    <div class="small muted" style="margin:8px 4px 0">お店（例：無印良品）の中に、店舗（例：イオンモール福岡店・かやの森店）をいくつも入れられます</div>
  </template>

  <!-- ===== お店の追加・編集 ===== -->
  <template v-else-if="S.view === 'storeEdit' && S.storeDraft">
    <div class="title">{{ storeOf(S.storeDraft.ID) ? 'お店を編集' : 'お店を追加' }}</div>
    <div class="card" style="padding:4px 16px">
      <div class="field"><label>店名</label><input v-model="S.storeDraft['店名']" placeholder="例：無印良品" maxlength="30"></div>
      <div class="field"><label>別名</label><input v-model="S.storeDraft['別名']" placeholder="例：無印、MUJI（なくてもOK）" maxlength="40"></div>
    </div>
    <div class="small muted" style="margin:6px 4px 0">地図で店名がちがう書き方のとき（例：「無印 博多」）も、別名に入れておくと同じお店として見つけます</div>
    <div class="sec" style="margin-top:4px">店舗<span class="small muted">位置を入れた店舗が、現在地の表示に出ます</span></div>
    <div class="list" v-if="draftBranches.length">
      <button v-for="b in draftBranches" :key="b.ID" class="item" style="grid-template-columns:34px 1fr auto" @click="editBranch(b)">
        <span class="bic" v-html="svg('pin')"></span>
        <div class="t"><b>{{ branchLabel(b) }}</b><span>{{ hasPos(b) ? (S.here ? 'ここから ' + distText(meters(S.here, { lat: +b['緯度'], lng: +b['経度'] })) : '位置あり') : '位置なし' }}</span></div>
        <span class="muted">›</span>
      </button>
    </div>
    <div v-else class="card small muted">まだ店舗がありません。「＋ 店舗を追加」で場所を入れてください</div>
    <button class="btn" style="margin-top:8px" @click="editBranch(null)">＋ 店舗を追加</button>
    <button class="big" @click="saveStore">{{ storeOf(S.storeDraft.ID) ? '保存する' : '登録する' }}</button>
    <div class="row2" style="margin-top:10px"><button class="btn" @click="go('storeList')">もどる</button><button v-if="storeOf(S.storeDraft.ID)" class="btn danger" @click="deleteStore">このお店を消す</button></div>
  </template>

  <!-- ===== 店舗（支店）の追加・編集 ===== -->
  <template v-else-if="S.view === 'branchEdit' && S.branchDraft && S.storeDraft">
    <div class="title">{{ S.storeDraft['店名'] }}の店舗</div>
    <div class="card" style="padding:4px 16px">
      <div class="field"><label>店舗名</label><input v-model="S.branchDraft['支店名']" placeholder="例：イオンモール福岡店（なくてもOK）" maxlength="30"></div>
    </div>
    <div class="sec" style="margin-top:4px">店舗の位置</div>
    <div class="addr"><input v-model="S.addrQ" placeholder="店名か住所（例：無印良品 かやの森）" @keydown.enter.prevent="searchAddr"><button class="btn pri" @click="searchAddr" :disabled="S.addrBusy">{{ S.addrBusy ? '…' : '探す' }}</button></div>
    <div class="list addrres" v-if="S.addrRes && S.addrRes.length > 1">
      <button v-for="(r, i) in S.addrRes" :key="i" class="item" style="grid-template-columns:30px 1fr auto" @click="pickAddr(r)"><span class="bic" v-html="svg('pin')"></span><div class="t"><b>{{ r.title }}</b><span v-if="r.sub">{{ r.sub }}</span></div><span class="muted small">{{ r.m != null ? distText(r.m) : '›' }}</span></button>
    </div>
    <button class="btn" style="margin-top:8px" @click="useHere"><span style="display:inline-flex;gap:6px;align-items:center" v-html="svg('locate') + '現在地を使う'"></span></button>
    <div class="small muted" style="margin:8px 4px 0">店名・住所で探す、現在地を使う、下の地図でお店の場所を押す、のどれかで位置を決めます（現在地から近い順。店名は 30km 以内だけ。登録ずみの店舗は出ません）</div>
    <div id="map" class="map"></div>
    <div class="coord"><span v-html="svg('pin')"></span><span class="cv">{{ S.branchDraft['緯度'] !== '' ? S.branchDraft['緯度'] + ', ' + S.branchDraft['経度'] : 'まだ位置がありません' }}</span><button v-if="S.branchDraft['緯度'] !== ''" class="clearpin" @click="clearPin">位置を消す</button></div>
    <button class="big" @click="saveBranch">決定</button>
    <div class="row2" style="margin-top:10px"><button class="btn" @click="backToStore">もどる</button><button v-if="S.branchDraft.ID" class="btn danger" @click="deleteBranch">この店舗を消す</button></div>
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
  <div v-if="cands.length" class="cands" @mousedown.prevent>
    <button v-for="c in cands" :key="c.name" class="cand" :class="{ mine: c.from === 0 }" @mousedown.prevent @click="pickCand(c)">{{ c.name }}<small v-if="c.genre">{{ c.genre }}</small></button>
  </div>
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
<div v-if="S.priceSave && S.priceSave.c" class="modal" @click.self="S.priceSave = null"><div class="sheet">
  <div style="font-weight:800;font-size:17px;margin-bottom:4px">値段を記録</div>
  <div class="small muted" style="margin-bottom:10px">{{ perText(unitInfo(S.priceSave.c)) }}（{{ Math.round(unitInfo(S.priceSave.c).price).toLocaleString() }}円）</div>
  <div class="card" style="padding:4px 16px"><div class="field"><label>品名</label><input v-model="S.priceSave.name" placeholder="例：豚こま" maxlength="20"></div></div>
  <div class="sec" style="margin-top:4px">お店<span v-if="S.priceSave.auto" class="small muted">いま近くのお店を選んでいます</span></div>
  <div class="chips" style="flex-wrap:wrap">
    <button v-for="s in sortedStores" :key="s.ID" class="chip" :class="{ on: S.priceSave.sid === s.ID }" @click="S.priceSave.sid = s.ID; S.priceSave.auto = false; S.priceSave.touched = true">{{ s['店名'] }}</button>
    <button class="chip" :class="{ on: !S.priceSave.sid }" @click="S.priceSave.sid = ''; S.priceSave.auto = false; S.priceSave.touched = true">お店未定</button>
  </div>
  <div v-if="priceBook(S.priceSave.name).length" class="hint" style="margin-top:10px">{{ rowHint({ ...S.priceSave.c, name: S.priceSave.name }).text }}</div>
  <div class="row2" style="margin-top:14px"><button class="btn" @click="S.priceSave = null">やめる</button><button class="btn pri" @click="savePrice">記録する</button></div>
</div></div>
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
