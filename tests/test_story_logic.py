"""python -m pytest tests  または  python tests/test_story_logic.py で実行"""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import story_data, story_logic as L


def test_reduction_matches_spec_table():
    for defense, expected in [(1, 0.02), (15, 0.23), (35, 0.41), (70, 0.58)]:
        assert round(L.reduction(defense), 2) == expected


def test_damage_never_negative_and_never_zero_for_positive_attack():
    assert L.damage(1, 10_000) > 0
    assert L.damage(5, 0) == 5


def test_difficulty_multipliers():
    vh = L.enemy_stats(10, "very_hard")
    assert math.isclose(vh["hp"], 3102 * 5.184) and math.isclose(vh["atk"], 12.2 * 5.184) and math.isclose(vh["def"], 19.8 * 3.456)
    extra = L.enemy_stats(story_data.EXTRA_ENEMY, "very_hard")          # エクストラは難易度に関係なく固定
    assert extra == {"hp": 5360, "atk": 21.3, "def": 29.0}           # ベリーハードのステージ6と同じ
    n = L.enemy_stats(1, "normal")
    assert math.isclose(n["hp"], 409.2) and math.isclose(n["def"], 1.782)


def test_display_hp():
    assert L.display_hp(9.02) == 9
    assert L.display_hp(0.3) == 1          # 生きている間は1と表示
    assert L.display_hp(0) == 0 and L.display_hp(-2) == 0


def test_battle_config_lv1():
    c = L.battle_config(1, 1, "easy", 1)
    assert math.isclose(c["ally"]["tap_damage"], 1 * (1 - 1.155 / 51.155))      # イージーは敵が1.155倍
    assert math.isclose(c["enemy"]["hit_damage"], 1.155 * (1 - 1 / 51))
    assert math.isclose(c["ally"]["tap_damage_up"], 4 * (1 - 1.155 / 51.155))   # 攻撃力アップ（+3）中
    assert c["attack_ms"] == 3000 and c["pause_ms"] == 800 and c["ally"]["hp"] == 10
    assert not c["final"] and not c["extra"] and c["stage_count"] == 10
    assert L.battle_config(1, 1, "easy", 1, ally_hp=4.5)["ally"]["hp"] == 4.5


def test_data_tables_consistent():
    assert [e["lv"] for e in story_data.ENEMIES] == list(range(1, 12)) + [11]
    assert [e["lv"] for e in L.stages_for("easy")] == list(range(1, 11))
    assert [L.enemy_key(e) for e in L.stages_for("hard")][-1] == "enemy_11_hard"
    assert [L.enemy_key(e) for e in L.stages_for("very_hard")][-2:] == ["enemy_11_hard", "enemy_11_veryhard"]
    assert [L.stage_count(d) for d in ("easy", "normal", "hard", "very_hard")] == [10, 10, 11, 12]
    assert [a["lv"] for a in story_data.ALLIES] == list(range(1, 12))
    ids = {d["id"] for d in story_data.DIFFICULTIES}
    for a in story_data.ALLIES:
        assert len(a["abilities"]) == len(story_data.ABILITY_THRESHOLDS)
        if a["unlock"] and not a["unlock"].get("extra"):
            assert a["unlock"]["min_difficulty"] in ids
    root = Path(L.__file__).parent / "assets/story"
    for e in story_data.ENEMIES + [story_data.EXTRA_ENEMY]:
        for g in e["gimmicks"]:
            assert g in story_data.STATUS_EFFECTS
        assert (root / "enemies" / e["image"]).exists()
        assert (root / "hitmasks" / f"{L.enemy_key(e)}.png").exists()
        assert len(e["lines"]) == 3
    pending = set()   # 画像待ちのID（届くまでは絵文字のアイコンで表示する）
    for i in story_data.ITEMS:
        assert i["id"] in pending or (root / "items" / f"{i['id']}.webp").exists()
    for eq in story_data.EQUIPMENT:
        assert eq["id"] in pending or (root / "equipment" / f"{eq['id']}.webp").exists()
    for key, equip_id in story_data.ULTRA_REWARDS.items():
        assert L.enemy_by_key(key) and L.get_equipment(equip_id)["rank"] == "ultra"
    for a in story_data.ALLIES:
        for folder in ("allies", "ally_icons"):
            assert (Path(L.__file__).parent / "assets/story" / folder / a["image"]).exists()


class FixedRng:
    """random の代わり。random() は決めた値を順に返す"""
    def __init__(self, values, randint=1):
        self.values, self._randint = list(values), randint
    def random(self):
        return self.values.pop(0)
    def randint(self, a, b):
        return self._randint
    def choices(self, population, weights):
        return [population[0]]
    def choice(self, seq):
        return seq[0]
    def uniform(self, a, b):
        return (a + b) / 2


def profile_with_items(**items):
    p = L.new_profile()
    p["items"] = dict(items)
    return p


