import streamlit as st

import common
import web_games

common.setup_page("あみだくじ", "🎉")
common.hero("🎉 ドキドキ！ほんかく あみだくじ", "ぜんいんが 先に スタートを えらんで、真ん中を ひらいて けっかを 見よう！")

ROUND_KEY = "amida_round"  # ゲームごとに増やして、新しいあみだを作る
DEFAULTS = {"lot_started": False, "lot_mode": "くじ引き（あたりは1人）", "lot_names": [], "lot_count": 5}
common.init_state(DEFAULTS)
st.session_state.setdefault(ROUND_KEY, 0)
MODES = ("くじ引き（あたりは1人）", "じゅんい決め")

# --- 設定画面（さいしょに出る） ---
if not st.session_state.lot_started:
    with st.container(border=True):
        st.subheader("① 何人で あそぶ？")
        num_players = st.slider(
            "人数", min_value=2, max_value=8, value=st.session_state.lot_count, label_visibility="collapsed",
        )
    with st.container(border=True):
        st.subheader("② どっちで あそぶ？")
        game_mode = st.radio(
            "あそびかた", MODES, index=MODES.index(st.session_state.lot_mode), horizontal=True,
            label_visibility="collapsed",
        )
        st.caption(
            "くじ引き：あたりは ひとりだけ。" if game_mode == MODES[0]
            else "じゅんい決め：ぜんいんの 順位が きまるよ。"
        )
    with st.expander("③ なまえを かえる（おこのみで）"):
        names = [
            st.text_input(f"{i + 1}番めの人", value=f"{i + 1}P", key=f"lot_name_{i}", max_chars=8)
            for i in range(num_players)
        ]
    st.info(
        "**あそびかた**　① みんなが 順番に、上の ばんごうを タップして スタートを えらぶ　"
        "② 真ん中の よこ線は 「ひみつ」で かくれている（下の けっかは 見えているよ）　"
        "③ 全員 えらんだら ひみつを ひらいて スタート！ 点が おりて けっかが 出るよ",
        icon="💡",
    )
    if st.button("🏁 この内容で スタート！", type="primary", use_container_width=True):
        st.session_state.lot_started = True
        st.session_state.lot_count = num_players
        st.session_state.lot_mode = game_mode
        st.session_state.lot_names = [(n.strip() or f"{i + 1}P") for i, n in enumerate(names)]
        st.session_state[ROUND_KEY] += 1
        st.rerun()
    st.stop()

# --- ゲーム画面 ---
names = st.session_state.lot_names
st.caption(f"{len(names)}人 ／ {st.session_state.lot_mode}")
web_games.amida_game(
    f"amida_{st.session_state[ROUND_KEY]}", names=names,
    mode="rank" if st.session_state.lot_mode == "じゅんい決め" else "lot", round=st.session_state[ROUND_KEY],
)
st.caption("「もういちど」で 同じ人数のまま 新しい あみだが 作れるよ。")
if st.button("⚙️ 人数や あそびかたを かえる（設定にもどる）", use_container_width=True):
    st.session_state.lot_started = False
    st.rerun()
