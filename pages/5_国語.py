import json

import streamlit as st
from google.genai import types

import common

common.setup_page("AI国語アドベンチャー", "🧙‍♂️")
common.hero("🧙‍♂️ AI国語わくわくアドベンチャー 🌟", "入力したテーマに合わせて、AIがその場で『世界にひとつだけの国語教材』を作ります！")

client = common.get_gemini_client()

DEFAULTS = {
    "jp_state": "menu",  # menu, playing, ending
    "jp_step": 1,
    "jp_score": 0,
    "jp_quiz": None,
    "jp_theme": "",
    "jp_choice": None,  # 今のステージで「決定」した選択肢
    "jp_log": [],  # 各ステージの結果 (正解したか)
}
common.init_state(DEFAULTS)

# (章タイトル, 問題の種類, 問題文を固定で出すか(None なら q{n}_text を使う))
STAGES = [
    ("🌲 第一章：冒険のはじまり", "もんだい1（漢字のよみ）", None),
    ("⛈️ 第二章：突然のハプニング", "もんだい2（漢字の書き取り）", None),
    ("🥕 第三章：こっそり隠したおやつ", "もんだい3（登場人物のきもち）", "主人公の『ちょっとずるい気持ち』を読み解こう。"),
    ("🐺 第四章：大ピンチのあとに", "もんだい4（おはなしの読解）", "主人公がとった『予想外のピンチの切り抜け方』の理由はどれかな？"),
    ("💎 最終章：ほんとうの宝物", "もんだい5（こころの変化）", "大冒険のさいご、主人公の心はどう変化したかな？"),
]
STORY_KEYS = {1: "intro", 2: "q1_story", 3: "q2_story", 4: "q3_story", 5: "q4_story"}
REQUIRED_KEYS = ["intro", "q1_text", "q2_text"] + [
    f"q{n}_{suffix}" for n in range(1, 6) for suffix in ("opts", "ans", "ok", "ng")
] + [f"q{n}_story" for n in range(1, 5)]


def generate_quiz_with_ai(theme_word):
    prompt = f"""
    あなたは小学校3年生の優しい国語の先生です。
    ユーザーが指定したテーマ「{theme_word}」に基づいた、ワクワクする冒険ストーリーと、国語のクイズをひらがなベースで5問作成してください。

    【ルール】
    - 出題する漢字や文章の難易度は、小学3年生のレベルに合わせてください。
    - クイズは合計5問で、以下の構成にしてください。
      - 第1問: ストーリーの導入 + 漢字の「読み」の3択問題
      - 第2問: ストーリーの展開 + 漢字の「書き（同音異義語など間違いやすいもの）」の3択問題
      - 第3問: ストーリーの展開 + 登場人物の「ずるい気持ち」や「マイナスな感情」を読み解く読解3択問題
      - 第4問: ストーリーの大ピンチ + 「予想外のユニークな行動やセリフ」の理由を答えさせる読解3択問題
      - 第5問: ストーリーの結末 + 主人公の「心の成長や変化」を答えさせる読解3択問題

    必ず以下のJSONフォーマットのみで出力してください。余計な挨拶や説明のテキストは一切含めないでください。

    {{
      "intro": "ストーリーの始まりと世界観の説明（150文字程度）",
      "q1_text": "第1問の問題文（例: カッコの漢字の読み方は？「未知の惑星を(探検)する。」）",
      "q1_opts": ["選択肢1", "選択肢2", "選択肢3"],
      "q1_ans": "正しい選択肢の文字列（optsの中のどれかと完全一致させること）",
      "q1_ok": "正解した時の褒め言葉や解説",
      "q1_ng": "不正解の時の優しい解説",

      "q1_story": "第1問の後のストーリー展開（150文字程度）",
      "q2_text": "第2問の問題文（漢字の書き取り）",
      "q2_opts": ["選択肢1", "選択肢2", "選択肢3"],
      "q2_ans": "正しい選択肢の文字列",
      "q2_ok": "正解時の解説",
      "q2_ng": "不正解時の解説",

      "q2_story": "第2問の後のストーリー展開（おやつを隠すなどの展開）",
      "q3_opts": ["読解選択肢1", "読解選択肢2", "読解選択肢3"],
      "q3_ans": "正しい読解選択肢の文字列",
      "q3_ok": "正解時の解説",
      "q3_ng": "不正解時の解説",

      "q3_story": "第3問の後のストーリー展開（大ピンチ到来）",
      "q4_opts": ["ユニークな行動の理由の選択肢1", "選択肢2", "選択肢3"],
      "q4_ans": "正しい選択肢の文字列",
      "q4_ok": "正解時の解説",
      "q4_ng": "不正解時の解説",

      "q4_story": "第4問の後のストーリー展開（結末へ）",
      "q5_opts": ["心の成長に関する選択肢1", "選択肢2", "選択肢3"],
      "q5_ans": "正しい選択肢の文字列",
      "q5_ok": "正解時の解説",
      "q5_ng": "不正解時の解説"
    }}
    """
    last_error = None
    for _ in range(2):  # 形式が崩れたときは1回だけやり直す
        try:
            response = client.models.generate_content(
                model=common.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7),
            )
            data = json.loads(response.text)
            missing = [k for k in REQUIRED_KEYS if k not in data]
            if missing:
                raise ValueError(f"足りない項目: {', '.join(missing)}")
            for n in range(1, 6):
                if data[f"q{n}_ans"] not in data[f"q{n}_opts"]:
                    raise ValueError(f"第{n}問の正解が選択肢にありません")
            return data
        except Exception as e:
            last_error = e
    st.error(f"AIが問題を作るときにエラーが起きちゃったみたい。もう一度ためしてね：{last_error}")
    return None