def test_ability_points():
    assert math.isclose(L.ability_gain(3, "hard"), 0.6)
    assert math.isclose(L.ability_gain(1, "normal"), 0.15)
    assert math.isclose(L.ability_gain(10, "easy"), 1.0)
    p = L.new_profile()
    for _ in range(50):                             # 1ステージずつ50回でちょうど 5.0 になる
        run = L.start_run(p, 1, "easy", {})
        run["cleared"] = 1
        L.finish_run(p, "abandon")
    assert L.ability_points(p, 1) == 5.0
    assert len(L.unlocked_abilities(1, 4.99)) == 0 and len(L.unlocked_abilities(1, 5.0)) == 1
    assert L.ability_gauges(7.5) == [1.0, 0.5, 0.0]


def test_stats_with_abilities_and_equipment():
    p = L.new_profile()
    p["ability"]["1"] = 10.0                       # アビ1・2（攻撃+1、攻撃+1）
    uid = L.add_equipment(p, "leather_shield")
    L.add_equipment(p, "poison_charm")
    L.set_equipment(p, 1, [uid, 2])
    s = L.ally_stats(1, p)
    assert L.ally_level(p, 1) == 3                 # 10ポイントで Lv.3
    base = L.base_stats(1, 3)
    assert math.isclose(s["atk"], base["atk"] + 2) and math.isclose(s["def"], base["def"] + 2)
    assert s["hp"] == base["hp"] and s["resist"] == ["poison"]


def test_levels_and_growth():
    # Lv.10 に要るポイント：コウはベリーハード全クリア30回分、ルナは50回分
    vh_clear = 12 * story_data.ABILITY_POINT_PER_STAGE * 3
    assert math.isclose(L.level_threshold(1, 10), vh_clear * 30, rel_tol=1e-6)
    assert math.isclose(L.level_threshold(10, 10), vh_clear * 50, rel_tol=1e-6)
    steps = [L.level_threshold(1, n + 1) - L.level_threshold(1, n) for n in range(1, 10)]
    assert steps == sorted(steps) and steps[0] < steps[-1]          # 後のレベルほど多く要る
    assert L.level_of(1, 0) == 1 and L.level_of(1, 108) == 10 and L.level_of(1, 107.9) == 9
    for lv in range(1, 12):
        ally = story_data.ALLIES[lv - 1]
        assert L.base_stats(lv, 1) == {"hp": ally["hp"], "atk": ally["atk"], "def": ally["def"]}
        assert L.base_stats(lv, 10) == ally["max"]
        atk = [L.base_stats(lv, n)["atk"] for n in range(1, 11)]
        assert atk == sorted(atk)
    # コウの Lv.10 は、マリの Lv.10 よりほんの少し弱い
    kou, mari = L.base_stats(1, 10), L.base_stats(2, 10)
    assert kou["atk"] == mari["atk"] and kou["hp"] < mari["hp"] and kou["def"] < mari["def"]
    # 必殺技のチャージは、1ターン50回として、コウ（250）を基準に4ターン分以上
    assert story_data.ALLIES[0]["skill"]["charge"] == 250
    assert all(a["skill"]["charge"] >= 200 for a in story_data.ALLIES)


def test_skill_config_and_charge_carry():
    p = L.new_profile()
    c = L.battle_config(1, 1, "easy", 1, profile=p, charge=50)
    assert c["skill"]["type"] == "strike" and c["skill"]["start"] == 50
    assert math.isclose(c["skill"]["damage"], L.damage(1 * 50, 1.155))
    luna = L.battle_config(1, 12, "very_hard", 10)["skill"]
    assert math.isclose(luna["damage"], 33 * 120)                    # 防御無視
    assert math.isclose(L.battle_config(1, 1, "easy", 2)["skill"]["heal"], 11 * 0.2)
    run = L.start_run(p, 1, "easy", {})
    L.apply_battle(p, {"ally_hp": 10, "charge": 999})
    assert run["charge"] == 250                                       # 上限で止まる
    L.restore_checkpoint(p)
    assert run["charge"] == 0                                         # 負けたらステージ開始時に戻る
    L.apply_battle(p, {"ally_hp": 10, "charge": 80})
    L.clear_stage(p, FixedRng([0.9, 0.5]))
    assert run["charge"] == 80 and run["checkpoint"]["charge"] == 80  # ステージをまたいで残る


def test_equipment_rules():
    p = L.new_profile()
    p["allies"] = [1, 2]
    a = L.add_equipment(p, "wood_sword")
    b = L.add_equipment(p, "wood_sword")
    L.set_equipment(p, 1, [a, b])                  # 装備品は同じ種類を重ねて付けられる
    assert L.ally_stats(1, p)["atk"] == 3
    assert L.equip_choices(p, 2) == []             # コウが2本とも付けているので、マリは使えない
    try:
        L.set_equipment(p, 2, [a])
        assert False
    except ValueError:
        pass
    L.set_equipment(p, 1, [a])
    L.set_equipment(p, 2, [b])
    # 装備品は3つまで
    more = [L.add_equipment(p, "leather_shield") for _ in range(3)]
    try:
        L.set_equipment(p, 1, [a] + more)
        assert False, "装備品を4つ付けられてしまった"
    except ValueError:
        pass
    # アクセサリは装備品と別のわくで3つまで。同じ種類は1つだけ
    c1, c2 = L.add_equipment(p, "poison_charm"), L.add_equipment(p, "poison_charm")
    t, f = L.add_equipment(p, "thunder_ring"), L.add_equipment(p, "fire_bangle")
    L.set_equipment(p, 1, [a] + more[:2] + [c1, t, f])
    gear, acc = L.split_equipped(p, 1)
    assert len(gear) == 3 and len(acc) == 3
    try:
        L.set_equipment(p, 1, [c1, c2])
        assert False, "同じアクセサリを2つ付けられてしまった"
    except ValueError:
        pass
    assert L.equip_choices(p, 2, accessory=True) == [c2]
    assert set(L.equip_choices(p, 2, accessory=False)) == {b, more[2]}


