"use strict";
// ===== レシート読み取り（その他 → レシート読み取り） =====
// 1) カメラ：画面の中のレシートを毎秒9回ほど調べ（位置・傾き・明るさ・手ぶれ・ピント）、全部 90% 以上を 0.5 秒保ったら自動で撮る
// 2) 撮った写真（何枚でも）を Python に渡し、Gemini に1回でまとめて読んでもらう
// 3) 品名・金額・税・個数を、カテゴリごとのグループで直して保存（家計簿の記録）。「記録」で買い物リストの値段の記録にも入れる

const R = { step: "home", shots: [], pending: "", sentAt: 0, error: "", receipts: [], seen: "" };
try { Object.assign(R, JSON.parse(sessionStorage.getItem("kb_receipt") || "{}"), { shots: [] }); } catch (e) {}
if (R.step === "wait" || R.step === "shots") R.step = R.receipts.length ? "edit" : "home";
function rkeep() { try { sessionStorage.setItem("kb_receipt", JSON.stringify({ step: R.step, pending: R.pending, receipts: R.receipts, seen: R.seen, model: R.model })); } catch (e) {} }

const MAX_SHOTS = 8;
const TAXES = [8, 10, 0];
const taxText = t => t === 0 ? "非課税" : t + "%";
// 買い物リストと同じ単位（[そろえる単位, 何倍か, 何あたりで見せるか]）
const RUNITS = { g: ["g", 1, 100], kg: ["g", 1000, 100], ml: ["ml", 1, 100], L: ["ml", 1000, 100], 個: ["個", 1, 1], パック: ["パック", 1, 1], 玉: ["玉", 1, 1], 本: ["本", 1, 1], 枚: ["枚", 1, 1],
  袋: ["袋", 1, 1], 束: ["束", 1, 1], 切れ: ["切れ", 1, 1], 尾: ["尾", 1, 1], 缶: ["缶", 1, 1], ロール: ["ロール", 1, 1], 回: ["回", 1, 1] };
const rIsCount = u => (RUNITS[u] || RUNITS.g)[2] === 1;
const rnum = v => { const n = parseFloat(String(v ?? "").replace(/[^0-9.\-]/g, "")); return isFinite(n) ? n : 0; };
const normKey = s => String(s || "").normalize("NFKC").toLowerCase().replace(/[\s　]/g, "");
const nowStamp = () => { const d = new Date(); return `${ymd(d)} ${pad(d.getHours())}:${pad(d.getMinutes())}`; };

// ---------------------------------------------------------------- 計算
const lineExact = (rc, it) => rnum(it.price) * (rc.tax_mode === "外税" ? 1 + (+it.tax || 0) / 100 : 1);
const lineYen = (rc, it) => Math.round(lineExact(rc, it));
function receiptCalc(rc) {          // レシートと同じ出し方の合計（外税は税率ごとに1円未満を切りすて）
  if (rc.tax_mode !== "外税") return rc.items.reduce((a, it) => a + Math.round(rnum(it.price)), 0);
  const by = {};
  rc.items.forEach(it => by[+it.tax || 0] = (by[+it.tax || 0] || 0) + rnum(it.price));
  return Object.entries(by).reduce((a, [t, s]) => a + Math.round(s) + Math.floor(s * t / 100), 0);
}
const groupCats = rc => [...new Set(rc.items.map(it => it.cat))];
function groupAlloc(rc) {            // グループごとの金額（合計がレシートの合計とぴったり合うように、端数を配る）
  const cs = groupCats(rc), ex = cs.map(c => rc.items.filter(it => it.cat === c).reduce((a, it) => a + lineExact(rc, it), 0));
  const total = receiptCalc(rc), fl = ex.map(Math.floor);
  let rest = total - fl.reduce((a, b) => a + b, 0);
  const order = ex.map((v, i) => [v - Math.floor(v), i]).sort((a, b) => b[0] - a[0]);
  for (let k = 0; rest > 0 && k < order.length * 3; k++, rest--) fl[order[k % order.length][1]]++;
  for (let k = 0; rest < 0 && k < order.length * 3; k++, rest++) fl[order[order.length - 1 - (k % order.length)][1]]--;
  return Object.fromEntries(cs.map((c, i) => [c, fl[i]]));
}
const groupAmt = (rc, c) => { const o = (rc.amt || {})[c]; return o !== undefined && o !== "" ? int(o) : groupAlloc(rc)[c] || 0; };
const receiptSum = rc => groupCats(rc).reduce((a, c) => a + groupAmt(rc, c), 0);
const grandTotal = () => R.receipts.reduce((a, rc) => a + receiptSum(rc), 0);

// ---------------------------------------------------------------- 読み取り結果を、直す画面の形にする
function matchStore(name) {
  const t = normKey(name);
  let best = null, len = 0;
  for (const s of D.stores || []) {
    for (const n of [s["店名"], ...String(s["別名"] || "").split(/[、,，・\/\s]+/)]) {
      const k = normKey(n);
      if (k.length >= 2 && t.includes(k) && k.length > len) { best = s; len = k.length; }
    }
  }
  return best ? best.ID : "";
}
function fromResult(list) {
  const exp = cats(EXP).map(c => c["名前"]);
  const fallback = exp.includes("食費") ? "食費" : exp[0] || "その他";
  const memo = Object.fromEntries((D.rmemo || []).map(m => [m["キー"], m]));
  return list.map(r => {
    const items = r.items.map(it => {
      const key = normKey(it.raw || it.name), m = memo[key];
      let name = it.name || it.raw, cat = exp.includes(it.category) ? it.category : fallback, mem = false;
      if (m) { if (m["品名"]) name = m["品名"]; if (exp.includes(m["カテゴリ"])) cat = m["カテゴリ"]; mem = true; }
      return { k: uid(), key, raw: it.raw || "", name, price: String(it.price), qty: String(it.qty || 1), tax: TAXES.includes(+it.tax) ? +it.tax : 8, cat, unsure: !!it.unsure && !mem, mem, oname: name, ocat: cat, rec: false };
    });
    const pay = r.payment === "クレカ" ? CARD : r.payment === "現金" ? CASH : S.pay || CASH;
    return { id: uid(), store: [r.store, r.branch].filter(Boolean).join(" "), date: r.date || today(), tax_mode: r.tax_mode === "外税" ? "外税" : "内税",
      total: +r.total || 0, pay, sid: matchStore(`${r.store} ${r.branch}`), items, amt: {} };
  });
}

// ---------------------------------------------------------------- 画面
V.other = () => `<div class="title">その他</div>
  <div class="list">
    <button class="item tap" data-go="receipt"><div class="ic">${svgIcon("camera")}</div><div class="t"><b>レシート読み取り</b><span>撮るだけで品名・金額を読みとって記録</span></div><div class="v"><i class="chev">›</i></div><span></span></button>
  </div>`;

