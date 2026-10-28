"""戦闘コンポーネント（ブラウザ側で1ステージ分の戦闘を動かし、結果を Python に返す）

連打・敵の反撃・タイマーはブラウザの中で処理する（押すたびにサーバーと通信すると、
数えもれや遅れが出るため）。戦闘が終わると、次の dict を返す。

    {"round": 戦闘の番号, "result": "win" | "lose" | "quit",
     "ally_hp": 残りHP, "enemy_hp": 敵の残りHP, "taps": タップ数, "hits": 当たった数,
     "misses": 外れた数, "damage_dealt": 与えたダメージ, "damage_taken": 受けたダメージ,
     "enemy_attacks": 敵の攻撃回数, "elapsed_ms": かかった時間,
     "used": {アイテムのid: 使った個数}}

戦闘中は None を返す。
"""
from pathlib import Path

import streamlit.components.v1 as components

import story_assets

_component = components.declare_component(
    "story_battle", path=str(Path(__file__).resolve().parent / "web" / "story")
)


def battle(config, key):
    """story_logic.battle_config() で作った設定で戦闘を始める"""
    lv = config["enemy"]["lv"]
    return _component(
        config=config,
        scene_html=story_assets.stage_html(lv),
        scene_css=story_assets.SCENE_CSS,
        hit_mask=story_assets.hit_mask_uri(lv),
        ally_icon=story_assets.ally_icon_uri(config["ally"]["lv"]),
        key=key,
        default=None,
    )
