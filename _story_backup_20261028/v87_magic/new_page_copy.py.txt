"""ストーリーモード（イージー・ノーマルは10ステージ、ハードは11、ベリーハードは12ステージ）

流れ： ホーム（キャラ・「装備」「アイテム」） → 「クエスト」（難易度・続きから） → 戦闘 → ステージ間の画面 → … → 終わり
ホームの上に「クエスト」「称号」「攻略」。サイドバーは出さず、右上の「トップへ」でトップページに戻る。
- 進み具合は各ステージの始めに自動で保存する（チェックポイント）。手動の中断セーブはない。
- 負けたとき・「やめる」で戻ったときは、そのステージを始めたときのHPからやり直す（戦闘で使ったアイテムは戻らない）。
- 挑戦が終わるのは、全クリアしたときと「新規にプレイ」を押したとき（負け扱い）だけ。
数値は story_data.py、計算は story_logic.py、保存は story_profile.py にある。
"""
import streamlit as st

import common
import history
import story_assets
import story_battle
import story_data
import story_logic as L
import story_guide
import story_inventory
import story_profile

common.setup_page("ストーリーモード", "⚔️")

USER = st.session_state.get("player_name") or "ななしさん"
STAT_NAMES = {"hp": "HP", "atk": "攻撃力", "def": "防御力", "mp": "MP", "mag": "魔力"}
OUTCOME_NAMES = {"clear": "全クリア", "abandon": "中断"}

common.init_state({
    "story_view": "home",        # home / quest / ally_detail / inventory / guide / titles / shop / spells / battle / between / retry / extra_lost / end
    "story_detail": None,        # キャラ一覧で、くわしく見ているキャラ
    "story_ally": 1,
    "story_difficulty": "easy",
    "story_rewards": None,       # 直前のステージクリアでもらった物
    "story_chest_open": False,
    "story_recruit_shown": 0,    # 仲間入りのカードを何枚目まで見せたか
    "story_summary": None,       # 挑戦が終わったときのまとめ
    "story_notice": None,
    "story_confirm_new": False,  # 「新規にプレイ」の確認を出しているか
})
# 1回の戦闘ごとに増やす番号（前の戦闘の結果をまちがえて拾わないため）
st.session_state.setdefault("story_round", 0)


# ---------------------------------------------------------------------------
# 保存と記録
# ---------------------------------------------------------------------------
def save():
    try:
        story_profile.save_profile(USER, st.session_state.story_profile)
    except Exception as e:
        st.toast(f"セーブできなかったよ：{e}", icon="⚠️")


def log_run(summary, run_id):
    """挑戦が終わったときに1回だけ記録する（全クリア / 中断）"""
    history.log_once(
        "ストーリー", f"story-{run_id}",
        キャラ=L.get_ally(summary["ally"])["name"],
        難易度=L.get_difficulty(summary["difficulty"])["name"],
        結果=OUTCOME_NAMES[summary["outcome"]],
        クリアしたステージ=summary["cleared"],
        アビリティ=f"+{summary['ability_after'] - summary['ability_before']:g}",
        エクストラ="倒した" if summary.get("extra_won") else "",
    )


def choose_ally(lv):
    """キャラをえらぶ（セーブデータにも残して、開き直しても同じキャラにする）"""
    st.session_state.story_ally = lv
    if profile.get("last_ally") != lv:
        profile["last_ally"] = lv
        save()


def go(view):
    st.session_state.story_view = view
    st.rerun()


def go_battle():
    """次の戦闘を始める（その時点のHPとかばんをチェックポイントとして残す）"""
    L.begin_stage(profile)
    save()
    st.session_state.story_round += 1
    go("battle")


# プロフィールは、このページを開いた最初の1回だけ読み込み、あとは手元のコピーを使う
if st.session_state.get("story_profile_user") != USER:
    try:
        loaded = story_profile.load_profile(USER)
    except Exception as e:
        st.error(f"セーブデータを読みこめなかったよ。しばらくしてから開きなおしてね。（{e}）")
        st.stop()
    st.session_state.story_profile = loaded
    st.session_state.story_profile_user = USER
    st.session_state.story_view = "home"
    st.session_state.story_ally = loaded.get("last_ally") or 1      # 前回えらんでいたキャラ（開き直しても、そのまま）
profile = st.session_state.story_profile

# 称号ができる前のデータ：成績の記録から、全クリアした難易度を拾っておく（最初の1回だけ）
if profile.get("titles_seen") is None:
    try:
        _rows = history.read_history("ストーリー")
    except Exception:
        _rows = []
    L.backfill_cleared_modes(profile, _rows, USER)
    save()

