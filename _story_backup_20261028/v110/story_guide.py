"""ストーリーモードの「攻略」ページ（味方・装備とアイテム・敵・攻略のコツ）

数字は story_data.py から読み、確率は「ときどき」「ごく稀に」などの言い方で出す（nuance）。
Lv.10 と Lv.11 の2体は「謎多き者」として、名前を伏せ、形だけの絵（当たりマスクから作る影）で見せる。
"""
import html

import streamlit as st

import story_assets
import story_data
import story_logic as L

STAT_NAMES = {"hp": "HP", "atk": "攻撃力", "def": "防御力"}

# 謎多き者（名前を伏せ、影だけ見せる）
MYSTERY = {"enemy_10", "enemy_11_hard", "enemy_11_veryhard"}

ALLY_TEXT = {
    1: "村で畑をたがやしていた青年。力は弱いが、ここからすべてが始まる。",
    2: "村を守る自警団に入ったばかり。守りの心得を少しずつ身につけていく。",
    3: "若くして中隊を率いる新兵の隊長。体力と腕力のバランスがよい。",
    4: "魔法で戦況を読む戦術家。守りが固く、粘り強く戦える。",
    5: "王を守る近衛騎士のえりすぐり。どんな局面でも崩れない。",
    6: "古代の魔導を研究する学者。打たれ強さと一撃の重さを兼ね備える。",
    7: "王宮の近衛隊をまとめる隊長。鍛えるほどに攻撃力がのびる。",
    8: "魔導と機械を極めた天才。守りも攻めも高い水準にある。",
    9: "まだ形の定まらない「概念」そのもの。底知れない力を秘める。",
    10: "光の国をすべる帝。ほかのだれも寄せつけない力を持つ。",
    11: "ステージの番人だった宇宙龍が、心を通わせて仲間になった姿。背に乗る天使とともに、銀河そのものの力をふるう。",
    12: "森の入り口を守る槍の使い手。鹿の紋の盾をかかげ、迷いこんだ旅人を助けてきた。",
    13: "森の奥で薬草を育てる年老いた薬師。土と草の声を聞き、傷も心もいやす。",
    14: "古い大樹に宿った魂が、戦士の姿になった者。森を荒らす者には容赦しない。",
    15: "翠玉の杖で大地を操る魔女。森の結晶から力を引き出す。",
    16: "蔦の鎧に身を包む騎士。ルーンの盾で仲間を守り、茨のように斬りこむ。",
    17: "森の魔法を極めた大賢者。古い魔法陣と書物の知恵で、嵐さえ呼ぶ。",
    18: "森の微精霊たちが慕い、集う大精霊。まわりを舞う色とりどりの光の粒は、彼女を慕う微精霊。黒翼の執行者に乱された森を見守っている。",
}

ENEMY_TEXT = {
    "enemy_01": "墓地をさまよう、なれの果て。動きはにぶいが、油断は禁物。",
    "enemy_02": "呪いにとらわれた元・剣士。いまも主のない戦いを続けている。",
    "enemy_03": "姿を消して背後にしのびよる暗殺者。打たれ弱いぶん、すばやい。",
    "enemy_04": "骨だけになっても魔術を捨てなかった魔術師。祭壇で力をたくわえている。",
    "enemy_05": "深淵に仕える従者。鞭で獲物を闇へ引きずり込む。",
    "enemy_06": "死霊の軍勢をひきいる将軍。重い一撃をふるう。",
    "enemy_07": "高い身分をほこる悪魔。触れた者に毒をまとわせる。",
    "enemy_08": "玉座から動かない半神の王。雷で相手の動きを封じる。",
    "enemy_09": "災いを運ぶ代行者。毒・雷・火をあやつり、すべてを無に還そうとする。",
}

