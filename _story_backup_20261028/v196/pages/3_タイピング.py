"""AIタイピングマスター：テーマを入れると、AIがタイピングの問題を10問つくる。5分以内にクリアすると裏メニュー（プログラミング・ミッション／じゆうモード）。
画面はぜんぶ JavaScript（web/typing。ゲームの本体は typing.js・code.js）。
Python は「AIで問題をつくる」「おわったら点数を出して記録し、表彰状をつくる」だけ。"""
import json
import time

import streamlit as st

import auth
import common
import history
import js_page
import pdfgen
import web_games

common.setup_page("AIタイピングマスター", "⌨️")
ss = st.session_state
NORMAL_Q = 10
SECRET_TIME_LIMIT = 300.0  # 5分以内にクリアで裏メニュー解放
# ty_ で始めないキーは「もどる」でリセットされない
UNLOCK_KEY = "typing_unlocked"
ROUND_KEY = "typing_round"  # ゲームごとに増やして、前のゲームの結果をまちがえて拾わないようにする

# スピード点（40点）の目標。1秒に何打鍵できたら満点か（年れいで変える）
LEVEL_TARGET = {
    "小1〜2年（6〜8さい）": 0.3,
    "小3〜4年（8〜10さい）": 0.5,
    "小5〜6年（10〜12さい）": 0.8,
    "中学生": 1.2,
    "高校生": 1.6,
    "大人（社会人・学び直し）": 2.0,
}

RANK_TEXT = {
    "S": "🌈 S ランク：タイピングの達人！",
    "A": "🥇 A ランク：とっても はやい！",
    "B": "🥈 B ランク：いい調子！",
    "C": "🥉 C ランク：その調子で 練習しよう！",
    "D": "🌱 D ランク：ゆっくり 正確に いこう！",
}


def format_time(seconds):
    minutes, secs = int(seconds // 60), round(seconds % 60, 1)
    return f"{minutes}分 {secs}秒" if minutes else f"{secs}秒"


def call_ai(prompt, temperature, retries=3):
    from google.genai import types

    client = common.get_gemini_client()
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=common.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=temperature),
            )
            return json.loads(response.text)
        except Exception as e:
            if attempt == retries - 1:
                raise RuntimeError(f"AIのサーバーが混み合っているみたい。少し時間をあけてもう一度ためしてね！：{e}")
            time.sleep(2)


def generate_typing_issues(theme_word):
    prompt = f"""
    あなたは小学校3年生にタイピングを教えるパソコン教室の優しい先生です。
    ユーザーが指定したテーマ「{theme_word}」に関連する、子供が喜ぶワクワクする言葉や短い文章をタイピングの問題として【10問】作成してください。

    【ルール】
    - 対象は小学3年生なので、問題の日本語はすべて「ひらがな」または「簡単なカタカナ」のみにしてください。漢字は絶対に使わないでください。
    - 各問題に対して、パソコンのキーボードで実際に入力する用のローマ字（半角小文字）を対応させてください。
    - カタカナの長音（ー）は、必ずハイフン「-」で出力してください。（例: クリーパーは "kuri-pa-"）
    - ローマ字の単語と単語の間に、半角スペースや空白を絶対に含めないでください。
    - 短すぎず長すぎず、3〜12文字くらいの問題にしてください。
    - 問題は10問きっちり作成してください。

    必ず以下のJSONフォーマットのみで出力してください。余計な挨拶や説明のテキストは一切含めないでください。

    {{
      "issues": [
        {{"japanese": "もんだい1のひらがな", "romaji": "monndai1"}},
        {{"japanese": "もんだい10のひらがな", "romaji": "monndai10"}}
      ]
    }}
    """
    return call_ai(prompt, 0.3)


def valid_issues(data, count):
    return bool(data) and len(data.get("issues", [])) >= count and all(
        issue.get("japanese") and issue.get("romaji") for issue in data["issues"][:count]
    )


def typing_points(r, level):
    """100点満点 = 正確さ60点（ノーミスの問題は満点、ミスのあった問題は半分）+ スピード40点（年れいの目標に届けば満点）。"""
    total = r["total"] or 1
    accuracy = 60 * (r["perfect"] + 0.5 * r["missedQuestions"]) / total
    speed = 40 * min(1.0, (r["kpm"] / 60) / LEVEL_TARGET[level])
    score = round(accuracy + speed)
    accuracy_pt = round(accuracy)
    return score, accuracy_pt, score - accuracy_pt


