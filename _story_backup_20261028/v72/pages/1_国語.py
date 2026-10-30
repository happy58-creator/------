import json
import random
import time

import streamlit as st
from google.genai import types

import auth
import common
import history
import kokugo_logic as K
import pdfgen

common.setup_page("AI国語アドベンチャー", "🧙‍♂️")
common.hero("🧙‍♂️ AI国語わくわくアドベンチャー 🌟", "入力したテーマに合わせて、AIがその場で『世界にひとつだけの国語教材』を作ります！")

client = common.get_gemini_client()

DEFAULTS = {
    "jp_state": "menu",  # menu, playing, ending
    "jp_step": 1,
    "jp_score": 0,
    "jp_quiz": None,
    "jp_theme": "",
    "jp_grade": "",
    "jp_answer": None,  # 今の問題で答えた結果 {"typed", "ok", "note"}
    "jp_retry": "",     # 採点しないで書き直してもらうときのひとこと
    "jp_log": [],  # 各問題の結果 (正解したか)
    "jp_rows": [],  # PDF・履歴用 (問題, あなたの答え, 正しい答え, 正解か)
    "jp_played_at": "",
}
common.init_state(DEFAULTS)

KIND_LABELS = {
    "read": "📖 漢字の読み（漢字 → ひらがな）",
    "write": "✍️ 漢字の書き取り（ひらがな → 漢字）",
    "text": "💭 文章問題",
}
KIND_HOWTO = {
    "read": "【　】の漢字の 読み方を、ひらがなで書こう。",
    "write": "【　】のひらがなを、漢字（と送りがな）で書こう。",
}


def build_prompt(theme, grade):
    return f"""
あなたは{K.GRADE_NAMES[grade]}を受け持つ、やさしくて話のうまい国語の先生です。
子どもが入力したテーマ「{theme}」から、全10章のワクワクする冒険ストーリーと、国語の問題10問を作ってください。

【まずテーマの確認】
- テーマが意味のない文字の並び（例：「あいあいあ」「ふぁふぁふぁ」「ぬるもら」のような でたらめ）や、
  子どもにふさわしくない言葉（暴力・性的・悪口など）なら "theme_ok": false にして、"theme_reason" に短い理由を書き、
  chapters と questions は空の配列にしてください。ふつうの言葉なら "theme_ok": true。

【対象】{K.GRADE_NAMES[grade]}
- 文章：{K.reading_level(grade)}
- 漢字：{K.kanji_range(grade)}の中から出すこと。範囲外の漢字は、問題にも本文にも使わない（ひらがなにする）。

【お話】全10章。テーマの世界にぴったり合う流れにする（テーマと関係ない物や生き物を無理に出さない）。
- 各章に、テーマに合った短い章タイトル（先頭に合う絵文字1つ、例：「🚀 第3章：あやしい信号」）と、本文（{"80〜120" if K.GRADES.index(grade) < 2 else "120〜180"}文字）。
- 起承転結がわかるように：はじまり → 出会い・事件 → ピンチ → 工夫や協力 → 結末（主人公の成長）。

【問題】全10問。第n問は第n章の本文をもとにする。
- 第1〜3問「漢字の読み」：本文に出てくる言葉から、その学年にふさわしい漢字の言葉を1つ選び、
  "text" はその言葉をふくむ短い1文で、言葉を【】でかこむ（例：「未知の星を【探検】する。」）。
  "word" は【】の中の漢字の言葉そのもの。"answers" は正しい読み（ひらがなだけ。読みが2通りある場合は両方）。
- 第4〜6問「漢字の書き取り」：その学年で書けるようにする漢字の言葉（送りがながある動詞・形容詞を少なくとも1問ふくめる）。
  "text" はその言葉をひらがなにして【】でかこんだ短い1文（例：「ふねで 海を【わたる】。」）。
  "reading" は【】の中のひらがな。"answers" は正しい書き方（送りがなまで正しく。例：["渡る"]。別の正しい書き方があれば両方）。
- 第7〜10問「文章問題」：3択。4問とも ちがう観点にする。観点は次から4つ：
  登場人物の気持ち／行動の理由／言葉や表現の意味／場面の様子／心の変化／話の順序やつながり／指示語がさすもの
  "view" に観点、"text" に問題文（毎回ちがう聞き方で）、"opts" に選択肢3つ（まぎらわしいが、本文を読めば1つに決まる）、
  "ans" に正解（opts のどれかと完全に同じ文字列）。
- どの問題も "ok"（正解したときのほめ言葉と短い解説）と "ng"（まちがえたときのやさしい解説。答えの理由がわかるように）を書く。

次のJSONだけを出力してください（説明やあいさつは書かない）。
{{
  "theme_ok": true,
  "theme_reason": "",
  "chapters": [{{"title": "...", "story": "..."}}],
  "questions": [
    {{"text": "...【探検】...", "word": "探検", "answers": ["たんけん"], "ok": "...", "ng": "..."}},
    {{"text": "...【わたる】...", "reading": "わたる", "answers": ["渡る"], "ok": "...", "ng": "..."}},
    {{"view": "登場人物の気持ち", "text": "...", "opts": ["...", "...", "..."], "ans": "...", "ok": "...", "ng": "..."}}
  ]
}}
（chapters と questions は、それぞれ10こ。questions は 読み3つ → 書き取り3つ → 文章問題4つ の順）
"""


