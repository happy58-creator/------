"""漢字のかきとり：学年・書きかた・年れいをえらんで、10字を指やペンで書く。
画面はぜんぶ JavaScript（web/kanji。書き取りの本体は kanji.js）。
Python は「10字えらぶ（data/kanji.json）」「おわったら点数を出して記録し、表彰状をつくる」だけ。"""
import base64
import json
import random
import re
import time
from pathlib import Path

import streamlit as st

import common
import history
import js_page
import pdfgen
import web_games

common.setup_page("漢字のかきとり", ":material/edit:")
ss = st.session_state
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "kanji.json"
QUESTIONS = 10

# 判定のゆるさ（お手本の線から どれくらい ずれていいか）。年れいが低いほど ゆるい。
LEVEL_TOL = {
    "小1〜2年（6〜8さい）": 24,
    "小3〜4年（8〜10さい）": 21,
    "小5〜6年（10〜12さい）": 18,
    "中学生": 16,
    "高校生": 14,
    "大人（社会人・学び直し）": 13,
}
MODES = {
    "trace": ("✏️ なぞり書き", "うすいお手本を なぞって 書き順を おぼえよう"),
    "recall": ("🧠 見て書く", "漢字を見ながら、お手本なしで 書こう（まちがえたら ヒントが出るよ）"),
    "reading": ("📖 読みから書く", "読みと いみだけを 見て 思い出して 書こう（いちばん むずかしい！）"),
}
POINTS_OK = 8  # 1文字 10点中、これ以上なら「よくできた」


@st.cache_data(show_spinner=False)
def load_kanji():
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def reading_of(entry):
    return "・".join((entry.get("k") or [])[:2] or (entry.get("o") or [])[:2])


def pdf_info(grade, mode, level):
    return f"{grade}年生の漢字 ／ {MODES[mode][0]} ／ {level}"


KANA_LEVELS = set(list(LEVEL_TOL)[:2])        # 小1〜4年：コメントは ひらがな中心


def ai_comment(items, level, mode):
    """書いた字の画像をまとめて AI に見せて、1字ずつの ひとことと、全体の ひとことを もらう（2.5 → 3.5 Lite、1回だけ）"""
    from google.genai import types
    parts, lines = [], []
    for k, it in enumerate(items[:QUESTIONS]):
        m = re.match(r"data:image/(jpeg|png);base64,(.+)$", str(it.get("img") or ""), re.S)
        if not m:
            continue
        lines.append(f"{len(lines) + 1}. お手本の字「{it.get('ch')}」（アプリの判定 {it.get('points')}点 / 10点、書き順などのミス {it.get('misses', 0)}回）")
        parts.append(f"{len(lines)}番の画像：")
        parts.append(types.Part.from_bytes(data=base64.b64decode(m.group(2)), mime_type=f"image/{m.group(1)}"))
    if not lines:
        return {}, ""
    kana = level in KANA_LEVELS
    prompt = f"""あなたは やさしい書写（習字）の先生です。{level}の生徒が、スマホやタブレットに 指で漢字を書きました（{MODES.get(mode, ('', ''))[0]}）。
画像は 白地に黒い線で、書いた線だけが写っています（うすい十字線は ます目の中心）。線の太さは 一定なので、筆の強弱は 見なくてよいです。

{chr(10).join(lines)}

1字ずつ、お手本の字と くらべて、次のところを 見てください。
- とめ・はね・はらい（線の終わりの形）
- 字のバランス（大きさ、ます目の中での位置、部分どうしの大きさや間）
- 線の長さ・向き・つき出し・すき間

そして、それぞれ 1〜2文の ひとことを 書いてください。
- まず よかった所を 1つ。そのあと 直すと もっとよくなる所を 1つ、具体的に（例：「３画目の はらいを もう少し 長く のばそう」）。
- うまく 見えない所は、むりに 言わない。
{"- ひらがな中心で、小学校低学年でも 読める ことばで。" if kana else "- 年齢に合った、やさしい ことばで。"}
さいごに overall に、全体を通した ひとこと（1〜2文、ほめて はげます）。

次の JSON だけで 答えてください（items は {len(lines)}個、番号の順）。
{{"items": ["...", "..."], "overall": "..."}}"""
    client = common.get_gemini_client()
    res = client.models.generate_content(model=getattr(common, "GEMINI_CHEAP", common.GEMINI_MODEL), contents=[prompt] + parts,
                                         config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.3))
    data = json.loads(res.text)
    got = [str(x).strip() for x in (data.get("items") or [])]
    out, n = {}, 0
    for k, it in enumerate(items[:QUESTIONS]):
        if re.match(r"data:image/(jpeg|png);base64,", str(it.get("img") or "")):
            if n < len(got) and got[n]:
                out[f"{int(it.get('i', k))}:{it.get('ch')}"] = got[n]
            n += 1
    return out, str(data.get("overall") or "").strip()