MYSTERY_TEXT = {
    "enemy_10": ("？？？ ― 終わりを告げる者",
                 "ノーマル以下では最後に待つ者。世界の始まりと終わりを知るという。"
                 "体力が半分を切ると、なにかを唱えはじめる……。"),
    "enemy_11_hard": ("？？？ ― はじまりの光",
                      "ハード以上でだけ姿を見せる。光の輪をまとい、すべてはそこから生まれたと語る。"
                      "近づくと、あたりが暗くなるという。"),
    "enemy_11_veryhard": ("？？？ ― 声なき者",
                          "ベリーハードの最奥に、ひとことも話さずに座っている。"
                          "その姿を見た者は、自分の攻撃がすり抜けるような感覚をおぼえるという。"),
}

# 倒したあとに見せる、謎の敵の本当の姿の説明
REVEAL_TEXT = {
    "enemy_10": "世界を創り、そして終わらせてきた創造主。体力が半分を切るとメテオを詠唱し、"
                "次の攻撃で大きなダメージと黒炎を与えてくる。詠唱が見えたら、回復と封炎の巻物で備えよう。",
    "enemy_11_hard": "光の輪と水晶をまとう、すべての始まり。メテオに加えて、あたりを暗くする「陰」で当たる範囲を狭めてくる。"
                     "体の中心をねらって連打しよう。ベリーハードでは、最後の者の前に立ちはだかる。",
    "enemy_11_veryhard": "ひとことも話さない、ベリーハードの最奥の存在。陰に加えて、攻撃をすり抜けさせる「影」を使う。"
                         "必殺技やアイテムを出し惜しみせず、全力で挑もう。",
}

EXTRA_TEXT = ("各ステージを見回っている「ステージの番人」。謎多き者たちの使者だといわれる。"
              "ステージを進むうちに、ごく稀に行く手に現れる。逃げることもできるが、倒せば見たことのない装備が手に入り、さらに……。"
              "追いつめると真の姿に目覚めて大きく傷をいやし、守りの術ごと焼きはらう黒き業火を放つという。業火を受けると黒炎になり、しばらく防御力が半分になる。")

ULTRA_HOW = {
    "dragon_scale": "ステージの番人（極点の宇宙龍）を倒す",
    "origin_robe": "ハード以上で「はじまりの光」を倒す",
    "silence_blade": "ベリーハードで「声なき者」を倒す",
}

