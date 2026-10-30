import json
import random
import time

import streamlit as st
from google.genai import types

import auth
import common
import history
import kokugo_classics as KC
import kokugo_lessons as KL
import kokugo_logic as K
import learn_log
import pdfgen

common.setup_page("AI国語アドベンチャー", "🧙‍♂️")
common.hero("🧙‍♂️ AI国語わくわくアドベンチャー 🌟", "入力したテーマに合わせて、AIがその場で『世界にひとつだけの国語教材』を作ります！")

client = common.get_gemini_client()

DEFAULTS = {
    "jp_state": "menu",  # menu, playing, ending, lecture（古典の講座）, work（作品を読む）
    "jp_step": 1,
    "jp_score": 0,
    "jp_quiz": None,
    "jp_theme": "",
    "jp_grade": "",
    "jp_course": "",
    "jp_passage": None,  # 古典の本文（kokugo_classics の1つ）
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
    "text": "💭 読解",
    "essay": "📝 自分で書こう",
    "kana": "📜 古典のかなづかい",
    "classic": "📜 古典の読解",
}
KIND_HOWTO = {
    "read": "【　】の漢字の 読み方を、ひらがなで書こう。",
    "write": "【　】のひらがなを、漢字（と送りがな）で書こう。",
    "kana": "【　】の言葉を、今のかなづかい（現代かなづかい）に直して、ひらがなで書こう。",
}


def section_text(genre, n, passage):
    name, _, _ = K.GENRES[genre]
    if genre == "story":
        return (f"全{n}章のワクワクする冒険の物語。テーマの世界にぴったり合う流れにする（テーマと関係ない物や生き物を無理に出さない）。"
                "起承転結がわかるように（はじまり → 事件 → ピンチ → 工夫や協力 → 結末と成長）。"
                "各章のタイトルは、先頭に合う絵文字1つ＋「第○章：…」。")
    if genre == "guide":
        return (f"古典作品『{passage['title']}』（{passage['author']}・{passage['era']}）へ案内する文章を全{n}章。"
                "テーマの世界の人物がこの作品に出会う、などテーマと作品を自然につなぎ、作品の時代や作者、読みどころを紹介する。"
                "古典の本文そのものは書き写さない。各章のタイトルは、先頭に絵文字1つ＋短い見出し。")
    return (f"テーマについての{name}を全{n}段落。段落ごとに短い小見出し（先頭に絵文字1つ）と本文。"
            "段落どうしのつながり（問題提起・具体例・対比・まとめ など）がはっきりわかる構成にする。")


def question_spec(plan, genre):
    views = "／".join(K.GENRES[genre][2])
    lines = []
    for n, kind in enumerate(plan, 1):
        if kind == "read":
            lines.append(f"- 第{n}問 漢字の読み：文章から学年にふさわしい漢字の言葉を1つ。text はその言葉をふくむ短い1文で、言葉を【】でかこむ。"
                         "word は【】の中の漢字の言葉、answers は正しい読み（ひらがなだけ）。")
        elif kind == "write":
            lines.append(f"- 第{n}問 漢字の書き取り：学年で書けるようにする漢字の言葉（送りがなのある動詞・形容詞もまぜる）。"
                         "text はその言葉をひらがなにして【】でかこんだ短い1文。reading は【】の中のひらがな、answers は正しい書き方（送りがなまで正しく）。")
        elif kind == "text":
            lines.append(f"- 第{n}問 読解（3択）：view に観点（次からえらび、読解の問題どうしで同じ観点を使わない：{views}）、"
                         "text に問題文（毎回ちがう聞き方で）、opts に選択肢3つ（まぎらわしいが本文を読めば1つに決まる）、ans に正解（opts のどれかと同じ文字列）。")
        elif kind == "essay":
            lines.append(f"- 第{n}問 自分で書く：テーマにそった要約・意見文・スピーチ原稿など（2問で種類を変える）。"
                         "text に指示（目的・読み手・条件・字数を具体的に）、limit に字数の [下限, 上限]（例：[100, 200]）、rubric に採点の観点を3つ。")
        elif kind == "kana":
            lines.append(f"- 第{n}問 古典のかなづかい：古典の本文から歴史的かなづかいをふくむ言葉を1つ（本文のとおりに）。"
                         "text は「【やうやう】を現代かなづかいに直して、ひらがなで書こう。」の形。word は【】の中の言葉（本文のとおり）、answers は現代かなづかいのひらがな。")
        elif kind == "classic":
            lines.append(f"- 第{n}問 古典の読解（3択）：古典の本文について。view に観点（次からえらび、古典の問題どうしで同じ観点を使わない："
                         f"{'／'.join(K.VIEWS_CLASSIC)}）、text に問題文、opts に選択肢3つ、ans に正解。本文と参考の現代語訳にもとづき、本文にないことは問わない。")
    return "\n".join(lines)


