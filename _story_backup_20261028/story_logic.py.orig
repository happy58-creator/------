"""ストーリーモードの計算（Streamlit に依存しない純粋な関数だけ）

ダメージの式はここだけに書く。ブラウザ側の戦闘画面には、ここで計算した
「1タップのダメージ」「敵の1回の攻撃のダメージ」「状態異常のダメージ」などの数字を渡すので、
式が2か所に分かれない。

プロフィール（ユーザーごとの保存データ）と挑戦（run）は、JSON にそのまま変換できる dict。
ここの関数はそれを書きかえるだけで、保存は story_profile がする。

    プロフィール = {
        "allies": [1, ...],                    仲間になったキャラの Lv
        "ability": {"1": 1.5, ...},           キャラごとのアビリティポイントの累計
        "equipment": [{"uid": 1, "id": "wood_sword"}, ...],   倉庫（1つずつ番号つき）
        "next_uid": 2,
        "equipped": {"1": [1, ...]},          キャラごとに付けている装備の番号（3つまで）
        "items": {"potion": 3, ...},          ホームのアイテム
        "run": 挑戦 or None,                   進行中の挑戦
        "suspended": 挑戦 or None,             中断セーブ（1つだけ）
    }
    挑戦 = {"id", "ally", "difficulty", "stage"（次に戦うステージ）, "hp", "cleared",
            "bag": {"carried": {...}, "picked": {...}}}
"""
import random
import secrets

import story_data


def get_difficulty(difficulty_id):
    return next(d for d in story_data.DIFFICULTIES if d["id"] == difficulty_id)


def get_enemy(lv):
    return next(e for e in story_data.ENEMIES if e["lv"] == lv)


def get_ally(lv):
    return next(a for a in story_data.ALLIES if a["lv"] == lv)


def get_item(item_id):
    return next(i for i in story_data.ITEMS if i["id"] == item_id)


def get_equipment(equip_id):
    return next(e for e in story_data.EQUIPMENT if e["id"] == equip_id)


def at_least(difficulty_id, min_difficulty_id):
    """difficulty_id が min_difficulty_id「以上」か（表の上からの順で判定）"""
    return get_difficulty(difficulty_id)["rank"] >= get_difficulty(min_difficulty_id)["rank"]


# ---------------------------------------------------------------------------
# ダメージ
# ---------------------------------------------------------------------------
def reduction(defense):
    """防御力から軽減率を出す： 防御 ÷ (防御 + K)"""
    defense = max(0.0, float(defense))
    return defense / (defense + story_data.DEFENSE_K)


def damage(attack, defense):
    """攻撃力 attack の攻撃が、防御力 defense の相手に与えるダメージ"""
    return float(attack) * (1.0 - reduction(defense))


def enemy_stats(lv, difficulty_id):
    """難易度の倍率をかけた敵のステータス"""
    enemy = get_enemy(lv)
    difficulty = get_difficulty(difficulty_id)
    return {
        "hp": enemy["hp"] * difficulty["enemy_hp_atk"],
        "atk": enemy["atk"] * difficulty["enemy_hp_atk"],
        "def": enemy["def"] * difficulty["enemy_def"],
    }


def display_hp(hp):
    """画面に出すHP。四捨五入した整数で、生きている間は最低1と表示する"""
    if hp <= 0:
        return 0
    return max(1, int(hp + 0.5))


# ---------------------------------------------------------------------------
# プロフィール
# ---------------------------------------------------------------------------
def new_profile():
    return {
        "allies": [1],
        "ability": {},
        "equipment": [],
        "next_uid": 1,
        "equipped": {},
        "items": {},
        "run": None,
        "suspended": None,
    }


def normalize_profile(data):
    """読みこんだデータに足りない項目を補う（古い形のデータでも動くように）"""
    profile = new_profile()
    if isinstance(data, dict):
        profile.update({k: v for k, v in data.items() if k in profile})
    if 1 not in profile["allies"]:
        profile["allies"].insert(0, 1)
    return profile


