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
STAGE_HEAL_RATE = 0.5       # ステージをクリアしたときに回復する割合（減っているHPに対して）

# ---------------------------------------------------------------------------
# 難易度
#   enemy_hp_atk : 敵のHP・攻撃力にかける倍率
#   enemy_def    : 敵の防御力にかける倍率
#   ability      : アビリティポイントにかける倍率
#   rank         : 「◯◯以上」の判定に使う順位（大きいほど難しい）
#   敵の倍率は、ベリーハードを HP・攻撃力 3.6倍・防御力 2.4倍とし、イージー（1倍）とのあいだを
#   同じ比率で上がるように決めた（ノーマル・ハードは小数第2位で丸め）。
#   そのあと味方にレベルと必殺技が付いたので、イージーは1.1倍、ノーマル以上は1.2倍に上げた。
#   さらに剣の属性・アイテムが増えたので、イージー1.05倍・ノーマル1.1倍・ハードとベリーハード1.2倍に上げた（下の表はその値）
# ---------------------------------------------------------------------------
DIFFICULTIES = [
    {"id": "easy",      "name": "イージー",     "rank": 0, "enemy_hp_atk": 1.155, "enemy_def": 1.155,  "ability": 1.0},
    {"id": "normal",    "name": "ノーマル",     "rank": 1, "enemy_hp_atk": 2.046, "enemy_def": 1.782, "ability": 1.5},
    {"id": "hard",      "name": "ハード",       "rank": 2, "enemy_hp_atk": 3.384, "enemy_def": 2.592, "ability": 2.0},
    {"id": "very_hard", "name": "ベリーハード", "rank": 3, "enemy_hp_atk": 5.184, "enemy_def": 3.456, "ability": 3.0},
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
    # 凍え：次の自分の攻撃（連打）の時間が slow_seconds 秒みじかくなる。氷よけの指輪で半分
    "freeze":      {"icon": "❄️", "name": "凍え", "turns": 1, "slow_seconds": 1.0, "resistible": True},
    # 突風：次の自分の攻撃（連打）のあいだ、敵が風でゆれて当てにくい
    "wind":        {"icon": "🌪️", "name": "突風", "turns": 1, "resistible": False},
}

