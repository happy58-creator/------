"""AI英語スピーキング：「聞いて答える」と「見て話す」。
画面はぜんぶ JavaScript（web/speaking）。読み上げ・音声認識・録音はブラウザの機能を使う。
Python は「AIで10問つくる」「おわったら記録して表彰状をつくる（話すモードは、録音をまとめてAIに送って1問ずつ点数と発音アドバイス）」だけ。"""
import base64
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

common.setup_page("AI英語スピーキング", "🎤")
ss = st.session_state
client = common.get_gemini_client()

TOTAL_Q = 10
SUBJECT = "AI英語スピーキング"
# 年齢層 -> (AIへの指示, 日本語を ひらがな中心にするか)（AI英語と同じ）
LEVELS = {
    "小1〜2年（6〜8さい）": ("英語に初めて触れる子ども向け。色・動物・食べ物・数・家族など、身近で超基本の単語だけ。文は I like ~. / This is ~. 程度の3語前後。", True),
    "小3〜4年（8〜10さい）": ("小学校中学年向け。英検5級レベル。身の回り・学校・曜日・天気などの基本単語。文は主語＋動詞の短い現在形・be動詞・can。", True),
    "小5〜6年（10〜12さい）": ("小学校高学年向け。英検5〜4級レベル。教科・スポーツ・場所・道案内などの単語。文は過去形・現在進行形・疑問文の基本。", False),
    "中学生": ("中学生向け。英検3級レベル。単語は中学で習う標準語彙。文は不定詞・動名詞・比較・受け身・現在完了の基本。", False),
    "高校生": ("高校生向け。英検準2級〜2級レベル。抽象的な語彙や熟語・句動詞。文は関係代名詞・仮定法・分詞構文の基本。", False),
    "大人（社会人・学び直し）": ("大人向け。日常会話と職場で使う実用英語（TOEIC 600点前後）。メール・会議・旅行・買い物でよく使う語彙や表現。", False),
}
MODES = {"聞く": "聞いて答える", "話す": "見て話す"}
# モード -> コース -> (説明, 問いかけ)
COURSES = {
    "聞く": {
        "単語": ("英単語を聞いて、日本語の意味を選ぼう", "いま聞こえた単語の意味は？"),
        "文": ("英語の文を聞いて、正しい日本語訳を選ぼう", "いま聞こえた文の意味は？"),
        "しつもん": ("英語の しつもんを聞いて、正しい答えを選ぼう", "しつもんへの 答えは どれ？"),
    },
    "話す": {
        "単語": ("英単語を見て、声に出して言ってみよう", "声に出して 言ってみよう"),
        "文": ("英語の文を見て、声に出して読んでみよう", "声に出して 読んでみよう"),
    },
}


def build_prompt(mode, course, level, topic):
    guide, kana = LEVELS[level]
    topic_line = f"- テーマは「{topic}」に関連づけてください。" if topic else "- テーマはおまかせ（いろいろな分野から出す）。"
    ja_rule = "日本語（ja・choices・hint・tip・explanation）は、漢字をなるべく使わず ひらがな中心にしてください。" if kana else "日本語は、年齢に合った自然な表現にしてください。"
    common_rule = """- en は読み上げ（音声合成）と音声認識に使います。記号・絵文字・かっこ・カタカナを入れず、ふつうの英語のつづりだけで書いてください。
- reading には en のカタカナの読みを入れます。
- ja には en の日本語訳を入れます。"""
    if mode == "聞く" and course == "しつもん":
        form = """- 「しつもんコース」です。en は英語のかんたんな しつもん（例：What color is the sky?）。それを聞いて、正しい答えを3〜4択で選ばせます。
- choices は英語の答え（短い文や語）。answer は正しい答えで、choices の1つと完全に一致させます。
- ja には しつもんの日本語訳を入れます。"""
    elif mode == "聞く":
        what = "英単語（または熟語）" if course == "単語" else "短い英語の文"
        form = f"""- 「聞いて答える・{course}コース」です。en は {what}。それを聞いて、正しい日本語の意味を3〜4択で選ばせます。
- choices は日本語の選択肢。聞きまちがえやすい音の似た語の意味や、少しだけちがう訳など、まぎらわしい誤答を混ぜてください。
- answer は正しい日本語で、choices の1つと完全に一致させます。"""
    else:
        what = "英単語（または熟語）" if course == "単語" else "声に出して読むのにちょうどよい長さの英語の文"
        form = f"""- 「見て話す・{course}コース」です。en は {what}。画面に出して、声に出して言わせます。
- 日本人がまちがえやすい音（L と R、TH、V と B、語末の子音、アクセントなど）がほどよく入るようにしてください。
- choices と answer は使わず、空の配列・空文字にします。"""
    return f"""
あなたは経験豊富な英語の先生です。次の条件で、英語のリスニング・スピーキング練習の問題を【{TOTAL_Q}問】作成してください。

【対象】{level}
【レベルの目安】{guide}
{topic_line}
{ja_rule}
{common_rule}
{form}
- hint には、答えそのものを言わずに助けになるヒントを日本語で書いてください。
- tip には、en を発音するときのコツを日本語で1文（例：th は 舌を前歯に軽く当てて）。
- explanation には、答えや意味の説明を日本語で1〜2文。
- 同じ単語や文を重複させないでください。

必ず次のJSONのみで出力してください。

{{"questions": [{{"en": "...", "reading": "...", "ja": "...", "choices": ["..."], "answer": "...", "hint": "...", "tip": "...", "explanation": "..."}}]}}
"""


