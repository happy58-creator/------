"""AI国語アドベンチャー：テーマを入れると、AIがその学年の文章と10問をつくる。「学ぶ」は読解・文法・言葉・古典の講座と、古典の作品。
画面はぜんぶ JavaScript（web/kokugo）。漢字の読み書きの答え合わせも画面でする（kokugo_logic.check_reading / check_writing と同じ）。
Python は次のことだけ（どれも nonce つきのたのみごと）：
  gen：AIで文章と10問をつくる（ふざけた入力は記録）　essay：自分で書いた文章を AI が採点　done：記録して表彰状
  ai：まちがえた問題の AI先生の解説　learned：学んだ ✓　lquiz：講座の「やってみよう」をつくりなおす"""
import json
import random
import time

import streamlit as st
from google.genai import types

import ai_explain
import auth
import common
import history
import js_page
import kokugo_classics as KC
import kokugo_lessons as KL
import kokugo_logic as K
import learn_log
import pdfgen
import web_games

common.setup_page("AI国語アドベンチャー", "🧙‍♂️")
ss = st.session_state
client = common.get_gemini_client()
SUBJECT = "国語"
QUIZ_COURSE = {"中1": "chu1", "中2": "chu_koten", "中3": "chu_koten", "高1": "gengo_bunka", "高2": "koten_tankyu", "高3": "koten_tankyu"}

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
    raise RuntimeError(f"AIが問題を作るときにエラーが起きちゃったみたい。もう一度ためしてね：{last_error}")