V.receipt = () => {
  if (R.step === "wait") return `<div class="title">撮影入力</div>
    <div class="card rwait"><div class="spin"></div><b>読みとっています…</b><div class="small muted">${R.shots.length || ""}${R.shots.length ? "枚の写真を" : ""}まとめて送りました。10〜30秒ほどかかります（うまくいかないときは、予備のAIで1回だけ読みなおします）</div></div>`;
  if (R.step === "edit") return editView();
  const shots = R.shots.length ? `<div class="sec">撮った写真（${R.shots.length}枚）</div>
    <div class="rshots">${R.shots.map((s, i) => `<div class="rshot"><img src="${s.thumb}" alt=""><button data-r="delshot" data-i="${i}" aria-label="消す">✕</button></div>`).join("")}</div>` : "";
  return `<div class="title">撮影入力</div>
    ${R.error ? `<div class="alert">⚠️ <span>${esc(R.error)}</span></div>` : ""}
    ${!D.ocr ? `<div class="alert">⚠️ <span>AIのカギ（GEMINI_API_KEY）が設定されていないので、読み取りが使えません</span></div>` : ""}
    ${R.shots.length ? "" : `<div class="card small muted" style="line-height:1.7">カメラを向けると、レシートの位置・傾き・明るさ・ピントを自動で調べて、読みとりやすい状態が0.5秒続いたら自動で撮ります。長いレシートは上から順に何枚かに分けて撮ってください。ちがうレシートも続けて撮れます（まとめて1回で読みとります）</div>`}
    ${shots}
    <button class="big pink" data-r="cam">${R.shots.length ? "もう1枚撮る" : "カメラで撮る"}</button>
    <label class="btn rpick">写真から選ぶ<input type="file" accept="image/*" multiple data-r="file"></label>
    ${R.shots.length ? `<button class="big blue" data-r="send" ${D.ocr ? "" : "disabled"}>読みとる（${R.shots.length}枚をまとめて送る）</button>` : ""}
    ${R.receipts.length ? `<button class="btn" style="margin-top:10px" data-r="resume">前の読み取り結果にもどる</button>` : ""}`;
};

function editView() {
  const exp = cats(EXP);
  const icon = c => svgIcon(iconKey(exp.find(x => x["名前"] === c) || { 名前: c }));
  const body = R.receipts.map((rc, i) => {
    const calc = receiptCalc(rc), diff = rc.total ? calc - rc.total : 0;
    const groups = groupCats(rc).map(c => {
      const own = (rc.amt || {})[c] !== undefined && rc.amt[c] !== "";
      const lines = rc.items.map((it, j) => it.cat !== c ? "" : `<div class="rline ${it.unsure ? "unsure" : ""}">
        <div class="rl1"><input data-ri="${i}|${j}|name" value="${esc(it.name)}" placeholder="品名" maxlength="40">
          <button class="rrec ${it.rec ? "done" : ""}" data-r="rec" data-i="${i}" data-j="${j}">${it.rec ? "記録済" : "記録"}</button></div>
        <div class="rl2"><label class="ryen"><input data-ri="${i}|${j}|price" inputmode="numeric" value="${esc(it.price)}" placeholder="0">円</label>
          <button class="rtax t${it.tax}" data-r="tax" data-i="${i}" data-j="${j}">${taxText(it.tax)}</button>
          <label class="rqty">×<input data-ri="${i}|${j}|qty" inputmode="numeric" value="${esc(it.qty)}" placeholder="1"></label>
          <button class="rmove" data-r="move" data-i="${i}" data-j="${j}" aria-label="カテゴリを変える">${icon(it.cat)}</button>
          <button class="rdel" data-r="dline" data-i="${i}" data-j="${j}" aria-label="消す">✕</button></div>
        ${it.raw && normKey(it.raw) !== normKey(it.name) || it.unsure || it.mem ? `<div class="rraw">${it.raw ? `レシート：${esc(it.raw)}` : ""}${it.unsure ? `<i class="runsure">要確認</i>` : ""}${it.mem ? `<i class="rmem">覚えた直し方</i>` : ""}${rc.tax_mode === "外税" ? `<span>税込 ${yen(lineYen(rc, it))}</span>` : ""}</div>`
          : rc.tax_mode === "外税" ? `<div class="rraw"><span>税込 ${yen(lineYen(rc, it))}</span></div>` : ""}
      </div>`).join("");
      return `<div class="rgroup"><div class="ghead"><button class="gcat" data-r="gcat" data-i="${i}" data-c="${esc(c)}"><span class="bic">${icon(c)}</span><b>${esc(c)}</b><i class="chev">▾</i></button>
          <label class="gamt ${own ? "own" : ""}">まとめて<input data-rg="${i}" data-c="${esc(c)}" inputmode="numeric" value="${groupAmt(rc, c)}">円</label></div>
        ${own ? `<div class="gnote">計算では ${yen(groupAlloc(rc)[c] || 0)}・<button data-r="greset" data-i="${i}" data-c="${esc(c)}">計算にもどす</button></div>` : ""}
        ${lines}<button class="radd" data-r="addline" data-i="${i}" data-c="${esc(c)}">＋ 行を足す</button></div>`;
    }).join("");
    return `<div class="rcard">
      <div class="card rhead">
        <div class="field"><label>お店</label><input data-rh="${i}|store" value="${esc(rc.store)}" placeholder="お店の名前" maxlength="40"></div>
        <div class="field"><label>日付</label><input type="date" data-rh="${i}|date" value="${esc(rc.date)}"></div>
        <div class="rbtns"><button class="paybtn ${rc.pay === CARD ? "is-card" : rc.pay === FURI ? "is-furi" : ""}" data-r="pay" data-i="${i}">${rc.pay}</button>
          <button class="rmode" data-r="mode" data-i="${i}">${rc.tax_mode}</button>
          <span class="rsumline" id="rsum${i}">${sumLine(rc)}</span></div>
      </div>
      ${groups || `<div class="empty">品物がありません</div>`}
      <div class="rfoot"><button class="radd" data-r="addline" data-i="${i}" data-c="">＋ 品物を足す</button><button class="rdrop" data-r="dropr" data-i="${i}">このレシートを外す</button></div>
    </div>`;
  }).join("");
  return `<button class="rback" data-go="home">‹ もどる（結果は残ります）</button><div class="title">読み取り結果</div>
    <div class="small muted" style="margin:-6px 4px 10px">直してから下の「保存」を押してください。行の右のアイコンでカテゴリを変えると、そのグループに移ります。「記録」で買い物リストの値段の記録に入れます</div>
    ${/lite/.test(R.model || "") ? `<div class="alert">ℹ️ <span>いつものAIが混んでいたので、予備のAI（軽いもの）で読みました。品名や金額をいつもより念入りに見てください</span></div>` : ""}
    ${body}
    <div class="rtotal"><span>合計</span><b id="rgrand">${yen(grandTotal())}</b></div>
    <button class="big pink" data-r="save">保存する（家計簿に記録）</button>
    <button class="btn" style="margin-top:10px" data-r="discard">読み取り結果を消す</button>
    <div class="foot rbar"><span>合計 <b id="rgrand2">${yen(grandTotal())}</b></span><button data-r="save">保存</button></div>`;
}
function sumLine(rc) {
  const calc = receiptCalc(rc), diff = rc.total ? calc - rc.total : 0, own = receiptSum(rc);
  return (own !== calc ? `<b style="color:#b24d72">まとめ金額で ${yen(own)}</b><br>` : "") + (rc.total ? (diff ? `<b class="exp">レシート ${yen(rc.total)}・差 ${yen(diff, true)}</b>` : `<span class="ok">レシート ${yen(rc.total)} と一致</span>`) : `<span>計算 ${yen(calc)}</span>`);
}
const memoOf = (head, names) => ((head ? head + "：" : "") + names.join("・")).slice(0, 60);
// 入力中は全部を書きかえない（キーボードが閉じないように）。合計などだけ直す
function refreshTotals() {
  R.receipts.forEach((rc, i) => {
    const el = document.getElementById("rsum" + i); if (el) el.innerHTML = sumLine(rc);
    appEl.querySelectorAll(`[data-rg="${i}"]`).forEach(inp => { if (inp !== document.activeElement) inp.value = groupAmt(rc, inp.dataset.c); });
  });
  ["rgrand", "rgrand2"].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = yen(grandTotal()); });
}

