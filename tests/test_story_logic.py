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
    assert math.isclose(vh["hp"], 1551 * 3.6) and math.isclose(vh["atk"], 12.2 * 3.6) and math.isclose(vh["def"], 19.8 * 2.4)
    extra = L.enemy_stats(story_data.EXTRA_ENEMY, "very_hard")          # エクストラは難易度に関係なく固定
    assert extra == {"hp": 1861, "atk": 14.8, "def": 20.2}           # ベリーハードのステージ6と同じ
    n = L.enemy_stats(1, "normal")
    assert math.isclose(n["hp"], 155) and math.isclose(n["def"], 1.35)


def test_display_hp():
    assert L.display_hp(9.02) == 9
    assert L.display_hp(0.3) == 1          # 生きている間は1と表示
    assert L.display_hp(0) == 0 and L.display_hp(-2) == 0


def test_battle_config_lv1():
    c = L.battle_config(1, 1, "easy", 1)
    assert math.isclose(c["ally"]["tap_damage"], 1 * (1 - 1 / 51))
    assert math.isclose(c["enemy"]["hit_damage"], 1 * (1 - 1 / 51))
    assert math.isclose(c["ally"]["tap_damage_up"], 4 * (1 - 1 / 51))   # 攻撃力アップ（+3）中
    assert c["attack_ms"] == 3000 and c["pause_ms"] == 800 and c["ally"]["hp"] == 10
    assert not c["final"] and not c["extra"] and c["stage_count"] == 10
    assert L.battle_config(1, 1, "easy", 1, ally_hp=4.5)["ally"]["hp"] == 4.5


def test_data_tables_consistent():
    assert [e["lv"] for e in story_data.ENEMIES] == list(range(1, 12)) + [11]
    assert [e["lv"] for e in L.stages_for("easy")] == list(range(1, 11))
    assert [L.enemy_key(e) for e in L.stages_for("hard")][-1] == "enemy_11_hard"
    assert [L.enemy_key(e) for e in L.stages_for("very_hard")][-2:] == ["enemy_11_hard", "enemy_11_veryhard"]
    assert [L.stage_count(d) for d in ("easy", "normal", "hard", "very_hard")] == [10, 10, 11, 12]
    assert [a["lv"] for a in story_data.ALLIES] == list(range(1, 11))
    ids = {d["id"] for d in story_data.DIFFICULTIES}
    for a in story_data.ALLIES:
        assert len(a["abilities"]) == len(story_data.ABILITY_THRESHOLDS)
        if a["unlock"]:
            assert a["unlock"]["min_difficulty"] in ids
    root = Path(L.__file__).parent / "assets/story"
    for e in story_data.ENEMIES + [story_data.EXTRA_ENEMY]:
        for g in e["gimmicks"]:
            assert g in story_data.STATUS_EFFECTS
        assert (root / "enemies" / e["image"]).exists()
        assert (root / "hitmasks" / f"{L.enemy_key(e)}.png").exists()
        assert len(e["lines"]) == 3
    for i in story_data.ITEMS:
        assert (root / "items" / f"{i['id']}.webp").exists() or (root / "items" / f"{i['id']}.png").exists()
    for eq in story_data.EQUIPMENT:
        assert any((root / "equipment" / f"{eq['id']}{ext}").exists() for ext in (".webp", ".png"))
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
    assert s["atk"] == 3 and s["def"] == 3 and s["hp"] == 10 and s["resist"] == ["poison"]


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
    assert p["items"] == {i["id"]: 10 for i in story_data.ITEMS}


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
            for kind, e in L.roll_treasure(2, "very_hard", rng) if kind == "equip"}
    assert seen == {"normal"}
    seen = {L.get_equipment(e)["rank"] for _ in range(800)
            for kind, e in L.roll_treasure(7, "normal", rng) if kind == "equip"}
    assert seen == {"normal", "rare", "epic", "accessory"}
    seen = {L.get_equipment(e)["rank"] for _ in range(800)
            for kind, e in L.roll_treasure(9, "easy", rng) if kind == "equip"}
    assert seen == {"normal", "rare"}


