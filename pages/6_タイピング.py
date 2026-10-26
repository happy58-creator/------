import html
import json
import time

import streamlit as st
from google.genai import types

import common
import history

common.setup_page("AIタイピングマスター", "⌨️")
common.hero("⌨️ AIワクワクたいぴんぐアドベンチャー 🌟", "入力したテーマに合わせて、AIがキミ専用のタイピングもんだいを作ってくれるよ！")

client = common.get_gemini_client()

NORMAL_Q = 10
SECRET_Q = 5
SECRET_TIME_LIMIT = 300.0  # 5分以内にクリアで裏メニュー解放

DEFAULTS = {
    "ty_state": "menu",  # menu, playing, ending, secret_playing, secret_ending
    "ty_q": 0,
    "ty_miss": 0,
    "ty_correct": 0,  # ノーミスで正解した数
    "ty_data": None,
    "ty_mode": "みながらモード",
    "ty_theme": "",
    "ty_start": 0.0,
    "ty_q_start": 0.0,
    "ty_total_time": 0.0,
    "ty_done": set(),  # 正解済みの問題番号
    "ty_missed": set(),  # 1回でもミスした問題番号
}
common.init_state(DEFAULTS)

# ローマ字の表記ゆれを、問題で使っている短い綴りにそろえる
ROMAJI_VARIANTS = [
    ("sha", "sya"), ("shu", "syu"), ("sho", "syo"), ("shi", "si"),
    ("cha", "tya"), ("chu", "tyu"), ("cho", "tyo"), ("chi", "ti"),
    ("ja", "zya"), ("ju", "zyu"), ("jo", "zyo"), ("ji", "zi"),
    ("tsu", "tu"), ("fu", "hu"),
]


def normalize_romaji(text):
    t = (text or "").lower().replace(" ", "").replace("　", "").strip()
    for long_form, short_form in ROMAJI_VARIANTS:
        t = t.replace(long_form, short_form)
    return t


def render_highlight(target, typed, mono=False):
    """打った文字を緑、まちがいを赤、まだの文字を灰色で表示する。"""
    parts = []
    for i, ch in enumerate(target):
        shown = html.escape(ch) if ch != " " else "␣"
        if i < len(typed):
            color = "#2ECC71" if typed[i] == ch else "#E74C3C"
            parts.append(f"<span style='color:{color};font-weight:bold'>{shown}</span>")
        else:
            parts.append(f"<span style='color:#BDC3C7'>{shown}</span>")
    if len(typed) > len(target):
        extra = html.escape(typed[len(target):])
        parts.append(f"<span style='color:#fff;background:#E74C3C;border-radius:3px;padding:0 2px'>{extra}</span>")
    style = (
        "font-family:monospace;font-size:24px;background:#222;padding:12px;border-radius:8px;color:#fff;"
        if mono
        else "text-align:center;font-size:34px;letter-spacing:2px;margin-bottom:2px;"
    )
    st.markdown(f"<p style='{style}'>{''.join(parts)}</p>", unsafe_allow_html=True)