def build_prompt(theme, grade, course_id, plan, passage):
    course = K.COURSES[course_id]
    genre = course["genre"]
    n_sec = K.section_count(plan)
    passage_block = ""
    if passage:
        passage_block = (f"\n【古典の本文】『{passage['title']}』{passage['author']}（{passage['era']}・{KC.KIND_NAMES[passage['kind']]}）\n"
                         f"{passage['text']}\n【参考：現代語訳】\n{passage['yaku']}\n")
    return f"""
あなたは{K.GRADE_NAMES[grade]}の国語（科目：{course['name']}）を受け持つ、やさしくて話のうまい先生です。
生徒が入力したテーマ「{theme}」をもとに、文章と国語の問題{len(plan)}問を作ってください。

【まずテーマの確認】
- テーマが意味のない文字の並び（例：「あいあいあ」「ぬるもら」のような でたらめ）や、子どもにふさわしくない言葉（暴力・性的・悪口など）なら
  "theme_ok": false にして "theme_reason" に短い理由を書き、chapters と questions は空の配列にする。ふつうの言葉なら "theme_ok": true。

【対象】{K.GRADE_NAMES[grade]}
- 文章：{K.reading_level(grade)}
- 漢字：{K.kanji_range(grade)}の中から出すこと。範囲外の漢字は使わない（ひらがなにする）。
{passage_block}
【文章（chapters）】{section_text(genre, n_sec, passage)}
- 1章（1段落）は{"80〜120" if K.GRADES.index(grade) < 2 else "120〜200"}文字。chapters はちょうど{n_sec}こ。title と story を持つ。
- 古典以外の問題は、出てくる順に、第1章・第2章…の文章をもとにする（1問につき1章）。

【問題（questions）】ちょうど{len(plan)}問、次の順番で。
{question_spec(plan, genre)}
- どの問題も "ok"（正解したときのほめ言葉と短い解説）と "ng"（まちがえたときのやさしい解説）を書く。自分で書く問題は ok と ng に、書き方のポイントを書く。

次の形のJSONだけを出力してください（説明やあいさつは書かない）。
{{"theme_ok": true, "theme_reason": "", "chapters": [{{"title": "...", "story": "..."}}],
  "questions": [{{"text": "...", "word": "...", "reading": "...", "answers": ["..."], "view": "...", "opts": ["...", "...", "..."], "ans": "...",
                 "limit": [100, 200], "rubric": ["...", "...", "..."], "ok": "...", "ng": "..."}}]}}
（それぞれの問題では、その種類に必要な項目だけ書けばよい）
"""


def pick_passage(theme, course_id):
    """テーマに近い古典を、用意した本文の中からAIにえらんでもらう（だめなら言葉の一致か、ランダム）"""
    school, kinds = K.COURSES[course_id]["classic"]
    items = KC.candidates(school, kinds)
    catalog = "\n".join(f"{c['id']}：{c['title']}（{'・'.join(c['tags'][:6])}）" for c in items)
    try:
        response = client.models.generate_content(
            model=common.GEMINI_MODEL,
            contents=f"テーマ「{theme}」に、内容がいちばん近い作品を次の一覧から1つえらび、JSON {{\"id\": \"...\"}} だけを出力してください。\n{catalog}",
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.3),
        )
        cid = json.loads(response.text).get("id")
        found = [c for c in items if c["id"] == cid]
        if found:
            return found[0]
    except Exception:
        pass
    return KC.pick_by_tags(theme, items, random)


def generate_quiz_with_ai(theme, grade, course_id, passage):
    """(quiz, None) か (None, ふざけた入力の理由) か (None, None)（エラー）"""
    plan = K.course_plan(course_id, passage)
    last_error = None
    for _ in range(3):  # 形が崩れたときは、やり直す
        try:
            response = client.models.generate_content(
                model=common.GEMINI_MODEL,
                contents=build_prompt(theme, grade, course_id, plan, passage),
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.8),
            )
            data = json.loads(response.text)
            if isinstance(data, dict) and data.get("theme_ok") is False:
                return None, "AIの判定：" + (str(data.get("theme_reason") or "意味のない言葉"))[:60]
            return K.shuffle_choices(K.validate(data, plan, passage)), None
        except Exception as e:
            last_error = e
    st.error(f"AIが問題を作るときにエラーが起きちゃったみたい。もう一度ためしてね：{last_error}")
    return None, None


