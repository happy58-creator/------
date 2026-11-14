"use strict";
// 店舗の位置さがし（買い物リスト shopping/ui/app.js と同じもの。直すときは両方を直す）
// 2点の距離（m）
function meters(a, b) {
  const R = 6371000, r = x => x * Math.PI / 180;
  const dLat = r(b.lat - a.lat), dLng = r(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
const distText = m => m < 1000 ? `${Math.round(m / 10) * 10}m` : `${(m / 1000).toFixed(1)}km`;
// 店舗の規模：ピンからこの範囲にいれば「そのお店にいる」とみなす（現在地の表示・買ったお店の記録・値段の記録のお店）
const SIZES = { 大: { m: 1000, hint: "大型ショッピングモールなど" }, 中: { m: 600, hint: "大型店舗・ホームセンターなど" }, 小: { m: 300, hint: "駐車場50台以下の店舗など" } };
const SIZE_NEXT = { 中: "小", 小: "大", 大: "中" };          // ボタンを押すたびに 中→小→大→中
const sizeOf = b => SIZES[b && b["規模"]] ? b["規模"] : "中";   // 未設定は「中」
const radiusOf = b => SIZES[sizeOf(b)].m;
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
