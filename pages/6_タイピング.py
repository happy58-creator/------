import json
import time

import streamlit as st

import common
import history
import pdfgen
import web_games

common.setup_page("AIタイピングマスター", "⌨️")
common.hero("⌨️ AIワクワクたいぴんぐアドベンチャー 🌟", "入力したテーマに合わせて、AIがキミ専用のタイピングもんだいを作ってくれるよ！")

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

DEFAULTS = {
    "ty_level": "小3〜4年（8〜10さい）",
    "ty_state": "menu",  # menu, playing, ending, code_playing, code_ending, sandbox
    "ty_data": None,
    "ty_mode": "みながらモード",
    "ty_theme": "",
    "ty_result": None,
}
common.init_state(DEFAULTS)
st.session_state.setdefault(ROUND_KEY, 0)
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
                st.error(f"AIのサーバーが混み合っているみたい。少し時間をあけてもう一度ためしてね！：{e}")
                return None
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


def pdf_button(r):
    st.download_button(
        "📥 けっかをPDFで保存する（印刷もできるよ！）",
        data=pdfgen.build_pdf(
            r["subject"], r["pdf_info"], st.session_state.get("player_name", ""),
            r["played_at"], r["score"], r["pdf_rows"],
        ),
        file_name="タイピングけっか.pdf", mime="application/pdf", type="primary", use_container_width=True,
    )


def start(state):
    st.session_state[ROUND_KEY] += 1
    st.session_state.ty_result = None
    st.session_state.ty_state = state
    st.rerun()


def back_to_menu():
    common.reset_state("ty_", DEFAULTS)
    st.rerun()


state = st.session_state.ty_state

# --- メニュー ---
if state == "menu":
    with st.container(border=True):
        st.subheader("🛠️ モードをえらんでね")
        mode_choice = st.radio(
            "タイピングのモード設定：",
            ["みながらモード（ローマ字がみえるよ）", "あんもくモード（ひらがなだけで挑戦！）"],
            horizontal=True,
        )
        st.session_state.ty_mode = "みながらモード" if "みながら" in mode_choice else "あんもくモード"
        levels = list(LEVEL_TARGET)
        st.session_state.ty_level = st.selectbox(
            "年れい（点数の「スピード」の目標に使うよ）", levels, index=common.age_level_index(len(levels)),
        )

    with st.container(border=True):
        st.subheader("✍️ どんなテーマでもんだいを作る？")
        with st.form("ty_theme_form"):
            theme_input = st.text_input("すきな言葉（キーワード）：", placeholder="ここに文字を入力してね")
            go = st.form_submit_button("🚀 AIにもんだいを作ってもらってスタート！", type="primary", use_container_width=True)

    st.caption("コツ：「si / shi」「ti / chi」「tu / tsu」など、どの打ち方でも正解になるよ！ 1文字ずつ その場で判定するよ。")
    if go:
        if not theme_input.strip():
            st.warning("⚠️ 言葉を入力してね！")
        else:
            with st.spinner("🧙‍♂️ AI先生が、キミのために10問のタイピングもんだいを作成中だよ..."):
                data = generate_typing_issues(theme_input.strip())
            if valid_issues(data, NORMAL_Q):
                st.session_state.ty_data = data["issues"][:NORMAL_Q]
                st.session_state.ty_theme = theme_input.strip()
                start("playing")
            elif data:
                st.error("もんだいの形がうまく作れなかったよ。もう一回ためしてね！")

    if st.session_state.get(UNLOCK_KEY):
        with st.container(border=True):
            st.subheader("🔓 ひらいた 裏メニュー")
            c1, c2 = st.columns(2)
            if c1.button("🤖 プログラミング・ミッション", use_container_width=True):
                start("code_playing")
            if c2.button("🎨 じゆうに プログラミング", use_container_width=True):
                start("sandbox")

