"""戦闘コンポーネント（ブラウザ側で1ステージ分の戦闘を動かし、結果を Python に返す）

ターン制：自分のターン（アイテムを1つ使ってから、攻撃か魔法）→ 敵のターン、を繰り返す。連打・エフェクト・状態異常・
ターンの進行はすべてブラウザの中で処理する（押すたびにサーバーと通信すると、数えもれや遅れが出るため）。
ダメージの数字は story_logic.battle_config() で計算したものをそのまま使う。
戦闘が終わると、次の dict を返す（戦闘中は None）。

    {"round": 戦闘の番号, "result": "win" | "lose" | "quit" | "escape"（エクストラの「にげる」）,
     "ally_hp": 残りHP, "enemy_hp": 敵の残りHP, "turns": 自分のターン数,
     "taps": タップ数, "hits": 当たった数, "misses": 外れた数,
     "damage_dealt": 与えたダメージ, "damage_taken": 受けたダメージ,
     "enemy_attacks": 敵の攻撃回数, "elapsed_ms": かかった時間,
     "used": {アイテムのid: 使った個数},
     "ally_mp": 残りMP, "used_mp": 使ったMP, "crits": 会心の回数, "casts": 魔法の回数, "chant_taps": 詠唱で円に当てた回数}

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
/* 戦闘中は外側のページを動かさない（連打やピンチでページがずれないように） */
html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main {
  overflow: hidden !important; overscroll-behavior: none !important; touch-action: none !important;
}
</style>
"""


def kz_args(config):
    """風哭きの森：敵が何体もいる画面と、それぞれの当たりマスク（覚醒・大技の絵も）"""
    foes = [story_logic.enemy_by_key(f["key"]) for f in config["foes"]]
    out = {"scene_html": story_assets.kz_stage_html(foes, config["area"]),
           "hit_masks": [story_assets.kz_hit_mask_uri(e) for e in foes]}
    aw = foes[0].get("awaken") if len(foes) == 1 and config.get("awaken") else None
    if aw:
        awake = {**foes[0], "image": aw["image"], "cutout": aw.get("cutout", True), "name": aw["name"]}
        out["awaken_scene_html"] = story_assets.kz_stage_html([awake], config["area"])
        out["awaken_hit_mask"] = story_assets.kz_hit_mask_uri(awake)
        if aw.get("special"):
            out["awaken_special_image"] = story_assets.image_uri(f"enemies/{aw['special']['image']}")
    return out


def battle(config, key):
    """story_logic.battle_config() で作った設定で戦闘を始める"""
    if config.get("foes"):
        return _battle_kz(config, key)
    enemy = story_logic.enemy_by_key(config["enemy"]["key"])
    awaken = {}
    assist = config.get("assist")
    has_feather = any(i["id"] == "spirit_feather" and i["count"] > 0 for i in config["items"])
    if assist and (assist["random"] or assist.get("rescue") or has_feather):     # アステルの援護が起こりうるときだけ、絵を送る
        a = story_data.ASSIST
        awaken["assist_images"] = {"sky": story_assets.image_uri(f"skills/{a['image']}"),
                                   "skill": story_assets.image_uri(f"skills/{a['skill_image']}")}
    skill_scene = (config.get("skill") or {}).get("scene")
    if skill_scene:
        awaken["skill_scene_image"] = story_assets.image_uri(f"skills/{skill_scene['image']}")
    scene = enemy.get("meteor_scene")
    if scene and "meteor" in enemy.get("gimmicks", []):
        awaken["meteor_scene"] = {"name": scene["name"], "focus": scene.get("focus", "50% 50%"),
                                  "image": story_assets.image_uri(f"enemies/{scene['image']}")}
    if config.get("awaken") and enemy.get("awaken"):
        aw = enemy["awaken"]
        awake_enemy = {**enemy, "image": aw["image"], "focus": aw.get("focus", enemy.get("focus")), "name": aw["name"]}
        awaken = {"awaken_scene_html": story_assets.stage_html(awake_enemy),
                  "awaken_hit_mask": story_assets.hit_mask_uri(awake_enemy),
                  "awaken_special_image": story_assets.image_uri(f"enemies/{aw['special']['image']}")}
    return _component(
        config=config,
        scene_html=story_assets.stage_html(enemy),
        scene_css=story_assets.SCENE_CSS,
        hit_mask=story_assets.hit_mask_uri(enemy),
        ally_icon=story_assets.ally_icon_uri(config["ally"]["lv"]),
        item_icons={item["id"]: story_assets.item_thumb(item["id"], 192) for item in config["items"]},
        equip_icons={e["id"]: story_assets.equipment_thumb(e["id"]) for part in ("gear", "acc") for e in config["loadout"][part]},
        status_icons={sid: uri for sid in story_data.STATUS_EFFECTS if (uri := story_assets.status_icon_uri(sid))},
        **party_args(config),
        **awaken,
        key=key,
        default=None,
    )


def party_args(config):
    """パーティの仲間の顔と必殺技の絵"""
    out = {"member_icons": {}, "member_skill_images": {}, "member_equip_icons": {}}
    for m in config.get("party") or []:
        out["member_icons"][str(m["lv"])] = story_assets.ally_icon_uri(m["lv"])
        sc = (m.get("skill") or {}).get("scene")
        if sc:
            out["member_skill_images"][str(m["lv"])] = story_assets.image_uri(f"skills/{sc['image']}")
        for part in ("gear", "acc"):
            for e in m["loadout"][part]:
                out["member_equip_icons"][e["id"]] = story_assets.equipment_thumb(e["id"])
    return out


def _common_args(config):
    out = party_args(config)
    assist = config.get("assist")
    has_feather = any(i["id"] == "spirit_feather" and i["count"] > 0 for i in config["items"])
    if assist and (assist["random"] or assist.get("rescue") or has_feather):
        a = story_data.ASSIST
        out["assist_images"] = {"sky": story_assets.image_uri(f"skills/{a['image']}"),
                                "skill": story_assets.image_uri(f"skills/{a['skill_image']}")}
    skill_scene = (config.get("skill") or {}).get("scene")
    if skill_scene:
        out["skill_scene_image"] = story_assets.image_uri(f"skills/{skill_scene['image']}")
    return out


def _battle_kz(config, key):
    kz = kz_args(config)
    return _component(
        config=config,
        scene_css=story_assets.SCENE_CSS,
        hit_mask=kz["hit_masks"][0],
        ally_icon=story_assets.ally_icon_uri(config["ally"]["lv"]),
        item_icons={item["id"]: story_assets.item_thumb(item["id"], 192) for item in config["items"]},
        equip_icons={e["id"]: story_assets.equipment_thumb(e["id"]) for part in ("gear", "acc") for e in config["loadout"][part]},
        status_icons={sid: uri for sid in story_data.STATUS_EFFECTS if (uri := story_assets.status_icon_uri(sid))},
        **_common_args(config), **kz,
        key=key,
        default=None,
    )
