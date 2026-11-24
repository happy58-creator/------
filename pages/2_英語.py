"""AI英語チャレンジ：年れい・コースをえらぶと、AIが英語の問題を10問つくる。
画面はぜんぶ JavaScript（web/english）。Python は「AIで10問つくる」「1回分の結果を記録して表彰状をつくる」だけ。"""
import json
import random
import time

import streamlit as st
from google.genai import types

import common
import datastore
import history
import js_page
import pdfgen
import web_games

common.setup_page("AI英語チャレンジ", ":material/translate:")
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

# コース → 向き（英→和・和→英）。向きのないコースは "" だけ
COURSES = {
    "単語": {"icon": "word", "dirs": {
        "英→和": ("英単語を見て、日本語の意味を選ぼう（絵文字つき）", "この単語の意味は？"),
        "和→英": ("日本語を見て、正しい英単語を選ぼう", "これを 英語にすると？")}},
    "文": {"icon": "lines", "dirs": {
        "英→和": ("英語の文を読んで、正しい日本語訳を選ぼう", "この文の意味は？"),
        "和→英": ("日本語の文を見て、正しい英語の文を選ぼう", "これを 英語にすると？")}},
    "穴うめ": {"icon": "pen", "dirs": {
        "": ("短い英語の文の ＿＿ に入ることばを選ぼう", "＿＿ に入ることばは？")}},
}


def course_label(course, d):
    return f"{course}（{d}）" if d else course