# ---------------------------------------------------------------------------
# 敵（イージーの値。ほかの難易度は DIFFICULTIES の倍率をかける）
#   決め方：Lv.1〜5 は最初の数値。Lv.6 からは1ステージごとに HP・攻撃力を約1.3倍にした。
#           そのうえで HP・攻撃力・防御力を、Lv.1 はそのまま、Lv.10 は1.1倍にし、あいだは Lv に比例して
#           少しずつ上げている（Lv.n は 1 + 0.1 × (n−1) ÷ 9 倍。Lv.11 は Lv.10 と同じ1.1倍）。
#           HP は整数、攻撃力・防御力は小数第1位で四捨五入
#           さらに、1ターンの連打が平均50回くらいになるとわかったので、HP をすべて2倍にした（攻撃力・防御力はそのまま）
#   image       : assets/story/enemies/ の中のファイル名（当たりマスクは hitmasks/ の同じ名前の .png）
#   cutout      : True なら背景を透過した画像。背景は scene の画像とCSSで描く
#   scene       : 背景の種類（story_assets の _SCENE_LAYERS のキー。"image" は画像そのものが背景）
#   floating    : 宙に浮かせて表示する（足元の影を出さない）
#   gimmicks    : 使う状態異常。後から別のギミックを足すときはここに書く
#   immune      : 効かない剣の属性（Lv.9 以降と宇宙龍は「天変地異」の特性で雷が効かない）。書いていなければ全部効く
#   difficulties: 出てくる難易度。None ならすべて。
#                 ハードは11ステージ（最後が混沌の初源）、ベリーハードは12ステージ（混沌の初源のあとに永遠の沈黙）
#   lines       : 敵のターンに出す一言（毎回この中から1つ選ぶ）
#   effect      : 敵の攻撃エフェクトの種類と色（web/story/index.html の EFFECTS）
#   meteor_scene: メテオを撃つときに画面いっぱいに出す絵と技名（focus は横長の絵のどこを見せるか）。
#                 メテオを使う敵（gimmicks に meteor がある敵）だけで出る
# ---------------------------------------------------------------------------
_ALL = None
ENEMIES = [
    {"lv": 1, "name": "薄汚れたゾンビ", "hp": 200, "atk": 1, "def": 1,
     "image": "enemy_01.webp", "cutout": True, "scene": "corridor", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["ウゥ……アァ……", "……ニク……", "グアァァッ！"], "effect": {"type": "claw", "color": "#9db36b"}},
    {"lv": 2, "name": "呪われた戦士", "hp": 284, "atk": 1, "def": 2,
     "image": "enemy_02.webp", "cutout": True, "scene": "prison", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["呪いは……解けぬ……", "この剣、錆びてはおらぬ", "ここから先へは通さん"], "effect": {"type": "slash", "color": "#d8d2c4"}},
    {"lv": 3, "name": "幽霊の暗殺者", "hp": 408, "atk": 2, "def": 3.1,
     "image": "enemy_03.webp", "cutout": True, "scene": "catacomb", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["……背中が、がら空きだ", "影は斬れまい", "音もなく、消えろ"], "effect": {"type": "ghost", "color": "#8fd8ff"}},
    {"lv": 4, "name": "骨の魔術師", "hp": 578, "atk": 2.1, "def": 4.1,
     "image": "enemy_04.webp", "cutout": True, "scene": "altar", "floating": False, "gimmicks": ["freeze"], "difficulties": _ALL,
     "lines": ["我が魔術の糧となれ", "骨の髄まで凍えるがいい", "クク……愚かな"], "effect": {"type": "magic", "color": "#b26bff"}},
    {"lv": 5, "name": "深淵の従者", "weak": "light", "resist_elem": "dark", "hp": 794, "atk": 3.1, "def": 6.3,
     "image": "enemy_05.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["深淵へ……引きずり込んでやる", "シャアアッ！", "主のもとへは行かせぬ"], "effect": {"type": "whip", "color": "#e0483e"}},
    {"lv": 6, "name": "死霊の将軍", "weak": "light", "resist_elem": "ice", "hp": 1034, "atk": 4.1, "def": 8.4,
     "image": "enemy_06.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["我が軍勢の前にひれ伏せ", "死してなお、我は戦う", "この一撃、受けてみよ"], "effect": {"type": "slash", "color": "#a9c4b0"}},
    {"lv": 7, "name": "悪魔の貴族", "weak": "ice", "resist_elem": "fire", "hp": 1366, "atk": 5.4, "def": 10.7,
     "image": "enemy_07.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": ["poison"], "difficulties": _ALL,
     "lines": ["下賤の者が、我に触れるな", "地獄の炎で焼かれるがいい", "フフ……退屈させるな"], "effect": {"type": "fire", "color": "#ff7a2a"}},
    {"lv": 8, "name": "半神の魔王", "weak": "dark", "resist_elem": "thunder", "hp": 1790, "atk": 7.1, "def": 12.9,
     "image": "enemy_08.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": ["thunder"], "difficulties": _ALL,
     "lines": ["玉座から動くまでもない", "神の雷、その身で知れ", "ひざまずけ"], "effect": {"type": "thunder", "color": "#ffd84a"}},
    {"lv": 9, "name": "災厄の代行者", "weak": "light", "resist_elem": "dark", "hp": 2374, "atk": 9.4, "def": 16.3,
     "image": "enemy_09.webp", "meteor_scene": {"name": "災厄の流星", "image": "meteor_09.webp", "focus": "50% 50%"}, "cutout": True, "scene": "nebula", "floating": True, "immune": ["thunder"], "gimmicks": ["poison", "thunder", "fire"], "difficulties": _ALL,
     "lines": ["すべては無に還る", "災いは、選ばない", "抗うな。苦しむだけだ"], "effect": {"type": "void", "color": "#9a6bff"}},
    {"lv": 10, "name": "終焉の創造主", "weak": "dark", "resist_elem": "light", "hp": 3102, "atk": 12.2, "def": 19.8,
     "image": "enemy_10.webp", "meteor_scene": {"name": "終焉の星墜", "image": "meteor_10.webp", "focus": "55% 45%"}, "cutout": False, "scene": "image", "floating": False, "immune": ["thunder"], "gimmicks": ["poison", "thunder", "fire", "meteor"], "difficulties": _ALL,
     "lines": ["世界を創り、そして終わらせる", "星の一つも、我が意のまま", "よくぞここまで来た。だが、ここで終わりだ"], "effect": {"type": "cosmic", "color": "#a8d4ff"}},
    {"lv": 11, "name": "混沌の初源", "weak": "dark", "resist_elem": "light", "hp": 4026, "atk": 15.8, "def": 23.1,
     "image": "enemy_11_hard.webp", "meteor_scene": {"name": "原初の流星雨", "image": "meteor_11_hard.webp", "focus": "72% 45%"}, "cutout": False, "scene": "image", "floating": False, "immune": ["thunder"], "gimmicks": ["poison", "thunder", "fire", "meteor", "darkness"], "difficulties": ["hard", "very_hard"],
     "lines": ["すべてはわたしから生まれた", "還りなさい、始まりの光へ", "混沌こそ、世界の母"], "effect": {"type": "radiance", "color": "#ffd27a"}},
    {"lv": 11, "name": "永遠の沈黙", "weak": "thunder", "resist_elem": "ice", "hp": 4026, "atk": 15.8, "def": 23.1,
     "image": "enemy_11_veryhard.webp", "meteor_scene": {"name": "無音の墜星", "image": "meteor_11_veryhard.webp", "focus": "55% 50%"}, "cutout": False, "scene": "image", "floating": False, "immune": ["thunder"], "gimmicks": ["poison", "thunder", "fire", "meteor", "darkness", "shadow"], "difficulties": ["very_hard"],
     "lines": ["…………", "音も、光も、ここには届かない", "沈め"], "effect": {"type": "silence", "color": "#6f8cff"}},
]

# ---------------------------------------------------------------------------
# エクストラステージ：極点の宇宙龍（混沌の初源・永遠の沈黙の使い。各ステージを見回っている）
#   ステージをクリアするたびに EXTRA_CHANCE の確率で、次のステージの前に現れる（1回の挑戦で1度まで）
#   「にげる」で戦わずに先へ進める（負けにならない）。倒すと超激レア装備（ULTRA_REWARDS）
#   強さは難易度に関係なく固定（ベリーハードのステージ6と同じ：Lv.6 の HP1034・攻撃4.1 × 5.184、防御8.4 × 3.456）
#   fit / focus : 横長の絵なので、画面を埋めるように拡大し（cover）、focus の位置を中心に見せる
# ---------------------------------------------------------------------------
EXTRA_CHANCE = 0.01
EXTRA_ENEMY = {
    "lv": "???", "name": "極点の宇宙龍", "weak": "ice", "resist_elem": "fire", "title": "災厄と創造の統合者", "hp": 5360, "atk": 21.3, "def": 29.0, "fixed_stats": True,
    "image": "enemy_extra.webp", "cutout": False, "scene": "image", "floating": False, "fit": "cover", "focus": "64% 50%",
    "immune": ["thunder"], "gimmicks": ["black_flame", "shadow", "darkness"], "difficulties": None,
    "lines": ["……見つけたぞ、小さき者", "我が主の領域を荒らすか", "星ごと呑み込んでくれよう"],
    "effect": {"type": "cosmic", "color": "#c49bff"},
    # 覚醒：HPが hp_rate 以下になると、地鳴りとともに姿が変わる（1回の戦闘で1度だけ）
    #   heal_rate : 減っているHPのこの割合を回復する
    #   stat_rate : HP以外（攻撃力・防御力）は、ベリーハードの最後の敵（永遠の沈黙）のこの倍にする
    #   special   : 覚醒して最初の攻撃で必ず使い、そのあとは chance の確率で使う大技「術式解除＋業火」。
    #               アイテムでかけた守り（封炎の巻物・防御アップ）を消してから、最大HPの damage_rate の
    #               割合ダメージ（防御で減らない）を与え、必ず黒炎にする。かかった黒炎は、黒炎払い・浄化で治せる
    "awaken": {
        "hp_rate": 0.5, "heal_rate": 0.3, "stat_rate": 1.05,
        "name": "極点の宇宙龍・覚醒", "title": "星を喰らう終焉",
        "image": "enemy_extra_awake.webp", "focus": "45% 45%",
        "lines": ["……目覚めの時だ", "星々よ、我が糧となれ", "終わりを見せてやろう"],
        "effect": {"type": "cosmic", "color": "#ff7a3a"},
        "special": {"name": "破術・終焉の黒き業火", "chance": 0.07, "damage_rate": 0.2, "image": "extra_awake_attack.webp",
                    "line": "……小賢しい術ごと、黒き炎に還れ"},
    },
}

# ---------------------------------------------------------------------------
# 味方
#   unlock    : None なら最初から使える。
#               min_difficulty 以上の難易度で stage をクリアしたとき、chance の確率で仲間になる
#               {"extra": True} はエクストラステージ（極点の宇宙龍）を倒したときに必ず仲間になる
#   abilities : アビリティポイントの合計が ABILITY_THRESHOLDS に達するたびに順に解放
#               name があれば名前つきのアビリティ。immune はかからなくなる状態異常
#   image     : assets/story/allies/（全身）と assets/story/ally_icons/（顔）の中のファイル名
#   hp/atk/def: Lv.1 のステータス。max は Lv.10 のステータス（あいだは STAT_CURVE の曲線で上がる）
#   skill     : 必殺技（下の「必殺技」を参照）
#
# レベル（全員 Lv.1 から Lv.10 まで）
#   アビリティポイントと同じポイントで上がる（挑戦が終わるたびに、クリアしたステージ数 × 0.1 × 難易度の倍率）。
#   Lv.10 になるのに要るポイントは、Lv.1 のキャラ（コウ）が LEVEL_POINTS[0]（ベリーハード全クリア約30回分）、
#   Lv.10 のキャラ（ルナ）が LEVEL_POINTS[1]（約50回分）。あいだのキャラは順番に合わせて決める。
#   レベル n に要る合計 = Lv.10 に要る合計 × ((n−1) ÷ 9) ^ LEVEL_CURVE（後のレベルほど多く要る）
#   レベル n のステータス = Lv.1 + (Lv.10 − Lv.1) × ((n−1) ÷ 9) ^ STAT_CURVE（後のレベルほど大きく上がる）
#
# 必殺技（skill）
#   攻撃で敵に当たった回数（コンボ）が charge に達すると、戦闘画面の味方のアイコンを押して使える。
#   自分のターンに1回。アイテムとは別で、使ったあともそのターンに攻撃できる。
#   チャージはステージをまたいで残る（負けてやり直すときは、そのステージを始めたときの値に戻る）。
#   charge は「1ターン50回当てる」として、コウの5ターン分（250）を基準に決めた。最短でも4ターン分。
#   （はじめは25回で決めていたが、実際は平均50回くらいなので、charge を2倍、攻撃系の power も2倍にした。
#     そのうえで弱めだったコウ・アーサー・エリナの power を少し上げた）
#   type:
#     strike : 攻撃力 × power のダメージ。pierce なら敵の防御で減らない。guard ターン防御2倍、stun ターン敵が動けない
#     guard  : 最大HPの heal_rate を回復して、guard ターン防御力2倍
#     boost  : 次の攻撃（連打）のダメージが mult 倍
#     barrier: 敵の攻撃 blocks 回を無効にして、状態異常（毒・雷・火・黒炎）を治す
#     break  : turns ターン（敵のターンの回数）のあいだ、敵の防御を0にする
#   anim : 戦闘画面の演出（web/story/index.html の SKILL_FX）
#   scene: 必殺技の絵（assets/story/skills/）。grand なら特別演出（アステル）
# ---------------------------------------------------------------------------
STARTER_ALLIES = (1, 2, 3)       # 最初から仲間（コウ・マリ・アレックス）。前から遊んでいる人にも足す
ABILITY_THRESHOLDS = (5, 10, 25)
ABILITY_POINT_PER_STAGE = 0.1     # クリアしたステージ1つにつき 0.1（全クリアで 1.0）
LEVEL_MAX = 10
LEVEL_POINTS = (108, 180)         # Lv.10 に要るポイント（コウ ＝ 3.6 × 30回、ルナ ＝ 3.6 × 50回）
LEVEL_CURVE = 2.0
STAT_CURVE = 1.3

ALLIES = [
    {"lv": 1,  "name": "平凡な農民、コウ",         "hp": 10, "atk": 1, "def": 1, "max": {"hp": 34, "atk": 7, "def": 8},  "image": "ally_01.webp", "magic": {"mp": (8, 30), "mag": (1, 5), "crit": 0.05, "spells": ["quick", "brave", "war_cry"]}, "class": "fighter", "unlock": None,
     "abilities": [{"stat": "atk", "value": 1}, {"stat": "atk", "value": 1}, {"stat": "def", "value": 3}], "skill": {"name": "渾身のひと振り", "type": "strike", "charge": 250, "power": 50, "anim": "kou", "scene": {"image": "skill_kou.webp", "focus": "50% 30%"}, "text": "大きく振りかぶって一撃。攻撃力×50 のダメージ"}},
    {"lv": 2,  "name": "新米自警団員、マリ",       "hp": 11, "atk": 2, "def": 1, "max": {"hp": 35, "atk": 7, "def": 9},  "image": "ally_02.webp", "magic": {"mp": (15, 50), "mag": (2, 12), "crit": 0.03, "spells": ["heal", "cure", "mana_heal", "heal_all", "revive"]}, "class": "magic", "unlock": None,
     "abilities": [{"stat": "def", "value": 1}, {"stat": "def", "value": 1}, {"stat": "atk", "value": 4}], "skill": {"name": "守りの誓い", "type": "guard", "charge": 200, "heal_rate": 0.2, "guard": 3, "anim": "mari", "scene": {"image": "skill_mari.webp", "focus": "45% 30%"}, "text": "光の盾でHPを最大の20%回復し、3ターン防御力2倍"}},
    {"lv": 3,  "name": "新兵中隊長、アレックス",   "hp": 13, "atk": 2, "def": 3, "max": {"hp": 40, "atk": 8, "def": 10},  "image": "ally_03.webp", "magic": {"mp": (12, 40), "mag": (2, 10), "crit": 0.06, "spells": ["brave", "war_cry", "haste_all"]}, "class": "fighter", "unlock": None,
     "abilities": [{"stat": "hp", "value": 3}, {"stat": "hp", "value": 3}, {"stat": "atk", "value": 3}], "skill": {"name": "突撃号令", "type": "boost", "charge": 200, "mult": 2, "anim": "alex", "scene": {"image": "skill_alex.webp", "focus": "45% 25%"}, "text": "号令で奮い立ち、次の攻撃のダメージが2倍"}},
    {"lv": 4,  "name": "魔導戦術家、セリス",       "hp": 16, "atk": 2, "def": 5, "max": {"hp": 45, "atk": 6, "def": 18},  "image": "ally_04.webp", "magic": {"mp": (25, 90), "mag": (3, 20), "crit": 0.02, "spells": ["fire", "ice", "mana_heal", "thunderbolt", "explosion"]}, "class": "magic", "unlock": {"min_difficulty": "normal", "stage": 3, "chance": 0.30},
     "abilities": [{"stat": "atk", "value": 1}, {"stat": "atk", "value": 1}, {"stat": "hp", "value": 10}], "skill": {"name": "魔法障壁", "type": "barrier", "charge": 250, "blocks": 2, "anim": "celis", "scene": {"image": "skill_celis.webp", "focus": "40% 35%"}, "text": "魔法陣の障壁で敵の攻撃2回を無効にし、状態異常も治す"}},
    {"lv": 5,  "name": "先鋭近衛騎士、アーサー",   "hp": 22, "atk": 4, "def": 4, "max": {"hp": 60, "atk": 11, "def": 13},  "image": "ally_05.webp", "magic": {"mp": (15, 55), "mag": (2, 14), "crit": 0.05, "spells": ["protect", "guard_all", "brave"]}, "class": "fighter", "unlock": {"min_difficulty": "hard", "stage": 1, "chance": 0.30},
     "abilities": [{"stat": "def", "value": 2}, {"stat": "def", "value": 2}, {"stat": "hp", "value": 15}], "skill": {"name": "聖盾撃", "type": "strike", "charge": 300, "power": 60, "guard": 2, "anim": "arthur", "scene": {"image": "skill_arthur.webp", "focus": "40% 25%"}, "text": "聖なる盾ごと突撃。攻撃力×60 のダメージと、2ターン防御力2倍"}},
    {"lv": 6,  "name": "古代魔導研究者、エリナ",   "hp": 30, "atk": 6, "def": 3, "max": {"hp": 70, "atk": 17, "def": 8},  "image": "ally_06.webp", "magic": {"mp": (30, 110), "mag": (4, 24), "crit": 0.02, "spells": ["rune_bolt", "blizzard", "heal", "explosion", "meteor"]}, "class": "magic", "unlock": {"min_difficulty": "normal", "stage": 6, "chance": 0.40},
     "abilities": [{"stat": "hp", "value": 5}, {"stat": "hp", "value": 5}, {"stat": "def", "value": 8}], "skill": {"name": "古代魔法・崩壊", "type": "strike", "charge": 350, "power": 70, "pierce": True, "anim": "erina", "scene": {"image": "skill_erina.webp", "focus": "50% 33%"}, "text": "古代文字が崩れ落ちる。攻撃力×70 の防御無視ダメージ"}},
    {"lv": 7,  "name": "王宮近衛隊長、ガイウス",   "hp": 45, "atk": 10, "def": 6, "max": {"hp": 95, "atk": 26, "def": 14},  "image": "ally_07.webp", "magic": {"mp": (10, 35), "mag": (1, 8), "crit": 0.1, "spells": ["gale_stance", "brave", "war_cry"]}, "class": "fighter", "unlock": {"min_difficulty": "normal", "stage": 7, "chance": 0.20},
     "abilities": [{"stat": "atk", "value": 2}, {"stat": "atk", "value": 2}, {"stat": "atk", "value": 6}], "skill": {"name": "百裂剣", "type": "strike", "charge": 350, "power": 80, "anim": "gaius", "scene": {"image": "skill_gaius.webp", "focus": "30% 22%"}, "text": "目にも止まらぬ百の斬撃。攻撃力×80 のダメージ"}},
    {"lv": 8,  "name": "魔導工学の至高者、レイノ", "hp": 63, "atk": 13, "def": 15, "max": {"hp": 125, "atk": 28, "def": 32}, "image": "ally_08.webp", "magic": {"mp": (30, 120), "mag": (4, 26), "crit": 0.02, "spells": ["thunder", "rune_bolt", "cure", "thunderbolt", "meteor"]}, "class": "magic", "unlock": {"min_difficulty": "hard", "stage": 5, "chance": 0.60},
     "abilities": [{"stat": "def", "value": 3}, {"stat": "def", "value": 3}, {"stat": "atk", "value": 8}], "skill": {"name": "魔導砲", "type": "strike", "charge": 400, "power": 70, "pierce": True, "stun": 1, "anim": "reino", "scene": {"image": "skill_reino.webp", "focus": "65% 30%"}, "text": "魔導砲の光線。攻撃力×70 の防御無視ダメージと、敵を1ターン動けなくする（雷が効かない敵にも効く）"}},
    {"lv": 9,  "name": "概念の卵、ガレン",         "hp": 73, "atk": 20, "def": 19, "max": {"hp": 150, "atk": 36, "def": 40}, "image": "ally_09.webp", "magic": {"mp": (20, 80), "mag": (3, 18), "crit": 0.04, "spells": ["protect", "guard_all", "haste_all"]}, "class": "fighter", "unlock": {"min_difficulty": "hard", "stage": 5, "chance": 0.30},
     "abilities": [{"stat": "hp", "value": 10}, {"stat": "hp", "value": 10}, {"stat": "def", "value": 15}], "skill": {"name": "概念崩し", "type": "break", "charge": 250, "turns": 3, "anim": "garen", "scene": {"image": "skill_garen.webp", "focus": "45% 28%"}, "text": "敵の「守る」という概念を壊し、3ターン敵の防御を0にする"}},
    {"lv": 10, "name": "至高の光帝、ルナ",         "hp": 100, "atk": 33, "def": 35, "max": {"hp": 160, "atk": 50, "def": 52}, "image": "ally_10.webp", "magic": {"mp": (35, 130), "mag": (5, 30), "crit": 0.03, "spells": ["holy", "high_heal", "heal_all", "full_heal", "holy_all"]}, "class": "magic", "unlock": {"min_difficulty": "very_hard", "stage": 7, "chance": 0.20},
     "abilities": [{"stat": "atk", "value": 3}, {"stat": "atk", "value": 3}, {"stat": "hp", "value": 40}], "skill": {"name": "光帝の裁き", "type": "strike", "charge": 500, "power": 120, "pierce": True, "anim": "luna", "scene": {"image": "skill_luna.webp", "focus": "50% 26%"}, "text": "天から光の柱が降りる。攻撃力×120 の防御無視ダメージ"}},
    # エクストラステージ（極点の宇宙龍）を倒すと、必ず仲間になる（unlock の extra）。いちばん強いキャラ
    {"lv": 11, "name": "極点の宇宙龍、アステル",   "hp": 120, "atk": 40, "def": 42, "max": {"hp": 200, "atk": 62, "def": 65},
     "image": "ally_11.webp", "magic": {"mp": (40, 150), "mag": (5, 32), "crit": 0.08, "spells": ["war_cry", "guard_all", "haste_all"]}, "class": "fighter", "unlock": {"extra": True, "chance": 1.0},
     # アビリティ3「聖霊の加護」：HP+50 と、基本の状態異常（毒・雷・火）にかからない
     "abilities": [{"stat": "atk", "value": 4}, {"stat": "def", "value": 4},
                   {"stat": "hp", "value": 50, "name": "聖霊の加護", "immune": ["poison", "thunder", "fire"]}],
     "skill": {"name": "創世の咆哮", "type": "strike", "charge": 550, "power": 140, "pierce": True, "break": 2, "anim": "astel",
               # 必殺技の特別演出（grand）：暗転 → 星が集まり魔法陣 → 絵 → 技名 → 光の咆哮
               "scene": {"image": "skill_astel.webp", "grand": True, "reading": "そうせいのほうこう", "sub": "GENESIS ROAR"},
               "text": "銀河を呑む咆哮。攻撃力×140 の防御無視ダメージと、2ターン敵の防御を0にする"}},
]

# ---------------------------------------------------------------------------
# アイテム（ポーション類は状態異常もすべて治す）
#   heal_rate : 最大HPに対する回復量（1.0 で全回復）
#   icon      : 画面に出す絵文字（装備・状態異常も同じ）
#   guard     : 防御力2倍が続くターン数
#   atk_bonus : 攻撃力に足す値（atk_turns ターン＝自分の攻撃 atk_turns 回のあいだ）
#   weight    : 宝箱でアイテムが出たときの選ばれやすさ
#   cure      : 治す状態異常（ポーション類はHPを回復するだけで、状態異常は治さない）
#   ward      : そのターン数のあいだ、新しく黒炎にかからない（すでにかかっている黒炎は続く）
#   where     : 宝箱から出る条件 {難易度: そのステージ以上}。書いていなければ、いつでも出る
#   最初に持っているのは、where のないアイテムを INITIAL_ITEM_COUNT 個ずつ
# 自分のターンに1つだけ使え、使ったあとも攻撃できる
# ---------------------------------------------------------------------------
MAX_CARRY_ITEMS = 30
GUARD_MULTIPLIER = 2.0
INITIAL_ITEM_COUNT = 10     # 最初にホームに持っているアイテムの数（全種類それぞれ）

ITEMS = [
    {"id": "potion",       "icon": "🧪", "name": "ポーション",       "heal_rate": 0.3, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 40},
    {"id": "guard_up",     "icon": "🛡️", "name": "防御アップ",       "heal_rate": 0.0, "cure": [], "guard": 3, "atk_bonus": 0, "atk_turns": 0, "weight": 25},
    {"id": "atk_up",       "icon": "💪", "name": "攻撃力アップ",     "heal_rate": 0.0, "cure": [], "guard": 0, "atk_bonus": 3, "atk_turns": 3, "weight": 20},
    {"id": "hi_potion",    "icon": "⚗️", "name": "ハイポーション",   "heal_rate": 0.6, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 20},
    {"id": "mega_potion",  "icon": "💖", "name": "メガポーション",   "heal_rate": 1.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 10},
    {"id": "elixir",       "icon": "✨", "name": "エリクサー",       "heal_rate": 1.0, "mp_rate": 1.0, "cure": [], "guard": 3, "atk_bonus": 0, "atk_turns": 0, "weight": 5},
    {"id": "panacea",      "icon": "🌿", "name": "万能薬",           "heal_rate": 0.0, "cure": ["poison", "thunder", "fire", "freeze"], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 25},
    {"id": "seal_scroll",  "icon": "📜", "name": "封炎の巻物",       "heal_rate": 0.0, "cure": [], "ward": 3, "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 10,
     "where": {"hard": 5, "very_hard": 5}},
    {"id": "purge_scroll", "icon": "🔥", "name": "黒炎払いの巻物",   "heal_rate": 0.0, "cure": ["black_flame"], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 10,
     "where": {"normal": 7, "hard": 5, "very_hard": 5}},
    {"id": "holy_circle",  "icon": "🔯", "name": "浄化の魔法陣",     "heal_rate": 0.0, "cure": ["poison", "thunder", "fire", "black_flame", "freeze", "wind"], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 5,
     "where": {"easy": 10, "normal": 9, "hard": 8, "very_hard": 7}},
    # アステルの援護のあとにだけ出る、特別なアイテム（宝箱・ログインボーナス・最初の配布には出ない）
    #   special   : 特別なアイテム（宝箱などから出ない）
    #   home_use  : ホーム（倉庫とリュックの画面）で使う。"level_up" はいまのキャラのレベルを1上げる
    #   assist    : 戦闘で使うと、アステルの援護を呼ぶ（この戦闘のあいだ、精霊の加護も受けられる）
    {"id": "white_scale",  "icon": "🐉", "name": "白龍の鱗",         "heal_rate": 0.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0,
     "special": True, "home_use": "level_up"},
    {"id": "spirit_feather", "icon": "🪶", "name": "精霊の羽",       "heal_rate": 1.0, "mp_rate": 1.0, "revive": 1.0,
     "cure": ["poison", "thunder", "fire", "black_flame", "darkness", "shadow", "freeze"],
     "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "special": True, "assist": True},
    # ---- 魔法といっしょに増えたアイテム -------------------------------------------------
    #   mp_rate   : 最大MPに対する回復量          revive : 倒れそうになったときに使うと、最大HPのこの割合で立ち上がる
    #   crit      : 会心率に足す値（crit_turns ターン＝自分の攻撃の回数）
    #   mag_mult  : 魔力にかける倍率（mag_turns ターン＝自分の行動の回数）
    #   haste     : 連打の時間に足す秒数（haste_turns ターン＝自分の攻撃の回数）
    #   new_item  : 最初の配布（INITIAL_ITEM_COUNT 個ずつ）には入れない
    #   boss      : 宝箱・ログインボーナスには出ない。ボス（最後のステージ・エクストラ）を倒したときだけ
    {"id": "ether",          "icon": "💧", "name": "エーテル",         "heal_rate": 0.0, "mp_rate": 0.3, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 15, "new_item": True},
    {"id": "hi_ether",       "icon": "🔷", "name": "ハイエーテル",     "heal_rate": 0.0, "mp_rate": 1.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "new_item": True, "boss": True},
    {"id": "last_elixir",    "icon": "🌈", "name": "ラストエリクサー", "heal_rate": 1.0, "mp_rate": 1.0, "all": True,
     "cure": ["poison", "thunder", "fire", "black_flame", "darkness", "shadow", "freeze"], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "new_item": True, "boss": True},
    {"id": "life_leaf",      "icon": "🍃", "name": "いのちの葉",       "heal_rate": 0.0, "revive": 0.3, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 8, "new_item": True},
    {"id": "phoenix_down",   "icon": "🪶", "name": "不死鳥の羽",       "heal_rate": 0.0, "revive": 1.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "new_item": True, "boss": True},
    {"id": "crit_potion",    "icon": "⚡", "name": "会心の薬",         "heal_rate": 0.0, "crit": 0.15, "crit_turns": 3, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 10, "new_item": True},
    {"id": "magic_water",    "icon": "🔮", "name": "魔力の水",         "heal_rate": 0.0, "mag_mult": 1.5, "mag_turns": 3, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 10, "new_item": True},
    {"id": "gale_sandglass", "icon": "⏳", "name": "疾風の砂時計",     "heal_rate": 0.0, "haste": 1.0, "haste_turns": 3, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 8, "new_item": True},
    # 魔導書：倉庫で「使う」と、いまのキャラが spell の魔法を覚える（1人 MAX_BOOK_SPELLS つまで）。リュックには入れられない
    {"id": "book_fire",    "icon": "📕", "name": "炎の魔導書",   "spell": "explosion",   "heal_rate": 0.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "home_use": "learn", "boss": True, "new_item": True},
    {"id": "book_ice",     "icon": "📘", "name": "氷の魔導書",   "spell": "blizzard",    "heal_rate": 0.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "home_use": "learn", "boss": True, "new_item": True},
    {"id": "book_thunder", "icon": "📒", "name": "雷の魔導書",   "spell": "thunderbolt", "heal_rate": 0.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "home_use": "learn", "boss": True, "new_item": True},
    {"id": "book_light",   "icon": "📔", "name": "光の魔導書",   "spell": "holy",        "heal_rate": 0.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "home_use": "learn", "boss": True, "new_item": True},
    {"id": "book_dark",    "icon": "📓", "name": "闇の魔導書",   "spell": "darkness",    "heal_rate": 0.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "home_use": "learn", "boss": True, "new_item": True},
    {"id": "book_heal",    "icon": "📗", "name": "癒しの魔導書", "spell": "heal",        "heal_rate": 0.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "home_use": "learn", "boss": True, "new_item": True},
    {"id": "book_revive",  "icon": "📙", "name": "蘇生の魔導書", "spell": "revive",      "heal_rate": 0.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "home_use": "learn", "boss": True, "new_item": True},
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
MAX_ATTR_WEAPONS = 1        # 属性の付いた剣は、1キャラ1本まで
ACCESSORY_RANK = "accessory"
ACCESSORY_RANKS = ("accessory", "charm")   # アクセサリのわくに付けるランク

EQUIP_RANKS = {
    "normal":    {"name": "ノーマル",   "weight": 60, "min_stage": 1, "min_difficulty": "easy"},
    "rare":      {"name": "レア",       "weight": 30, "min_stage": 3, "min_difficulty": "easy"},
    "epic":      {"name": "激レア",     "weight": 10, "min_stage": 7, "min_difficulty": "normal"},
    "accessory": {"name": "アクセサリ", "weight": 30, "min_stage": 5, "min_difficulty": "normal"},
    # 強さがランダムなアクセサリ（攻撃・防御・体力）。どの難易度・ステージでも出る。種類は難易度で決まる
    "charm":     {"name": "アクセサリ", "weight": 30, "min_stage": 1, "min_difficulty": "easy"},
    # 超激レアは宝箱からは出ない（weight 0）。特別な敵を倒したときのごほうび（ULTRA_REWARDS）だけ
    "ultra":     {"name": "超激レア",   "weight": 0,  "min_stage": 99, "min_difficulty": "very_hard"},
}

EQUIPMENT = [
    {"id": "wood_sword",     "icon": "🗡️", "name": "木の剣",         "rank": "normal",    "atk": 1,  "def": 0,  "hp": 0,  "resist": None},
    {"id": "leather_shield", "icon": "🛡️", "name": "革の盾",         "rank": "normal",    "atk": 0,  "def": 2,  "hp": 0,  "resist": None},
    {"id": "travel_cloak",   "icon": "🧥", "name": "旅人のマント",   "rank": "normal",    "atk": 0,  "def": 0,  "hp": 5,  "resist": None},
    # 魔法使い向け：mag（魔力）・mp（最大MP）を上げる。書いていない装備は 0
    {"id": "magic_wand",     "icon": "🪄", "name": "魔法の杖",       "rank": "normal",    "atk": 0,  "def": 0,  "hp": 0,  "mag": 2,  "mp": 5,  "resist": None},
    {"id": "steel_sword",    "icon": "⚔️", "name": "鋼の剣",         "rank": "rare",      "atk": 3,  "def": 0,  "hp": 0,  "resist": None},
    {"id": "steel_shield",   "icon": "🛡️", "name": "鋼の盾",         "rank": "rare",      "atk": 0,  "def": 6,  "hp": 0,  "resist": None},
    {"id": "knight_armor",   "icon": "🥋", "name": "騎士の鎧",       "rank": "rare",      "atk": 0,  "def": 0,  "hp": 15, "resist": None},
    {"id": "sage_staff",     "icon": "🦯", "name": "賢者の杖",       "rank": "rare",      "atk": 0,  "def": 0,  "hp": 0,  "mag": 5,  "mp": 15, "resist": None},
    {"id": "holy_sword",     "icon": "🌟", "name": "聖剣",           "rank": "epic",      "atk": 8,  "def": 0,  "hp": 0,  "resist": None},
    {"id": "holy_shield",    "icon": "🔰", "name": "聖なる盾",       "rank": "epic",      "atk": 0,  "def": 15, "hp": 0,  "resist": None},
    {"id": "dragon_armor",   "icon": "🐉", "name": "竜の鎧",         "rank": "epic",      "atk": 0,  "def": 0,  "hp": 40, "resist": None},
    {"id": "star_robe",      "icon": "🌌", "name": "星のローブ",     "rank": "epic",      "atk": 0,  "def": 5,  "hp": 0,  "mag": 10, "mp": 35, "resist": None},
    {"id": "poison_charm",   "icon": "📿", "name": "毒よけのお守り", "rank": "accessory", "atk": 0,  "def": 0,  "hp": 0,  "resist": "poison"},
    {"id": "thunder_ring",   "icon": "💍", "name": "雷よけの指輪",   "rank": "accessory", "atk": 0,  "def": 0,  "hp": 0,  "resist": "thunder"},
    {"id": "ice_ring",       "icon": "❄️", "name": "氷よけの指輪",   "rank": "accessory", "atk": 0,  "def": 0,  "hp": 0,  "resist": "freeze"},
    {"id": "fire_bangle",    "icon": "🔥", "name": "火よけの腕輪",   "rank": "accessory", "atk": 0,  "def": 0,  "hp": 0,  "resist": "fire"},
    # 黒炎・陰・影よけは、その状態異常を使う敵が出るハード以上でだけ宝箱から出る（min_difficulty）
    {"id": "black_flame_ring",  "icon": "🌑", "name": "黒炎の指輪",   "rank": "accessory", "atk": 0, "def": 0, "hp": 0, "resist": "black_flame", "min_difficulty": "hard"},
    {"id": "darkness_bracelet", "icon": "🌘", "name": "陰の腕輪",     "rank": "accessory", "atk": 0, "def": 0, "hp": 0, "resist": "darkness",    "min_difficulty": "hard"},
    {"id": "shadow_charm",      "icon": "👤", "name": "影のお守り",   "rank": "accessory", "atk": 0, "def": 0, "hp": 0, "resist": "shadow",      "min_difficulty": "hard"},
    # 強さがランダムなアクセサリ。roll の stat が min〜max だけ上がる（宝箱から出たときに決まる。ステージ後半ほど高め）
    #   difficulty の難易度でだけ出る。同じ物は2つ付けられないが、ちがう物（木霊の指輪と金獅子の指輪など）は同時に付けられる
    {"id": "ring_1", "icon": "💍", "name": "木霊の指輪", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "atk", "min": 1, "max": 3, "difficulty": "easy"}},
    {"id": "ring_2", "icon": "💍", "name": "闘志の銅輪", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "atk", "min": 2, "max": 6, "difficulty": "normal"}},
    {"id": "ring_3", "icon": "💍", "name": "金獅子の指輪", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "atk", "min": 4, "max": 9, "difficulty": "hard"}},
    {"id": "ring_4", "icon": "💍", "name": "覇王の神秘輪", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "atk", "min": 6, "max": 12, "difficulty": "very_hard"}},
    {"id": "guard_1", "icon": "🧿", "name": "若葉の守り札", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "def", "min": 1, "max": 3, "difficulty": "easy"}},
    {"id": "guard_2", "icon": "🧿", "name": "銅の守護符", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "def", "min": 2, "max": 6, "difficulty": "normal"}},
    {"id": "guard_3", "icon": "🧿", "name": "守護術式の魔石", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "def", "min": 4, "max": 9, "difficulty": "hard"}},
    {"id": "guard_4", "icon": "🧿", "name": "精霊王の護符", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "def", "min": 6, "max": 12, "difficulty": "very_hard"}},
    {"id": "life_1", "icon": "📿", "name": "生命の木の首飾り", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "hp", "min": 5, "max": 15, "difficulty": "easy"}},
    {"id": "life_2", "icon": "📿", "name": "銅の生命鈴", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "hp", "min": 10, "max": 30, "difficulty": "normal"}},
    {"id": "life_3", "icon": "📿", "name": "活力の魔石", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "hp", "min": 20, "max": 45, "difficulty": "hard"}},
    {"id": "life_4", "icon": "📿", "name": "不死鳥の羽飾り", "rank": "charm", "atk": 0, "def": 0, "hp": 0, "resist": None, "roll": {"stat": "hp", "min": 30, "max": 60, "difficulty": "very_hard"}},
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
#   属性が付く確率と発動率は、難易度ごとに下限〜上限を決め、ステージの後半ほど曲線（ATTR_CURVE）で上がる。
#     付く確率 = 下限 + (上限 − 下限) × t      （t = ((ステージ − 1) ÷ (ステージ数 − 1)) ^ ATTR_CURVE）
#     発動率   = 下限 + (上限 − 下限) × (0.6 × t + 0.4 × ランダム)   （後半ほど高めに出るが、ばらつきも残す）
#   超激レアの剣（沈黙の魔剣）は最後のステージで手に入るので、t = 1 で抽選する
#   付く数は WEAPON_ATTR_COUNTS の比率で1〜3個（同じ属性は重ならない）。比率も序盤→後半で曲線で移る。
#   黒炎・陰・影はハード以上でだけ付く（ATTR_MIN_DIFFICULTY）。
#   発動率は、剣を手に入れたときにランダムで決まり、そのあと変わらない。
#     毒・火・雷：3つで1つの発動率（ATTR_GROUP_CHANCE の範囲）。発動したら、付いている中から1つ
#     黒炎・陰・影：それぞれ別の発動率（ATTR_SOLO_CHANCE の範囲。ハード以上だけ）。毒・火・雷と同時に発動することもある
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
# 超激レアの剣：手に入れたとき、ベリーハードの剣と同じ確率で属性を抽選する（属性が付けば「属性の剣は1本まで」に入る）
ULTRA_ATTR_SWORDS = {"silence_blade": "very_hard"}
ATTR_CURVE = 1.5
# 属性が付く確率（ステージ1 → 最後のステージ）
WEAPON_ATTR_CHANCE = {"easy": (0.10, 0.20), "normal": (0.15, 0.35), "hard": (0.30, 0.50), "very_hard": (0.45, 0.70)}
WEAPON_ATTR_COUNTS = {                       # 1個・2個・3個の比率（ステージ序盤 → 後半。あいだは同じ曲線で移る）
    "easy":      ((80, 20, 0),  (70, 25, 5)),
    "normal":    ((75, 20, 5),  (65, 25, 10)),
    "hard":      ((60, 25, 15), (45, 30, 25)),
    "very_hard": ((40, 40, 20), (25, 35, 40)),
}
ATTR_GROUP = ("poison", "fire", "thunder")
ATTR_SOLO = ("black_flame", "darkness", "shadow")
ATTR_MIN_DIFFICULTY = {"black_flame": "hard", "darkness": "hard", "shadow": "hard"}
# 発動率の下限〜上限（難易度ごと）
ATTR_GROUP_CHANCE = {"easy": (0.01, 0.10), "normal": (0.05, 0.18), "hard": (0.15, 0.25), "very_hard": (0.20, 0.30)}
ATTR_SOLO_CHANCE = {"easy": (0.01, 0.01), "normal": (0.01, 0.01), "hard": (0.01, 0.05), "very_hard": (0.05, 0.15)}   # イージー・ノーマルでは付かない
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


