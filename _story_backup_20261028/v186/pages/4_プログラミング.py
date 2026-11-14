import html
import json
import random

import streamlit as st
from google.genai import types

import time

import common
import history
import pdfgen

common.setup_page("AIプログラミング教室", "💻")
common.hero("💻 AIプログラミング教室", "言語と年れいを えらぶと、AI先生が ぴったりの レッスンを つくるよ！")

client = common.get_gemini_client()

QUIZ_Q = 5
PHASES = ["words", "grammar", "write", "quiz"]
PHASE_LABELS = {"words": "① たんご", "grammar": "② ぶんぽう", "write": "③ かいてみよう", "quiz": "④ クイズ"}
DEFAULTS = {
    "pg_state": "menu",  # menu, learn, ending
    "pg_phase": "words",
    "pg_lesson": None,
    "pg_lang": "",
    "pg_level": "",
    "pg_topic": "",
    "pg_w": 0,  # 「かいてみよう」で今のステップ
    "pg_w_done": False,
    "pg_q": 0,
    "pg_choice": None,
    "pg_score": 0,
    "pg_log": [],
    "pg_rows": [],  # PDF・履歴用 (問題, あなたの答え, 正しい答え, 正解か)
    "pg_played_at": "",
}
common.init_state(DEFAULTS)

# 言語 -> (何に使う言語か, テーマの候補)
LANGUAGES = {
    "Python": ("AI・データ分析・自動化・Web・ゲームなど、いちばん幅広く使われる読みやすい言語。", ["表示（print）", "変数", "条件分岐（if）", "くり返し（for / while）", "リスト", "関数"]),
    "JavaScript": ("Webページを動かす言語。ボタンの反応やアニメーション、Webアプリを作る。", ["表示（console.log）", "変数（let / const）", "条件分岐（if）", "くり返し（for）", "配列", "関数"]),
    "HTML・CSS": ("Webページの形（HTML）と見た目（CSS）をつくる言語。", ["見出しと文章", "リンクと画像", "リスト", "色と文字の大きさ（CSS）", "レイアウトの基本"]),
    "Java": ("会社のシステム・Androidアプリ・大規模なサービスで使われる言語。", ["表示（System.out.println）", "変数と型", "条件分岐（if）", "くり返し（for）", "配列", "メソッド"]),
    "C言語": ("パソコンの中身や機械の制御に近い、速くて古典的な言語。", ["表示（printf）", "変数と型", "条件分岐（if）", "くり返し（for）", "配列", "関数"]),
    "SQL": ("データベースから、データを取り出したり書きかえたりする言語。", ["SELECT（取り出す）", "WHERE（条件）", "ORDER BY（並べかえ）", "INSERT（追加）", "UPDATE / DELETE", "集計（COUNT / SUM）"]),
}

LEVELS = {
    "小1〜2年（6〜8さい）": "6〜8歳。説明はほぼひらがな。たとえ話と絵文字を多く使い、1つのことだけを教える。専門用語は避け、出すコードは1行〜2行の超簡単なもの。",
    "小3〜4年（8〜10さい）": "8〜10歳。漢字は小3まで、ふりがな不要の範囲。身近なたとえ話で、最初の一歩を教える。コードは短く簡単に。",
    "小5〜6年（10〜12さい）": "10〜12歳。たとえ話を使いながら基本用語も教える。コードは短く、1つの考え方に絞る。",
    "中学生": "中学生。基本用語を正しく教え、簡単な応用例を入れる。",
    "高校生": "高校生。用語を正確に説明し、よくあるまちがいや実用例も触れる。",
    "大人（社会人・学び直し）": "大人の初学者。実務での使いどころ、よくあるミス、ベストプラクティスも簡潔に触れる。",
}