// ---------------------------------------------------------------- 記録（買い物リストの値段の記録）
let recDraft = null;
function openRec(i, j) {
  const rc = R.receipts[i], it = rc.items[j];
  openRecWith({ name: it.name, price: lineYen(rc, it), qty: it.qty, sid: rc.sid, date: rc.date, done: sid => { it.rec = true; if (!rc.sid && sid) rc.sid = sid; rkeep(); } });
}
// 値段の記録の下書き（o：name, price, qty, sid, date, done(sid)：記録したあとにすること）
function openRecWith(o) {
  const last = (D.units || {})[o.name] || [];
  const unit = RUNITS[last[0]] ? last[0] : "個", qty = Math.max(1, int(o.qty) || 1);
  recDraft = { name: o.name, price: String(o.price), qty, unit, amt: rIsCount(unit) ? String(qty) : String(last[1] || ""),
    pack: rIsCount(unit) ? "1" : String(qty > 1 ? qty : (last[2] || 1)), sid: o.sid || "", memo: "レシートから", date: o.date || today(), done: o.done };
  drawRec();
}
function recInfo() {
  const d = recDraft, u = RUNITS[d.unit] || RUNITS.g, price = rnum(d.price);
  const amt = rnum(d.amt) || (rIsCount(d.unit) ? 1 : 0), total = amt * u[1] * (rIsCount(d.unit) ? 1 : Math.max(1, rnum(d.pack) || 1));
  if (!price || !total) return null;
  return { base: u[0], per: u[2], v: price / total * u[2], price };
}
const perLabel = x => x ? `${x.per === 1 ? "1" + x.base : x.per + x.base}あたり ${x.v < 10 ? x.v.toFixed(2) : x.v < 100 ? x.v.toFixed(1) : Math.round(x.v).toLocaleString()}円` : "値段と量を入れると、1あたりの値段が出ます";
function drawRec() {
  const d = recDraft, cnt = rIsCount(d.unit);
  modal(`<div class="title" style="margin-top:0">値段を記録</div>
    <div class="small muted" style="margin:-8px 4px 10px;text-align:center">買い物リストの「計算」の記録に入ります</div>
    <div class="card" style="padding:4px 16px">
      <div class="field"><label>品名</label><input data-rd="name" value="${esc(d.name)}" maxlength="40"></div>
      <div class="field"><label>値段</label><div class="amount" style="font-size:18px"><input data-rd="price" inputmode="numeric" style="font-size:18px" value="${esc(d.price)}">円<span class="small muted" style="font-weight:600;margin-left:6px">税込</span></div></div>
      <div class="field"><label>${cnt ? "数" : "量"}</label><div class="amount" style="font-size:18px"><input data-rd="amt" inputmode="decimal" style="font-size:18px" value="${esc(d.amt)}" placeholder="${cnt ? "1" : "例：300"}">
        <select data-rd="unit" class="runit">${Object.keys(RUNITS).map(u => `<option ${u === d.unit ? "selected" : ""}>${u}</option>`).join("")}</select></div></div>
      ${cnt ? "" : `<div class="field"><label>入数</label><div class="amount" style="font-size:18px"><input data-rd="pack" inputmode="numeric" style="font-size:18px" value="${esc(d.pack)}" placeholder="1">こ</div></div>`}
      <div class="field"><label>お店</label><select data-rd="sid"><option value="">お店未定</option>${(D.stores || []).map(s => `<option value="${esc(s.ID)}" ${s.ID === d.sid ? "selected" : ""}>${esc(s["店名"])}</option>`).join("")}</select></div>
      <div class="field"><label>メモ</label><input data-rd="memo" value="${esc(d.memo)}" maxlength="40" placeholder="任意"></div>
    </div>
    <div class="small muted" id="rper" style="margin:-4px 4px 10px">${perLabel(recInfo())}</div>
    ${(D.stores || []).length ? "" : `<div class="small muted" style="margin:-4px 4px 10px">お店は、買い物リストの「店舗」で登録したお店から選べます</div>`}
    <div class="row2"><button class="btn" data-r="mclose">やめる</button><button class="btn pri pink" data-r="recsave">記録する</button></div>`);
}
function saveRec() {
  const d = recDraft, name = String(d.name || "").trim(), info = recInfo();
  if (!name) { toast("品名を入れてください"); return; }
  if (!info) { toast(rIsCount(d.unit) ? "値段を入れてください" : "値段と量を入れてください"); return; }
  const st = (D.stores || []).find(s => s.ID === d.sid);
  act({ type: "add_price", row: { ID: uid(), 品名: name, 店舗ID: d.sid || "", 店名: st ? st["店名"] : "", 値段: String(Math.round(info.price)),
    量: String(rnum(d.amt) || (rIsCount(d.unit) ? 1 : "")), 単位: d.unit, 入数: rIsCount(d.unit) ? "1" : String(Math.max(1, rnum(d.pack) || 1)),
    単価: String(+info.v.toFixed(3)), 基準: info.base, 基準量: String(info.per), 日付: d.date || today(), メモ: String(d.memo || "").trim() } });
  D.units = { ...(D.units || {}), [name]: [d.unit, d.amt, d.pack] };
  closeModal();
  if (d.done) d.done(d.sid);
  toast(`記録しました：${name}（${st ? st["店名"] : "お店未定"}）`); render(true);
}