def owned_allies(profile):
    return sorted(set(profile["allies"]))


# ---------------------------------------------------------------------------
# アビリティ（ポイントは 0.01 = 1 の整数）
# ---------------------------------------------------------------------------
def ability_points(profile, ally_lv):
    return float(profile["ability"].get(str(ally_lv), 0))


def ability_gain(cleared, difficulty_id):
    """クリアしたステージ数 × 0.1 × 倍率"""
    return cleared * story_data.ABILITY_POINT_PER_STAGE * get_difficulty(difficulty_id)["ability"]


def unlocked_abilities(ally_lv, points):
    """解放済みのアビリティ"""
    abilities = get_ally(ally_lv)["abilities"]
    return [a for a, need in zip(abilities, story_data.ABILITY_THRESHOLDS) if points >= need]


def ability_gauges(points):
    """アビリティ3つぶんの進み具合（0.0〜1.0）。前のしきい値から次のしきい値までで測る"""
    gauges, low = [], 0
    for high in story_data.ABILITY_THRESHOLDS:
        gauges.append(min(1.0, max(0.0, (points - low) / (high - low))))
        low = high
    return gauges


# ---------------------------------------------------------------------------
# 装備
# ---------------------------------------------------------------------------
def equipped_uids(profile, ally_lv):
    return list(profile["equipped"].get(str(ally_lv), []))


def equipment_by_uid(profile):
    return {e["uid"]: e for e in profile["equipment"]}


def equipped_items(profile, ally_lv):
    """キャラが付けている装備のデータ（story_data.EQUIPMENT の行）"""
    by_uid = equipment_by_uid(profile)
    return [get_equipment(by_uid[u]["id"]) for u in equipped_uids(profile, ally_lv) if u in by_uid]


def equip_choices(profile, ally_lv):
    """このキャラが付けられる装備（ほかのキャラが付けていない物）の uid 一覧"""
    used_by_others = {
        uid for lv, uids in profile["equipped"].items() if lv != str(ally_lv) for uid in uids
    }
    return [e["uid"] for e in profile["equipment"] if e["uid"] not in used_by_others]


def set_equipment(profile, ally_lv, uids):
    """装備を付けかえる。ルールに合わなければ ValueError（メッセージは画面に出せる文）"""
    uids = list(dict.fromkeys(uids))
    if len(uids) > story_data.MAX_EQUIP_SLOTS:
        raise ValueError(f"装備は {story_data.MAX_EQUIP_SLOTS}つまでだよ。")
    allowed = set(equip_choices(profile, ally_lv))
    if any(u not in allowed for u in uids):
        raise ValueError("ほかのキャラが付けている装備は付けられないよ。")
    by_uid = equipment_by_uid(profile)
    kinds = [by_uid[u]["id"] for u in uids]
    if len(kinds) != len(set(kinds)):
        raise ValueError("同じ装備を2つ付けることはできないよ。")
    profile["equipped"][str(ally_lv)] = uids


def add_equipment(profile, equip_id):
    uid = profile["next_uid"]
    profile["equipment"].append({"uid": uid, "id": equip_id})
    profile["next_uid"] = uid + 1
    return uid


# ---------------------------------------------------------------------------
# 味方のステータス（基本 + アビリティ + 装備）
# ---------------------------------------------------------------------------
def ally_stats(lv, profile=None):
    ally = get_ally(lv)
    stats = {"hp": float(ally["hp"]), "atk": float(ally["atk"]), "def": float(ally["def"]), "resist": []}
    if profile is None:
        return stats
    for ability in unlocked_abilities(lv, ability_points(profile, lv)):
        stats[ability["stat"]] += ability["value"]
    for equip in equipped_items(profile, lv):
        for stat in ("hp", "atk", "def"):
            stats[stat] += equip[stat]
        if equip["resist"]:
            stats["resist"].append(equip["resist"])
    return stats


