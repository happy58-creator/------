// 保存のしくみ。
// 環境変数 GCP_SERVICE_ACCOUNT（サービスアカウントの JSON）と KAKEIBO_SPREADSHEET_ID があれば、
// 家計簿と同じ Google スプレッドシートに保存する（シートは「買い物」「店舗」「買い物ジャンル」）。
// なければ、手元の data フォルダに JSON で保存する（試す用）。
// 追加の部品（npm のパッケージ）は使わず、Node.js に入っている機能だけで Google の API を呼ぶ。
"use strict";
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const TABLES = {
  買い物: ["ID", "品名", "ジャンル", "メモ", "店舗ID", "済", "登録日時"],
  店舗: ["ID", "店名", "緯度", "経度", "並び"],
  買い物ジャンル: ["名前", "アイコン", "並び"],
};
const LOCAL_DIR = path.join(__dirname, "data");

function account() {
  try {
    const raw = process.env.GCP_SERVICE_ACCOUNT;
    if (!raw || !process.env.KAKEIBO_SPREADSHEET_ID) return null;
    const a = JSON.parse(raw);
    return a.client_email && a.private_key ? a : null;
  } catch (e) {
    console.error("GCP_SERVICE_ACCOUNT が読めません:", e.message);
    return null;
  }
}
const usingSheets = () => !!account();

// ---- Google の認証（サービスアカウントの鍵で署名して、1時間使える合鍵をもらう）----
let tokenCache = { token: "", exp: 0 };
const b64url = (b) => Buffer.from(b).toString("base64").replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
async function accessToken() {
  if (tokenCache.token && Date.now() / 1000 < tokenCache.exp - 60) return tokenCache.token;
  const a = account();
  const now = Math.floor(Date.now() / 1000);
  const head = b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const body = b64url(JSON.stringify({ iss: a.client_email, scope: "https://www.googleapis.com/auth/spreadsheets",
    aud: a.token_uri || "https://oauth2.googleapis.com/token", iat: now, exp: now + 3600 }));
  const sig = b64url(crypto.createSign("RSA-SHA256").update(`${head}.${body}`).sign(a.private_key));
  const res = await fetch(a.token_uri || "https://oauth2.googleapis.com/token", {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion: `${head}.${body}.${sig}` }),
  });
  const j = await res.json();
  if (!res.ok) throw new Error("Google の認証に失敗しました: " + (j.error_description || j.error || res.status));
  tokenCache = { token: j.access_token, exp: now + (j.expires_in || 3600) };
  return tokenCache.token;
}
async function api(method, url, body) {
  const res = await fetch("https://sheets.googleapis.com/v4/spreadsheets/" + process.env.KAKEIBO_SPREADSHEET_ID + url, {
    method, headers: { Authorization: "Bearer " + (await accessToken()), "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await res.json().catch(() => ({}));
  if (!res.ok) { const e = new Error((j.error && j.error.message) || "Google スプレッドシートのエラー " + res.status); e.status = res.status; throw e; }
  return j;
}
const range = (name, r) => encodeURIComponent(`'${name}'!${r}`);
const checked = new Set();
async function ensureSheet(name) {
  if (checked.has(name)) return;
  const meta = await api("GET", "?fields=sheets.properties.title");
  if (!(meta.sheets || []).some((s) => s.properties.title === name)) {
    await api("POST", ":batchUpdate", { requests: [{ addSheet: { properties: { title: name } } }] });
    await api("PUT", `/values/${range(name, "A1")}?valueInputOption=RAW`, { values: [TABLES[name]] });
  }
  checked.add(name);
}

// ---- 読む・書く ----
function toRows(name, values) {
  const cols = TABLES[name];
  if (!values || !values.length) return [];
  const head = values[0];
  return values.slice(1).filter((r) => r.some((v) => v !== "")).map((r) => Object.fromEntries(cols.map((c) => [c, head.indexOf(c) >= 0 ? (r[head.indexOf(c)] ?? "") : ""])));
}
const cache = new Map();          // 表ごとの中身（保存したら作り直す）
async function load(name) {
  if (!TABLES[name]) throw new Error("知らない表: " + name);
  if (cache.has(name)) return cache.get(name);
  let rows;
  if (usingSheets()) {
    await ensureSheet(name);
    const j = await api("GET", `/values/${range(name, "A:Z")}`);
    rows = toRows(name, j.values);
  } else {
    const f = path.join(LOCAL_DIR, name + ".json");
    rows = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : [];
  }
  cache.set(name, rows);
  return rows;
}
async function save(name, rows) {
  if (!TABLES[name]) throw new Error("知らない表: " + name);
  const cols = TABLES[name];
  const clean = (rows || []).map((r) => Object.fromEntries(cols.map((c) => [c, r[c] === undefined || r[c] === null ? "" : String(r[c])])));
  if (usingSheets()) {
    await ensureSheet(name);
    await api("POST", `/values/${range(name, "A:Z")}:clear`, {});
    await api("PUT", `/values/${range(name, "A1")}?valueInputOption=RAW`, { values: [cols, ...clean.map((r) => cols.map((c) => r[c]))] });
  } else {
    fs.mkdirSync(LOCAL_DIR, { recursive: true });
    fs.writeFileSync(path.join(LOCAL_DIR, name + ".json"), JSON.stringify(clean, null, 1));
  }
  cache.set(name, clean);
  return clean;
}

module.exports = { TABLES, load, save, usingSheets };