def grade_essay(q, answer):
    """自分で書いた文章を、AIが観点ごとに見て 0〜10点で採点する（目安）。(点数, よいところ, アドバイス) か None"""
    prompt = f"""あなたは{K.GRADE_NAMES[st.session_state.jp_grade]}の国語の先生です。生徒が書いた文章を採点してください。
【問題】{q['text']}
【字数】{q['limit'][0]}〜{q['limit'][1]}字
【採点の観点】{'／'.join(q['rubric'])}
【生徒の文章】
{answer}

観点ごとに見て、10点満点で点数をつけてください。学年に合わせて、よいところは具体的にほめ、直すとよいところを1〜2つ、やさしく書いてください。
次のJSONだけを出力：{{"score": 0〜10の整数, "good": "よいところ", "advice": "直すとよいところ"}}"""
    for _ in range(2):
        try:
            response = client.models.generate_content(
                model=common.GEMINI_MODEL, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
            )
            return K.essay_score(json.loads(response.text))
        except Exception:
            continue
    return None


def report_silly(theme, reason):
    """ふざけた入力：画面で知らせて、記録する（管理者が「せいせきの履歴」の「入力チェック」で見られる）"""
    history.log_result("入力チェック", ページ="国語", 入力=theme, 理由=reason, 学年=st.session_state.get("jp_grade_pick", ""))
    st.error("🚨 この入力は記録されました。どんなテーマで遊ぶか、おうちの人と相談してみよう。")


def course_name():
    c = K.COURSES.get(st.session_state.jp_course)
    return c["name"] if c else ""


def pdf_info():
    info = f"テーマ：{st.session_state.jp_theme}　学年：{K.GRADE_NAMES.get(st.session_state.jp_grade, '')}　科目：{course_name()}"
    if st.session_state.jp_passage:
        info += f"　古典：{KC.get(st.session_state.jp_passage)['title']}"
    return info


def correct_text(q):
    if q["kind"] in ("text", "classic"):
        return q["ans"]
    if q["kind"] == "essay":
        return "（AIの採点）"
    return "／".join(q["answers"])


def record_answer(typed, ok, note="", points=None):
    st.session_state.jp_answer = {"typed": typed, "ok": ok, "note": note,
                                  "points": (K.POINT if ok else 0) if points is None else points}
    st.session_state.jp_retry = ""


def go_next():
    step = st.session_state.jp_step
    q = st.session_state.jp_quiz["questions"][step - 1]
    ans = st.session_state.jp_answer
    question = f"{KIND_LABELS[q['kind']].split(' ', 1)[1]} {q['text']}"
    if q["kind"] in ("text", "classic"):
        question = f"{K.KIND_NAMES[q['kind']]}（{q['view']}） {q['text']}\n（{'／'.join(q['opts'])}）"
    typed = ans["typed"] + (f"（{ans['points']}/10点）" if q["kind"] == "essay" else "")
    st.session_state.jp_rows.append((question, typed, correct_text(q), ans["ok"]))
    st.session_state.jp_log.append(ans["ok"])
    st.session_state.jp_score += ans["points"]
    st.session_state.jp_answer = None
    st.session_state.jp_retry = ""
    st.session_state.jp_step += 1
    if st.session_state.jp_step > K.TOTAL:
        st.session_state.jp_state = "ending"
        st.session_state.jp_played_at = time.strftime("%Y-%m-%d %H:%M:%S")
        history.log_result(
            "国語", テーマ=st.session_state.jp_theme, 点数=st.session_state.jp_score,
            詳細=pdfgen.make_record("AI国語アドベンチャー", pdf_info(), st.session_state.jp_rows),
            学年=K.GRADE_NAMES.get(st.session_state.jp_grade, ""), 科目=course_name(),
        )


def start_play(quiz, theme, grade, course_id, passage_id):
    common.reset_state("jp_", DEFAULTS)
    st.session_state.jp_quiz = quiz
    st.session_state.jp_theme = theme
    st.session_state.jp_grade = grade
    st.session_state.jp_course = course_id
    st.session_state.jp_passage = passage_id
    st.session_state.jp_state = "playing"
    st.rerun()


