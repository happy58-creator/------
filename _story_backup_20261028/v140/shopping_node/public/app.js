"use strict";
// 買い物リストの画面（Vue 3）。画面は 入力・一覧・店舗別・計算・メニュー。
// データはサーバー（/api/data・/api/save）に保存。押したらすぐ画面を変えて、保存は後ろで行う。
const { createApp, reactive, computed, nextTick } = Vue;

// ---------- 小さな道具 ----------
const uid = () => Date.now().toString(36).slice(-6) + Math.random().toString(36).slice(2, 6);
const svg = (k, cls) => `<svg class="${cls || "li"}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${CAT_ICON[k] || CAT_ICON.box}</svg>`;
const iconKey = g => { const v = String((g && g["アイコン"]) || ""); return v.startsWith("i:") && CAT_ICON[v.slice(2)] ? v.slice(2) : "box"; };
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const yen = n => "¥" + Math.round(n).toLocaleString("ja-JP");
// 2点の距離（m）
function meters(a, b) {
  const R = 6371000, r = x => x * Math.PI / 180;
  const dLat = r(b.lat - a.lat), dLng = r(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
const distText = m => m < 1000 ? `${Math.round(m / 10) * 10}m` : `${(m / 1000).toFixed(1)}km`;
const NEAR = 1000;      // 現在地から 1km 以内のお店
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
  leafletP = css("/vendor/leaflet.css").catch(() => css("https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"))
    .then(() => add("script", { src: "/vendor/leaflet.js" }).catch(() => add("script", { src: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js" })))
    .then(() => window.L);
  return leafletP;
}

// ---------- サーバーとのやりとり ----------
async function call(method, url, body) {
  const res = await fetch(url, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined, credentials: "same-origin" });
  const j = await res.json().catch(() => ({}));
  if (!res.ok) { const e = new Error(j.error || "通信エラー"); e.status = res.status; throw e; }
  return j;
}

const FOOT = [["入力", "pencil", "input"], ["一覧", "list", "list"], ["店舗別", "store", "stores"], ["計算", "calc", "calc"], ["メニュー", "home", "menu"]];
const ICON_FOOT = { home: '<circle cx="5.5" cy="12" r="1.6" fill="currentColor"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="18.5" cy="12" r="1.6" fill="currentColor"/>' };

const App = {
  setup() {
    const S = reactive({
      phase: "loading", password: false, pw: "", loginErr: "", token: "",
      view: "input", items: [], stores: [], genres: [], sheets: false, kakeiboUrl: "",
      // 入力
      genre: "", name: "", memo: "", storeId: "",
      // 一覧・店舗別
      listMode: "todo", storeMode: "all", storeSel: "", here: null, hereErr: "", hereBusy: false,
      // 計算
      price: "", qty: "1", lines: [], tax: "込",
      // 店舗の登録・ジャンル
      storeDraft: null, genreDraft: null, pickFor: -1,
      toast: "", toastOn: false, saving: 0, confirm: null,
    });
    try { Object.assign(S, JSON.parse(sessionStorage.getItem("sh_state") || "{}"), { storeDraft: null, genreDraft: null, confirm: null }); } catch (e) {}
    const keep = () => { try { sessionStorage.setItem("sh_state", JSON.stringify({ view: S.view, genre: S.genre, storeId: S.storeId, listMode: S.listMode, storeMode: S.storeMode, storeSel: S.storeSel, lines: S.lines, tax: S.tax })); } catch (e) {} };

    let tt;
    const toast = m => { S.toast = m; S.toastOn = true; clearTimeout(tt); tt = setTimeout(() => S.toastOn = false, 2200); };

    // ---- 読み込み・保存（保存は順番に、後ろで） ----
    async function loadAll() {
      const d = await call("GET", "/api/data");
      Object.assign(S, { items: d.items, stores: d.stores, genres: d.genres, sheets: d.sheets, kakeiboUrl: d.kakeiboUrl });
      if (!S.genre && S.genres[0]) S.genre = S.genres[0]["名前"];
    }
    let chain = Promise.resolve();
    function save(table, rows) {
      const key = { 買い物: "items", 店舗: "stores", 買い物ジャンル: "genres" }[table];
      S[key] = rows;
      S.saving++;
      chain = chain.then(() => call("POST", "/api/save", { table, rows })).catch(e => {
        if (e.status === 401) { S.phase = "login"; toast("ログインし直してください"); } else toast("保存できませんでした：" + e.message);
      }).finally(() => S.saving--);
    }
    async function start() {
      try {
        const me = await call("GET", "/api/me");
        S.password = me.password;
        if (!me.ok) { S.phase = "login"; return; }
        S.token = me.token;
        await loadAll(); S.phase = "app";
      } catch (e) { S.phase = "login"; S.loginErr = e.message; }
    }
    async function login() {
      S.loginErr = "";
      try { const r = await call("POST", "/api/login", { password: S.pw }); S.token = r.token; S.pw = ""; await loadAll(); S.phase = "app"; }
      catch (e) { S.loginErr = e.message; }
    }
    async function logout() { await call("POST", "/api/logout").catch(() => {}); S.phase = "login"; S.token = ""; }

    // ---- 名前で探す道具 ----
    const genreOf = name => S.genres.find(g => g["名前"] === name);
    const gIcon = name => svg(iconKey(genreOf(name)));
    const storeOf = id => S.stores.find(s => s.ID === id);
    const storeName = id => (storeOf(id) || {})["店名"] || "お店未定";
    const sortedGenres = computed(() => [...S.genres].sort((a, b) => (+a["並び"] || 0) - (+b["並び"] || 0)));
    const sortedStores = computed(() => [...S.stores].sort((a, b) => (+a["並び"] || 0) - (+b["並び"] || 0)));
    const todo = computed(() => S.items.filter(i => !i["済"]));

    // ---- 入力 ----
    function addItem() {
      const name = S.name.trim();
      if (!name) { toast("品名を入れてください"); return; }
      const row = { ID: uid(), 品名: name, ジャンル: S.genre || "その他", メモ: S.memo.trim(), 店舗ID: S.storeId, 済: "", 登録日時: new Date().toISOString().slice(0, 16).replace("T", " ") };
      save("買い物", [...S.items, row]);
      toast(`追加しました：${name}${S.storeId ? "（" + storeName(S.storeId) + "）" : ""}`);
      S.name = ""; S.memo = "";
      nextTick(() => { const el = document.getElementById("nameIn"); if (el) el.focus(); });
    }
    const recent = computed(() => [...S.items].filter(i => !i["済"]).sort((a, b) => String(b["登録日時"]).localeCompare(a["登録日時"])).slice(0, 5));

    // ---- 一覧（ジャンル別） ----
    const byGenre = list => {
      const order = sortedGenres.value.map(g => g["名前"]), o = {};
      for (const it of list) (o[it["ジャンル"] || "その他"] = o[it["ジャンル"] || "その他"] || []).push(it);
      return Object.entries(o).sort((a, b) => (order.indexOf(a[0]) + 999 * (order.indexOf(a[0]) < 0)) - (order.indexOf(b[0]) + 999 * (order.indexOf(b[0]) < 0)));
    };
    const listGroups = computed(() => byGenre(S.listMode === "todo" ? todo.value : S.items));
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
    const storeGroups = computed(() => {
      const items = todo.value;
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

    // ---- 店舗の登録（店名と位置。位置は現在地か、地図でピン） ----
    let map = null, marker = null;
    function editStore(s) {
      S.storeDraft = s ? { ...s } : { ID: "", 店名: "", 緯度: "", 経度: "", 並び: String(S.stores.length) };
      S.view = "storeEdit"; keep();
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
      S.view = v; S.storeDraft = null; S.genreDraft = null; keep(); window.scrollTo(0, 0);
      if (v === "stores" && S.storeMode === "here") findHere();
    }
    const footOn = k => S.view === k || (k === "menu" && !FOOT.some(f => f[2] === S.view));
    const footIcon = k => k === "home" ? `<svg class="li" viewBox="0 0 24 24" fill="none">${ICON_FOOT.home}</svg>` : svg(k);
    function toKakeibo() {
      const u = S.kakeiboUrl; if (!u) return;
      location.href = u + (u.includes("?") ? "&" : "?") + "kt=" + encodeURIComponent(S.token);
    }

    start();
    return { S, svg, gIcon, yen, distText, NEAR, FOOT, footOn, footIcon, sortedGenres, sortedStores, todo, recent, listGroups, storeGroups, nearStores,
      taxRate, calcTotal, storeName, iconKey, CAT_ICON,
      login, logout, addItem, toggle, removeItem, clearDone, setStoreMode, findHere, addLine, clearLines,
      editStore, useHere, saveStore, deleteStore, editGenres, gMove, gAdd, gSave, go, keep, toKakeibo };
  },
  template: `
<div v-if="S.phase === 'loading'" class="loading">読み込み中…</div>

<div v-else-if="S.phase === 'login'" class="login">
  <div class="title">買い物リスト</div>
  <form class="card" @submit.prevent="login">
    <div class="small muted" style="margin:0 2px 6px">パスワード（家計簿と同じ）</div>
    <input type="password" v-model="S.pw" autocomplete="current-password">
    <button class="big" type="submit">ひらく</button>
    <div class="err" v-if="S.loginErr">{{ S.loginErr }}</div>
  </form>
</div>

<template v-else>
<div class="wrap">

  <!-- ===== 入力 ===== -->
  <template v-if="S.view === 'input'">
    <div class="title">買い物リスト</div>
    <div class="sec" style="margin-top:0">ジャンル<button class="link" @click="editGenres">編集・追加 ›</button></div>
    <div class="genres">
      <button v-for="g in sortedGenres" :key="g['名前']" class="genre" :class="{ on: S.genre === g['名前'] }" @click="S.genre = g['名前']; keep()">
        <span v-html="svg(iconKey(g))" style="padding:0"></span><span>{{ g['名前'] }}</span></button>
      <button class="genre add" @click="editGenres"><span v-html="svg('box')" style="padding:0"></span><span>追加</span></button>
    </div>
    <div class="card" style="padding:4px 16px;margin-top:14px">
      <div class="field"><label>品名</label><input id="nameIn" v-model="S.name" placeholder="例：たまねぎ" maxlength="40" @keydown.enter.prevent="addItem"></div>
      <div class="field"><label>メモ</label><input v-model="S.memo" placeholder="任意（例：2個・特売）" maxlength="60"></div>
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
      <div class="day"><span class="bic" v-html="gIcon(g)"></span>{{ g }}<b>{{ list.length }}件</b></div>
      <div class="list">
        <div v-for="it in list" :key="it.ID" class="item" :class="{ done: it['済'] }" style="grid-template-columns:34px 1fr auto">
          <button class="mark" @click="toggle(it)" :aria-label="it['済'] ? 'もどす' : '買った'"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></button>
          <button class="t" style="text-align:left" @click="toggle(it)"><b>{{ it['品名'] }}</b><span>{{ storeName(it['店舗ID']) }}{{ it['メモ'] ? '・' + it['メモ'] : '' }}</span></button>
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
          <template v-else-if="S.here">現在地から {{ NEAR / 1000 }}km 以内のお店：<b>{{ storeGroups.length }}件</b></template>
        </div>
        <button class="chip" @click="findHere">更新</button>
      </div>
      <div v-if="S.here && !S.hereBusy && !storeGroups.length" class="card small muted">
        1km 以内に登録したお店はありません。<template v-if="nearStores.length">いちばん近いのは「{{ nearStores[0].s['店名'] }}」（{{ distText(nearStores[0].m) }}）です。</template>
      </div>
    </template>
    <template v-for="g in storeGroups" :key="g.id">
      <div class="day"><span class="bic" v-html="svg(g.id ? 'store' : 'box')"></span>{{ g.name }}<span v-if="g.dist !== null" class="dist">{{ distText(g.dist) }}</span><b>{{ g.items.length }}件</b></div>
      <div class="list">
        <div v-if="!g.items.length" class="empty small" style="padding:16px 0">このお店で買うものはありません</div>
        <div v-for="it in g.items" :key="it.ID" class="item" :class="{ done: it['済'] }">
          <button class="mark" @click="toggle(it)"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></button>
          <button class="t" style="text-align:left" @click="toggle(it)"><b>{{ it['品名'] }}</b><span>{{ it['ジャンル'] }}{{ it['メモ'] ? '・' + it['メモ'] : '' }}</span></button>
          <span class="bic" v-html="gIcon(it['ジャンル'])"></span>
        </div>
      </div>
    </template>
  </template>

  <!-- ===== 計算 ===== -->
  <template v-else-if="S.view === 'calc'">
    <div class="title">計算</div>
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
    <div class="small muted" style="margin:10px 4px 0">お店で値段を足していくための計算です（保存はしません）</div>
  </template>

  <!-- ===== メニュー ===== -->
  <template v-else-if="S.view === 'menu'">
    <div class="title">メニュー</div>
    <div class="tiles">
      <button class="tile" @click="go('storeList')"><span v-html="svg('store')"></span>お店の登録</button>
      <button class="tile" @click="editGenres"><span v-html="svg('tag')"></span>ジャンル</button>
      <button class="tile" v-if="S.kakeiboUrl" @click="toKakeibo"><span v-html="svg('wallet')"></span>家計簿へ</button>
      <button class="tile" @click="clearDone"><span v-html="svg('list')"></span>買ったものを消す</button>
    </div>
    <div class="card small" style="margin-top:14px">{{ S.sheets ? '保存先：Google スプレッドシート（家計簿と同じファイル）' : '⚠️ いまは試し用の保存です。README の手順で Google スプレッドシートにつないでください' }}</div>
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
    <button class="btn pri" @click="useHere"><span style="display:inline-flex;gap:6px;align-items:center" v-html="svg('locate') + '現在地を使う'"></span></button>
    <div class="small muted" style="margin:8px 4px 0">または、下の地図でお店の場所を押すと、そこにピンを立てます</div>
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