def test_bag_uses_carried_first_and_overflow_goes_home():
    p = profile_with_items(potion=40)
    run = L.start_run(p, 1, "easy", {"potion": 30})
    assert p["items"]["potion"] == 10
    assert L.put_picked(p, run["bag"], "potion") is False and p["items"]["potion"] == 11
    L.take_from_bag(run["bag"], "potion")
    assert L.put_picked(p, run["bag"], "elixir") is True
    run["bag"]["picked"]["potion"] = 2
    L.take_from_bag(run["bag"], "potion", 30)
    assert run["bag"]["carried"] == {} and run["bag"]["picked"] == {"elixir": 1, "potion": 1}


def test_finish_run_returns_everything_and_adds_ability():
    for outcome in ("clear", "abandon"):
        p = profile_with_items(potion=5)
        run = L.start_run(p, 1, "hard", {"potion": 5})
        run["bag"]["picked"] = {"elixir": 2}
        run["cleared"] = 3
        summary = L.finish_run(p, outcome)
        assert p["run"] is None
        assert p["items"]["elixir"] == 2 and p["items"]["potion"] == 5
        assert summary["ability_after"] == 0.6 and summary["lost"] == {}


def test_new_profile_has_starter_items():
    p = L.new_profile()
    assert p["items"] == {i["id"]: 10 for i in story_data.ITEMS if not i.get("where") and not i.get("special")}


def test_clear_stage_heals_rolls_and_saves_rewards():
    p = L.new_profile()
    run = L.start_run(p, 1, "normal", {})
    run["stage"] = 2
    run["hp"] = 1.0
    # 宝箱が出る → 2個 → 1個目アイテム・2個目装備 → マリの抽選に当たる
    rewards = L.clear_stage(p, FixedRng([0.0, 0.0, 0.9, 0.99, 0.1, 0.5], randint=2))   # 剣の属性なし・最後はエクストラの抽選（外れ）
    assert run["hp"] == 5.5 and run["stage"] == 3 and run["cleared"] == 1   # 減ったHP（9）の半分を回復
    assert rewards["items"] == ["potion"] and rewards["equipment"] == ["wood_sword"]
    assert 2 in p["allies"] and rewards["allies"] == [2]
    assert p["equipment"] == [{"uid": 1, "id": "wood_sword"}]
    assert not run["extra"] and not rewards["extra_next"]


def test_unlock_needs_difficulty_and_exact_stage():
    p = L.new_profile()
    assert L.roll_unlocks(p, 2, "easy", FixedRng([0.0] * 10)) == []          # マリはノーマル以上
    assert L.roll_unlocks(p, 5, "very_hard", FixedRng([0.0] * 10)) == [8, 9]  # レイノとガレンは別々に抽選
    assert L.roll_unlocks(p, 5, "hard", FixedRng([0.5, 0.5])) == [8]


def test_treasure_equipment_ranks_follow_stage_and_difficulty():
    import random
    rng = random.Random(1)
    seen = {L.get_equipment(e)["rank"] for _ in range(400)
            for kind, e, *_ in L.roll_treasure(2, "very_hard", rng) if kind == "equip"}
    assert seen == {"normal", "charm"}
    seen = {L.get_equipment(e)["rank"] for _ in range(800)
            for kind, e, *_ in L.roll_treasure(7, "normal", rng) if kind == "equip"}
    assert seen == {"normal", "rare", "epic", "accessory", "charm"}
    seen = {L.get_equipment(e)["rank"] for _ in range(800)
            for kind, e, *_ in L.roll_treasure(9, "easy", rng) if kind == "equip"}
    assert seen == {"normal", "rare", "charm"}


def test_checkpoint_restores_hp_and_bag():
    p = profile_with_items(potion=3)
    run = L.start_run(p, 1, "easy", {"potion": 3})
    L.apply_battle(p, {"ally_hp": 0, "used": {"potion": 2}})
    assert run["hp"] == 0 and L.bag_counts(run["bag"]) == {"potion": 1}
    L.restore_checkpoint(p, {"potion": 2})        # 負けたら、HPはステージを始めたときに戻る。使ったアイテムは戻らない
    assert run["hp"] == 10 and L.bag_counts(run["bag"]) == {"potion": 1}
    assert L.bag_counts(run["checkpoint"]["bag"]) == {"potion": 1}      # やり直しても、使った分は戻らない
    L.restore_checkpoint(p)
    assert L.bag_counts(run["bag"]) == {"potion": 1}
    L.apply_battle(p, {"ally_hp": 4, "used": {}})
    L.clear_stage(p, FixedRng([0.9, 0.5]))       # 宝箱なし・エクストラなし
    assert run["hp"] == 7 and run["checkpoint"]["hp"] == 7   # 減ったHPの半分を回復。次のステージのチェックポイント
    run["hp"] = 10                                # ステージ間でポーションを使った
    L.begin_stage(p)                              # 戦闘の前にもう一度残す
    assert run["checkpoint"]["hp"] == 10