def code_points(r):
    """裏メニューは正確さ中心：ノーミスのステージは満点、ミスのあったステージは半分。"""
    stages = r["stages"] or 1
    return round(100 * (r["perfect"] + 0.5 * (stages - r["perfect"])) / stages)


def miss_text(n):
    return "ノーミス" if not n else f"ミス {n}回"



def done_typing(v):
    r, level, mode, theme = v.get("result") or {}, v.get("level"), v.get("mode"), str(v.get("theme") or "")
    if level not in LEVEL_TARGET:
        return {"error": "えらび方がおかしいよ"}
    score, accuracy_pt, speed_pt = typing_points(r, level)
    romaji_of = {i.get("japanese"): i.get("romaji") for i in v.get("issues") or []}
    pdf_rows = [(f"{d['text']}（{romaji_of.get(d['text'], '')}）", miss_text(d["miss"]), "ノーミス", d["miss"] == 0) for d in r.get("details", [])]
    info = f"{mode} ／ {level} ／ テーマ：{theme}　正確さ {accuracy_pt}/60 ＋ スピード {speed_pt}/40 ／ タイム {format_time(r['time'])}"
    history.log_once("タイピング", f"ty-{v.get('run')}", 種類="通常", テーマ=theme, モード=mode, ノーミス正解=r["perfect"], ミスした問題=r["missedQuestions"],
                     タイム秒=r["time"], 点数=score, 年齢層=level, 詳細=pdfgen.make_record("AIタイピングマスター", info, pdf_rows))
    if r["time"] <= SECRET_TIME_LIMIT:
        ss[UNLOCK_KEY] = True
    pdf = pdfgen.build_pdf("AIタイピングマスター", info, ss.get("player_name", ""), time.strftime("%Y-%m-%d %H:%M:%S"), score, pdf_rows)
    return {"score": score, "accuracyPt": accuracy_pt, "speedPt": speed_pt, "rankText": RANK_TEXT.get(r.get("rank"), ""),
            "unlocked": r["time"] <= SECRET_TIME_LIMIT, "pdf": js_page.pdf_b64(pdf)}


def done_code(v):
    r, level = v.get("result") or {}, v.get("level") or ""
    score = code_points(r)
    pdf_rows = [(f"ステージ {i + 1}", miss_text(n), "ノーミス", n == 0) for i, n in enumerate(r.get("stageMisses", []))]
    info = f"プログラミング・ミッション（{r['stages']}ステージ） ／ {level}　ミス {r['misses']}回 ／ タイム {format_time(r['time'])}"
    history.log_once("タイピング", f"tyc-{v.get('run')}", 種類="プログラミング", テーマ=f"ロボット{r['stages']}ステージ", モード="-",
                     ノーミス正解=r["perfect"], ミスした問題=r["stages"] - r["perfect"], タイム秒=r["time"], 点数=score, 年齢層=level,
                     詳細=pdfgen.make_record("プログラミング・ミッション", info, pdf_rows))
    pdf = pdfgen.build_pdf("プログラミング・ミッション", info, ss.get("player_name", ""), time.strftime("%Y-%m-%d %H:%M:%S"), score, pdf_rows)
    return {"score": score, "pdf": js_page.pdf_b64(pdf)}


def handle(v):
    t = v.get("type")
    if t == "gen":
        theme = str(v.get("theme") or "").strip()[:40]
        if not theme:
            return {"error": "言葉を入力してね！"}
        data = generate_typing_issues(theme)
        if not valid_issues(data, NORMAL_Q):
            return {"error": "もんだいの形がうまく作れなかったよ。もう一回ためしてね！"}
        return {"issues": data["issues"][:NORMAL_Q], "theme": theme}
    if t == "typing_done":
        return done_typing(v)
    if t == "code_done":
        return done_code(v)
    return {}


levels = list(LEVEL_TARGET)
# 管理者だけ、URL の末尾に ?ura=1 をつけると、解放しなくても裏メニューに入れる
admin_ura = auth.is_admin() and st.query_params.get("ura") == "1"
js_page.serve(web_games.typing_study, "ty", handle,
              levels=levels, level=levels[common.age_level_index(len(levels))], unlocked=bool(ss.get(UNLOCK_KEY)), adminUra=admin_ura,
              secret=SECRET_TIME_LIMIT)