# ログインボーナス：その日はじめて開いたら、ランダムでアイテムを1つ（倉庫へ）
_today = __import__("datetime").datetime.now(__import__("zoneinfo").ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")
_bonus = L.daily_bonus(profile, _today)
if _bonus:
    save()
    st.session_state.story_notice = f"🎁 今日のログインボーナス：{L.get_item(_bonus)['name']} を1こ もらったよ（倉庫に入れたよ）"

if st.session_state.story_view in ("battle", "between", "retry", "extra_lost") and not profile["run"]:
    st.session_state.story_view = "home"


# ---------------------------------------------------------------------------
# 表示の部品
# ---------------------------------------------------------------------------
def short_name(lv):
    return L.get_ally(lv)["name"].split("、")[-1]


def ability_text(ability):
    return L.ability_label(ability)


def equip_text(equip, entry=None):
    return L.equip_effect_text(entry or equip["id"])


def attr_text(attrs):
    """剣の属性の説明。例：「毒・火 23%／黒炎 12%」（％は攻撃が当たったときの発動率）"""
    if not attrs:
        return ""
    names = story_data.STATUS_EFFECTS
    group = [a for a in story_data.ATTR_GROUP if a in attrs]
    parts = []
    if group:
        parts.append("・".join(names[a]["icon"] + names[a]["name"] for a in group) + f" {attrs[group[0]]:.0%}")
    parts += [f"{names[a]['icon']}{names[a]['name']} {attrs[a]:.0%}" for a in story_data.ATTR_SOLO if a in attrs]
    return "／".join(parts)


def equip_label(equip, entry=None):
    """装備の名前と効果。entry（倉庫の1件）を渡すと、剣の属性も書く"""
    rank = "【超激レア】" if equip["rank"] == "ultra" else ""
    attrs = attr_text((entry or {}).get("attrs"))
    return f"{equip['icon']} {rank}{equip['name']}（{equip_text(equip, entry)}）" + (f"【属性 {attrs}】" if attrs else "")


def entry_label(entry):
    return equip_label(L.get_equipment(entry["id"]), entry)


def item_label(item_id):
    item = L.get_item(item_id)
    return f"{item['icon']} {item['name']}"


def counts_text(counts):
    return "、".join(f"{item_label(k)} ×{v}" for k, v in counts.items() if v) or "なし"


def hp_bar(hp, max_hp):
    st.progress(min(1.0, max(0.0, hp / max_hp)), text=f"❤️ HP {L.display_hp(hp)} / {max_hp:g}")


def mp_bar(mp, max_mp):
    if max_mp > 0:
        st.progress(min(1.0, max(0.0, mp / max_mp)), text=f"🔮 MP {int(mp)} / {max_mp:g}")


def stage_label(run):
    return "EXTRA STAGE" if run.get("extra") else f"ステージ{run['stage']}"


def ability_gauges(lv, points):
    """アビリティの進み具合（数字は出さず、ゲージだけ）"""
    abilities = L.get_ally(lv)["abilities"]
    for i, (ability, gauge) in enumerate(zip(abilities, L.ability_gauges(points)), start=1):
        if gauge >= 1.0:
            st.markdown(f"✅ アビリティ{i}：**{ability_text(ability)}**")
        else:
            st.progress(gauge, text=f"🔒 アビリティ{i}：{ability_text(ability)}")


def show_stats(lv):
    base = L.ally_stats(lv)
    now = L.ally_stats(lv, profile)
    parts = []
    for stat in ("hp", "atk", "def"):
        extra = now[stat] - base[stat]
        parts.append(f"{STAT_NAMES[stat]} **{now[stat]:g}**" + (f"（+{extra:g}）" if extra else ""))
    st.markdown("　".join(parts))
    if now["resist"]:
        st.caption("たいせい：" + "・".join(story_data.STATUS_EFFECTS[r]["name"] for r in now["resist"]))


def show_ultra(rewards):
    """超激レア装備（特別な敵を倒したときに必ずもらえる）"""
    by_uid = L.equipment_by_uid(profile)
    uids = rewards.get("ultra_uids") or [None] * len(rewards.get("ultra", []))
    for equip_id, uid in zip(rewards.get("ultra", []), uids):
        equip = L.get_equipment(equip_id)
        attrs = attr_text((by_uid.get(uid) or {}).get("attrs"))      # 沈黙の魔剣は属性が付くことがある
        col_icon, col_text = st.columns([1, 4])
        col_icon.image(str(story_assets.equipment_icon_path(equip_id)), width=72)
        col_text.success(f"🌟 超激レア装備 **{equip['name']}** を 手に入れた！（{equip_text(equip)}）"
                         + (f"【属性 {attrs}】" if attrs else "") + " → 倉庫へ")


def show_recruits(rewards):
    """仲間入りのカードを1枚ずつ見せる（Lv の低い順）。全部見せ終わったら True"""
    joined = sorted(rewards["allies"])
    shown = st.session_state.story_recruit_shown
    if shown >= len(joined):
        return True
    lv = joined[shown]
    if shown == 0:
        st.balloons()
    with st.container(border=True):
        col_icon, col_text = st.columns([1, 2])
        col_icon.image(str(story_assets.ally_image_path(lv)), width="stretch")
        with col_text:
            st.markdown(f"### 🤝 {L.get_ally(lv)['name']} が 仲間になった！")
            show_stats(lv)
            rest = len(joined) - shown - 1
            if st.button("つぎへ ▶" if rest else "OK", type="primary", width="stretch", key=f"_story_recruit_{shown}"):
                st.session_state.story_recruit_shown = shown + 1
                st.rerun()
            if rest:
                st.caption(f"ほかにも {rest}人 いるよ！")
    return False


def icon_html(uri, title="", count=None, attrs=(), size=44):
    """小さなアイコン1つ（右下に個数、下に属性の小さなアイコン）"""
    badge = (f"<span style='position:absolute;right:1px;bottom:1px;background:rgba(0,0,0,.8);color:#fff;"
             f"font:700 11px/15px sans-serif;padding:0 4px;border-radius:8px'>{count}</span>") if count else ""
    small = "".join(f"<img src='{a}' style='width:14px;height:14px;border-radius:50%;border:1px solid #8cf;background:#000'>"
                    for a in attrs if a)
    under = f"<div style='display:flex;justify-content:center;gap:1px;margin-top:-6px'>{small}</div>" if small else ""
    return (f"<div title='{title}' style='display:inline-block;margin:2px;vertical-align:top'>"
            f"<div style='position:relative;width:{size}px;height:{size}px'>"
            f"<img src='{uri}' style='width:100%;height:100%;border-radius:8px;object-fit:cover'>{badge}</div>{under}</div>")


def entry_icon(entry, size=44):
    attrs = [story_assets.status_thumb(a) for a in (entry.get("attrs") or {})]
    return icon_html(story_assets.equipment_thumb(entry["id"]), L.get_equipment(entry["id"])["name"], attrs=attrs, size=size)


def item_icon(item_id, count=None, size=44):
    return icon_html(story_assets.item_thumb(item_id), L.get_item(item_id)["name"], count=count, size=size)


def show_rewards(rewards):
    """ステージクリアでもらった物（仲間 → 超激レア → 宝箱の順。宝箱は「あける」を押してから見せる）"""
    if not show_recruits(rewards):
        return False
    show_ultra(rewards)
    if rewards.get("money"):
        st.markdown(f"{story_data.MONEY_ICON} **{rewards['money']:,} {story_data.MONEY_NAME}** を手に入れた！"
                    f"（いま {profile.get('money', 0):,}）")
    if rewards.get("boss_drop"):              # ボスを倒すと特別なアイテム
        drop = rewards["boss_drop"]
        where = "リュックへ" if rewards.get("boss_where") == "pack" else "リュックがいっぱいなので倉庫へ"
        st.success(f"👑 ボスが {L.get_item(drop)['name']} を落とした！ → {where}")
        st.markdown(f"{item_icon(drop)} <b>{L.get_item(drop)['name']}</b>：{L.item_effect_text(L.get_item(drop))}",
                    unsafe_allow_html=True)
    if rewards.get("first_book"):             # はじめての全クリア：魔導書
        book = rewards["first_book"]
        st.success(f"📖 はじめての全クリアのごほうび！ {L.get_item(book)['name']} を手に入れた！ → 倉庫へ")
        st.markdown(f"{item_icon(book)} <b>{L.get_item(book)['name']}</b>：{L.item_effect_text(L.get_item(book))}",
                    unsafe_allow_html=True)
    if rewards.get("assist_drop"):            # アステルの援護のあとは、特別なアイテムが必ず手に入る
        drop = rewards["assist_drop"]
        where = "リュックへ" if rewards.get("assist_where") == "pack" else "リュックがいっぱいなので倉庫へ"
        st.success(f"✨ アステルが {L.get_item(drop)['name']} を残していった！ → {where}")
        st.markdown(f"{item_icon(drop)} <b>{L.get_item(drop)['name']}</b>：{L.item_effect_text(L.get_item(drop))}",
                    unsafe_allow_html=True)
    if rewards.get("extra"):
        return True
    if not rewards["chests"]:
        st.caption("宝箱は 出なかった…")
        return True
    if not st.session_state.story_chest_open:
        st.markdown(f"<div style='font-size:2.6rem;text-align:center'>{'🎁' * rewards['chests']}</div>",
                    unsafe_allow_html=True)
        if st.button(f"🎁 宝箱を あける（{rewards['chests']}こ）", width="stretch"):
            st.session_state.story_chest_open = True
            st.rerun()
        return True
    by_uid = L.equipment_by_uid(profile)
    lines = []
    for i in rewards["items"]:
        lines.append(f"{item_icon(i)} {L.get_item(i)['name']} → リュックへ")
    for i in rewards["sent_home"]:
        lines.append(f"{item_icon(i)} {L.get_item(i)['name']} → リュックがいっぱいなので倉庫へ")
    uids = rewards.get("equipment_uids") or [None] * len(rewards["equipment"])
    for e, u in zip(rewards["equipment"], uids):
        entry = by_uid.get(u) or {"id": e}
        attrs = attr_text(entry.get("attrs"))
        lines.append(f"{entry_icon(entry)} {L.get_equipment(e)['name']}（{equip_text(L.get_equipment(e), entry if 'uid' in entry else None)}）"
                     + (f"【属性 {attrs}】" if attrs else "") + " → 倉庫へ")
    st.markdown("**🎁 宝箱の中身**<br>" + "<br>".join(lines), unsafe_allow_html=True)
    return True


def new_rewards(rewards):
    st.session_state.story_rewards = rewards
    st.session_state.story_chest_open = False
    st.session_state.story_recruit_shown = 0


# ---------------------------------------------------------------------------
# キャラの表示（左に絵と装備のアイコン、右にステータス）
# ---------------------------------------------------------------------------
def ally_panel_html(lv):
    left, right = ally_panel_parts(lv)
    return ("<div style='display:flex;gap:12px;align-items:flex-start'>"
            f"<div style='width:30%;flex:none'>{left}</div><div style='flex:1;min-width:0'>{right}</div></div>")


def ally_panel_parts(lv, split=False):
    """キャラの表示を、左（画像・属性・装備のアイコン）と右（名前・ステータス・必殺技・アビリティ）に分けて返す"""
    ally = L.get_ally(lv)
    points = L.ability_points(profile, lv)
    level, progress = L.level_progress(lv, points)
    base, now = L.base_stats(lv, level), L.ally_stats(lv, profile)      # （+）はアビリティと装備のぶん
    stats = []
    for stat in ("hp", "atk", "def", "mp", "mag"):
        extra = now[stat] - base[stat]
        stats.append(f"{STAT_NAMES[stat]} <b>{now[stat]:g}</b>" + (f"<span style='color:#7fd8a0'>（+{extra:g}）</span>" if extra else ""))
    stats.append(f"会心率 <b>{now['crit']:.0%}</b>")
    exp = ("<div style='font-size:12px;margin-top:4px'>"
           + ("レベル最大！" if level >= story_data.LEVEL_MAX else f"次のレベルまで")
           + "<div style='height:7px;border-radius:4px;background:#2a2228;overflow:hidden'>"
           f"<div style='height:100%;width:{progress * 100:.0f}%;background:linear-gradient(90deg,#4aa3c9,#8fe0ff)'></div></div></div>")
    skill = ally["skill"]
    skill_html = (f"<div style='font-size:12px;margin-top:6px;color:#ffe28a'>✨ 必殺技：<b>{skill['name']}</b>"
                  f"（コンボ{skill['charge']}でチャージ）<div style='color:#d8ccb0'>{skill['text']}</div></div>")
    gauges = []
    for i, (ability, gauge) in enumerate(zip(ally["abilities"], L.ability_gauges(L.ability_points(profile, lv))), start=1):
        mark = "✅" if gauge >= 1 else "🔒"
        gauges.append(f"<div style='font-size:12px;margin-top:4px'>{mark} アビリティ{i}：{ability_text(ability)}"
                      f"<div style='height:6px;border-radius:3px;background:#2a2228;overflow:hidden'>"
                      f"<div style='height:100%;width:{gauge * 100:.0f}%;background:linear-gradient(90deg,#c9a24a,#ffe28a)'></div></div></div>")
    gear, acc = L.split_equipped(profile, lv)
    by_uid = L.equipment_by_uid(profile)
    def icon_row(uids, slots):
        """装備のアイコンを1行に3つ（空いているわくは点線）"""
        cells = [f"<img src='{story_assets.equipment_thumb(by_uid[u]['id'])}' title='{L.get_equipment(by_uid[u]['id'])['name']}' "
                 "style='width:100%;aspect-ratio:1;border-radius:7px;object-fit:cover;display:block'>" for u in uids[:slots]]
        cells += ["<div style='aspect-ratio:1;border-radius:7px;border:1px dashed rgba(233,214,166,.3)'></div>"] * (slots - len(cells))
        return f"<div style='display:grid;grid-template-columns:repeat({slots},1fr);gap:3px;margin-top:4px'>{''.join(cells)}</div>"
    icons = icon_row(gear, story_data.MAX_GEAR_SLOTS) + icon_row(acc, story_data.MAX_ACCESSORY_SLOTS)
    # 剣の属性は、キャラの絵の下のほうに小さく重ねて出す
    attrs = [a for u in gear for a in (by_uid[u].get("attrs") or {})]
    overlay = "".join(
        f"<img src='{story_assets.status_thumb(a)}' title='{story_data.STATUS_EFFECTS[a]['name']}' "
        "style='width:22px;height:22px;border-radius:50%;border:1px solid rgba(140,200,255,.95);"
        "box-shadow:0 1px 4px rgba(0,0,0,.8);background:#000'>" for a in dict.fromkeys(attrs))
    overlay_html = (f"<div style='position:absolute;left:0;right:0;bottom:6px;display:flex;justify-content:center;gap:3px'>"
                    f"{overlay}</div>") if overlay else ""
    resist = now["resist"]
    resist_html = ("<div style='font-size:12px;color:#b9ab90;margin-top:4px'>たいせい："
                   + "・".join(story_data.STATUS_EFFECTS[r]["name"] for r in resist) + "</div>") if resist else ""
    pic = (f"<div style='position:relative'>"
           f"<img src='{story_assets.ally_thumb(lv)}' style='width:100%;border-radius:12px;display:block'>{overlay_html}</div>")
    left = pic + f"<div style='margin-top:2px'>{icons}</div>"
    right = (f"<div style='font-weight:700;font-size:17px'>{ally['name']}"
             f"<span style='margin-left:8px;color:#8fe0ff'>Lv.{level}</span></div>"
             f"<div style='font-size:14px;margin-top:4px;line-height:1.6'>{''.join(f'<div>{x}</div>' for x in stats)}</div>{resist_html}{exp}{skill_html}{''.join(gauges)}")
    if split:      # ホーム用：画像・装備品の行・アクセサリの行を別々に（それぞれ押せるようにする）
        return pic, icon_row(gear, story_data.MAX_GEAR_SLOTS), icon_row(acc, story_data.MAX_ACCESSORY_SLOTS), right
    return left, right


def ally_detail_html(lv):
    """キャラの詳しい説明（大きい画像・Lv.1 と Lv.10 のステータス・説明・必殺技・アビリティ・仲間になる方法）"""
    esc = story_guide.esc
    ally = L.get_ally(lv)
    have = lv in L.owned_allies(profile)
    low, high = L.base_stats(lv, 1), L.base_stats(lv, story_data.LEVEL_MAX)
    gray = "" if have else "filter:grayscale(1) brightness(.6);"
    rows = "".join(
        f"<tr><th>{STAT_NAMES[k]}</th><td>{low[k]:g}</td><td>{high[k]:g}</td></tr>" for k in ("hp", "atk", "def"))
    skill = ally["skill"]
    abilities = "".join(
        f"<li>{esc(L.ability_label(a))}</li>" for a in ally["abilities"])
    mark = (f"<span style='color:#7fd8a0'>✅ 仲間（いま Lv.{L.ally_level(profile, lv)}）</span>" if have
            else "<span style='color:#b9ab90'>🔒 まだ仲間ではない</span>")
    return f"""
<div class="sd-wrap">
  <div class="sd-pic"><img src="{story_assets.ally_thumb(lv, size=720)}" style="{gray}" alt=""></div>
  <div class="sd-name">{esc(ally['name'])}</div>
  <div class="sd-mark">{mark}</div>
  <p class="sd-text">{esc(story_guide.ALLY_TEXT.get(lv, ''))}</p>
  <table class="sd-stats"><tr><th></th><th>はじめ（Lv.1）</th><th>最大（Lv.{story_data.LEVEL_MAX}）</th></tr>{rows}</table>
  <div class="sd-sec">✨ 必殺技：{esc(skill['name'])}<small>（コンボ{skill['charge']}でチャージ）</small></div>
  <p class="sd-text">{esc(skill['text'])}</p>
  <div class="sd-sec">🔓 アビリティ<small>（遊ぶほど順に解放）</small></div>
  <ol class="sd-list">{abilities}</ol>
  <div class="sd-sec">🤝 仲間になるには</div>
  <p class="sd-text">{esc(story_guide.join_text(ally))}</p>
</div>"""


DETAIL_CSS = """<style>
.sd-wrap { max-width: 560px; margin: 0 auto; }
.sd-pic { text-align: center; background: radial-gradient(ellipse at 50% 40%, rgba(233,214,166,.18), transparent 70%); border-radius: 16px; }
.sd-pic img { width: 100%; max-width: 420px; border-radius: 14px; display: inline-block; box-shadow: 0 8px 30px rgba(0,0,0,.45); }
.sd-name { font-weight: 800; font-size: 22px; text-align: center; margin-top: 10px; }
.sd-mark { text-align: center; font-size: 14px; margin-top: 2px; }
.sd-text { font-size: 15px; line-height: 1.7; margin: 6px 0; }
.sd-stats { width: 100%; border-collapse: collapse; margin: 10px 0 4px; font-size: 15px; }
.sd-stats th, .sd-stats td { border-bottom: 1px solid rgba(128,128,128,.3); padding: 6px 8px; text-align: center; }
.sd-stats th:first-child { text-align: left; }
.sd-sec { font-weight: 700; font-size: 16px; margin-top: 14px; }
.sd-sec small { font-weight: 400; font-size: 12px; opacity: .75; margin-left: 4px; }
.sd-list { margin: 4px 0 0 1.2em; padding: 0; font-size: 15px; line-height: 1.7; }
</style>"""


def view_ally_detail():
    """キャラ一覧で画像を押したときの、くわしい説明（画面のいちばん上から出す）"""
    lv = st.session_state.get("story_detail") or 1
    have = lv in L.owned_allies(profile)
    in_run = bool(profile["run"])

    def back():
        st.session_state.story_detail = None
        go(st.session_state.get("story_detail_back") or "ally_picker")

    with st.container(key="story_detail_btns"):              # ボタンは上（説明は下の箱の中でスクロール）
        col_back, col_pick = st.columns(2)
        if col_back.button("◀ 一覧にもどる", key="_story_detail_back", width="stretch"):
            back()
        if have and not in_run and col_pick.button("このキャラにする", key="_story_detail_pick", type="primary", width="stretch"):
            choose_ally(lv)
            st.session_state.story_detail = None
            go("home")
    with box(BOX_H, key="story_ally_detail", offset=70):
        st.markdown(DETAIL_CSS + ally_detail_html(lv), unsafe_allow_html=True)


def view_ally_picker():
    """キャラクター一覧（画面の上の真ん中に出す。まだ仲間でないキャラはグレー）。画像を押すと、くわしい説明の画面"""
    if profile["run"]:
        go("home")                                # 挑戦中はキャラを変えられない
    compact_title("🔄 キャラクター変更", "画像を押すと、くわしく見られるよ")
    owned = L.owned_allies(profile)
    # スマホでも1行5体のまま並べる（Streamlit は狭い画面で列を縦に積むので、この箱の中だけ止める）
    # 画像の上に透明なボタンを重ねて、画像を押すと説明が開くようにする
    st.html("""<style>
.st-key-story_picker [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 6px !important; }
.st-key-story_picker [data-testid="stColumn"], .st-key-story_picker [data-testid="column"] {
  min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }
.st-key-story_picker button { padding: 2px 4px !important; min-height: 32px !important; font-size: 12px !important; }
.st-key-story_picker [class*="st-key-story_card_"] { position: relative !important; gap: 0 !important; }
.st-key-story_picker [class*="st-key-_story_detail_"] { position: absolute !important; inset: 0 !important; z-index: 2; margin: 0 !important; }
.st-key-story_picker [class*="st-key-_story_detail_"] > div, .st-key-story_picker [class*="st-key-_story_detail_"] .stButton {
  width: 100% !important; height: 100% !important; }
.st-key-story_picker [class*="st-key-_story_detail_"] button {
  width: 100% !important; height: 100% !important; min-height: 0 !important; opacity: 0 !important; cursor: zoom-in !important; }
</style>""")
    with box(BOX_H, key="story_picker", offset=110):
        for row in range(0, len(story_data.ALLIES), 5):
            cols = st.columns(5)
            for col, ally in zip(cols, story_data.ALLIES[row:row + 5]):
                lv = ally["lv"]
                have = lv in owned
                style = "" if have else "filter:grayscale(1) brightness(.45)"
                name = short_name(lv) if have else "？？？"
                with col.container(key=f"story_card_{lv}"):
                    st.markdown(f"<img src='{story_assets.ally_thumb(lv)}' style='width:100%;border-radius:8px;display:block;{style}'>",
                                unsafe_allow_html=True)
                    if st.button("くわしく", key=f"_story_detail_{lv}"):
                        st.session_state.story_detail = lv
                        st.session_state.story_detail_back = "ally_picker"
                        go("ally_detail")
                col.markdown(f"<div style='text-align:center;font-size:11px;line-height:1.3;white-space:nowrap;overflow:hidden;"
                             f"text-overflow:ellipsis'>{name}<br>"
                             f"{'Lv.' + str(L.ally_level(profile, lv)) if have else '&nbsp;'}</div>", unsafe_allow_html=True)
                if have and col.button("えらぶ", key=f"_story_pick_{lv}", width="stretch",
                                       type="primary" if lv == st.session_state.story_ally else "secondary"):
                    choose_ally(lv)
                    go("home")
    if st.button("◀ もどる", key="_story_pick_close", width="stretch"):
        go("home")


# ---------------------------------------------------------------------------
# ホーム
# ---------------------------------------------------------------------------
HOME_CSS = """<style>
/* ストーリーモードではサイドバーを出さず、上の余白をつめる */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"] { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }
/* 中身のない部品（CSS だけ・スクリプトだけ・高さ0の部品）が、ページの上に余白を作らないようにする（動きはそのまま） */
[data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style:only-child),
[data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > div > style:only-child),
[data-testid="stElementContainer"]:has(> [data-testid="stHtml"]:empty),
[data-testid="stElementContainer"]:has(iframe[height="0"]) {
  position: absolute !important; width: 0 !important; height: 0 !important; overflow: hidden !important; margin: 0 !important; padding: 0 !important; }
[data-testid="stMainBlockContainer"], .block-container { padding-top: .5rem !important; padding-bottom: .5rem !important; }
/* 横並びのまま（スマホでも縦に積まない） */
.st-key-story_head [data-testid="stHorizontalBlock"], .st-key-story_menu [data-testid="stHorizontalBlock"],
.st-key-story_panel [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 8px !important; align-items: center; }
.st-key-story_panel [data-testid="stHorizontalBlock"] { align-items: flex-start; }
.st-key-story_head [data-testid="stColumn"], .st-key-story_menu [data-testid="stColumn"], .st-key-story_panel [data-testid="stColumn"] {
  min-width: 0 !important; }
.st-key-story_head h3 { margin: 0 !important; padding: 0 !important; font-size: 1.35rem !important; white-space: nowrap; }
.st-key-story_head button { min-height: 32px !important; }
.st-key-story_head button, .st-key-story_menu button { padding: 4px 6px !important; min-height: 38px !important; font-size: 13px !important;
  white-space: nowrap !important; }
.st-key-story_menu button p, .st-key-story_head button p { white-space: nowrap !important; overflow: hidden; text-overflow: clip; }
/* スマホでは10%だと字が入らないので、いちばん小さい幅を決めておく */
.st-key-story_menu [data-testid="stColumn"]:nth-child(1) { min-width: 92px !important; }
.st-key-story_menu [data-testid="stColumn"]:nth-child(2) { min-width: 72px !important; }
.st-key-story_menu [data-testid="stColumn"]:nth-child(3), .st-key-story_menu [data-testid="stColumn"]:nth-child(4) { min-width: 52px !important; }
/* 画像（と装備のアイコン）の下：「装備」は少し離し、「装備」「アクセサリ」「アイテム」のあいだはつめる */
.st-key-story_panel .st-key-_story_inv_equip { margin-top: 8px !important; }
.st-key-story_panel .st-key-_story_inv_acc, .st-key-story_panel .st-key-_story_inv_item, .st-key-story_panel .st-key-_story_inv_spells { margin-top: 2px !important; }
/* 「キャラクター変更」はアビリティから少し離す */
.st-key-story_panel .st-key-_story_change { margin-top: 12px !important; }
.st-key-story_panel .st-key-_story_inv_equip button, .st-key-story_panel .st-key-_story_inv_acc button, .st-key-story_panel .st-key-_story_inv_item button,
.st-key-story_panel .st-key-_story_inv_spells button {
  white-space: nowrap !important; font-size: 12px !important; padding: 2px 2px !important; min-height: 34px !important; }
.st-key-story_panel .st-key-_story_inv_equip p, .st-key-story_panel .st-key-_story_inv_acc p, .st-key-story_panel .st-key-_story_inv_item p,
.st-key-story_panel .st-key-_story_inv_spells p { white-space: nowrap !important; font-size: 12px !important; }
.st-ctitle { margin: 0 0 6px; line-height: 1.35; }
.st-ctitle b { font-size: 1.3rem; display: block; }
.st-ctitle span { font-size: .9rem; opacity: .8; }
/* ステージ間：左に次の敵、右にボタン（スマホでも横並び） */
.st-key-story_next [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 10px !important; align-items: flex-start; }
.st-key-story_next [data-testid="stColumn"] { min-width: 0 !important; }
.st-key-story_next img { max-height: 210px; object-fit: contain; }
.st-key-story_next button { min-height: 44px !important; }
.st-key-story_picker, .st-key-story_ally_detail, .st-key-story_detail_btns { max-width: 640px; margin: 0 auto; width: 100%; }
.st-key-story_detail_btns [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 8px !important; }
/* スマホでは列が1つずつ100%幅になり、横に並べると右にはみ出すので、等分にする */
.st-key-story_detail_btns [data-testid="stHorizontalBlock"] > div,
.st-key-story_picker [data-testid="stHorizontalBlock"] > div { min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }
.st-key-story_detail_btns button { min-height: 40px !important; padding: 4px 6px !important; }
.st-key-story_panel button { padding: 4px 4px !important; min-height: 36px !important; font-size: 12px !important; }
/* ホーム：キャラの画像・装備品の行・アクセサリの行を押せるように（透明なボタンを重ねる） */
.st-key-story_tap_pic, .st-key-story_tap_gear, .st-key-story_tap_acc { position: relative !important; gap: 0 !important; cursor: pointer; }
.st-key-story_panel [data-testid="stColumn"]:first-child [data-testid="stVerticalBlock"] { gap: 4px !important; }
/* Streamlit の文字のかたまりは下に -1rem の余白があり、すき間をつめると上の部品と重なるので 0 にする */
.st-key-story_tap_pic [data-testid="stMarkdown"], .st-key-story_tap_gear [data-testid="stMarkdown"], .st-key-story_tap_acc [data-testid="stMarkdown"],
.st-key-story_tap_pic [data-testid="stMarkdownContainer"], .st-key-story_tap_gear [data-testid="stMarkdownContainer"],
.st-key-story_tap_acc [data-testid="stMarkdownContainer"] { margin: 0 !important; }
.st-key-story_tap_pic [data-testid="stElementContainer"], .st-key-story_tap_gear [data-testid="stElementContainer"],
.st-key-story_tap_acc [data-testid="stElementContainer"] { margin: 0 !important; }
[class*="st-key-_story_tap_"] { position: absolute !important; inset: 0 !important; z-index: 3; margin: 0 !important; }
[class*="st-key-_story_tap_"] > div, [class*="st-key-_story_tap_"] .stButton, [class*="st-key-_story_tap_"] button {
  width: 100% !important; height: 100% !important; min-height: 0 !important; }
[class*="st-key-_story_tap_"] button { opacity: 0 !important; padding: 0 !important; cursor: pointer !important; }
.st-key-story_tap_pic:hover img, .st-key-story_tap_gear:hover, .st-key-story_tap_acc:hover { filter: brightness(1.12); }
/* 準備画面：装備・アクセサリ・アイテムのボタン */
.st-key-story_ready { max-width: 560px; margin: 0 auto; width: 100%; }
.st-key-story_ready button { min-height: 48px !important; font-size: 15px !important; }
.st-key-story_quests button { min-height: 52px !important; font-size: 15px !important; }
</style>"""
st.html(HOME_CSS)          # <style> だけの st.html は場所をとらない（上に余白ができない）


BOX_H = 430          # 中身が多いところは、この高さの箱の中だけでスクロールする（ページ全体は動かさない）


def compact_title(title, sub=""):
    """大きな見出し（hero）の代わりの、小さな1〜2行の見出し"""
    st.markdown(f"<div class='st-ctitle'><b>{title}</b>" + (f"<span>{sub}</span>" if sub else "") + "</div>",
                unsafe_allow_html=True)


def box(height=BOX_H, key=None, offset=None):
    """中だけスクロールする箱。offset を渡すと、画面の高さ − offset(px) にそろえる（画面からはみ出さない）"""
    if offset is not None:
        key = key or f"sbox_{offset}"
        st.html(f"<style>.st-key-{key} {{ height: max(220px, calc(100dvh - {offset}px)) !important; }}</style>")
    return st.container(height=height, border=True, key=key)


def story_header(title="⚔️ ストーリーモード", back=None):
    """いちばん上の1行：見出しと、右に「トップへ」（back を渡すと、そのボタンに変える）"""
    with st.container(key="story_head"):
        col_title, col_btn = st.columns([7, 3], vertical_alignment="center")
        col_title.markdown(f"### {title}")
        if back is None:
            if col_btn.button("🏠 トップへ", key="_story_top", width="stretch"):
                if "home" in common.PAGES:
                    st.switch_page(common.PAGES["home"])
        else:
            label, view = back
            if col_btn.button(label, key="_story_head_back", width="stretch"):
                go(view)


def view_home():
    story_header()
    # 上のメニュー：クエスト（画面の約20%）・称号・攻略（約10%ずつ）を横に並べる
    with st.container(key="story_menu"):
        col_quest, col_shop, col_title, col_guide, _ = st.columns([2, 1.3, 1, 1, 4.7])
        if col_quest.button("クエスト", key="_story_quest", type="primary", width="stretch"):
            st.session_state.story_confirm_new = False
            go("quest")
        if col_shop.button("ショップ", key="_story_shop", width="stretch"):
            st.session_state.story_shop_back = "home"
            go("shop")
        if col_title.button("称号", key="_story_titles", width="stretch"):
            go("titles")
        if col_guide.button("攻略", key="_story_guide", width="stretch"):
            go("guide")
    st.markdown(f"<div style='text-align:right;font-size:14px;margin:-4px 0 2px'>{story_data.MONEY_ICON} "
                f"<b>{profile.get('money', 0):,}</b> {story_data.MONEY_NAME}</div>", unsafe_allow_html=True)
    show_notice()

    run = profile["run"]
    owned = L.owned_allies(profile)
    if run:
        st.session_state.story_ally = run["ally"]
    elif st.session_state.story_ally not in owned:
        st.session_state.story_ally = 1
    lv = st.session_state.story_ally

    with st.container(border=True, key="story_panel"):
        pic, gear_row, acc_row, right = ally_panel_parts(lv, split=True)
        col_pic, col_info = st.columns([3, 7])
        with col_pic:
            # 画像・装備品の行・アクセサリの行の上に、透明なボタンを重ねる（押すと、くわしい説明・装備・アクセサリの画面）
            with st.container(key="story_tap_pic"):
                st.markdown(pic, unsafe_allow_html=True)
                if st.button("くわしく", key="_story_tap_pic"):
                    st.session_state.story_detail = lv
                    st.session_state.story_detail_back = "home"
                    go("ally_detail")
            with st.container(key="story_tap_gear"):
                st.markdown(gear_row, unsafe_allow_html=True)
                if st.button("装備", key="_story_tap_gear"):
                    open_inventory("equip", "home")
            with st.container(key="story_tap_acc"):
                st.markdown(acc_row, unsafe_allow_html=True)
                if st.button("アクセサリ", key="_story_tap_acc"):
                    open_inventory("acc", "home")
        with col_pic:                                # 画像の下：装備・アクセサリ・アイテム（縦に並べる）
            loadout_buttons("home", "_story_inv")
        col_info.markdown(right, unsafe_allow_html=True)
        if run:
            st.caption(f"📌 挑戦中：{L.get_difficulty(run['difficulty'])['name']} {stage_label(run)}"
                       "（「クエスト」から続きを遊べるよ。挑戦中はキャラを変えられないよ）")
            if not st.session_state.story_confirm_new:
                if st.button("⏹ クエストを中断", key="_story_home_abandon", width="stretch"):
                    st.session_state.story_confirm_new = True
                    st.rerun()
        elif st.button("🔄 キャラクター変更", key="_story_change", width="stretch"):
            go("ally_picker")
    if run and st.session_state.story_confirm_new:
        confirm_abandon(run, "今の挑戦を中断して終わらせますか？（負け扱い。ここまでのアビリティはもらえて、アイテムはすべて倉庫に戻ります）")


def show_notice():
    notice = st.session_state.pop("story_notice", None)
    if notice:
        st.info(notice)


INV_BUTTONS = (("equip", "🛡️ 装備"), ("acc", "💍 アクセサリ"), ("item", "🎒 アイテム"), ("spells", "🔮 魔法"))


def open_inventory(mode, back):
    """装備・アクセサリ・アイテムの画面を開く（閉じたら back の画面にもどる）"""
    st.session_state.story_inv_mode = mode
    st.session_state.story_inv_back = back
    st.session_state.story_round += 1
    go("inventory")


def loadout_buttons(back, prefix, counts=False):
    """装備・アクセサリ・アイテムの3つのボタン（ホームの画像の下と、出発前の準備画面で使う）"""
    lv = profile["run"]["ally"] if profile["run"] else st.session_state.story_ally
    gear, acc = L.split_equipped(profile, lv)
    bag = L.bag_total(profile["run"]["bag"]) if profile["run"] else sum(L.pack_counts(profile).values())
    nums = {"equip": f"{len(gear)} / {story_data.MAX_GEAR_SLOTS}", "acc": f"{len(acc)} / {story_data.MAX_ACCESSORY_SLOTS}",
            "item": f"{bag} / {story_data.MAX_CARRY_ITEMS}"}
    nums["spells"] = f"{len(L.known_spells(profile, lv))}"
    for mode, label in INV_BUTTONS:
        if st.button(label + (f"（{nums[mode]}）" if counts else ""), key=f"{prefix}_{mode}", width="stretch"):
            if mode == "spells":
                st.session_state.story_spells_back = back
                go("spells")
            open_inventory(mode, back)


def view_quest():
    """クエスト：挑戦中なら「続きから」、そうでなければクエスト（難易度）の一覧。えらぶと準備画面へ"""
    story_header("🗺️ クエスト", ("◀ もどる", "home"))
    show_notice()
    run = profile["run"]
    if run:
        view_continue(run)
    else:
        view_quest_list()


def view_quest_list():
    owned = L.owned_allies(profile)
    if st.session_state.story_ally not in owned:
        st.session_state.story_ally = 1
    compact_title("クエスト一覧", "遊ぶクエストをえらんでね")
    with st.container(key="story_quests"):
        for diff in story_data.DIFFICULTIES:
            label = f"{diff['name']}（{L.stage_count(diff['id'])}ステージ）"
            if diff["id"] in profile["cleared_modes"]:
                label += "　🏆クリア"
            if st.button(label, key=f"_story_diff_{diff['id']}", width="stretch"):
                st.session_state.story_difficulty = diff["id"]
                go("ready")
    st.caption("負けても、そのステージの最初から何度でもやり直せるよ。進み具合は自動で保存されるよ。")


def view_ready():
    """出発前の準備：装備・アクセサリ・アイテムを整えて「出発」"""
    if profile["run"]:
        go("quest")
    story_header("🧭 出発の準備", ("◀ もどる", "quest"))
    show_notice()
    lv = st.session_state.story_ally
    diff = L.get_difficulty(st.session_state.story_difficulty)
    with st.container(key="story_ready"):
        compact_title(f"{diff['name']}（{L.stage_count(diff['id'])}ステージ）",
                      f"{L.get_ally(lv)['name']}（Lv.{L.ally_level(profile, lv)}）で挑戦するよ")
        loadout_buttons("ready", "_story_ready", counts=True)
        st.write("")
        if st.button("⚔️ 出発", key="_story_go", type="primary", width="stretch"):
            L.start_run(profile, lv, diff["id"])
            new_rewards(None)
            go_battle()
        st.caption("キャラはホームの「キャラクター変更」で変えられるよ。")


def view_continue(run):
    """進行中の挑戦があるとき：「続きから」と「新規にプレイ」。キャラは変えられない（装備とリュックは変えられる）"""
    st.session_state.story_ally = run["ally"]
    max_hp = L.ally_stats(run["ally"], profile)["hp"]
    with st.container(border=True):
        st.markdown(
            f"#### 📌 続きから：{L.get_difficulty(run['difficulty'])['name']} {stage_label(run)} ／ "
            f"{short_name(run['ally'])} HP {L.display_hp(run['hp'])}/{max_hp:g}"
        )
        hp_bar(run["hp"], max_hp)
        st.caption(f"クリアしたステージ：{run['cleared']} / {L.stage_count(run['difficulty'])}　"
                   f"リュック：{L.bag_total(run['bag'])} / {story_data.MAX_CARRY_ITEMS}こ　"
                   "（挑戦中はキャラを変えられないよ）")
        with st.container(key="story_ready"):
            loadout_buttons("quest", "_story_cont", counts=True)
        if st.button("▶️ 続きから", type="primary", width="stretch"):
            st.session_state.story_confirm_new = False
            go_battle()

    if not st.session_state.story_confirm_new:
        if st.button("🆕 新規にプレイ", width="stretch"):
            st.session_state.story_confirm_new = True
            st.rerun()
        return
    confirm_abandon(run, "今の挑戦を終わらせて新しく始めますか？（負け扱い。アイテムはすべてホームに戻ります）")


def confirm_abandon(run, text):
    """挑戦を終わらせる確認（クエスト画面の「新規にプレイ」と、ホームの「クエストを中断」で使う）"""
    with st.container(border=True):
        st.warning(text)
        col_no, col_yes = st.columns(2)
        if col_no.button("やめておく", key="_story_abandon_no", width="stretch"):
            st.session_state.story_confirm_new = False
            st.rerun()
        if col_yes.button("終わらせる", key="_story_abandon_yes", type="primary", width="stretch"):
            st.session_state.story_confirm_new = False
            run_id = run["id"]
            summary = L.abandon_run(profile)
            save()
            log_run(summary, run_id)
            st.session_state.story_summary = summary
            new_rewards(None)
            go("end")


# ---------------------------------------------------------------------------
# 倉庫とリュック・攻略
# ---------------------------------------------------------------------------
def view_inventory():
    lv = profile["run"]["ally"] if profile["run"] else st.session_state.story_ally
    round_id = st.session_state.story_round
    st.markdown(story_battle.fullscreen_css(), unsafe_allow_html=True)    # 画面いっぱいに広げる
    notice = st.session_state.get("story_inventory_notice")
    result = story_inventory.inventory(profile, lv, round_id, key=f"story_inventory_{round_id}", notice=notice,
                                       mode=st.session_state.get("story_inv_mode", "equip"))
    if not result or result.get("round") != round_id:
        return
    st.session_state.story_inventory_notice = None
    if result.get("action") in ("save", "use"):
        try:
            L.apply_inventory(profile, lv, result)
            message = L.use_home_item(profile, lv, result["use"]) if result.get("action") == "use" else None
        except ValueError as e:
            st.session_state.story_inventory_notice = f"できなかったよ：{e}"
            st.session_state.story_round += 1
            go("inventory")
        save()
        if message:                               # 使ったあとは、倉庫とリュックの画面にもどる
            st.session_state.story_inventory_notice = message
            st.session_state.story_round += 1
            go("inventory")
        st.session_state.story_notice = "保存したよ。"
    go(st.session_state.get("story_inv_back") or "home")


TITLE_CSS = """<style>
.tt-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin: 6px 0 18px; }
.tt-card { text-align: center; padding: 10px 8px 12px; border-radius: 14px; border: 1px solid rgba(128,128,128,.28);
  background: linear-gradient(180deg, rgba(120,90,200,.10), rgba(0,0,0,0)); }
.tt-card.on { border-color: rgba(233,200,110,.75); box-shadow: 0 0 16px rgba(233,200,110,.25); }
.tt-card img { width: 100%; max-width: 140px; aspect-ratio: 1; object-fit: contain; display: block; margin: 0 auto 6px; }
.tt-card.off img { filter: grayscale(1) brightness(.35); }
.tt-name { font-weight: 800; font-size: 15px; }
.tt-card.off .tt-name { opacity: .55; }
.tt-how { font-size: 12px; opacity: .75; margin-top: 3px; line-height: 1.4; }
.tt-mark { font-size: 12px; margin-top: 4px; }
.tt-card.on .tt-mark { color: #e9c86e; font-weight: 700; }
@media (max-width: 520px) { .tt-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; } }
</style>"""


def title_cards(items):
    cards = []
    for t in items:
        cls = "on" if t["earned"] else "off"
        mark = "🏅 獲得！" if t["earned"] else "🔒 まだ"
        cards.append(f"<div class='tt-card {cls}'><img src='{story_assets.title_thumb(t['badge'])}' alt=''>"
                     f"<div class='tt-name'>{story_guide.esc(t['name'])}</div>"
                     f"<div class='tt-how'>{story_guide.esc(t['how'])}</div><div class='tt-mark'>{mark}</div></div>")
    return "<div class='tt-grid'>" + "".join(cards) + "</div>"


def view_titles():
    items = L.titles(profile)
    got = sum(t["earned"] for t in items)
    compact_title("🏅 称号", f"手に入れた称号：{got} / {len(items)}")
    if st.button("🏠 ホームにもどる", key="_story_titles_back_top"):
        go("home")
    with box(BOX_H, key="sbox_titles", offset=150):
        st.markdown("**モード全クリ・エクストラ**")
        st.markdown(TITLE_CSS + title_cards([t for t in items if t["kind"] != "ally"]), unsafe_allow_html=True)
        st.markdown(f"**キャラ Lv.{story_data.LEVEL_MAX}**")
        st.markdown(title_cards([t for t in items if t["kind"] == "ally"]), unsafe_allow_html=True)


def show_new_titles(new_titles):
    """挑戦の終わりに、新しく手に入れた称号を知らせる"""
    if not new_titles:
        return
    st.markdown("**🏅 新しい称号**")
    st.markdown(TITLE_CSS + title_cards(new_titles), unsafe_allow_html=True)


def view_guide():
    compact_title("📖 攻略", "味方・装備・敵のことと、攻略のコツ")
    if st.button("🏠 ホームにもどる", key="_story_guide_back_top"):
        go("home")
    story_guide.render(profile, lambda i: box(BOX_H, key=f"sbox_guide{i}", offset=195))   # タブは箱の上


# ---------------------------------------------------------------------------
# 戦闘（画面いっぱい）
# ---------------------------------------------------------------------------
def view_battle():
    run = profile["run"]
    round_id = st.session_state.story_round
    stage_no = L.EXTRA if run.get("extra") else run["stage"]
    st.markdown(story_battle.fullscreen_css(), unsafe_allow_html=True)
    config = L.battle_config(round_id, stage_no, run["difficulty"], run["ally"], run["hp"], profile, run["bag"],
                             charge=run.get("charge", 0), ally_mp=L.run_mp(profile))
    result = story_battle.battle(config, key=f"story_battle_{round_id}")
    if not result or result.get("round") != round_id:
        return
    outcome = result["result"]
    L.note_battle(profile, result)            # はじめての救援を受けたかなど（勝ち負けに関係なく）
    if outcome == "win":
        L.apply_battle(profile, result)
        rewards = L.clear_stage(profile)
        save()
        new_rewards(rewards)
        if rewards["finished"]:
            log_run(rewards["finished"], run["id"])
            st.session_state.story_summary = rewards["finished"]
            go("end")
        go("between")
    elif outcome == "escape":                 # エクストラの「にげる」：HPはそのまま、使ったアイテムは減る
        L.apply_battle(profile, result)
        L.skip_extra(profile)
        L.begin_stage(profile)
        save()
        new_rewards(None)
        st.session_state.story_notice = "宇宙龍から にげた！ 次のステージへ進もう。"
        go("between")
    elif outcome == "lose":
        L.restore_checkpoint(profile, result.get("used"))   # 使ったアイテムは戻らない
        save()
        go("extra_lost" if run.get("extra") else "retry")
    else:                                      # やめる：ホームへ。次はこのステージの最初から
        L.restore_checkpoint(profile, result.get("used"))   # 使ったアイテムは戻らない
        save()
        st.session_state.story_notice = f"{stage_label(run)} の最初から 続けられるよ。（戦闘で使ったアイテムは もどらないよ）"
        go("home")


# ---------------------------------------------------------------------------
# 負けたとき
# ---------------------------------------------------------------------------
def view_retry():
    run = profile["run"]
    enemy = L.run_enemy(run)
    compact_title("💀 やられてしまった…", f"{stage_label(run)}　Lv.{enemy['lv']} {enemy['name']}")
    st.markdown("負けても大丈夫。このステージを始めたときの HP とかばんに もどして、もう一度 挑戦できるよ。")
    hp_bar(run["hp"], L.ally_stats(run["ally"], profile)["hp"])
    counts = L.bag_counts(run["bag"])
    st.markdown("リュック：" + ("".join(item_icon(k, n) for k, n in counts.items()) or "からっぽ"), unsafe_allow_html=True)
    col_retry, col_home = st.columns(2)
    if col_retry.button("⚔️ もう一度たたかう", type="primary", width="stretch"):
        go_battle()
    if col_home.button("🏠 ホームへ", width="stretch"):
        go("home")


def view_extra_lost():
    """エクストラ（宇宙龍）に負けたとき：もう一度戦うか、先へ進むか（どちらも負けにはならない）"""
    run = profile["run"]
    enemy = story_data.EXTRA_ENEMY
    compact_title("🐉 宇宙龍に やられてしまった…", f"Lv.{enemy['lv']} {enemy['name']} ― {enemy['title']}")
    with st.container(key="story_next"):
        col_img, col_text = st.columns([2, 3])
        col_img.image(str(story_assets.enemy_image_path(enemy)), width="stretch")
        col_text.markdown("負けにはならないよ。HP は、宇宙龍と戦い始めたときに もどったよ。")
        with col_text:
            hp_bar(run["hp"], L.ally_stats(run["ally"], profile)["hp"])
    col_retry, col_skip = st.columns(2)
    if col_retry.button("🔥 もう一度戦う", type="primary", width="stretch"):
        go_battle()
    if col_skip.button("➡️ 先へ進む", width="stretch"):
        L.skip_extra(profile)
        L.begin_stage(profile)
        save()
        new_rewards(None)
        st.session_state.story_notice = "宇宙龍は 去っていった…（この挑戦では もう現れない）"
        go("between")


# ---------------------------------------------------------------------------
# ステージ間の画面
# ---------------------------------------------------------------------------
def view_between():
    """ステージの間：左上に次の敵、右に「すすむ」。もらった物とかばんは、下の箱の中でスクロール"""
    run = profile["run"]
    rewards = st.session_state.story_rewards
    max_hp = L.ally_stats(run["ally"], profile)["hp"]
    max_mp = L.ally_stats(run["ally"], profile)["mp"]
    notice = st.session_state.pop("story_notice", None)
    if rewards and rewards.get("extra"):
        compact_title("🌟 EXTRA STAGE クリア！", f"{story_data.EXTRA_ENEMY['name']} を たおした！")
    elif rewards:
        enemy = L.enemy_by_key(rewards["enemy"])
        compact_title(f"🎉 ステージ{rewards['stage']} クリア！", f"Lv.{enemy['lv']} {enemy['name']} を たおした！")
    else:
        compact_title(f"📌 {stage_label(run)} へ", f"{short_name(run['ally'])} ／ {L.get_difficulty(run['difficulty'])['name']}")
    if notice:
        st.info(notice)
    if rewards and not show_recruits(rewards):
        return                                # 仲間入りのカードを見せ終わるまで、先へは進めない

    # 上：左に次の敵、右に「すすむ」
    with st.container(key="story_next"):
        col_img, col_text = st.columns([2, 3])
        if run.get("extra"):
            col_img.markdown(f"<img src='{story_assets.silhouette_uri(L.enemy_key(story_data.EXTRA_ENEMY))}' "
                             "style='width:100%;border-radius:10px;filter:drop-shadow(0 0 12px #b48cff)'>", unsafe_allow_html=True)
            with col_text:
                st.markdown("**⚠️ EXTRA STAGE**　ただならぬ気配……**？？？** が 行く手をはばんでいる！")
                st.caption("戦わずに「にげる」こともできるよ（負けにはならない）。")
                hp_bar(run["hp"], max_hp)
                mp_bar(L.run_mp(profile), max_mp)
                if st.button("⚔️ 立ち向かう", type="primary", width="stretch"):
                    go_battle()
        else:
            enemy = L.run_enemy(run)
            final = run["stage"] == L.stage_count(run["difficulty"])
            label = "FINAL STAGE" if final else f"ステージ{run['stage']}"
            col_img.image(str(story_assets.enemy_image_path(enemy)), width="stretch")
            with col_text:
                st.markdown(f"**次の敵**：{label}<br>Lv.{enemy['lv']} {enemy['name']}", unsafe_allow_html=True)
                if enemy["gimmicks"]:
                    st.caption("とくちょう：" + "・".join(
                        f"{story_data.STATUS_EFFECTS[g]['icon']}{story_data.STATUS_EFFECTS[g]['name']}" for g in enemy["gimmicks"]))
                if enemy.get("weak"):
                    w = story_data.ELEMENTS[enemy["weak"]]
                    st.caption(f"弱点：{w['icon']}{w['name']}の魔法")
                hp_bar(run["hp"], max_hp)
                mp_bar(L.run_mp(profile), max_mp)
                if st.button(f"⚔️ {label} へ すすむ", type="primary", width="stretch"):
                    go_battle()
        with col_text:
            if st.button("🏠 ホームへ（続きから遊べるよ）", width="stretch"):
                go("home")

    # 下：もらった物・かばん（箱の中だけスクロール）
    with box(BOX_H - 140, key="sbox_between", offset=340):
        if rewards:
            healed = []
            if rewards["healed"] > 0:
                healed.append(f"HPが {L.display_hp(rewards['healed'])}")
            if rewards.get("mp_healed", 0) >= 1:
                healed.append(f"MPが {int(rewards['mp_healed'])}")
            if healed:
                st.caption(f"休けいして {'、'.join(healed)} 回復したよ。")
            show_rewards(rewards)
        st.markdown("**🎒 かばん**")
        counts = L.bag_counts(run["bag"])
        if not counts:
            st.caption("かばんは からっぽ。")
        for item in story_data.ITEMS:
            n = counts.get(item["id"], 0)
            if not n:
                continue
            col_name, col_use = st.columns([5, 3])
            col_name.markdown(f"{item_icon(item['id'], n, size=32)} {item['name']}", unsafe_allow_html=True)
            if (item["heal_rate"] > 0 or item.get("mp_rate")) and not item.get("assist") and not item.get("revive"):
                full = (item["heal_rate"] <= 0 or run["hp"] >= max_hp) and (not item.get("mp_rate") or L.run_mp(profile) >= max_mp)
                if col_use.button("つかう", key=f"_story_use_{item['id']}", width="stretch", disabled=full):
                    L.take_from_bag(run["bag"], item["id"])
                    run["hp"] = L.heal(run["hp"], max_hp, item)
                    if item.get("mp_rate"):
                        run["mp"] = min(max_mp, L.run_mp(profile) + max_mp * item["mp_rate"])
                    save()
                    st.rerun()
            else:
                col_use.caption("戦闘中に使えるよ")


# ---------------------------------------------------------------------------
# 挑戦の終わり（全クリア / 新規にプレイ）
# ---------------------------------------------------------------------------
def view_end():
    summary = st.session_state.story_summary
    if not summary:
        go("home")
    name = short_name(summary["ally"])
    difficulty = L.get_difficulty(summary["difficulty"])["name"]
    if summary["outcome"] == "clear":
        boss = L.stages_for(summary["difficulty"])[-1]["name"]
        compact_title("👑 全クリア！", f"{name} は {boss}を たおした！（{difficulty}）")
    else:
        compact_title("🏳️ 挑戦を 終えた", f"{name} ／ {difficulty} ／ ステージ{summary['cleared']}まで クリア")

    rewards = st.session_state.story_rewards
    if summary["outcome"] == "clear" and rewards:
        if not show_rewards(rewards):
            return
        if not rewards["allies"]:
            st.balloons()

    if st.button("🏠 ホームに もどる", type="primary", width="stretch", key="_story_end_home_top"):
        st.session_state.story_summary = None
        new_rewards(None)
        go("home")
    with box(BOX_H, key="sbox_end", offset=150):
        end_details(summary, name)


def end_details(summary, name):
    """挑戦の終わり：新しい称号・アビリティ・倉庫にもどった物（箱の中）"""
    show_new_titles(summary.get("new_titles"))

    st.markdown("**✨ アビリティ**")
    if summary["ability_after"] > summary["ability_before"]:
        st.caption(f"{name} の アビリティが たまったよ！")
    level_before = L.level_of(summary["ally"], summary["ability_before"])
    level_after = L.level_of(summary["ally"], summary["ability_after"])
    if level_after > level_before:
        st.success(f"⬆️ {name} の レベルが {level_before} → {level_after} に上がった！")
        for sp in L.level_spells(summary["ally"], level_after):
            if level_before < sp["level"] <= level_after:
                st.success(f"🔮 新しい魔法「{L.get_spell(sp['id'])['name']}」を覚えた！（{L.spell_short_text(sp['id'])}）")
    if summary["new_abilities"]:
        st.success(f"🎊 新しいアビリティを {summary['new_abilities']}つ 解放した！")
    ability_gauges(summary["ally"], summary["ability_after"])

    st.markdown("**🎒 アイテム**")
    returned = summary["returned"]
    st.markdown("倉庫にもどった物：" + ("".join(item_icon(k, n) for k, n in returned.items()) or "なし"),
                unsafe_allow_html=True)



# ---------------------------------------------------------------------------
# ショップ（倉庫のアイテムを買う・売る）
# ---------------------------------------------------------------------------
SHOP_CSS = """<style>
.shop-scene { position: relative; width: 100%; max-width: 760px; margin: 0 auto 6px; aspect-ratio: 1536 / 838; border-radius: 14px; overflow: hidden;
  box-shadow: 0 6px 20px rgba(0,0,0,.45); }
.shop-scene img { position: absolute; display: block; pointer-events: none; }
.shop-scene .bg, .shop-scene .front { inset: 0; width: 100%; height: 100%; object-fit: cover; }
.shop-scene .keeper { height: 62.5%; top: 41.9%; left: 73.8%; transform: translateX(-50%); }
.shop-scene .say { position: absolute; left: 3%; top: 5%; max-width: 52%; background: rgba(255,250,235,.94); color: #3a2a14; border-radius: 12px;
  padding: 6px 10px; font-size: clamp(11px, 2.6vw, 14px); line-height: 1.45; font-weight: 700; box-shadow: 0 3px 10px rgba(0,0,0,.4); }
.shop-money { text-align: center; font-size: 17px; margin: 2px 0 6px; }
.st-key-story_shop_list [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 6px !important; align-items: center; }
.st-key-story_shop_list [data-testid="stColumn"] { min-width: 0 !important; }
.st-key-story_shop_list button { padding: 2px 4px !important; min-height: 36px !important; font-size: 12px !important; white-space: nowrap !important; }
.st-key-story_shop_list button p { font-size: 12px !important; white-space: nowrap !important; }
.shop-row { display: flex; gap: 8px; align-items: center; font-size: 13px; line-height: 1.35; }
.shop-row img { width: 44px; height: 44px; border-radius: 8px; flex: none; object-fit: cover; }
.shop-row b { font-size: 14px; } .shop-row small { opacity: .75; display: block; }
.shop-row .p { color: #ffd36a; font-weight: 800; white-space: nowrap; }
</style>"""


def view_shop():
    back = st.session_state.get("story_shop_back") or "home"
    story_header("🏪 ショップ", ("◀ もどる", back))
    st.html(SHOP_CSS)
    line = st.session_state.setdefault("story_shop_line", __import__("random").choice(story_data.SHOP_LINES))
    bg = story_assets.thumb_uri("backgrounds/bg_shop.webp", 1100)
    keeper = story_assets.thumb_uri("shop/shopkeeper.webp", 640)
    front = story_assets.thumb_uri("shop/bg_shop_front.webp", 1100)
    if bg:
        st.markdown("<div class='shop-scene'>"
                    f"<img class='bg' src='{bg}' alt=''>" + (f"<img class='keeper' src='{keeper}' alt='店主'>" if keeper else "")
                    + (f"<img class='front' src='{front}' alt=''>" if front else "") + f"<div class='say'>{line}</div></div>",
                    unsafe_allow_html=True)
    st.markdown(f"<div class='shop-money'>{story_data.MONEY_ICON} <b>{profile.get('money', 0):,}</b> {story_data.MONEY_NAME}</div>",
                unsafe_allow_html=True)
    show_notice()
    money = profile.get("money", 0)
    tab_buy, tab_sell = st.tabs(["🛒 買う", "💰 売る"])
    with tab_buy:
        st.caption("買った物は倉庫に入るよ。魔導書や強い薬は、ボスが持っているらしい……")
        with box(BOX_H - 60, key="story_shop_list", offset=470):
            for item_id in story_data.SHOP_ITEMS:
                item, price = L.get_item(item_id), L.buy_price(item_id)
                have = profile["items"].get(item_id, 0)
                col_text, col_one, col_five = st.columns([6, 2, 2], vertical_alignment="center")
                col_text.markdown(f"<div class='shop-row'><img src='{story_assets.item_thumb(item_id)}' alt=''><div><b>{item['name']}</b> "
                                  f"<span class='p'>{price:,}</span><small>{L.item_effect_text(item)}（倉庫 {have}こ）</small></div></div>",
                                  unsafe_allow_html=True)
                for col, n in ((col_one, 1), (col_five, 5)):
                    if col.button(f"{n}こ買う", key=f"_shop_buy_{item_id}_{n}", width="stretch", disabled=money < price * n):
                        shop_action(L.buy_item, item_id, n)
    with tab_sell:
        st.caption("倉庫のアイテムを、半分の値段で買い取るよ（リュックの中の物は売れないよ）。")
        with box(BOX_H - 60, key="story_shop_sell", offset=470):
            rows = [(i, profile["items"].get(i["id"], 0)) for i in story_data.ITEMS]
            rows = [(i, n) for i, n in rows if n > 0 and L.sell_price(i["id"]) > 0]
            if not rows:
                st.caption("売れるアイテムは ないよ。")
            for item, have in rows:
                price = L.sell_price(item["id"])
                col_text, col_one, col_all = st.columns([6, 2, 2], vertical_alignment="center")
                col_text.markdown(f"<div class='shop-row'><img src='{story_assets.item_thumb(item['id'])}' alt=''><div><b>{item['name']}</b> "
                                  f"<span class='p'>{price:,}</span><small>倉庫 {have}こ</small></div></div>", unsafe_allow_html=True)
                if col_one.button("1こ売る", key=f"_shop_sell_{item['id']}_1", width="stretch"):
                    shop_action(L.sell_item, item["id"], 1)
                if col_all.button(f"全部（{have}）", key=f"_shop_sell_{item['id']}_all", width="stretch"):
                    shop_action(L.sell_item, item["id"], have)


def shop_action(fn, item_id, count):
    try:
        st.session_state.story_notice = fn(profile, item_id, count)
        save()
    except ValueError as e:
        st.session_state.story_notice = f"できなかったよ：{e}"
    st.rerun()


# ---------------------------------------------------------------------------
# 魔法（覚えている魔法と、魔導書）
# ---------------------------------------------------------------------------
def spell_line(sid, stats):
    sp, n = L.get_spell(sid), L.spell_numbers(sid, stats)
    elem = story_data.ELEMENTS[sp["element"]]
    extra = ""
    if "power" in n:
        extra = f"威力 {n['power']:.0f}"
    elif "heal" in n:
        extra = f"HP +{n['heal']:.0f}" + (f"・MP +{n['mp_heal']:.0f}" if n.get("mp_heal") else "")
    elif sp["kind"] == "brave":
        extra = f"攻撃×{1 + n['boost']:.2f}（{n['turns']}回）"
    elif sp["kind"] == "protect":
        extra = f"{n['turns']}ターン"
    elif sp["kind"] == "haste":
        extra = f"+{n['seconds']:g}秒（{n['turns']}回）"
    return (f"{elem['icon'] if sp['kind'] == 'attack' else '🔮'} <b>{sp['name']}</b>　MP {n['cost']}"
            f"<br><span style='font-size:12px;opacity:.8'>{L.spell_short_text(sid)}" + (f"　{extra}" if extra else "") + "</span>")


def view_spells():
    back = st.session_state.get("story_spells_back") or "home"
    story_header("🔮 魔法", ("◀ もどる", back))
    show_notice()
    lv = profile["run"]["ally"] if profile["run"] else st.session_state.story_ally
    stats = L.ally_stats(lv, profile)
    cut = story_data.MP_COST_CUT * L.mag_coef(stats["mag"])
    compact_title(f"{short_name(lv)}（Lv.{L.ally_level(profile, lv)}）",
                  f"MP {stats['mp']:g}　魔力 {stats['mag']:g}（消費MP −{cut:.0%}）　会心率 {stats['crit']:.0%}　詠唱の満点 {L.chant_taps(stats['mag'])}回")
    with box(BOX_H + 40, key="story_spell_box", offset=200):
        st.markdown("**レベルで覚える魔法**")
        for sp in L.level_spells(lv, L.ally_level(profile, lv)):
            if sp["learned"]:
                st.markdown(spell_line(sp["id"], stats), unsafe_allow_html=True)
            else:
                st.markdown(f"🔒 <b>？？？</b>　<span style='font-size:12px;opacity:.75'>Lv.{sp['level']} で覚える</span>",
                            unsafe_allow_html=True)
        books = L.book_spells(profile, lv)
        st.markdown(f"**魔導書で覚えた魔法（{len(books)} / {story_data.MAX_BOOK_SPELLS}）**")
        for sid in books:
            st.markdown(spell_line(sid, stats), unsafe_allow_html=True)
        for _ in range(story_data.MAX_BOOK_SPELLS - len(books)):
            st.caption("＋ 空き（下の魔導書で覚えられるよ）")
        st.markdown("**倉庫の魔導書**")
        owned = [(b, profile["items"].get(b, 0)) for b in L.book_ids() if profile["items"].get(b, 0) > 0]
        if not owned:
            st.caption("魔導書は まだ持っていないよ。ボスを倒したり、はじめて全クリアするともらえるよ。")
        known = L.known_spells(profile, lv)
        for book, n in owned:
            item = L.get_item(book)
            sid = item["spell"]
            st.markdown(f"{item_icon(book, n, size=36)} <b>{item['name']}</b> → 「{L.get_spell(sid)['name']}」"
                        f"<span style='font-size:12px;opacity:.8'>（{L.spell_short_text(sid)}）</span>", unsafe_allow_html=True)
            if sid in known:
                st.caption("もう覚えているよ。")
            elif len(books) < story_data.MAX_BOOK_SPELLS:
                if st.button(f"📖 {short_name(lv)}が覚える", key=f"_learn_{book}", width="stretch"):
                    learn_action(lv, book, None)
            else:
                cols = st.columns(len(books))
                for col, old in zip(cols, books):
                    if col.button(f"「{L.get_spell(old)['name']}」と入れかえ", key=f"_learn_{book}_{old}", width="stretch"):
                        learn_action(lv, book, old)
        st.caption("魔力が高いほど、MPが少なくてすみ、詠唱の満点も近くなるよ。魔導書の魔法は、別の魔導書で入れかえられる（忘れた魔法の本は戻らない）。")


def learn_action(lv, book, replace):
    try:
        st.session_state.story_notice = L.learn_book(profile, lv, book, replace)
        save()
    except ValueError as e:
        st.session_state.story_notice = f"できなかったよ：{e}"
    st.rerun()


{
    "home": view_home, "quest": view_quest, "ready": view_ready, "ally_detail": view_ally_detail, "ally_picker": view_ally_picker,
    "inventory": view_inventory, "guide": view_guide, "titles": view_titles, "shop": view_shop, "spells": view_spells,
    "battle": view_battle, "between": view_between, "retry": view_retry,
    "extra_lost": view_extra_lost, "end": view_end,
}[st.session_state.story_view]()
