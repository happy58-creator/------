import streamlit as st

import common
import web_games

common.setup_page("あみだくじ", "🎉")
common.hero("🎉 ドキドキ！ほんかく あみだくじ", "ぜんいんが 先に スタートを えらんで、真ん中を ひらいて けっかを 見よう！")

ROUND_KEY = "amida_round"  # ゲームごとに増やして、新しいあみだを作る
DEFAULTS = {"lot_started": False, "lot_mode": "くじ引き（あたりは1人）", "lot_names": []}
common.init_state(DEFAULTS)
st.session_state.setdefault(ROUND_KEY, 0)

# --- 設定（サイドバー） ---
with st.sidebar:
    st.header("⚙️ 設定（せってい）")
    num_players = st.slider("何人で あそぶ？", min_value=2, max_value=8, value=5)
    game_mode = st.radio("どっちで あそぶ？", ("くじ引き（あたりは1人）", "じゅんい決め"))
    with st.expander("✏️ なまえを かえる（おこのみで）"):
        names = [
            st.text_input(f"{i + 1}番めの人", value=f"{i + 1}P", key=f"lot_name_{i}", max_chars=8)
            for i in range(num_players)
        ]
    st.write("---")
    start_button = st.button("ゲームをはじめる！", type="primary", use_container_width=True)

if start_button:
    st.session_state.lot_started = True
    st.session_state.lot_mode = game_mode
    st.session_state.lot_names = [(n.strip() or f"{i + 1}P") for i, n in enumerate(names)]
    st.session_state[ROUND_KEY] += 1

if not st.session_state.lot_started:
    st.info("👈 左側の メニューで 人数と あそびかたを えらんで「ゲームをはじめる！」を おしてね！")
    with st.container(border=True):
        st.markdown(
            "**あそびかた**\n\n"
            "1. みんなが 順番に、上の ばんごう（スタート）を タップして えらびます。\n"
            "2. 真ん中の よこ線は 「ひみつ」で かくれています。下の けっか（順位・あたり）は 見えています。\n"
            "3. 全員 えらびおわったら、ひみつを ひらいて スタート！ 点が おりていって けっかが 出ます。"
        )
    st.stop()

names = st.session_state.lot_names
st.caption(f"{len(names)}人 ／ {st.session_state.lot_mode}")
web_games.amida_game(
    f"amida_{st.session_state[ROUND_KEY]}", names=names,
    mode="rank" if st.session_state.lot_mode == "じゅんい決め" else "lot", round=st.session_state[ROUND_KEY],
)
st.caption("「もういちど」で 同じ人数のまま 新しい あみだが 作れるよ。人数やなまえを かえるときは、左のメニューから。")