# ---------------------------------------------------------------------------
# 称号（バッジ）
#   モード全クリ：その難易度を最後のステージまでクリアする
#   エクストラ  ：ステージの番人（極点の宇宙龍）を倒す
#   キャラ      ：そのキャラを Lv.10（最大）にする。名前は「（肩書き）を極めし者」
#   badge : assets/story/titles/ の中のファイル名
# ---------------------------------------------------------------------------
MODE_TITLES = {
    "easy":      {"name": "初号の踏破者",   "badge": "title_easy.webp"},
    "normal":    {"name": "星翼の探索者",   "badge": "title_normal.webp"},
    "hard":      {"name": "星辰の覚醒者",   "badge": "title_hard.webp"},
    "very_hard": {"name": "虚無を統べる者", "badge": "title_very_hard.webp"},
}
EXTRA_TITLE = {"name": "宇宙龍を討ちし者", "badge": "title_extra.webp"}
ALLY_TITLE_BADGE = "title_ally_{lv:02d}.webp"


# ---------------------------------------------------------------------------
# アステルの援護（たまたま通りかかったアステルが、必殺技で助けてくれる）
#   chance : 敵の攻撃が終わるたびに、この確率で起こる（1回の戦闘で1度だけ）。
#            エクストラ（宇宙龍）と、アステル自身で遊んでいるときは起こらない
#   ally / level : 援護するキャラとレベル（Lv.10 のステータスとアビリティで、必殺技の効果ものる）
#   image  : 空を見上げたときの絵（assets/story/skills/）
#   drops  : 援護があったステージをクリアすると、このどちらかが必ず手に入る（精霊の羽で呼んだときは出ない）
#   はじめて遊ぶ人は、はじめて倒れそうになったとき（HPが0になったとき）に、必ずアステルが助けに来る（HP1で踏みとどまる）。
#   精霊の羽を持っていれば、倒れそうになったときに「使う？」と聞く（使うとHP全回復＋援護）
# ---------------------------------------------------------------------------
#   chance : 敵の攻撃のたびに来る確率。仲間の数で直線的に下がる（1体 1% → 4体以上 0.0001%）
ASSIST = {"chance": 0.01, "chance_min": 0.000001, "chance_allies": (1, 4), "ally": 11, "level": 10, "image": "assist_sky.webp", "skill_image": "skill_astel_assist.webp",
          "drops": ["white_scale", "spirit_feather"]}