SUBJECT = "国語"
LEC_PAGES = ["ポイント", "例", "やってみよう", "まとめ"]
QUIZ_COURSE = {"中1": "chu1", "中2": "chu_koten", "中3": "chu_koten", "高1": "gengo_bunka", "高2": "koten_tankyu", "高3": "koten_tankyu"}


def school_of(grade):
    return "高" if grade.startswith("高") else ("中" if grade.startswith("中") else "小")


def learned_mark(uid):
    return "✓ " if uid in learn_log.learned(SUBJECT) else ""


def open_lecture(lid, grade):
    ss = st.session_state
    ss.jp_state, ss.jp_lid, ss.jp_lpage, ss.jp_lgrade = "lecture", lid, 0, grade
    new_lecture_quiz()
    st.rerun()


def new_lecture_quiz():
    ss = st.session_state
    ss.jp_lquiz = KL.make_quiz(ss.jp_lid, random.Random())
    ss.jp_lchecked = False
    for i in range(5):
        ss.pop(f"jp_lq_{i}", None)


def open_work(wid, grade):
    ss = st.session_state
    ss.jp_state, ss.jp_wid, ss.jp_lgrade = "work", wid, grade
    st.rerun()


def show_passage(passage):
    st.markdown(passage["text"].replace("\n", "  \n"))
    if passage.get("hakubun"):
        st.caption("白文：" + passage["hakubun"].replace("\n", "　"))


def learn_menu(grade):
    """古典をまなぶ：講座と作品の一覧"""
    school = school_of(grade)
    lectures = KL.lectures_for(school)
    works = KC.candidates("高" if school == "高" else "中", tuple(KC.KIND_NAMES))
    done = learn_log.learned(SUBJECT)
    total = len(lectures) + len(works)
    got = sum(1 for lec in lectures if "lec_" + lec["id"] in done) + sum(1 for w in works if "work_" + w["id"] in done)
    st.caption(f"📖 まなんだ：{got} / {total}（✓ がついているよ）")
    with st.container(border=True):
        st.subheader("🎓 ミニ講座")
        cols = st.columns(2)
        for i, lec in enumerate(lectures):
            if cols[i % 2].button(f"{learned_mark('lec_' + lec['id'])}{lec['emoji']} {lec['title']}", key=f"jp_lec_{lec['id']}", use_container_width=True):
                open_lecture(lec["id"], grade)
    with st.container(border=True):
        st.subheader("📜 作品を読む")
        st.caption("原文と現代語訳、読みどころ。読んだあと、その作品で問題にも挑戦できるよ。")
        for kind in KC.KIND_NAMES:
            items = [w for w in works if w["kind"] == kind]
            if not items:
                continue
            st.markdown(f"**{KC.KIND_NAMES[kind]}**")
            cols = st.columns(2)
            for i, w in enumerate(items):
                if cols[i % 2].button(f"{learned_mark('work_' + w['id'])}{w['title']}", key=f"jp_work_{w['id']}", use_container_width=True):
                    open_work(w["id"], grade)


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

        course_ids = K.courses_for(grade)
        if len(course_ids) > 1:
            st.subheader("📚 科目")
            course_id = st.radio("科目をえらんでね", course_ids, key=f"jp_course_pick_{grade}", label_visibility="collapsed",
                                 format_func=lambda c: f"{K.COURSES[c]['name']}　―　{K.COURSES[c]['desc']}")
        else:
            course_id = course_ids[0]
            st.caption(f"📚 {K.COURSES[course_id]['name']}：{K.COURSES[course_id]['desc']}")

        mode = "quiz"
        if K.GRADES.index(grade) >= 4:          # 小5から：古典をまなぶ
            mode = st.radio("なにをする？", ["quiz", "learn"], horizontal=True, key="jp_mode",
                            format_func=lambda m: {"quiz": "🏁 問題にちょうせん", "learn": "📖 古典をまなぶ"}[m])
    if mode == "learn":
        learn_menu(grade)
        st.stop()
    with st.container(border=True):
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
            with st.spinner("🧙‍♂️ AI先生が、キミのために特別な文章と問題を作成中だよ...（20〜30秒くらい待ってね）"):
                passage = pick_passage(theme, course_id) if "classic" in K.COURSES[course_id] else None
                quiz, silly = generate_quiz_with_ai(theme, grade, course_id, passage)
            if silly:
                report_silly(theme, silly)
            elif quiz:
                start_play(quiz, theme, grade, course_id, passage["id"] if passage else None)