def test_extra_stage_flow():
    p = L.new_profile()
    run = L.start_run(p, 1, "easy", {})
    rewards = L.clear_stage(p, FixedRng([0.9, 0.0]))   # 宝箱なし → エクストラが出る
    assert rewards["extra_next"] and run["extra"] and run["extra_seen"] and run["stage"] == 2
    assert L.run_enemy(run)["name"] == "極点の宇宙龍"
    c = L.battle_config(1, L.EXTRA, "easy", 1)
    assert c["extra"] and not c["final"] and c["enemy"]["gimmicks"] == ["black_flame", "shadow", "darkness"]
    rewards = L.clear_stage(p, FixedRng([]))            # 倒した：回復・宝箱・クリア数なし、逆鱗をもらう
    assert rewards["ultra"] == ["dragon_scale"] and run["cleared"] == 1 and run["stage"] == 2
    assert not run["extra"] and run["extra_won"]
    assert L.clear_stage(p, FixedRng([0.9]))["extra_next"] is False   # 1回の挑戦で1度まで（抽選もしない）


def test_skip_extra():
    p = L.new_profile()
    run = L.start_run(p, 1, "easy", {})
    run["extra"] = run["extra_seen"] = True
    L.skip_extra(p)
    assert not run["extra"] and L.run_enemy(run)["lv"] == 1


def test_final_stage_gives_ultra_and_clears():
    for diff, last, ultra in (("hard", 11, "origin_robe"), ("very_hard", 12, "silence_blade")):
        p = L.new_profile()
        run = L.start_run(p, 1, diff, {})
        run["stage"], run["cleared"] = last, last - 1
        assert L.battle_config(1, last, diff, 1)["final"]
        rewards = L.clear_stage(p, FixedRng([0.99, 0.9] if ultra == "silence_blade" else [0.9]))   # 魔剣は属性の抽選が先
        assert rewards["ultra"] == [ultra] and rewards["finished"]["outcome"] == "clear"
        assert rewards["finished"]["cleared"] == last and p["run"] is None
    # ベリーハードのステージ11は混沌の初源（最後ではない）。倒すと初源の聖衣
    p = L.new_profile()
    run = L.start_run(p, 1, "very_hard", {})
    run["stage"], run["cleared"] = 11, 10
    assert not L.battle_config(1, 11, "very_hard", 1)["final"]
    rewards = L.clear_stage(p, FixedRng([0.9, 0.5]))
    assert rewards["ultra"] == ["origin_robe"] and not rewards["finished"] and run["stage"] == 12
    p = L.new_profile()
    run = L.start_run(p, 1, "easy", {})
    run["stage"] = 10
    assert L.clear_stage(p, FixedRng([0.9]))["finished"]


def test_old_profile_migrates():
    old = {"allies": [1, 2], "items": {"potion": 15}, "run": None,
           "suspended": {"id": "x", "ally": 1, "difficulty": "easy", "stage": 3, "hp": 5.0, "cleared": 2,
                         "bag": {"carried": {}, "picked": {"potion": 1}}}}
    p = L.normalize_profile(old)
    assert p["run"]["stage"] == 3 and p["run"]["checkpoint"]["hp"] == 5.0 and p["run"]["extra"] is False
    assert p["items"]["potion"] == 15 and p["items"]["atk_up"] == 10
    assert "suspended" not in p
    p["items"]["atk_up"] = 0                      # 一度受け取ったら、もう補わない
    assert L.normalize_profile(p)["items"]["atk_up"] == 0


def test_weapon_attrs_roll():
    assert L.roll_weapon_attrs("leather_shield", "very_hard", FixedRng([0.0])) is None   # 剣でなければ付かない
    # 付く確率：難易度ごとの下限〜上限を、ステージの後半ほど曲線で上げる
    assert math.isclose(L.weapon_attr_chance("easy", 1), 0.10) and math.isclose(L.weapon_attr_chance("easy", 10), 0.20)
    assert math.isclose(L.weapon_attr_chance("very_hard", 12), 0.70)
    mid = L.weapon_attr_chance("easy", 5)
    assert 0.10 < mid < 0.10 + (0.20 - 0.10) * 4 / 9                                 # 曲線なので、前半はゆっくり上がる
    assert L.roll_weapon_attrs("wood_sword", "easy", FixedRng([0.15]), stage=1) is None
    a = L.roll_weapon_attrs("wood_sword", "easy", FixedRng([0.05, 0.5]), stage=1)
    assert a == {"poison": 0.03}                                                       # 1〜10% の 0.4×0.5 の位置
    assert L.attr_pool("normal") == ["poison", "fire", "thunder"]                       # 黒炎・陰・影はハード以上
    assert L.attr_pool("hard")[-3:] == ["black_flame", "darkness", "shadow"]
    import random
    rng = random.Random(5)
    counts = {1: 0, 2: 0, 3: 0}
    first, last = [], []
    for _ in range(3000):
        a = L.roll_weapon_attrs("steel_sword", "very_hard", rng, stage=12)
        if not a:
            continue
        counts[len(a)] += 1
        group = {v for k, v in a.items() if k in story_data.ATTR_GROUP}
        assert len(group) <= 1 and all(0.20 <= v <= 0.30 for v in group)              # 毒・火・雷は同じ発動率
        assert all(0.05 <= v <= 0.15 for k, v in a.items() if k in story_data.ATTR_SOLO)
        last += list(group)
    for _ in range(3000):
        a = L.roll_weapon_attrs("steel_sword", "very_hard", rng, stage=1)
        first += [v for k, v in (a or {}).items() if k in story_data.ATTR_GROUP]
    total = sum(counts.values())
    assert 0.66 < total / 3000 < 0.74                                                   # 最後のステージは70%
    assert abs(counts[3] / total - 0.40) < 0.04                                         # 後半は 25/35/40
    assert sum(last) / len(last) > sum(first) / len(first) + 0.03                      # 後半ほど発動率が高い