# ---------------------------------------------------------------------------
# 魔法（MP・魔力・会心）
#   キャラの magic：mp / mag は (Lv.1, Lv.10)。あいだは HP・攻撃・防御と同じ曲線（STAT_CURVE）で上がる。
#                    crit は会心率（レベルで変わらない）。spells は SPELL_LEVELS のレベルで順に覚える魔法。
#   魔力係数 = 2 × 魔力 ÷ (魔力 + MAGIC_COEF_K)（魔力10で1、魔力が大きいほど2に近づく）
#   攻撃魔法のダメージ = 魔力 × SPELL_POWER × 詠唱率 × 属性 × 会心。敵の防御は MAGIC_DEF_RATE 倍だけ効く
#     敵全体の魔法は、敵が1体なので SPELL_ALL_RATE 倍
#   回復・強化の量 = 基本の量 × 魔力係数 × 詠唱率（全回復は 最大HP × 詠唱率）
#   消費MP = 基本の消費 × (1 − MP_COST_CUT × 魔力係数) の切り上げ（最低1）
#     割合で消費する魔法（全回復・蘇生）は 最大MP × mp_rate × (1 − MP_COST_CUT × 魔力係数)。mp_floor より下がらない
#   詠唱：魔法をえらぶと、画面の円の中を連打する
#     満点の回数 = CHANT_MAX_TAPS × (1 − CHANT_MAG_CUT × 魔力係数)（切り上げ）。詠唱の時間 = 満点の回数 ÷ CHANT_TAPS_PER_SEC 秒
#     円の直径 = CHANT_CIRCLE_MAX × (1 − CHANT_CIRCLE_SHRINK × 重さ)。重さ = 基本の消費 ÷ CHANT_HEAVY_MP（最大1）。割合消費は1
#     詠唱率 = 円の中のタップ ÷ 満点の回数（最大100%、最低 CHANT_MIN_RATE）
#   会心：連打の1回ごとに会心率で、その1回が CRIT_MULT 倍（防御は効く）。魔法は会心率の MAGIC_CRIT_RATE 倍の確率で MAGIC_CRIT_MULT 倍
# ---------------------------------------------------------------------------
SPELL_LEVELS = (1, 4, 7)            # 魔法系以外（3つ）
SPELL_LEVELS_MAGIC = (1, 3, 5, 7, 9)   # 魔法系（5つ）
# キャラの系統：magic（魔法系。連打は狙った敵1体にだけ当たる。攻撃・回復の魔法）／fighter（それ以外。連打は何体にも当たる。強化の魔法）
#   系統ごとに、基本のステータスにかける倍率
CLASS_MULT = {
    "magic":   {"hp": 0.9,  "atk": 0.75, "def": 0.9, "mp": 1.3, "mag": 1.3},
    "fighter": {"hp": 1.15, "atk": 1.2,  "def": 1.1, "mp": 0.7, "mag": 0.6},
}
MAX_BOOK_SPELLS = 2            # 魔導書で覚えられる魔法の数（1人）
MAGIC_COEF_K = 10
MP_COST_CUT = 0.2
SPELL_POWER = {"small": 60, "mid": 90, "big": 130, "huge": 180}   # 1ターン60回当てる前提（魔力＝攻撃力なら、小で連打1ターン分）
SPELL_ALL_RATE = 0.7
# 敵1体の攻撃魔法：詠唱のあとに「ねらい」。動く円を、タップで止める（止めなければ AIM_MS で止まる）
#   円の中に弱点（赤い点）→ AIM_RATES["weak"]、敵の体が全部入る → "full"、体の一部 → "part"、何も入らない → "miss"
#   そのぶん、敵1体の魔法の威力は SPELL_SINGLE_MULT 倍。円の直径は詠唱の円 × AIM_SIZE
SPELL_SINGLE_MULT = 1.5
AIM_RATES = {"weak": 1.5, "full": 1.0, "part": 0.8, "miss": 0.1}
AIM_MS = 4000
AIM_SIZE = 0.6
MAGIC_DEF_RATE = 0.5
ELEMENT_WEAK = 1.5
ELEMENT_RESIST = 0.5
CHANT_MAX_TAPS = 120
CHANT_MAG_CUT = 0.35
CHANT_TAPS_PER_SEC = 15
CHANT_MIN_RATE = 0.1
CHANT_CIRCLE_MAX = 300
CHANT_CIRCLE_SHRINK = 0.6
CHANT_HEAVY_MP = 40
CRIT_MULT = 2.0
MAGIC_CRIT_MULT = 1.5
MAGIC_CRIT_RATE = 0.5
STAGE_MP_RATE = 0.3            # ステージをクリアしたとき、減っているMPのこの割合を回復（戦闘が終われば全回復）
HASTE_MAX = 3.0                # 連打の時間をのばせるのは、合わせて3秒まで