def build_prompt(lang, level, topic):
    return f"""
あなたは経験豊富で優しいプログラミングの先生です。次の条件でレッスンを作成してください。

【言語】{lang}（{LANGUAGES[lang][0]}）
【レッスンのテーマ】{topic}
【対象】{level}
【年齢への配慮】{LEVELS[level]}
- 対象の年齢が理解できる範囲に内容を絞り、難しい言語やテーマでも、その年齢向けの最も基本の部分だけを教えること。

【構成】
1. overview: この言語は何に使うか／このレッスンで学ぶことを2〜3文で。
2. words: このテーマで出てくる単語（キーワード・用語）を4〜6個。term=単語、meaning=意味、usage=何に使うか（短く）。
3. grammar: 文法（書き方のルール）を2〜3個。title=名前、pattern=書き方の型（コード）、explain=説明、example=具体例コード（1〜3行）。
4. steps: 「説明しながら一緒に書く」ためのコードを4〜6ステップ。**各ステップは1行で完結させ、先頭にインデント（空白）を付けないこと。**
   Pythonなどインデントが必要な構文は、1行で書ける形（例: for i in range(3): print(i)）にすること。
   全ステップを順に並べると、1つの完成したプログラムになるようにする。codeは実際に動く正しいコード、explainはその1行が何をするかの日本語の説明。
5. output: 完成したプログラムを実行したときの画面表示（HTML・CSSの場合は、ブラウザでどう見えるかの説明）。
6. quiz: 確認クイズを【{QUIZ_Q}問】。4択、answerはchoicesの中の1つと完全に一致。explanationに解説。

必ず次のJSONのみで出力してください。余計な文章は一切含めないでください。

{{
  "overview": "...",
  "words": [{{"term": "...", "meaning": "...", "usage": "..."}}],
  "grammar": [{{"title": "...", "pattern": "...", "explain": "...", "example": "..."}}],
  "steps": [{{"code": "...", "explain": "..."}}],
  "output": "...",
  "quiz": [{{"question": "...", "choices": ["...", "...", "...", "..."], "answer": "...", "explanation": "..."}}]
}}
"""


def validate_lesson(data):
    if not isinstance(data, dict):
        raise ValueError("形式がちがいます")
    for key, minimum in (("words", 3), ("grammar", 1), ("steps", 3), ("quiz", QUIZ_Q)):
        if not isinstance(data.get(key), list) or len(data[key]) < minimum:
            raise ValueError(f"{key} が足りません")
    for s in data["steps"]:
        if not (isinstance(s, dict) and str(s.get("code", "")).strip() and s.get("explain")):
            raise ValueError("steps の形がちがいます")
    data["quiz"] = data["quiz"][:QUIZ_Q]
    for q in data["quiz"]:
        if not (q.get("question") and isinstance(q.get("choices"), list) and q.get("answer") in q["choices"]):
            raise ValueError("quiz の形がちがいます")
        random.shuffle(q["choices"])
    return data


def generate_lesson(lang, level, topic):
    last_error = None
    for _ in range(2):  # 形式が崩れたときは1回だけやり直す
        try:
            response = client.models.generate_content(
                model=common.GEMINI_MODEL,
                contents=build_prompt(lang, level, topic),
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.5),
            )
            return validate_lesson(json.loads(response.text))
        except Exception as e:
            last_error = e
    st.error(f"AIがレッスンを作るときにエラーが起きちゃったみたい。もう一度ためしてね：{last_error}")
    return None


# スマホのキーボードは " や ' を “ ” ‘ ’（くるっとした形）に自動で変えたり、全角で入ったりするので、半角の記号にそろえる
_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‟": '"', "″": '"', "＂": '"', "〝": '"', "〟": '"',
                         "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "＇": "'", "｀": "`"})


def normalize_code(text):
    """くるっとした引用符・全角の英数字や記号（＝ （ ） ； など）を、半角にそろえる"""
    text = (text or "").translate(_QUOTES)
    return "".join(chr(ord(c) - 0xFEE0) if "！" <= c <= "～" else ("" if c == "\u3000" else c) for c in text)


def squash(text):
    """空白をすべて無視して比べる（スペースの数のちがいは気にしない）。記号の全角・半角のちがいも気にしない。"""
    return "".join(normalize_code(text).split())


def render_highlight(target, typed):
    parts = []
    t = squash(typed)
    g = squash(target)
    for i, ch in enumerate(g):
        if i < len(t):
            color = "#2ECC71" if t[i] == ch else "#E74C3C"
            parts.append(f"<span style='color:{color};font-weight:bold'>{html.escape(ch)}</span>")
        else:
            parts.append(f"<span style='color:#BDC3C7'>{html.escape(ch)}</span>")
    if len(t) > len(g):
        parts.append(f"<span style='color:#fff;background:#E74C3C;border-radius:3px;padding:0 2px'>{html.escape(t[len(g):])}</span>")
    st.markdown(
        f"<p style='font-family:monospace;font-size:20px;background:#222;padding:12px;border-radius:8px;color:#fff;word-break:break-all'>"
        f"{''.join(parts)}</p>",
        unsafe_allow_html=True,
    )


def set_phase(phase):
    st.session_state.pg_phase = phase


def submit_choice(choice):
    st.session_state.pg_choice = choice


def pdf_info():
    ss = st.session_state
    return f"言語：{ss.pg_lang} ／ テーマ：{ss.pg_topic} ／ {ss.pg_level}"