def submit_choice(choice):
    st.session_state.jp_choice = choice


def go_next(is_correct):
    st.session_state.jp_log.append(is_correct)
    if is_correct:
        st.session_state.jp_score += 20
    st.session_state.jp_choice = None
    st.session_state.jp_step += 1
    if st.session_state.jp_step > 5:
        st.session_state.jp_state = "ending"


# --- メニュー ---
if st.session_state.jp_state == "menu":
    with st.container(border=True):
        st.subheader("✍️ どんなお話で遊びたい？テーマを教えてね！")
        st.caption("（例：恐竜、マインクラフト、魔法学校、宇宙飛行士、ねこ、など何でもOK！）")
        with st.form("jp_theme_form"):
            theme_input = st.text_input("すきな言葉（キーワード）：", placeholder="ここに文字を入力してね")
            submitted = st.form_submit_button("🚀 このテーマでAIに問題を作ってもらう！", type="primary", use_container_width=True)

    if submitted:
        if not theme_input.strip():
            st.warning("⚠️ 言葉を入力してね！")
        else:
            with st.spinner("🧙‍♂️ AI先生が、キミのために特別なお話とクイズを作成中だよ...（10秒くらい待ってね）"):
                quiz = generate_quiz_with_ai(theme_input.strip())
            if quiz:
                common.reset_state("jp_", DEFAULTS)
                st.session_state.jp_quiz = quiz
                st.session_state.jp_theme = theme_input.strip()
                st.session_state.jp_state = "playing"
                st.rerun()

# --- プレイ ---
elif st.session_state.jp_state == "playing":
    data = st.session_state.jp_quiz
    step = st.session_state.jp_step
    chapter, kind, fixed_text = STAGES[step - 1]

    st.caption(f"テーマ：{st.session_state.jp_theme}　／　いまの点数：{st.session_state.jp_score}点")
    st.progress((step - 1) / 5, text=f"ステージ {step} / 5")
    st.header(chapter)
    st.info(data[STORY_KEYS[step]])
    st.subheader(f"❓ {kind}")
    st.markdown(fixed_text or data[f"q{step}_text"])

    opts = data[f"q{step}_opts"]
    chosen = st.session_state.jp_choice
    if chosen is None:
        ans = st.radio("どれかな？", opts, index=None, key=f"jp_radio_{step}")
        st.button("これで決定！", disabled=ans is None, on_click=submit_choice, args=(ans,), type="primary")
    else:
        is_correct = chosen == data[f"q{step}_ans"]
        st.radio("どれかな？", opts, index=opts.index(chosen), key=f"jp_radio_{step}", disabled=True)
        if is_correct:
            st.success("⭕ せいかい！ " + data[f"q{step}_ok"])
        else:
            st.error(f"❌ ざんねん… 正しい答えは「{data[f'q{step}_ans']}」だよ。\n\n" + data[f"q{step}_ng"])
        label = "結果発表へ！ 🏆" if step == 5 else "次のステージへ進む ➡️"
        st.button(label, on_click=go_next, args=(is_correct,), type="primary", use_container_width=True)

# --- 結果 ---
elif st.session_state.jp_state == "ending":
    score = st.session_state.jp_score
    st.header("🏆 大冒険お疲れさまでした！ 🏆")
    st.subheader(f"キミの点数は... 【 {score}点 / 100点 】 🎯")
    st.write("".join("⭕" if ok else "❌" for ok in st.session_state.jp_log))

    if score == 100:
        st.balloons()
        st.success("🥇 【ランク：国語マスター神】")
        st.write("すごすぎる！全問大正解！AI先生が作った難しい漢字も読解も完璧（かんぺき）にクリアしたね！")
    elif score >= 60:
        st.warning("🥈 【ランク：一流の冒険家】")
        st.write("素晴らしい！お話の気持ちの変化をしっかり読み解くことができたね。次はちがうテーマで満点を目指そう！")
    else:
        st.info("🏃 【ランク：みならい冒険家】")
        st.write("お疲れさま！AI先生のお話は楽しかったかな？次はキミの大好きな別のテーマを入力してリベンジだ！")

    st.divider()
    col_same, col_new = st.columns(2)
    with col_same:
        if st.button("🔁 同じお話をもう一度", use_container_width=True):
            quiz, theme = st.session_state.jp_quiz, st.session_state.jp_theme
            common.reset_state("jp_", DEFAULTS)
            st.session_state.jp_quiz, st.session_state.jp_theme = quiz, theme
            st.session_state.jp_state = "playing"
            st.rerun()
    with col_new:
        if st.button("🔄 別のテーマで新しく遊ぶ", type="primary", use_container_width=True):
            common.reset_state("jp_", DEFAULTS)
            st.rerun()