ELEMENTS = {
    "fire":    {"name": "炎", "icon": "🔥", "color": "#ff7a3a"},
    "ice":     {"name": "氷", "icon": "❄️", "color": "#8fe0ff"},
    "thunder": {"name": "雷", "icon": "⚡", "color": "#ffe14a"},
    "light":   {"name": "光", "icon": "✨", "color": "#fff1b0"},
    "dark":    {"name": "闇", "icon": "🌑", "color": "#b07bff"},
    "wind":    {"name": "風", "icon": "🌪️", "color": "#9ff0c8"},
    None:      {"name": "無", "icon": "🔷", "color": "#9fc0ff"},
}

# 魔法
#   kind   : attack（敵にダメージ）/ heal（HP回復）/ mana（HP小＋MP小）/ full（HP全回復）/ cure（状態異常を治す）/
#            revive（戦闘不能から復活。仲間がいるときだけ）/ protect（防御2倍）/ brave（攻撃のダメージアップ）/ haste（連打の時間をのばす）
#   target : enemy（敵1体）/ enemies（敵全体）/ ally（味方1人）/ allies（味方全体）/ self（自分）
#   tier   : 攻撃魔法の強さ（SPELL_POWER）   mp : 基本の消費MP   mp_rate / mp_floor : 割合で消費する魔法
#   heal / mp_heal : 最大HP・最大MPに対する基本の回復量（× 魔力係数 × 詠唱率）
#   turns  : 効果が続くターン（protect・brave は × 魔力係数で少しのびる）   power : brave のダメージアップ（× 魔力係数）
#   seconds: haste で連打の時間に足す秒数（魔力では変わらない）
SPELLS = {
    "fire":        {"name": "ファイア",           "element": "fire",    "kind": "attack", "target": "enemy",   "tier": "small", "mp": 5},
    "ice":         {"name": "アイス",             "element": "ice",     "kind": "attack", "target": "enemy",   "tier": "small", "mp": 5},
    "thunder":     {"name": "サンダー",           "element": "thunder", "kind": "attack", "target": "enemy",   "tier": "small", "mp": 5},
    "rune_bolt":   {"name": "ルーンボルト",       "element": None,      "kind": "attack", "target": "enemy",   "tier": "mid",   "mp": 10},
    "blizzard":    {"name": "ブリザード",         "element": "ice",     "kind": "attack", "target": "enemy",   "tier": "mid",   "mp": 10},
    "thunderbolt": {"name": "サンダーボルト",     "element": "thunder", "kind": "attack", "target": "enemies", "tier": "mid",   "mp": 16},
    "explosion":   {"name": "エクスプロージョン", "element": "fire",    "kind": "attack", "target": "enemies", "tier": "big",   "mp": 28},
    "holy":        {"name": "ホーリー",           "element": "light",   "kind": "attack", "target": "enemy",   "tier": "big",   "mp": 18},
    "darkness":    {"name": "ダークネス",         "element": "dark",    "kind": "attack", "target": "enemy",   "tier": "big",   "mp": 18},
    "meteor":      {"name": "メテオ",             "element": None,      "kind": "attack", "target": "enemies", "tier": "huge",  "mp": 48},
    "heal":        {"name": "ヒール",             "element": None, "kind": "heal",    "target": "ally",  "heal": 0.25, "mp": 5},
    "mana_heal":   {"name": "マナヒール",         "element": None, "kind": "mana",    "target": "ally",  "heal": 0.15, "mp_heal": 0.10, "mp": 6},
    "high_heal":   {"name": "ハイヒール",         "element": None, "kind": "heal",    "target": "ally",  "heal": 0.55, "mp": 12},
    "full_heal":   {"name": "フルケア",           "element": None, "kind": "full",    "target": "ally",  "mp_rate": 0.7,  "mp_floor": 0.5},
    "cure":        {"name": "キュア",             "element": None, "kind": "cure",    "target": "ally",  "mp": 4},
    "revive":      {"name": "リバイブ",           "element": None, "kind": "revive",  "target": "ally",  "heal": 0.5, "mp_rate": 0.35, "mp_floor": 0.25},
    "protect":     {"name": "プロテクト",         "element": None, "kind": "protect", "target": "ally",  "turns": 3, "mp": 8},
    "brave":       {"name": "ブレイブ",           "element": None, "kind": "brave",   "target": "ally",  "turns": 3, "power": 0.3, "mp": 8},
    "quick":       {"name": "クイック",           "element": None, "kind": "haste",   "target": "ally",  "turns": 3, "seconds": 1.0, "mp": 6},
    # 味方全体（パーティ全員。1人のときは自分）
    "heal_all":    {"name": "ヒーリングオール",   "element": None, "kind": "heal",    "target": "allies", "heal": 0.2, "mp": 14},
    "war_cry":     {"name": "ウォークライ",       "element": None, "kind": "brave",   "target": "allies", "turns": 3, "power": 0.2, "mp": 14},
    "guard_all":   {"name": "ガードオール",       "element": None, "kind": "protect", "target": "allies", "turns": 2, "mp": 14},
    "haste_all":   {"name": "疾風の号令",         "element": None, "kind": "haste",   "target": "allies", "turns": 2, "seconds": 1.0, "mp": 12},
    "holy_all":    {"name": "セイントレイ",       "element": "light", "kind": "attack", "target": "enemies", "tier": "big", "mp": 30},
    "gale_stance": {"name": "疾風の構え",         "element": None, "kind": "haste",   "target": "self",  "turns": 3, "seconds": 2.0, "mp": 8},
}

