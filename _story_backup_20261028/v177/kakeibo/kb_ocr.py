"""レシートの読み取り（Gemini）。
画面で撮った写真（何枚でも）を、1回の問い合わせでまとめて送り、
お店・日付・品名・金額・税・個数・カテゴリを JSON で受けとる。
1枚のレシートを分けて撮った写真も、ちがうレシートの写真も、まとめて送ってよい（Gemini が見分ける）。"""
import base64
import json
import os
import re

import streamlit as st

MODEL_FALLBACK = "gemini-3.6-flash"
FALLBACK_MODEL = "gemini-3.5-flash-lite"   # 予備：混雑・回数の上限のとき（回数の上限はモデルごとに別）


def _key():
    try:
        k = st.secrets.get("GEMINI_API_KEY")
        if k:
            return k
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


def available():
    return bool(_key())


def _model():
    try:
        import common          # 教材アプリと同じモデル
        return getattr(common, "GEMINI_MODEL", MODEL_FALLBACK)
    except Exception:
        return MODEL_FALLBACK


def _image(url):
    """data:image/jpeg;base64,... → (bytes, mime)"""
    m = re.match(r"data:(image/[\w.+-]+);base64,(.*)$", str(url), re.S)
    if not m:
        raise ValueError("写真の形がちがいます")
    return base64.b64decode(m.group(2)), m.group(1)


def _prompt(cats, names):
    hint = "、".join(names[:300]) if names else "（なし）"
    return f"""あなたは日本のレシートを読みとる係です。写真は1枚以上あります。
- 1枚のレシートを上下に分けて撮った写真があります。同じレシートの写真はつなげて1つのレシートとして読み、重なって写っている行は1回だけ数えてください。
- ちがうレシートの写真は、別のレシートとして分けてください。

各レシートについて：
- store：お店の名前（チェーン名。例「無印良品」「トライアル」）。branch：支店名（例「イオンモール福岡店」。なければ空）
- date：日付 YYYY-MM-DD（わからなければ空）。time：時刻 HH:MM（なければ空）
- tax_mode：品物の金額が税込なら "内税"、税抜で最後に消費税を足す形なら "外税"
- total：レシートに書いてある支払いの合計（税込）。整数
- items：品物の一覧（レシートの順）
  - raw：レシートに書いてあるとおりの品名（半角カナもそのまま）
  - name：ふつうの書き方に直した品名（例「ﾌﾞﾀｺﾏｷﾞﾚ」→「豚こま切れ」、「ｷﾞｭｳﾆｭｳ」→「牛乳」）。下の「よく使う品名」に同じものがあれば、その書き方にそろえる
  - price：その行の金額（値引き後。2コ×158 なら 316）。外税のレシートなら税抜の金額のまま。整数
  - qty：個数（書いてなければ 1）
  - tax：税率 8・10・0（0 は非課税）。「※」「軽」などの印は 8%（軽減税率）。食品は多くが 8%、日用品・外食・酒は 10%
  - category：次のカテゴリから1つ：{"・".join(cats)}
- 品物ごとの値引き（「値引」「割引」「-30」など）は、その品物の price から引いて、行を作らない
- お会計全体の値引き・クーポンは、name を「値引き」、price をマイナスにした行にする
- 小計・合計・消費税・お預り・お釣り・ポイント・支払方法の行は items に入れない
- payment：支払方法がわかれば "現金"・"クレカ"・"その他"、わからなければ空
- 読めない文字があっても、できるだけ推測して埋める。自信がない行は "unsure": true をつける

よく使う品名：{hint}

次の JSON だけを出力：
{{"receipts":[{{"store":"","branch":"","date":"","time":"","tax_mode":"内税","total":0,"payment":"","items":[{{"raw":"","name":"","price":0,"qty":1,"tax":8,"category":"","unsure":false}}]}}]}}"""


def _int(v):
    try:
        return int(round(float(str(v).replace(",", "").replace("¥", "").replace("円", "").strip() or 0)))
    except Exception:
        return 0