# --- プレイ ---
elif st.session_state.jp_state == "playing":
    data = st.session_state.jp_quiz
    step = st.session_state.jp_step
    q = data["questions"][step - 1]
    passage = KC.get(st.session_state.jp_passage) if st.session_state.jp_passage else None
    total = len(data["questions"])

    st.caption(f"テーマ：{st.session_state.jp_theme}　／　{K.GRADE_NAMES.get(st.session_state.jp_grade, '')}・{course_name()}"
               f"　／　いまの点数：{st.session_state.jp_score}点")
    st.progress((step - 1) / total, text=f"第{step}問 / {total}問")
    if q["section"] is not None:
        chapter = data["chapters"][q["section"]]
        st.header(chapter["title"])
        st.info(chapter["story"])
    else:
        st.header(f"📜 {passage['title']}")
        st.caption(f"{passage['author']}／{passage['era']}／{KC.KIND_NAMES[passage['kind']]}")
        with st.container(border=True):
            st.markdown(passage["text"].replace("\n", "  \n"))
            if passage.get("hakubun"):
                st.caption("白文：" + passage["hakubun"].replace("\n", "　"))
    st.subheader(f"❓ 第{step}問　{KIND_LABELS[q['kind']]}" + (f"（{q['view']}）" if q["kind"] in ("text", "classic") else ""))
    if q["kind"] in KIND_HOWTO:
        st.caption(KIND_HOWTO[q["kind"]])
    st.markdown(f"#### {q['text']}")
    if q["kind"] == "essay":
        st.caption(f"字数：{q['limit'][0]}〜{q['limit'][1]}字　／　採点の観点：{'・'.join(q['rubric'])}　（AIの採点なので、点数は目安だよ）")

    ans = st.session_state.jp_answer
    if ans is None:
        if q["kind"] in ("text", "classic"):
            choice = st.radio("どれかな？", q["opts"], index=None, key=f"jp_radio_{step}")
            if st.button("これで決定！", disabled=choice is None, type="primary"):
                record_answer(choice, choice == q["ans"])
                st.rerun()
        elif q["kind"] == "essay":
            with st.form(f"jp_form_{step}"):
                typed = st.text_area("ここに書こう", key=f"jp_typed_{step}", height=200)
                sent = st.form_submit_button("これで提出！", type="primary")
            if st.session_state.jp_retry:
                st.warning(st.session_state.jp_retry)
            if sent:
                length = len(K.clean(typed))
                lo, hi = q["limit"]
                if length < lo // 2:
                    st.session_state.jp_retry = f"✏️ もう少し書いてみよう（いま {length}字。{lo}字くらいから）"
                elif length > int(hi * 1.5):
                    st.session_state.jp_retry = f"✏️ 長すぎるよ（いま {length}字。{hi}字までにまとめよう）"
                else:
                    with st.spinner("📝 AI先生が読んでいるよ..."):
                        result = grade_essay(q, typed.strip())
                    if result is None:
                        st.session_state.jp_retry = "⚠️ 採点がうまくいかなかったよ。もう一度「提出」を押してね。"
                    else:
                        score, good, advice = result
                        note = (f"👍 よいところ：{good}\n\n" if good else "") + (f"💡 アドバイス：{advice}" if advice else "")
                        record_answer(typed.strip(), score >= 6, note, points=score)
                st.rerun()
        else:
            with st.form(f"jp_form_{step}"):
                label = {"read": "読み方（ひらがな）", "write": "漢字で書こう", "kana": "現代かなづかい（ひらがな）"}[q["kind"]]
                typed = st.text_input(label, key=f"jp_typed_{step}")
                sent = st.form_submit_button("これで決定！", type="primary")
            if st.session_state.jp_retry:
                st.warning(st.session_state.jp_retry)
            if sent:
                if q["kind"] in ("read", "kana"):
                    result, note = K.check_reading(typed, q["answers"])
                else:
                    result, note = K.check_writing(typed, q["answers"], q.get("reading", ""))
                if result == "retry":                # 書き方のまちがい（ひらがなで書いた など）は、採点しないで書き直し
                    st.session_state.jp_retry = "✏️ " + note
                else:
                    record_answer(typed.strip(), result == "ok", note)
                st.rerun()
    else:
        if q["kind"] in ("text", "classic"):
            st.radio("どれかな？", q["opts"], index=q["opts"].index(ans["typed"]), key=f"jp_radio_{step}", disabled=True)
        else:
            st.markdown(f"キミの答え：**{ans['typed']}**")
        if q["kind"] == "essay":
            show = st.success if ans["ok"] else st.warning
            show(f"📝 {ans['points']} / 10点（目安）\n\n{ans['note']}\n\n" + q["ok"])
        elif ans["ok"]:
            st.success("⭕ せいかい！ " + q["ok"])
        else:
            note = f"{ans['note']}\n\n" if ans.get("note") else ""
            st.error(f"❌ ざんねん… 正しい答えは「{correct_text(q)}」だよ。\n\n{note}" + q["ng"])
        if q["section"] is None and passage:
            with st.expander("📖 現代語訳を見る"):
                st.markdown(passage["yaku"].replace("\n", "  \n"))
        label = "結果発表へ！ 🏆" if step == total else "次の問題へ進む ➡️"
        st.button(label, on_click=go_next, type="primary", use_container_width=True)