# 敵の魔法：敵が炎・雷・黒炎・凍えをかけるときは、魔法として名前を出す（ダメージは通常攻撃と同じ。状態異常が必ず付く）
ENEMY_SPELLS = {
    "fire":        {"name": "ヘルフレイム",   "element": "fire"},
    "thunder":     {"name": "ライトニング",   "element": "thunder"},
    "black_flame": {"name": "ダークフレア",   "element": "dark"},
    "freeze":      {"name": "フロストノヴァ", "element": "ice"},
    "wind":        {"name": "ウィンドカッター", "element": "wind"},
}

# ---------------------------------------------------------------------------
# マニー（お金）とショップ
#   ステージをクリアするたびに (MONEY_STAGE_BASE + MONEY_STAGE_STEP × ステージ) × 難易度の倍率
#   全クリアで MONEY_CLEAR_BONUS × 倍率、エクストラ（宇宙龍）を倒すと MONEY_EXTRA × 倍率
#   イージーをステージ6くらいまで進めると約70マニー。エーテル（300）はクエスト4回くらいで買える
#   ITEM_PRICES はショップで買う値段。売るときは SELL_RATE 倍。SHOP_ITEMS にないアイテムは買えない（売れる）
# ---------------------------------------------------------------------------
MONEY_NAME = "マニー"
MONEY_ICON = "🪙"
MONEY_STAGE_BASE = 5
MONEY_STAGE_STEP = 2
MONEY_DIFF = {"easy": 1.0, "normal": 1.5, "hard": 2.0, "very_hard": 3.0}
MONEY_CLEAR_BONUS = 50
MONEY_EXTRA = 150
SELL_RATE = 0.5
ITEM_PRICES = {
    "potion": 40, "guard_up": 60, "atk_up": 60, "hi_potion": 120, "panacea": 80, "mega_potion": 300,
    "seal_scroll": 150, "purge_scroll": 150, "holy_circle": 250, "elixir": 1200,
    "ether": 300, "life_leaf": 500, "crit_potion": 250, "magic_water": 250, "gale_sandglass": 350,
    "hi_ether": 1000, "last_elixir": 2500, "phoenix_down": 1500, "white_scale": 2000, "spirit_feather": 1500,
    "book_fire": 2000, "book_ice": 2000, "book_thunder": 2000, "book_light": 2000, "book_dark": 2000,
    "book_heal": 2000, "book_revive": 2000,
}
SHOP_ITEMS = ["potion", "hi_potion", "mega_potion", "ether", "guard_up", "atk_up", "panacea", "crit_potion",
              "magic_water", "gale_sandglass", "life_leaf", "seal_scroll", "purge_scroll", "holy_circle"]
SHOP_LINES = ["いらっしゃい。ゆっくり見ていっておくれ", "魔導書かい？ あれは店には置いとらんのじゃ。強いボスが持っとるらしいぞ",
              "エーテルはMPを回復する薬じゃよ", "いらないものは、半分の値段で買い取るぞい"]

# ボスのドロップ：最後のステージの敵・エクストラ（宇宙龍）を倒すと、BOSS_DROPS の比率で1つ（"book" は魔導書のどれか）
#   その難易度をはじめて全クリアしたときは、魔導書を1冊（まだ持っていない物から）
BOSS_DROPS = {"hi_ether": 40, "phoenix_down": 30, "last_elixir": 15, "book": 15}