TIPS = [
    ("魔法と詠唱", "「魔法」をえらぶと詠唱が始まる。画面の円の中だけ数える（円の外のタップは数えない）。"
               "攻撃魔法は4秒のあいだに押した回数ぶん強くなり、上限はない（1タップ ＝ 魔力 × 消費MP × 0.1。敵1体は1.5倍、敵全体は0.45倍）。"
               "回復・強化の魔法は、押した数で詠唱率が決まり、魔力が高いほど少ない連打で満点になる（最低10%）。"
               "強い魔法ほど円が小さい。詠唱で押した回数も、必殺技のチャージになる。"
               "魔法を使ったターンは攻撃できない。MPはステージをクリアすると少し回復し、戦いが終わると全回復する。"),
    ("ねらい（敵1体の魔法）", "敵1体の攻撃魔法は、詠唱のあとに円が画面を動きまわる。タップで止めよう。"
                      "円の中に赤い点（弱点）があれば1.5倍、敵の体が全部入れば1倍、一部なら0.8倍、何も入らなければ0.1倍。"),
    ("パーティ", "ホームのカードを左右にスライドして、リーダー1人とサブ2人までを決める（上のわくを押すと、そのキャラのカードへ）。1人ずつ順番に動き、敵は毎回だれか1人をねらう。"
             "戦闘中に「サブ オート」を押すと、サブが自分で連打・魔法をする（連打はだいたい40〜67回くらい。ねらいは円が大きい魔法ほど当たりやすい）。"
             "倒れた仲間は戦闘不能になり、いのちの葉・不死鳥の羽・リバイブでしか戻らない（ホームに戻れば元どおり）。"
             "回復のアイテムや魔法は、だれに使うかえらべる。経験値は全員が同じだけもらえる。敵の強さは人数で変わらない。"),
    ("魔法系とそれ以外", "キャラは「魔法系」と「戦士系」に分かれる。魔法系はMP・魔力が高く、魔法を5つ覚えて攻撃・全体攻撃・回復・状態異常の回復が得意。"
                   "そのかわり攻撃力が低く、連打はねらった敵1体（光っている敵）にしか当たらない。"
                   "戦士系はHP・攻撃力が高く、連打は当てた敵すべてに当たる。魔法は味方1人や味方全員を強くする補助が中心。"
                   "万能（アステル）は連打が何体にも当たり、敵1体・敵全体の攻撃魔法も補助も使える。"
                   "必殺技は、魔法系・万能が範囲（敵全体に1体あたり0.7倍／味方全員）、戦士系が単体（敵1体・自分）。"),
    ("ボス戦", "ボスが1体だけの戦いでは、ボスはパーティ全員への全体攻撃が多く、1人をねらう攻撃はとても強い。HPの多い仲間や防御の魔法でしのごう。"),
    ("敵が何体も", "1ステージに敵が何体も出る。自分のターンに敵をタップすると、魔法・必殺技でねらう敵が変わる。"
               "連打は当てた敵にそれぞれダメージが入る。回復役の敵は先に倒そう。敵全体の魔法は全員に当たる。"),
    ("弱点と耐性", "Lv.5 より強い敵には、魔法の弱点（1.5倍）と耐性（半分）がある。弱点は戦闘画面の上に出るけど、耐性は使ってみないとわからない。"
               "剣の攻撃は属性に関係ないので、弱点の魔法がなくても必ず倒せる。魔導書で好きな属性の魔法を覚えよう。"),
    ("会心", "連打の1回ごとに、会心率でその1回のダメージが2倍になる（敵の防御は効いたまま）。魔法は会心率の半分の確率で1.5倍。会心の薬で上げられる。"),
    ("マニーとショップ", "ステージをクリアするとマニーがもらえる。難しい難易度・先のステージほど多い。全クリアやエクストラでボーナス。"
                     "ショップでアイテムを買える。いらないアイテムは半分の値段で売れる。"),
    ("連打のコツ", "1本指より、3本指で交互にタップするとコンボがぐんと伸びる。慣れてきたら、両手の6本指でタップするのもおすすめ。"
                "ただし両手だと手で画面がかくれて、敵に当たっているか（タップが当たる範囲の中か）が見えにくくなるので気をつけよう。"
                "外れたタップはコンボにならないから、ときどき手をずらして敵の位置を確かめよう。"),
    ("毒・雷・火", "ポーション類では治らない。万能薬か浄化の魔法陣で治そう。治しても、そのターンに攻撃できる。"),
    ("黒炎", "黒炎払いの巻物か浄化の魔法陣で消せる。封炎の巻物を先に使えば、しばらく黒炎にかからない（メテオのあとの黒炎も）。"),
    ("雷", "しびれて攻撃できないあいだも、アイテムは使える。万能薬で治せば、そのターンに攻撃できる。"),
    ("メテオの詠唱", "予告が出たら、次の敵の攻撃は大ダメージ。そのあいだに回復しておこう。"),
    ("陰", "当たる範囲が真ん中に寄る。敵の体の中心をねらって連打しよう。"),
    ("影", "攻撃をまるごとかわされることがある。自分の攻撃の回数で消えるので、あせらず攻撃を続けよう。"),
    ("攻撃力アップ", "1タップごとに効くので、たくさん当てられる人ほど得をする。"),
    ("必殺技", "敵に当てた回数でチャージがたまり、ステージをまたいでも残る。ボスまでためておくのも作戦。"
             "負けてやり直すと、そのステージを始めたときのチャージに戻る。"),
    ("リュック", "戦闘で使ったアイテムは、負けたり「やめる」で抜けたりしても戻らない。ここぞというときに使おう。"),
    ("剣の属性", "毒・火・黒炎は、当たった攻撃が強いほど追加ダメージも大きくなる。属性の剣は1本しか付けられないので、いちばん合う1本をえらぼう。"),
    ("ステージの番人", "勝てないと思ったら「にげる」を。負けても、もう一度戦うか先へ進むかをえらべる。"
                     "倒せば、いちばん強い仲間が加わる。"),
]