def test_weapon_attrs_reach_battle_config():
    p = L.new_profile()
    uid = L.add_equipment(p, "wood_sword", {"poison": 0.2, "fire": 0.2, "shadow": 0.05})
    L.add_equipment(p, "wood_sword")
    L.set_equipment(p, 1, [uid, 2])
    c = L.battle_config(1, 9, "hard", 1, profile=p)
    assert c["weapons"] == [{"name": "木の剣", "group": ["poison", "fire"], "group_chance": 0.2, "solo": {"shadow": 0.05}}]
    assert c["enemy_status"]["thunder"]["immune"]                                       # Lv.9 から雷は効かない
    assert not L.battle_config(1, 8, "hard", 1)["enemy_status"]["thunder"]["immune"]
    assert L.battle_config(1, L.EXTRA, "hard", 1)["enemy_status"]["thunder"]["immune"]
    assert c["enemy_status"]["black_flame"]["dot"] == [(0.60, 3), (0.05, 10)]
    import json
    assert L.normalize_profile(json.loads(json.dumps(p)))["equipment"][0]["attrs"]["shadow"] == 0.05


def test_black_flame_darkness_shadow_accessories():
    p = L.new_profile()
    for eq in ("black_flame_ring", "darkness_bracelet", "shadow_charm"):
        L.add_equipment(p, eq)
    L.set_equipment(p, 1, [1, 2, 3])
    c = L.battle_config(1, L.EXTRA, "hard", 1, profile=p)
    plain = L.battle_config(1, L.EXTRA, "hard", 1)
    assert math.isclose(c["status"]["black_flame"]["damage"], plain["status"]["black_flame"]["damage"] / 2)
    assert c["status"]["darkness"]["hit_scale"] == 0.89 and plain["status"]["darkness"]["hit_scale"] == 0.77
    assert math.isclose(c["status"]["shadow"]["evade_rate"], 0.15)
    import random
    rng = random.Random(2)
    def seen(diff):
        return {e for _ in range(1500) for kind, e, *_ in L.roll_treasure(9, diff, rng) if kind == "equip"}
    new = {"black_flame_ring", "darkness_bracelet", "shadow_charm"}
    assert not (seen("normal") & new)              # ノーマル以下では出ない
    assert new <= seen("hard")


def test_only_one_attr_weapon():
    p = L.new_profile()
    a = L.add_equipment(p, "wood_sword", {"poison": 0.2})
    b = L.add_equipment(p, "steel_sword", {"fire": 0.1})
    c = L.add_equipment(p, "steel_sword")
    L.set_equipment(p, 1, [a, c])
    try:
        L.set_equipment(p, 1, [a, b])
        assert False, "属性の剣を2本付けられてしまった"
    except ValueError:
        pass


def test_pack_and_inventory():
    p = L.new_profile()
    p["items"] = {"potion": 10, "elixir": 10}
    s1 = L.add_equipment(p, "wood_sword")
    s2 = L.add_equipment(p, "wood_sword")
    ring = L.add_equipment(p, "thunder_ring")
    # リュックに5個・倉庫に5個、剣2本と指輪を付ける、s2 をロック
    L.apply_inventory(p, 1, {"store": {"potion": 5, "elixir": 10}, "pack": {"potion": 5},
                             "gear": [s1, s2], "acc": [ring], "deleted": [], "locked": [s2]})
    assert p["items"]["potion"] == 5 and p["pack"] == {"potion": 5} and p["locked"] == [s2]
    assert L.ally_stats(1, p)["atk"] == 3
    # 増やす・減らす（アイテムは削除できない）・ロックした装備を消すのはだめ。失敗したら何も変わらない
    for bad in ({"store": {"potion": 9, "elixir": 10}, "pack": {"potion": 5}},
                {"store": {"potion": 3, "elixir": 10}, "pack": {"potion": 5}},
                {"store": {"potion": 5}, "pack": {"potion": 5}},
                {"store": {"potion": 5, "elixir": 10}, "pack": {"potion": 5}, "deleted": [s2], "locked": [s2]}):
        snapshot = json.dumps(p, sort_keys=True)
        try:
            L.apply_inventory(p, 1, {"gear": [s1, s2], "acc": [ring], **bad})
            assert False, bad
        except ValueError:
            pass
        assert json.dumps(p, sort_keys=True) == snapshot
    # 装備は削除できる（剣1本）
    L.apply_inventory(p, 1, {"store": {"potion": 5, "elixir": 10}, "pack": {"potion": 5}, "gear": [s2], "acc": [ring],
                             "deleted": [s1], "locked": [s2]})
    assert [e["uid"] for e in p["equipment"]] == [s2, ring]
    # 挑戦を始めるとリュックの中身を持っていき、リュックは空になる
    run = L.start_run(p, 1, "easy")
    assert L.bag_counts(run["bag"]) == {"potion": 5} and p["pack"] == {} and p["items"] == {"potion": 5, "elixir": 10}
    # 挑戦中はかばんを入れ替える
    L.apply_inventory(p, 1, {"store": {"potion": 3, "elixir": 10}, "pack": {"potion": 7}, "gear": [s2], "acc": [ring], "locked": [s2]})
    assert L.bag_counts(run["bag"]) == {"potion": 7} and p["items"] == {"potion": 3, "elixir": 10}