def generate_quiz_with_ai(theme, grade):
    """(quiz, None) か (None, ふざけた入力の理由) か (None, None)（エラー）"""
    last_error = None
    for _ in range(3):  # 形が崩れたときは、やり直す
        try:
            response = client.models.generate_content(
                model=common.GEMINI_MODEL,
                contents=build_prompt(theme, grade),
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.8),
            )
            data = json.loads(response.text)
            if isinstance(data, dict) and data.get("theme_ok") is False:
                return None, "AIの判定：" + (str(data.get("theme_reason") or "意味のない言葉"))[:60]
            return K.shuffle_choices(K.validate(data)), None
        except Exception as e:
            last_error = e
    st.error(f"AIが問題を作るときにエラーが起きちゃったみたい。もう一度ためしてね：{last_error}")
    return None, None


def report_silly(theme, reason):
    """ふざけた入力：画面で知らせて、記録する（管理者が「せいせきの履歴」の「入力チェック」で見られる）"""
    history.log_result("入力チェック", ページ="国語", 入力=theme, 理由=reason, 学年=st.session_state.get("jp_grade_pick", ""))
    st.error("🚨 この入力は記録されました。どんなテーマで遊ぶか、おうちの人と相談してみよう。")


def pdf_info():
    return f"テーマ：{st.session_state.jp_theme}　学年：{K.GRADE_NAMES.get(st.session_state.jp_grade, '')}"


def correct_text(q):
    if q["kind"] == "text":
        return q["ans"]
    return "／".join(q["answers"])


def record_answer(typed, ok, note=""):
    st.session_state.jp_answer = {"typed": typed, "ok": ok, "note": note}
    st.session_state.jp_retry = ""


def go_next():
    step = st.session_state.jp_step
    q = st.session_state.jp_quiz["questions"][step - 1]
    ans = st.session_state.jp_answer
    question = f"{KIND_LABELS[q['kind']].split(' ', 1)[1]} {q['text']}"
    if q["kind"] == "text":
        question = f"文章問題（{q['view']}） {q['text']}\n（{'／'.join(q['opts'])}）"
    st.session_state.jp_rows.append((question, ans["typed"], correct_text(q), ans["ok"]))
    st.session_state.jp_log.append(ans["ok"])
    if ans["ok"]:
        st.session_state.jp_score += K.POINT
    st.session_state.jp_answer = None
    st.session_state.jp_retry = ""
    st.session_state.jp_step += 1
    if st.session_state.jp_step > K.TOTAL:
        st.session_state.jp_state = "ending"
        st.session_state.jp_played_at = time.strftime("%Y-%m-%d %H:%M:%S")
        history.log_result(
            "国語", テーマ=st.session_state.jp_theme, 点数=st.session_state.jp_score,
            詳細=pdfgen.make_record("AI国語アドベンチャー", pdf_info(), st.session_state.jp_rows),
            学年=K.GRADE_NAMES.get(st.session_state.jp_grade, ""),
        )


