"""ストーリーモードのデータ表（数値はすべてここで調整する）

処理は書かない。ここにあるのは定数と、敵・味方・アイテム・装備の表だけ。
仕様書「連打ゲーム ストーリーモード 仕様書」の決定内容をそのまま写している。
"""

# ---------------------------------------------------------------------------
# 戦闘の基本
# ---------------------------------------------------------------------------
TURN_SECONDS = 3.0          # 敵が攻撃する間隔。この長さを「1ターン」として数える
DEFENSE_K = 50              # 軽減率 = 防御 ÷ (防御 + DEFENSE_K)。小さくすると防御が効きやすい
STAGE_HEAL_RATE = 0.5       # ステージ間で回復する割合（最大HPに対して）
STAGE_COUNT = 10

# ---------------------------------------------------------------------------
# 難易度
#   enemy_hp_atk : 敵のHP・攻撃力にかける倍率
#   enemy_def    : 敵の防御力にかける倍率
#   ability      : アビリティポイントにかける倍率
#   rank         : 「◯◯以上」の判定に使う順位（大きいほど難しい）
# ---------------------------------------------------------------------------
DIFFICULTIES = [
    {"id": "easy",      "name": "イージー",     "rank": 0, "enemy_hp_atk": 1.0, "enemy_def": 1.0, "ability": 1.0},
    {"id": "normal",    "name": "ノーマル",     "rank": 1, "enemy_hp_atk": 1.5, "enemy_def": 1.2, "ability": 1.5},
    {"id": "hard",      "name": "ハード",       "rank": 2, "enemy_hp_atk": 2.0, "enemy_def": 1.5, "ability": 2.0},
    {"id": "very_hard", "name": "ベリーハード", "rank": 3, "enemy_hp_atk": 3.0, "enemy_def": 2.0, "ability": 3.0},
]

# ---------------------------------------------------------------------------
# 状態異常（ギミック）
#   max_hp_rate     : 毎ターン受けるダメージ（最大HPに対する割合）
#   current_hp_rate : 1回だけ受けるダメージ（今のHPに対する割合）
#   defense_applies : 防御力で軽減されるか
#   resistible      : 耐性アクセサリで半分にできるか
# ---------------------------------------------------------------------------
STATUS_CHANCE = 0.30            # 敵が攻撃するたびに状態異常を付ける確率
METEOR_TRIGGER_HP_RATE = 0.5    # 敵のHPがこの割合を切ったら、メテオを1回だけ使う
RESIST_RATE = 0.5               # 耐性アクセサリの効果（ダメージ・ターン数を半分）

STATUS_EFFECTS = {
    "poison":      {"icon": "☠️", "name": "毒",   "turns": 4, "max_hp_rate": 0.05, "defense_applies": False, "resistible": True},
    "thunder":     {"icon": "⚡", "name": "雷",   "turns_min": 1, "turns_max": 3, "resistible": True},  # タップできない
    "fire":        {"icon": "🔥", "name": "火",   "turns": 3, "max_hp_rate": 0.08, "defense_applies": True,  "resistible": True},
    "meteor":      {"icon": "☄️", "name": "メテオ", "current_hp_rate": 0.5, "then": "black_flame", "resistible": False},
    "black_flame": {"icon": "🌑", "name": "黒炎", "turns": 3, "max_hp_rate": 0.10, "defense_applies": False, "resistible": False},
}