CSS = """
<style>
.sg-card { display:flex; gap:12px; align-items:flex-start; padding:10px; margin:0 0 10px; border-radius:12px;
  background:#16121a; border:1px solid rgba(233,214,166,.22); color:#f4ecda; }
.sg-card img.pic { width:30%; max-width:150px; max-height:150px; border-radius:10px; flex:none; object-fit:contain; background:#0c0b10; }
.sg-card img.pic.small { width:64px; height:64px; }
.sg-card .body { flex:1; min-width:0; font-size:14px; line-height:1.55; }
.sg-card .ttl { font-weight:700; font-size:16px; color:#e9d6a6; }
.sg-card .sub { font-size:12px; color:#b9ab90; }
.sg-card .chips { display:flex; flex-wrap:wrap; gap:4px; margin-top:4px; }
.sg-card .chip { display:inline-flex; align-items:center; gap:3px; font-size:12px; padding:1px 7px; border-radius:99px;
  background:#2a2030; border:1px solid rgba(255,255,255,.15); }
.sg-card .chip img { width:16px; height:16px; border-radius:50%; }
.sg-card .gray { filter:grayscale(1) brightness(.5); }
</style>
"""


def nuance(p):
    """確率を言葉で（数字は出さない）"""
    if p < 0.2:
        return "ごく稀に"
    if p < 0.4:
        return "稀に"
    if p < 0.6:
        return "ときどき"
    if p < 0.85:
        return "よく"
    return "ほぼ必ず"


def nuance_weight(weight):
    """宝箱の中での出やすさ（ほかの物とくらべた言い方）"""
    if weight >= 40:
        return "よく"
    if weight >= 20:
        return "ときどき"
    if weight >= 10:
        return "稀に"
    return "ごく稀に"


def esc(text):
    return html.escape(str(text))


def card(pic, title, sub, body, chips="", small=False, gray=False):
    cls = "pic" + (" small" if small else "") + (" gray" if gray else "")
    img = f'<img class="{cls}" src="{pic}" alt="">' if pic else ""
    return (f'<div class="sg-card">{img}<div class="body"><div class="ttl">{title}</div>'
            f'<div class="sub">{sub}</div><div>{body}</div>'
            + (f'<div class="chips">{chips}</div>' if chips else "") + "</div></div>")


def status_chips(ids):
    out = []
    for sid in ids:
        effect = story_data.STATUS_EFFECTS[sid]
        icon = story_assets.status_thumb(sid)
        img = f'<img src="{icon}" alt="">' if icon else effect["icon"]
        out.append(f'<span class="chip">{img}{esc(effect["name"])}</span>')
    return "".join(out)


def join_text(ally):
    cond = ally["unlock"]
    if not cond:
        return "最初から仲間"
    if cond.get("extra"):
        return "ステージの番人（極点の宇宙龍）を倒すと、必ず仲間になる"
    if cond.get("kz_extra"):
        return "風哭きの森のエクストラ（黒翼の執行者）を倒すと、必ず仲間になる"
    diff = L.get_difficulty(cond["min_difficulty"])["name"]
    scope = "で" if cond["min_difficulty"] == "very_hard" else "以上で"
    where = "風哭きの森の" if cond.get("quest") == "kz" else ""
    return f"{where}{diff}{scope}ステージ{cond['stage']}をクリアすると、{nuance(cond['chance'])}仲間になる"


def ability_text(ally):
    return "・".join(L.ability_label(a) for a in ally["abilities"])


