import math
import time

import streamlit as st

import common

common.setup_page("限界突破！超高速連打ゲーム", "⚡")

TIME_OPTIONS = [
    {"label": "3秒", "sec": 3, "description": "まずはおためし"},
    {"label": "10秒", "sec": 10, "description": "集中力チャレンジ"},
    {"label": "1分", "sec": 60, "description": "本気モード"},
    {"label": "5分", "sec": 300, "description": "持久力チャレンジ"},
    {"label": "10分", "sec": 600, "description": "限界突破！"},
]

st.markdown(
    """
    <style>
        .game-hero {
        padding: 1.5rem 1.25rem;
        border-radius: 1.25rem;
        background: linear-gradient(135deg, #fff1dc, #ffe2e7 55%, #e9e8ff);
        text-align: center;
        margin-bottom: 1rem;
    }
    .game-hero h1 { margin: 0; color: #542b69; }
    .game-hero p { margin: .5rem 0 0; color: #584b62; }
    div.stButton > button[kind="primary"] {
        min-height: 3.2rem;
        border-radius: .9rem;
        font-weight: 700;
    }
    .st-key-hit-button-area button {
        height: min(42vh, 380px) !important;
        min-height: 220px !important;
        font-size: 2rem !important;
        border-radius: 1.5rem !important;
        box-shadow: 0 8px 18px rgba(190, 45, 68, .24);
    }
    div[data-testid="stMetric"] {
        padding: .8rem;
        border: 1px solid rgba(128, 128, 128, .2);
        border-radius: .9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

common.init_state({
    "rapid_game_state": "menu",
    "rapid_selected_time": 0,
    "rapid_click_count": 0,
    "rapid_best_scores": {},
    "rapid_game_history": [],
})


def get_rank(clicks_per_second):
    if clicks_per_second < 4:
        return "🌱", "チャレンジャー", "いいスタート！自分のペースで続けてみよう。"
    if clicks_per_second < 7:
        return "⭐", "スピードスター", "リズムよく押せているね！"
    if clicks_per_second < 10:
        return "🔥", "プロゲーマー級", "すごい集中力！ナイスチャレンジ！"
    if clicks_per_second < 15:
        return "🚀", "超人級", "目にもとまらぬ速さ！"
    return "🏅", "神の指", "驚きの記録！まさに限界突破！"


def start_game(duration):
    st.session_state.rapid_selected_time = duration
    st.session_state.rapid_click_count = 0
    st.session_state.rapid_countdown_end_time = time.monotonic() + 3
    st.session_state.rapid_game_state = "countdown"


def finish_game():
    duration = st.session_state.rapid_selected_time
    clicks = st.session_state.rapid_click_count
    cps = clicks / duration
    best_scores = st.session_state.rapid_best_scores
    previous_best = best_scores.get(duration, 0)
    is_new_record = clicks > previous_best
    best_scores[duration] = max(previous_best, clicks)
    st.session_state.rapid_show_record_celebration = is_new_record
    st.session_state.rapid_game_history.insert(
        0,
        {
            "duration": duration,
            "clicks": clicks,
            "cps": cps,
            "played_at": time.strftime("%H:%M"),
        },
    )
    del st.session_state.rapid_game_history[5:]
    st.session_state.rapid_game_state = "result"


common.hero("⚡ 限界突破！超高速連打ゲーム", "時間内にボタンを連打して、自己ベストに挑戦しよう！")

if st.session_state.rapid_game_state == "menu":
    st.subheader("🎮 チャレンジコースを選ぼう")
    st.caption("コースを選ぶと3秒のカウントダウンが始まるよ。準備してね！")
    columns = st.columns(len(TIME_OPTIONS))
    for column, option in zip(columns, TIME_OPTIONS):
        with column:
            st.markdown(f"#### {option['label']}")
            st.caption(option["description"])
            if st.button(
                "スタート",
                key=f"start_{option['sec']}",
                type="primary",
                use_container_width=True,
            ):
                start_game(option["sec"])
                st.rerun()

    st.divider()
    st.subheader("🏆 ベストスコア")
    scores = st.session_state.rapid_best_scores
    score_columns = st.columns(len(TIME_OPTIONS))
    for column, option in zip(score_columns, TIME_OPTIONS):
        with column:
            score = scores.get(option["sec"])
            st.metric(option["label"], f"{score:,} 回" if score is not None else "—")
    st.caption("記録はこのブラウザーの画面を開いている間保存されます。")

    history = st.session_state.rapid_game_history
    if history:
        st.subheader("🕘 最近のチャレンジ")
        for index, attempt in enumerate(history, start=1):
            st.write(
                f"**{index}.** {attempt['duration']}秒コース — "
                f"{attempt['clicks']:,}回（{attempt['cps']:.2f}回/秒）"
            )

elif st.session_state.rapid_game_state in ("countdown", "playing"):

    @st.fragment(run_every="100ms")
    def render_live_game():
        if st.session_state.rapid_game_state == "countdown":
            remaining = st.session_state.rapid_countdown_end_time - time.monotonic()
            if remaining <= 0:
                st.session_state.rapid_game_state = "playing"
                st.session_state.rapid_start_time = time.monotonic()
                st.rerun()
            else:
                number = math.ceil(remaining)
                st.markdown(
                    f"<h2 style='text-align:center'>準備はいい？</h2>"
                    f"<div style='text-align:center;font-size:7rem;font-weight:800;"
                    f"color:#ff4b4b;line-height:1.2'>{number}</div>",
                    unsafe_allow_html=True,
                )
                st.caption(f"{st.session_state.rapid_selected_time}秒コースに挑戦！")

        elif st.session_state.rapid_game_state == "playing":
            duration = st.session_state.rapid_selected_time
            elapsed = time.monotonic() - st.session_state.rapid_start_time
            remaining = max(0.0, duration - elapsed)
            if remaining <= 0:
                finish_game()
                st.rerun()

            progress = min(1.0, elapsed / duration)
            st.progress(progress, text=f"残り {remaining:.1f} 秒")
            st.markdown(
                f"<div style='text-align:center;font-size:1.25rem'>"
                f"いまのスコア</div><div style='text-align:center;font-size:3.5rem;"
                f"font-weight:800;color:#ff4b4b;line-height:1.2'>"
                f"{st.session_state.rapid_click_count:,}<span style='font-size:1.3rem'> 回</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            with st.container(key="hit-button-area"):
                if st.button(
                    "🔴 ここを連打！",
                    key="hit_button",
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state.rapid_click_count += 1
            st.caption("ボタンを押した回数を数えるよ。時間切れまでがんばろう！")

    render_live_game()

elif st.session_state.rapid_game_state == "result":
    clicks = st.session_state.rapid_click_count
    duration = st.session_state.rapid_selected_time
    cps = clicks / duration
    rank_emoji, rank_name, rank_message = get_rank(cps)

    if st.session_state.get("rapid_show_record_celebration", False):
        st.balloons()
        st.success("🎉 新しいベストスコア！")
        st.session_state.rapid_show_record_celebration = False

    st.subheader("🏁 チャレンジ終了！")
    st.markdown(f"## {rank_emoji} ランク：{rank_name}")
    st.info(rank_message)
    if clicks == 0:
        st.warning("次はボタンを押してみよう！")

    first_try = (
        clicks == st.session_state.rapid_best_scores.get(duration, 0)
        and len(
            [
                attempt
                for attempt in st.session_state.rapid_game_history
                if attempt["duration"] == duration
            ]
        )
        == 1
    )
    if first_try:
        st.caption("このコースの初チャレンジ記録だよ。次は自分の記録に挑戦！")

    st.markdown(f"### {duration}秒で **{clicks:,} 回** 連打！")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("⚡ 1秒あたり", f"{cps:.2f} 回")
    with col2:
        st.metric("⏱️ 1回あたり", f"{duration / clicks:.2f} 秒" if clicks else "—")
    with col3:
        st.metric("🏆 このコースのベスト", f"{st.session_state.rapid_best_scores[duration]:,} 回")

    st.divider()
    col_again, col_menu = st.columns(2)
    with col_again:
        if st.button("🔁 同じコースでもう一度", type="primary", use_container_width=True):
            start_game(duration)
            st.rerun()
    with col_menu:
        if st.button("🎮 コースを選びなおす", use_container_width=True):
            st.session_state.rapid_game_state = "menu"
            st.rerun()

    st.subheader("🕘 最近のチャレンジ")
    for index, attempt in enumerate(st.session_state.rapid_game_history, start=1):
        st.write(
            f"**{index}.** {attempt['duration']}秒 — {attempt['clicks']:,}回 "
            f"（{attempt['cps']:.2f}回/秒）"
        )
