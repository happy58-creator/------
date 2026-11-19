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


def pdf_info(grade, mode, level, th=False):
    return f"{grade}年生の漢字 ／ {MODES[mode][0]} ／ {level}" + (" ／ とめ・はね判定あり" if th else "")


KANA_LEVELS = set(list(LEVEL_TOL)[:2])        # 小1〜4年：コメントは ひらがな中心


def ai_comment(items, level, mode, th=False):
    """書いた字（左にお手本・右に書いた字の画像）と、アプリが測ったデータを AI に見せて、
    1字ずつの ひとことと、全体の ひとことを もらう（2.5 → 3.5 Lite、1回だけ）"""
    from google.genai import types
    parts, lines = [], []
    for k, it in enumerate(items[:QUESTIONS]):
        m = re.match(r"data:image/(jpeg|png);base64,(.+)$", str(it.get("img") or ""), re.S)
        if not m:
            continue
        no = len(lines) + 1
        facts = [str(f)[:120] for f in (it.get("facts") or [])][:8]
        lines.append(f"{no}番「{it.get('ch')}」：アプリの判定 {it.get('points')}点 / 10点、書き順などのミス {it.get('misses', 0)}回"
                     + (f"、とめ・はねのミス {it.get('endMiss', 0)}回" if th else "")
                     + "\n  アプリが測ったデータ：" + ("／".join(facts) if facts else "なし"))
        parts.append(f"{no}番の画像：")
        parts.append(types.Part.from_bytes(data=base64.b64decode(m.group(2)), mime_type=f"image/{m.group(1)}"))
    if not lines:
        return {}, ""
    kana = level in KANA_LEVELS
    side = any(it.get("cmp") for it in items)
    pic = ("画像は 1字につき1枚。左が お手本（教科書の字の形）、右が 生徒の 書いた字です。どちらも 同じ大きさの ます目で、うすい十字線は ます目の中心。"
           "小さい数字は 書き順の番号で、その画の 書きはじめに ついています（左は赤、右は青）。" if side else
           "画像は 白地に黒い線で、生徒の 書いた線だけが 写っています（うすい十字線は ます目の中心）。")
    endrule = ("- とめ・はね・はらい は、今回 アプリが 判定しています。データに「できていない」画が あれば、それを いちばん先に 直す所として 伝える。"
               if th else
               "- とめ・はね・はらい は、今回は 判定していないので、ふれない（指で書いた線は 太さが一定で、画像では 正しく見えないため）。")
    prompt = f"""あなたは 小学校で 書写を 教えている、やさしくて 具体的な 先生です。{level}の生徒が、スマホやタブレットに 指で漢字を書きました（{MODES.get(mode, ('', ''))[0].split(' ', 1)[-1]}）。
{pic}

それぞれの字に「アプリが測ったデータ」を つけます。これは 線の座標から 計算した 正確な値です。
- アドバイスは、このデータと 画像の 両方に 合うことだけを 書く。データと 画像が 食いちがうときは データを 信じる。
- データにない 問題は、左右の画像を くらべて はっきり わかるときだけ 書く。わからない所は 書かない。
- 「○画目」は データや 画像の 番号と 同じ 数え方。

{chr(10).join(lines)}

1字ずつ、2文で ひとことを 書いてください。
- 1文目：よかった所を 具体的に（何画目か、どの部分か。データの「お手本に とても近い画」などを 使う）。
- 2文目：いちばん 直すと よくなる所を 1つだけ。何画目を どうするかを、体の動きで わかる 言い方で（例：「4画目の 横の線を もう少し 右まで のばそう」「右の部分を 少し 下げて、左と 高さを そろえよう」）。
- 「バランスよく」「ていねいに」のような あいまいな ことばだけで 終わらせない。
- 大きな ずれが ないときは、2文目は「この形を おぼえておこう」のように ほめて しめる。
{endrule}
{"- ひらがな中心で、小学校低学年でも 読める ことばで。1文は 短く。" if kana else "- 年齢に合った、やさしい ことばで。"}
さいごに overall に、10字を 通して 多かった くせ（例：右に よりがち、横の線が 短め）を 1つと、はげましを 1〜2文で。

次の JSON だけで 答えてください（items は {len(lines)}個、番号の順）。
{{"items": ["...", "..."], "overall": "..."}}"""
    client = common.get_gemini_client()
    res = client.models.generate_content(model=getattr(common, "GEMINI_CHEAP", common.GEMINI_MODEL), contents=[prompt] + parts,
                                         config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2))
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
        grade, mode, level, th = int(v.get("grade") or 1), v.get("mode"), v.get("level"), bool(v.get("th"))
        if mode not in MODES or level not in LEVEL_TOL:
            return {"error": "えらび方がおかしいよ"}
        items = v.get("results") or []
        score = round(sum(float(r.get("points") or 0) for r in items) / max(1, len(items)) * 10)
        good = sum(1 for r in items if float(r.get("points") or 0) >= POINTS_OK)
        rows, pdf_rows = [], []
        for r in items:
            entry = data.get(r.get("ch"), {})
            note = "わからない" if r.get("skipped") else f"ミス{r.get('misses', 0)}回・ヒント{r.get('hints', 0)}回" + (f"・とめはね{r.get('endMiss', 0)}回" if th else "")
            pts = float(r.get("points") or 0)
            pdf_rows.append((f"{r.get('ch')}（{reading_of(entry)}）", note, f"{r.get('strokes')}画 / {pts:g}点", pts >= POINTS_OK))
            rows.append({"ch": r.get("ch"), "reading": reading_of(entry)})
        info = pdf_info(grade, mode, level, th)
        history.log_once("漢字", f"kj-{v.get('run')}", 学年=f"{grade}年生", モード=MODES[mode][0], 年齢層=level, 点数=score, 正解数=good,
                         詳細=pdfgen.make_record("漢字のかきとり", info, pdf_rows))
        pdf = pdfgen.build_pdf("漢字のかきとり", info, ss.get("player_name", ""), time.strftime("%Y-%m-%d %H:%M:%S"), score, pdf_rows)
        return {"score": score, "good": good, "rows": rows, "info": info, "pdf": js_page.pdf_b64(pdf)}
    if t == "comment":                            # AI先生の ひとこと（書いた字の画像を まとめて1回）
        if ss.get(f"kj_cmt_{v.get('run')}"):          # 同じ回は1回だけ（回数の節約）
            return ss[f"kj_cmt_{v.get('run')}"]
        try:
            items, overall = ai_comment(v.get("items") or [], v.get("level"), v.get("mode"), bool(v.get("th")))
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