def handle(v):
    data = load_kanji()
    t = v.get("type")
    if t == "start":                              # 10字えらぶ
        grade = int(v.get("grade") or 1)
        pool = [ch for ch, e in data.items() if int(e["g"]) == grade]
        chosen = random.sample(pool, min(QUESTIONS, len(pool)))
        return {"kanjis": [{"c": ch, **data[ch]} for ch in chosen]}
    if t == "done":                               # 書きおわった：点数・記録・表彰状
        grade, mode, level = int(v.get("grade") or 1), v.get("mode"), v.get("level")
        if mode not in MODES or level not in LEVEL_TOL:
            return {"error": "えらび方がおかしいよ"}
        items = v.get("results") or []
        score = round(sum(float(r.get("points") or 0) for r in items) / max(1, len(items)) * 10)
        good = sum(1 for r in items if float(r.get("points") or 0) >= POINTS_OK)
        rows, pdf_rows = [], []
        for r in items:
            entry = data.get(r.get("ch"), {})
            note = "わからない" if r.get("skipped") else f"ミス{r.get('misses', 0)}回・ヒント{r.get('hints', 0)}回"
            pts = float(r.get("points") or 0)
            pdf_rows.append((f"{r.get('ch')}（{reading_of(entry)}）", note, f"{r.get('strokes')}画 / {pts:g}点", pts >= POINTS_OK))
            rows.append({"ch": r.get("ch"), "reading": reading_of(entry)})
        info = pdf_info(grade, mode, level)
        history.log_once("漢字", f"kj-{v.get('run')}", 学年=f"{grade}年生", モード=MODES[mode][0], 年齢層=level, 点数=score, 正解数=good,
                         詳細=pdfgen.make_record("漢字のかきとり", info, pdf_rows))
        pdf = pdfgen.build_pdf("漢字のかきとり", info, ss.get("player_name", ""), time.strftime("%Y-%m-%d %H:%M:%S"), score, pdf_rows)
        return {"score": score, "good": good, "rows": rows, "info": info, "pdf": js_page.pdf_b64(pdf)}
    if t == "comment":                            # AI先生の ひとこと（書いた字の画像を まとめて1回）
        if ss.get(f"kj_cmt_{v.get('run')}"):          # 同じ回は1回だけ（回数の節約）
            return ss[f"kj_cmt_{v.get('run')}"]
        try:
            items, overall = ai_comment(v.get("items") or [], v.get("level"), v.get("mode"))
            out = {"items": items, "overall": overall} if items or overall else {"error": "AI先生の コメントを もらえなかったよ"}
        except Exception as e:
            print(f"[漢字] コメント：{type(e).__name__}: {e}", flush=True)
            out = {"error": (common.ai_error_text(e) if hasattr(common, "ai_error_text") else "AI先生の コメントを もらえなかったよ")}
        if not out.get("error"):
            ss[f"kj_cmt_{v.get('run')}"] = out
        return out
    return {}


try:
    counts = {}
    for e in load_kanji().values():
        counts[int(e["g"])] = counts.get(int(e["g"]), 0) + 1
except FileNotFoundError:
    st.error("漢字のデータ（data/kanji.json）が見つからないよ。`python3 scripts/build_kanji_data.py` で作ってね。")
    st.stop()
levels = list(LEVEL_TOL)
js_page.serve(web_games.kanji_study, "kj", handle,
              counts=counts, modes=[{"id": k, "name": v[0], "desc": v[1]} for k, v in MODES.items()],
              levels=[{"id": k, "tol": v} for k, v in LEVEL_TOL.items()], level=levels[common.age_level_index(len(levels))],
              n=QUESTIONS, okPoints=POINTS_OK)
