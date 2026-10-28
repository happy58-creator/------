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

EXTRA_TEXT = ("各ステージを見回っている「ステージの番人」。謎多き者たちの使者だといわれる。"
              "ステージを進むうちに、ごく稀に行く手に現れる。逃げることもできるが、倒せば見たことのない装備が手に入るという。")

ULTRA_HOW = {
    "dragon_scale": "ステージの番人（極点の宇宙龍）を倒す",
    "origin_robe": "ハード以上で「はじまりの光」を倒す",
    "silence_blade": "ベリーハードで「声なき者」を倒す",
}

TIPS = [
    ("毒・火・黒炎", "ポーション類で治る。治しても、そのターンに攻撃できるよ。長い戦いになる敵には、よけのアクセサリが効く。"),
    ("雷", "しびれて攻撃できないあいだも、アイテムは使える。ポーションで治せば、そのターンに攻撃できる。"),
    ("メテオの詠唱", "予告が出たら、次の敵の攻撃は大ダメージ。そのあいだに回復しておこう。"),
    ("陰", "当たる範囲が真ん中に寄る。敵の体の中心をねらって連打しよう。"),
    ("影", "攻撃をまるごとかわされることがある。自分の攻撃の回数で消えるので、あせらず攻撃を続けよう。"),
    ("攻撃力アップ", "1タップごとに効くので、たくさん当てられる人ほど得をする。"),
    ("リュック", "負けても、そのステージを始めたときの中身に戻る。こまめにアイテムを使ってだいじょうぶ。"),
    ("剣の属性", "毒・火・黒炎は、当たった攻撃が強いほど追加ダメージも大きくなる。属性の剣は1本しか付けられないので、いちばん合う1本をえらぼう。"),
    ("ステージの番人", "勝てないと思ったら「にげる」を。負けても、もう一度戦うか先へ進むかをえらべる。"),
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
    diff = L.get_difficulty(cond["min_difficulty"])["name"]
    scope = "で" if cond["min_difficulty"] == "very_hard" else "以上で"
    return f"{diff}{scope}ステージ{cond['stage']}をクリアすると、{nuance(cond['chance'])}仲間になる"


def ability_text(ally):
    return "・".join(f"{STAT_NAMES[a['stat']]}+{a['value']}" for a in ally["abilities"])


def section_allies(profile):
    owned = set(L.owned_allies(profile))
    parts = []
    for ally in story_data.ALLIES:
        lv = ally["lv"]
        stats = f"HP {ally['hp']}　攻撃力 {ally['atk']}　防御力 {ally['def']}"
        body = (f"{esc(ALLY_TEXT.get(lv, ''))}<br><b>仲間になるには：</b>{esc(join_text(ally))}"
                f"<br><b>アビリティ：</b>{esc(ability_text(ally))}（たくさん遊ぶと順に解放）")
        mark = "✅ 仲間" if lv in owned else "🔒 まだ仲間ではない"
        parts.append(card(story_assets.ally_thumb(lv), f"Lv.{lv} {esc(ally['name'])}", f"{stats}　／　{mark}", body,
                          gray=lv not in owned))
    st.markdown(CSS + "".join(parts), unsafe_allow_html=True)


def equip_how(equip):
    if equip["rank"] == "ultra":
        return ULTRA_HOW.get(equip["id"], "？？？")
    rank = story_data.EQUIP_RANKS[equip["rank"]]
    diff_id = equip.get("min_difficulty") or rank["min_difficulty"]
    diff = "" if diff_id == "easy" else f"{L.get_difficulty(diff_id)['name']}以上の"
    stage = "どのステージでも" if rank["min_stage"] <= 1 else f"ステージ{rank['min_stage']}以降で"
    return f"宝箱から（{diff}{stage}）。{nuance_weight(rank['weight'])}出る"


def equip_effect(equip):
    if equip["rank"] == "ultra":
        return "？？？　まだだれも使ったことのない、未知の装備。"
    if equip["resist"]:
        return f"{story_data.STATUS_EFFECTS[equip['resist']]['name']}を半分にする"
    return "・".join(f"{STAT_NAMES[s]}+{equip[s]}" for s in ("hp", "atk", "def") if equip[s])


def section_equipment():
    parts = [f"<p style='font-size:14px'>宝箱はステージをクリアすると{nuance(story_data.TREASURE_CHANCE)}出る。"
             "中身はアイテムのことが多く、装備は難しい難易度・先のステージほど良い物が出る。</p>"]
    for rank_id, rank in story_data.EQUIP_RANKS.items():
        rows = [e for e in story_data.EQUIPMENT if e["rank"] == rank_id]
        parts.append(f"<h4 style='color:#e9d6a6;margin:14px 0 6px'>{esc(rank['name'])}</h4>")
        for equip in rows:
            sub = "アクセサリ（3つまで・同じ物は1つ）" if rank_id == "accessory" else "装備品（3つまで）"
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
        effect = []
        if item["heal_rate"] >= 1:
            effect.append("HPを全回復")
        elif item["heal_rate"]:
            effect.append(f"最大HPの{item['heal_rate']:.0%}を回復")
        if item["cure"]:
            effect.append("状態異常を治す")
        if item["guard"]:
            effect.append(f"{item['guard']}ターン防御力2倍")
        if item["atk_bonus"]:
            effect.append(f"自分の攻撃{item['atk_turns']}回ぶん攻撃力+{item['atk_bonus']}")
        parts.append(card(story_assets.item_thumb(item["id"]), esc(item["name"]),
                          f"宝箱から{nuance_weight(item['weight'])}出る", esc("・".join(effect)), small=True))
    st.markdown(CSS + "".join(parts), unsafe_allow_html=True)


def section_enemies():
    parts = []
    seen = set()
    for enemy in story_data.ENEMIES:
        key = L.enemy_key(enemy)
        if key in seen:
            continue
        seen.add(key)
        where = ("ハード・ベリーハード" if enemy["difficulties"] == ["hard", "very_hard"]
                 else "ベリーハードだけ" if enemy["difficulties"] == ["very_hard"] else "すべての難易度")
        gimmicks = [g for g in enemy["gimmicks"] if g != "meteor"]
        if key in MYSTERY:
            title, text = MYSTERY_TEXT[key]
            chips = status_chips(gimmicks[:2]) + '<span class="chip">…ほか、得体の知れない力</span>'
            parts.append(card(story_assets.silhouette_uri(key), esc(title), f"Lv.{enemy['lv']}　{where}",
                              esc(text), chips=chips))
        else:
            chips = status_chips(gimmicks)
            if "thunder" in enemy.get("immune", []):
                chips += '<span class="chip">天変地異：雷が効かない</span>'
            parts.append(card(story_assets.thumb_uri(f"enemies/{enemy['image']}", 240), f"Lv.{enemy['lv']} {esc(enemy['name'])}",
                              where, esc(ENEMY_TEXT.get(key, "")), chips=chips))
    extra = story_data.EXTRA_ENEMY
    chips = status_chips(extra["gimmicks"]) + '<span class="chip">天変地異：雷が効かない</span>'
    parts.append(card(story_assets.thumb_uri(f"enemies/{extra['image']}", 300), f"Lv.??? {esc(extra['name'])}",
                      f"{esc(extra['title'])}　／　HP ???　攻撃力 ???　防御力 ???", esc(EXTRA_TEXT), chips=chips))
    st.markdown(CSS + "".join(parts), unsafe_allow_html=True)


def section_tips():
    parts = [card(None, esc(title), "", esc(text)) for title, text in TIPS]
    st.markdown(CSS + "".join(parts), unsafe_allow_html=True)


def render(profile):
    tab_ally, tab_equip, tab_enemy, tab_tips = st.tabs(["味方", "装備・アイテム", "敵", "攻略のコツ"])
    with tab_ally:
        section_allies(profile)
    with tab_equip:
        section_equipment()
    with tab_enemy:
        section_enemies()
    with tab_tips:
        section_tips()