def start_play(quiz, theme, grade):
    common.reset_state("jp_", DEFAULTS)
    st.session_state.jp_quiz = quiz
    st.session_state.jp_theme = theme
    st.session_state.jp_grade = grade
    st.session_state.jp_state = "playing"
    st.rerun()


# --- メニュー ---
if st.session_state.jp_state == "menu":
    age_grade = K.grade_for_age(st.session_state.get("auth_age"))
    with st.container(border=True):
        st.subheader("🎓 学年")
        if auth.is_admin() or age_grade is None:
            # 管理者（年齢の登録がない人）は、学年をえらべる
            default = st.session_state.get("jp_grade_pick") or age_grade or K.DEFAULT_GRADE
            grade = st.selectbox("学年をえらんでね", K.GRADES, index=K.GRADES.index(default),
                                 format_func=lambda g: K.GRADE_NAMES[g], key="jp_grade_pick")
        else:
            grade = age_grade
            st.session_state.jp_grade_pick = grade
            st.markdown(f"**{K.GRADE_NAMES[grade]}** の問題が出るよ（{st.session_state.auth_age}さい）")

        st.subheader("✍️ どんなお話で遊びたい？テーマを教えてね！")
        st.caption(f"（例：恐竜、マインクラフト、魔法学校、宇宙飛行士、ねこ、など何でもOK！ {K.THEME_MAX}文字まで）")
        with st.form("jp_theme_form"):
            theme_input = st.text_input("すきな言葉（キーワード）：", placeholder="ここに文字を入力してね")
            submitted = st.form_submit_button("🚀 このテーマでAIに問題を作ってもらう！", type="primary", use_container_width=True)

    if submitted:
        theme = theme_input.strip()
        problem = K.theme_problem(theme)
        if problem and problem[0] == "empty":
            st.warning("⚠️ 言葉を入力してね！")
        elif problem and problem[0] == "long":
            st.warning(f"📏 テーマを もう少し短く入力してね（{K.THEME_MAX}文字まで。いまは {len(theme)}文字）")
        elif problem:
            report_silly(theme, problem[1])
        else:
            with st.spinner("🧙‍♂️ AI先生が、キミのために特別なお話とクイズを作成中だよ...（20秒くらい待ってね）"):
                quiz, silly = generate_quiz_with_ai(theme, grade)
            if silly:
                report_silly(theme, silly)
            elif quiz:
                start_play(quiz, theme, grade)