// ---------------------------------------------------------------- 一覧・カレンダーから明細を見る（撮影入力で保存した記録）
function detailOf(r) { try { const d = JSON.parse(r["明細"] || ""); return d && Array.isArray(d.i) ? d : null; } catch (e) { return null; } }
function detailCount(r) { const d = r["明細"] ? detailOf(r) : null; return d ? d.i.length : 0; }
let detailId = "";
function openDetail(id) {
  const r = D.records.find(x => x.ID === id), d = r && detailOf(r);
  if (!d) { closeModal(); return; }
  detailId = id;
  const exp = cats(EXP), icon = c => svgIcon(iconKey(exp.find(x => x["名前"] === c) || { 名前: c }));
  const sum = d.i.reduce((a, it) => a + int(it.p), 0);
  modal(`<div class="dhead"><div class="ic">${icon(r["カテゴリ"])}</div><div><b>${esc(r["カテゴリ"])}</b><span>${dlabel(r["日付"])}${d.s ? "・" + esc(d.s) : ""}・${esc(payOf(r))}</span></div><div class="v exp">${yen(int(r["金額"]))}</div></div>
    <div class="dlist">${d.i.map((it, j) => `<div class="drow">
      <div class="dn"><b>${esc(it.n)}</b><span>${it.q > 1 ? `×${it.q}・` : ""}${taxText(+it.t || 0)}</span></div>
      <div class="dp">${yen(int(it.p))}</div>
      <button class="rmove" data-r="dmove" data-j="${j}" aria-label="カテゴリを変える">${icon(r["カテゴリ"])}</button>
      <button class="rrec ${it.rec ? "done" : ""}" data-r="drec" data-j="${j}">${it.rec ? "記録済" : "記録"}</button></div>`).join("")}</div>
    ${sum !== int(r["金額"]) ? `<div class="small muted" style="margin:6px 4px 0">品物の合計 ${yen(sum)}（まとめ金額・端数のちがいがあります）</div>` : ""}
    <div class="small muted" style="margin:8px 4px 12px">品物のアイコンでカテゴリを変えると、その品物の金額がそのカテゴリの記録へ移ります。「記録」で買い物リストの値段の記録に入れます</div>
    <div class="row2"><button class="btn" data-r="dcat">全部のカテゴリを変える</button><button class="btn pri pink" data-r="mclose">閉じる</button></div>`);
}
// 同じレシートで、そのカテゴリの記録（なければ作る）
function siblingOf(r, d, cat) {
  return D.records.find(x => x.ID !== r.ID && x["カテゴリ"] === cat && x["種類"] === r["種類"] && (detailOf(x) || {}).r === d.r && d.r) || null;
}
function moveItem(j, cat) {
  const r = D.records.find(x => x.ID === detailId), d = r && detailOf(r); if (!d || !d.i[j] || r["カテゴリ"] === cat) return;
  const it = d.i[j], from = { ...r }, fd = { ...d, i: d.i.filter((_, k) => k !== j) };
  let to = siblingOf(r, d, cat), isNew = !to;
  to = to ? { ...to } : { ID: uid(), 日付: r["日付"], 種類: r["種類"], 金額: 0, カテゴリ: cat, メモ: "", 支払方法: r["支払方法"], 登録日時: r["登録日時"], 明細: JSON.stringify({ ...d, i: [] }) };
  const td = detailOf(to); td.i.push(it);
  let move = int(it.p);
  if (!fd.i.length) move = int(from["金額"]);              // 最後の品物：残りの金額（端数）もいっしょに移す
  from["金額"] = int(from["金額"]) - move; to["金額"] = int(to["金額"]) + move;
  from["明細"] = JSON.stringify(fd); from["メモ"] = memoOf(d.s, fd.i.map(x => x.n));
  to["明細"] = JSON.stringify(td); to["メモ"] = memoOf(td.s, td.i.map(x => x.n));
  const gone = !fd.i.length;
  act({ type: "update_records", rows: [...(gone ? [] : [from]), ...(isNew ? [] : [to])], add: isNew ? [to] : [], del: gone ? [r.ID] : [] });
  if (it.k) act({ type: "save_receipt_memo", rows: [{ キー: it.k, 品名: it.n, カテゴリ: cat, 更新: today() }] });     // 次のレシートから、このカテゴリにする
  toast(`「${it.n}」を${cat}へ移しました`);
  if (gone) closeModal(); else openDetail(r.ID);
}
function recatAll(cat) {
  const r = D.records.find(x => x.ID === detailId), d = r && detailOf(r); if (!d || r["カテゴリ"] === cat) return;
  const to = siblingOf(r, d, cat);
  if (to) {           // 同じレシートの同じカテゴリがあれば、ひとつにまとめる
    const td = detailOf(to), nd = { ...td, i: [...td.i, ...d.i] };
    act({ type: "update_records", rows: [{ ...to, 金額: int(to["金額"]) + int(r["金額"]), 明細: JSON.stringify(nd), メモ: memoOf(nd.s, nd.i.map(x => x.n)) }], del: [r.ID] });
    openDetail(to.ID);
  } else {
    act({ type: "update_records", rows: [{ ...r, カテゴリ: cat }] });
    openDetail(r.ID);
  }
  const memo = d.i.filter(it => it.k).map(it => ({ キー: it.k, 品名: it.n, カテゴリ: cat, 更新: today() }));
  if (memo.length) act({ type: "save_receipt_memo", rows: memo });
  toast(`${cat}に変えました`);
}
function recFromDetail(j) {
  const r = D.records.find(x => x.ID === detailId), d = r && detailOf(r), it = d && d.i[j]; if (!it) return;
  const id = r.ID;
  openRecWith({ name: it.n, price: it.p, qty: it.q, sid: d.sid, date: r["日付"], done: sid => {
    const cur = D.records.find(x => x.ID === id), cd = cur && detailOf(cur); if (!cd || !cd.i[j]) return;
    cd.i[j] = { ...cd.i[j], rec: 1 }; if (!cd.sid && sid) cd.sid = sid;
    act({ type: "update_records", rows: [{ ...cur, 明細: JSON.stringify(cd) }] });
    setTimeout(() => openDetail(id), 50);
  } });
}

// ---------------------------------------------------------------- カテゴリを選ぶ
let catPick = null;
function pickCat(title, cur, fn) {
  catPick = fn;
  modal(`<div class="title" style="margin-top:0">${title}</div>
    <div class="cats">${cats(EXP).map(c => `<button class="cat ${c["名前"] === cur ? "on" : ""}" data-r="catok" data-v="${esc(c["名前"])}">${svgIcon(iconKey(c), "ic")}<span>${esc(c["名前"])}</span></button>`).join("")}</div>
    <button class="btn" style="margin-top:14px" data-r="mclose">閉じる</button>`);
}

// ---------------------------------------------------------------- 保存
function saveAll() {
  const recs = [], memo = [], stamp = nowStamp();
  let skipped = 0;
  for (const rc of R.receipts) {
    for (const c of groupCats(rc)) {
      const amt = groupAmt(rc, c), names = rc.items.filter(it => it.cat === c).map(it => String(it.name).trim()).filter(Boolean);
      if (amt <= 0) { skipped++; continue; }
      const head = String(rc.store || "").trim();
      const det = { r: rc.id, s: head, sid: rc.sid || "", i: rc.items.filter(it => it.cat === c && String(it.name).trim()).map(it => ({
        n: String(it.name).trim(), p: lineYen(rc, it), q: Math.max(1, int(it.qty) || 1), t: +it.tax || 0, k: it.key || "", ...(it.rec ? { rec: 1 } : {}) })) };
      recs.push({ ID: uid(), 日付: rc.date || today(), 種類: EXP, 金額: amt, カテゴリ: c, メモ: memoOf(head, names), 支払方法: rc.pay, 登録日時: stamp, 明細: JSON.stringify(det) });
    }
    for (const it of rc.items) {
      const name = String(it.name).trim();
      if (it.key && name && (name !== it.oname || it.cat !== it.ocat)) memo.push({ キー: it.key, 品名: name, カテゴリ: it.cat, 更新: today() });
    }
  }
  if (!recs.length) { toast("保存する金額がありません"); return; }
  act({ type: "add_records", recs });
  if (memo.length) act({ type: "save_receipt_memo", rows: memo });
  const total = recs.reduce((a, r) => a + r["金額"], 0);
  R.receipts = []; R.step = "home"; rkeep();
  toast(`${recs.length}件を記録しました（${yen(total)}）${skipped ? "・0円以下のグループは外しました" : ""}`);
  go("list");
}