def valid(q, mode):
    if not (isinstance(q, dict) and str(q.get("en") or "").strip()):
        return False
    if mode == "話す":
        return True
    ch = q.get("choices")
    return isinstance(ch, list) and 2 <= len(ch) <= 5 and q.get("answer") in ch


def ai_call(contents, temperature):
    """AIに1回たのむ（失敗したら予備のモデルで1回だけ）→ JSON"""
    last = None
    for model in (common.GEMINI_MODEL, getattr(common, "GEMINI_FALLBACK_MODEL", common.GEMINI_MODEL)):
        try:
            res = client.models.generate_content(
                model=model, contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=temperature),
            )
            return json.loads(res.text)
        except Exception as e:
            last = e
            print(f"[スピーキング] {model}: {type(e).__name__}: {e}", flush=True)
    if isinstance(last, (ValueError, KeyError)):
        raise RuntimeError("AIの返事を うまく読めなかったよ。もう一度ためしてね")
    raise RuntimeError(common.ai_error_text(last) if hasattr(common, "ai_error_text") else f"AIでエラーが起きちゃった：{last}")


def generate(mode, course, level, topic):
    data = ai_call(build_prompt(mode, course, level, topic), 0.6)
    items = [q for q in (data.get("questions") or []) if valid(q, mode)][:TOTAL_Q]
    if len(items) < min(TOTAL_Q, 8):
        raise RuntimeError("AIが うまく問題を作れなかったよ。もう一度ためしてね")
    for q in items:
        q["en"] = str(q["en"]).strip()
        if mode == "聞く":
            random.shuffle(q["choices"])
    return items


def review_prompt(level, items):
    lines = "\n".join(
        f"{k + 1}. お手本：「{it['en']}」／ ブラウザの音声認識の結果：「{it.get('said') or '（なし）'}」" + ("" if it.get("audio") else "（録音なし）")
        for k, it in enumerate(items))
    return f"""あなたは やさしくて正確な英語の発音の先生です。生徒（{level}）が、次の英語を1つずつ声に出して読みました。
音声はこのあと、番号の順に並んでいます（録音なしの番号は、音声がありません）。

{lines}

1問ずつ、実際の音声をよく聞いて採点してください。
- score：0〜100の整数。お手本どおりに言えているか（言いもらし・言いまちがい）と、発音（音・アクセント・なめらかさ）で決めます。年齢に合わせて、がんばりを認めつつ正直に。録音がない・何も聞こえないときは 0。
- heard：あなたに聞こえた英語。
- comment：日本語で1〜2文。よかった所と、直すとよい音を具体的に（例：「three」の th が s になっているよ。舌を前歯に軽く当ててみよう）。
- advice：全体を通した アドバイスを日本語で2〜3文（いちばん大事な練習ポイント）。
{"日本語は ひらがな中心にしてください。" if LEVELS.get(level, ("", False))[1] else ""}

必ず次のJSONのみで出力してください（items は {len(items)} 個、番号の順）。
{{"items": [{{"score": 80, "heard": "...", "comment": "..."}}], "advice": "..."}}
"""


