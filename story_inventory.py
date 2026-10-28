"""倉庫とリュックの画面（ブラウザ側で入れ替えて、「決定」で Python に返す）

左に倉庫（アイテムと装備）、右にリュック・装備品・アクセサリの3つの箱。
アイコンをドラッグして入れ替え、クリックで下に効果を出す。削除・ロック・決定ボタンがある。
「決定」で次の dict を返す（story_logic.apply_inventory にそのまま渡せる）。

    {"round": 番号, "action": "save",
     "store": {アイテムID: 個数}, "pack": {アイテムID: 個数},
     "gear": [uid, ...], "acc": [uid, ...], "deleted": [uid, ...], "locked": [uid, ...]}

「もどる」は {"round": 番号, "action": "cancel"}。画面を開いているあいだは None。
"""
from pathlib import Path

import streamlit.components.v1 as components

import story_assets
import story_data
import story_logic as L

_component = components.declare_component(
    "story_inventory", path=str(Path(__file__).resolve().parent / "web" / "story_inventory")
)

STAT_NAMES = {"hp": "HP", "atk": "攻撃力", "def": "防御力"}


def equip_effect(equip):
    if equip["resist"]:
        return f"{story_data.STATUS_EFFECTS[equip['resist']]['name']}を半分にする"
    return "・".join(f"{STAT_NAMES[s]}+{equip[s]:g}" for s in ("hp", "atk", "def") if equip[s])


ATTR_TEXT = {
    "poison": "当たった攻撃のダメージの半分くらいを、しばらく毎ターン与える",
    "fire": "当たった攻撃のダメージの7割を、3ターン与える",
    "black_flame": "当たった攻撃のダメージの6割を3ターン、そのあと少しずつ長く与える",
    "thunder": "敵を1〜2ターン動けなくする（強い敵には効かないことも）",
    "darkness": "敵の次の攻撃を弱める",
    "shadow": "敵の攻撃をよけやすくなる（2回分）",
}


def item_effect(item):
    parts = []
    if item["heal_rate"] >= 1:
        parts.append("HPを全回復")
    elif item["heal_rate"]:
        parts.append(f"最大HPの{item['heal_rate']:.0%}を回復")
    if item["cure"]:
        parts.append("状態異常を治す")
    if item["guard"]:
        parts.append(f"{item['guard']}ターン防御力2倍")
    if item["atk_bonus"]:
        parts.append(f"自分の攻撃{item['atk_turns']}回ぶん攻撃力+{item['atk_bonus']}")
    return "・".join(parts)


def inventory_config(profile, ally_lv, round_id):
    """コンポーネントに渡す設定"""
    store = {k: int(v) for k, v in profile["items"].items() if int(v) > 0}
    pack = L.pack_counts(profile)
    items = [
        {"id": i["id"], "name": i["name"], "icon": story_assets.item_thumb(i["id"]),
         "effect": item_effect(i), "store": store.get(i["id"], 0), "pack": pack.get(i["id"], 0)}
        for i in story_data.ITEMS
    ]
    owners = {u: int(lv) for lv, uids in profile["equipped"].items() for u in uids}
    gear, acc = L.split_equipped(profile, ally_lv)
    statuses = story_data.STATUS_EFFECTS
    equipment = []
    order = {e["id"]: n for n, e in enumerate(story_data.EQUIPMENT)}
    for entry in sorted(profile["equipment"], key=lambda e: (order[e["id"]], e["uid"])):
        equip = L.get_equipment(entry["id"])
        owner = owners.get(entry["uid"])
        attrs = entry.get("attrs") or {}
        equipment.append({
            "uid": entry["uid"], "id": entry["id"], "name": equip["name"],
            "rank": story_data.EQUIP_RANKS[equip["rank"]]["name"], "ultra": equip["rank"] == "ultra",
            "accessory": L.is_accessory(entry["id"]), "icon": story_assets.equipment_thumb(entry["id"]),
            "effect": equip_effect(equip),
            "attrs": [{"id": a, "name": statuses[a]["name"], "icon": story_assets.status_thumb(a),
                       "chance": round(c * 100), "text": ATTR_TEXT[a]} for a, c in attrs.items()],
            "place": "gear" if entry["uid"] in gear else "acc" if entry["uid"] in acc else "store",
            "other": L.short_name(owner) if owner is not None and owner != ally_lv else None,
            "locked": entry["uid"] in profile["locked"],
        })
    return {
        "round": round_id,
        "ally": L.short_name(ally_lv),
        "in_run": bool(profile["run"]),
        "items": items,
        "equipment": equipment,
        "limits": {"pack": story_data.MAX_CARRY_ITEMS, "gear": story_data.MAX_GEAR_SLOTS,
                   "acc": story_data.MAX_ACCESSORY_SLOTS, "attr_weapons": story_data.MAX_ATTR_WEAPONS},
    }


def inventory(profile, ally_lv, round_id, key):
    return _component(config=inventory_config(profile, ally_lv, round_id), key=key, default=None)