def section_allies(profile):
    owned = set(L.owned_allies(profile))
    parts = [f"<p style='font-size:14px'>キャラはみんな Lv.1 から始まり、Lv.{story_data.LEVEL_MAX} まで育つ。"
             "挑戦を終えるたびにたまるポイントでレベルが上がり、後のレベルほど上がりにくいが、ステータスも大きく伸びる。"
             "強いキャラほど、育てるのに時間がかかる。</p>"]
    for ally in story_data.ALLIES:
        lv = ally["lv"]
        low, high = L.base_stats(lv, 1), L.base_stats(lv, story_data.LEVEL_MAX)
        stats = (f"HP {low['hp']:g}→{high['hp']:g}　攻撃力 {low['atk']:g}→{high['atk']:g}　"
                 f"防御力 {low['def']:g}→{high['def']:g}　MP {low['mp']:g}→{high['mp']:g}　魔力 {low['mag']:g}→{high['mag']:g}"
                 f"（Lv.1→Lv.{story_data.LEVEL_MAX}）　会心率 {(ally.get('magic') or {}).get('crit', 0):.0%}")
        skill = ally["skill"]
        cls = {"magic": "魔法系（連打は敵1体・魔法が得意・必殺技は範囲）",
               "all": "万能（連打は複数の敵に当たる・攻撃も補助も使える魔法・必殺技は範囲）"}.get(
            ally.get("class"), "戦士系（連打は複数の敵に当たる・補助の魔法・必殺技は単体）")
        body = (f"<b>タイプ：</b>{cls}<br>{esc(ALLY_TEXT.get(lv, ''))}<br><b>仲間になるには：</b>{esc(join_text(ally))}"
                f"<br><b>必殺技：</b>{esc(skill['name'])}（コンボ{skill['charge']}でチャージ）― {esc(L.skill_target_tag(lv) + skill['text'])}"
                f"<br><b>アビリティ：</b>{esc(ability_text(ally))}（たくさん遊ぶと順に解放）"
                f"<br><b>覚える魔法：</b>" + esc("、".join(f"Lv.{sp['level']} {L.get_spell(sp['id'])['name']}（{L.spell_short_text(sp['id'])}）"
                                                     for sp in L.level_spells(lv, 1))))
        if lv in owned:
            mark = f"✅ 仲間（いま Lv.{L.ally_level(profile, lv)}）"
        else:
            mark = "🔒 まだ仲間ではない"
        parts.append(card(story_assets.ally_thumb(lv), esc(ally["name"]), f"{stats}　／　{mark}", body,
                          gray=lv not in owned))
    st.markdown(CSS + "".join(parts), unsafe_allow_html=True)


def equip_how(equip):
    if equip["rank"] == "ultra":
        return ULTRA_HOW.get(equip["id"], "？？？")
    if equip.get("roll"):
        diff = L.get_difficulty(equip["roll"]["difficulty"])["name"]
        return f"{diff}の宝箱から（どのステージでも）。ステージの後半ほど、数値の高い物が出やすい"
    rank = story_data.EQUIP_RANKS[equip["rank"]]
    diff_id = equip.get("min_difficulty") or rank["min_difficulty"]
    diff = "" if diff_id == "easy" else f"{L.get_difficulty(diff_id)['name']}以上の"
    stage = "どのステージでも" if rank["min_stage"] <= 1 else f"ステージ{rank['min_stage']}以降で"
    return f"宝箱から（{diff}{stage}）。{nuance_weight(rank['weight'])}出る"


def equip_effect(equip):
    if equip["rank"] == "ultra":
        return "？？？　まだだれも使ったことのない、未知の装備。"
    return L.equip_effect_text(equip["id"])