def go_next_quiz(is_correct):
    q = st.session_state.pg_lesson["quiz"][st.session_state.pg_q]
    question = f"{q['question']}\n（{'／'.join(q['choices'])}）"
    st.session_state.pg_rows.append((question, st.session_state.pg_choice, q["answer"], is_correct))
    st.session_state.pg_log.append(is_correct)
    if is_correct:
        st.session_state.pg_score += 1
    st.session_state.pg_choice = None
    st.session_state.pg_q += 1
    if st.session_state.pg_q >= QUIZ_Q:
        st.session_state.pg_state = "ending"
        score = st.session_state.pg_score
        st.session_state.pg_played_at = time.strftime("%Y-%m-%d %H:%M:%S")
        history.log_result(
            "プログラミング", 言語=st.session_state.pg_lang, テーマ=st.session_state.pg_topic,
            年齢層=st.session_state.pg_level, 点数=score * 20, 正解数=score,
            詳細=pdfgen.make_record("AIプログラミング教室", pdf_info(), st.session_state.pg_rows),
        )


def next_write_step():
    st.session_state.pg_w += 1
    st.session_state.pg_w_done = False


state = st.session_state.pg_state

# --- メニュー ---
if state == "menu":
    with st.container(border=True):
        st.subheader("① 言語を えらんでね")
        lang = st.radio("言語", list(LANGUAGES), horizontal=True, label_visibility="collapsed")
        st.caption(f"💡 {LANGUAGES[lang][0]}")
    with st.container(border=True):
        st.subheader("② 年れいを えらんでね")
        level_names = list(LEVELS)
        level = st.radio("年れい", level_names, index=common.age_level_index(len(level_names)), label_visibility="collapsed")
        if st.session_state.get("auth_age") is not None:
            st.caption(f"{st.session_state.auth_age}さいなので、おすすめを えらんでおいたよ。かえてもOK！")
    with st.container(border=True):
        st.subheader("③ 学ぶテーマを えらんでね")
        topics = ["おまかせ（はじめの一歩）"] + LANGUAGES[lang][1]
        topic = common.pick("テーマ", topics, key=f"pg_topic_{lang}")

    if st.button("🚀 AI先生にレッスンを作ってもらう！", type="primary", use_container_width=True):
        topic_name = LANGUAGES[lang][1][0] if topic.startswith("おまかせ") else topic
        with st.spinner("🧙‍♂️ AI先生がレッスンを作っているよ...（15秒くらい待ってね）"):
            lesson = generate_lesson(lang, level, topic_name)
        if lesson:
            common.reset_state("pg_", DEFAULTS)
            st.session_state.pg_lesson = lesson
            st.session_state.pg_lang = lang
            st.session_state.pg_level = level
            st.session_state.pg_topic = topic_name
            st.session_state.pg_state = "learn"
            st.rerun()