# ---------------------------------------------------------------------------
# クエスト「風哭きの森」（1ステージに敵が1〜3体。イージー〜ベリーハードを選ぶ）
#   今までのクエスト（id "main"）とは別。ステージは全部で KZ_STAGE_COUNT。
#   敵の強さ：今までのクエストの、同じ番号のステージの敵（イージーの値）を元に
#     HP・攻撃力 = 元 × KZ_SCALE × 役割の倍率 × 人数の倍率（KZ_SHARE。ボス・中ボスはかけない）
#     防御力     = 元 × KZ_SCALE × 役割の倍率
#   そのうえで、難易度の倍率（DIFFICULTIES）をかける。
#   役割（role）：KZ_ROLES。phys_cut は剣（連打）のダメージにかける倍率（石の体）
#   heal   : 回復役。自分のターンに、仲間の中でいちばん減っている敵を最大HPのこの割合だけ回復する
#   double : 1ターンに2回攻撃する     heavy : 3回に1回、力をためて（予告して）次のターンにこの倍の一撃
#   gimmicks に "wind"（突風）：次の自分の連打のあいだ、敵がゆれて当てにくい
# ---------------------------------------------------------------------------
KZ_QUEST = {"id": "kz", "name": "風哭きの森", "sub": "闇の柱と風の番人", "icon": "🌲"}
KZ_STAGE_COUNT = 10
# 強さの決め方（目標から逆算する）
#   基準のキャラ（KZ_REF：推奨レベルの上のほうのキャラと、そのくらいで持っていそうな装備）が、1ターン KZ_TAPS 回当てたとき
#     ・敵を全部倒すのにかかるターン数 = KZ_TURNS（ふつうのステージは最初→ステージ8へ直線で増える）
#     ・そのステージで受けるダメージ（アイテムなし）= 最大HP × KZ_DAMAGE
#   になるように、敵全員のHPの合計と、1ターンに受けるダメージを決め、役割（KZ_ROLES の hp / atk）の比で分ける。
#   防御力は、今までのクエストの同じ番号のステージの敵（イージーの値）× 難易度の倍率 × 役割の def。
#   推奨レベル：イージー Lv.1〜3、ノーマル Lv.3〜5、ハード Lv.5〜8、ベリーハード Lv.8〜10
KZ_TAPS = 60
KZ_REF = {   # (キャラ, レベル, 装備の 攻撃・防御・HP)
    "easy": (3, 3, (0, 0, 0)), "normal": (5, 5, (3, 6, 15)), "hard": (7, 8, (8, 15, 40)), "very_hard": (9, 10, (20, 30, 60)),
}
KZ_TURNS = {     # ふつうのステージ（最初, 最後）・中ボス・ボス。エクストラはボスの KZ_EXTRA_TURNS 倍
    "easy": ((2.5, 3.5), 5, 6), "normal": ((3.5, 4.5), 6, 7), "hard": ((4.5, 5.5), 7, 8.5), "very_hard": ((5.5, 6.5), 8, 10),
}
KZ_DAMAGE = {"stage": (0.35, 0.55), "midboss": 0.85, "boss": 1.4, "extra": 1.9}
KZ_EXTRA_TURNS = 1.5
# パーティ（3人）で、こちらが先手。1ターン目に全員で合わせて300タップをこえることもある前提で強くする
#   HP：基準のキャラの KZ_PARTY_HP 倍ぶん（ボス・中ボスはさらに KZ_BOSS_HP 倍）
#   攻撃：受けるダメージの合計を KZ_PARTY_DMG 倍（3人で受けるので、1人あたりは少し重いくらい）
KZ_PARTY_HP = {"easy": 1.3, "normal": 2.2, "hard": 2.5, "very_hard": 2.5}   # イージーは初めての人向けに少しだけ
KZ_PARTY_DMG = {"easy": 1.6, "normal": 2.6, "hard": 3.0, "very_hard": 3.0}
KZ_BOSS_HP = 1.2
# ボス・中ボス（1体だけのとき）の攻撃：BOSS_AOE_CHANCE の確率で全体攻撃（1人あたり BOSS_AOE_RATE 倍）、それ以外は1人への強い一撃（BOSS_SINGLE_RATE 倍）
BOSS_AOE_CHANCE = 0.65
BOSS_AOE_RATE = 0.6
BOSS_SINGLE_RATE = 1.6
# 挑戦の後半ほど強く：ステージの進み t（最初0 → 最後1）で、HP・攻撃力に (1 + KZ_RAMP × t^1.5) をかける
#   （挑戦のあいだに装備・アイテム・仲間がそろい、パーティ3人で戦うことを見こんで、後半をきびしくする）
KZ_RAMP = {"hp": 5.0, "atk": 1.5}
KZ_ROLES = {   # hp・atk は同じステージの中での分け方の比。def は防御力の倍率
    "zako":    {"hp": 1.0, "atk": 1.0, "def": 1.0},
    "healer":  {"hp": 0.8, "atk": 0.6, "def": 0.9},
    "tank":    {"hp": 1.5, "atk": 0.8, "def": 1.5},
    "fast":    {"hp": 0.8, "atk": 1.1, "def": 0.8},
    "mage":    {"hp": 0.9, "atk": 1.15, "def": 0.8},
    "stone":   {"hp": 1.2, "atk": 1.0, "def": 1.2, "phys_cut": 0.5},
    "midboss": {"hp": 3.0, "atk": 2.0, "def": 1.2, "boss": True},
    "boss":    {"hp": 1.0, "atk": 1.0, "def": 1.3, "boss": True},
    "extra":   {"hp": 1.0, "atk": 1.0, "def": 1.5, "boss": True},
}
KZ_EXTRA_CHANCE = 0.02
KZ_HEAVY_EVERY = 3              # heavy の敵は、この回数に1回力をためる
KZ_AREAS = {
    "forest": {"name": "静寂の森",   "bg": "bg_kz_forest.webp"},
    "valley": {"name": "黒風の渓谷", "bg": "bg_kz_valley.webp"},
    "gate":   {"name": "番人の迷宮", "bg": "bg_kz_gate.webp"},
    "extra":  {"name": "闇の柱の門", "bg": "bg_kz_extra.webp"},
}
_C = lambda e, n, h, v: {"easy": e, "normal": n, "hard": h, "very_hard": v}
# ステージ：fixed は必ず出る敵、boss_pick はこの中から1体（中ボス）、pool から残りの数だけ選ぶ（同じ敵が重なってもよい）
#   count は難易度ごとの (最少, 最多) の体数（fixed・boss_pick もふくむ）
KZ_STAGES = [
    {"area": "forest", "name": "森の入口",     "pool": ["kz_01", "kz_02"], "count": _C((1, 1), (1, 2), (2, 2), (2, 3))},
    {"area": "forest", "name": "木もれ日の小道", "pool": ["kz_01", "kz_02"], "count": _C((1, 2), (2, 2), (2, 3), (3, 3))},
    {"area": "forest", "name": "苔むした祭壇", "fixed": ["kz_03"], "pool": ["kz_01", "kz_02"], "count": _C((2, 2), (2, 3), (3, 3), (3, 3))},
    {"area": "valley", "name": "黒く染まる木々", "pool": ["kz_04", "kz_05", "kz_06", "kz_07", "kz_08", "kz_02"], "count": _C((1, 2), (2, 2), (2, 3), (3, 3))},
    {"area": "valley", "name": "突風の吊り橋", "pool": ["kz_04", "kz_05", "kz_06", "kz_07", "kz_08", "kz_02"], "count": _C((2, 2), (2, 3), (3, 3), (3, 3))},
    {"area": "valley", "name": "渓谷の奥",     "boss_pick": ["kz_09", "kz_10"], "pool": ["kz_05", "kz_06", "kz_07"], "count": _C((1, 1), (1, 2), (2, 2), (2, 3))},
    {"area": "gate",   "name": "迷宮の門",     "fixed": ["kz_12"], "pool": ["kz_11"], "count": _C((2, 2), (2, 3), (3, 3), (3, 3))},
    {"area": "gate",   "name": "迷宮の深部",   "pool": ["kz_13", "kz_14", "kz_15", "kz_11"], "count": _C((2, 2), (2, 3), (3, 3), (3, 3))},
    {"area": "gate",   "name": "雷の祭壇",     "boss_pick": ["kz_16", "kz_20"], "count": _C((1, 1), (1, 1), (1, 1), (1, 1))},
    {"area": "gate",   "name": "最奥",         "fixed": ["kz_17"], "count": _C((1, 1), (1, 1), (1, 1), (1, 1)),
     "intro": "門の前に、くずれた盾と槌が落ちている……これは、風の番人の……？"},
]
# 敵（image は assets/story/enemies/ の名前。cutout=False は背景つきの1枚絵で、1体だけで出る）
KZ_ENEMIES = [
    {"id": "kz_01", "name": "鎧ネズミの斥候", "role": "zako", "image": "kz_01.webp", "cutout": True, "gimmicks": [],
     "lines": ["チュチュッ！", "ここは通さないチュ", "ナイフの錆にしてやる！"], "effect": {"type": "claw", "color": "#c9a46b"}},
    {"id": "kz_02", "name": "黒羽のハーピー", "role": "fast", "image": "kz_02.webp", "cutout": True, "floating": True, "gimmicks": ["wind"],
     "lines": ["キィィーッ！", "風が、おかしいの……", "吹き飛ばしてあげる！"], "effect": {"type": "claw", "color": "#9ff0c8"}},
    {"id": "kz_03", "name": "森のトカゲ呪術師", "role": "healer", "heal": 0.15, "image": "kz_03.webp", "cutout": True, "gimmicks": ["poison"],
     "lines": ["森の精よ、仲間を癒やせ", "シュルル……", "祭壇を汚すな"], "effect": {"type": "magic", "color": "#6dff9a"}},
    {"id": "kz_04", "name": "翠鎧の女戦士", "role": "tank", "image": "kz_04.webp", "cutout": True, "gimmicks": [], "weak": "thunder", "resist_elem": "ice",
     "lines": ["この盾、くだけるものか！", "はあぁっ！", "闇の柱には近づかせない"], "effect": {"type": "slash", "color": "#bfe8c8"}},
    {"id": "kz_05", "name": "紫雷の闇剣士", "role": "fast", "image": "kz_05.webp", "cutout": True, "gimmicks": ["thunder"], "weak": "light", "resist_elem": "thunder",
     "lines": ["雷よ、刃に宿れ", "……遅い", "しびれて動けまい"], "effect": {"type": "slash", "color": "#c69bff"}},
    {"id": "kz_06", "name": "双刃の暗殺者", "role": "fast", "image": "kz_06.webp", "cutout": True, "gimmicks": ["shadow"], "weak": "light", "resist_elem": "dark",
     "lines": ["……影から影へ", "ふたつの刃、よけられるか", "背中を見せたな"], "effect": {"type": "slash", "color": "#e070ff"}},
    {"id": "kz_07", "name": "宵闇の術師", "role": "mage", "image": "kz_07.webp", "cutout": True, "gimmicks": ["darkness"], "weak": "light", "resist_elem": "dark",
     "lines": ["宵闇よ、目をふさげ", "ククク……", "光など、ここには届かぬ"], "effect": {"type": "void", "color": "#9a6bff"}},
    {"id": "kz_08", "name": "髑髏杖の闇術師", "role": "mage", "image": "kz_08.webp", "cutout": True, "gimmicks": ["black_flame"], "weak": "light", "resist_elem": "dark",
     "lines": ["黒き炎に焼かれよ", "闇の柱は、もうすぐ完成する", "髑髏が笑っておるわ"], "effect": {"type": "magic", "color": "#b26bff"}},
    {"id": "kz_09", "name": "闇蜘蛛アラクネ", "role": "midboss", "image": "kz_09.webp", "cutout": True, "gimmicks": ["poison", "shadow"], "weak": "fire", "resist_elem": "dark",
     "lines": ["わたしの巣に、ようこそ", "毒はお好き？", "もう逃げられないわよ"], "effect": {"type": "claw", "color": "#8a6bbf"}},
    {"id": "kz_10", "name": "虹翼のキマイラ", "role": "midboss", "double": True, "image": "kz_10.webp", "cutout": True, "gimmicks": ["fire", "wind"], "weak": "ice", "resist_elem": "fire",
     "lines": ["グルルルァ！", "三つの首が、おまえを見ている", "ガアァァッ！"], "effect": {"type": "fire", "color": "#ff9a5a"}},
    {"id": "kz_11", "name": "台座のガーゴイル", "role": "stone", "image": "kz_11.webp", "cutout": True, "gimmicks": [], "weak": "thunder", "resist_elem": "ice",
     "lines": ["……ゴゴゴ", "石の眠りを、さますな", "門に近づく者は砕く"], "effect": {"type": "claw", "color": "#b8b0a0"}},
    {"id": "kz_12", "name": "呪石の魔像", "role": "stone", "heavy": 2.5, "image": "kz_12.webp", "cutout": True, "gimmicks": [], "weak": "thunder", "resist_elem": "dark",
     "lines": ["門ヲ……マモル……", "ルーンが、光る……", "ツブレロ"], "effect": {"type": "void", "color": "#7fb0ff"}},
    {"id": "kz_13", "name": "顔なき魔導師", "role": "mage", "image": "kz_13.webp", "cutout": True, "gimmicks": ["darkness", "freeze"], "weak": "light", "resist_elem": "dark",
     "lines": ["顔など、とうに捨てた", "魔法陣よ、まわれ", "あなたの光も、いただくわ"], "effect": {"type": "magic", "color": "#d27bff"}},
    {"id": "kz_14", "name": "虹炎の闇術師", "role": "mage", "image": "kz_14.webp", "cutout": True, "gimmicks": ["fire", "thunder", "freeze"], "weak": "dark", "resist_elem": "fire",
     "lines": ["七色の炎を見せてやろう", "どの属性がお好みかな？", "王の御前だ、ひれ伏せ"], "effect": {"type": "radiance", "color": "#ff7af0"}},
    {"id": "kz_15", "name": "百眼の影", "role": "tank", "image": "kz_15.webp", "cutout": True, "floating": True, "gimmicks": ["shadow"], "weak": "light", "resist_elem": "dark",
     "lines": ["……ミテイル……", "ヒャクノメガ、オマエヲ……", "ニガサナイ"], "effect": {"type": "void", "color": "#6f7bff"}},
    {"id": "kz_16", "name": "雷鳴の大魔導師", "role": "midboss", "double": True, "image": "kz_16.webp", "cutout": False, "gimmicks": ["thunder"], "weak": "ice", "resist_elem": "thunder",
     "lines": ["雷鳴よ、我が声となれ", "祭壇は、すでに闇のもの", "砕け散れ！"], "effect": {"type": "thunder", "color": "#9ad8ff"}},
    {"id": "kz_17", "name": "風の番人", "role": "boss", "double": True, "image": "kz_17.webp", "cutout": True, "gimmicks": ["wind"], "weak": "thunder", "resist_elem": "ice",
     "title": "森を護りし者",
     "lines": ["……ここは、通さぬ……", "風よ……我が刃に……", "森を……まもる……のだ……"], "effect": {"type": "slash", "color": "#7dffb8"},
     # 覚醒：HPが半分を切ると、闇に呑まれた姿に変わる。攻撃・防御は stat_rate 倍、heavy の一撃も使う
     "awaken": {"hp_rate": 0.5, "heal_rate": 0.2, "heal_to": 0.8, "stat_rate": 1.25, "name": "闇纏いの番人", "title": "闇に堕ちた風",
                "image": "kz_18.webp", "cutout": True, "heavy": 2.5,
                "lines": ["風は……闇に、なった", "もう、なにも護らない", "消えろ"], "effect": {"type": "void", "color": "#8bff9a"}}},
    {"id": "kz_20", "name": "星冠の死王", "role": "midboss", "image": "kz_20.webp", "cutout": False, "gimmicks": ["black_flame", "meteor"], "weak": "light", "resist_elem": "dark",
     "lines": ["星々は、わが冠", "ひれ伏せ、小さき者よ", "宇宙の果てに還るがいい"], "effect": {"type": "cosmic", "color": "#c49bff"}},
]
# エクストラ：黒翼の執行者（風哭きの森のステージのあいだに、まれに現れる。強さは難易度で変わる）
KZ_EXTRA_ENEMY = {
    "id": "kz_19", "name": "黒翼の執行者", "title": "闇の柱より来たる者", "role": "extra", "base_stage": 9,
    "image": "kz_19.webp", "cutout": True, "floating": True, "gimmicks": ["black_flame", "shadow", "wind"], "weak": "light", "resist_elem": "dark",
    "lines": ["……番人を堕としたのは、私だ", "その翼で、どこまで飛べる？", "闇の柱の礎となれ"], "effect": {"type": "void", "color": "#b07bff"},
    "awaken": {"hp_rate": 0.5, "heal_rate": 0.25, "stat_rate": 1.3, "name": "黒翼の執行者・解放", "title": "星を裂く翼",
               "image": "kz_19_awake.webp", "cutout": True, "heavy": 2.5,
               "lines": ["……少し、本気を見せよう", "星の魔法陣よ、開け", "終わりだ"], "effect": {"type": "cosmic", "color": "#d27bff"},
               "special": {"name": "星裂く黒翼の魔法陣", "chance": 0.08, "damage_rate": 0.22, "image": "kz_19_special.webp",
                           "line": "……魔法陣よ、すべてを裂け"}},
}
KZ_END_LINE = "……番人が倒れたか。だが、柱はまだ立っている"