def test_new_items_and_potions():
    potion = L.get_item("potion")
    assert potion["cure"] == [] and L.get_item("elixir")["cure"] == []          # ポーション類はHPだけ
    assert L.get_item("panacea")["cure"] == ["poison", "thunder", "fire"]
    assert "black_flame" in L.get_item("holy_circle")["cure"] and L.get_item("seal_scroll")["ward"] == 3
    av = lambda item_id, stage, diff: L.item_available(L.get_item(item_id), stage, diff)
    assert av("panacea", 1, "easy")
    assert not av("seal_scroll", 9, "normal") and not av("seal_scroll", 4, "hard") and av("seal_scroll", 5, "hard")
    assert av("purge_scroll", 7, "normal") and not av("purge_scroll", 6, "normal") and av("purge_scroll", 5, "very_hard")
    assert [d for d in ("easy", "normal", "hard", "very_hard") if av("holy_circle", 8, d)] == ["hard", "very_hard"]
    assert av("holy_circle", 10, "easy") and not av("holy_circle", 9, "easy")
    assert set(L.initial_items()) == {"potion", "guard_up", "atk_up", "hi_potion", "mega_potion", "elixir", "panacea"}
    import random
    rng = random.Random(3)
    got = {i for _ in range(2000) for kind, i, *_ in L.roll_treasure(3, "easy", rng) if kind == "item"}
    assert "panacea" in got and not got & {"seal_scroll", "purge_scroll", "holy_circle"}


def test_random_accessories():
    import random
    rng = random.Random(4)
    for diff, lo, hi in (("easy", 1, 3), ("very_hard", 6, 12)):
        early = [L.roll_charm_value({"min": lo, "max": hi}, 1, L.stage_count(diff), rng) for _ in range(300)]
        late = [L.roll_charm_value({"min": lo, "max": hi}, L.stage_count(diff), L.stage_count(diff), rng) for _ in range(300)]
        assert min(early) == lo and max(late) == hi and max(early) <= lo + 0.45 * (hi - lo) + 0.5
        assert sum(late) / 300 > sum(early) / 300
    # 宝箱：その難易度の種類だけ出て、数値が付く
    found = [x for _ in range(3000) for x in L.roll_treasure(5, "hard", rng) if x[0] == "equip" and len(x) == 3]
    assert found and {L.get_equipment(e)["roll"]["difficulty"] for _, e, _ in found} == {"hard"}
    # 付けるとステータスに足される。ちがう指輪は同時に付けられる、同じ物は1つだけ
    p = L.new_profile()
    a = L.add_equipment(p, "ring_1", bonus={"atk": 3})
    b = L.add_equipment(p, "ring_3", bonus={"atk": 7})
    h = L.add_equipment(p, "life_2", bonus={"hp": 22})
    L.set_equipment(p, 1, [a, b, h])
    s = L.ally_stats(1, p)
    assert s["atk"] == 1 + 10 and s["hp"] == 10 + 22
    c = L.add_equipment(p, "ring_1", bonus={"atk": 1})
    try:
        L.set_equipment(p, 1, [a, c])
        assert False
    except ValueError:
        pass


def test_defeated_and_daily_bonus():
    p = L.new_profile()
    L.start_run(p, 1, "easy", {})
    L.clear_stage(p, FixedRng([0.9, 0.5]))
    assert p["defeated"] == ["enemy_01"]
    before = sum(p["items"].values())
    got = L.daily_bonus(p, "2026-10-28", FixedRng([]))
    assert got == "potion" and sum(p["items"].values()) == before + 1
    assert L.daily_bonus(p, "2026-10-28") is None                  # 同じ日は1回だけ
    assert L.daily_bonus(p, "2026-10-29", FixedRng([])) == "potion"