def grade_essay(q, answer, grade):
    """自分で書いた文章を、AIが観点ごとに見て 0〜10点で採点する（目安）。(点数, よいところ, アドバイス) か None"""
    prompt = f"""あなたは{K.GRADE_NAMES[grade]}の国語の先生です。生徒が書いた文章を採点してください。
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



def school_of(grade):
    return "高" if grade.startswith("高") else ("中" if grade.startswith("中") else "小")


def work_course(w, grade):
    """作品で問題を作るときの科目（小学生と、中学生の近代文学は なし）"""
    course_id = QUIZ_COURSE.get(grade)
    if course_id and w["kind"] == "kindai":
        course_id = "gengo_bunka" if school_of(grade) == "高" else None
    return course_id


def course_name(course_id):
    c = K.COURSES.get(course_id)
    return c["name"] if c else ""


def pdf_info(theme, grade, course_id, passage_id):
    info = f"テーマ：{theme}　学年：{K.GRADE_NAMES.get(grade, '')}　科目：{course_name(course_id)}"
    if passage_id:
        info += f"　古典：{KC.get(passage_id)['title']}"
    return info


def max_grade():
    """管理者・年齢がわからない人は全部。ほかの人は、いまの学年まで"""
    g = K.grade_for_age(ss.get("auth_age"))
    return None if (auth.is_admin() or g is None) else g


def grade_ok(grade):
    m = max_grade()
    return grade in K.GRADES and (m is None or K.GRADES.index(grade) <= K.GRADES.index(m))


def pub_lecture(lec):
    return {k: v for k, v in lec.items() if not callable(v)}


def handle(v):
    t = v.get("type")
    grade = v.get("grade") or ""
    if t == "gen":                                      # テーマ（または古典の作品）で、文章と10問をつくる
        if not grade_ok(grade):
            return {"error": "その学年は まだ えらべないよ"}
        course_id = v.get("course")
        if v.get("work"):                               # 学ぶ：この作品で問題に挑戦（科目は作品と学年で決まる）
            w = KC.get(v["work"])
            course_id = work_course(w, grade)
            if not course_id:
                return {"error": "この作品では 問題を作れないよ"}
            theme, passage = w["title"], w
        elif course_id not in K.courses_for(grade):
            return {"error": "えらび方がおかしいよ"}
        else:
            theme = str(v.get("theme") or "").strip()
            problem = K.theme_problem(theme)
            if problem and problem[0] == "empty":
                return {"error": "⚠️ 言葉を入力してね！"}
            if problem and problem[0] == "long":
                return {"error": f"📏 テーマを もう少し短く入力してね（{K.THEME_MAX}文字まで。いまは {len(theme)}文字）"}
            if problem:
                history.log_result("入力チェック", ページ="国語", 入力=theme, 理由=problem[1], 学年=grade)
                return {"silly": True}
            passage = pick_passage(theme, course_id) if "classic" in K.COURSES[course_id] else None
        quiz, silly = generate_quiz_with_ai(theme, grade, course_id, passage)
        if silly:
            history.log_result("入力チェック", ページ="国語", 入力=theme, 理由=silly, 学年=grade)
            return {"silly": True}
        return {"quiz": quiz, "theme": theme, "grade": grade, "course": course_id, "passage": passage}
    if t == "essay":                                    # 自分で書いた文章を、AI が採点（目安）
        q, answer = v.get("q") or {}, str(v.get("answer") or "").strip()
        res = grade_essay(q, answer, grade if grade in K.GRADES else K.DEFAULT_GRADE)
        if res is None:
            return {"error": "⚠️ 採点が うまくいかなかったよ。もう一度「提出」を押してね。"}
        score, good, advice = res
        return {"score": score, "good": good, "advice": advice}
    if t == "done":                                     # 10問おわった：記録して、表彰状をつくる
        rows = [(str(r[0]), str(r[1]), str(r[2]), bool(r[3])) for r in v.get("rows") or []][:K.TOTAL]
        score = max(0, min(100, int(v.get("score") or 0)))
        info = pdf_info(v.get("theme") or "", grade, v.get("course"), v.get("passage"))
        history.log_once("国語", f"jp-{v.get('run')}", テーマ=v.get("theme") or "", 点数=score, 詳細=pdfgen.make_record("AI国語アドベンチャー", info, rows),
                         学年=K.GRADE_NAMES.get(grade, ""), 科目=course_name(v.get("course")))
        pdf = pdfgen.build_pdf("AI国語アドベンチャー", info, ss.get("player_name", ""), time.strftime("%Y-%m-%d %H:%M:%S"), score, rows)
        return {"pdf": js_page.pdf_b64(pdf)}
    if t == "ai":                                       # まちがえた問題の AI先生の解説
        items = [{"q": str(i.get("q")), "user": str(i.get("user")), "correct": str(i.get("correct")), "hint": str(i.get("hint") or "")} for i in v.get("items") or []]
        return {"notes": ai_explain.cached_explanations(f"jp-{v.get('run')}", "国語", K.GRADE_NAMES.get(grade, ""), items)}
    if t == "learned":
        uid = str(v.get("uid") or "")
        if uid.startswith(("lec_", "work_")):
            learn_log.mark(SUBJECT, grade, uid, str(v.get("title") or uid))
        return {}
    if t == "lquiz":
        lid = v.get("lid")
        return {"lid": lid, "quiz": KL.make_quiz(lid, random.Random())}
    return {}


@st.cache_data(show_spinner=False)
def learn_data():
    """学ぶの教材（ぜんぶの学年ぶん。学校ごとの番号は画面でえらぶ）"""
    order = getattr(KL, "GROUP_ORDER", ["読解", "文法・表現", "言葉・漢字", "古典"])
    lectures, by_school = {}, {}
    for s in ("小", "中", "高"):
        ls = sorted(KL.lectures_for(s), key=lambda lec: order.index(lec.get("group", "古典")) if lec.get("group", "古典") in order else len(order))
        by_school[s] = [lec["id"] for lec in ls]
        for lec in ls:
            lectures[lec["id"]] = pub_lecture(lec)
    works, work_school = {}, {}
    for s in ("中", "高"):
        ws = KC.candidates(s, tuple(KC.KIND_NAMES))
        work_school[s] = [w["id"] for w in ws]
        for w in ws:
            works[w["id"]] = w
    guides = {wid: KL.WORK_GUIDES.get(wid, {"kind": KC.KIND_NAMES[w["kind"]], "points": []}) for wid, w in works.items()}
    return {"lectures": lectures, "bySchool": by_school, "works": works, "workSchool": work_school, "guides": guides,
            "kindNames": KC.KIND_NAMES, "groupOrder": order}


def catalog():
    return {"grades": K.GRADES, "gradeNames": K.GRADE_NAMES, "byGrade": {g: K.courses_for(g) for g in K.GRADES},
            "courses": {c: {"name": v["name"], "desc": v["desc"]} for c, v in K.COURSES.items()},
            "workCourse": {g: QUIZ_COURSE.get(g) for g in K.GRADES}, "themeMax": K.THEME_MAX,
            "kindLabels": KIND_LABELS, "kindHowto": KIND_HOWTO, "kindNames": K.KIND_NAMES, "point": K.POINT}


if "jp_lquiz" not in ss:                               # 講座の「やってみよう」（講座ごとに1つ。ちがう問題はたのまれたら作る）
    ss.jp_lquiz = {lid: KL.make_quiz(lid, random.Random()) for lid in learn_data()["lectures"]}
age_grade = K.grade_for_age(ss.get("auth_age"))
js_page.serve(web_games.kokugo_study, "jp", handle,
              cat=catalog(), learn=learn_data(), lquiz=ss.jp_lquiz, learned=sorted(learn_log.learned(SUBJECT)),
              me={"grade": age_grade or K.DEFAULT_GRADE, "maxGrade": max_grade(), "age": ss.get("auth_age")})