def build_prompt(course, d, level, topic, kana_only, focus=None):
    guide = LEVELS[level][0]
    topic_line = f"- テーマは「{topic}」に関連づけてください。" if topic else "- テーマはおまかせ（いろいろな分野から出す）。"
    if focus:
        topic_line = ("- この生徒が 前に まちがえた 単語・文です。これらを できるだけ 多く 使って、ちがう形の 問題に してください"
                      "（同じ問題を そのまま 出さない。単語は 意味や 使い方を 変えて、文は 単語を 入れかえて）：\n  " + " ／ ".join(focus[:12]))
    ja_rule = (
        "日本語の説明（reading以外）は、漢字をなるべく使わず ひらがな中心にしてください。"
        if kana_only
        else "日本語の説明は、年齢に合った自然な表現にしてください。"
    )
    if course == "単語" and d == "和→英":
        form = """- 「単語コース（日本語→英語）」です。1問ごとに日本語の単語を1つ出し、それを表す正しい英単語を3〜4択で答えさせます。
- promptには日本語の単語（または短いことば）だけを書きます。年齢が低いときは、ひらがなだけで書きます。
- emojiには、その単語を表す絵文字を1〜2個入れます（抽象語で合う絵文字がなければ空文字）。
- readingには、正解の英単語のカタカナの読みを入れます。
- translationは使わず空文字にします。
- choicesは英単語（または熟語）の選択肢。つづりが似ている語や、意味が近い語など、まぎらわしい誤答を混ぜてください。"""
    elif course == "単語":
        form = """- 「単語コース（英語→日本語）」です。1問ごとに英単語を1つ出し、その日本語の意味を3〜4択で答えさせます。
- promptには英単語（または熟語）だけを書きます。
- emojiには、その単語を表す絵文字を1〜2個入れます（抽象語で合う絵文字がなければ空文字）。
- readingには、カタカナの読みを入れます。
- translationは使わず空文字にします。
- choicesは日本語の意味の選択肢。紛らわしい誤答を混ぜてください。"""
    elif course == "文" and d == "和→英":
        form = """- 「文コース（日本語→英語）」です。1問ごとに日本語の短い文を出し、それを表す正しい英語の文を3〜4択で答えさせます。
- promptには日本語の文を書きます（例：わたしは毎日学校に行きます。）。年齢が低いときは、ひらがなだけで書きます。
- emojiには、場面を表す絵文字を1〜2個入れます（なければ空文字）。
- readingとtranslationは使わず空文字にします。
- choicesは英語の文。語順・時制・三単現の s・前置詞などが少しだけちがう、まぎらわしい誤答を混ぜてください。
- answerは正しい英語の文で、choicesの中の1つと完全に一致させてください。"""
    elif course == "文":
        form = """- 「文コース（英語→日本語）」です。1問ごとに英語の短い文を出し、その正しい日本語訳を3〜4択で答えさせます。
- promptには英語の文を書きます。
- emojiには、場面を表す絵文字を1〜2個入れます（なければ空文字）。
- readingとtranslationは使わず空文字にします。
- choicesは日本語訳。主語・時制・否定・疑問などが少しだけちがう、まぎらわしい誤答を混ぜてください。
- answerは正しい日本語訳で、choicesの中の1つと完全に一致させてください。"""
    else:
        form = """- 「穴うめコース」です。1問ごとに英語の文の一部を ＿＿ にして、入る英語を3〜4択で答えさせます。
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


def generate_questions(course, d, level, topic, focus=None):
    prompt = build_prompt(course, d, level, topic, LEVELS[level][1], focus)
    last_error = None
    for model in (common.GEMINI_MODEL, getattr(common, "GEMINI_FALLBACK_MODEL", common.GEMINI_MODEL)):   # 失敗したら予備のモデルで1回だけ
        try:
            response = client.models.generate_content(
                model=model,
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
            print(f"[英語] {model}: {type(e).__name__}: {e}", flush=True)     # Manage app のログで原因がわかるように
    if isinstance(last_error, ValueError):
        raise RuntimeError("AIが うまく10問を作れなかったよ。もう一度ためしてね")
    raise RuntimeError(common.ai_error_text(last_error) if hasattr(common, "ai_error_text") else f"AIでエラーが起きちゃった：{last_error}")


# ---------------------------------------------------------------- 問題の保存（使い回し）と 苦手
POOL_TAB, POOL_COLS = "問題プール", ["キー", "日時", "問題"]
POOL_MIN = 30          # 保存した問題が これだけ たまったら、まだ見ていない問題から 出す（AIの回数を 使わない）


def pool_key(course, d, level, topic):
    return f"英語|{course}|{d}|{level}|{topic}"


def pool_of(key):
    out = []
    for r in datastore.read(POOL_TAB, POOL_COLS):
        if r.get("キー") == key:
            try:
                q = json.loads(r.get("問題") or "")
                if valid_question(q):
                    out.append(q)
            except ValueError:
                pass
    return list({q["prompt"]: q for q in out}.values())


def pool_add(key, qs):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    datastore.append(POOL_TAB, POOL_COLS, [{"キー": key, "日時": now, "問題": json.dumps(q, ensure_ascii=False)} for q in qs])


def my_rows(course_lbl, level, days=None):
    """その人の この コース・年齢層の 記録の 1問ずつ：[(日時, 問題文, 自分の答え, 正しい答え, 正解か)]（古い順）"""
    out = []
    for r in reversed(datastore.my_history("英語", days=days)):
        if r.get("コース") != course_lbl or r.get("年齢層") != level:
            continue
        try:
            rec = json.loads(r.get("詳細") or "{}")
        except ValueError:
            continue
        for x in rec.get("r") or []:
            if len(x) >= 4:
                out.append((str(r.get("日時")), str(x[0]).split("\n")[0], str(x[1]), str(x[2]), bool(x[3])))
    return out


def weak_list(course_lbl, level):
    """苦手：さいごに 答えたとき まちがえていた 問題（新しい順）。[(問題文, 自分の答え, 正しい答え)]"""
    last = {}
    for when, q, a, c, ok in my_rows(course_lbl, level):
        last[q] = (ok, a, c, when)
    return [(q, a, c) for q, (ok, a, c, when) in sorted(last.items(), key=lambda kv: kv[1][3], reverse=True) if not ok]


def weak_questions(course, d, level):
    """苦手だけで 問題を つくる。保存した問題が あれば それを、なければ 記録から（正しい答え＋自分の答え＋ほかの答え）"""
    lbl = course_label(course, d)
    weak = weak_list(lbl, level)[:TOTAL_Q]
    if not weak:
        return []
    pool = {q["prompt"]: q for q in pool_of(pool_key(course, d, level, ""))}
    for r in datastore.read(POOL_TAB, POOL_COLS):           # テーマつきで 作った問題も さがす
        if r.get("キー", "").startswith(f"英語|{course}|{d}|{level}|"):
            try:
                q = json.loads(r.get("問題") or "")
                pool.setdefault(q.get("prompt"), q)
            except ValueError:
                pass
    others = list({c for _, _, c in weak_list(lbl, level)} | {c for *_, c, ok in my_rows(lbl, level) if ok})
    out = []
    for prompt, mine, right in weak:
        q = pool.get(prompt)
        if q and valid_question(q):
            q = dict(q)
        else:
            ch = [right] + ([mine] if mine and mine != right else [])
            ch += random.sample([o for o in others if o not in ch], min(max(0, 3 - len(ch)), len([o for o in others if o not in ch])))
            if len(ch) < 2:
                continue
            q = {"prompt": prompt, "choices": ch, "answer": right, "emoji": "", "reading": "", "translation": "",
                 "hint": "前に まちがえた 問題だよ。よく 思い出してね", "explanation": f"正しい答えは「{right}」"}
        random.shuffle(q["choices"])
        out.append(q)
    return out


def weak_counts():
    """メニューに出す：年齢層・コースごとの 苦手の数 {"年齢層|単語|英→和": 3, ...}（記録は 1回だけ 読む。少しのあいだ 覚えておく）"""
    hit = ss.get("en_weak")
    if hit and time.time() - hit[0] < 120:
        return hit[1]
    last = {}
    for r in reversed(datastore.my_history("英語")):
        try:
            rec = json.loads(r.get("詳細") or "{}")
        except ValueError:
            continue
        for x in rec.get("r") or []:
            if len(x) >= 4:
                last[(r.get("年齢層"), r.get("コース"), str(x[0]).split("\n")[0])] = bool(x[3])
    out = {}
    for c, v in COURSES.items():
        for d in v["dirs"]:
            lbl = course_label(c, d)
            for lv in LEVELS:
                n = sum(1 for (l2, c2, _), ok in last.items() if l2 == lv and c2 == lbl and not ok)
                if n:
                    out[f"{lv}|{c}|{d}"] = n
    ss["en_weak"] = (time.time(), out)
    return out


def get_questions(course, d, level, topic, kind):
    """kind："new"（保存した問題 か AI）・"weak"（苦手だけ）・"weakai"（苦手を使って AI が 新しく）。(問題, どこから)"""
    if kind == "weak":
        qs = weak_questions(course, d, level)
        if not qs:
            raise RuntimeError("このコースの 苦手は まだ ないよ。ふつうの問題で 練習しよう")
        return qs, "weak"
    key = pool_key(course, d, level, topic)
    if kind == "weakai":
        focus = [f"{q}（{c}）" for q, _, c in weak_list(course_label(course, d), level)]
        if not focus:
            raise RuntimeError("このコースの 苦手は まだ ないよ。ふつうの問題で 練習しよう")
        qs = generate_questions(course, d, level, topic, focus)
        pool_add(key, qs)
        return qs, "weakai"
    pool = pool_of(key)
    seen = {q for _, q, *_ in my_rows(course_label(course, d), level, days=7)}
    fresh = [q for q in pool if q["prompt"] not in seen]
    if len(pool) >= POOL_MIN and len(fresh) >= TOTAL_Q:
        qs = [dict(q) for q in random.sample(fresh, TOTAL_Q)]
        for q in qs:
            random.shuffle(q["choices"])
        return qs, "pool"
    try:
        qs = generate_questions(course, d, level, topic)
    except RuntimeError:
        if len(pool) >= TOTAL_Q:                                # AI が 使えない：保存した問題で 続ける
            qs = [dict(q) for q in random.sample(fresh if len(fresh) >= TOTAL_Q else pool, TOTAL_Q)]
            return qs, "pool_noai"
        raise
    pool_add(key, qs)
    return qs, "ai"


def pdf_info(course, level, topic):
    return f"{course}コース ／ {level} ／ テーマ：{topic or 'おまかせ'}"


def handle(v):
    t = v.get("type")
    if t == "gen":
        course, d, level, topic = v.get("course"), v.get("dir") or "", v.get("level"), str(v.get("topic") or "").strip()[:40]
        if course not in COURSES or d not in COURSES[course]["dirs"] or level not in LEVELS:
            return {"error": "えらび方がおかしいよ"}
        qs, src = get_questions(course, d, level, topic, v.get("kind") or "new")
        ss.pop("en_weak", None)
        return {"questions": qs, "source": src}
    if t == "log":                              # 10問おわった：記録して、表彰状をつくる
        course = course_label(str(v.get("course") or ""), str(v.get("dir") or ""))
        level, topic = v.get("level"), v.get("topic") or ""
        rows = [(str(r[0]), str(r[1]), str(r[2]), bool(r[3])) for r in v.get("rows") or []][:TOTAL_Q]
        score = sum(1 for r in rows if r[3])
        info = pdf_info(course, level, topic)
        ss.pop("en_weak", None)
        history.log_once("英語", f"en-{v.get('run')}", コース=course, 年齢層=level, テーマ=topic or "おまかせ", 点数=score * 10, 正解数=score,
                         詳細=pdfgen.make_record("AI英語チャレンジ", info, rows))
        pdf = pdfgen.build_pdf("AI英語チャレンジ", info, ss.get("player_name", ""), time.strftime("%Y-%m-%d %H:%M:%S"), score * 10, rows)
        return {"pdf": js_page.pdf_b64(pdf)}
    return {}


levels = list(LEVELS)
js_page.serve(web_games.english_study, "en", handle,
              levels=levels, level=levels[common.age_level_index(len(levels))], age=ss.get("auth_age"),
              weak=weak_counts(),
              courses=[{"id": c, "icon": v["icon"], "dirs": [{"id": d, "desc": x[0], "ask": x[1]} for d, x in v["dirs"].items()]} for c, v in COURSES.items()])