def section_equipment():
    parts = [f"<p style='font-size:14px'>宝箱はステージをクリアすると{nuance(story_data.TREASURE_CHANCE)}出る。"
             "中身はアイテムのことが多く、装備は難しい難易度・先のステージほど良い物が出る。</p>"]
    for rank_id, rank in story_data.EQUIP_RANKS.items():
        rows = [e for e in story_data.EQUIPMENT if e["rank"] == rank_id]
        parts.append(f"<h4 style='color:#e9d6a6;margin:14px 0 6px'>{esc(rank['name'])}</h4>")
        for equip in rows:
            sub = "アクセサリ（3つまで・同じ物は1つ）" if rank_id in story_data.ACCESSORY_RANKS else "装備品（3つまで）"
            body = f"<b>効果：</b>{esc(equip_effect(equip))}<br><b>手に入れ方：</b>{esc(equip_how(equip))}"
            parts.append(card(story_assets.equipment_thumb(equip["id"]), esc(equip["name"]), sub, body, small=True))
    group = [s for s in story_data.ATTR_GROUP]
    solo = [s for s in story_data.ATTR_SOLO]
    parts.append("<h4 style='color:#e9d6a6;margin:14px 0 6px'>剣の属性</h4>")
    parts.append(card(None, "剣に宿る力", "木の剣・鋼の剣・聖剣", (
        "宝箱から出た剣には、属性が宿っていることがある。難しい難易度ほど宿りやすく、"
        "ベリーハードではほぼ必ず宿る。ひとつの剣に、多いと3つまで宿る。"
        "攻撃が当たったときに、剣ごとに決まった確率で発動し、敵に状態異常をかける。"
        "黒炎・陰・影はハード以上の剣にだけ宿る。属性の剣は1本しか付けられない。"),
        chips=status_chips(group + solo)))
    parts.append("<h4 style='color:#e9d6a6;margin:14px 0 6px'>アイテム</h4>")
    for item in story_data.ITEMS:
        effect = [L.item_effect_text(item)]
        where = item.get("where")
        if item.get("special"):
            how = "まれに空から現れる者の援護を受け、そのステージをクリアすると手に入る（2種類のどちらか）"
        elif item.get("boss"):
            how = "ボス（最後のステージの敵・宇宙龍）を倒すと手に入ることがある" + ("。はじめて全クリアしたときにも1冊もらえる" if item.get("home_use") == "learn" else "")
        elif L.buy_price(item["id"]):
            how = f"ショップで {L.buy_price(item['id']):,}{story_data.MONEY_NAME}" + (f"。宝箱からも{nuance_weight(item['weight'])}出る" if item["weight"] else "")
        elif where:
            cond = "・".join(f"{L.get_difficulty(d)['name']}{n}" for d, n in where.items())
            how = f"宝箱から（{cond} 以上のステージ）。{nuance_weight(item['weight'])}出る"
        else:
            how = f"宝箱から{nuance_weight(item['weight'])}出る"
        parts.append(card(story_assets.item_thumb(item["id"]), esc(item["name"]), how, esc("・".join(effect)), small=True))
    st.markdown(CSS + "".join(parts), unsafe_allow_html=True)


