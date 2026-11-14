"""AI英語チャレンジ：年れい・コースをえらぶと、AIが英語の問題を10問つくる。
画面はぜんぶ JavaScript（web/english）。Python は「AIで10問つくる」「1回分の結果を記録して表彰状をつくる」だけ。"""
import json
import random
import time

import streamlit as st
from google.genai import types

import common
import history
import js_page
import pdfgen
import web_games

common.setup_page("AI英語チャレンジ", "🔤")
ss = st.session_state
client = common.get_gemini_client()

TOTAL_Q = 10
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
    "和英": "日本語を見て、正しい英語を選ぼう（日本語 → 英語）",
}
COURSE_ICONS = {"単語": "🔤", "文": "📝", "和英": "🇯🇵"}
COURSE_QUESTIONS = {"単語": "この単語の意味は？", "文": "＿＿ に入ることばは？", "和英": "これを 英語にすると？"}


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
    elif course == "和英":
        form = """- 「和英コース（日本語→英語）」です。1問ごとに日本語を出し、それを表す正しい英語を3〜4択で答えさせます。
- promptには日本語を書きます。年齢が低いときは、ひらがなだけで書きます。レベルが上がるほど、短い文（例：わたしは毎日学校に行きます。）も混ぜてください。
- emojiには、場面や意味を表す絵文字を1〜2個入れます（なければ空文字）。
- readingとtranslationは使わず空文字にします。
- choicesは英語の選択肢（単語・熟語・短い文）。つづりや文法がまぎらわしい誤答を混ぜてください。
- answerは正しい英語で、choicesの中の1つと完全に一致させてください。"""
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
    raise RuntimeError(f"AIが問題を作るときにエラーが起きちゃったみたい。もう一度ためしてね：{last_error}")



def pdf_info(course, level, topic):
    return f"{course}コース ／ {level} ／ テーマ：{topic or 'おまかせ'}"


def handle(v):
    t = v.get("type")
    if t == "gen":
        course, level, topic = v.get("course"), v.get("level"), str(v.get("topic") or "").strip()[:40]
        if course not in COURSES or level not in LEVELS:
            return {"error": "えらび方がおかしいよ"}
        return {"questions": generate_questions(course, level, topic)}
    if t == "log":                              # 10問おわった：記録して、表彰状をつくる
        course, level, topic = v.get("course"), v.get("level"), v.get("topic") or ""
        rows = [(str(r[0]), str(r[1]), str(r[2]), bool(r[3])) for r in v.get("rows") or []][:TOTAL_Q]
        score = sum(1 for r in rows if r[3])
        info = pdf_info(course, level, topic)
        history.log_once("英語", f"en-{v.get('run')}", コース=course, 年齢層=level, テーマ=topic or "おまかせ", 点数=score * 10, 正解数=score,
                         詳細=pdfgen.make_record("AI英語チャレンジ", info, rows))
        pdf = pdfgen.build_pdf("AI英語チャレンジ", info, ss.get("player_name", ""), time.strftime("%Y-%m-%d %H:%M:%S"), score * 10, rows)
        return {"pdf": js_page.pdf_b64(pdf)}
    return {}


levels = list(LEVELS)
js_page.serve(web_games.english_study, "en", handle,
              levels=levels, level=levels[common.age_level_index(len(levels))], age=ss.get("auth_age"),
              courses=[{"id": c, "desc": COURSES[c], "icon": COURSE_ICONS[c], "ask": COURSE_QUESTIONS[c]} for c in COURSES])
