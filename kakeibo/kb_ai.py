"""家計簿・買い物リストで AI を使う 3つの機能（どちらの ページからも 使う）。
- review(month)：月の ふりかえり。数字は 記録から アプリが 数え、AI は ひとことに するだけ。「ふりかえり」シートに 保存（家計簿・買い物リスト 共通）
- tidy_names()：買い物リストの 値段の記録の 品名を そろえる 案・参考に ならない 値段を 消す 案（反映は 画面で 確認してから）
- menu_items(text)：献立から 材料の 一覧（ジャンルつき）
AI は 2.5 → 3.5 Lite（回数を 節約）。"""
import json
import re
import time
from collections import Counter, defaultdict

import kb_ocr
import kb_store as store
from kb_calc import EXPENSE, INCOME

REVIEW = "ふりかえり"
CONV = ("セブン", "ローソン", "ファミリーマート", "ファミマ", "ミニストップ", "デイリーヤマザキ", "セイコーマート", "ポプラ", "NewDays", "ニューデイズ")


def _client():
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=kb_ocr._key(), http_options=types.HttpOptions(timeout=60_000))
    try:
        import common
        return common.wrap_client(client), getattr(common, "GEMINI_CHEAP", ["gemini-2.5-flash", "gemini-3.5-flash-lite"])
    except Exception:
        return client, "gemini-2.5-flash"


def _ask(prompt, temp=0.3):
    from google.genai import types
    client, model = _client()
    res = client.models.generate_content(model=model, contents=prompt,
                                         config=types.GenerateContentConfig(response_mime_type="application/json", temperature=temp))
    return json.loads(res.text)