def test_extra_ally_joins_and_is_strongest():
    astel = story_data.ALLIES[10]
    for stat in ("hp", "atk", "def"):
        assert all(astel[stat] > a[stat] and astel["max"][stat] > a["max"][stat] for a in story_data.ALLIES[:10])
    assert astel["skill"]["charge"] == max(a["skill"]["charge"] for a in story_data.ALLIES)
    p = L.new_profile()
    run = L.start_run(p, 1, "easy", {})
    assert L.roll_unlocks(p, 1, "very_hard", FixedRng([0.0] * 10)) == [5]      # 宝箱の抽選では出ない
    run["extra"] = run["extra_seen"] = True
    rewards = L.clear_stage(p, FixedRng([]))
    assert rewards["allies"] == [11] and 11 in p["allies"]
    c = L.battle_config(1, 1, "easy", 11)["skill"]
    assert c["break_turns"] == 2 and math.isclose(c["damage"], 40 * 140)
    # アビリティ3「聖霊の加護」：毒・雷・火にかからない（25ポイントから）
    assert L.battle_config(1, 9, "hard", 11, profile=p)["ally"]["immune"] == []
    p["ability"]["11"] = 25
    assert L.battle_config(1, 9, "hard", 11, profile=p)["ally"]["immune"] == ["poison", "thunder", "fire"]
    assert "聖霊の加護" in L.ability_label(astel["abilities"][2])


def test_battle_config_status_numbers():
    p = L.new_profile()
    L.add_equipment(p, "fire_bangle")
    L.set_equipment(p, 1, [1])
    c = L.battle_config(1, 10, "easy", 1, profile=p, bag={"carried": {"potion": 2}, "picked": {"potion": 1}})
    assert c["final"] and c["enemy"]["key"] == "enemy_10" and len(c["enemy"]["lines"]) == 3
    assert c["status"]["darkness"]["hit_scale"] == 0.77 and c["status"]["shadow"]["evade_rate"] == 0.30
    assert c["enemy"]["gimmicks"] == ["poison", "thunder", "fire"] and c["enemy"]["meteor"]
    assert math.isclose(c["status"]["poison"]["damage"], 10 * 0.05)
    assert math.isclose(c["status"]["fire"]["damage"], 10 * 0.08 * 0.5 * (1 - 1 / 51))
    assert math.isclose(c["status"]["fire"]["damage_guard"], 10 * 0.08 * 0.5 * (1 - 2 / 52))
    assert math.isclose(c["status"]["black_flame"]["damage"], 1.0)
    assert c["enemy"]["hit_damage_guard"] < c["enemy"]["hit_damage"]
    potion = next(i for i in c["items"] if i["id"] == "potion")
    assert potion["count"] == 3 and math.isclose(potion["heal"], 3.0) and potion["cure"] == []


def test_profile_round_trips_through_json():
    import json
    p = L.new_profile()
    L.start_run(p, 1, "easy", {})
    assert L.normalize_profile(json.loads(json.dumps(p))) == p
    assert L.normalize_profile(None)["allies"] == [1]



def test_titles():
    p = L.new_profile()
    assert [t["id"] for t in L.titles(p)][:5] == ["mode_easy", "mode_normal", "mode_hard", "mode_very_hard", "extra"]
    assert len(L.titles(p)) == 5 + len(story_data.ALLIES) and not any(t["earned"] for t in L.titles(p))
    # 全クリアで、その難易度の称号
    L.start_run(p, 1, "easy")
    p["run"]["cleared"] = 10
    s = L.finish_run(p, "clear")
    assert p["cleared_modes"] == ["easy"] and [t["id"] for t in s["new_titles"]] == ["mode_easy"]
    assert L.take_new_titles(p) == []                       # 一度知らせたら、もう出ない
    # 中断では全クリアにならない
    L.start_run(p, 1, "normal")
    assert L.finish_run(p, "abandon")["new_titles"] == [] and p["cleared_modes"] == ["easy"]
    # 宇宙龍を倒す・Lv.10 にする
    p["defeated"].append(L.enemy_key(story_data.EXTRA_ENEMY))
    p["ability"]["1"] = L.level_points_max(1)
    assert {t["id"] for t in L.take_new_titles(p)} == {"extra", "ally_1"}
    # 仲間でないキャラは、ポイントがあっても称号にならない
    p["ability"]["10"] = 999
    assert not next(t for t in L.titles(p) if t["id"] == "ally_10")["earned"]


def test_titles_backfill_from_history():
    old = {"allies": [1], "defeated": ["enemy_11_veryhard"]}
    p = L.normalize_profile(old)
    assert p["titles_seen"] is None and p["cleared_modes"] == []
    rows = [{"名前": "a", "難易度": "ハード", "結果": "全クリア"}, {"名前": "a", "難易度": "イージー", "結果": "中断"},
            {"名前": "b", "難易度": "ノーマル", "結果": "全クリア"}]
    L.backfill_cleared_modes(p, rows, "a")
    assert sorted(p["cleared_modes"]) == ["hard", "very_hard"]
    assert set(p["titles_seen"]) == {"mode_hard", "mode_very_hard"}
    assert L.take_new_titles(p) == []