# --- タイピング（JavaScript の画面） ---
elif state == "playing":
    result = web_games.typing_game(
        "typing", key=f"ty_game_{st.session_state[ROUND_KEY]}",
        issues=st.session_state.ty_data, mode=st.session_state.ty_mode, round=st.session_state[ROUND_KEY],
    )
    if result and result.get("type") == "typing_done" and result.get("round") == st.session_state[ROUND_KEY]:
        score, accuracy_pt, speed_pt = typing_points(result, st.session_state.ty_level)
        romaji_of = {i["japanese"]: i["romaji"] for i in st.session_state.ty_data}
        pdf_rows = [
            (f"{d['text']}（{romaji_of.get(d['text'], '')}）", miss_text(d["miss"]), "ノーミス", d["miss"] == 0)
            for d in result.get("details", [])
        ]
        pdf_info = (
            f"{st.session_state.ty_mode} ／ {st.session_state.ty_level} ／ テーマ：{st.session_state.ty_theme}　"
            f"正確さ {accuracy_pt}/60 ＋ スピード {speed_pt}/40 ／ タイム {format_time(result['time'])}"
        )
        result.update(
            score=score, accuracy_pt=accuracy_pt, speed_pt=speed_pt, pdf_rows=pdf_rows, pdf_info=pdf_info,
            played_at=time.strftime("%Y-%m-%d %H:%M:%S"), subject="AIタイピングマスター",
        )
        st.session_state.ty_result = result
        history.log_result(
            "タイピング", 種類="通常", テーマ=st.session_state.ty_theme, モード=st.session_state.ty_mode,
            ノーミス正解=result["perfect"], ミスした問題=result["missedQuestions"], タイム秒=result["time"],
            点数=score, 年齢層=st.session_state.ty_level,
            詳細=pdfgen.make_record(result["subject"], pdf_info, pdf_rows),
        )
        if result["time"] <= SECRET_TIME_LIMIT:
            st.session_state[UNLOCK_KEY] = True
        st.session_state.ty_state = "ending"
        st.rerun()
    if st.button("↩️ やめて メニューに もどる"):
        back_to_menu()

# --- タイピングのけっか ---
elif state == "ending":
    r = st.session_state.ty_result
    st.header("🏆 タイピング大冒険クリア！ 🏆")
    st.balloons()
    st.subheader(RANK_TEXT.get(r["rank"], ""))

    st.metric("🎯 点数", f"{r['score']} / 100 点", help="正確さ60点 ＋ スピード40点（スピードの目標は年れいで変わるよ）")
    st.caption(f"✅ 正確さ {r['accuracy_pt']} / 60 点　＋　⚡ スピード {r['speed_pt']} / 40 点　（{st.session_state.ty_level}）")
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 ノーミス正解", f"{r['perfect']} / {r['total']} 問")
    c2.metric("⏱️ ごうけいタイム", format_time(r["time"]))
    c3.metric("⚡ はやさ", f"{r['kpm']} 打/分")
    c4, c5, c6 = st.columns(3)
    c4.metric("✅ 正確さ", f"{r['accuracy']} %")
    c5.metric("❌ ミスタイプ", f"{r['misses']} 回")
    c6.metric("🔥 さいだいコンボ", f"{r['maxCombo']}")
    if r["misses"] == 0:
        st.success("✨ ノーミス達成！パーフェクト！")
    elif r["weakKeys"]:
        keys = "、".join(f"「{k.upper()}」（{n}回）" for k, n in r["weakKeys"])
        st.info(f"🔍 まちがえやすかったキー：{keys}　つぎは ここを 意識してみよう！")
    pdf_button(r)
    st.divider()

    if r["time"] <= SECRET_TIME_LIMIT:
        st.markdown(
            "<div style='background:#FFF3CD;padding:20px;border-radius:10px;border-left:6px solid #FFC107;text-align:center'>"
            "<h3 style='color:#856404;margin:0'>✨ 5分以内でクリア達成！ひみつのゲートが開いたよ！ ✨</h3>"
            "<p style='color:#856404'>本物の Python のコードを打つと ロボットが動く<b>「プログラミング・ミッション（全6ステージ）」</b>に挑戦しよう！</p></div>",
            unsafe_allow_html=True,
        )
        if st.button("🔥 プログラミング・ミッションを始める！", type="primary", use_container_width=True):
            start("code_playing")
    else:
        st.info("💡 5分（300秒）以内でクリアすると、特別な「裏メニュー」が出現するよ！次はもっと早く打てるように挑戦してみよう！")

    if st.button("🔄 もどって別のテーマで遊ぶ", use_container_width=True):
        back_to_menu()