// ---------------------------------------------------------------- 写真を送る
function sendShots() {
  if (!R.shots.length) return;
  if (!D.ocr) { toast("AIのカギが設定されていません"); return; }
  R.pending = uid(); R.sentAt = Date.now(); R.error = ""; R.step = "wait"; rkeep();
  SL.value({ queue: QUEUE, ocr: { id: R.pending, images: R.shots.map(s => s.url) } });
  render();
  setTimeout(() => { if (R.step === "wait" && Date.now() - R.sentAt >= 89000) { R.step = "shots"; R.error = "時間がかかりすぎました。通信のよいところで、もう一度「読みとる」を押してください"; render(); } }, 90000);
}
window.addEventListener("message", e => {
  const m = e.data;
  if (!m || m.type !== "streamlit:render") return;
  const o = (m.args || {}).ocr;
  if (!o || !o.id || o.id === R.seen) return;
  if (o.id !== R.pending) return;
  R.seen = o.id;
  if (o.error) { R.step = R.shots.length ? "shots" : "home"; R.error = o.error; }
  else { R.receipts = fromResult(o.receipts || []); R.model = o.model || ""; R.step = "edit"; R.shots = []; R.error = ""; }
  rkeep();
  if (S.view === "receipt") { closeModal(); render(); scrollEl.scrollTop = 0; }
});

// ---------------------------------------------------------------- 写真から選ぶ（カメラが使えないときも）
function fileToShot(file) {
  return new Promise((res, rej) => {
    const img = new Image(), url = URL.createObjectURL(file);
    img.onload = () => { URL.revokeObjectURL(url); res(makeShot(img, img.naturalWidth, img.naturalHeight)); };
    img.onerror = () => { URL.revokeObjectURL(url); rej(new Error("読めない写真")); };
    img.src = url;
  });
}
function makeShot(src, w, h, crop) {
  const c = crop || { x: 0, y: 0, w, h }, LONG = 2600, k = Math.min(1, LONG / Math.max(c.w, c.h));
  const cv = document.createElement("canvas");
  cv.width = Math.round(c.w * k); cv.height = Math.round(c.h * k);
  cv.getContext("2d").drawImage(src, c.x, c.y, c.w, c.h, 0, 0, cv.width, cv.height);
  const tk = 160 / Math.max(cv.width, cv.height), tc = document.createElement("canvas");
  tc.width = Math.round(cv.width * tk); tc.height = Math.round(cv.height * tk);
  tc.getContext("2d").drawImage(cv, 0, 0, tc.width, tc.height);
  return { url: cv.toDataURL("image/jpeg", 0.86), thumb: tc.toDataURL("image/jpeg", 0.7) };
}

// ================================================================ カメラ（自動撮影）
const CAM = { on: false, stream: null, video: null, timer: 0, prev: null, okSince: 0, armed: true, capSmall: null, peak: [], allOkSince: 0, last: null, busy: false };
const SW = 180;             // 調べるときの小さな絵の幅
const PASS = 0.75;         // それぞれの点数がこれ以上（75%）なら合格
const HOLD = 500;           // 90% 以上をこの時間（ミリ秒）保ったら撮る
function camHtml() {
  return `<div id="cam"><video playsinline muted autoplay></video><canvas class="ov"></canvas>
    <div class="ctop"><button class="cx" data-r="camclose" aria-label="閉じる">✕</button><div class="cscore"><b>—</b><span>読みとりやすさ</span></div><div class="ccount"></div></div><div class="cres"></div>
    <div class="cmsg">カメラを準備しています…</div>
    <div class="cchips"></div>
    <div class="cbot"><div class="cthumb"></div><button class="cshut" data-r="shut" aria-label="撮る"></button><button class="cdone" data-r="camdone">完了</button></div>
    <div class="cflash"></div></div>`;
}
async function openCam() {
  if (R.shots.length >= MAX_SHOTS) { toast(`写真は${MAX_SHOTS}枚までです`); return; }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { toast("この画面ではカメラが使えません。「写真から選ぶ」を使ってください"); return; }
  document.body.insertAdjacentHTML("beforeend", camHtml());
  const el = document.getElementById("cam");
  CAM.video = el.querySelector("video"); CAM.on = true; CAM.armed = true; CAM.okSince = 0; CAM.prev = null; CAM.peak = []; CAM.allOkSince = 0;
  updCount();
  try {
    CAM.stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 2560 }, height: { ideal: 1440 } } });
    if (!CAM.on) { stopStream(); return; }
    try { await CAM.stream.getVideoTracks()[0].applyConstraints({ advanced: [{ focusMode: "continuous" }] }); } catch (e) {}   // できる端末だけ：ピントを合わせつづける
    CAM.video.srcObject = CAM.stream;
    await CAM.video.play().catch(() => {});
    CAM.timer = setInterval(analyze, 110);
  } catch (e) {
    closeCam();
    toast(e && e.name === "NotAllowedError" ? "カメラが許可されていません。設定で許可するか「写真から選ぶ」を使ってください" : "カメラを使えませんでした。「写真から選ぶ」を使ってください");
  }
}
function stopStream() { if (CAM.stream) CAM.stream.getTracks().forEach(t => t.stop()); CAM.stream = null; }
function closeCam() {
  CAM.on = false; clearInterval(CAM.timer); stopStream();
  const el = document.getElementById("cam"); if (el) el.remove();
  if (S.view === "receipt") render();
}
function updCount() {
  const el = document.getElementById("cam"); if (!el) return;
  el.querySelector(".ccount").textContent = R.shots.length ? `${R.shots.length}枚` : "";
  const t = R.shots[R.shots.length - 1];
  el.querySelector(".cthumb").innerHTML = t ? `<img src="${t.thumb}" alt="">` : "";
}

