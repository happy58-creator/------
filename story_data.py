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
     "image": "enemy_04.webp", "cutout": True, "scene": "altar", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["我が魔術の糧となれ", "骨の髄まで凍えるがいい", "クク……愚かな"], "effect": {"type": "magic", "color": "#b26bff"}},
    {"lv": 5, "name": "深淵の従者", "hp": 794, "atk": 3.1, "def": 6.3,
     "image": "enemy_05.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["深淵へ……引きずり込んでやる", "シャアアッ！", "主のもとへは行かせぬ"], "effect": {"type": "whip", "color": "#e0483e"}},
    {"lv": 6, "name": "死霊の将軍", "hp": 1034, "atk": 4.1, "def": 8.4,
     "image": "enemy_06.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": [], "difficulties": _ALL,
     "lines": ["我が軍勢の前にひれ伏せ", "死してなお、我は戦う", "この一撃、受けてみよ"], "effect": {"type": "slash", "color": "#a9c4b0"}},
    {"lv": 7, "name": "悪魔の貴族", "hp": 1366, "atk": 5.4, "def": 10.7,
     "image": "enemy_07.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": ["poison"], "difficulties": _ALL,
     "lines": ["下賤の者が、我に触れるな", "地獄の炎で焼かれるがいい", "フフ……退屈させるな"], "effect": {"type": "fire", "color": "#ff7a2a"}},
    {"lv": 8, "name": "半神の魔王", "hp": 1790, "atk": 7.1, "def": 12.9,
     "image": "enemy_08.webp", "cutout": False, "scene": "image", "floating": False, "gimmicks": ["thunder"], "difficulties": _ALL,
     "lines": ["玉座から動くまでもない", "神の雷、その身で知れ", "ひざまずけ"], "effect": {"type": "thunder", "color": "#ffd84a"}},
    {"lv": 9, "name": "災厄の代行者", "hp": 2374, "atk": 9.4, "def": 16.3,
     "image": "enemy_09.webp", "meteor_scene": {"name": "災厄の流星", "image": "meteor_09.webp", "focus": "50% 50%"}, "cutout": True, "scene": "nebula", "floating": True, "immune": ["thunder"], "gimmicks": ["poison", "thunder", "fire"], "difficulties": _ALL,
     "lines": ["すべては無に還る", "災いは、選ばない", "抗うな。苦しむだけだ"], "effect": {"type": "void", "color": "#9a6bff"}},
    {"lv": 10, "name": "終焉の創造主", "hp": 3102, "atk": 12.2, "def": 19.8,
     "image": "enemy_10.webp", "meteor_scene": {"name": "終焉の星墜", "image": "meteor_10.webp", "focus": "55% 45%"}, "cutout": False, "scene": "image", "floating": False, "immune": ["thunder"], "gimmicks": ["poison", "thunder", "fire", "meteor"], "difficulties": _ALL,
     "lines": ["世界を創り、そして終わらせる", "星の一つも、我が意のまま", "よくぞここまで来た。だが、ここで終わりだ"], "effect": {"type": "cosmic", "color": "#a8d4ff"}},
    {"lv": 11, "name": "混沌の初源", "hp": 4026, "atk": 15.8, "def": 23.1,
     "image": "enemy_11_hard.webp", "meteor_scene": {"name": "原初の流星雨", "image": "meteor_11_hard.webp", "focus": "72% 45%"}, "cutout": False, "scene": "image", "floating": False, "immune": ["thunder"], "gimmicks": ["poison", "thunder", "fire", "meteor", "darkness"], "difficulties": ["hard", "very_hard"],
     "lines": ["すべてはわたしから生まれた", "還りなさい、始まりの光へ", "混沌こそ、世界の母"], "effect": {"type": "radiance", "color": "#ffd27a"}},
    {"lv": 11, "name": "永遠の沈黙", "hp": 4026, "atk": 15.8, "def": 23.1,
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
    "lv": "???", "name": "極点の宇宙龍", "title": "災厄と創造の統合者", "hp": 5360, "atk": 21.3, "def": 29.0, "fixed_stats": True,
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
ABILITY_THRESHOLDS = (5, 10, 25)
ABILITY_POINT_PER_STAGE = 0.1     # クリアしたステージ1つにつき 0.1（全クリアで 1.0）
LEVEL_MAX = 10
LEVEL_POINTS = (108, 180)         # Lv.10 に要るポイント（コウ ＝ 3.6 × 30回、ルナ ＝ 3.6 × 50回）
LEVEL_CURVE = 2.0
STAT_CURVE = 1.3

ALLIES = [
    {"lv": 1,  "name": "平凡な農民、コウ",         "hp": 10, "atk": 1, "def": 1, "max": {"hp": 34, "atk": 7, "def": 8},  "image": "ally_01.webp", "unlock": None,
     "abilities": [{"stat": "atk", "value": 1}, {"stat": "atk", "value": 1}, {"stat": "def", "value": 3}], "skill": {"name": "渾身のひと振り", "type": "strike", "charge": 250, "power": 50, "anim": "kou", "scene": {"image": "skill_kou.webp", "focus": "50% 30%"}, "text": "大きく振りかぶって一撃。攻撃力×50 のダメージ"}},
    {"lv": 2,  "name": "新米自警団員、マリ",       "hp": 11, "atk": 2, "def": 1, "max": {"hp": 35, "atk": 7, "def": 9},  "image": "ally_02.webp", "unlock": {"min_difficulty": "normal", "stage": 2, "chance": 0.30},
     "abilities": [{"stat": "def", "value": 1}, {"stat": "def", "value": 1}, {"stat": "atk", "value": 4}], "skill": {"name": "守りの誓い", "type": "guard", "charge": 200, "heal_rate": 0.2, "guard": 3, "anim": "mari", "scene": {"image": "skill_mari.webp", "focus": "45% 30%"}, "text": "光の盾でHPを最大の20%回復し、3ターン防御力2倍"}},
    {"lv": 3,  "name": "新兵中隊長、アレックス",   "hp": 13, "atk": 2, "def": 3, "max": {"hp": 40, "atk": 8, "def": 10},  "image": "ally_03.webp", "unlock": {"min_difficulty": "easy", "stage": 4, "chance": 0.50},
     "abilities": [{"stat": "hp", "value": 3}, {"stat": "hp", "value": 3}, {"stat": "atk", "value": 3}], "skill": {"name": "突撃号令", "type": "boost", "charge": 200, "mult": 2, "anim": "alex", "scene": {"image": "skill_alex.webp", "focus": "45% 25%"}, "text": "号令で奮い立ち、次の攻撃のダメージが2倍"}},
    {"lv": 4,  "name": "魔導戦術家、セリス",       "hp": 16, "atk": 2, "def": 5, "max": {"hp": 45, "atk": 6, "def": 18},  "image": "ally_04.webp", "unlock": {"min_difficulty": "normal", "stage": 3, "chance": 0.30},
     "abilities": [{"stat": "atk", "value": 1}, {"stat": "atk", "value": 1}, {"stat": "hp", "value": 10}], "skill": {"name": "魔法障壁", "type": "barrier", "charge": 250, "blocks": 2, "anim": "celis", "scene": {"image": "skill_celis.webp", "focus": "40% 35%"}, "text": "魔法陣の障壁で敵の攻撃2回を無効にし、状態異常も治す"}},
    {"lv": 5,  "name": "先鋭近衛騎士、アーサー",   "hp": 22, "atk": 4, "def": 4, "max": {"hp": 60, "atk": 11, "def": 13},  "image": "ally_05.webp", "unlock": {"min_difficulty": "hard", "stage": 1, "chance": 0.30},
     "abilities": [{"stat": "def", "value": 2}, {"stat": "def", "value": 2}, {"stat": "hp", "value": 15}], "skill": {"name": "聖盾撃", "type": "strike", "charge": 300, "power": 60, "guard": 2, "anim": "arthur", "text": "聖なる盾ごと突撃。攻撃力×60 のダメージと、2ターン防御力2倍"}},
    {"lv": 6,  "name": "古代魔導研究者、エリナ",   "hp": 30, "atk": 6, "def": 3, "max": {"hp": 70, "atk": 17, "def": 8},  "image": "ally_06.webp", "unlock": {"min_difficulty": "normal", "stage": 6, "chance": 0.40},
     "abilities": [{"stat": "hp", "value": 5}, {"stat": "hp", "value": 5}, {"stat": "def", "value": 8}], "skill": {"name": "古代魔法・崩壊", "type": "strike", "charge": 350, "power": 70, "pierce": True, "anim": "erina", "text": "古代文字が崩れ落ちる。攻撃力×70 の防御無視ダメージ"}},
    {"lv": 7,  "name": "王宮近衛隊長、ガイウス",   "hp": 45, "atk": 10, "def": 6, "max": {"hp": 95, "atk": 26, "def": 14},  "image": "ally_07.webp", "unlock": {"min_difficulty": "normal", "stage": 7, "chance": 0.20},
     "abilities": [{"stat": "atk", "value": 2}, {"stat": "atk", "value": 2}, {"stat": "atk", "value": 6}], "skill": {"name": "百裂剣", "type": "strike", "charge": 350, "power": 80, "anim": "gaius", "text": "目にも止まらぬ百の斬撃。攻撃力×80 のダメージ"}},
    {"lv": 8,  "name": "魔導工学の至高者、レイノ", "hp": 63, "atk": 13, "def": 15, "max": {"hp": 125, "atk": 28, "def": 32}, "image": "ally_08.webp", "unlock": {"min_difficulty": "hard", "stage": 5, "chance": 0.60},
     "abilities": [{"stat": "def", "value": 3}, {"stat": "def", "value": 3}, {"stat": "atk", "value": 8}], "skill": {"name": "魔導砲", "type": "strike", "charge": 400, "power": 70, "pierce": True, "stun": 1, "anim": "reino", "text": "魔導砲の光線。攻撃力×70 の防御無視ダメージと、敵を1ターン動けなくする（雷が効かない敵にも効く）"}},
    {"lv": 9,  "name": "概念の卵、ガレン",         "hp": 73, "atk": 20, "def": 19, "max": {"hp": 150, "atk": 36, "def": 40}, "image": "ally_09.webp", "unlock": {"min_difficulty": "hard", "stage": 5, "chance": 0.30},
     "abilities": [{"stat": "hp", "value": 10}, {"stat": "hp", "value": 10}, {"stat": "def", "value": 15}], "skill": {"name": "概念崩し", "type": "break", "charge": 250, "turns": 3, "anim": "garen", "text": "敵の「守る」という概念を壊し、3ターン敵の防御を0にする"}},
    {"lv": 10, "name": "至高の光帝、ルナ",         "hp": 100, "atk": 33, "def": 35, "max": {"hp": 160, "atk": 50, "def": 52}, "image": "ally_10.webp", "unlock": {"min_difficulty": "very_hard", "stage": 7, "chance": 0.20},
     "abilities": [{"stat": "atk", "value": 3}, {"stat": "atk", "value": 3}, {"stat": "hp", "value": 40}], "skill": {"name": "光帝の裁き", "type": "strike", "charge": 500, "power": 120, "pierce": True, "anim": "luna", "text": "天から光の柱が降りる。攻撃力×120 の防御無視ダメージ"}},
    # エクストラステージ（極点の宇宙龍）を倒すと、必ず仲間になる（unlock の extra）。いちばん強いキャラ
    {"lv": 11, "name": "極点の宇宙龍、アステル",   "hp": 120, "atk": 40, "def": 42, "max": {"hp": 200, "atk": 62, "def": 65},
     "image": "ally_11.webp", "unlock": {"extra": True, "chance": 1.0},
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
    {"id": "elixir",       "icon": "✨", "name": "エリクサー",       "heal_rate": 1.0, "cure": [], "guard": 3, "atk_bonus": 0, "atk_turns": 0, "weight": 5},
    {"id": "panacea",      "icon": "🌿", "name": "万能薬",           "heal_rate": 0.0, "cure": ["poison", "thunder", "fire"], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 25},
    {"id": "seal_scroll",  "icon": "📜", "name": "封炎の巻物",       "heal_rate": 0.0, "cure": [], "ward": 3, "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 10,
     "where": {"hard": 5, "very_hard": 5}},
    {"id": "purge_scroll", "icon": "🔥", "name": "黒炎払いの巻物",   "heal_rate": 0.0, "cure": ["black_flame"], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 10,
     "where": {"normal": 7, "hard": 5, "very_hard": 5}},
    {"id": "holy_circle",  "icon": "🔯", "name": "浄化の魔法陣",     "heal_rate": 0.0, "cure": ["poison", "thunder", "fire", "black_flame"], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 5,
     "where": {"easy": 10, "normal": 9, "hard": 8, "very_hard": 7}},
    # アステルの援護のあとにだけ出る、特別なアイテム（宝箱・ログインボーナス・最初の配布には出ない）
    #   special   : 特別なアイテム（宝箱などから出ない）
    #   home_use  : ホーム（倉庫とリュックの画面）で使う。"level_up" はいまのキャラのレベルを1上げる
    #   assist    : 戦闘で使うと、アステルの援護を呼ぶ（この戦闘のあいだ、精霊の加護も受けられる）
    {"id": "white_scale",  "icon": "🐉", "name": "白龍の鱗",         "heal_rate": 0.0, "cure": [], "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0,
     "special": True, "home_use": "level_up"},
    {"id": "spirit_feather", "icon": "🪶", "name": "精霊の羽",       "heal_rate": 1.0, "cure": ["poison", "thunder", "fire", "black_flame", "darkness", "shadow"],
     "guard": 0, "atk_bonus": 0, "atk_turns": 0, "weight": 0, "special": True, "assist": True},
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
ASSIST = {"chance": 0.01, "ally": 11, "level": 10, "image": "assist_sky.webp", "skill_image": "skill_astel_assist.webp",
          "drops": ["white_scale", "spirit_feather"]}