# --- 裏メニュー：プログラミング・ミッション ---
elif state == "code_playing":
    st.markdown("<h2 style='color:#FF9800'>💻 裏メニュー：プログラミング・ミッション</h2>", unsafe_allow_html=True)
    result = web_games.typing_game("code", key=f"ty_code_{st.session_state[ROUND_KEY]}", round=st.session_state[ROUND_KEY])
    if result and result.get("type") == "code_done" and result.get("round") == st.session_state[ROUND_KEY]:
        score = code_points(result)
        pdf_rows = [
            (f"ステージ {i + 1}", miss_text(n), "ノーミス", n == 0)
            for i, n in enumerate(result.get("stageMisses", []))
        ]
        pdf_info = (
            f"プログラミング・ミッション（{result['stages']}ステージ） ／ {st.session_state.ty_level}　"
            f"ミス {result['misses']}回 ／ タイム {format_time(result['time'])}"
        )
        result.update(
            score=score, pdf_rows=pdf_rows, pdf_info=pdf_info,
            played_at=time.strftime("%Y-%m-%d %H:%M:%S"), subject="プログラミング・ミッション",
        )
        st.session_state.ty_result = result
        history.log_result(
            "タイピング", 種類="プログラミング", テーマ=f"ロボット{result['stages']}ステージ", モード="-",
            ノーミス正解=result["perfect"], ミスした問題=result["stages"] - result["perfect"], タイム秒=result["time"],
            点数=score, 年齢層=st.session_state.ty_level,
            詳細=pdfgen.make_record(result["subject"], pdf_info, pdf_rows),
        )
        st.session_state.ty_state = "code_ending"
        st.rerun()
    if st.button("↩️ やめて メニューに もどる"):
        back_to_menu()

# --- 裏メニュー・リザルト ---
elif state == "code_ending":
    r = st.session_state.ty_result
    st.header("👑 プログラミング・マスター達成！ 👑")
    st.balloons()
    st.metric("🎯 点数", f"{r['score']} / 100 点", help="ノーミスのステージは満点、ミスのあったステージは半分で計算するよ")
    c1, c2, c3 = st.columns(3)
    c1.metric("🌟 ノーミス ステージ", f"{r['perfect']} / {r['stages']}")
    c2.metric("❌ バグ（ミス）", f"{r['misses']} 回")
    c3.metric("⏱️ クリアタイム", format_time(r["time"]))
    st.success(
        "🤖 AI先生からのメッセージ：\n\n全ステージ クリア おめでとう！ "
        "move・for・変数・if は、本物のプログラマーも 毎日つかっている命令だよ。"
        "つぎは「じゆうモード」で、自分だけの プログラムを 書いてみよう！"
    )
    pdf_button(r)
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("🎨 じゆうに プログラミングする", type="primary", use_container_width=True):
        start("sandbox")
    if c2.button("🔄 もう一度最初から遊ぶ", use_container_width=True):
        back_to_menu()

# --- じゆうモード ---
elif state == "sandbox":
    st.markdown("<h2 style='color:#FF9800'>🎨 じゆうに プログラミング</h2>", unsafe_allow_html=True)
    st.caption("左にコードを書いて「▶ じっこう」。ほしを ぜんぶ あつめたり、色で 絵を かいたりしてみよう！")
    web_games.typing_game("sandbox", key="ty_sandbox_game")
    if st.button("↩️ メニューに もどる"):
        back_to_menu()
