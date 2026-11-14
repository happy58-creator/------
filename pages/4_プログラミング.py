"""AIプログラミング教室：言語・年れい・テーマをえらぶと、AI先生がレッスン（たんご・ぶんぽう・かいてみよう・クイズ）をつくる。
画面はぜんぶ JavaScript（web/programming）。Python は「AIでレッスンをつくる」「クイズの結果を記録して表彰状をつくる」だけ。"""
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

common.setup_page("AIプログラミング教室", "💻")
ss = st.session_state
client = common.get_gemini_client()

QUIZ_Q = 5
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
    raise RuntimeError(f"AIがレッスンを作るときにエラーが起きちゃったみたい。もう一度ためしてね：{last_error}")




def handle(v):
    t = v.get("type")
    if t == "gen":
        lang, level, topic = v.get("lang"), v.get("level"), str(v.get("topic") or "")
        if lang not in LANGUAGES or level not in LEVELS:
            return {"error": "えらび方がおかしいよ"}
        if topic not in LANGUAGES[lang][1]:
            topic = LANGUAGES[lang][1][0]               # おまかせ（はじめの一歩）
        return {"lesson": generate_lesson(lang, level, topic), "topic": topic}
    if t == "log":                                      # クイズがおわった：記録して、表彰状をつくる
        lang, level, topic = v.get("lang"), v.get("level"), v.get("topic") or ""
        rows = [(str(r[0]), str(r[1]), str(r[2]), bool(r[3])) for r in v.get("rows") or []][:QUIZ_Q]
        score = sum(1 for r in rows if r[3])
        info = f"言語：{lang} ／ テーマ：{topic} ／ {level}"
        history.log_once("プログラミング", f"pg-{v.get('run')}", 言語=lang, テーマ=topic, 年齢層=level, 点数=score * 20, 正解数=score,
                         詳細=pdfgen.make_record("AIプログラミング教室", info, rows))
        pdf = pdfgen.build_pdf("AIプログラミング教室", info, ss.get("player_name", ""), time.strftime("%Y-%m-%d %H:%M:%S"), score * 20, rows)
        return {"pdf": js_page.pdf_b64(pdf)}
    return {}


levels = list(LEVELS)
js_page.serve(web_games.programming_study, "pg", handle,
              langs=[{"id": k, "desc": v[0], "topics": v[1]} for k, v in LANGUAGES.items()],
              levels=levels, level=levels[common.age_level_index(len(levels))], age=ss.get("auth_age"), quizN=QUIZ_Q)
