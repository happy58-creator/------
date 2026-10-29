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
        "items": {"potion": 3, ...},          倉庫（ホーム）のアイテム
        "pack": {"potion": 5, ...},           リュック（挑戦していないとき。次の挑戦に持っていく分）
        "locked": [3, ...],                   ロックした装備の番号（削除できない）
        "run": 挑戦 or None,                   進行中の挑戦（自動で保存。手動の中断セーブはない）
        "starter_items": True,                最初のアイテム（全種類10個）を受け取ったか
    }
    挑戦中のリュックは、挑戦の "bag"（下）を使う。
    挑戦 = {"id", "ally", "difficulty",
            "stage"（次に戦うステージ番号）, "extra"（次の戦いがエクストラなら True）,
            "hp", "bag": {"carried": {...}, "picked": {...}}（いまのHPとかばん）,
            "checkpoint": {"hp", "bag"}（そのステージを始めたときのHPとかばん。負けたら・やめたらここに戻る）,
            "cleared"（クリアしたステージ数。エクストラは数えない。やり直しても減らない）,
            "extra_seen", "extra_won"（エクストラが出たか・倒したか）}
"""
import copy
import random
import secrets
from pathlib import Path

import story_data


def get_difficulty(difficulty_id):
    return next(d for d in story_data.DIFFICULTIES if d["id"] == difficulty_id)


EXTRA = "EX"   # エクストラステージを表すステージ番号の代わり


def stages_for(difficulty_id):
    """その難易度で戦う敵を、ステージ順に並べた一覧（イージー・ノーマルは10、ハード・ベリーハードは11）"""
    return [e for e in story_data.ENEMIES if e["difficulties"] is None or difficulty_id in e["difficulties"]]


def stage_count(difficulty_id):
    return len(stages_for(difficulty_id))


def stage_enemy(stage_no, difficulty_id):
    """ステージ番号（1から）と難易度から、その敵を返す。stage_no が EXTRA ならエクストラの敵"""
    if stage_no == EXTRA:
        return story_data.EXTRA_ENEMY
    return stages_for(difficulty_id)[stage_no - 1]


def get_enemy(lv, difficulty_id="easy"):
    """Lv の敵（Lv.11 は難易度で変わるので difficulty_id で選ぶ）"""
    return next(e for e in stages_for(difficulty_id if lv == 11 else "easy") if e["lv"] == lv)


def enemy_key(enemy):
    """敵を区別する名前（画像ファイル名の拡張子なし。例：enemy_11_hard）"""
    return Path(enemy["image"]).stem


def enemy_by_key(key):
    return next(e for e in story_data.ENEMIES + [story_data.EXTRA_ENEMY] if enemy_key(e) == key)


def run_enemy(run):
    """挑戦で次に戦う敵"""
    return stage_enemy(EXTRA if run.get("extra") else run["stage"], run["difficulty"])


def get_ally(lv):
    return next(a for a in story_data.ALLIES if a["lv"] == lv)


def ability_label(ability):
    """アビリティの説明。例：「攻撃力+1」「聖霊の加護（HP+50・毒・雷・火にかからない）」"""
    text = f"{STAT_LABELS[ability['stat']]}+{ability['value']}"
    if ability.get("immune"):
        text += "・" + "・".join(story_data.STATUS_EFFECTS[s]["name"] for s in ability["immune"]) + "にかからない"
    return f"{ability['name']}（{text}）" if ability.get("name") else text


def short_name(lv):
    """キャラの名前だけ（「平凡な農民、コウ」→「コウ」）"""
    return get_ally(lv)["name"].split("、")[-1]


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


def enemy_stats(enemy, difficulty_id):
    """難易度の倍率をかけた敵のステータス。enemy は敵のデータ（Lv の数字でもよい）。

    fixed_stats の敵（エクストラ）は倍率をかけない。
    """
    if not isinstance(enemy, dict):
        enemy = get_enemy(enemy, difficulty_id)
    if enemy.get("fixed_stats"):
        return {"hp": float(enemy["hp"]), "atk": float(enemy["atk"]), "def": float(enemy["def"])}
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
        "items": initial_items(),
        "pack": {},
        "locked": [],
        "defeated": [],          # 倒したことのある敵（攻略で、謎の敵の姿を見せる）
        "cleared_modes": [],     # 全クリアしたことのある難易度
        "titles_seen": [],       # 知らせ済みの称号（新しく手に入れた称号を、挑戦の終わりに知らせる）
        "bonus_day": "",         # ログインボーナスをもらった日（YYYY-MM-DD）
        "rescue_used": False,    # はじめて倒れそうになったときの、アステルの救援を受けたか（前から遊んでいる人も対象）
        "run": None,
        "starter_items": True,
    }


def initial_items():
    """最初にホームに持っているアイテム（いつでも出るアイテムを INITIAL_ITEM_COUNT 個ずつ）"""
    return {item["id"]: story_data.INITIAL_ITEM_COUNT for item in story_data.ITEMS if not item.get("where") and not item.get("special")}


def item_available(item, stage, difficulty_id):
    """そのステージの宝箱から出るアイテムか（where の条件）"""
    if item.get("special"):
        return False
    where = item.get("where")
    return not where or (difficulty_id in where and stage >= where[difficulty_id])


def equip_bonus(entry):
    """倉庫の装備1つぶんの上がり方 {"hp", "atk", "def"}（ランダムのアクセサリは、決まった数値が足される）"""
    equip = get_equipment(entry["id"])
    stats = {stat: equip[stat] for stat in ("hp", "atk", "def")}
    for stat, value in (entry.get("bonus") or {}).items():
        stats[stat] += value
    return stats


STAT_LABELS = {"hp": "HP", "atk": "攻撃力", "def": "防御力"}


def equip_effect_text(entry_or_id):
    """装備の効果の文（倉庫の1件を渡すと、ランダムのアクセサリは決まった数値で書く）"""
    entry = entry_or_id if isinstance(entry_or_id, dict) else {"id": entry_or_id}
    equip = get_equipment(entry["id"])
    if equip["resist"]:
        return f"{story_data.STATUS_EFFECTS[equip['resist']]['name']}を半分にする"
    if equip.get("roll") and not entry.get("bonus"):
        roll = equip["roll"]
        return f"{STAT_LABELS[roll['stat']]}+{roll['min']}〜{roll['max']}（手に入れたときに決まる）"
    stats = equip_bonus(entry)
    return "・".join(f"{STAT_LABELS[st]}+{stats[st]:g}" for st in ("hp", "atk", "def") if stats[st])


def item_effect_text(item):
    if item.get("home_use") == "level_up":
        return "ホームの「倉庫とリュック」で使うと、いまのキャラのレベルが1上がる"
    if item.get("assist"):
        return ("戦闘で使うとHP全回復・状態異常をすべて治し、その戦闘のあいだ精霊の加護（毒・雷・火にかからない）。"
                "さらにアステルが援護に来る。倒れそうになったときにも使える")
    parts = []
    if item["heal_rate"] >= 1:
        parts.append("HPを全回復")
    elif item["heal_rate"]:
        parts.append(f"最大HPの{item['heal_rate']:.0%}を回復")
    if item.get("ward"):
        parts.append(f"{item['ward']}ターン黒炎にかからない（かかっている黒炎は続く）")
    if item["cure"]:
        parts.append("・".join(story_data.STATUS_EFFECTS[c]["name"] for c in item["cure"]) + "を治す")
    if item["guard"]:
        parts.append(f"{item['guard']}ターン防御力2倍")
    if item["atk_bonus"]:
        parts.append(f"自分の攻撃{item['atk_turns']}回ぶん攻撃力+{item['atk_bonus']}")
    return "・".join(parts)


def roll_charm_value(roll, stage, count, rng=random):
    """ランダムのアクセサリの数値。範囲 min〜max の中で、ステージの後半ほど高めに出る"""
    t = (stage - 1) / max(1, count - 1)
    u = 0.6 * min(1.0, max(0.0, t)) + 0.4 * rng.random()
    return roll["min"] + round((roll["max"] - roll["min"]) * u)


def normalize_run(run):
    """古い形の挑戦データに、新しい項目を補う"""
    if not isinstance(run, dict):
        return None
    run.setdefault("extra", False)
    run.setdefault("extra_seen", False)
    run.setdefault("extra_won", False)
    run.setdefault("charge", 0)
    run.setdefault("cleared", 0)
    if not run.get("checkpoint"):
        run["checkpoint"] = {"hp": run["hp"], "bag": copy.deepcopy(run["bag"]), "charge": run.get("charge", 0)}
    return run


def normalize_profile(data):
    """読みこんだデータに足りない項目を補う（古い形のデータでも動くように）

    - 前の版の「中断セーブ」（suspended）は、そのまま進行中の挑戦に移す
    - 最初のアイテムをまだ受け取っていなければ、全種類 INITIAL_ITEM_COUNT 個までふやす
    """
    profile = new_profile()
    if isinstance(data, dict):
        profile["starter_items"] = False
        profile.update({k: v for k, v in data.items() if k in profile})
        if not profile["run"] and data.get("suspended"):
            profile["run"] = data["suspended"]
    if not profile["starter_items"]:
        for item_id, n in initial_items().items():
            profile["items"][item_id] = max(n, profile["items"].get(item_id, 0))
        profile["starter_items"] = True
    if isinstance(data, dict) and "titles_seen" not in data:
        profile["titles_seen"] = None     # 称号ができる前のデータ：ページ側で、前の記録から全クリアを拾ってから決める
    profile["run"] = normalize_run(profile["run"])
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


def is_accessory(equip_id):
    return get_equipment(equip_id)["rank"] in story_data.ACCESSORY_RANKS


def equip_choices(profile, ally_lv, accessory=None):
    """このキャラが付けられる装備（ほかのキャラが付けていない物）の uid 一覧。

    accessory=True ならアクセサリだけ、False なら装備品だけ、None なら両方。
    """
    used_by_others = {
        uid for lv, uids in profile["equipped"].items() if lv != str(ally_lv) for uid in uids
    }
    return [
        e["uid"] for e in profile["equipment"]
        if e["uid"] not in used_by_others and (accessory is None or is_accessory(e["id"]) == accessory)
    ]


def split_equipped(profile, ally_lv):
    """付けている装備を (装備品の uid 一覧, アクセサリの uid 一覧) に分ける"""
    by_uid = equipment_by_uid(profile)
    uids = [u for u in equipped_uids(profile, ally_lv) if u in by_uid]
    accessories = [u for u in uids if is_accessory(by_uid[u]["id"])]
    return [u for u in uids if u not in accessories], accessories


def set_equipment(profile, ally_lv, uids):
    """装備を付けかえる（装備品とアクセサリをまとめて渡す）。ルールに合わなければ ValueError（画面に出せる文）

    - 装備品は3つまで。同じ種類を重ねて付けてよい
    - アクセサリは3つまで。同じ種類は2つ付けられない
    - 属性の付いた剣は MAX_ATTR_WEAPONS 本まで
    - ほかのキャラが付けている装備（番号）は付けられない
    """
    uids = list(dict.fromkeys(uids))
    by_uid = equipment_by_uid(profile)
    if any(u not in by_uid for u in uids):
        raise ValueError("倉庫にない装備は付けられないよ。")
    allowed = set(equip_choices(profile, ally_lv))
    if any(u not in allowed for u in uids):
        raise ValueError("ほかのキャラが付けている装備は付けられないよ。")
    gear = [u for u in uids if not is_accessory(by_uid[u]["id"])]
    accessories = [by_uid[u]["id"] for u in uids if is_accessory(by_uid[u]["id"])]
    if len(gear) > story_data.MAX_GEAR_SLOTS:
        raise ValueError(f"装備品は {story_data.MAX_GEAR_SLOTS}つまでだよ。")
    if len(accessories) > story_data.MAX_ACCESSORY_SLOTS:
        raise ValueError(f"アクセサリは {story_data.MAX_ACCESSORY_SLOTS}つまでだよ。")
    if len(accessories) != len(set(accessories)):
        raise ValueError("同じアクセサリを2つ付けることはできないよ。")
    if sum(1 for u in gear if by_uid[u].get("attrs")) > story_data.MAX_ATTR_WEAPONS:
        raise ValueError("属性の付いた剣は1本だけ付けられるよ。")
    profile["equipped"][str(ally_lv)] = uids


def add_equipment(profile, equip_id, attrs=None, bonus=None):
    """倉庫に装備を1つ入れて、番号（uid）を返す。attrs は剣の属性 {属性ID: 発動率}、bonus はランダムのアクセサリの数値"""
    uid = profile["next_uid"]
    entry = {"uid": uid, "id": equip_id}
    if attrs:
        entry["attrs"] = dict(attrs)
    if bonus:
        entry["bonus"] = dict(bonus)
    profile["equipment"].append(entry)
    profile["next_uid"] = uid + 1
    return uid


# ---------------------------------------------------------------------------
# 剣の属性
#   倉庫の剣には {"attrs": {"poison": 0.23, "fire": 0.23, "black_flame": 0.12}} のように付く。
#   毒・火・雷（ATTR_GROUP）は同じ発動率を共有し、黒炎・陰・影（ATTR_SOLO）はそれぞれの発動率を持つ。
# ---------------------------------------------------------------------------
def attr_pool(difficulty_id):
    """その難易度で剣に付く可能性のある属性"""
    return [
        a for a in story_data.ATTR_GROUP + story_data.ATTR_SOLO
        if a not in story_data.ATTR_MIN_DIFFICULTY or at_least(difficulty_id, story_data.ATTR_MIN_DIFFICULTY[a])
    ]


def roll_weapon_attrs(equip_id, difficulty_id, rng=random):
    """宝箱から出た装備に付く属性 {属性ID: 発動率}。剣でなければ、または付かなければ None"""
    if equip_id not in story_data.SWORDS:
        return None
    if rng.random() >= story_data.WEAPON_ATTR_CHANCE[difficulty_id]:
        return None
    count = rng.choices([1, 2, 3], story_data.WEAPON_ATTR_COUNTS[difficulty_id])[0]
    pool = attr_pool(difficulty_id)
    chosen = []
    while len(chosen) < min(count, len(pool)):
        a = rng.choice([p for p in pool if p not in chosen])
        chosen.append(a)
    attrs = {}
    group = [a for a in chosen if a in story_data.ATTR_GROUP]
    if group:
        chance = round(rng.uniform(*story_data.ATTR_GROUP_CHANCE), 2)
        for a in group:
            attrs[a] = chance
    for a in chosen:
        if a in story_data.ATTR_SOLO:
            attrs[a] = round(rng.uniform(*story_data.ATTR_SOLO_CHANCE), 2)
    return {a: attrs[a] for a in story_data.ATTR_GROUP + story_data.ATTR_SOLO if a in attrs}


# 剣の属性の説明（倉庫の画面と戦闘中の装備の確認で使う）
ATTR_TEXT = {
    "poison": "当たった攻撃のダメージの半分くらいを、しばらく毎ターン与える",
    "fire": "当たった攻撃のダメージの7割を、3ターン与える",
    "black_flame": "当たった攻撃のダメージの6割を3ターン、そのあと少しずつ長く与える",
    "thunder": "敵を1〜2ターン動けなくする（強い敵には効かないことも）",
    "darkness": "敵の次の攻撃を弱める",
    "shadow": "敵の攻撃をよけやすくなる（2回分）",
}


def loadout_config(profile, ally_lv):
    """戦闘中に見る「いまの装備」。付けている装備品・アクセサリ、剣の属性、効かない・半分にする状態異常"""
    effects = story_data.STATUS_EFFECTS
    ally = ally_stats(ally_lv, profile)
    gear, acc = split_equipped(profile, ally_lv) if profile is not None else ([], [])
    by_uid = equipment_by_uid(profile) if profile is not None else {}

    def entry_info(uid):
        entry = by_uid[uid]
        equip = get_equipment(entry["id"])
        attrs = entry.get("attrs") or {}
        group = [a for a in story_data.ATTR_GROUP if a in attrs]
        lines = []
        if group:
            names = "・".join(effects[a]["name"] for a in group)
            lines.append({"ids": group, "chance": round(attrs[group[0]] * 100),
                          "text": f"当たると{round(attrs[group[0]] * 100)}%で{names}" + ("のどれか1つ" if len(group) > 1 else "")})
        for a in story_data.ATTR_SOLO:
            if a in attrs:
                lines.append({"ids": [a], "chance": round(attrs[a] * 100),
                              "text": f"当たると{round(attrs[a] * 100)}%で{effects[a]['name']}：{ATTR_TEXT[a]}"})
        return {"uid": uid, "id": entry["id"], "name": equip["name"], "rank": story_data.EQUIP_RANKS[equip["rank"]]["name"],
                "effect": equip_effect_text(entry), "attrs": lines}

    gear_info = [entry_info(u) for u in gear if u in by_uid]
    acc_info = [entry_info(u) for u in acc if u in by_uid]
    used = {a for e in gear_info + acc_info for line in e["attrs"] for a in line["ids"]}
    return {
        "gear": gear_info,
        "acc": acc_info,
        # 付けている剣に付いている属性の説明
        "attr_help": [{"id": a, "name": effects[a]["name"], "text": ATTR_TEXT[a]}
                      for a in story_data.ATTR_GROUP + story_data.ATTR_SOLO if a in used],
        "resist": [{"id": r, "name": effects[r]["name"]} for r in dict.fromkeys(ally["resist"])],
        "immune": [{"id": r, "name": effects[r]["name"]} for r in ally.get("immune", [])],
        "stats": {"hp": ally["hp"], "atk": ally["atk"], "def": ally["def"]},
    }


def weapon_attr_config(entry):
    """戦闘画面に渡す、剣1本ぶんの属性（なければ None）"""
    attrs = entry.get("attrs") or {}
    group = [a for a in story_data.ATTR_GROUP if a in attrs]
    solo = {a: attrs[a] for a in story_data.ATTR_SOLO if a in attrs}
    if not group and not solo:
        return None
    return {"name": get_equipment(entry["id"])["name"], "group": group,
            "group_chance": attrs[group[0]] if group else 0, "solo": solo}


# ---------------------------------------------------------------------------
# 味方のステータス（基本 + アビリティ + 装備）
# ---------------------------------------------------------------------------
def level_points_max(ally_lv):
    """そのキャラが Lv.10 になるのに要るポイント（コウからルナへ、順番に増える。アステルはルナより少し多い）"""
    low, high = story_data.LEVEL_POINTS
    return low + (high - low) * (ally_lv - 1) / 9


def level_threshold(ally_lv, level):
    """レベル level になるのに要るポイントの合計（曲線で増える）"""
    t = (level - 1) / (story_data.LEVEL_MAX - 1)
    return round(level_points_max(ally_lv) * t ** story_data.LEVEL_CURVE, 2)


def level_of(ally_lv, points):
    level = 1
    while level < story_data.LEVEL_MAX and points + 1e-9 >= level_threshold(ally_lv, level + 1):
        level += 1
    return level


def ally_level(profile, ally_lv):
    return level_of(ally_lv, ability_points(profile, ally_lv)) if profile is not None else 1


def level_progress(ally_lv, points):
    """(レベル, 次のレベルまでの進み具合 0.0〜1.0)。Lv.10 なら 1.0"""
    level = level_of(ally_lv, points)
    if level >= story_data.LEVEL_MAX:
        return level, 1.0
    low, high = level_threshold(ally_lv, level), level_threshold(ally_lv, level + 1)
    return level, max(0.0, min(1.0, (points - low) / (high - low)))


def base_stats(ally_lv, level=1):
    """レベル level のときのステータス（Lv.1 から Lv.10 へ、曲線で上がる）。HPは整数、攻撃・防御は小数第1位"""
    ally = get_ally(ally_lv)
    t = ((level - 1) / (story_data.LEVEL_MAX - 1)) ** story_data.STAT_CURVE
    stats = {}
    for stat in ("hp", "atk", "def"):
        value = ally[stat] + (ally["max"][stat] - ally[stat]) * t
        stats[stat] = float(round(value)) if stat == "hp" else round(value, 1)
    return stats


def ally_stats(lv, profile=None):
    """味方のステータス（レベル + アビリティ + 装備）。profile がなければ Lv.1 の素のステータス"""
    stats = {**base_stats(lv, ally_level(profile, lv)), "resist": [], "immune": []}
    if profile is None:
        return stats
    for ability in unlocked_abilities(lv, ability_points(profile, lv)):
        stats[ability["stat"]] += ability["value"]
        stats["immune"] += [s for s in ability.get("immune", []) if s not in stats["immune"]]
    by_uid = equipment_by_uid(profile)
    for uid in equipped_uids(profile, lv):
        if uid not in by_uid:
            continue
        entry, equip = by_uid[uid], get_equipment(by_uid[uid]["id"])
        for stat, value in equip_bonus(entry).items():
            stats[stat] += value
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
def start_run(profile, ally_lv, difficulty_id, carried=None):
    """ステージ1から挑戦を始める。

    carried を渡さなければ、リュック（profile["pack"]）の中身をそのまま持っていく。
    carried を渡したときは、倉庫からその数を持ち出す。
    """
    if ally_lv not in owned_allies(profile):
        raise ValueError("まだ仲間になっていないキャラだよ。")
    if carried is None:
        carried = {k: int(v) for k, v in profile["pack"].items() if int(v) > 0}
        profile["items"] = {k: profile["items"].get(k, 0) + carried.get(k, 0) for k in set(profile["items"]) | set(carried)}
        profile["pack"] = {}
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
        "extra": False,
        "hp": ally_stats(ally_lv, profile)["hp"],
        "cleared": 0,
        "bag": new_bag(carried),
        "extra_seen": False,
        "extra_won": False,
        "charge": 0,
    }
    profile["run"] = run
    begin_stage(profile)
    return run


def begin_stage(profile):
    """ステージを始めるときのチェックポイント（いまのHPとかばん）を残す"""
    run = profile["run"]
    run["checkpoint"] = {"hp": run["hp"], "bag": copy.deepcopy(run["bag"]), "charge": run.get("charge", 0)}


def restore_checkpoint(profile, used=None):
    """負けたとき・「やめる」で戻ったとき：そのステージを始めたときのHPとチャージに戻す。
    かばんも始めたときに戻すが、戦闘で使ったアイテム（used）は戻らない（チェックポイントからも減らす）"""
    run = profile["run"]
    cp = run["checkpoint"]
    for item_id, n in (used or {}).items():
        n = min(int(n or 0), bag_counts(cp["bag"]).get(item_id, 0))
        if n > 0:
            take_from_bag(cp["bag"], item_id, n)
    run["hp"] = cp["hp"]
    run["bag"] = copy.deepcopy(cp["bag"])
    run["charge"] = cp.get("charge", 0)


def apply_battle(profile, result):
    """戦闘の結果（使ったアイテムと残りHP）を挑戦に反映する"""
    run = profile["run"]
    for item_id, n in (result.get("used") or {}).items():
        try:
            take_from_bag(run["bag"], item_id, int(n))
        except (ValueError, KeyError, TypeError):
            pass
    run["hp"] = max(0.0, float(result.get("ally_hp", run["hp"])))
    if result.get("assist") in ("random", "rescue") and result.get("result") == "win":
        run["assist_drop"] = True                  # アステルがたまたま援護した：クリアすると特別なアイテム
    if "charge" in result:                         # 必殺技のチャージはステージをまたいで残す
        cap = get_ally(run["ally"])["skill"]["charge"]
        run["charge"] = max(0, min(cap, int(result.get("charge") or 0)))


def note_battle(profile, result):
    """戦闘で起きたことを残す（はじめての救援を受けたら、もう出さない）。
    「やめる」で抜けたときは、ステージの最初に戻るので、救援も受けなかったことにする（保留）"""
    if result.get("assist") == "rescue" and result.get("result") != "quit":
        profile["rescue_used"] = True


def skip_extra(profile):
    """エクストラを飛ばして、次のステージへ（「にげる」・負けたあとの「先へ進む」）"""
    profile["run"]["extra"] = False


def roll_treasure(stage, difficulty_id, rng=random):
    """宝箱の中身。[("item", id) / ("equip", id), ...]（宝箱が出なければ空）"""
    if rng.random() >= story_data.TREASURE_CHANCE:
        return []
    found = []
    for _ in range(rng.randint(*story_data.TREASURE_COUNT)):
        if rng.random() < story_data.TREASURE_ITEM_RATE:
            items = [i for i in story_data.ITEMS if item_available(i, stage, difficulty_id)]
            found.append(("item", rng.choices([i["id"] for i in items], [i["weight"] for i in items])[0]))
        else:
            ranks = [
                rank for rank, cond in story_data.EQUIP_RANKS.items()
                if stage >= cond["min_stage"] and at_least(difficulty_id, cond["min_difficulty"])
            ]
            rank = rng.choices(ranks, [story_data.EQUIP_RANKS[r]["weight"] for r in ranks])[0]
            if rank == "charm":     # 強さがランダムなアクセサリ：その難易度の3種類から1つ
                choices = [e for e in story_data.EQUIPMENT if e["rank"] == "charm" and e["roll"]["difficulty"] == difficulty_id]
                equip = rng.choice(choices)
                value = roll_charm_value(equip["roll"], stage, stage_count(difficulty_id), rng)
                found.append(("equip", equip["id"], {equip["roll"]["stat"]: value}))
                continue
            found.append(("equip", rng.choice([
                e["id"] for e in story_data.EQUIPMENT
                if e["rank"] == rank and at_least(difficulty_id, e.get("min_difficulty", "easy"))
            ])))
    return found


def roll_unlocks(profile, stage, difficulty_id, rng=random):
    """このクリアで仲間になるキャラの Lv（キャラごとに別々に抽選）"""
    owned = set(profile["allies"])
    joined = []
    for ally in story_data.ALLIES:
        cond = ally["unlock"]
        if ally["lv"] in owned or not cond or cond.get("extra") or cond["stage"] != stage:
            continue
        if at_least(difficulty_id, cond["min_difficulty"]) and rng.random() < cond["chance"]:
            joined.append(ally["lv"])
    return joined


def clear_stage(profile, rng=random):
    """ステージをクリアしたときの処理。もらった物を返す。

    ふつうのステージ：HP回復・宝箱・仲間入り・（Lv.11 なら）超激レア装備。最後のステージなら挑戦も
    終わらせる（返り値の "finished" に結果が入る）。そうでなければ EXTRA_CHANCE の確率で、次の戦いを
    エクストラにする（1回の挑戦で1度まで）。
    エクストラ：超激レア装備をもらう。回復・宝箱・仲間入りはなく、クリア数にも数えない。
    """
    run = profile["run"]
    rewards = {"stage": run["stage"], "extra": bool(run.get("extra")), "healed": 0, "items": [], "sent_home": [],
               "equipment": [], "equipment_uids": [], "ultra": [], "allies": [], "chests": 0, "finished": None, "extra_next": False}
    enemy = run_enemy(run)
    if enemy_key(enemy) not in profile["defeated"]:
        profile["defeated"].append(enemy_key(enemy))
    ultra = story_data.ULTRA_REWARDS.get(enemy_key(enemy))
    if ultra:
        add_equipment(profile, ultra)
        rewards["ultra"].append(ultra)
    if run.get("extra"):
        run["extra"] = False
        run["extra_won"] = True
        for ally in story_data.ALLIES:          # 宇宙龍を倒すと仲間になるキャラ
            if (ally["unlock"] or {}).get("extra") and ally["lv"] not in profile["allies"]:
                profile["allies"].append(ally["lv"])
                rewards["allies"].append(ally["lv"])
        rewards["enemy"] = enemy_key(enemy)
        return rewards

    stage = run["stage"]
    rewards["enemy"] = enemy_key(enemy)
    max_hp = ally_stats(run["ally"], profile)["hp"]
    run["cleared"] += 1
    run["stage"] += 1
    healed_from = run["hp"]
    run["hp"] = min(max_hp, run["hp"] + max(0.0, max_hp - run["hp"]) * story_data.STAGE_HEAL_RATE)
    rewards["healed"] = run["hp"] - healed_from

    if run.pop("assist_drop", False):
        drop = rng.choice(story_data.ASSIST["drops"])
        rewards["assist_drop"] = drop
        rewards["assist_where"] = "pack" if put_picked(profile, run["bag"], drop) else "store"
    treasure = roll_treasure(stage, run["difficulty"], rng)
    rewards["chests"] = len(treasure)
    for kind, thing_id, *extra in treasure:
        if kind == "item":
            (rewards["items"] if put_picked(profile, run["bag"], thing_id) else rewards["sent_home"]).append(thing_id)
        else:
            bonus = extra[0] if extra else None
            uid = add_equipment(profile, thing_id, roll_weapon_attrs(thing_id, run["difficulty"], rng), bonus)
            rewards["equipment"].append(thing_id)
            rewards["equipment_uids"].append(uid)
    for lv in roll_unlocks(profile, stage, run["difficulty"], rng):
        profile["allies"].append(lv)
        rewards["allies"].append(lv)
    if stage >= stage_count(run["difficulty"]):
        rewards["finished"] = finish_run(profile, "clear")
    else:
        if not run["extra_seen"] and rng.random() < story_data.EXTRA_CHANCE:
            run["extra"] = True
            run["extra_seen"] = True
            rewards["extra_next"] = True
        begin_stage(profile)    # 次のステージのチェックポイント（ステージ間でアイテムを使ったら、戦闘の前にもう一度残す）
    return rewards


def finish_run(profile, outcome, run=None):
    """挑戦を終わらせる。outcome は "clear"（全クリア）/ "abandon"（「新規にプレイ」で終えた）。

    どちらでも、かばんのアイテム（持ち込んだ分も拾った分も）はすべてホームに戻り、
    クリアしたステージ数に応じてアビリティポイントを加える。
    """
    run = run or profile["run"]
    bag = run["bag"]
    returned = {}
    for part in ("carried", "picked"):
        for item_id, n in bag[part].items():
            returned[item_id] = returned.get(item_id, 0) + n
    returned = {k: v for k, v in returned.items() if v > 0}
    for item_id, n in returned.items():
        profile["items"][item_id] = profile["items"].get(item_id, 0) + n
    gained = ability_gain(run["cleared"], run["difficulty"])
    key = str(run["ally"])
    before = float(profile["ability"].get(key, 0))
    # 0.1 を足し続けて 4.9999… になり、5 に届かないことがないよう、小数第2位で丸める
    profile["ability"][key] = round(before + gained, 2)
    if profile.get("run") is run:
        profile["run"] = None
    if outcome == "clear" and run["difficulty"] not in profile["cleared_modes"]:
        profile["cleared_modes"].append(run["difficulty"])
    new_titles = take_new_titles(profile)
    return {
        "outcome": outcome, "ally": run["ally"], "difficulty": run["difficulty"], "cleared": run["cleared"],
        "extra_won": bool(run.get("extra_won")), "returned": returned, "lost": {},
        "ability_before": before, "ability_after": profile["ability"][key],
        "new_abilities": len(unlocked_abilities(run["ally"], profile["ability"][key])) - len(unlocked_abilities(run["ally"], before)),
        "new_titles": new_titles,
    }


# ---------------------------------------------------------------------------
# 称号
# ---------------------------------------------------------------------------
def titles(profile):
    """称号の一覧（モード全クリ4つ → エクストラ → キャラ Lv.10）。earned は手に入れたかどうか"""
    out = []
    cleared = set(profile.get("cleared_modes") or [])
    for diff in story_data.DIFFICULTIES:
        t = story_data.MODE_TITLES[diff["id"]]
        out.append({"id": f"mode_{diff['id']}", "kind": "mode", "name": t["name"], "badge": t["badge"],
                    "how": f"{diff['name']}を全クリアする（{stage_count(diff['id'])}ステージ）", "earned": diff["id"] in cleared})
    t = story_data.EXTRA_TITLE
    out.append({"id": "extra", "kind": "extra", "name": t["name"], "badge": t["badge"],
                "how": "ステージの番人（極点の宇宙龍）を倒す",
                "earned": enemy_key(story_data.EXTRA_ENEMY) in profile.get("defeated", [])})
    for ally in story_data.ALLIES:
        lv = ally["lv"]
        role = ally["name"].split("、")[0]
        out.append({"id": f"ally_{lv}", "kind": "ally", "ally": lv, "name": f"{role}を極めし者",
                    "badge": story_data.ALLY_TITLE_BADGE.format(lv=lv),
                    "how": f"{short_name(lv)}を Lv.{story_data.LEVEL_MAX} にする",
                    "earned": lv in profile["allies"] and ally_level(profile, lv) >= story_data.LEVEL_MAX})
    return out


def take_new_titles(profile):
    """まだ知らせていない、手に入れた称号を返して、知らせ済みにする"""
    if profile.get("titles_seen") is None:
        profile["titles_seen"] = []
    new = [t for t in titles(profile) if t["earned"] and t["id"] not in profile["titles_seen"]]
    profile["titles_seen"] += [t["id"] for t in new]
    return new


def backfill_cleared_modes(profile, history_rows, user):
    """称号ができる前に全クリアしていた難易度を、成績の記録（ストーリー）から拾う。そのあと、いまの称号を知らせ済みにする"""
    names = {d["name"]: d["id"] for d in story_data.DIFFICULTIES}
    for row in history_rows or []:
        if str(row.get("名前")) == user and row.get("結果") == "全クリア":
            diff = names.get(row.get("難易度"))
            if diff and diff not in profile["cleared_modes"]:
                profile["cleared_modes"].append(diff)
    if "enemy_11_veryhard" in profile["defeated"] and "very_hard" not in profile["cleared_modes"]:
        profile["cleared_modes"].append("very_hard")      # 永遠の沈黙はベリーハードの最後の敵
    profile["titles_seen"] = [t["id"] for t in titles(profile) if t["earned"]]


def abandon_run(profile):
    """「新規にプレイ」：いまの挑戦を負け扱いで終わらせる"""
    return finish_run(profile, "abandon")


# ---------------------------------------------------------------------------
# 戦闘コンポーネントに渡す設定
# ---------------------------------------------------------------------------
def assist_config(ally_lv, enemy, extra, rescue=False):
    """アステルの援護（たまたま来る・精霊の羽で呼ぶ）。Lv.10 とアビリティのステータスで、必殺技を撃つ"""
    a = story_data.ASSIST
    helper = get_ally(a["ally"])
    stats = base_stats(a["ally"], a["level"])
    for ability in helper["abilities"]:
        stats[ability["stat"]] += ability["value"]
    skill = helper["skill"]
    raw = stats["atk"] * skill["power"]
    return {
        "random": not extra and ally_lv != a["ally"],     # たまたま来るのは、エクストラ以外・アステル以外のとき
        "rescue": bool(rescue) and not extra,            # はじめて倒れそうになったとき、必ず助けに来る
        "chance": a["chance"], "who": helper["name"], "speaker": short_name(a["ally"]), "name": skill["name"],
        "damage": raw if skill.get("pierce") else damage(raw, enemy["def"]), "damage_break": raw,
        "break_turns": skill.get("break", 0), "scene": skill.get("scene"),
        "immune": [s for ab in helper["abilities"] for s in ab.get("immune", [])],   # 精霊の羽：精霊の加護
    }


def use_home_item(profile, ally_lv, item_id):
    """倉庫のアイテムをホームで使う（白龍の鱗：キャラのレベルを1上げる）。うまくいけば知らせる文、だめなら ValueError"""
    item = get_item(item_id)
    if not item.get("home_use"):
        raise ValueError("このアイテムは戦闘で使うよ。")
    if profile["items"].get(item_id, 0) <= 0:
        raise ValueError("倉庫にないよ。")
    if item["home_use"] == "level_up":
        level = ally_level(profile, ally_lv)
        if level >= story_data.LEVEL_MAX:
            raise ValueError(f"{short_name(ally_lv)} はもうレベルが最大だよ。")
        key = str(ally_lv)
        profile["ability"][key] = max(float(profile["ability"].get(key, 0)), level_threshold(ally_lv, level + 1))
        profile["items"][item_id] -= 1
        if profile["items"][item_id] <= 0:
            del profile["items"][item_id]
        return f"🐉 {item['name']}を使った！ {short_name(ally_lv)} のレベルが {level} → {level + 1} に上がった！"
    raise ValueError("使えないアイテムだよ。")


def awaken_stats():
    """覚醒した宇宙龍の攻撃力・防御力（ベリーハードの最後の敵の stat_rate 倍）"""
    aw = story_data.EXTRA_ENEMY["awaken"]
    last = enemy_stats(stages_for("very_hard")[-1], "very_hard")
    return {"atk": round(last["atk"] * aw["stat_rate"], 1), "def": round(last["def"] * aw["stat_rate"], 1)}


def awaken_config(ally, max_hp, skill):
    """戦闘画面に渡す、覚醒のあとの数字（敵の攻撃・防御が変わるので、ダメージを計算し直しておく）"""
    aw = story_data.EXTRA_ENEMY.get("awaken")
    if not aw:
        return None
    st = awaken_stats()
    guard_def = ally["def"] * story_data.GUARD_MULTIPLIER
    atk_up = max(i["atk_bonus"] for i in story_data.ITEMS)
    out = {
        "hp_rate": aw["hp_rate"], "heal_rate": aw["heal_rate"], "name": aw["name"], "title": aw["title"],
        "lines": aw["lines"], "effect": aw["effect"], "atk": st["atk"], "def": st["def"],
        "hit_damage": damage(st["atk"], ally["def"]), "hit_damage_guard": damage(st["atk"], guard_def),
        "tap_damage": damage(ally["atk"], st["def"]), "tap_damage_up": damage(ally["atk"] + atk_up, st["def"]),
        "special": {k: v for k, v in aw["special"].items() if k != "image"},
    }
    if skill and skill.get("type") == "strike":
        raw = skill["damage_break"]
        out["skill_damage"] = raw if skill.get("pierce") else damage(raw, st["def"])
    return out


def _status_label(status_id):
    effect = story_data.STATUS_EFFECTS[status_id]
    return {"name": effect["name"], "icon": effect["icon"]}


def skill_config(ally_lv, ally, enemy, max_hp, charge=0):
    """戦闘画面に渡す必殺技。ダメージや回復量はここで計算しておく"""
    skill = dict(get_ally(ally_lv)["skill"])
    if skill["type"] == "strike":
        raw = ally["atk"] * skill["power"]
        skill["break_turns"] = skill.get("break", 0)       # 敵の防御を0にするターン数（創世の咆哮）
        skill["damage"] = raw if skill.get("pierce") else damage(raw, enemy["def"])
        skill["damage_break"] = raw                       # 敵の防御が0のとき
    if skill["type"] == "guard":
        skill["heal"] = max_hp * skill["heal_rate"]
    skill["start"] = max(0, min(skill["charge"], int(charge or 0)))
    return skill


def battle_config(round_id, stage_no, difficulty_id, ally_lv, ally_hp=None, profile=None, bag=None, charge=0):
    """戦闘コンポーネントに渡す設定（JSON にそのまま変換できる dict）

    stage_no はステージ番号（1から）か EXTRA。charge は必殺技のチャージ（挑戦の run["charge"]）。
    ally_hp を渡すと、そのHPから戦闘を始める（ステージをまたいだHPの引き継ぎ用）。
    profile を渡すと、アビリティと装備の補正を入れる。bag を渡すと、戦闘中に使えるアイテムを入れる。
    """
    enemy_data = stage_enemy(stage_no, difficulty_id)
    enemy = enemy_stats(enemy_data, difficulty_id)
    ally = ally_stats(ally_lv, profile)
    max_hp = ally["hp"]
    resist = set(ally["resist"])
    effects = story_data.STATUS_EFFECTS
    gimmicks = enemy_data["gimmicks"]

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
    darkness, shadow = effects["darkness"], effects["shadow"]
    status["darkness"] = {"name": darkness["name"], "icon": darkness["icon"], "turns": darkness["turns"],
                          "hit_scale": darkness["resist_hit_scale"] if "darkness" in resist else darkness["hit_scale"]}
    status["shadow"] = {"name": shadow["name"], "icon": shadow["icon"], "turns": shadow["turns"],
                        "evade_rate": shadow["evade_rate"] * rate("shadow")}

    counts = bag_counts(bag) if bag else {}
    items = [
        {"id": i["id"], "name": i["name"], "icon": i["icon"], "count": counts.get(i["id"], 0),
         "heal": max_hp * i["heal_rate"], "cure": list(i["cure"]), "ward": i.get("ward", 0), "guard": i["guard"],
         "atk_turns": i["atk_turns"] if i["atk_bonus"] else 0}
        for i in story_data.ITEMS if not i.get("home_use")
    ]
    for entry in items:                      # 精霊の羽：使うとアステルの援護
        entry["assist"] = bool(get_item(entry["id"]).get("assist"))
    atk_up = max(i["atk_bonus"] for i in story_data.ITEMS)
    weapons = []
    if profile is not None:
        by_uid = equipment_by_uid(profile)
        for uid in equipped_uids(profile, ally_lv):
            if uid in by_uid and (w := weapon_attr_config(by_uid[uid])):
                weapons.append(w)
    immune = enemy_data.get("immune", [])
    fx = story_data.ATTR_EFFECTS
    enemy_status = {
        "poison": {**_status_label("poison"), "dot": fx["poison"]["dot"]},
        "fire": {**_status_label("fire"), "dot": fx["fire"]["dot"]},
        "black_flame": {**_status_label("black_flame"), "dot": fx["black_flame"]["dot"]},
        "thunder": {**_status_label("thunder"), "turns_min": fx["thunder"]["turns_min"],
                    "turns_max": fx["thunder"]["turns_max"], "immune": "thunder" in immune},
        "darkness": {**_status_label("darkness"), "turns": fx["darkness"]["turns"],
                     "damage_min": fx["darkness"]["damage_min"], "damage_max": fx["darkness"]["damage_max"]},
        "shadow": {**_status_label("shadow"), "turns": fx["shadow"]["turns"], "evade_rate": fx["shadow"]["evade_rate"]},
    }
    extra = stage_no == EXTRA
    count = stage_count(difficulty_id)
    return {
        "round": round_id,
        "stage": stage_no,
        "stage_count": count,
        "extra": extra,
        "final": not extra and stage_no == count,
        "enemy": {
            "key": enemy_key(enemy_data),
            "lv": enemy_data["lv"],
            "name": enemy_data["name"],
            "title": enemy_data.get("title", ""),
            "lines": enemy_data["lines"],
            "effect": enemy_data["effect"],
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
            "tap_damage": damage(ally["atk"], enemy["def"]),             # 1タップで敵に与えるダメージ
            "tap_damage_up": damage(ally["atk"] + atk_up, enemy["def"]), # 攻撃力アップ中
            # 概念崩し（敵の防御0）のあいだ
            "tap_damage_break": damage(ally["atk"], 0),
            "immune": ally.get("immune", []),                        # かからない状態異常（聖霊の加護）
            "tap_damage_up_break": damage(ally["atk"] + atk_up, 0),
        },
        "skill": (skill := skill_config(ally_lv, ally, enemy, max_hp, charge)),
        "assist": assist_config(ally_lv, enemy, extra,
                                rescue=profile is not None and not profile.get("rescue_used", False)),   # アステルの援護
        # エクストラ（宇宙龍）だけ：HPが半分を切ると覚醒する
        "awaken": awaken_config(ally, max_hp, skill) if extra else None,
        "status": status,
        "status_chance": story_data.STATUS_CHANCE,
        "weapons": weapons,                  # 付けている剣の属性（攻撃が当たったときに発動の抽選）
        "loadout": loadout_config(profile, ally_lv),   # 戦闘中に「装備」ボタンで見る中身
        "enemy_status": enemy_status,        # 剣の属性で敵にかかる状態異常の数字
        "meteor": {"trigger_rate": story_data.METEOR_TRIGGER_HP_RATE,
                   "current_hp_rate": effects["meteor"]["current_hp_rate"]},
        "items": items,
        "attack_ms": int(story_data.ATTACK_SECONDS * 1000),
        "pause_ms": int(story_data.TURN_PAUSE_SECONDS * 1000),
    }


# ---------------------------------------------------------------------------
# 倉庫とリュック（画面でまとめて入れ替えて、「決定」で反映する）
# ---------------------------------------------------------------------------
def pack_counts(profile):
    """いまのリュックの中身 {アイテムID: 個数}（挑戦中は挑戦のかばん）"""
    if profile["run"]:
        return bag_counts(profile["run"]["bag"])
    return {k: int(v) for k, v in profile["pack"].items() if int(v) > 0}


def delete_equipment(profile, uid):
    """倉庫から装備を捨てる。ロックしている物と、ほかのキャラが付けている物は捨てられない"""
    if uid in profile["locked"]:
        raise ValueError("ロックしている装備は削除できないよ。")
    profile["equipment"] = [e for e in profile["equipment"] if e["uid"] != uid]
    for lv in profile["equipped"]:
        profile["equipped"][lv] = [u for u in profile["equipped"][lv] if u != uid]


def apply_inventory(profile, ally_lv, result):
    """倉庫とリュックの画面の「決定」を反映する。ルールに合わなければ ValueError（何も変えない）

    result = {"store": {アイテムID: 個数}, "pack": {アイテムID: 個数},
              "gear": [uid, ...], "acc": [uid, ...], "deleted": [uid, ...], "locked": [uid, ...]}
    - アイテムは削除できない：倉庫とリュックの合計は、前とまったく同じでないといけない
    - リュックは MAX_CARRY_ITEMS 個まで
    - 装備のルールは set_equipment と同じ。ロックした装備・ほかのキャラが付けている装備は削除できない
    """
    import copy as _copy
    before = _copy.deepcopy(profile)
    try:
        old_pack = pack_counts(profile)
        store = {k: int(v) for k, v in (result.get("store") or {}).items() if int(v) > 0}
        pack = {k: int(v) for k, v in (result.get("pack") or {}).items() if int(v) > 0}
        old_store = {k: int(v) for k, v in profile["items"].items() if int(v) > 0}
        for item_id in set(store) | set(pack) | set(old_store) | set(old_pack):
            get_item(item_id)
            if store.get(item_id, 0) + pack.get(item_id, 0) != old_store.get(item_id, 0) + old_pack.get(item_id, 0):
                raise ValueError("アイテムの数が合わないよ。もう一度ためしてね。")
        if sum(pack.values()) > story_data.MAX_CARRY_ITEMS:
            raise ValueError(f"リュックに入るのは {story_data.MAX_CARRY_ITEMS}個までだよ。")

        locked = [int(u) for u in (result.get("locked") or [])]
        by_uid = equipment_by_uid(profile)
        profile["locked"] = [u for u in dict.fromkeys(locked) if u in by_uid]
        others = {u for lv, uids in profile["equipped"].items() if lv != str(ally_lv) for u in uids}
        for uid in (int(u) for u in (result.get("deleted") or [])):
            if uid not in by_uid:
                continue
            if uid in others:
                raise ValueError("ほかのキャラが付けている装備は削除できないよ。")
            delete_equipment(profile, uid)

        set_equipment(profile, ally_lv, [int(u) for u in (result.get("gear") or [])] + [int(u) for u in (result.get("acc") or [])])

        profile["items"] = store
        if profile["run"]:
            run = profile["run"]
            run["bag"] = {"carried": pack, "picked": {}}
            if run["ally"] == ally_lv:
                run["hp"] = min(run["hp"], ally_stats(ally_lv, profile)["hp"])
        else:
            profile["pack"] = pack
    except Exception:
        profile.clear()
        profile.update(before)
        raise


# ---------------------------------------------------------------------------
# ログインボーナス（その日はじめてストーリーモードを開いたら、アイテムを1つ）
# ---------------------------------------------------------------------------
def daily_bonus(profile, today, rng=random):
    """today（"2026-10-28" など）にまだもらっていなければ、ランダムでアイテムを1つ倉庫に入れて、その ID を返す"""
    if profile.get("bonus_day") == today:
        return None
    items = [i for i in story_data.ITEMS if not i.get("where") and not i.get("special")]
    item_id = rng.choices([i["id"] for i in items], [i["weight"] for i in items])[0]
    profile["items"][item_id] = profile["items"].get(item_id, 0) + 1
    profile["bonus_day"] = today
    return item_id