# --- 古典の講座 ---
elif st.session_state.jp_state == "lecture":
    ss = st.session_state
    lec = KL.get_lecture(ss.jp_lid)
    uid = "lec_" + lec["id"]
    page = ss.jp_lpage
    st.subheader(f"{lec['emoji']} {lec['title']}")
    st.caption(f"{page + 1} / {len(LEC_PAGES)}：{LEC_PAGES[page]}" + ("　✓ まなんだ" if uid in learn_log.learned(SUBJECT) else ""))
    st.progress((page + 1) / len(LEC_PAGES))
    with st.container(border=True):
        if page == 0:
            st.markdown(f"#### 💡 {lec['intro']}")
            st.markdown("**おぼえよう**")
            st.markdown("\n".join(f"- {p}" for p in lec["points"]))
        elif page == 1:
            st.markdown("#### 📜 作品の中で見てみよう")
            for text, note in lec["examples"]:
                st.markdown(f"> {text}")
                st.caption("👉 " + note)
        elif page == 2:
            st.markdown("#### 🙋 やってみよう（点数はつかないよ）")
            with st.form("jp_lquiz_form"):
                for i, q in enumerate(ss.jp_lquiz):
                    st.markdown(f"**{i + 1}.** {q['q']}")
                    if q["type"] == "choice":
                        st.radio("こたえ", q["opts"], index=None, key=f"jp_lq_{i}", label_visibility="collapsed")
                    else:
                        st.text_input("こたえ（ひらがな）", key=f"jp_lq_{i}", label_visibility="collapsed", placeholder="ひらがなで")
                if st.form_submit_button("答えを たしかめる", type="primary"):
                    ss.jp_lchecked = True
            if ss.jp_lchecked:
                for i, q in enumerate(ss.jp_lquiz):
                    got = ss.get(f"jp_lq_{i}") or ""
                    ok = (got == q["ans"]) if q["type"] == "choice" else K.check_reading(got, q["answers"])[0] == "ok"
                    right = q["ans"] if q["type"] == "choice" else q["show"]
                    (st.success if ok else st.error)(f"{i + 1}. {'⭕ せいかい！' if ok else '❌ 答えは「' + right + '」'}　{q['explain']}")
            if st.button("🔄 ちがう問題で もう一度", key="jp_lquiz_new"):
                new_lecture_quiz()
                st.rerun()
        else:
            st.markdown("#### 🎓 まとめ")
            st.markdown("\n".join(f"- {p}" for p in lec["points"]))
            if uid in learn_log.learned(SUBJECT):
                st.success("✓ この講座は まなんだよ！")
            elif st.button("✅ まなんだ！（記録する）", type="primary", use_container_width=True):
                learn_log.mark(SUBJECT, ss.jp_lgrade, uid, lec["title"])
                st.balloons()
                st.rerun()
    col_prev, col_next = st.columns(2)
    if page > 0 and col_prev.button("◀ 前へ", use_container_width=True):
        ss.jp_lpage -= 1
        st.rerun()
    if page < len(LEC_PAGES) - 1 and col_next.button("次へ ▶", type="primary", use_container_width=True):
        ss.jp_lpage += 1
        st.rerun()
    if st.button("↩ 古典の一覧に もどる"):
        ss.jp_state = "menu"
        st.rerun()

