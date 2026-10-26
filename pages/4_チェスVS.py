import streamlit as st

import common
import history
import web_games

common.setup_page("チェス", "♟️")
common.hero("♟️ デジタルチェス", "駒をクリック（ドラッグもOK）して動かそう！ CPU戦も2人対戦もできるよ。")

result = web_games.chess_game(key="chess_board")

# ゲームが終わると盤から結果がとどく。同じゲームは1回だけ記録する。
if result and result.get("type") == "game_over":
    saved = history.log_once(
        "チェス", result["id"],
        あそびかた=result["mode"], 難易度=result["level"], 結果=result["result"], 手数=result["moves"],
    )
    if saved:
        st.toast("せいせきを記録したよ！", icon="📒")

with st.expander("📘 チェスのルール（かんたん説明）"):
    st.markdown(
        """
- **目的**：相手のキングを、にげられないように追いつめたら勝ち（**チェックメイト**）。
- **チェック**：キングがねらわれている状態。つぎの手で かならず にげよう。
- **キャスリング**：キングとルークが一度も動いていなければ、キングを2マス横に動かすと ルークがとなりに来るよ。
- **アンパッサン**：となりのポーンが2マス進んできたら、ななめうしろに回りこんで とれる特別ルール。
- **プロモーション**：ポーンが いちばん奥まで進むと、クイーンなどに なれるよ。
- 途中でページを閉じても、このパソコンなら つづきから あそべるよ。
"""
    )
