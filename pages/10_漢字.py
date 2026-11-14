"""漢字のかきとり：学年・書きかた・年れいをえらんで、10字を指やペンで書く。
画面はぜんぶ JavaScript（web/kanji。書き取りの本体は kanji.js）。
Python は「10字えらぶ（data/kanji.json）」「おわったら点数を出して記録し、表彰状をつくる」だけ。"""
import json
import random
import time
from pathlib import Path

import streamlit as st

import common
import history
import js_page
import pdfgen
import web_games

common.setup_page("漢字のかきとり", "✍️")
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