# --- 作品を読む ---
elif st.session_state.jp_state == "work":
    ss = st.session_state
    w = KC.get(ss.jp_wid)
    guide = KL.WORK_GUIDES.get(w["id"], {"kind": KC.KIND_NAMES[w["kind"]], "points": []})
    uid = "work_" + w["id"]
    st.subheader(f"📜 {w['title']}")
    st.caption(f"{w['author']}／{w['era']}／{guide['kind']}" + ("　✓ 読んだ" if uid in learn_log.learned(SUBJECT) else ""))
    with st.container(border=True):
        st.markdown("**🔎 読みどころ**")
        st.markdown("\n".join(f"- {p}" for p in guide["points"]))
    show_yaku = st.toggle("現代語訳を となりに 出す", value=True, key="jp_show_yaku")
    paras = w["text"].split("\n\n")
    yakus = w["yaku"].split("\n\n")
    if len(paras) != len(yakus):
        paras, yakus = [w["text"]], [w["yaku"]]
    for para, yaku in zip(paras, yakus):
        if show_yaku:
            col_a, col_b = st.columns(2)
            with col_a, st.container(border=True):
                st.caption("原文" if w["kind"] in ("kobun", "waka", "kindai") else "書き下し文")
                show_passage({"text": para, "hakubun": w.get("hakubun") if len(paras) == 1 else None})
            with col_b, st.container(border=True):
                st.caption("現代語訳" if w["kind"] != "kindai" else "言葉の意味")
                st.markdown(yaku.replace("\n", "  \n"))
        else:
            with st.container(border=True):
                show_passage({"text": para, "hakubun": w.get("hakubun") if len(paras) == 1 else None})
    if uid in learn_log.learned(SUBJECT):
        st.success("✓ この作品は 読んだよ！")
    elif st.button("✅ 読んだ！（記録する）", type="primary", use_container_width=True):
        learn_log.mark(SUBJECT, ss.jp_lgrade, uid, w["title"])
        st.balloons()
        st.rerun()
    course_id = QUIZ_COURSE.get(ss.jp_lgrade)
    if course_id and w["kind"] == "kindai":
        # 近代文学の問題は、高校の「言語文化」の形で出す（中学生には出さない）
        course_id = "gengo_bunka" if school_of(ss.jp_lgrade) == "高" else None
    if course_id:
        if st.button(f"🏁 この作品で問題に挑戦（{K.COURSES[course_id]['name']}・10問）", use_container_width=True):
            with st.spinner("🧙‍♂️ AI先生が、この作品の問題を作成中だよ...（20〜30秒くらい待ってね）"):
                quiz, silly = generate_quiz_with_ai(w["title"], ss.jp_lgrade, course_id, w)
            if quiz:
                start_play(quiz, w["title"], ss.jp_lgrade, course_id, w["id"])
    if st.button("↩ 古典の一覧に もどる"):
        ss.jp_state = "menu"
        st.rerun()

# --- 結果 ---
elif st.session_state.jp_state == "ending":
    score = st.session_state.jp_score
    st.header("🏆 大冒険お疲れさまでした！ 🏆")
    st.subheader(f"キミの点数は... 【 {score}点 / 100点 】 🎯")
    st.write("".join("⭕" if ok else "❌" for ok in st.session_state.jp_log))
    kinds = [q["kind"] for q in st.session_state.jp_quiz["questions"]]
    parts = []
    for kind in dict.fromkeys(kinds):
        idx = [i for i, k in enumerate(kinds) if k == kind]
        parts.append(f"{K.KIND_NAMES[kind]}：{sum(1 for i in idx if st.session_state.jp_log[i])} / {len(idx)}")
    st.caption("　".join(parts))

    if score == 100:
        st.balloons()
        st.success("🥇 【ランク：国語マスター神】")
        st.write("すごすぎる！全問大正解！漢字も読解も完璧（かんぺき）にクリアしたね！")
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
            ss = st.session_state
            start_play(K.shuffle_choices(ss.jp_quiz, random), ss.jp_theme, ss.jp_grade, ss.jp_course, ss.jp_passage)
    with col_new:
        if st.button("🔄 別のテーマで新しく遊ぶ", type="primary", use_container_width=True):
            common.reset_state("jp_", DEFAULTS)
            st.rerun()
