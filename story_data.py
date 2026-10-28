"""ストーリーモードのデータ表（数値はすべてここで調整する）

処理は書かない。ここにあるのは定数と、敵・味方・アイテム・装備の表だけ。
仕様書「連打ゲーム ストーリーモード 仕様書」の決定内容をそのまま写している。
"""

# ---------------------------------------------------------------------------
# 戦闘の基本
# ---------------------------------------------------------------------------
# ターン制：自分のターン（攻撃かアイテム）→ 敵のターン（1回攻撃）を、どちらかのHPが0になるまで繰り返す。
# 攻撃は「よーい、スタート！」から ATTACK_SECONDS 秒のあいだ連打し、合計ダメージで一気に攻撃する。
ATTACK_SECONDS = 3.0        # 1回の攻撃で連打できる時間
TURN_PAUSE_SECONDS = 0.8    # 攻撃のあと、相手のターンに移るまでの間
DEFENSE_K = 50              # 軽減率 = 防御 ÷ (防御 + DEFENSE_K)。小さくすると防御が効きやすい
STAGE_HEAL_RATE = 0.5       # ステージ間で回復する割合（最大HPに対して）

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
    "thunder":     {"icon": "⚡", "name": "雷",   "turns_min": 1, "turns_max": 3, "resistible": True},  # 攻撃できない（アイテムは使える）
    "fire":        {"icon": "🔥", "name": "火",   "turns": 3, "max_hp_rate": 0.08, "defense_applies": True,  "resistible": True},
    "meteor":      {"icon": "☄️", "name": "メテオ", "current_hp_rate": 0.5, "then": "black_flame", "resistible": False},
    "black_flame": {"icon": "🌑", "name": "黒炎", "turns": 3, "max_hp_rate": 0.10, "defense_applies": False, "resistible": True},
    # 陰：画面が暗くなり、当たりマスクが敵の重心を中心に縦横 hit_scale 倍に縮む（面積で約6割）。自分の攻撃1回分
    # 陰よけの腕輪：狭まり方が半分になる（面積で約6割 → 約8割。縦横 resist_hit_scale 倍）
    "darkness":    {"icon": "🌘", "name": "陰",   "turns": 1, "hit_scale": 0.77, "resist_hit_scale": 0.89, "resistible": True},
    # 影：自分の攻撃が evade_rate の確率で丸ごと回避される。自分の攻撃2回分
    # 影よけのお守り：回避される確率が半分（30% → 15%）
    "shadow":      {"icon": "👤", "name": "影",   "turns": 2, "evade_rate": 0.30, "resistible": True},
}