# ---------------------------------------------------------------------------
# 闇の回廊も、1ステージに敵が何体も（風哭きの森と同じしくみ・同じ強さの決め方）
#   MAIN_GROUPS：そのステージのいつもの敵（キー）を「リーダー」にして、pool から残りの数だけ足す。
#     lead は画面に出す姿（Lv.5〜7 は切り抜いた絵 *_cut を使う）。bg はその背景（assets/story/backgrounds/bg_*.webp）
#   ここにない敵（1枚絵の Lv.8・10・11）は1体だけで出る（最後のステージはボス、それ以外は中ボスの強さ）
#   強さの目安（KZ_TURNS・KZ_DAMAGE）は風哭きの森と同じ。最後のステージがボス
# ---------------------------------------------------------------------------
MAIN_GROUPS = {
    "enemy_01": {"bg": "corridor", "lead": "enemy_01", "pool": ["enemy_01", "kz_01"], "count": _C((1, 2), (2, 2), (2, 3), (3, 3))},
    "enemy_02": {"bg": "prison", "lead": "enemy_02", "pool": ["enemy_01", "enemy_02", "kz_01"], "count": _C((2, 2), (2, 3), (3, 3), (3, 3))},
    "enemy_03": {"bg": "catacomb", "lead": "enemy_03", "pool": ["enemy_01", "enemy_02", "kz_06"], "count": _C((2, 2), (2, 3), (3, 3), (3, 3))},
    "enemy_04": {"bg": "altar", "lead": "enemy_04", "pool": ["enemy_03", "kz_08", "enemy_01"], "count": _C((2, 2), (2, 3), (3, 3), (3, 3))},
    "enemy_05": {"bg": "catacomb", "lead": "enemy_05_cut", "pool": ["kz_07", "kz_13", "enemy_04"], "count": _C((2, 2), (2, 3), (3, 3), (3, 3))},
    "enemy_06": {"bg": "prison", "lead": "enemy_06_cut", "pool": ["enemy_02", "kz_04", "enemy_04"], "count": _C((2, 2), (2, 3), (3, 3), (3, 3))},
    "enemy_07": {"bg": "altar", "lead": "enemy_07_cut", "pool": ["kz_08", "kz_14", "kz_06"], "count": _C((2, 2), (2, 3), (3, 3), (3, 3))},
    "enemy_09": {"bg": "nebula", "lead": "enemy_09", "pool": ["kz_15", "kz_07", "kz_13"], "count": _C((2, 2), (2, 3), (3, 3), (3, 3))},
}
# 切り抜いた姿（元の敵と同じ名前・セリフ。base は元の敵のキー）
MAIN_CUTS = {"enemy_05_cut": "enemy_05", "enemy_06_cut": "enemy_06", "enemy_07_cut": "enemy_07"}
KZ_ROLES["leader"] = {"hp": 1.6, "atk": 1.3, "def": 1.15}