def _int(x):
    try:
        return int(float(str(x).replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _prev(month):
    y, m = map(int, month.split("-"))
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def _shop_of(memo):
    head = str(memo or "").split("：")[0].strip()
    return head if 0 < len(head) <= 30 and head != str(memo or "").strip() else ""


# ---------------------------------------------------------------- 月の ふりかえり
def review_facts(month):
    recs = store.load("記録")
    def tot(mon, kind):
        out = defaultdict(int)
        for r in recs:
            if str(r.get("日付", "")).startswith(mon) and r.get("種類") == kind:
                out[r.get("カテゴリ") or "その他"] += _int(r.get("金額"))
        return out
    now, before = tot(month, EXPENSE), tot(_prev(month), EXPENSE)
    inc = sum(tot(month, INCOME).values())
    cats = []
    for c in sorted(set(now) | set(before), key=lambda c: -now.get(c, 0)):
        d = now.get(c, 0) - before.get(c, 0)
        cats.append({"カテゴリ": c, "今月": now.get(c, 0), "先月": before.get(c, 0), "差": d})
    shops = Counter()
    for r in recs:
        if str(r.get("日付", "")).startswith(month) and r.get("種類") == EXPENSE:
            s = _shop_of(r.get("メモ"))
            if s:
                shops[s] += 1
    bought = [r for r in store.load("購入記録") if str(r.get("日時", "")).startswith(month)]
    for r in bought:
        if r.get("店名"):
            shops[r["店名"]] += 0          # 買い物リストで 買ったお店も 名前だけ 入れる
    conv = sum(n for s, n in shops.items() if any(c in s for c in CONV))
    pay = Counter(r.get("支払方法") or "未設定" for r in recs if str(r.get("日付", "")).startswith(month) and r.get("種類") == EXPENSE)
    genres = Counter(r.get("ジャンル") or "その他" for r in bought)
    return {
        "月": month, "支出の合計": sum(now.values()), "先月の支出": sum(before.values()), "収入の合計": inc,
        "カテゴリ": cats[:10], "よく行ったお店": [f"{s}（{n}回）" for s, n in shops.most_common(6) if n],
        "コンビニの回数": conv, "支払方法": dict(pay),
        "買い物リストで買った品物の数": len(bought), "買った品物のジャンル": dict(genres.most_common(6)),
        "値段を記録した数": sum(1 for r in store.load("価格記録") if str(r.get("日付", "")).startswith(month)),
    }


def review(month, remake=False, make=True):
    """{"month", "facts", "comment": {...}, "made"}。保存してあれば それを返す（remake で 作りなおす）"""
    if not re.match(r"^\d{4}-\d{2}$", month or ""):
        raise RuntimeError("月の 形が おかしいです")
    facts = review_facts(month)
    rows = store.load(REVIEW)
    old = next((r for r in rows if r.get("月") == month), None)
    if old and not remake:
        try:
            return {"month": month, "facts": facts, "comment": json.loads(old.get("コメント") or ""), "made": old.get("日時", "")}
        except ValueError:
            pass
    if (not make and not remake) or (not facts["支出の合計"] and not facts["買い物リストで買った品物の数"]):
        return {"month": month, "facts": facts, "comment": None, "made": ""}
    d = _ask(f"""あなたは 家計の やりくりを 一緒に 考える、やさしくて 具体的な アドバイザーです。
次は ある家庭の {month} の 家計簿と 買い物リストの 記録を、アプリが 数えた ものです（正確な 値）。
データに ない ことは 書かない。金額・回数は データの とおりに 書く（1円単位の 数字は「約」を つけて まるめて よい）。

{json.dumps(facts, ensure_ascii=False, indent=1)}

次の JSON だけで 答えてください：
{{"headline": "今月を ひとことで（30字くらい）",
  "points": ["気づき（先月より 増えた・減った カテゴリ、コンビニの 回数、よく行く お店 など。数字を 入れる）", "…（2〜4個）"],
  "tips": ["来月 ためせる 具体的な 工夫（買い物リストの 使い方・まとめ買い・値段の 記録 など）", "…（1〜2個）"]}}""")
    comment = {"headline": str(d.get("headline") or ""), "points": [str(x) for x in d.get("points") or []][:4],
               "tips": [str(x) for x in d.get("tips") or []][:2]}
    made = time.strftime("%Y-%m-%d %H:%M:%S")
    rows = [r for r in rows if r.get("月") != month] + [{"月": month, "コメント": json.dumps(comment, ensure_ascii=False), "日時": made}]
    store.save(REVIEW, rows)
    return {"month": month, "facts": facts, "comment": comment, "made": made}


# ---------------------------------------------------------------- 品名を そろえる
def tidy_names():
    """{"merge": [{"to": 品名, "from": [品名…], "why"}], "drop": [{"id", "name", "price", "why"}]}
    値段の記録（価格記録）を 見て、同じ品物の 書き方ちがいと、参考に ならない 値段（読みまちがい・ケタちがい など）を 出す"""
    rows = store.load("価格記録")
    if not rows:
        return {"merge": [], "drop": []}
    names = Counter(str(r.get("品名") or "").strip() for r in rows if r.get("品名"))
    by = defaultdict(list)
    for r in rows:
        by[str(r.get("品名") or "").strip()].append(r)
    lines = []
    for n, k in names.most_common(250):
        ps = [f"{r.get('ID')}:{_int(r.get('値段'))}円/{r.get('量') or ''}{r.get('単位') or ''}x{r.get('入数') or 1}@{r.get('店名') or ''}" for r in by[n][:8]]
        lines.append(f"{n}（{k}件）：" + "、".join(ps))
    d = _ask(f"""あなたは 家計の データを 整理する 係です。次は 買い物の 値段の記録です（品名：ID:値段/量x入数@お店）。
1. 同じ 品物なのに 書き方が ちがう 品名を まとめる 案を 出してください（例：「明治おいしい牛乳900ml」「おいしい牛乳」→「明治おいしい牛乳 900ml」）。
   - 量や 種類が ちがう 物（牛乳 500ml と 1000ml、豚こま と 豚ロース）は まとめない
   - to は いちばん わかりやすい 書き方（ブランド＋品名＋量）。from は 今の 品名を そのまま 書く
2. 参考に ならない 値段の 記録を 出してください：同じ 品物の ほかの 値段と くらべて ケタが ちがう、0円・1円、量が おかしい など。id を そのまま 書く
はっきり しない ものは 出さない。

{chr(10).join(lines)}

次の JSON だけで 答えてください：
{{"merge": [{{"to": "まとめた 品名", "from": ["今の品名", "今の品名"], "why": "理由（短く）"}}],
  "drop": [{{"id": "記録のID", "why": "理由（短く）"}}]}}""", 0.1)
    ids = {str(r.get("ID")): r for r in rows}
    merge = []
    for m in d.get("merge") or []:
        src = [n for n in dict.fromkeys(str(x).strip() for x in (m.get("from") or [])) if n in names]
        to = str(m.get("to") or "").strip()
        if to and (len(src) >= 2 or (src and src[0] != to)):
            merge.append({"to": to[:60], "from": src, "why": str(m.get("why") or "")[:80], "n": sum(names[n] for n in src)})
    drop = []
    for x in d.get("drop") or []:
        r = ids.get(str(x.get("id")))
        if r:
            drop.append({"id": str(r.get("ID")), "name": r.get("品名", ""), "price": _int(r.get("値段")), "shop": r.get("店名", ""),
                         "date": r.get("日付", ""), "why": str(x.get("why") or "")[:80]})
    return {"merge": merge[:30], "drop": drop[:30]}


# ---------------------------------------------------------------- 献立から 材料
def menu_items(text, genres, people=2):
    """[{"name", "genre", "for", "amount", "staple"}]。staple：家に ありがちな 調味料など（はじめから 外しておく）"""
    text = str(text or "").strip()[:300]
    if not text:
        raise RuntimeError("献立を 入れてください")
    gl = "・".join(genres)
    d = _ask(f"""次の 献立を {people}人分 作るのに 必要な 材料を 書き出してください。
献立：{text}
- 同じ 材料は 1つに まとめる（for に どの 料理か）
- name は お店で 買うときの 名前（例：豚こま切れ肉、玉ねぎ、カレールウ）。amount は だいたいの 量（例：300g、2個）
- genre は 次の どれか：{gl}
- staple：塩・こしょう・しょうゆ・砂糖・油・みりん など、ふつう 家に ある 調味料なら true
次の JSON だけで 答えてください：
{{"items": [{{"name": "", "genre": "", "for": "", "amount": "", "staple": false}}]}}""", 0.2)
    out = []
    for it in d.get("items") or []:
        n = str(it.get("name") or "").strip()
        if not n:
            continue
        g = str(it.get("genre") or "")
        out.append({"name": n[:40], "genre": g if g in genres else (genres[-1] if genres else ""), "for": str(it.get("for") or "")[:40],
                    "amount": str(it.get("amount") or "")[:20], "staple": bool(it.get("staple"))})
    return out[:40]


def handle(req, genres=()):
    """画面からの AI の たのみごと（kind：review・tidy・menu）→ 結果の dict（id つき）"""
    kind = req.get("kind")
    try:
        if not kb_ocr.available() and not (kind == "review" and not req.get("make") and not req.get("remake")):
            raise RuntimeError("AIのカギ（GEMINI_API_KEY）が 設定されていません")
        if kind == "review":
            out = review(str(req.get("month") or ""), bool(req.get("remake")), bool(req.get("make")))
        elif kind == "tidy":
            out = tidy_names()
        elif kind == "menu":
            out = {"items": menu_items(req.get("text"), list(genres), int(req.get("people") or 2))}
        else:
            out = {"error": "わからない たのみごと"}
    except Exception as e:
        print(f"[家計AI] {kind}: {type(e).__name__}: {e}", flush=True)
        msg = str(e) if isinstance(e, RuntimeError) else ""
        if not msg:
            try:
                import common
                msg = common.ai_error_text(e)
            except Exception:
                msg = f"うまく いきませんでした（{type(e).__name__}）"
        out = {"error": msg}
    return {"id": req.get("id"), "kind": kind, **out}