# ---------------------------------------------------------------------------
# かばん（持ち込んだ分 / 拾った分）
# ---------------------------------------------------------------------------
def new_bag(carried=None):
    return {"carried": {k: v for k, v in (carried or {}).items() if v > 0}, "picked": {}}


def bag_counts(bag):
    counts = {}
    for part in ("carried", "picked"):
        for item_id, n in bag[part].items():
            counts[item_id] = counts.get(item_id, 0) + n
    return {k: v for k, v in counts.items() if v > 0}


def bag_total(bag):
    return sum(bag_counts(bag).values())


def take_from_bag(bag, item_id, count=1):
    """かばんから使う。持ち込んだ分から先に減らす。足りなければ ValueError"""
    if bag_counts(bag).get(item_id, 0) < count:
        raise ValueError("そのアイテムはもうないよ。")
    for part in ("carried", "picked"):
        have = bag[part].get(item_id, 0)
        used = min(have, count)
        if used:
            bag[part][item_id] = have - used
            if not bag[part][item_id]:
                del bag[part][item_id]
            count -= used


def put_picked(profile, bag, item_id):
    """拾ったアイテムをかばんに入れる。30個をこえる分はホームに送る。かばんに入ったら True"""
    if bag_total(bag) < story_data.MAX_CARRY_ITEMS:
        bag["picked"][item_id] = bag["picked"].get(item_id, 0) + 1
        return True
    profile["items"][item_id] = profile["items"].get(item_id, 0) + 1
    return False


def heal(hp, max_hp, item):
    return min(max_hp, hp + max_hp * item["heal_rate"])


# ---------------------------------------------------------------------------
# 挑戦の始まりと終わり
# ---------------------------------------------------------------------------
def start_run(profile, ally_lv, difficulty_id, carried):
    """ホームのアイテムを持ち込んで、ステージ1から挑戦を始める"""
    if ally_lv not in owned_allies(profile):
        raise ValueError("まだ仲間になっていないキャラだよ。")
    carried = {k: int(v) for k, v in carried.items() if int(v) > 0}
    if sum(carried.values()) > story_data.MAX_CARRY_ITEMS:
        raise ValueError(f"持っていけるアイテムは {story_data.MAX_CARRY_ITEMS}個までだよ。")
    for item_id, n in carried.items():
        if profile["items"].get(item_id, 0) < n:
            raise ValueError("ホームにあるより多くは持っていけないよ。")
    for item_id, n in carried.items():
        profile["items"][item_id] -= n
    get_difficulty(difficulty_id)
    run = {
        "id": secrets.token_hex(6),
        "ally": ally_lv,
        "difficulty": difficulty_id,
        "stage": 1,
        "hp": ally_stats(ally_lv, profile)["hp"],
        "cleared": 0,
        "bag": new_bag(carried),
    }
    profile["run"] = run
    return run


def roll_treasure(stage, difficulty_id, rng=random):
    """宝箱の中身。[("item", id) / ("equip", id), ...]（宝箱が出なければ空）"""
    if rng.random() >= story_data.TREASURE_CHANCE:
        return []
    found = []
    for _ in range(rng.randint(*story_data.TREASURE_COUNT)):
        if rng.random() < story_data.TREASURE_ITEM_RATE:
            items = story_data.ITEMS
            found.append(("item", rng.choices([i["id"] for i in items], [i["weight"] for i in items])[0]))
        else:
            ranks = [
                rank for rank, cond in story_data.EQUIP_RANKS.items()
                if stage >= cond["min_stage"] and at_least(difficulty_id, cond["min_difficulty"])
            ]
            rank = rng.choices(ranks, [story_data.EQUIP_RANKS[r]["weight"] for r in ranks])[0]
            found.append(("equip", rng.choice([e["id"] for e in story_data.EQUIPMENT if e["rank"] == rank])))
    return found


