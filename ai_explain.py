"""まちがえた問題を、AIがやさしく解説する（どこでまちがえたか・正しい解き方）。1回の呼び出しでまとめて作る。"""
import json

import streamlit as st

import common


def ai_available():
    """AIのカギがあるか（ないときは、AIの解説を出さない。common.get_gemini_client はカギがないと画面を止めるため先に確かめる）"""
    import os
    try:
        if st.secrets.get("GEMINI_API_KEY"):
            return True
    except Exception:
        pass
    return bool(os.environ.get("GEMINI_API_KEY"))


def explain_mistakes(subject, grade_name, items):
    """items: [{"q": 問題, "user": キミの答え, "correct": 正しい答え, "hint": 解き方のヒント}]
    返り値：items と同じ順の解説（文字列）のリスト。うまくいかなければ None。
    """
    if not items:
        return []
    if not ai_available():
        return None
    from google.genai import types

    lines = []
    for i, it in enumerate(items, 1):
        lines.append(f"[{i}] 問題：{it['q']}\n    生徒の答え：{it['user'] or '（未入力）'}\n    正しい答え：{it['correct']}\n    解き方のヒント：{it.get('hint', '')}")
    prompt = f"""あなたは{grade_name}を教える、やさしい{subject}の先生です。
生徒がまちがえた問題について、1問ずつ解説してください。

- まず、生徒の答えのどこがまちがいか（計算ミス・考え方のちがい・書き方の問題など）を、答えから推測して短く指摘する。未入力なら、手がかりの見つけ方を書く。
- 次に、正しい答えの出し方を、番号つきの手順で（2〜4ステップ）。
- {grade_name}にわかる言葉で。数式は $...$ で書いてよい。1問あたり200字くらいまで。
- 正しい答えは上に書いたものが正しい。ちがう答えを書かないこと。

{chr(10).join(lines)}

次のJSONだけを出力：{{"explanations": ["[1]の解説", "[2]の解説", ...]}}（問題と同じ数・同じ順）"""
    try:
        client = common.get_gemini_client()
        response = client.models.generate_content(
            model=common.GEMINI_MODEL, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.3),
        )
        out = json.loads(response.text).get("explanations")
        if isinstance(out, list) and len(out) == len(items):
            return [str(x) for x in out]
    except Exception:
        pass
    return None


def cached_explanations(key, subject, grade_name, items):
    """同じ結果画面で何度も呼ばないよう、セッションにとっておく"""
    store = st.session_state.setdefault("ai_explain_cache", {})
    if key not in store:
        with st.spinner("🤖 AI先生が、まちがえた問題の解説を書いているよ..."):
            store[key] = explain_mistakes(subject, grade_name, items)
    return store[key]