# --- プレイ ---
elif st.session_state.jp_state == "playing":
    data = st.session_state.jp_quiz
    step = st.session_state.jp_step
    chapter = data["chapters"][step - 1]
    q = data["questions"][step - 1]

    st.caption(f"テーマ：{st.session_state.jp_theme}　／　{K.GRADE_NAMES.get(st.session_state.jp_grade, '')}"
               f"　／　いまの点数：{st.session_state.jp_score}点")
    st.progress((step - 1) / K.TOTAL, text=f"第{step}問 / {K.TOTAL}問")
    st.header(chapter["title"])
    st.info(chapter["story"])
    st.subheader(f"❓ 第{step}問　{KIND_LABELS[q['kind']]}" + (f"（{q['view']}）" if q["kind"] == "text" else ""))
    if q["kind"] in KIND_HOWTO:
        st.caption(KIND_HOWTO[q["kind"]])
    st.markdown(f"#### {q['text']}")

    ans = st.session_state.jp_answer
    if ans is None:
        if q["kind"] == "text":
            choice = st.radio("どれかな？", q["opts"], index=None, key=f"jp_radio_{step}")
            if st.button("これで決定！", disabled=choice is None, type="primary"):
                record_answer(choice, choice == q["ans"])
                st.rerun()
        else:
            with st.form(f"jp_form_{step}"):
                label = "読み方（ひらがな）" if q["kind"] == "read" else "漢字で書こう"
                typed = st.text_input(label, key=f"jp_typed_{step}")
                sent = st.form_submit_button("これで決定！", type="primary")
            if st.session_state.jp_retry:
                st.warning(st.session_state.jp_retry)
            if sent:
                if q["kind"] == "read":
                    result, note = K.check_reading(typed, q["answers"])
                else:
                    result, note = K.check_writing(typed, q["answers"], q.get("reading", ""))
                if result == "retry":                # 書き方のまちがい（ひらがなで書いた など）は、採点しないで書き直し
                    st.session_state.jp_retry = "✏️ " + note
                else:
                    record_answer(typed.strip(), result == "ok", note)
                st.rerun()
    else:
        if q["kind"] == "text":
            st.radio("どれかな？", q["opts"], index=q["opts"].index(ans["typed"]), key=f"jp_radio_{step}", disabled=True)
        else:
            st.markdown(f"キミの答え：**{ans['typed']}**")
        if ans["ok"]:
            st.success("⭕ せいかい！ " + q["ok"])
        else:
            note = f"{ans['note']}\n\n" if ans.get("note") else ""
            st.error(f"❌ ざんねん… 正しい答えは「{correct_text(q)}」だよ。\n\n{note}" + q["ng"])
        label = "結果発表へ！ 🏆" if step == K.TOTAL else "次の問題へ進む ➡️"
        st.button(label, on_click=go_next, type="primary", use_container_width=True)

# --- 結果 ---
elif st.session_state.jp_state == "ending":
    score = st.session_state.jp_score
    st.header("🏆 大冒険お疲れさまでした！ 🏆")
    st.subheader(f"キミの点数は... 【 {score}点 / 100点 】 🎯")
    st.write("".join("⭕" if ok else "❌" for ok in st.session_state.jp_log))
    rows = st.session_state.jp_rows
    parts = (("漢字の読み", 0, K.READ_N), ("漢字の書き取り", K.READ_N, K.READ_N + K.WRITE_N), ("文章問題", K.READ_N + K.WRITE_N, K.TOTAL))
    st.caption("　".join(f"{name}：{sum(r[3] for r in rows[a:b])} / {b - a}" for name, a, b in parts))

    if score == 100:
        st.balloons()
        st.success("🥇 【ランク：国語マスター神】")
        st.write("すごすぎる！全問大正解！漢字の読み書きも読解も完璧（かんぺき）にクリアしたね！")
    elif score >= 60:
        st.warning("🥈 【ランク：一流の冒険家】")
        st.write("素晴らしい！お話の気持ちの変化をしっかり読み解くことができたね。次はちがうテーマで満点を目指そう！")
    else:
        st.info("🏃 【ランク：みならい冒険家】")
        st.write("お疲れさま！AI先生のお話は楽しかったかな？次はキミの大好きな別のテーマを入力してリベンジだ！")

    common.pdf_preview_button(
        pdfgen.build_pdf(
            "AI国語アドベンチャー", pdf_info(), st.session_state.get("player_name", ""),
            st.session_state.jp_played_at, score, st.session_state.jp_rows,
        ),
    )

    st.divider()
    col_same, col_new = st.columns(2)
    with col_same:
        if st.button("🔁 同じお話をもう一度", use_container_width=True):
            quiz, theme, grade = st.session_state.jp_quiz, st.session_state.jp_theme, st.session_state.jp_grade
            start_play(K.shuffle_choices(quiz, random), theme, grade)
    with col_new:
        if st.button("🔄 別のテーマで新しく遊ぶ", type="primary", use_container_width=True):
            common.reset_state("jp_", DEFAULTS)
            st.rerun()