def _clean(data, cats):
    out = []
    for r in (data or {}).get("receipts") or []:
        items = []
        for it in r.get("items") or []:
            name = str(it.get("name") or it.get("raw") or "").strip()
            if not name or not _int(it.get("price")):        # 0円の行（読みまちがい・メモの行）は入れない
                continue
            tax = _int(it.get("tax"))
            items.append({
                "raw": str(it.get("raw") or "").strip(), "name": name, "price": _int(it.get("price")),
                "qty": max(1, _int(it.get("qty")) or 1), "tax": tax if tax in (0, 8, 10) else 8,
                "category": it.get("category") if it.get("category") in cats else "", "unsure": bool(it.get("unsure")),
            })
        date = str(r.get("date") or "")
        out.append({
            "store": str(r.get("store") or "").strip(), "branch": str(r.get("branch") or "").strip(),
            "date": date if re.match(r"^\d{4}-\d{2}-\d{2}$", date) else "", "time": str(r.get("time") or ""),
            "tax_mode": "外税" if r.get("tax_mode") == "外税" else "内税", "total": _int(r.get("total")),
            "payment": str(r.get("payment") or ""), "items": items,
        })
    return [r for r in out if r["items"]]


def _reset_jst():
    """1日の回数が戻る時刻（日本時間）。アメリカ太平洋時間の0時（冬は17時、夏は16時）"""
    try:
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        la = datetime.now(ZoneInfo("America/Los_Angeles"))
        nxt = (la + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return f"{nxt.astimezone(ZoneInfo('Asia/Tokyo')).hour}時"
    except Exception:
        return "17時ごろ"


def _code(e):
    """エラーの番号（429：回数の上限、5xx：Google側の混雑・不具合、404：モデルがない）"""
    for k in ("code", "status_code"):
        v = getattr(e, k, None)
        if isinstance(v, int):
            return v
    m = re.search(r"\b(4\d\d|5\d\d)\b", str(e))
    return int(m.group(1)) if m else 0


def read_receipts(images, cats, names):
    """images：data URL の一覧。返り値 {"receipts": [...], "model": ...} か {"error": "..."}
    失敗したら：混雑（5xx）は少し待って同じモデルで1回だけ送り直し、それでもダメなら予備のモデル（回数の上限は別）で読む。
    1日の回数が少ない（無料は20回）ので、送り直しは多くしない。"""
    if not images:
        return {"error": "写真がありません"}
    if not available():
        return {"error": "AIのカギ（GEMINI_API_KEY）が設定されていないので、読み取りが使えません"}
    import time
    try:
        from google import genai
        from google.genai import types
        parts = []
        for u in images[:10]:
            b, mime = _image(u)
            parts.append(types.Part.from_bytes(data=b, mime_type=mime))
        parts.append(_prompt(cats, names))
        client = genai.Client(api_key=_key())
    except Exception as e:
        return {"error": f"写真を送る準備ができませんでした（{type(e).__name__}）"}
    main = _model()
    plan = [(main, 0), (main, 4), (FALLBACK_MODEL, 0)]       # （モデル, 送る前に待つ秒）
    codes, i = [], 0
    while i < len(plan):
        model, wait = plan[i]
        i += 1
        if wait:
            time.sleep(wait)
        try:
            res = client.models.generate_content(           # 写真が何枚でも、問い合わせは1回
                model=model, contents=parts,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
            )
            receipts = _clean(json.loads(res.text), cats)
            if not receipts:
                return {"error": "レシートの品物を読みとれませんでした。明るいところで、もう一度撮ってみてください"}
            return {"receipts": receipts, "model": model}
        except Exception as e:
            c = _code(e)
            codes.append(c)
            if c == 429 or c == 404 or (400 <= c < 500 and model == main):
                # 回数の上限・モデルがない・写真の問題：同じモデルで送り直してもむだ → 予備のモデルへ
                while i < len(plan) and plan[i][0] == model:
                    i += 1
    if codes and all(c == 429 for c in codes if c != 404):
        return {"error": f"AIの読み取り回数の上限に達しました。1分ほど待ってもう一度押してください。1日の回数を使い切った場合は、{_reset_jst()}（日本時間）に戻ります（写真は残っています）"}
    if any(500 <= c < 600 for c in codes) or not any(codes):
        return {"error": "Geminiが混み合っていて読みとれませんでした。少し時間をおいて、もう一度「読みとる」を押してください（写真は残っています）"}
    return {"error": f"読み取りに失敗しました（エラー {'・'.join(str(c) for c in codes if c)}）。写真を撮り直してみてください"}