def roll_unlocks(profile, stage, difficulty_id, rng=random):
    """このクリアで仲間になるキャラの Lv（キャラごとに別々に抽選）"""
    owned = set(profile["allies"])
    joined = []
    for ally in story_data.ALLIES:
        cond = ally["unlock"]
        if ally["lv"] in owned or not cond or cond["stage"] != stage:
            continue
        if at_least(difficulty_id, cond["min_difficulty"]) and rng.random() < cond["chance"]:
            joined.append(ally["lv"])
    return joined


def clear_stage(profile, rng=random):
    """ステージをクリアしたときの処理（HP回復・宝箱・仲間入り）。もらった物を返す。

    全クリアなら挑戦も終わらせる（返り値の "finished" に結果が入る）。
    """
    run = profile["run"]
    stage = run["stage"]
    max_hp = ally_stats(run["ally"], profile)["hp"]
    run["cleared"] += 1
    run["stage"] += 1
    healed_from = run["hp"]
    run["hp"] = min(max_hp, run["hp"] + max_hp * story_data.STAGE_HEAL_RATE)

    rewards = {"stage": stage, "healed": run["hp"] - healed_from, "items": [], "sent_home": [], "equipment": [],
               "allies": [], "chests": 0, "finished": None}
    treasure = roll_treasure(stage, run["difficulty"], rng)
    rewards["chests"] = len(treasure)
    for kind, thing_id in treasure:
        if kind == "item":
            (rewards["items"] if put_picked(profile, run["bag"], thing_id) else rewards["sent_home"]).append(thing_id)
        else:
            add_equipment(profile, thing_id)
            rewards["equipment"].append(thing_id)
    for lv in roll_unlocks(profile, stage, run["difficulty"], rng):
        profile["allies"].append(lv)
        rewards["allies"].append(lv)
    if run["cleared"] >= story_data.STAGE_COUNT:
        rewards["finished"] = finish_run(profile, "clear")
    return rewards


def finish_run(profile, outcome, run=None):
    """挑戦を終わらせる。outcome は "clear" / "lose" / "quit"。

    持ち込んだ残りは全クリアのときだけホームに戻る。拾った残りはいつもホームに入る。
    アビリティポイントは全クリアと負けのときだけ加える。
    """
    run = run or profile["run"]
    bag = run["bag"]
    returned = dict(bag["picked"])
    if outcome == "clear":
        for item_id, n in bag["carried"].items():
            returned[item_id] = returned.get(item_id, 0) + n
    for item_id, n in returned.items():
        profile["items"][item_id] = profile["items"].get(item_id, 0) + n
    gained = ability_gain(run["cleared"], run["difficulty"]) if outcome in ("clear", "lose") else 0
    key = str(run["ally"])
    before = float(profile["ability"].get(key, 0))
    # 0.1 を足し続けて 4.9999… になり、5 に届かないことがないよう、小数第2位で丸める
    profile["ability"][key] = round(before + gained, 2)
    if profile.get("run") is run:
        profile["run"] = None
    return {
        "outcome": outcome, "ally": run["ally"], "difficulty": run["difficulty"], "cleared": run["cleared"],
        "returned": returned, "lost": {} if outcome == "clear" else dict(bag["carried"]),
        "ability_before": before, "ability_after": profile["ability"][key],
        "new_abilities": len(unlocked_abilities(run["ally"], profile["ability"][key])) - len(unlocked_abilities(run["ally"], before)),
    }


def suspend_run(profile):
    """中断セーブ（ステージ間の画面でだけ呼ぶ）"""
    profile["suspended"] = profile["run"]
    profile["run"] = None


def resume_run(profile):
    """中断セーブから再開する。セーブは消える"""
    profile["run"] = profile["suspended"]
    profile["suspended"] = None
    return profile["run"]