# ---------------------------------------------------------------------------
# 敵（イージーの値。ほかの難易度は DIFFICULTIES の倍率をかける）
#   HP     : 同じLvの味方（装備なし）が毎秒8回ほどの連打で、Lv.1 は約12秒、Lv.10 は約45秒で倒せる量。
#            Lv.6 だけ多め（装備なしの Lv.10 がベリーハードで5ステージ止まりになるように）
#   攻撃力 : 1ステージごとに約1.45倍
#   image      : assets/story/enemies/ の中のファイル名
#   cutout     : True なら背景を透過した画像。scene の背景はCSSで描く
#   scene      : 背景の種類（story_assets.SCENE_CSS のクラス名）
#   floating   : 宙に浮かせて表示する（足元の影を出さない）
#   gimmicks   : 使う状態異常。後から別のギミックを足すときはここに書く
# ---------------------------------------------------------------------------
ENEMIES = [
    {"lv": 1,  "name": "薄汚れたゾンビ", "hp": 100,  "atk": 1.5,  "def": 1,  "image": "enemy_01.webp", "cutout": True,  "scene": "corridor", "floating": False, "gimmicks": []},
    {"lv": 2,  "name": "呪われた戦士",   "hp": 220,  "atk": 2.2,  "def": 2,  "image": "enemy_02.webp", "cutout": True,  "scene": "prison",   "floating": False, "gimmicks": []},
    {"lv": 3,  "name": "幽霊の暗殺者",   "hp": 250,  "atk": 3.2,  "def": 3,  "image": "enemy_03.webp", "cutout": True,  "scene": "catacomb", "floating": False, "gimmicks": []},
    {"lv": 4,  "name": "骨の魔術師",     "hp": 300,  "atk": 4.6,  "def": 4,  "image": "enemy_04.webp", "cutout": True,  "scene": "altar",    "floating": False, "gimmicks": []},
    {"lv": 5,  "name": "深淵の従者",     "hp": 600,  "atk": 6.6,  "def": 6,  "image": "enemy_05.webp", "cutout": False, "scene": "image",    "floating": False, "gimmicks": []},
    {"lv": 6,  "name": "死霊の将軍",     "hp": 1300, "atk": 9.6,  "def": 8,  "image": "enemy_06.webp", "cutout": False, "scene": "image",    "floating": False, "gimmicks": []},
    {"lv": 7,  "name": "悪魔の貴族",     "hp": 2000, "atk": 14,   "def": 10, "image": "enemy_07.webp", "cutout": False, "scene": "image",    "floating": False, "gimmicks": ["poison"]},
    {"lv": 8,  "name": "半神の魔王",     "hp": 2800, "atk": 20,   "def": 12, "image": "enemy_08.webp", "cutout": False, "scene": "image",    "floating": False, "gimmicks": ["thunder"]},
    {"lv": 9,  "name": "災厄の代行者",   "hp": 4800, "atk": 29,   "def": 15, "image": "enemy_09.webp", "cutout": True,  "scene": "nebula",   "floating": True,  "gimmicks": ["poison", "thunder", "fire"]},
    {"lv": 10, "name": "終焉の創造主",   "hp": 9000, "atk": 42,   "def": 18, "image": "enemy_10.webp", "cutout": False, "scene": "image",    "floating": False, "gimmicks": ["poison", "thunder", "fire", "meteor"]},
]

# ---------------------------------------------------------------------------
# 味方
#   unlock    : None なら最初から使える。
#               min_difficulty 以上の難易度で stage をクリアしたとき、chance の確率で仲間になる
#   abilities : アビリティポイントの合計が ABILITY_THRESHOLDS に達するたびに順に解放
#   image     : assets/story/allies/（全身）と assets/story/ally_icons/（顔）の中のファイル名
#   skill     : 今回は作らない（後から足せるように項目だけ用意）
# ---------------------------------------------------------------------------
ABILITY_THRESHOLDS = (5, 10, 25)
ABILITY_POINT_PER_STAGE = 0.1     # クリアしたステージ1つにつき 0.1（全クリアで 1.0）