# ---------------------------------------------------------------------------
# 敵（イージーの値。ほかの難易度は DIFFICULTIES の倍率をかける）
#   決め方：Lv.1〜5 は最初の数値。Lv.6 からは1ステージごとに HP・攻撃力を約1.3倍にした。
#           そのうえで HP・攻撃力・防御力を、Lv.1 はそのまま、Lv.10 は1.1倍にし、あいだは Lv に比例して
#           少しずつ上げている（Lv.n は 1 + 0.1 × (n−1) ÷ 9 倍。Lv.11 は Lv.10 と同じ1.1倍）。
#           HP は整数、攻撃力・防御力は小数第1位で四捨五入
#   image       : assets/story/enemies/ の中のファイル名（当たりマスクは hitmasks/ の同じ名前の .png）
#   cutout      : True なら背景を透過した画像。背景は scene の画像とCSSで描く
#   scene       : 背景の種類（story_assets の _SCENE_LAYERS のキー。"image" は画像そのものが背景）
#   floating    : 宙に浮かせて表示する（足元の影を出さない）
#   gimmicks    : 使う状態異常。後から別のギミックを足すときはここに書く
#   immune      : 効かない剣の属性（Lv.9 以降と宇宙龍は「天変地異」の特性で雷が効かない）。書いていなければ全部効く
#   difficulties: 出てくる難易度。None ならすべて。Lv.11 はハードとベリーハードで別の敵が出る
#   lines       : 敵のターンに出す一言（毎回この中から1つ選ぶ）
#   effect      : 敵の攻撃エフェクトの種類と色（web/story/index.html の EFFECTS）
# ---------------------------------------------------------------------------
_ALL = None
ENEMIES = [
    {"lv": 1, "name": "薄汚れたゾンビ", "hp": 100, "atk": 1, "def": 1,
     "image": "enemy_01.webp", "cutout": True, "scene": "corridor", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["ウゥ……アァ……", "……ニク……", "グアァァッ！"], "effect": {"type": "claw", "color": "#9db36b"}},
    {"lv": 2, "name": "呪われた戦士", "hp": 142, "atk": 1, "def": 2,
     "image": "enemy_02.webp", "cutout": True, "scene": "prison", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["呪いは……解けぬ……", "この剣、錆びてはおらぬ", "ここから先へは通さん"], "effect": {"type": "slash", "color": "#d8d2c4"}},
    {"lv": 3, "name": "幽霊の暗殺者", "hp": 204, "atk": 2, "def": 3.1,
     "image": "enemy_03.webp", "cutout": True, "scene": "catacomb", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["……背中が、がら空きだ", "影は斬れまい", "音もなく、消えろ"], "effect": {"type": "ghost", "color": "#8fd8ff"}},
    {"lv": 4, "name": "骨の魔術師", "hp": 289, "atk": 2.1, "def": 4.1,
     "image": "enemy_04.webp", "cutout": True, "scene": "altar", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["我が魔術の糧となれ", "骨の髄まで凍えるがいい", "クク……愚かな"], "effect": {"type": "magic", "color": "#b26bff"}},
    {"lv": 5, "name": "深淵の従者", "hp": 397, "atk": 3.1, "def": 6.3,
     "image": "enemy_05.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["深淵へ……引きずり込んでやる", "シャアアッ！", "主のもとへは行かせぬ"], "effect": {"type": "whip", "color": "#e0483e"}},
    {"lv": 6, "name": "死霊の将軍", "hp": 517, "atk": 4.1, "def": 8.4,
     "image": "enemy_06.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["我が軍勢の前にひれ伏せ", "死してなお、我は戦う", "この一撃、受けてみよ"], "effect": {"type": "slash", "color": "#a9c4b0"}},
    {"lv": 7, "name": "悪魔の貴族", "hp": 683, "atk": 5.4, "def": 10.7,
     "image": "enemy_07.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": ["poison"], "difficulties": _ALL,
     "lines": ["下賤の者が、我に触れるな", "地獄の炎で焼かれるがいい", "フフ……退屈させるな"], "effect": {"type": "fire", "color": "#ff7a2a"}},
    {"lv": 8, "name": "半神の魔王", "hp": 895, "atk": 7.1, "def": 12.9,
     "image": "enemy_08.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": ["thunder"], "difficulties": _ALL,
     "lines": ["玉座から動くまでもない", "神の雷、その身で知れ", "ひざまずけ"], "effect": {"type": "thunder", "color": "#ffd84a"}},
    {"lv": 9, "name": "災厄の代行者", "hp": 1187, "atk": 9.4, "def": 16.3,
     "image": "enemy_09.webp", "cutout": True, "scene": "nebula", "floating": True, "immune": ["thunder"], "gimmicks": ["poison", "thunder", "fire"], "difficulties": _ALL,
     "lines": ["すべては無に還る", "災いは、選ばない", "抗うな。苦しむだけだ"], "effect": {"type": "void", "color": "#9a6bff"}},
    {"lv": 10, "name": "終焉の創造主", "hp": 1551, "atk": 12.2, "def": 19.8,
     "image": "enemy_10.webp", "cutout": False, "scene": "image", "floating": False, "immune": ["thunder"], "gimmicks": ["poison", "thunder", "fire", "meteor"], "difficulties": _ALL,
     "lines": ["世界を創り、そして終わらせる", "星の一つも、我が意のまま", "よくぞここまで来た。だが、ここで終わりだ"], "effect": {"type": "cosmic", "color": "#a8d4ff"}},
    {"lv": 11, "name": "混沌の初源", "hp": 2013, "atk": 15.8, "def": 23.1,
     "image": "enemy_11_hard.webp", "cutout": False, "scene": "image", "floating": False, "immune": ["thunder"], "gimmicks": ["poison", "thunder", "fire", "meteor", "darkness"], "difficulties": ["hard"],
     "lines": ["すべてはわたしから生まれた", "還りなさい、始まりの光へ", "混沌こそ、世界の母"], "effect": {"type": "radiance", "color": "#ffd27a"}},
    {"lv": 11, "name": "永遠の沈黙", "hp": 2013, "atk": 15.8, "def": 23.1,
     "image": "enemy_11_veryhard.webp", "cutout": False, "scene": "image", "floating": False, "immune": ["thunder"], "gimmicks": ["poison", "thunder", "fire", "meteor", "darkness", "shadow"], "difficulties": ["very_hard"],
     "lines": ["…………", "音も、光も、ここには届かない", "沈め"], "effect": {"type": "silence", "color": "#6f8cff"}},
]

# ---------------------------------------------------------------------------
# エクストラステージ：極点の宇宙龍（混沌の初源・永遠の沈黙の使い。各ステージを見回っている）
#   ステージをクリアするたびに EXTRA_CHANCE の確率で、次のステージの前に現れる（1回の挑戦で1度まで）
#   「にげる」で戦わずに先へ進める（負けにならない）。倒すと超激レア装備（ULTRA_REWARDS）
#   強さは難易度に関係なく固定（ベリーハードのステージ5と同じ：HP380×3・攻撃3×3・防御6×2）
#   fit / focus : 横長の絵なので、画面を埋めるように拡大し（cover）、focus の位置を中心に見せる
# ---------------------------------------------------------------------------
EXTRA_CHANCE = 0.01
EXTRA_ENEMY = {
    "lv": "???", "name": "極点の宇宙龍", "title": "災厄と創造の統合者", "hp": 1140, "atk": 9, "def": 12, "fixed_stats": True,
    "image": "enemy_extra.webp", "cutout": False, "scene": "image", "floating": False, "fit": "cover", "focus": "64% 50%",
    "immune": ["thunder"], "gimmicks": ["black_flame", "shadow", "darkness"], "difficulties": None,
    "lines": ["……見つけたぞ、小さき者", "我が主の領域を荒らすか", "星ごと呑み込んでくれよう"],
    "effect": {"type": "cosmic", "color": "#c49bff"},
}

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
    {"lv": 1,  "name": "平凡な農民、コウ",         "hp": 10, "atk": 1, "def": 1,  "image": "ally_01.webp", "unlock": None,
     "abilities": [{"stat": "atk", "value": 1}, {"stat": "atk", "value": 1}, {"stat": "def", "value": 3}], "skill": None},
    {"lv": 2,  "name": "新米自警団員、マリ",       "hp": 11, "atk": 2, "def": 1,  "image": "ally_02.webp", "unlock": {"min_difficulty": "normal", "stage": 2, "chance": 0.30},
     "abilities": [{"stat": "def", "value": 1}, {"stat": "def", "value": 1}, {"stat": "atk", "value": 4}], "skill": None},
    {"lv": 3,  "name": "新兵中隊長、アレックス",   "hp": 13, "atk": 2, "def": 3,  "image": "ally_03.webp", "unlock": {"min_difficulty": "easy", "stage": 4, "chance": 0.50},
     "abilities": [{"stat": "hp", "value": 3}, {"stat": "hp", "value": 3}, {"stat": "atk", "value": 3}], "skill": None},
    {"lv": 4,  "name": "魔導戦術家、セリス",       "hp": 16, "atk": 2, "def": 5,  "image": "ally_04.webp", "unlock": {"min_difficulty": "normal", "stage": 3, "chance": 0.30},
     "abilities": [{"stat": "atk", "value": 1}, {"stat": "atk", "value": 1}, {"stat": "hp", "value": 10}], "skill": None},
    {"lv": 5,  "name": "先鋭近衛騎士、アーサー",   "hp": 22, "atk": 4, "def": 4,  "image": "ally_05.webp", "unlock": {"min_difficulty": "hard", "stage": 1, "chance": 0.30},
     "abilities": [{"stat": "def", "value": 2}, {"stat": "def", "value": 2}, {"stat": "hp", "value": 15}], "skill": None},
    {"lv": 6,  "name": "古代魔導研究者、エリナ",   "hp": 30, "atk": 6, "def": 3,  "image": "ally_06.webp", "unlock": {"min_difficulty": "normal", "stage": 6, "chance": 0.40},
     "abilities": [{"stat": "hp", "value": 5}, {"stat": "hp", "value": 5}, {"stat": "def", "value": 8}], "skill": None},
    {"lv": 7,  "name": "王宮近衛隊長、ガイウス",   "hp": 45, "atk": 10, "def": 6,  "image": "ally_07.webp", "unlock": {"min_difficulty": "normal", "stage": 7, "chance": 0.20},
     "abilities": [{"stat": "atk", "value": 2}, {"stat": "atk", "value": 2}, {"stat": "atk", "value": 6}], "skill": None},
    {"lv": 8,  "name": "魔導工学の至高者、レイノ", "hp": 63, "atk": 13, "def": 15, "image": "ally_08.webp", "unlock": {"min_difficulty": "hard", "stage": 5, "chance": 0.60},
     "abilities": [{"stat": "def", "value": 3}, {"stat": "def", "value": 3}, {"stat": "atk", "value": 8}], "skill": None},
    {"lv": 9,  "name": "概念の卵、ガレン",         "hp": 73, "atk": 20, "def": 19, "image": "ally_09.webp", "unlock": {"min_difficulty": "hard", "stage": 5, "chance": 0.30},
     "abilities": [{"stat": "hp", "value": 10}, {"stat": "hp", "value": 10}, {"stat": "def", "value": 15}], "skill": None},
    {"lv": 10, "name": "至高の光帝、ルナ",         "hp": 100, "atk": 33, "def": 35, "image": "ally_10.webp", "unlock": {"min_difficulty": "very_hard", "stage": 7, "chance": 0.20},
     "abilities": [{"stat": "atk", "value": 3}, {"stat": "atk", "value": 3}, {"stat": "hp", "value": 40}], "skill": None},
]

# ---------------------------------------------------------------------------
# アイテム（ポーション類は状態異常もすべて治す）
#   heal_rate : 最大HPに対する回復量（1.0 で全回復）
#   icon      : 画面に出す絵文字（装備・状態異常も同じ）
#   guard     : 防御力2倍が続くターン数
#   atk_bonus : 攻撃力に足す値（atk_turns ターン＝自分の攻撃 atk_turns 回のあいだ）
#   weight    : 宝箱でアイテムが出たときの選ばれやすさ
# 自分のターンに1つだけ使え、使ったあとも攻撃できる
# ---------------------------------------------------------------------------
MAX_CARRY_ITEMS = 30
GUARD_MULTIPLIER = 2.0
INITIAL_ITEM_COUNT = 10     # 最初にホームに持っているアイテムの数（全種類それぞれ）

ITEMS = [
    {"id": "potion",      "icon": "🧪", "name": "ポーション",     "heal_rate": 0.3, "cure": True,  "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 40},
    {"id": "guard_up",    "icon": "🛡️", "name": "防御アップ",     "heal_rate": 0.0, "cure": False, "guard": 3, "atk_bonus": 0, "atk_turns": 0, "weight": 25},
    {"id": "atk_up",      "icon": "💪", "name": "攻撃力アップ",   "heal_rate": 0.0, "cure": False, "guard": 0, "atk_bonus": 3, "atk_turns": 3, "weight": 20},
    {"id": "hi_potion",   "icon": "⚗️", "name": "ハイポーション", "heal_rate": 0.6, "cure": True,  "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 20},
    {"id": "mega_potion", "icon": "💖", "name": "メガポーション", "heal_rate": 1.0, "cure": True,  "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 10},
    {"id": "elixir",      "icon": "✨", "name": "エリクサー",     "heal_rate": 1.0, "cure": True,  "guard": 3, "atk_bonus": 0, "atk_turns": 0, "weight": 5},
]

# ---------------------------------------------------------------------------
# 装備
#   装備品（ノーマル・レア・激レア・超激レア）とアクセサリは別のわく。1キャラにそれぞれ3つまで。
#   装備品は同じ種類を重ねて付けられる（木の剣2本など）。アクセサリは同じ種類を2つ付けられない。
#   どちらも、1つの装備（番号ごと）を使えるのは1人だけ。
#   宝箱では、EQUIP_RANKS の条件を満たすランクの中から weight の比率でランクを選び、
#   そのランクの装備から同じ確率で1つ選ぶ
# ---------------------------------------------------------------------------
MAX_GEAR_SLOTS = 3          # 装備品のわく
MAX_ACCESSORY_SLOTS = 3     # アクセサリのわく
ACCESSORY_RANK = "accessory"

EQUIP_RANKS = {
    "normal":    {"name": "ノーマル",   "weight": 60, "min_stage": 1, "min_difficulty": "easy"},
    "rare":      {"name": "レア",       "weight": 30, "min_stage": 3, "min_difficulty": "easy"},
    "epic":      {"name": "激レア",     "weight": 10, "min_stage": 7, "min_difficulty": "normal"},
    "accessory": {"name": "アクセサリ", "weight": 30, "min_stage": 5, "min_difficulty": "normal"},
    # 超激レアは宝箱からは出ない（weight 0）。特別な敵を倒したときのごほうび（ULTRA_REWARDS）だけ
    "ultra":     {"name": "超激レア",   "weight": 0,  "min_stage": 99, "min_difficulty": "very_hard"},
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
    # 黒炎・陰・影よけは、その状態異常を使う敵が出るハード以上でだけ宝箱から出る（min_difficulty）
    {"id": "black_flame_ring",  "icon": "🌑", "name": "黒炎の指輪",   "rank": "accessory", "atk": 0, "def": 0, "hp": 0, "resist": "black_flame", "min_difficulty": "hard"},
    {"id": "darkness_bracelet", "icon": "🌘", "name": "陰の腕輪",     "rank": "accessory", "atk": 0, "def": 0, "hp": 0, "resist": "darkness",    "min_difficulty": "hard"},
    {"id": "shadow_charm",      "icon": "👤", "name": "影のお守り",   "rank": "accessory", "atk": 0, "def": 0, "hp": 0, "resist": "shadow",      "min_difficulty": "hard"},
    {"id": "dragon_scale",   "icon": "🐲", "name": "宇宙龍の逆鱗",   "rank": "ultra",     "atk": 12, "def": 25, "hp": 60, "resist": None},
    {"id": "origin_robe",    "icon": "👘", "name": "初源の聖衣",     "rank": "ultra",     "atk": 0,  "def": 60, "hp": 0,  "resist": None},
    {"id": "silence_blade",  "icon": "🗡️", "name": "沈黙の魔剣",     "rank": "ultra",     "atk": 30, "def": 0,  "hp": 0,  "resist": None},
]

# 特別な敵を倒したときに必ずもらえる超激レア装備（敵の画像ファイル名の拡張子なし → 装備ID）
ULTRA_REWARDS = {
    "enemy_extra": "dragon_scale",        # 極点の宇宙龍：HP・防御・攻撃をそろって大きく上げる
    "enemy_11_hard": "origin_robe",       # 混沌の初源：防御を非常に大きく上げる
    "enemy_11_veryhard": "silence_blade", # 永遠の沈黙：攻撃を非常に大きく上げる
}

# ---------------------------------------------------------------------------
# 剣の属性（宝箱から出た剣に、確率で付く。付いた属性は、敵に状態異常としてかかる）
#   宝箱の装備が剣（SWORDS）だったとき、WEAPON_ATTR_CHANCE の確率で属性が付く。
#   付く数は WEAPON_ATTR_COUNTS の比率で1〜3個（同じ属性は重ならない）。
#   黒炎・陰・影はハード以上でだけ付く（ATTR_MIN_DIFFICULTY）。
#   発動率は、剣を手に入れたときにランダムで決まり、そのあと変わらない。
#     毒・火・雷：3つで1つの発動率（ATTR_GROUP_CHANCE の範囲）。発動したら、付いている中から1つ
#     黒炎・陰・影：それぞれ別の発動率（ATTR_SOLO_CHANCE の範囲）。毒・火・雷と同時に発動することもある
#   発動の抽選は、自分の攻撃が当たったとき（ミス・回避されたときは発動しない）。剣1本ごとに別々に抽選する。
#
#   効果（「その攻撃の合計ダメージ」を元にした追加ダメージは、敵のターンのはじめに入る。敵の防御では減らない）
#     毒  ：合計ダメージの50%を3ターン、そのあと25%を2ターン
#     火  ：合計ダメージの70%を3ターン
#     黒炎：合計ダメージの60%を3ターン、そのあと5%を10ターン
#     雷  ：敵が1〜2ターン動けない（immune に thunder がある敵には効かない）
#     陰  ：敵の次の1回の攻撃が、5〜8割（ランダム）のダメージになる
#     影  ：敵の攻撃を30%の確率でよける（敵の攻撃2回分）
#   同じ属性がもう一度かかったときは、重ならず、そのときのダメージを元に最初からやり直す
# ---------------------------------------------------------------------------
SWORDS = ("wood_sword", "steel_sword", "holy_sword")
WEAPON_ATTR_CHANCE = {"easy": 0.40, "normal": 0.60, "hard": 0.70, "very_hard": 0.95}
WEAPON_ATTR_COUNTS = {                       # 1個・2個・3個の比率
    "easy":      (60, 35, 5),
    "normal":    (55, 35, 10),
    "hard":      (45, 40, 15),
    "very_hard": (40, 40, 20),
}
ATTR_GROUP = ("poison", "fire", "thunder")
ATTR_SOLO = ("black_flame", "darkness", "shadow")
ATTR_MIN_DIFFICULTY = {"black_flame": "hard", "darkness": "hard", "shadow": "hard"}
ATTR_GROUP_CHANCE = (0.05, 0.40)
ATTR_SOLO_CHANCE = (0.01, 0.20)
ATTR_EFFECTS = {
    # dot: [(合計ダメージに対する割合, ターン数), ...] を順に
    "poison":      {"dot": [(0.50, 3), (0.25, 2)]},
    "fire":        {"dot": [(0.70, 3)]},
    "black_flame": {"dot": [(0.60, 3), (0.05, 10)]},
    "thunder":     {"turns_min": 1, "turns_max": 2},
    "darkness":    {"turns": 1, "damage_min": 0.5, "damage_max": 0.8},
    "shadow":      {"turns": 2, "evade_rate": 0.30},
}

# ---------------------------------------------------------------------------
# 宝箱
# ---------------------------------------------------------------------------
TREASURE_CHANCE = 0.70        # ステージクリア時に宝箱が出る確率
TREASURE_COUNT = (1, 3)       # 出る個数（同じ確率で選ぶ）
TREASURE_ITEM_RATE = 0.70     # 1個の中身がアイテムになる確率（残りは装備）