def section_enemies(profile):
    defeated = set(profile.get("defeated") or [])
    parts = ["<p style='font-size:14px'>影になっている敵は、倒すと本当の姿と詳しいことがわかる。</p>"]
    seen = set()
    for enemy in story_data.ENEMIES:
        key = L.enemy_key(enemy)
        if key in seen:
            continue
        seen.add(key)
        where = ("ハード・ベリーハード" if enemy["difficulties"] == ["hard", "very_hard"]
                 else "ベリーハードだけ" if enemy["difficulties"] == ["very_hard"] else "すべての難易度")
        gimmicks = [g for g in enemy["gimmicks"] if g != "meteor"]
        beaten = "　✅ 倒した" if key in defeated else ""
        if key in MYSTERY and key in defeated:      # 倒したことのある謎の敵は、本当の姿を見せる
            chips = status_chips(gimmicks) + '<span class="chip">天変地異：雷が効かない</span>'
            if "meteor" in enemy["gimmicks"]:
                chips = '<span class="chip">☄️ メテオ</span>' + chips
            parts.append(card(story_assets.thumb_uri(f"enemies/{enemy['image']}", 240),
                              f"Lv.{enemy['lv']} {esc(enemy['name'])}", f"{where}{beaten}", esc(REVEAL_TEXT[key]), chips=chips))
        elif key in MYSTERY:
            title, text = MYSTERY_TEXT[key]
            chips = status_chips(gimmicks[:2]) + '<span class="chip">…ほか、得体の知れない力</span>'
            parts.append(card(story_assets.silhouette_uri(key), esc(title), f"Lv.{enemy['lv']}　{where}",
                              esc(text), chips=chips))
        else:
            chips = status_chips(gimmicks)
            if "thunder" in enemy.get("immune", []):
                chips += '<span class="chip">天変地異：雷が効かない</span>'
            parts.append(card(story_assets.thumb_uri(f"enemies/{enemy['image']}", 240), f"Lv.{enemy['lv']} {esc(enemy['name'])}",
                              where + beaten, esc(ENEMY_TEXT.get(key, "")), chips=chips))
    # 風哭きの森の敵（倒すと姿がわかる）
    parts.append(f"<h4 style='color:#9fe8b9;margin:18px 0 6px'>{story_data.KZ_QUEST['icon']} {story_data.KZ_QUEST['name']}の敵</h4>")
    role_name = {"zako": "ザコ", "healer": "回復役（仲間を回復する。先に倒そう）", "tank": "盾役（HPが多い）", "fast": "すばやい",
                 "mage": "魔法使い", "stone": "石の体（剣が半分しか効かない。魔法で）", "midboss": "中ボス", "boss": "ボス", "extra": "エクストラ"}
    for e in story_data.KZ_ENEMIES + [story_data.KZ_EXTRA_ENEMY]:
        key = e["id"]
        seen_it = key in defeated
        weak = story_data.ELEMENTS[e["weak"]] if e.get("weak") else None
        traits = [role_name.get(e["role"], "")] + (["1ターンに2回攻撃"] if e.get("double") else []) + (["力をためて重い一撃"] if e.get("heavy") else [])
        body = "・".join(t for t in traits if t) + (f"<br><b>弱点：</b>{weak['icon']}{weak['name']}の魔法" if weak and seen_it else "")
        if e.get("awaken") and seen_it:
            body += f"<br><b>覚醒：</b>HPが半分を切ると「{esc(e['awaken']['name'])}」に変わる"
        pic = story_assets.thumb_uri(f"enemies/{e['image']}", 240) if seen_it else story_assets.silhouette_uri(key)
        parts.append(card(pic, esc(e["name"]) if seen_it else "？？？", ("✅ 倒した" if seen_it else "まだ見ぬ敵"),
                          body if seen_it else "倒すと、くわしいことがわかる。", chips=status_chips([g for g in e["gimmicks"] if g != "meteor"]) if seen_it else ""))
    extra = story_data.EXTRA_ENEMY
    chips = status_chips(extra["gimmicks"]) + '<span class="chip">天変地異：雷が効かない</span>'
    parts.append(card(story_assets.thumb_uri(f"enemies/{extra['image']}", 300), f"Lv.??? {esc(extra['name'])}",
                      f"{esc(extra['title'])}　／　HP ???　攻撃力 ???　防御力 ???", esc(EXTRA_TEXT), chips=chips))
    st.markdown(CSS + "".join(parts), unsafe_allow_html=True)


def section_tips():
    parts = [card(None, esc(title), "", esc(text)) for title, text in TIPS]
    st.markdown(CSS + "".join(parts), unsafe_allow_html=True)


def render(profile, box=None):
    """攻略ページ。box を渡すと、タブの中身をその箱（中だけスクロール）に入れる。タブ自体は箱の上に出る"""
    from contextlib import nullcontext
    wrap = box or (lambda i: nullcontext())
    tab_ally, tab_equip, tab_enemy, tab_tips = st.tabs(["味方", "装備・アイテム", "敵", "攻略のコツ"])
    with tab_ally, wrap(0):
        section_allies(profile)
    with tab_equip, wrap(1):
        section_equipment()
    with tab_enemy, wrap(2):
        section_enemies(profile)
    with tab_tips, wrap(3):
        section_tips()
