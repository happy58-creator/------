import json
import random

import streamlit as st
from google.genai import types

import common
import history

common.setup_page("AI英語チャレンジ", "🔤")
common.hero("🔤 AI英語チャレンジ", "年れいに合わせて、AIが英語の問題を10問つくるよ！")

client = common.get_gemini_client()

TOTAL_Q = 10
DEFAULTS = {
    "en_state": "menu",  # menu, playing, ending
    "en_questions": [],
    "en_q": 0,
    "en_score": 0,
    "en_choice": None,  # 今の問題で「決定」した選択肢
    "en_hint": False,
    "en_log": [],  # 各問題の結果 (正解したか)
    "en_course": "単語",
    "en_level": "",
    "en_topic": "",
    "en_assist": True,
}
common.init_state(DEFAULTS)

# 年齢層 -> (AIへの指示, 日本語表示を ひらがな中心にするか)
LEVELS = {
    "小1〜2年（6〜8さい）": ("英語に初めて触れる子ども向け。色・動物・食べ物・数・家族など、身近で超基本の単語だけ。文は I like ~. / This is ~. 程度の3語前後。", True),
    "小3〜4年（8〜10さい）": ("小学校中学年向け。英検5級レベル。身の回り・学校・曜日・天気などの基本単語。文は主語＋動詞の短い現在形・be動詞・can。", True),
    "小5〜6年（10〜12さい）": ("小学校高学年向け。英検5〜4級レベル。教科・スポーツ・場所・道案内などの単語。文は過去形・現在進行形・疑問文の基本。", False),
    "中学生": ("中学生向け。英検3級レベル。単語は中学で習う標準語彙。文は不定詞・動名詞・比較・受け身・現在完了の基本。", False),
    "高校生": ("高校生向け。英検準2級〜2級レベル。抽象的な語彙や熟語・句動詞。文は関係代名詞・仮定法・分詞構文の基本。", False),
    "大人（社会人・学び直し）": ("大人向け。日常会話と職場で使う実用英語（TOEIC 600点前後）。メール・会議・旅行・買い物でよく使う語彙や表現。", False),
}

COURSES = {
    "単語": "英単語を見て、意味を答えよう（絵文字つき）",
    "文": "短い英語の文の ＿＿ に入ることばを選ぼう",
}


def build_prompt(course, level, topic, kana_only):
    guide = LEVELS[level][0]
    topic_line = f"- テーマは「{topic}」に関連づけてください。" if topic else "- テーマはおまかせ（いろいろな分野から出す）。"
    ja_rule = (
        "日本語の説明（reading以外）は、漢字をなるべく使わず ひらがな中心にしてください。"
        if kana_only
        else "日本語の説明は、年齢に合った自然な表現にしてください。"
    )
    if course == "単語":
        form = """- 「単語コース」です。1問ごとに英単語を1つ出し、その日本語の意味を3〜4択で答えさせます。
- promptには英単語（または熟語）だけを書きます。
- emojiには、その単語を表す絵文字を1〜2個入れます（抽象語で合う絵文字がなければ空文字）。
- readingには、カタカナの読みを入れます。
- translationは使わず空文字にします。
- choicesは日本語の意味の選択肢。紛らわしい誤答を混ぜてください。"""
    else:
        form = """- 「文コース」です。1問ごとに英語の文の一部を ＿＿ にして、入る英語を3〜4択で答えさせます。
- promptには ＿＿ を1か所含む英語の文を書きます。
- emojiには場面を表す絵文字を1〜2個入れます（なければ空文字）。
- readingは使わず空文字にします。
- translationに、その文の日本語訳（正解を入れた完成形）を入れます。
- choicesは英語の選択肢（語または短い句）。文法的に紛らわしい誤答を混ぜてください。"""
    return f"""
あなたは経験豊富な英語の先生です。次の条件で英語の4択（または3択）クイズを【{TOTAL_Q}問】作成してください。

【対象】{level}
【レベルの目安】{guide}
{topic_line}
{ja_rule}
{form}
- 正解はchoicesの中に1つだけ、answerと完全に一致させてください。
- hintには、答えそのものを言わずに考え方を助けるヒントを日本語で書いてください。
- explanationには、なぜその答えになるかを日本語で1〜2文で書いてください。
- 同じ単語や文を重複させないでください。

必ず次のJSONのみで出力してください。余計な文章は含めないでください。

{{
  "questions": [
    {{"prompt": "...", "emoji": "...", "reading": "...", "translation": "...",
      "choices": ["...", "...", "..."], "answer": "...", "hint": "...", "explanation": "..."}}
  ]
}}
"""