# --- 学習 ---
elif state == "learn":
    lesson = st.session_state.pg_lesson
    phase = st.session_state.pg_phase
    st.caption(f"{st.session_state.pg_lang} ／ {st.session_state.pg_topic} ／ {st.session_state.pg_level}")
    st.progress(PHASES.index(phase) / len(PHASES), text="　".join(
        f"**{PHASE_LABELS[p]}**" if p == phase else PHASE_LABELS[p] for p in PHASES
    ))

    if phase == "words":
        st.header("📚 ① 出てくる単語")
        st.info(lesson.get("overview", ""))
        for w in lesson["words"]:
            with st.container(border=True):
                st.markdown(f"#### `{w['term']}`")
                st.markdown(f"**意味：** {w['meaning']}")
                st.markdown(f"**何に使う？** {w['usage']}")
        st.button("つぎへ：文法を見る ➡️", on_click=set_phase, args=("grammar",), type="primary", use_container_width=True)

    elif phase == "grammar":
        st.header("📐 ② 文法（書き方のルール）")
        for g in lesson["grammar"]:
            with st.container(border=True):
                st.markdown(f"#### {g['title']}")
                st.markdown("**書き方の型**")
                st.code(g["pattern"], language=st.session_state.pg_lang.split("・")[0].lower())
                st.markdown(g["explain"])
                if g.get("example"):
                    st.markdown("**れい**")
                    st.code(g["example"], language=st.session_state.pg_lang.split("・")[0].lower())
        col_back, col_next = st.columns(2)
        col_back.button("⬅️ 単語にもどる", on_click=set_phase, args=("words",), use_container_width=True)
        col_next.button("つぎへ：書いてみよう ➡️", on_click=set_phase, args=("write",), type="primary", use_container_width=True)

    elif phase == "write":
        steps = lesson["steps"]
        w = st.session_state.pg_w
        lang_tag = st.session_state.pg_lang.split("・")[0].lower()
        st.header("⌨️ ③ 説明を聞きながら書いてみよう")
        st.caption("1行ずつ、見本のとおりに打ってね。スペースの数は気にしなくていいよ。")
        if w > 0:
            st.markdown("**ここまでのプログラム**")
            st.code("\n".join(s["code"] for s in steps[:w]), language=lang_tag)

        if w < len(steps):
            step = steps[w]
            st.progress(w / len(steps), text=f"{w + 1} / {len(steps)} ステップ")
            st.info(f"🗣️ {step['explain']}")
            st.markdown("**👇 この1行を打とう**")
            st.code(step["code"], language=lang_tag)
            done = st.session_state.pg_w_done
            with st.form(f"pg_form_{w}"):
                typed = st.text_input("ここに打ってエンターを押してね", key=f"pg_input_{w}", disabled=done)
                submitted = st.form_submit_button("決定！", type="primary", disabled=done)
            if submitted and squash(typed) == squash(step["code"]):
                st.session_state.pg_w_done = True
                done = True
            if typed:
                render_highlight(step["code"], typed)
            if done:
                st.success("🎉 せいかい！")
                label = "完成！ 実行結果を見る ➡️" if w == len(steps) - 1 else "つぎのステップへ ➡️"
                st.button(label, on_click=next_write_step, type="primary", use_container_width=True)
            elif submitted:
                st.error("❌ おしい！赤い文字をなおしてもう一回ためしてね。")
        else:
            st.success("🎉 プログラムが完成したよ！")
            st.markdown("**💻 実行すると こうなるよ**")
            st.code(lesson.get("output", ""), language="text")
            st.button("つぎへ：クイズに挑戦 ➡️", on_click=set_phase, args=("quiz",), type="primary", use_container_width=True)

    elif phase == "quiz":
        q_idx = st.session_state.pg_q
        q = lesson["quiz"][q_idx]
        st.header(f"❓ ④ クイズ　{q_idx + 1} / {QUIZ_Q}")
        st.progress(q_idx / QUIZ_Q)
        st.markdown(f"#### {q['question']}")
        chosen = st.session_state.pg_choice
        if chosen is None:
            ans = st.radio("こたえ", q["choices"], index=None, key=f"pg_radio_{q_idx}", label_visibility="collapsed")
            st.button("これで決定！", disabled=ans is None, on_click=submit_choice, args=(ans,), type="primary")
        else:
            is_correct = chosen == q["answer"]
            st.radio("こたえ", q["choices"], index=q["choices"].index(chosen), key=f"pg_radio_{q_idx}", disabled=True, label_visibility="collapsed")
            if is_correct:
                st.success(f"⭕ せいかい！　{q['answer']}")
            else:
                st.error(f"❌ ざんねん… 正しい答えは「{q['answer']}」だよ。")
            if q.get("explanation"):
                st.info(q["explanation"])
            label = "結果発表へ！ 🏆" if q_idx == QUIZ_Q - 1 else "次の問題へ ➡️"
            st.button(label, on_click=go_next_quiz, args=(is_correct,), type="primary", use_container_width=True)

# --- 結果 ---
elif state == "ending":
    score = st.session_state.pg_score
    st.header("🏆 レッスンクリア！")
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 点数", f"{score * 20} / 100 点")
    c2.metric("✅ 正解数", f"{score} / {QUIZ_Q} 問")
    c3.metric("言語", st.session_state.pg_lang)
    st.write("".join("⭕" if ok else "❌" for ok in st.session_state.pg_log))
    if score == QUIZ_Q:
        st.balloons()
        st.success("🥇 パーフェクト！ もう立派なプログラマーだ！")
    elif score >= 3:
        st.success("🥈 いいね！ 単語と文法をもう一度見ると、さらに身につくよ。")
    else:
        st.info("🌱 よくがんばったね！ レッスンをもう一度やってみよう。")

    common.pdf_preview_button(
        pdfgen.build_pdf(
            "AIプログラミング教室", pdf_info(), st.session_state.get("player_name", ""),
            st.session_state.pg_played_at, score * 20, st.session_state.pg_rows,
        ),
    )

    st.divider()
    col_again, col_new = st.columns(2)
    with col_again:
        if st.button("🔁 同じレッスンをもう一度", use_container_width=True):
            lesson = st.session_state.pg_lesson
            keep = {k: st.session_state[k] for k in ("pg_lang", "pg_level", "pg_topic")}
            common.reset_state("pg_", DEFAULTS)
            for key, value in keep.items():
                st.session_state[key] = value
            for q in lesson["quiz"]:
                random.shuffle(q["choices"])
            st.session_state.pg_lesson = lesson
            st.session_state.pg_state = "learn"
            st.rerun()
    with col_new:
        if st.button("🔄 べつのレッスンを作る", type="primary", use_container_width=True):
            common.reset_state("pg_", DEFAULTS)
            st.rerun()