def test_checkpoint_restores_hp_and_bag():
    p = profile_with_items(potion=3)
    run = L.start_run(p, 1, "easy", {"potion": 3})
    L.apply_battle(p, {"ally_hp": 0, "used": {"potion": 2}})
    assert run["hp"] == 0 and L.bag_counts(run["bag"]) == {"potion": 1}
    L.restore_checkpoint(p)                       # 負けたら、そのステージを始めたときに戻る
    assert run["hp"] == 10 and L.bag_counts(run["bag"]) == {"potion": 3}
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
        rewards = L.clear_stage(p, FixedRng([0.9]))
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
    assert L.roll_weapon_attrs("wood_sword", "easy", FixedRng([0.5])) is None           # イージーは40%
    a = L.roll_weapon_attrs("wood_sword", "easy", FixedRng([0.3]))
    assert a == {"poison": 0.23}                                                       # 毒・火・雷の発動率は5〜40%
    assert L.attr_pool("normal") == ["poison", "fire", "thunder"]                       # 黒炎・陰・影はハード以上
    assert L.attr_pool("hard")[-3:] == ["black_flame", "darkness", "shadow"]
    import random
    rng = random.Random(5)
    counts = {1: 0, 2: 0, 3: 0}
    for _ in range(3000):
        a = L.roll_weapon_attrs("steel_sword", "very_hard", rng)
        if not a:
            continue
        counts[len(a)] += 1
        group = {v for k, v in a.items() if k in story_data.ATTR_GROUP}
        assert len(group) <= 1 and all(0.05 <= v <= 0.40 for v in group)              # 毒・火・雷は同じ発動率
        assert all(0.01 <= v <= 0.20 for k, v in a.items() if k in story_data.ATTR_SOLO)
    total = sum(counts.values())
    assert 0.92 < total / 3000 < 0.98                                                   # ベリーハードは95%
    assert abs(counts[3] / total - 0.20) < 0.03


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
        return {e for _ in range(1500) for kind, e in L.roll_treasure(9, diff, rng) if kind == "equip"}
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
    s1 = L.add_equipment(p, "wood_sword")
    s2 = L.add_equipment(p, "wood_sword")
    ring = L.add_equipment(p, "thunder_ring")
    # リュックに5個・倉庫に5個、剣2本と指輪を付ける、s2 をロック
    L.apply_inventory(p, 1, {"store": {"potion": 5, "elixir": 10}, "pack": {"potion": 5},
                             "gear": [s1, s2], "acc": [ring], "deleted": [], "locked": [s2]})
    assert p["items"]["potion"] == 5 and p["pack"] == {"potion": 5} and p["locked"] == [s2]
    assert L.ally_stats(1, p)["atk"] == 3
    # 増やすのはだめ・ロックした装備は消せない・失敗したら何も変わらない
    for bad in ({"store": {"potion": 9}, "pack": {"potion": 5}},
                {"store": {}, "pack": {"potion": 31}},
                {"store": {"potion": 5}, "pack": {"potion": 5}, "deleted": [s2], "locked": [s2]}):
        snapshot = json.dumps(p, sort_keys=True)
        try:
            L.apply_inventory(p, 1, {"gear": [s1, s2], "acc": [ring], **bad})
            assert False, bad
        except ValueError:
            pass
        assert json.dumps(p, sort_keys=True) == snapshot
    # 削除（ポーション2個と剣1本）
    L.apply_inventory(p, 1, {"store": {"potion": 3}, "pack": {"potion": 5}, "gear": [s2], "acc": [ring],
                             "deleted": [s1], "locked": [s2]})
    assert [e["uid"] for e in p["equipment"]] == [s2, ring] and "elixir" not in p["items"]
    # 挑戦を始めるとリュックの中身を持っていき、リュックは空になる
    run = L.start_run(p, 1, "easy")
    assert L.bag_counts(run["bag"]) == {"potion": 5} and p["pack"] == {} and p["items"] == {"potion": 3}
    # 挑戦中はかばんを入れ替える
    L.apply_inventory(p, 1, {"store": {"potion": 1}, "pack": {"potion": 7}, "gear": [s2], "acc": [ring], "locked": [s2]})
    assert L.bag_counts(run["bag"]) == {"potion": 7} and p["items"] == {"potion": 1}


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
    assert potion["count"] == 3 and math.isclose(potion["heal"], 3.0)


def test_profile_round_trips_through_json():
    import json
    p = L.new_profile()
    L.start_run(p, 1, "easy", {})
    assert L.normalize_profile(json.loads(json.dumps(p))) == p
    assert L.normalize_profile(None)["allies"] == [1]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