def valid_question(q):
    return (
        isinstance(q, dict)
        and q.get("prompt")
        and isinstance(q.get("choices"), list)
        and 2 <= len(q["choices"]) <= 5
        and q.get("answer") in q["choices"]
    )


def generate_questions(course, level, topic):
    prompt = build_prompt(course, level, topic, LEVELS[level][1])
    last_error = None
    for _ in range(2):  # 形式が崩れたときは1回だけやり直す
        try:
            response = client.models.generate_content(
                model=common.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.6),
            )
            items = json.loads(response.text).get("questions", [])
            items = [q for q in items if valid_question(q)][:TOTAL_Q]
            if len(items) < TOTAL_Q:
                raise ValueError(f"問題が{len(items)}問しか作れませんでした")
            for q in items:
                random.shuffle(q["choices"])
            return items
        except Exception as e:
            last_error = e
    st.error(f"AIが問題を作るときにエラーが起きちゃったみたい。もう一度ためしてね：{last_error}")
    return None


def submit_choice(choice):
    st.session_state.en_choice = choice


def go_next(is_correct):
    st.session_state.en_log.append(is_correct)
    if is_correct:
        st.session_state.en_score += 1
    st.session_state.en_choice = None
    st.session_state.en_hint = False
    st.session_state.en_q += 1
    if st.session_state.en_q >= TOTAL_Q:
        st.session_state.en_state = "ending"
        score = st.session_state.en_score
        history.log_result(
            "英語", コース=st.session_state.en_course, 年齢層=st.session_state.en_level,
            テーマ=st.session_state.en_topic or "おまかせ", 点数=score * 10, 正解数=score,
        )


def show_hint():
    st.session_state.en_hint = True


state = st.session_state.en_state

# --- メニュー ---
if state == "menu":
    with st.container(border=True):
        st.subheader("① 年れいを えらんでね")
        level_names = list(LEVELS)
        age = st.session_state.get("auth_age")
        default_level = 0 if age is None else next(
            (i for i, limit in enumerate((8, 10, 12, 15, 18)) if age <= limit), len(level_names) - 1
        )
        level = st.radio("年れい", level_names, index=default_level, label_visibility="collapsed")
        if age is not None:
            st.caption(f"{age}さいなので、このどれかを えらんでおいたよ。かえてもOK！")
    with st.container(border=True):
        st.subheader("② コースを えらんでね")
        course = st.radio(
            "コース", list(COURSES), horizontal=True, label_visibility="collapsed",
            format_func=lambda c: f"{'🔤' if c == '単語' else '📝'} {c}コース",
        )
        st.caption(COURSES[course])
    with st.container(border=True):
        st.subheader("③ おたすけ・テーマ（どちらもおこのみで）")
        assist = st.toggle("おたすけモード（読み方・日本語訳・絵文字を見ながら答える）", value=True)
        topic = st.text_input("テーマ（空らんならおまかせ）", placeholder="例：どうぶつ、りょこう、スポーツ、仕事")

    if st.button("🚀 AIに問題を作ってもらってスタート！", type="primary", use_container_width=True):
        with st.spinner("🧙‍♂️ AI先生が10問を作っているよ...（10秒くらい待ってね）"):
            questions = generate_questions(course, level, topic.strip())
        if questions:
            common.reset_state("en_", DEFAULTS)
            st.session_state.en_questions = questions
            st.session_state.en_course = course
            st.session_state.en_level = level
            st.session_state.en_topic = topic.strip()
            st.session_state.en_assist = assist
            st.session_state.en_state = "playing"
            st.rerun()