def format_time(seconds):
    minutes, secs = int(seconds // 60), round(seconds % 60, 1)
    return f"{minutes}分 {secs}秒" if minutes else f"{secs}秒"


def call_ai(prompt, temperature, retries=3):
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
    - 対象は小学3年生なので、問題の日本語はすべて「ひらがな」または「簡単なカタカナ」のみにしてください。
    - 各問題に対して、パソコンのキーボードで実際に入力する用のローマ字（半角小文字）を対応させてください。
    - カタカナの長音（ー）は、必ずハイフン「-」で出力してください。（例: クリーパーは "kuri-pa-"、ケーキは "ke-ki"）※母音を重ねる(keeki等)のは絶対に禁止です。
    - パソコン入力で最も一般的な、打鍵数の少ない表記に限定してください。
      - 「し」は必ず "si" にしてください（"shi" は禁止）。
      - 「ち」は必ず "ti" にしてください（"chi" は禁止）。
      - 「つ」は必ず "tu" にしてください（"tsu" は禁止）。
      - 「ふ」は必ず "hu" にしてください（"fu" は禁止）。
      - 「じ」は必ず "zi" にしてください（"ji" は禁止）。
      - 「しゃ・しゅ・しょ」は "sya, syu, syo" にしてください。
    - ローマ字の単語と単語の間に、半角スペースや空白を絶対に含めないでください。
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


def generate_secret_issues():
    prompt = """
    あなたは子供にプログラミングを教えるAI先生です。
    Pythonの基本的な文法、変数の定義、関数の使い方に関するタイピング問題を【5問】ランダムに作成してください。
    子供がコードをそのまま「真似っこ（模写）」して入力できるような問題にしてください。

    【ルール】
    - codeには、タイピングさせる実際のPythonコード（半角英数字、記号）を1行で入れてください。スペースも含めます。
    - descriptionには、そのコードが何をしているかの日本語の説明を入れてください。
    - resultには、そのコードを実行したときに画面にどう表示されるか（結果）を書いてください。
    - 問題は難しすぎず、5問きっちり作成してください。

    必ず以下のJSONフォーマットのみで出力してください。

    {
      "issues": [
        {"description": "画面に『こんにちは』と表示するよ", "code": "print(\\"hello\\")", "result": "hello"}
      ]
    }
    """
    return call_ai(prompt, 0.7, retries=2)


def start_round(state, issues):
    st.session_state.ty_data = issues
    st.session_state.ty_q = 0
    st.session_state.ty_miss = 0
    st.session_state.ty_correct = 0
    st.session_state.ty_done = set()
    st.session_state.ty_missed = set()
    st.session_state.ty_state = state
    st.session_state.ty_start = time.time()
    st.session_state.ty_q_start = time.time()


def valid_issues(data, count, keys):
    return bool(data) and len(data.get("issues", [])) >= count and all(
        all(k in issue for k in keys) for issue in data["issues"][:count]
    )


def play_question(total, secret):
    """1問分の入力フォームと判定。正解したら True を返す。"""
    q = st.session_state.ty_q
    issue = st.session_state.ty_data[q]
    if secret:
        target = issue["code"].strip()
        normalize = lambda t: (t or "").strip()
        input_label = "スペースや記号（かっこ、クォーテーション）も正確に合わせてね！"
        submit_label = "コードを実行する！ ⚡"
    else:
        target = normalize_romaji(issue["romaji"])
        normalize = normalize_romaji
        input_label = "ここにアルファベットを入力してエンターを押してね！"
        submit_label = "決定（けってい）！"

    done = q in st.session_state.ty_done
    st.progress(q / total, text=f"{q + 1} / {total} 問目")

    if secret:
        st.markdown(
            f"<div style='background:#2c3e50;padding:15px;border-radius:8px;color:#fff;font-size:18px;margin-bottom:15px'>"
            f"<b>📝 コードの説明:</b> {html.escape(issue['description'])}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("**👇 これをそっくりそのままキーボードで打とう：**")
        st.code(target, language="python")
    else:
        st.markdown(
            f"<h2 style='text-align:center;color:#1E88E5'>{html.escape(issue['japanese'])}</h2>",
            unsafe_allow_html=True,
        )

    with st.form(f"ty_form_{secret}_{q}", clear_on_submit=False):
        typed_raw = st.text_input(input_label, key=f"ty_input_{secret}_{q}", disabled=done)
        submitted = st.form_submit_button(submit_label, type="primary", disabled=done)

    typed = normalize(typed_raw)
    if submitted and not done:
        if typed == target:
            st.session_state.ty_done.add(q)
            done = True
            if q not in st.session_state.ty_missed:
                st.session_state.ty_correct += 1
        else:
            if q not in st.session_state.ty_missed:
                st.session_state.ty_missed.add(q)
                st.session_state.ty_miss += 1

    show_hint = secret or st.session_state.ty_mode == "みながらモード"
    shown_typed = typed if typed_raw else ""
    if show_hint:
        render_highlight(target, shown_typed, mono=secret)
    else:
        st.markdown(
            "<p style='text-align:center;font-size:20px;color:#E53935;font-weight:bold'>"
            "⚠️ あんもくモード：ローマ字はかくれているよ！</p>",
            unsafe_allow_html=True,
        )

    if done:
        st.success("🎉 お見事！正解コードです！" if secret else "🎉 せいかい！ カッコいいぞ！")
        if secret:
            st.markdown("**💻 パソコンの画面（実行結果）：**")
            st.code(issue["result"], language="text")
        return True
    if submitted:
        if secret:
            st.error("❌ おっと！文法エラー（打ち間違い）があるみたい。スペースやカッコをもう一度確かめてみてね！")
        else:
            st.error("❌ おっと！打ち方がちがうみたい。もう一回たしかめてみてね！")
    return False


def advance(total, finish_state):
    if st.session_state.ty_q < total - 1:
        if st.button("つぎのもんだいへ ➡️", key=f"ty_next_{st.session_state.ty_q}", type="primary", use_container_width=True):
            st.session_state.ty_q += 1
            st.session_state.ty_q_start = time.time()
            st.rerun()
    else:
        if st.button("結果発表（けっかはっぴょう）へ！ 🏆", key="ty_finish", type="primary", use_container_width=True):
            st.session_state.ty_total_time = round(time.time() - st.session_state.ty_start, 1)
            history.log_result(
                "タイピング", 種類="裏メニュー" if finish_state == "secret_ending" else "通常",
                テーマ=st.session_state.ty_theme, モード=st.session_state.ty_mode,
                ノーミス正解=st.session_state.ty_correct, ミスした問題=st.session_state.ty_miss,
                タイム秒=st.session_state.ty_total_time,
            )
            st.session_state.ty_state = finish_state
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

    with st.container(border=True):
        st.subheader("✍️ どんなテーマでもんだいを作る？")
        with st.form("ty_theme_form"):
            theme_input = st.text_input("すきな言葉（キーワード）：", placeholder="ここに文字を入力してね")
            go = st.form_submit_button("🚀 AIにもんだいを作ってもらってスタート！", type="primary", use_container_width=True)

    st.caption("コツ：「si」「ti」「tu」「hu」「zi」のみじかい打ち方でも、「shi」「chi」でも、どちらでもOK！")
    if go:
        if not theme_input.strip():
            st.warning("⚠️ 言葉を入力してね！")
        else:
            with st.spinner("🧙‍♂️ AI先生が、キミのために10問のタイピングもんだいを作成中だよ..."):
                data = generate_typing_issues(theme_input.strip())
            if valid_issues(data, NORMAL_Q, ("japanese", "romaji")):
                start_round("playing", data["issues"][:NORMAL_Q])
                st.session_state.ty_theme = theme_input.strip()
                st.rerun()
            elif data:
                st.error("もんだいの形がうまく作れなかったよ。もう一回ためしてね！")

# --- 通常プレイ / 裏メニュー ---
elif state in ("playing", "secret_playing"):
    secret = state == "secret_playing"
    total = SECRET_Q if secret else NORMAL_Q
    if secret:
        st.markdown("<h2 style='color:#FF9800'>💻 裏メニュー：プログラミング真似っこ</h2>", unsafe_allow_html=True)
    if play_question(total, secret):
        advance(total, "secret_ending" if secret else "ending")

# --- 通常リザルト ---
elif state == "ending":
    st.header("🏆 タイピング大冒険クリア！ 🏆")
    st.balloons()
    correct, miss, total_time = st.session_state.ty_correct, st.session_state.ty_miss, st.session_state.ty_total_time

    st.subheader("📊 キミのたいぴんぐ結果（けっか）")
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 ノーミス正解", f"{correct} / {NORMAL_Q} 問")
    c2.metric("⚠️ ミスした問題", f"{miss} 問")
    c3.metric("⏱️ ごうけいタイム", format_time(total_time))
    if miss == 0:
        st.success("✨ ノーミス達成！パーフェクト！")
    st.divider()

    if total_time <= SECRET_TIME_LIMIT:
        st.markdown(
            "<div style='background:#FFF3CD;padding:20px;border-radius:10px;border-left:6px solid #FFC107;text-align:center'>"
            "<h3 style='color:#856404;margin:0'>✨ 5分以内でクリア達成！ひみつのゲートが開いたよ！ ✨</h3>"
            "<p style='color:#856404'>AI先生から、本物のコードを1問ずつ真似して打つ<b>「プログラミング裏メニュー（全5回）」</b>への挑戦状だ！</p></div>",
            unsafe_allow_html=True,
        )
        if st.button("🔥 裏メニュー（プログラミング挑戦・全5回）を始める！", type="primary", use_container_width=True):
            with st.spinner("💻 AI先生がプログラミングの問題（5問）を用意しているよ..."):
                secret_data = generate_secret_issues()
            if valid_issues(secret_data, SECRET_Q, ("description", "code", "result")):
                start_round("secret_playing", secret_data["issues"][:SECRET_Q])
                st.rerun()
            elif secret_data:
                st.error("問題の形がうまく作れなかったよ。もう一回ためしてね！")
    else:
        st.info("💡 5分（300秒）以内でクリアすると、特別な「裏メニュー」が出現するよ！次はもっと早く打てるように挑戦してみよう！")

    if st.button("🔄 もどって別のテーマで遊ぶ", use_container_width=True):
        common.reset_state("ty_", DEFAULTS)
        st.rerun()

# --- 裏メニュー・リザルト ---
elif state == "secret_ending":
    st.header("👑 裏メニュー・プログラミングマスター達成！ 👑")
    st.balloons()
    st.subheader("📊 キミのハッカーリザルト")
    c1, c2 = st.columns(2)
    c1.metric("⚠️ バグ（ミス）した問題", f"{st.session_state.ty_miss} 問")
    c2.metric("⏱️ クリアにかかった時間", format_time(st.session_state.ty_total_time))
    st.success(
        "🤖 AI先生からのメッセージ：\n\n素晴らしい！全 5 回の本格的なプログラミング特訓をクリアしたね！"
        "記号やスペースの位置まで完璧に見抜いてタイピングできるなんて、キミはもう立派な未来のクリエイターだ！"
    )
    st.divider()
    if st.button("🔄 もう一度最初から遊ぶ", use_container_width=True):
        common.reset_state("ty_", DEFAULTS)
        st.rerun()
