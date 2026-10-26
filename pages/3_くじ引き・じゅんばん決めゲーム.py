import random
import time

import streamlit as st

import common

common.setup_page("くじ引き・じゅんばん決め", "🎉")
common.hero("🎉 ドキドキ！あみだ風くじ引き ＆ じゅんい決め", "ひとりずつ順番に、あみだくじをたどって結果を見よう！")

DEFAULTS = {
    "lot_started": False,
    "lot_idx": 0,
    "lot_results": {},
    "lot_revealed": {},
    "lot_mode": "くじ引き（あたりは1人）",
}
common.init_state(DEFAULTS)

# --- 設定（サイドバー） ---
with st.sidebar:
    st.header("⚙️ 設定（せってい）")
    num_players = st.slider("何人で あそぶ？", min_value=2, max_value=8, value=3)
    game_mode = st.radio("どっちで あそぶ？", ("くじ引き（あたりは1人）", "じゅんい決め"))
    st.write("---")
    start_button = st.button("ゲームをはじめる！", type="primary", use_container_width=True)

if start_button:
    players = [f"{i}P" for i in range(1, num_players + 1)]
    if game_mode == "くじ引き（あたりは1人）":
        winner = random.choice(players)
        results = {p: "🎉 あたり！ 🎉" if p == winner else "📁 はずれ" for p in players}
    else:
        ranks = list(range(1, num_players + 1))
        random.shuffle(ranks)
        results = {p: f"{r}位" for p, r in zip(players, ranks)}
    st.session_state.lot_results = results
    st.session_state.lot_started = True
    st.session_state.lot_idx = 0
    st.session_state.lot_revealed = {}
    st.session_state.lot_mode = game_mode


def play_amida_animation(columns):
    """玉(🔴)があみだを降りていく演出。"""
    status = st.empty()
    board = st.empty()
    status.markdown("### 🪵 あみだくじを おりています... 🪵")
    pos = random.randrange(columns)
    rows = 7
    for row in range(rows):
        lines = []
        for r in range(rows):
            cells = ["│"] * columns
            if r % 2 == 1 and r != row:  # 横棒（飾り）
                left = (r * 3) % (columns - 1)
                cells[left] = "├─"
                cells[left + 1] = "─┤"
            if r == row:
                cells[pos] = "🔴"
            lines.append("  ".join(cells))
        board.code("\n".join(lines))
        if row % 2 == 1 and columns > 1:
            pos = max(0, min(columns - 1, pos + random.choice([-1, 1])))
        time.sleep(0.25)
    status.markdown("### 🥁 ドルドルドルドル...... 🥁")
    time.sleep(0.6)
    status.markdown("### 🔔 ジャン！！！ 🔔")
    time.sleep(0.3)


# --- メイン ---
if not st.session_state.lot_started:
    st.info("👈 左側のメニューから人数とあそびかたを えらんで「ゲームをはじめる！」を押してね！")
    st.stop()

players_list = list(st.session_state.lot_results)
total = len(players_list)
idx = st.session_state.lot_idx
st.progress(len(st.session_state.lot_revealed) / total, text=f"{len(st.session_state.lot_revealed)} / {total} 人 おわり")

if idx < total:
    current = players_list[idx]
    with st.container(border=True):
        st.subheader(f"🎵 {current} の 番（ばん）だよ！")
        st.write("他の人は見ないでね。ボタンを押すと、あみだくじがスタート！")
        if st.button(f"👇 {current} のあみだくじをスタート！", key=f"lot_btn_{idx}", type="primary", use_container_width=True):
            play_amida_animation(total)
            st.session_state.lot_revealed[current] = st.session_state.lot_results[current]
            st.session_state.lot_idx += 1
            st.rerun()

if st.session_state.lot_revealed:
    last_player = list(st.session_state.lot_revealed)[-1]
    st.info(f"📢 【前の結果】 {last_player} は ➡️ **{st.session_state.lot_revealed[last_player]}** でした！")

if len(st.session_state.lot_revealed) == total:
    st.divider()
    st.subheader("📊 全員（ぜんいん）の結果発表！！！")
    if st.session_state.lot_mode == "じゅんい決め":
        # 順位順に並べて見やすく
        ordered = sorted(st.session_state.lot_revealed.items(), key=lambda kv: int(kv[1].rstrip("位")))
    else:
        ordered = list(st.session_state.lot_revealed.items())
    medals = {"1位": "🥇", "2位": "🥈", "3位": "🥉"}
    for player, res in ordered:
        if "あたり" in res or res == "1位":
            st.success(f"{medals.get(res, '🥇')} {player} : {res}")
        elif res in medals:
            st.warning(f"{medals[res]} {player} : {res}")
        else:
            st.info(f"🏃 {player} : {res}")
    if any("あたり" in r for r in st.session_state.lot_revealed.values()):
        st.balloons()

    if st.button("もういちど最初からあそぶ", type="primary", use_container_width=True):
        common.reset_state("lot_", DEFAULTS)
        st.rerun()