// 小さな絵の明るさ（0〜255）
function grayOf(img, n) { const g = new Uint8ClampedArray(n); for (let i = 0, p = 0; i < n; i++, p += 4) g[i] = (img[p] * 77 + img[p + 1] * 150 + img[p + 2] * 29) >> 8; return g; }
function otsu(g) {
  const h = new Array(256).fill(0); for (const v of g) h[v]++;
  let sum = 0; for (let i = 0; i < 256; i++) sum += i * h[i];
  let sb = 0, wb = 0, best = 0, t = 128;
  for (let i = 0; i < 256; i++) {
    wb += h[i]; if (!wb) continue; const wf = g.length - wb; if (!wf) break;
    sb += i * h[i]; const mb = sb / wb, mf = (sum - sb) / wf, v = wb * wf * (mb - mf) * (mb - mf);
    if (v > best) { best = v; t = i; }
  }
  return t;
}
// いちばん大きい明るいかたまり（＝レシート）
function biggestBlob(g, W, H, t) { return allBlobs(g, W, H, t, 0).sort((a, b) => b.area - a.area)[0] || null; }
// 明るいかたまりを全部（小さすぎるものは捨てる）
function allBlobs(g, W, H, t, minArea) {
  const lab = new Uint8Array(W * H), stack = new Int32Array(W * H), out = [];
  for (let s = 0; s < W * H; s++) {
    if (lab[s] || g[s] <= t) continue;
    let sp = 0, area = 0, x0 = W, x1 = 0, y0 = H, y1 = 0; stack[sp++] = s; lab[s] = 1;
    const pix = [];
    while (sp) {
      const p = stack[--sp], x = p % W, y = (p / W) | 0; area++; pix.push(p);
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
      if (x > 0 && !lab[p - 1] && g[p - 1] > t) { lab[p - 1] = 1; stack[sp++] = p - 1; }
      if (x < W - 1 && !lab[p + 1] && g[p + 1] > t) { lab[p + 1] = 1; stack[sp++] = p + 1; }
      if (y > 0 && !lab[p - W] && g[p - W] > t) { lab[p - W] = 1; stack[sp++] = p - W; }
      if (y < H - 1 && !lab[p + W] && g[p + W] > t) { lab[p + W] = 1; stack[sp++] = p + W; }
    }
    if (area >= minArea) out.push({ area, x0, x1, y0, y1, pix });
  }
  return out;
}
// レシートらしさ：中に文字（まわりより暗い細かな点）があるか。照明やテカリは、のっぺり明るいだけで文字がない
function paperOf(blob, g, W) {
  const L = {}, Rr = {};
  let sum = 0, sat = 0;
  for (const p of blob.pix) { const x = p % W, y = (p / W) | 0; sum += g[p]; if (g[p] >= 250) sat++; if (L[y] === undefined || x < L[y]) L[y] = x; if (Rr[y] === undefined || x > Rr[y]) Rr[y] = x; }
  const mean = sum / blob.area;
  let n = 0, dark = 0, edge = 0;
  for (const y in L) for (let x = L[y] + 1; x < Rr[y]; x++) {
    const p = +y * W + x; n++;
    if (g[p] < mean - 22) dark++;
    if (Math.abs(g[p] - g[p + 1]) > 18) edge++;
  }
  return { mean, sat: sat / blob.area, detail: n ? dark / n : 0, edge: n ? edge / n : 0 };
}
// かたまりの形（レシートは「幅がほぼ一定」で「左右のふちがまっすぐ」）
function shapeOf(blob, W) {
  const L = {}, Rr = {};
  for (const p of blob.pix) { const x = p % W, y = (p / W) | 0; if (L[y] === undefined || x < L[y]) L[y] = x; if (Rr[y] === undefined || x > Rr[y]) Rr[y] = x; }
  const h = blob.y1 - blob.y0, ys = Object.keys(L).map(Number).filter(y => y >= blob.y0 + h * .1 && y <= blob.y1 - h * .1);
  if (ys.length < 8) return { ok: false };
  const wd = ys.map(y => Rr[y] - L[y] + 1), mean = wd.reduce((a, b) => a + b, 0) / wd.length;
  const cv = Math.sqrt(wd.reduce((a, b) => a + (b - mean) ** 2, 0) / wd.length) / mean;
  const resid = E => {          // ふちを直線にあてはめたときのずれ（幅に対する割合）
    let sx = 0, sy = 0, sxy = 0, syy = 0; const n = ys.length;
    for (const y of ys) { sx += E[y]; sy += y; sxy += E[y] * y; syy += y * y; }
    const d = n * syy - sy * sy, a = d ? (n * sxy - sx * sy) / d : 0, b = (sx - a * sy) / n;
    return Math.sqrt(ys.reduce((acc, y) => acc + (E[y] - (a * y + b)) ** 2, 0) / n) / mean;
  };
  const rl = resid(L), rr = resid(Rr);
  return { ok: cv <= 0.2 && rl <= 0.1 && rr <= 0.1, cv, rl, rr, mean };
}
// レシートを探す：まわり（机の明るいところ・箱など）とつながっているときは、明るさのしきい値を上げて切りはなす
let lastT = 0;
function findReceipt(g, W, H) {
  const t0 = otsu(g);
  let mb = 0, nb = 0, md = 0, nd = 0; for (const x of g) { if (x > t0) { mb += x; nb++; } else { md += x; nd++; } }
  if ((nb ? mb / nb : 0) - (nd ? md / nd : 0) < 20) return null;
  // しきい値を上げながら、全部のかたまりを「形（幅が一定・ふちがまっすぐ）」と「文字があるか」で調べ、いちばんレシートらしいものを選ぶ
  let best = null;
  const lo = Math.max(60, Math.min(t0, lastT ? lastT - 14 : t0));
  for (let t = lo; t <= 236; t += 8) {
    const blobs = allBlobs(g, W, H, t, W * H * 0.03);
    if (!blobs.length) break;
    for (const b of blobs) {
      if (b.x1 - b.x0 < 6 || b.y1 - b.y0 < 8) continue;
      const sh = shapeOf(b, W); if (!sh.ok) continue;
      const pp = paperOf(b, g, W);
      if (pp.sat > 0.45 || pp.mean > 252) continue;          // 照明そのもの（真っ白でのっぺり）
      if (pp.detail < 0.015 && pp.edge < 0.03) continue;      // 文字がない（テカリ・白い箱など）
      const score = b.area * Math.min(1, (pp.detail + pp.edge) / 0.12) * (1 - Math.min(0.5, sh.cv * 2));
      if (!best || score > best.score) best = Object.assign(b, { t, score });
    }
  }
  if (best) lastT = best.t;
  return best;
}
function edgeAngle(blob, W) {      // 左右のふちの傾き（度）
  const L = {}, Rr = {};
  for (const p of blob.pix) { const x = p % W, y = (p / W) | 0; if (L[y] === undefined || x < L[y]) L[y] = x; if (Rr[y] === undefined || x > Rr[y]) Rr[y] = x; }
  const fit = E => {
    const ys = Object.keys(E).map(Number), h = blob.y1 - blob.y0, pts = ys.filter(y => y > blob.y0 + h * .1 && y < blob.y1 - h * .1);
    if (pts.length < 8) return null;
    let sx = 0, sy = 0, sxy = 0, syy = 0; for (const y of pts) { const x = E[y]; sx += x; sy += y; sxy += x * y; syy += y * y; }
    const n = pts.length, d = n * syy - sy * sy; if (!d) return null;
    return Math.atan((n * sxy - sx * sy) / d) * 180 / Math.PI;
  };
  const a = fit(L), b = fit(Rr);
  return a === null && b === null ? 0 : a === null ? b : b === null ? a : (a + b) / 2;
}
function lapVar(g, W, H) {          // ピントの目安（ラプラシアンのばらつき）
  let s = 0, s2 = 0, n = 0;
  for (let y = 1; y < H - 1; y += 1) for (let x = 1; x < W - 1; x += 1) {
    const p = y * W + x, v = 4 * g[p] - g[p - 1] - g[p + 1] - g[p - W] - g[p + W];
    s += v; s2 += v * v; n++;
  }
  return n ? s2 / n - (s / n) * (s / n) : 0;
}
const clamp01 = v => Math.max(0, Math.min(1, v));
let anaCv = null, focCv = null;
function analyze() {
  const v = CAM.video, el = document.getElementById("cam");
  if (!CAM.on || !v || !el || !v.videoWidth || CAM.busy) return;
  const vw = v.videoWidth, vh = v.videoHeight, W = SW, H = Math.round(SW * vh / vw);
  anaCv = anaCv || document.createElement("canvas"); anaCv.width = W; anaCv.height = H;
  const cx = anaCv.getContext("2d", { willReadFrequently: true }); cx.drawImage(v, 0, 0, W, H);
  const g = grayOf(cx.getImageData(0, 0, W, H).data, W * H);
  // 手ぶれ：前の絵とのちがい
  let motion = 40;
  if (CAM.prev && CAM.prev.length === g.length) { let d = 0; for (let i = 0; i < g.length; i += 2) d += Math.abs(g[i] - CAM.prev[i]); motion = d / (g.length / 2); }
  CAM.prev = g;
  // 撮ったあとは、別の場所（次の部分・次のレシート）に動かすまで撮らない
  if (!CAM.armed && CAM.capSmall && CAM.capSmall.length === g.length) {
    let d = 0; for (let i = 0; i < g.length; i += 2) d += Math.abs(g[i] - CAM.capSmall[i]);
    if (d / (g.length / 2) > 16) CAM.armed = true;
  }
  const blob = findReceipt(g, W, H);
  const found = !!blob;
  const sc = { pos: 0, tilt: 0, light: 0, still: clamp01(1 - motion / 40), focus: 0 };
  let msg = "レシートが見つかりません。まわりに白い物がない、暗めの所に置いてください", box = null, ang = 0;
  if (found) {
    const bw = blob.x1 - blob.x0 + 1, bh = blob.y1 - blob.y0 + 1, inside = blob.x0 >= 1 && blob.x1 <= W - 2;
    box = blob;
    // 文字が読める大きさか：レシートの幅が、カメラの絵で 700 ピクセルくらい（画面の幅の 45% まで）あればよい
    const needW = Math.min(0.45 * vw, 700), bwPx = bw / W * vw;
    sc.pos = Math.min(1, 0.9 * bwPx / needW, (bh / H) / 0.3); if (!inside) sc.pos = Math.min(sc.pos, 0.6);
    ang = edgeAngle(blob, W); sc.tilt = clamp01(1 - Math.abs(ang) / 50);
    let sum = 0, glare = 0; for (const p of blob.pix) { sum += g[p]; if (g[p] >= 250) glare++; }
    const mean = sum / blob.area, gl = glare / blob.area;
    sc.light = Math.min(mean < 120 ? 0.9 * mean / 120 : mean > 248 ? 0.85 : 1, clamp01(1 - gl * 5));
    // ピント：レシートのところだけを大きめに切りだして調べる
    const fw = 360, sx = blob.x0 / W * vw, sy = blob.y0 / H * vh, sw = bw / W * vw, sh = Math.min(bh / H * vh, sw * 1.6), fh = Math.max(40, Math.round(fw * sh / sw));
    focCv = focCv || document.createElement("canvas"); focCv.width = fw; focCv.height = fh;
    const fx = focCv.getContext("2d", { willReadFrequently: true }); fx.drawImage(v, sx, sy + (bh / H * vh - sh) / 2, sw, sh, 0, 0, fw, fh);
    const lv = lapVar(grayOf(fx.getImageData(0, 0, fw, fh).data, fw * fh), fw, fh);
    const now = Date.now(), others = sc.pos >= PASS && sc.tilt >= PASS && sc.light >= PASS && sc.still >= PASS;
    // ピントは「いまの構えの中でいちばんよかった値」とくらべる（構えがくずれたら、くらべる値もやりなおす）
    if (!others) CAM.peak = [];
    CAM.peak = CAM.peak.filter(p => now - p.t < 4000); CAM.peak.push({ t: now, v: lv });
    const peak = Math.max(...CAM.peak.map(p => p.v));
    CAM.allOkSince = others ? (CAM.allOkSince || now) : 0;
    const relax = CAM.allOkSince && now - CAM.allOkSince > 3000;          // 3秒たってもピントの数字が上がらないときは、その中でいちばんよいところで撮る
    const need = relax ? 0.85 * peak : Math.max(60, 0.7 * peak);
    sc.focus = clamp01(0.9 * lv / Math.max(1, need));
    msg = !inside ? "少しはなしてください（左右が切れています）" : sc.pos < PASS ? "もう少し近づけてください（長いレシートは上下に分けて撮れます）" : sc.tilt < PASS ? `まっすぐにしてください（${Math.round(ang)}°）`
      : sc.light < PASS ? (mean < 120 ? "暗いです。明るいところへ" : "光が反射しています。角度を少し変えて") : sc.still < PASS ? "動かさないでください" : sc.focus < PASS ? "ピントを合わせています…" : "そのまま…";
  }
  const score = Math.round(100 * Math.min(sc.pos, sc.tilt, sc.light, sc.still, sc.focus));
  const allOk = found && score >= PASS * 100, now = Date.now();
  if (allOk && CAM.armed) { CAM.okSince = CAM.okSince || now; } else CAM.okSince = 0;
  if (!CAM.armed && found) msg = "撮りました。次の部分・次のレシートへ動かしてください（終わったら「完了」）";
  // 画面に出す
  el.querySelector(".cscore b").textContent = found ? score + "%" : "—";
  el.querySelector(".cres").textContent = `${vw}×${vh}`;
  el.querySelector(".cscore").className = "cscore " + (allOk ? "ok" : score >= 60 ? "mid" : "");
  el.querySelector(".cmsg").textContent = msg;
  el.querySelector(".cchips").innerHTML = [["位置", sc.pos], ["傾き", sc.tilt], ["明るさ", sc.light], ["手ぶれ", sc.still], ["ピント", sc.focus]]
    .map(([l, s]) => `<span class="${found && s >= PASS ? "ok" : ""}">${l}</span>`).join("");
  drawBox(el, box, W, H, allOk && CAM.armed);
  if (CAM.okSince && now - CAM.okSince >= HOLD) capture(box, W, H, g);
}
function drawBox(el, b, W, H, ok) {
  const cv = el.querySelector(".ov"), v = CAM.video, r = v.getBoundingClientRect();
  cv.width = r.width; cv.height = r.height;
  const c = cv.getContext("2d"); c.clearRect(0, 0, cv.width, cv.height);
  if (!b) return;
  // video は object-fit: cover（はみ出た分は切れて見える）
  const k = Math.max(r.width / W, r.height / H), ox = (r.width - W * k) / 2, oy = (r.height - H * k) / 2;
  c.strokeStyle = ok ? "#2DB56A" : "#F2B33D"; c.lineWidth = 4; c.setLineDash(ok ? [] : [10, 8]);
  c.strokeRect(ox + b.x0 * k, oy + b.y0 * k, (b.x1 - b.x0 + 1) * k, (b.y1 - b.y0 + 1) * k);
}
function capture(b, W, H, g, manual) {
  const v = CAM.video; if (!v || !v.videoWidth || CAM.busy) return;
  CAM.busy = true;
  const vw = v.videoWidth, vh = v.videoHeight;
  let crop = null;
  if (b) {               // レシートのまわりだけを切りだす（少しよゆうをもたせる）
    const mx = (b.x1 - b.x0) * 0.04 + 2, my = (b.y1 - b.y0) * 0.03 + 2;
    const x0 = Math.max(0, (b.x0 - mx) / W * vw), y0 = Math.max(0, (b.y0 - my) / H * vh), x1 = Math.min(vw, (b.x1 + 1 + mx) / W * vw), y1 = Math.min(vh, (b.y1 + 1 + my) / H * vh);
    crop = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
  }
  const shot = makeShot(v, vw, vh, crop);
  R.shots.push(shot);
  CAM.armed = false; CAM.capSmall = g; CAM.okSince = 0;
  const el = document.getElementById("cam");
  if (el) { const f = el.querySelector(".cflash"); f.classList.remove("go"); void f.offsetWidth; f.classList.add("go"); }
  try { navigator.vibrate && navigator.vibrate(40); } catch (e) {}
  updCount();
  CAM.busy = false;
  if (R.shots.length >= MAX_SHOTS) { toast(`${MAX_SHOTS}枚撮りました`); closeCam(); }
}
function manualShot() {
  if (!CAM.video || !CAM.video.videoWidth) return;
  const v = CAM.video, W = SW, H = Math.round(SW * v.videoHeight / v.videoWidth);
  anaCv = anaCv || document.createElement("canvas"); anaCv.width = W; anaCv.height = H;
  const cx = anaCv.getContext("2d", { willReadFrequently: true }); cx.drawImage(v, 0, 0, W, H);
  const g = grayOf(cx.getImageData(0, 0, W, H).data, W * H);
  capture(findReceipt(g, W, H), W, H, g, true);
}