def review(level, items):
    if not any(it.get("audio") for it in items):        # 1問も話していない：AIに送らない（回数がもったいない）
        return [{"score": 0, "heard": "", "comment": ""} for _ in items], ""
    parts = [review_prompt(level, items)]
    for k, it in enumerate(items):
        if it.get("audio"):
            parts.append(f"{k + 1}番の音声：")
            parts.append(types.Part.from_bytes(data=base64.b64decode(it["audio"]), mime_type="audio/wav"))
    data = ai_call(parts, 0.2)
    got = data.get("items") or []
    out = []
    for k in range(len(items)):
        g = got[k] if k < len(got) and isinstance(got[k], dict) else {}
        try:
            sc = max(0, min(100, int(round(float(g.get("score", 0))))))
        except (TypeError, ValueError):
            sc = 0
        if not items[k].get("audio"):           # 話していない問題は 0点
            out.append({"score": 0, "heard": "", "comment": "この問題は 話していないよ。つぎは チャレンジしてみよう！"})
            continue
        out.append({"score": sc, "heard": str(g.get("heard") or ""), "comment": str(g.get("comment") or "")})
    return out, str(data.get("advice") or "")


def info_text(mode, course, level, topic):
    return f"{MODES[mode]}・{course}コース ／ {level} ／ テーマ：{topic or 'おまかせ'}"


def handle(v):
    t = v.get("type")
    mode, course, level = v.get("mode"), v.get("course"), v.get("level")
    topic = str(v.get("topic") or "").strip()[:40]
    if mode not in COURSES or course not in COURSES[mode] or level not in LEVELS:
        return {"error": "えらび方がおかしいよ"}
    if t == "gen":
        return {"questions": generate(mode, course, level, topic)}
    if t == "done":                             # おわった：（話すなら AI採点）→ 記録して、表彰状をつくる
        info = info_text(mode, course, level, topic)
        out = {}
        if mode == "聞く":
            rows = [(str(r[0]), str(r[1]), str(r[2]), bool(r[3])) for r in v.get("rows") or []][:TOTAL_Q]
            right = sum(1 for r in rows if r[3])
            score = round(right * 100 / max(1, len(rows)))
            comment = None
        else:
            items = [{"en": str(x.get("en") or "")[:200], "said": str(x.get("said") or "")[:300], "audio": x.get("audio") or "",
                      "local": int(x.get("local") or 0)} for x in (v.get("items") or [])][:TOTAL_Q]
            try:
                scores, advice = review(level, items)
                out = {"scores": scores, "advice": advice}
            except RuntimeError as e:          # AIがだめでも、ブラウザの判定で記録はする
                scores, advice = [{"score": it["local"], "heard": it["said"], "comment": ""} for it in items], ""
                out = {"aiError": str(e)}
            rows = [(it["en"], s["heard"] or it["said"] or "（聞きとれず）", f"{s['score']}点", s["score"] >= 60) for it, s in zip(items, scores)]
            right = sum(1 for r in rows if r[3])
            score = round(sum(s["score"] for s in scores) / max(1, len(scores)))
            comment = advice or None
        history.log_once("スピーキング", f"sp-{v.get('run')}", モード=MODES[mode], コース=course, 年齢層=level, テーマ=topic or "おまかせ",
                         点数=score, 正解数=right, 詳細=pdfgen.make_record(SUBJECT, info, rows))
        pdf = pdfgen.build_pdf(SUBJECT, info, ss.get("player_name", ""), time.strftime("%Y-%m-%d %H:%M:%S"), score, rows, comment=comment)
        return {**out, "score": score, "pdf": js_page.pdf_b64(pdf)}
    return {}


levels = list(LEVELS)
js_page.serve(web_games.speaking_study, "sp", handle,
              levels=levels, level=levels[common.age_level_index(len(levels))], age=ss.get("auth_age"),
              modes=[{"id": m, "desc": d, "courses": [{"id": c, "desc": x[0], "ask": x[1]} for c, x in COURSES[m].items()]} for m, d in MODES.items()])