ALLIES = [
    {"lv": 1,  "name": "平凡な農民、コウ",         "hp": 10,  "atk": 1,  "def": 1,  "image": "ally_01.webp", "unlock": None,
     "abilities": [{"stat": "atk", "value": 1}, {"stat": "atk", "value": 1}, {"stat": "def", "value": 3}], "skill": None},
    {"lv": 2,  "name": "新米自警団員、マリ",       "hp": 11,  "atk": 2,  "def": 1,  "image": "ally_02.webp", "unlock": {"min_difficulty": "normal", "stage": 2, "chance": 0.30},
     "abilities": [{"stat": "def", "value": 1}, {"stat": "def", "value": 1}, {"stat": "atk", "value": 4}], "skill": None},
    {"lv": 3,  "name": "新兵中隊長、アレックス",   "hp": 13,  "atk": 2,  "def": 3,  "image": "ally_03.webp", "unlock": {"min_difficulty": "easy", "stage": 4, "chance": 0.50},
     "abilities": [{"stat": "hp", "value": 3}, {"stat": "hp", "value": 3}, {"stat": "atk", "value": 3}], "skill": None},
    {"lv": 4,  "name": "魔導戦術家、セリス",       "hp": 16,  "atk": 2,  "def": 5,  "image": "ally_04.webp", "unlock": {"min_difficulty": "normal", "stage": 3, "chance": 0.30},
     "abilities": [{"stat": "atk", "value": 1}, {"stat": "atk", "value": 1}, {"stat": "hp", "value": 10}], "skill": None},
    {"lv": 5,  "name": "先鋭近衛騎士、アーサー",   "hp": 22,  "atk": 4,  "def": 4,  "image": "ally_05.webp", "unlock": {"min_difficulty": "hard", "stage": 1, "chance": 0.30},
     "abilities": [{"stat": "def", "value": 2}, {"stat": "def", "value": 2}, {"stat": "hp", "value": 15}], "skill": None},
    {"lv": 6,  "name": "古代魔導研究者、エリナ",   "hp": 30,  "atk": 6,  "def": 3,  "image": "ally_06.webp", "unlock": {"min_difficulty": "normal", "stage": 6, "chance": 0.40},
     "abilities": [{"stat": "hp", "value": 5}, {"stat": "hp", "value": 5}, {"stat": "def", "value": 8}], "skill": None},
    {"lv": 7,  "name": "王宮近衛隊長、ガイウス",   "hp": 45,  "atk": 10, "def": 6,  "image": "ally_07.webp", "unlock": {"min_difficulty": "normal", "stage": 7, "chance": 0.20},
     "abilities": [{"stat": "atk", "value": 2}, {"stat": "atk", "value": 2}, {"stat": "atk", "value": 6}], "skill": None},
    {"lv": 8,  "name": "魔導工学の至高者、レイノ", "hp": 63,  "atk": 13, "def": 15, "image": "ally_08.webp", "unlock": {"min_difficulty": "hard", "stage": 5, "chance": 0.60},
     "abilities": [{"stat": "def", "value": 3}, {"stat": "def", "value": 3}, {"stat": "atk", "value": 8}], "skill": None},
    {"lv": 9,  "name": "概念の卵、ガレン",         "hp": 73,  "atk": 20, "def": 19, "image": "ally_09.webp", "unlock": {"min_difficulty": "hard", "stage": 5, "chance": 0.30},
     "abilities": [{"stat": "hp", "value": 10}, {"stat": "hp", "value": 10}, {"stat": "def", "value": 15}], "skill": None},
    {"lv": 10, "name": "至高の光帝、ルナ",         "hp": 100,  "atk": 33,   "def": 35, "image": "ally_10.webp", "unlock": {"min_difficulty": "very_hard", "stage": 7, "chance": 0.20},
     "abilities": [{"stat": "atk", "value": 3}, {"stat": "atk", "value": 3}, {"stat": "hp", "value": 40}], "skill": None},
]

# ---------------------------------------------------------------------------
# アイテム（ポーション類は状態異常もすべて治す）
#   heal_rate : 最大HPに対する回復量（1.0 で全回復）
#   icon      : 画面に出す絵文字（装備・状態異常も同じ）
#   guard     : 防御力2倍が続くターン数
#   weight    : 宝箱でアイテムが出たときの選ばれやすさ
# ---------------------------------------------------------------------------
MAX_CARRY_ITEMS = 30
GUARD_MULTIPLIER = 2.0