// ================================================================ 操作
document.addEventListener("click", e => {
  const b = e.target.closest("[data-r]");
  if (!b || b.tagName === "INPUT") return;
  const a = b.dataset.r, i = +b.dataset.i, j = +b.dataset.j, rc = R.receipts[i];
  switch (a) {
    case "cam": openCam(); break;
    case "camclose": case "camdone": closeCam(); break;
    case "shut": manualShot(); break;
    case "delshot": R.shots.splice(i, 1); render(true); break;
    case "send": sendShots(); break;
    case "resume": R.step = "edit"; rkeep(); render(); break;
    case "tax": rc.items[j].tax = TAXES[(TAXES.indexOf(rc.items[j].tax) + 1) % TAXES.length]; rkeep(); render(true); break;
    case "mode": rc.tax_mode = rc.tax_mode === "外税" ? "内税" : "外税"; rkeep(); render(true); break;
    case "pay": rc.pay = PAY_METHODS[(PAY_METHODS.indexOf(rc.pay) + 1) % PAY_METHODS.length]; rkeep(); render(true); break;
    case "dline": rc.items.splice(j, 1); rkeep(); render(true); break;
    case "addline": {
      const exp = cats(EXP).map(c => c["名前"]), c = b.dataset.c || (exp.includes("食費") ? "食費" : exp[0] || "その他");
      rc.items.push({ k: uid(), key: "", raw: "", name: "", price: "", qty: "1", tax: rc.items.length ? rc.items[rc.items.length - 1].tax : 8, cat: c, unsure: false, mem: false, oname: "", ocat: c, rec: false });
      rkeep(); render(true);
      setTimeout(() => { const ins = appEl.querySelectorAll(`[data-ri^="${i}|${rc.items.length - 1}|name"]`); if (ins[0]) ins[0].focus(); }, 30);
      break;
    }
    case "move": pickCat("カテゴリを変える", rc.items[j].cat, c => { rc.items[j].cat = c; }); break;
    case "gcat": {
      const from = b.dataset.c;
      pickCat(`「${esc(from)}」のグループのカテゴリ`, from, c => {
        rc.items.forEach(it => { if (it.cat === from) it.cat = c; });
        if (rc.amt && rc.amt[from] !== undefined) { if (c !== from && rc.amt[c] === undefined) rc.amt[c] = rc.amt[from]; delete rc.amt[from]; }
      });
      break;
    }
    case "catok": { closeModal(); const fn = catPick; catPick = null; if (fn) fn(b.dataset.v); rkeep(); render(true); break; }
    case "greset": if (rc.amt) delete rc.amt[b.dataset.c]; rkeep(); render(true); break;
    case "rec": openRec(i, j); break;
    case "rdetail": if (!e.target.closest("[data-a]")) openDetail(b.dataset.id); break;
    case "dmove": { const r = D.records.find(x => x.ID === detailId); pickCat("この品物のカテゴリ", r ? r["カテゴリ"] : "", c => moveItem(j, c)); break; }
    case "dcat": { const r = D.records.find(x => x.ID === detailId); pickCat("まとめてカテゴリを変える", r ? r["カテゴリ"] : "", c => recatAll(c)); break; }
    case "drec": recFromDetail(j); break;
    case "recsave": saveRec(); break;
    case "mclose": closeModal(); break;
    case "dropr": confirmBox(`「${esc(rc.store || "このレシート")}」を外しますか？（保存されません）`, "外す", () => { R.receipts.splice(i, 1); if (!R.receipts.length) R.step = "home"; rkeep(); render(); }); break;
    case "discard": confirmBox("読み取り結果を消しますか？", "消す", () => { R.receipts = []; R.step = "home"; rkeep(); render(); }); break;
    case "save": saveAll(); break;
  }
});
document.addEventListener("input", e => {
  const t = e.target;
  if (t.dataset.ri) {
    const [i, j, f] = t.dataset.ri.split("|"), it = R.receipts[+i] && R.receipts[+i].items[+j]; if (!it) return;
    if (f !== "name") t.value = t.value.replace(f === "price" ? /[^0-9\-]/g : /[^0-9]/g, "");
    it[f] = t.value; if (f === "name") it.unsure = false;
    rkeep(); refreshTotals();
  } else if (t.dataset.rg !== undefined) {
    const rc = R.receipts[+t.dataset.rg]; if (!rc) return;
    t.value = t.value.replace(/[^0-9]/g, ""); rc.amt = rc.amt || {}; rc.amt[t.dataset.c] = t.value;
    rkeep(); refreshTotals();
  } else if (t.dataset.rh) {
    const [i, f] = t.dataset.rh.split("|"); if (R.receipts[+i]) R.receipts[+i][f] = t.value; rkeep();
  } else if (t.dataset.rd && recDraft && t.tagName !== "SELECT") {
    if (["price", "pack"].includes(t.dataset.rd)) t.value = t.value.replace(/[^0-9]/g, "");
    if (t.dataset.rd === "amt") t.value = t.value.replace(/[^0-9.]/g, "");
    recDraft[t.dataset.rd] = t.value;
    const p = document.getElementById("rper"); if (p) p.textContent = perLabel(recInfo());
  }
});
document.addEventListener("change", e => {
  const t = e.target;
  if (t.dataset.r === "file" && t.files && t.files.length) {
    const files = [...t.files].slice(0, MAX_SHOTS - R.shots.length);
    Promise.all(files.map(f => fileToShot(f).catch(() => null))).then(list => {
      list.filter(Boolean).forEach(s => R.shots.push(s));
      if (list.some(x => !x)) toast("読めない写真がありました");
      R.error = ""; render(true);
    });
    t.value = "";
  } else if (t.dataset.rd === "unit" && recDraft) {
    const was = rIsCount(recDraft.unit); recDraft.unit = t.value;
    if (was !== rIsCount(t.value)) { const q = recDraft.qty; recDraft.amt = rIsCount(t.value) ? String(q) : ""; recDraft.pack = rIsCount(t.value) ? "1" : String(q); }
    drawRec();
  } else if (t.dataset.rd === "sid" && recDraft) recDraft.sid = t.value;
  else if (t.dataset.rh && t.type === "date") { const [i] = t.dataset.rh.split("|"); if (R.receipts[+i]) R.receipts[+i].date = t.value; rkeep(); }
  else if (t.dataset.ri && t.dataset.ri.endsWith("|price")) render(true);           // 税込の表示を直す
});
document.addEventListener("visibilitychange", () => { if (document.hidden && CAM.on) closeCam(); });
if (S.view === "receipt" || S.view === "other") render();