def test_extra_awaken():
    last = L.enemy_stats(L.stages_for("very_hard")[-1], "very_hard")
    st = L.awaken_stats()
    assert st["atk"] > last["atk"] and st["def"] > last["def"]            # ベリーハードの最後の敵より少し上
    c = L.battle_config(1, L.EXTRA, "easy", 1)
    aw = c["awaken"]
    assert aw["hp_rate"] == 0.5 and aw["heal_rate"] == 0.3 and aw["special"]["chance"] == 0.07 and aw["special"]["damage_rate"] == 0.2
    assert math.isclose(aw["hit_damage"], L.damage(st["atk"], c["ally"]["def"]))
    assert math.isclose(aw["tap_damage"], L.damage(c["ally"]["atk"], st["def"]))
    assert math.isclose(aw["skill_damage"], L.damage(c["skill"]["damage_break"], st["def"]))
    assert L.battle_config(1, 3, "easy", 1)["awaken"] is None              # ふつうのステージでは覚醒しない


def test_astel_assist():
    import random as _r
    c = L.battle_config(1, 3, "easy", 1)
    a = c["assist"]
    assert a["random"] and a["chance"] == 0.01 and a["break_turns"] == 2
    st = L.base_stats(11, 10)
    atk = st["atk"] + sum(ab["value"] for ab in story_data.ALLIES[10]["abilities"] if ab["stat"] == "atk")
    assert math.isclose(a["damage"], atk * 140)                              # Lv.10 とアビリティ、防御無視
    assert set(a["immune"]) == {"poison", "thunder", "fire"}
    assert not L.battle_config(1, L.EXTRA, "easy", 1)["assist"]["random"]     # エクストラでは来ない
    assert not L.battle_config(1, 3, "easy", 11)["assist"]["random"]          # アステル自身のときも来ない
    assert "white_scale" not in [i["id"] for i in c["items"]]                 # 鱗はホームで使う
    assert next(i for i in c["items"] if i["id"] == "spirit_feather")["assist"]
    # 特別なアイテムは、宝箱・ログインボーナス・最初の配布には出ない
    for item_id in ("white_scale", "spirit_feather"):
        assert not L.item_available(L.get_item(item_id), 10, "very_hard") and item_id not in L.initial_items()
    rng = _r.Random(1)
    assert all(L.daily_bonus({"bonus_day": "", "items": {}}, "d", rng) not in ("white_scale", "spirit_feather") for _ in range(300))
    # たまたまの援護で勝つと、どちらかが必ず手に入る。精霊の羽で呼んだときは出ない
    for kind, expect in (("random", True), ("feather", False)):
        p = L.new_profile()
        L.start_run(p, 1, "easy", {})
        L.apply_battle(p, {"result": "win", "ally_hp": 10, "assist": kind})
        r = L.clear_stage(p, _r.Random(5))
        assert bool(r.get("assist_drop")) == expect
        if expect:
            assert r["assist_drop"] in ("white_scale", "spirit_feather") and r["assist_where"] == "pack"
            assert L.bag_counts(p["run"]["bag"]).get(r["assist_drop"]) == 1


def test_white_scale_levels_up():
    p = L.new_profile()
    p["items"]["white_scale"] = 2
    msg = L.use_home_item(p, 1, "white_scale")
    assert L.ally_level(p, 1) == 2 and p["items"]["white_scale"] == 1 and "1 → 2" in msg
    p["ability"]["1"] = L.level_points_max(1)
    try:
        L.use_home_item(p, 1, "white_scale"); assert False
    except ValueError:
        pass
    assert p["items"]["white_scale"] == 1                                      # 最大のときは減らない


def test_first_rescue_and_feather_heal():
    p = L.new_profile()
    assert L.battle_config(1, 1, "easy", 1, profile=p)["assist"]["rescue"]          # はじめての人は救援がある
    assert not L.battle_config(1, L.EXTRA, "easy", 1, profile=p)["assist"]["rescue"]
    old = L.normalize_profile({"allies": [1, 2], "ability": {"1": 30}})
    assert L.battle_config(1, 1, "easy", 1, profile=old)["assist"]["rescue"]        # 前から遊んでいる人にも、これから1度出る
    L.note_battle(p, {"result": "quit", "assist": "rescue"})                       # 「やめる」で抜けたら保留
    assert not p["rescue_used"]
    L.note_battle(p, {"result": "lose", "assist": "rescue"})                       # 負けても、1度受けたらもう出ない
    assert p["rescue_used"] and not L.battle_config(1, 1, "easy", 1, profile=p)["assist"]["rescue"]
    feather = next(i for i in L.battle_config(1, 1, "easy", 1)["items"] if i["id"] == "spirit_feather")
    assert math.isclose(feather["heal"], L.battle_config(1, 1, "easy", 1)["ally"]["max_hp"])   # 羽は全回復


def test_silence_blade_rolls_attrs():
    import random as _r
    got = []
    for seed in range(60):
        p = L.new_profile()
        run = L.start_run(p, 1, "very_hard", {})
        run["stage"] = 12; run["cleared"] = 11
        L.clear_stage(p, _r.Random(seed))
        blade = next(e for e in p["equipment"] if e["id"] == "silence_blade")
        got.append(blade.get("attrs") or {})
    with_attrs = [a for a in got if a]
    assert 30 <= len(with_attrs) <= 54                              # ベリーハードの最後のステージと同じ 70%
    assert any(len(a) == 3 for a in with_attrs) and any(a.keys() & {"black_flame", "darkness", "shadow"} for a in with_attrs)

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
