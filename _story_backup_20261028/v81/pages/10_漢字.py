import json
import random
import time
from pathlib import Path

import streamlit as st

import common
import history
import pdfgen
import web_games

common.setup_page("漢字のかきとり", "✍️")
common.hero("✍️ 漢字のかきとり", "指やペンで 書いてみよう！ 書き順と 形を チェックするよ。タブレットや スマホでも つかえるよ。")

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

DEFAULTS = {
    "kj_state": "menu",  # menu, playing, ending
    "kj_list": [],
    "kj_grade": 1,
    "kj_mode": "trace",
    "kj_level": "小3〜4年（8〜10さい）",
    "kj_result": None,
}
common.init_state(DEFAULTS)
ROUND_KEY = "kanji_round"  # kj_ で始めないので「もどる」でリセットされない（前のゲームの結果をまちがえて拾わないため）
st.session_state.setdefault(ROUND_KEY, 0)


@st.cache_data(show_spinner=False)
def load_kanji():
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def reading_of(entry):
    return "・".join((entry.get("k") or [])[:2] or (entry.get("o") or [])[:2])


def format_time(seconds):
    minutes, secs = int(seconds // 60), round(seconds % 60, 1)
    return f"{minutes}分 {secs}秒" if minutes else f"{secs}秒"


def pdf_info():
    ss = st.session_state
    return f"{ss.kj_grade}年生の漢字 ／ {MODES[ss.kj_mode][0]} ／ {ss.kj_level}"


try:
    data = load_kanji()
except FileNotFoundError:
    st.error("漢字のデータ（data/kanji.json）が見つからないよ。`python3 scripts/build_kanji_data.py` で作ってね。")
    st.stop()

state = st.session_state.kj_state

# --- メニュー ---
if state == "menu":
    with st.container(border=True):
        st.subheader("① 学年を えらんでね")
        grade = st.radio(
            "学年", [1, 2, 3, 4, 5, 6], horizontal=True, format_func=lambda g: f"{g}年生",
            label_visibility="collapsed",
        )
        count = sum(1 for e in data.values() if e["g"] == grade)
        st.caption(f"{grade}年生で ならう漢字は {count}字。その中から {QUESTIONS}字 出すよ。")
    with st.container(border=True):
        st.subheader("② 書きかたを えらんでね")
        mode = st.radio(
            "書きかた", list(MODES), format_func=lambda m: MODES[m][0], label_visibility="collapsed",
        )
        st.caption(MODES[mode][1])
    with st.container(border=True):
        st.subheader("③ 年れい（判定の ゆるさに つかうよ）")
        levels = list(LEVEL_TOL)
        level = st.selectbox(
            "年れい", levels, index=common.age_level_index(len(levels)), label_visibility="collapsed",
        )
        st.caption("年れいが 低いほど、すこしくらい ずれても OKに するよ。")

    if st.button("🚀 スタート！", type="primary", use_container_width=True):
        pool = [ch for ch, e in data.items() if e["g"] == grade]
        chosen = random.sample(pool, min(QUESTIONS, len(pool)))
        st.session_state.kj_list = [{"c": ch, **data[ch]} for ch in chosen]
        st.session_state.kj_grade, st.session_state.kj_mode, st.session_state.kj_level = grade, mode, level
        st.session_state[ROUND_KEY] += 1
        st.session_state.kj_result = None
        st.session_state.kj_state = "playing"
        st.rerun()
    st.caption(
        "書き順データ：KanjiVG（CC BY-SA 3.0, kanjivg.tagaini.net）　学年・読み：KANJIDIC2（kanjiapi.dev 経由）。"
        "「とめ・はね・はらい」の細かい判定は しないよ（書き順・画数・形を 大まかに チェック）。"
    )

# --- 書き取り（JavaScript の画面） ---
elif state == "playing":
    round_no = st.session_state[ROUND_KEY]
    result = web_games.kanji_game(
        f"kj_game_{round_no}", kanjis=st.session_state.kj_list, mode=st.session_state.kj_mode,
        tol=LEVEL_TOL[st.session_state.kj_level], round=round_no,
    )
    if result and result.get("type") == "kanji_done" and result.get("round") == round_no:
        items = result["results"]
        score = round(sum(r["points"] for r in items) / max(1, len(items)) * 10)
        good = sum(1 for r in items if r["points"] >= POINTS_OK)
        pdf_rows = []
        for r in items:
            entry = data.get(r["ch"], {})
            note = "わからない" if r["skipped"] else f"ミス{r['misses']}回・ヒント{r['hints']}回"
            pdf_rows.append((f"{r['ch']}（{reading_of(entry)}）", note, f"{r['strokes']}画 / {r['points']:g}点", r["points"] >= POINTS_OK))
        result.update(score=score, good=good, pdf_rows=pdf_rows, played_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        st.session_state.kj_result = result
        history.log_result(
            "漢字", 学年=f"{st.session_state.kj_grade}年生", モード=MODES[st.session_state.kj_mode][0],
            年齢層=st.session_state.kj_level, 点数=score, 正解数=good,
            詳細=pdfgen.make_record("漢字のかきとり", pdf_info(), pdf_rows),
        )
        st.session_state.kj_state = "ending"
        st.rerun()
    if st.button("↩️ やめて メニューに もどる"):
        common.reset_state("kj_", DEFAULTS)
        st.rerun()

# --- けっか ---
elif state == "ending":
    r = st.session_state.kj_result
    st.header("🏆 漢字のかきとり おつかれさま！")
    if r["score"] >= 90:
        st.balloons()
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 点数", f"{r['score']} / 100 点")
    c2.metric("⭐ よくできた", f"{r['good']} / {len(r['results'])} 字")
    c3.metric("⏱️ タイム", format_time(r["time"]))
    st.caption(f"{pdf_info()}")

    with st.expander("📋 1字ずつの けっか", expanded=True):
        for item in r["results"]:
            entry = data.get(item["ch"], {})
            mark = "🌟" if item["points"] >= 9 else "⭐" if item["points"] >= POINTS_OK else "👍" if not item["skipped"] else "🙈"
            note = "わからなかった" if item["skipped"] else f"ミス {item['misses']}回・ヒント {item['hints']}回"
            st.markdown(f"{mark} **{item['ch']}**　{reading_of(entry)}　（{item['strokes']}画）　**{item['points']:g}点**　— {note}")

    common.pdf_preview_button(
        pdfgen.build_pdf(
            "漢字のかきとり", pdf_info(), st.session_state.get("player_name", ""),
            r["played_at"], r["score"], r["pdf_rows"],
        ),
    )
    st.divider()
    col_again, col_menu = st.columns(2)
    with col_again:
        if st.button("🔁 おなじ学年で もう一度", type="primary", use_container_width=True):
            pool = [ch for ch, e in data.items() if e["g"] == st.session_state.kj_grade]
            chosen = random.sample(pool, min(QUESTIONS, len(pool)))
            st.session_state.kj_list = [{"c": ch, **data[ch]} for ch in chosen]
            st.session_state[ROUND_KEY] += 1
            st.session_state.kj_result = None
            st.session_state.kj_state = "playing"
            st.rerun()
    with col_menu:
        if st.button("🔄 学年や書きかたを かえる", use_container_width=True):
            common.reset_state("kj_", DEFAULTS)
            st.rerun()
