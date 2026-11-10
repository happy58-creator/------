// 買い物リストのサーバー（Node.js。追加の部品は使わない）
//   画面：public/ のファイル（Vue で作った画面）
//   API ：/api/login・/api/logout・/api/me・/api/data・/api/save
// ログインは家計簿と同じパスワード（環境変数 KAKEIBO_PASSWORD）で、24時間つづく。
// ログインの証明（トークン）は家計簿と同じ作り方なので、家計簿から ?t=証明 つきで開くと、そのまま入れる。
"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const store = require("./store");

const PORT = process.env.PORT || 8080;
const PUBLIC = path.join(__dirname, "public");
const LOGIN_HOURS = 24;
const PASSWORD = () => process.env.KAKEIBO_PASSWORD || "";

// ---- ログインの証明（家計簿の app.py の make_token と同じ形）----
function makeToken(exp) {
  const sig = crypto.createHmac("sha256", PASSWORD()).update(`kakeibo:${exp}`).digest("hex").slice(0, 32);
  return `${exp}.${sig}`;
}
function tokenOk(t) {
  if (!PASSWORD()) return true;                       // パスワードを決めていないとき（試す用）は、だれでも入れる
  const m = /^(\d+)\.([0-9a-f]{32})$/.exec(String(t || ""));
  if (!m || +m[1] <= Date.now() / 1000) return false;
  const good = Buffer.from(makeToken(+m[1])), got = Buffer.from(String(t));
  return good.length === got.length && crypto.timingSafeEqual(good, got);
}
function cookies(req) {
  return Object.fromEntries((req.headers.cookie || "").split(";").map((s) => s.trim().split("=")).filter((p) => p[0]).map(([k, ...v]) => [k, decodeURIComponent(v.join("="))]));
}
function cookieHeader(token, req) {
  const secure = (req.headers["x-forwarded-proto"] || "").includes("https") ? "; Secure" : "";
  if (!token) return `kb_token=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax${secure}`;
  const left = Math.max(0, +token.split(".")[0] - Math.floor(Date.now() / 1000));
  return `kb_token=${encodeURIComponent(token)}; Max-Age=${left}; Path=/; HttpOnly; SameSite=Lax${secure}`;
}
const authed = (req) => tokenOk(cookies(req).kb_token);

// ---- 返事の道具 ----
function json(res, code, obj, headers = {}) {
  res.writeHead(code, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...headers });
  res.end(JSON.stringify(obj));
}
function readBody(req) {
  return new Promise((ok, ng) => {
    let s = "";
    req.on("data", (c) => { s += c; if (s.length > 2e6) { ng(new Error("大きすぎます")); req.destroy(); } });
    req.on("end", () => { try { ok(s ? JSON.parse(s) : {}); } catch (e) { ng(e); } });
  });
}
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".png": "image/png",
  ".svg": "image/svg+xml", ".json": "application/json", ".ico": "image/x-icon", ".webp": "image/webp", ".webmanifest": "application/manifest+json" };
function sendFile(res, file) {
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" }); return res.end("見つかりません"); }
    const ext = path.extname(file);
    res.writeHead(200, { "Content-Type": TYPES[ext] || "application/octet-stream", "Cache-Control": ext === ".html" ? "no-store" : "public, max-age=3600" });
    res.end(buf);
  });
}

// ---- データ ----
const DEFAULT_GENRES = [["肉", "meat"], ["野菜", "carrot"], ["魚", "fish"], ["果物", "apple"], ["卵・乳製品", "egg"], ["豆腐・納豆", "tofu"], ["米・麺", "rice"],
  ["パン", "bread"], ["ラーメン", "bowl"], ["調味料", "bottle"], ["冷凍", "snow"], ["お菓子", "candy"], ["ジュース", "juice"], ["お酒", "beer"], ["日用品", "daily"], ["その他", "box"]];
async function allData() {
  let genres = await store.load("買い物ジャンル");
  if (!genres.length) genres = DEFAULT_GENRES.map(([n, i], k) => ({ 名前: n, アイコン: "i:" + i, 並び: String(k) }));
  return { items: await store.load("買い物"), stores: await store.load("店舗"), genres,
    sheets: store.usingSheets(), password: !!PASSWORD(), kakeiboUrl: process.env.KAKEIBO_URL || "" };
}

// ---- 道案内 ----
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  try {
    if (url.pathname.startsWith("/api/")) {
      if (req.method === "POST" && url.pathname === "/api/login") {
        const b = await readBody(req);
        const pw = Buffer.from(String(b.password || "")), good = Buffer.from(PASSWORD());
        if (!PASSWORD() || (pw.length === good.length && crypto.timingSafeEqual(pw, good))) {
          const token = makeToken(Math.floor(Date.now() / 1000) + LOGIN_HOURS * 3600);
          return json(res, 200, { ok: true, token }, { "Set-Cookie": cookieHeader(token, req) });
        }
        return json(res, 401, { ok: false, error: "パスワードがちがいます" });
      }
      if (req.method === "POST" && url.pathname === "/api/logout") return json(res, 200, { ok: true }, { "Set-Cookie": cookieHeader("", req) });
      if (url.pathname === "/api/me") return json(res, 200, { ok: authed(req), password: !!PASSWORD(), token: authed(req) ? (cookies(req).kb_token || "") : "" });
      if (!authed(req)) return json(res, 401, { ok: false, error: "ログインしてください" });
      if (req.method === "GET" && url.pathname === "/api/data") return json(res, 200, await allData());
      if (req.method === "POST" && url.pathname === "/api/save") {
        const b = await readBody(req);
        if (!store.TABLES[b.table]) return json(res, 400, { ok: false, error: "知らない表です" });
        await store.save(b.table, Array.isArray(b.rows) ? b.rows : []);
        return json(res, 200, { ok: true });
      }
      return json(res, 404, { ok: false, error: "見つかりません" });
    }
    // 家計簿から ?t=証明 つきで来たら、その証明でログインして、URL から消す
    const t = url.searchParams.get("t");
    if (t) {
      url.searchParams.delete("t");
      const to = url.pathname + (url.searchParams.toString() ? "?" + url.searchParams : "");
      res.writeHead(302, tokenOk(t) ? { Location: to, "Set-Cookie": cookieHeader(t, req) } : { Location: to });
      return res.end();
    }
    const file = path.normalize(path.join(PUBLIC, url.pathname === "/" ? "index.html" : url.pathname));
    if (!file.startsWith(PUBLIC)) { res.writeHead(403); return res.end(); }
    return sendFile(res, fs.existsSync(file) && fs.statSync(file).isFile() ? file : path.join(PUBLIC, "index.html"));
  } catch (e) {
    console.error(e);
    return json(res, 500, { ok: false, error: e.message || "エラー" });
  }
});
server.listen(PORT, () => console.log(`買い物リスト：http://localhost:${PORT}  （保存先：${store.usingSheets() ? "Google スプレッドシート" : "data フォルダ"}）`));