# --- プレイ ---
elif state == "playing":
    idx = st.session_state.en_q
    q = st.session_state.en_questions[idx]
    assist = st.session_state.en_assist
    is_word = st.session_state.en_course == "単語"

    st.caption(f"{st.session_state.en_level} ／ {st.session_state.en_course}コース　　いまの正解：{st.session_state.en_score}問")
    st.progress(idx / TOTAL_Q, text=f"{idx + 1} / {TOTAL_Q} 問目")

    with st.container(border=True):
        if assist and q.get("emoji"):
            st.markdown(f"<div class='big-center' style='font-size:4rem'>{q['emoji']}</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='big-center' style='font-size:2rem;color:#542b69'>{q['prompt']}</div>",
            unsafe_allow_html=True,
        )
        if assist and is_word and q.get("reading"):
            st.markdown(f"<div class='big-center' style='font-size:1.1rem;color:#6b5d68'>（{q['reading']}）</div>", unsafe_allow_html=True)
    st.markdown("**{}**".format("この単語の意味は？" if is_word else "＿＿ に入ることばは？"))

    chosen = st.session_state.en_choice
    if chosen is None:
        ans = st.radio("こたえ", q["choices"], index=None, key=f"en_radio_{idx}", label_visibility="collapsed")
        col_go, col_hint = st.columns(2)
        col_go.button("これで決定！", disabled=ans is None, on_click=submit_choice, args=(ans,), type="primary", use_container_width=True)
        col_hint.button("💡 ヒント", on_click=show_hint, disabled=st.session_state.en_hint, use_container_width=True)
        if st.session_state.en_hint:
            st.info(f"💡 {q.get('hint') or 'よく見て考えてみよう！'}")
    else:
        is_correct = chosen == q["answer"]
        st.radio("こたえ", q["choices"], index=q["choices"].index(chosen), key=f"en_radio_{idx}", disabled=True, label_visibility="collapsed")
        if is_correct:
            st.success(f"⭕ せいかい！　{q['answer']}")
        else:
            st.error(f"❌ ざんねん… 正しい答えは「{q['answer']}」だよ。")
        if q.get("translation"):
            st.markdown(f"📖 日本語訳：{q['translation']}")
        if q.get("explanation"):
            st.info(q["explanation"])
        label = "結果発表へ！ 🏆" if idx == TOTAL_Q - 1 else "次の問題へ ➡️"
        st.button(label, on_click=go_next, args=(is_correct,), type="primary", use_container_width=True)

# --- 結果 ---
elif state == "ending":
    score = st.session_state.en_score
    st.header("🏆 おつかれさま！")
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 点数", f"{score * 10} / 100 点")
    c2.metric("✅ 正解数", f"{score} / {TOTAL_Q} 問")
    c3.metric("コース", f"{st.session_state.en_course}")
    st.write("".join("⭕" if ok else "❌" for ok in st.session_state.en_log))

    if score == TOTAL_Q:
        st.balloons()
        st.success("🥇 パーフェクト！ 英語マスターだ！")
    elif score >= 7:
        st.success("🥈 すばらしい！ あと少しで満点だよ。")
    else:
        st.info("🌱 よくがんばったね！ まちがえた問題を見なおして、もう一回やってみよう。")

    wrong = [
        (q, ok) for q, ok in zip(st.session_state.en_questions, st.session_state.en_log) if not ok
    ]
    if wrong:
        with st.expander(f"👀 まちがえた問題を見なおす（{len(wrong)}問）", expanded=True):
            for q, _ in wrong:
                st.markdown(f"**{q['emoji'] + ' ' if q.get('emoji') else ''}{q['prompt']}**　→　**{q['answer']}**")
                if q.get("translation"):
                    st.caption(f"日本語訳：{q['translation']}")
                if q.get("explanation"):
                    st.caption(q["explanation"])

    st.divider()
    col_same, col_new = st.columns(2)
    with col_same:
        if st.button("🔁 同じ問題をもう一度", use_container_width=True):
            questions = st.session_state.en_questions
            keep = {k: st.session_state[k] for k in ("en_course", "en_level", "en_topic", "en_assist")}
            common.reset_state("en_", DEFAULTS)
            for key, value in keep.items():
                st.session_state[key] = value
            for q in questions:
                random.shuffle(q["choices"])
            st.session_state.en_questions = questions
            st.session_state.en_state = "playing"
            st.rerun()
    with col_new:
        if st.button("🔄 べつの問題をつくる", type="primary", use_container_width=True):
            common.reset_state("en_", DEFAULTS)
            st.rerun()