ITEMS = [
    {"id": "potion",      "icon": "🧪", "name": "ポーション",     "heal_rate": 0.3, "cure": True,  "guard": 0, "weight": 40},
    {"id": "guard_up",    "icon": "🛡️", "name": "防御アップ",     "heal_rate": 0.0, "cure": False, "guard": 3, "weight": 25},
    {"id": "hi_potion",   "icon": "⚗️", "name": "ハイポーション", "heal_rate": 0.6, "cure": True,  "guard": 0, "weight": 20},
    {"id": "mega_potion", "icon": "💖", "name": "メガポーション", "heal_rate": 1.0, "cure": True,  "guard": 0, "weight": 10},
    {"id": "elixir",      "icon": "✨", "name": "エリクサー",     "heal_rate": 1.0, "cure": True,  "guard": 3, "weight": 5},
]

# ---------------------------------------------------------------------------
# 装備（1キャラ3つまで。同じ装備は2つ付けられない）
#   EQUIP_RANKS の条件を満たすランクの中から weight の比率でランクを選び、
#   そのランクの装備から同じ確率で1つ選ぶ
# ---------------------------------------------------------------------------
MAX_EQUIP_SLOTS = 3

EQUIP_RANKS = {
    "normal":    {"name": "ノーマル",   "weight": 60, "min_stage": 1, "min_difficulty": "easy"},
    "rare":      {"name": "レア",       "weight": 30, "min_stage": 3, "min_difficulty": "easy"},
    "epic":      {"name": "激レア",     "weight": 10, "min_stage": 7, "min_difficulty": "normal"},
    "accessory": {"name": "アクセサリ", "weight": 30, "min_stage": 5, "min_difficulty": "normal"},
}

EQUIPMENT = [
    {"id": "wood_sword",     "icon": "🗡️", "name": "木の剣",         "rank": "normal",    "atk": 1,  "def": 0,  "hp": 0,  "resist": None},
    {"id": "leather_shield", "icon": "🛡️", "name": "革の盾",         "rank": "normal",    "atk": 0,  "def": 2,  "hp": 0,  "resist": None},
    {"id": "travel_cloak",   "icon": "🧥", "name": "旅人のマント",   "rank": "normal",    "atk": 0,  "def": 0,  "hp": 5,  "resist": None},
    {"id": "steel_sword",    "icon": "⚔️", "name": "鋼の剣",         "rank": "rare",      "atk": 3,  "def": 0,  "hp": 0,  "resist": None},
    {"id": "steel_shield",   "icon": "🛡️", "name": "鋼の盾",         "rank": "rare",      "atk": 0,  "def": 6,  "hp": 0,  "resist": None},
    {"id": "knight_armor",   "icon": "🥋", "name": "騎士の鎧",       "rank": "rare",      "atk": 0,  "def": 0,  "hp": 15, "resist": None},
    {"id": "holy_sword",     "icon": "🌟", "name": "聖剣",           "rank": "epic",      "atk": 8,  "def": 0,  "hp": 0,  "resist": None},
    {"id": "holy_shield",    "icon": "🔰", "name": "聖なる盾",       "rank": "epic",      "atk": 0,  "def": 15, "hp": 0,  "resist": None},
    {"id": "dragon_armor",   "icon": "🐉", "name": "竜の鎧",         "rank": "epic",      "atk": 0,  "def": 0,  "hp": 40, "resist": None},
    {"id": "poison_charm",   "icon": "📿", "name": "毒よけのお守り", "rank": "accessory", "atk": 0,  "def": 0,  "hp": 0,  "resist": "poison"},
    {"id": "thunder_ring",   "icon": "💍", "name": "雷よけの指輪",   "rank": "accessory", "atk": 0,  "def": 0,  "hp": 0,  "resist": "thunder"},
    {"id": "fire_bangle",    "icon": "🔥", "name": "火よけの腕輪",   "rank": "accessory", "atk": 0,  "def": 0,  "hp": 0,  "resist": "fire"},
]

# ---------------------------------------------------------------------------
# 宝箱
# ---------------------------------------------------------------------------
TREASURE_CHANCE = 0.70        # ステージクリア時に宝箱が出る確率
TREASURE_COUNT = (1, 3)       # 出る個数（同じ確率で選ぶ）
TREASURE_ITEM_RATE = 0.70     # 1個の中身がアイテムになる確率（残りは装備）
