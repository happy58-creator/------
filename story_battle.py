"""戦闘コンポーネント（ブラウザ側で1ステージ分の戦闘を動かし、結果を Python に返す）

ターン制：自分のターン（攻撃かアイテム）→ 敵のターン、を繰り返す。連打・エフェクト・状態異常・
ターンの進行はすべてブラウザの中で処理する（押すたびにサーバーと通信すると、数えもれや遅れが出るため）。
ダメージの数字は story_logic.battle_config() で計算したものをそのまま使う。
戦闘が終わると、次の dict を返す（戦闘中は None）。

    {"round": 戦闘の番号, "result": "win" | "lose" | "quit" | "escape"（エクストラの「にげる」）,
     "ally_hp": 残りHP, "enemy_hp": 敵の残りHP, "turns": 自分のターン数,
     "taps": タップ数, "hits": 当たった数, "misses": 外れた数,
     "damage_dealt": 与えたダメージ, "damage_taken": 受けたダメージ,
     "enemy_attacks": 敵の攻撃回数, "elapsed_ms": かかった時間,
     "used": {アイテムのid: 使った個数}}

画面いっぱいに表示するため、戦闘中のページでは fullscreen_css() を一緒に出すこと。
"""
from pathlib import Path

import streamlit.components.v1 as components

import story_assets
import story_data
import story_logic

_component = components.declare_component(
    "story_battle", path=str(Path(__file__).resolve().parent / "web" / "story")
)


def fullscreen_css():
    """戦闘コンポーネントの iframe を画面いっぱいに広げる CSS（st.markdown(..., unsafe_allow_html=True) で出す）"""
    return """
<style>
iframe[title="story_battle.story_battle"], div[data-testid="stCustomComponentV1"] iframe, iframe[data-testid="stCustomComponentV1"] {
  position: fixed !important; inset: 0 !important; width: 100vw !important; height: 100vh !important; height: 100dvh !important;
  z-index: 999999 !important; border: 0 !important; background: #07060a;
}
header[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stToolbar"] { display: none !important; }
</style>
"""


def battle(config, key):
    """story_logic.battle_config() で作った設定で戦闘を始める"""
    enemy = story_logic.enemy_by_key(config["enemy"]["key"])
    return _component(
        config=config,
        scene_html=story_assets.stage_html(enemy),
        scene_css=story_assets.SCENE_CSS,
        hit_mask=story_assets.hit_mask_uri(enemy),
        ally_icon=story_assets.ally_icon_uri(config["ally"]["lv"]),
        item_icons={item["id"]: story_assets.item_icon_uri(item["id"]) for item in config["items"]},
        status_icons={sid: uri for sid in story_data.STATUS_EFFECTS if (uri := story_assets.status_icon_uri(sid))},
        key=key,
        default=None,
    )
