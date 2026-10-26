import random

import streamlit as st

import common

common.setup_page("じゃんけんゲーム", "✊")
common.hero("✊✌️🖐️ じゃんけんゲーム", "コンピューターと勝負！ または2人でたいせん！")

HANDS = {"グー": "✊", "チョキ": "✌️", "パー": "🖐️"}
BEATS = {"グー": "チョキ", "チョキ": "パー", "パー": "グー"}  # key は value に勝つ

DEFAULTS = {
    "rps_mode": "コンピューターとたいせん",
    "rps_p1": None,
    "rps_p2": None,
    "rps_last": None,  # CPU戦の直前結果: (自分の手, 相手の手, 結果)
    "rps_score": {"win": 0, "lose": 0, "draw": 0},
    "rps_streak": 0,
    "rps_best_streak": 0,
    "rps_pvp_wins": {"p1": 0, "p2": 0, "draw": 0},
}
common.init_state(DEFAULTS)


def judge(a, b):
    """a から見た結果: win / lose / draw"""
    if a == b:
        return "draw"
    return "win" if BEATS[a] == b else "lose"


def hand_card(label, hand):
    st.markdown(
        f"<div class='big-center' style='font-size:5rem'>{HANDS[hand]}</div>"
        f"<div class='big-center' style='font-size:1.1rem'>{label}<br>（{hand}）</div>",
        unsafe_allow_html=True,
    )


def hand_buttons(prefix):
    """グー・チョキ・パーの大きなボタン。押された手を返す。"""
    picked = None
    for col, (name, emoji) in zip(st.columns(3), HANDS.items()):
        with col:
            if st.button(f"{emoji}\n\n{name}", key=f"{prefix}_{name}", use_container_width=True):
                picked = name
    return picked


mode = st.radio(
    "あそびかたを えらんでね：",
    ("コンピューターとたいせん", "2人でたいせん"),
    horizontal=True,
)
if mode != st.session_state.rps_mode:
    st.session_state.rps_mode = mode
    st.session_state.rps_p1 = None
    st.session_state.rps_p2 = None
    st.session_state.rps_last = None
    st.rerun()

# --- コンピューター対戦 ---
if mode == "コンピューターとたいせん":
    score = st.session_state.rps_score
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎉 かち", score["win"])
    c2.metric("👾 まけ", score["lose"])
    c3.metric("🤔 あいこ", score["draw"])
    c4.metric("🔥 れんしょう", st.session_state.rps_streak, help=f"さいこう {st.session_state.rps_best_streak} れんしょう")

    st.subheader("じぶんの手を えらんでね！")
    picked = hand_buttons("cpu")
    if picked:
        cpu = random.choice(list(HANDS))
        result = judge(picked, cpu)
        score[result] += 1
        if result == "win":
            st.session_state.rps_streak += 1
            st.session_state.rps_best_streak = max(
                st.session_state.rps_best_streak, st.session_state.rps_streak
            )
        elif result == "lose":
            st.session_state.rps_streak = 0
        st.session_state.rps_last = (picked, cpu, result)
        st.rerun()

    last = st.session_state.rps_last
    if last:
        mine, theirs, result = last
        st.divider()
        left, mid, right = st.columns([5, 1, 5])
        with left:
            hand_card("あなた", mine)
        with mid:
            st.markdown("<div class='big-center' style='font-size:2rem;padding-top:2rem'>VS</div>", unsafe_allow_html=True)
        with right:
            hand_card("コンピューター", theirs)
        if result == "draw":
            st.warning("🤔 あいこ！ もう一回！")
        elif result == "win":
            st.success("🎉 やったね！ あなたの 勝ち！")
            if st.session_state.rps_streak >= 3:
                st.balloons()
        else:
            st.error("👾 ざんねん！ 相手の 勝ち！")

    if score["win"] + score["lose"] + score["draw"] > 0:
        if st.button("せいせきをリセット"):
            st.session_state.rps_score = {"win": 0, "lose": 0, "draw": 0}
            st.session_state.rps_streak = 0
            st.session_state.rps_best_streak = 0
            st.session_state.rps_last = None
            st.rerun()

# --- 2人対戦 ---
else:
    wins = st.session_state.rps_pvp_wins
    c1, c2, c3 = st.columns(3)
    c1.metric("プレイヤー1", f"{wins['p1']} 勝")
    c2.metric("プレイヤー2", f"{wins['p2']} 勝")
    c3.metric("あいこ", f"{wins['draw']} 回")

    p1, p2 = st.session_state.rps_p1, st.session_state.rps_p2
    if p1 is None:
        st.subheader("【プレイヤー1】の手を選んでね")
        st.caption("次の人に見られないように！")
        picked = hand_buttons("p1")
        if picked:
            st.session_state.rps_p1 = picked
            st.rerun()
    elif p2 is None:
        st.subheader("【プレイヤー2】の手を選んでね")
        st.caption("プレイヤー1の手は かくれているよ。")
        picked = hand_buttons("p2")
        if picked:
            st.session_state.rps_p2 = picked
            result = judge(p1, picked)
            wins["draw" if result == "draw" else ("p1" if result == "win" else "p2")] += 1
            st.rerun()
    else:
        left, mid, right = st.columns([5, 1, 5])
        with left:
            hand_card("プレイヤー1", p1)
        with mid:
            st.markdown("<div class='big-center' style='font-size:2rem;padding-top:2rem'>VS</div>", unsafe_allow_html=True)
        with right:
            hand_card("プレイヤー2", p2)
        result = judge(p1, p2)
        if result == "draw":
            st.warning("🤔 あいこ！ もう一回！")
        else:
            st.success(f"🎉 プレイヤー{1 if result == 'win' else 2} の 勝ち！")
            st.balloons()
        if st.button("もういちど あそぶ", type="primary", use_container_width=True):
            st.session_state.rps_p1 = None
            st.session_state.rps_p2 = None
            st.rerun()