def drop_suspended(profile):
    """中断セーブを消して、その挑戦を「やめた」扱いで終わらせる"""
    run = profile["suspended"]
    profile["suspended"] = None
    return finish_run(profile, "quit", run=run) if run else None


# ---------------------------------------------------------------------------
# 戦闘コンポーネントに渡す設定
# ---------------------------------------------------------------------------
def battle_config(round_id, enemy_lv, difficulty_id, ally_lv, ally_hp=None, profile=None, bag=None):
    """戦闘コンポーネントに渡す設定（JSON にそのまま変換できる dict）

    ally_hp を渡すと、そのHPから戦闘を始める（ステージをまたいだHPの引き継ぎ用）。
    profile を渡すと、アビリティと装備の補正を入れる。bag を渡すと、戦闘中に使えるアイテムを入れる。
    """
    enemy = enemy_stats(enemy_lv, difficulty_id)
    ally = ally_stats(ally_lv, profile)
    max_hp = ally["hp"]
    resist = set(ally["resist"])
    effects = story_data.STATUS_EFFECTS
    gimmicks = get_enemy(enemy_lv)["gimmicks"]

    def rate(status_id):
        return story_data.RESIST_RATE if status_id in resist else 1.0

    def dot(status_id, defense):
        effect = effects[status_id]
        amount = max_hp * effect["max_hp_rate"] * rate(status_id)
        return amount * (1.0 - reduction(defense)) if effect["defense_applies"] else amount

    guard_def = ally["def"] * story_data.GUARD_MULTIPLIER
    status = {}
    for status_id in ("poison", "fire", "black_flame"):
        status[status_id] = {
            "name": effects[status_id]["name"], "icon": effects[status_id]["icon"], "turns": effects[status_id]["turns"],
            "damage": dot(status_id, ally["def"]), "damage_guard": dot(status_id, guard_def),
        }
    thunder = effects["thunder"]
    status["thunder"] = {"name": thunder["name"], "icon": thunder["icon"], "turns_min": thunder["turns_min"],
                         "turns_max": thunder["turns_max"], "halve": "thunder" in resist}

    counts = bag_counts(bag) if bag else {}
    items = [
        {"id": i["id"], "name": i["name"], "icon": i["icon"], "count": counts.get(i["id"], 0),
         "heal": max_hp * i["heal_rate"], "cure": i["cure"], "guard": i["guard"]}
        for i in story_data.ITEMS
    ]
    return {
        "round": round_id,
        "stage": enemy_lv,
        "stage_count": story_data.STAGE_COUNT,
        "enemy": {
            "lv": enemy_lv,
            "name": get_enemy(enemy_lv)["name"],
            "max_hp": enemy["hp"],
            "atk": enemy["atk"],
            "def": enemy["def"],
            "hit_damage": damage(enemy["atk"], ally["def"]),            # 敵の1回の攻撃で味方が受けるダメージ
            "hit_damage_guard": damage(enemy["atk"], guard_def),        # 防御アップ中
            "gimmicks": [g for g in gimmicks if g != "meteor"],          # 攻撃のたびに抽選する状態異常
            "meteor": "meteor" in gimmicks,
        },
        "ally": {
            "lv": ally_lv,
            "name": get_ally(ally_lv)["name"],
            "max_hp": max_hp,
            "hp": max_hp if ally_hp is None else float(ally_hp),
            "atk": ally["atk"],
            "def": ally["def"],
            "tap_damage": damage(ally["atk"], enemy["def"]),     # 1タップで敵に与えるダメージ
        },
        "status": status,
        "status_chance": story_data.STATUS_CHANCE,
        "meteor": {"trigger_rate": story_data.METEOR_TRIGGER_HP_RATE,
                   "current_hp_rate": effects["meteor"]["current_hp_rate"]},
        "items": items,
        "turn_ms": int(story_data.TURN_SECONDS * 1000),
        "countdown": 3,
    }
