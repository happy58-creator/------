"""ストーリーモード（イージー・ノーマルは10ステージ、ハードは11、ベリーハードは12ステージ）

流れ： ホーム（キャラ・難易度。装備とリュックは「倉庫とリュック」の画面） → 戦闘 → ステージ間の画面 → … → 終わり
ホームの上の「攻略」で、味方・装備・敵の説明と攻略のコツを見られる。
- 進み具合は各ステージの始めに自動で保存する（チェックポイント）。手動の中断セーブはない。
- 負けたとき・「やめる」で戻ったときは、そのステージを始めたときのHPとかばんからやり直す。
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
STAT_NAMES = {"hp": "HP", "atk": "攻撃力", "def": "防御力"}
OUTCOME_NAMES = {"clear": "全クリア", "abandon": "中断"}

common.init_state({
    "story_view": "home",        # home / inventory / guide / battle / between / retry / extra_lost / end
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
profile = st.session_state.story_profile

if st.session_state.story_view in ("battle", "between", "retry", "extra_lost") and not profile["run"]:
    st.session_state.story_view = "home"


# ---------------------------------------------------------------------------
# 表示の部品
# ---------------------------------------------------------------------------
def short_name(lv):
    return L.get_ally(lv)["name"].split("、")[-1]


def ability_text(ability):
    return f"{STAT_NAMES[ability['stat']]}+{ability['value']}"


def equip_text(equip):
    if equip["resist"]:
        return f"{story_data.STATUS_EFFECTS[equip['resist']]['name']}を半分にする"
    return "・".join(f"{STAT_NAMES[s]}+{equip[s]}" for s in ("hp", "atk", "def") if equip[s])


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
    return f"{equip['icon']} {rank}{equip['name']}（{equip_text(equip)}）" + (f"【属性 {attrs}】" if attrs else "")


def entry_label(entry):
    return equip_label(L.get_equipment(entry["id"]), entry)


def item_label(item_id):
    item = L.get_item(item_id)
    return f"{item['icon']} {item['name']}"


def counts_text(counts):
    return "、".join(f"{item_label(k)} ×{v}" for k, v in counts.items() if v) or "なし"


def hp_bar(hp, max_hp):
    st.progress(min(1.0, max(0.0, hp / max_hp)), text=f"❤️ HP {L.display_hp(hp)} / {max_hp:g}")


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
    for equip_id in rewards.get("ultra", []):
        equip = L.get_equipment(equip_id)
        col_icon, col_text = st.columns([1, 4])
        col_icon.image(str(story_assets.equipment_icon_path(equip_id)), width=72)
        col_text.success(f"🌟 超激レア装備 **{equip['name']}** を 手に入れた！（{equip_text(equip)}）→ 倉庫へ")


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
        lines.append(f"{entry_icon(entry)} {L.get_equipment(e)['name']}（{equip_text(L.get_equipment(e))}）"
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
    ally = L.get_ally(lv)
    base, now = L.ally_stats(lv), L.ally_stats(lv, profile)
    stats = []
    for stat in ("hp", "atk", "def"):
        extra = now[stat] - base[stat]
        stats.append(f"{STAT_NAMES[stat]} <b>{now[stat]:g}</b>" + (f"<span style='color:#7fd8a0'>（+{extra:g}）</span>" if extra else ""))
    gauges = []
    for i, (ability, gauge) in enumerate(zip(ally["abilities"], L.ability_gauges(L.ability_points(profile, lv))), start=1):
        mark = "✅" if gauge >= 1 else "🔒"
        gauges.append(f"<div style='font-size:12px;margin-top:4px'>{mark} アビリティ{i}：{ability_text(ability)}"
                      f"<div style='height:6px;border-radius:3px;background:#2a2228;overflow:hidden'>"
                      f"<div style='height:100%;width:{gauge * 100:.0f}%;background:linear-gradient(90deg,#c9a24a,#ffe28a)'></div></div></div>")
    gear, acc = L.split_equipped(profile, lv)
    by_uid = L.equipment_by_uid(profile)
    icons = "".join(icon_html(story_assets.equipment_thumb(by_uid[u]["id"]), L.get_equipment(by_uid[u]["id"])["name"], size=34)
                    for u in gear + acc)
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
    return (
        "<div style='display:flex;gap:12px;align-items:flex-start'>"
        f"<div style='width:30%;flex:none'><div style='position:relative'>"
        f"<img src='{story_assets.ally_thumb(lv)}' style='width:100%;border-radius:12px;display:block'>{overlay_html}</div>"
        f"<div style='margin-top:4px;line-height:0'>{icons or ''}</div></div>"
        f"<div style='flex:1;min-width:0'><div style='font-weight:700;font-size:17px'>Lv.{lv} {ally['name']}</div>"
        f"<div style='font-size:14px;margin-top:4px'>{'　'.join(stats)}</div>{resist_html}{''.join(gauges)}</div></div>"
    )


def view_ally_picker():
    """キャラクター一覧（まだ仲間でないキャラはグレー）"""
    owned = L.owned_allies(profile)
    # スマホでも1行5体のまま並べる（Streamlit は狭い画面で列を縦に積むので、この箱の中だけ止める）
    st.markdown("""<style>
.st-key-story_picker [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 6px !important; }
.st-key-story_picker [data-testid="stColumn"], .st-key-story_picker [data-testid="column"] {
  min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }
.st-key-story_picker button { padding: 2px 4px !important; min-height: 32px !important; font-size: 12px !important; }
</style>""", unsafe_allow_html=True)
    with st.container(border=True, key="story_picker"):
        st.markdown("**キャラクターを えらぶ**")
        for row in range(0, len(story_data.ALLIES), 5):
            cols = st.columns(5)
            for col, ally in zip(cols, story_data.ALLIES[row:row + 5]):
                lv = ally["lv"]
                have = lv in owned
                style = "" if have else "filter:grayscale(1) brightness(.45)"
                name = short_name(lv) if have else "？？？"
                col.markdown(f"<img src='{story_assets.ally_thumb(lv)}' style='width:100%;border-radius:8px;{style}'>"
                             f"<div style='text-align:center;font-size:11px;line-height:1.3;white-space:nowrap;overflow:hidden;"
                             f"text-overflow:ellipsis'>Lv.{lv}<br>{name}</div>", unsafe_allow_html=True)
                if have and col.button("えらぶ", key=f"_story_pick_{lv}", width="stretch",
                                       type="primary" if lv == st.session_state.story_ally else "secondary"):
                    st.session_state.story_ally = lv
                    st.session_state.story_pick_char = False
                    st.rerun()
        if st.button("とじる", key="_story_pick_close"):
            st.session_state.story_pick_char = False
            st.rerun()


# ---------------------------------------------------------------------------
# ホーム
# ---------------------------------------------------------------------------
def view_home():
    common.hero("⚔️ ストーリーモード",
                "敵をタップして攻撃！ ステージを勝ちぬいて、最後の敵をたおそう。"
                "（イージー・ノーマルは10、ハードは11、ベリーハードは12ステージ）")
    col_guide, col_bag = st.columns(2)
    if col_guide.button("📖 攻略", width="stretch"):
        go("guide")
    if col_bag.button("🎒 倉庫とリュック", width="stretch"):
        st.session_state.story_round += 1
        go("inventory")
    notice = st.session_state.pop("story_notice", None)
    if notice:
        st.info(notice)

    run = profile["run"]
    if run:
        view_continue(run)
    else:
        view_prepare()


def view_continue(run):
    """進行中の挑戦があるとき：「続きから」と「新規にプレイ」。キャラは変えられない（装備とリュックは変えられる）"""
    st.session_state.story_ally = run["ally"]
    max_hp = L.ally_stats(run["ally"], profile)["hp"]
    with st.container(border=True):
        st.markdown(
            f"#### 📌 続きから：{L.get_difficulty(run['difficulty'])['name']} {stage_label(run)} ／ "
            f"{short_name(run['ally'])} HP {L.display_hp(run['hp'])}/{max_hp:g}"
        )
        st.markdown(ally_panel_html(run["ally"]), unsafe_allow_html=True)
        hp_bar(run["hp"], max_hp)
        st.caption(f"クリアしたステージ：{run['cleared']} / {L.stage_count(run['difficulty'])}　"
                   f"リュック：{L.bag_total(run['bag'])} / {story_data.MAX_CARRY_ITEMS}こ　"
                   "（挑戦中はキャラを変えられないよ。装備とリュックは「倉庫とリュック」で変えられるよ）")
        if st.button("▶️ 続きから", type="primary", width="stretch"):
            st.session_state.story_confirm_new = False
            go_battle()

    if not st.session_state.story_confirm_new:
        if st.button("🆕 新規にプレイ", width="stretch"):
            st.session_state.story_confirm_new = True
            st.rerun()
        return
    with st.container(border=True):
        st.warning("今の挑戦を終わらせて新しく始めますか？（負け扱い。アイテムはすべてホームに戻ります）")
        col_no, col_yes = st.columns(2)
        if col_no.button("やめておく", width="stretch"):
            st.session_state.story_confirm_new = False
            st.rerun()
        if col_yes.button("終わらせる", type="primary", width="stretch"):
            st.session_state.story_confirm_new = False
            run_id = run["id"]
            summary = L.abandon_run(profile)
            save()
            log_run(summary, run_id)
            st.session_state.story_summary = summary
            new_rewards(None)
            go("end")


def view_prepare():
    """進行中の挑戦がないとき：キャラ・難易度をえらんで「プレイする」（装備とリュックは「倉庫とリュック」で）"""
    owned = L.owned_allies(profile)
    if st.session_state.story_ally not in owned:
        st.session_state.story_ally = 1
    lv = st.session_state.story_ally
    with st.container(border=True):
        st.markdown(ally_panel_html(lv), unsafe_allow_html=True)
        if st.button("🔄 キャラクター変更", width="stretch"):
            st.session_state.story_pick_char = not st.session_state.get("story_pick_char", False)
            st.rerun()
    if st.session_state.get("story_pick_char"):
        view_ally_picker()

    st.subheader("🎚️ 難易度")
    ids = [d["id"] for d in story_data.DIFFICULTIES]
    for row in (ids[:2], ids[2:]):
        cols = st.columns(2)
        for col, diff in zip(cols, row):
            label = f"{L.get_difficulty(diff)['name']}（{L.stage_count(diff)}ステージ）"
            chosen = diff == st.session_state.story_difficulty
            if col.button(("✔ " if chosen else "") + label, key=f"_story_diff_{diff}", width="stretch",
                          type="primary" if chosen else "secondary"):
                st.session_state.story_difficulty = diff
                st.rerun()

    pack = L.pack_counts(profile)
    st.subheader("🎒 リュック")
    if pack:
        st.markdown("".join(item_icon(k, n) for k, n in pack.items()), unsafe_allow_html=True)
    st.caption(f"{sum(pack.values())} / {story_data.MAX_CARRY_ITEMS}こ　持っていくアイテムは「🎒 倉庫とリュック」で入れてね。")

    st.divider()
    if st.button("⚔️ プレイする", type="primary", width="stretch"):
        L.start_run(profile, lv, st.session_state.story_difficulty)
        new_rewards(None)
        go_battle()
    st.caption("負けても、そのステージの最初から何度でもやり直せるよ。進み具合は自動で保存されるよ。")


# ---------------------------------------------------------------------------
# 倉庫とリュック・攻略
# ---------------------------------------------------------------------------
def view_inventory():
    lv = profile["run"]["ally"] if profile["run"] else st.session_state.story_ally
    round_id = st.session_state.story_round
    st.markdown(story_battle.fullscreen_css(), unsafe_allow_html=True)    # 画面いっぱいに広げる
    result = story_inventory.inventory(profile, lv, round_id, key=f"story_inventory_{round_id}")
    if not result or result.get("round") != round_id:
        return
    if result.get("action") == "save":
        try:
            L.apply_inventory(profile, lv, result)
        except ValueError as e:
            st.session_state.story_notice = f"保存できなかったよ：{e}"
            st.session_state.story_round += 1
            go("inventory")
        save()
        st.session_state.story_notice = "倉庫とリュックを保存したよ。"
    go("home")


def view_guide():
    common.hero("📖 攻略", "味方・装備・敵のことと、攻略のコツ")
    if st.button("🏠 ホームにもどる", key="_story_guide_back_top"):
        go("home")
    story_guide.render(profile)
    if st.button("🏠 ホームにもどる", key="_story_guide_back"):
        go("home")


# ---------------------------------------------------------------------------
# 戦闘（画面いっぱい）
# ---------------------------------------------------------------------------
def view_battle():
    run = profile["run"]
    round_id = st.session_state.story_round
    stage_no = L.EXTRA if run.get("extra") else run["stage"]
    st.markdown(story_battle.fullscreen_css(), unsafe_allow_html=True)
    config = L.battle_config(round_id, stage_no, run["difficulty"], run["ally"], run["hp"], profile, run["bag"])
    result = story_battle.battle(config, key=f"story_battle_{round_id}")
    if not result or result.get("round") != round_id:
        return
    outcome = result["result"]
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
        L.restore_checkpoint(profile)
        save()
        go("extra_lost" if run.get("extra") else "retry")
    else:                                      # やめる：ホームへ。次はこのステージの最初から
        L.restore_checkpoint(profile)
        save()
        st.session_state.story_notice = f"{stage_label(run)} の最初から 続けられるよ。"
        go("home")


# ---------------------------------------------------------------------------
# 負けたとき
# ---------------------------------------------------------------------------
def view_retry():
    run = profile["run"]
    enemy = L.run_enemy(run)
    common.hero("💀 やられてしまった…", f"{stage_label(run)}　Lv.{enemy['lv']} {enemy['name']}")
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
    common.hero("🐉 宇宙龍に やられてしまった…", f"Lv.{enemy['lv']} {enemy['name']} ― {enemy['title']}")
    st.image(str(story_assets.enemy_image_path(enemy)), width="stretch")
    st.markdown("負けにはならないよ。HP とかばんは、宇宙龍と戦い始めたときに もどったよ。")
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
    run = profile["run"]
    rewards = st.session_state.story_rewards
    max_hp = L.ally_stats(run["ally"], profile)["hp"]
    notice = st.session_state.pop("story_notice", None)
    if rewards and rewards.get("extra"):
        common.hero("🌟 EXTRA STAGE クリア！", f"{story_data.EXTRA_ENEMY['name']} を たおした！")
    elif rewards:
        enemy = L.enemy_by_key(rewards["enemy"])
        common.hero(f"🎉 ステージ{rewards['stage']} クリア！", f"Lv.{enemy['lv']} {enemy['name']} を たおした！")
    else:
        common.hero(f"📌 {stage_label(run)} へ", f"{short_name(run['ally'])} ／ {L.get_difficulty(run['difficulty'])['name']}")
    if notice:
        st.info(notice)
    if rewards:
        if not show_rewards(rewards):
            return                                # 仲間入りのカードを見せ終わるまで、先へは進めない
        if rewards["healed"] > 0:
            st.caption(f"休けいして HPが {L.display_hp(rewards['healed'])} 回復したよ。")

    hp_bar(run["hp"], max_hp)

    st.subheader("🎒 かばん")
    counts = L.bag_counts(run["bag"])
    if not counts:
        st.caption("かばんは からっぽ。")
    for item in story_data.ITEMS:
        n = counts.get(item["id"], 0)
        if not n:
            continue
        col_icon, col_name, col_use = st.columns([1, 4, 3])
        col_icon.image(str(story_assets.item_icon_path(item["id"])), width=36)
        col_name.markdown(f"{item['name']} ×{n}")
        if item["heal_rate"] > 0:
            if col_use.button("つかう", key=f"_story_use_{item['id']}", width="stretch",
                              disabled=run["hp"] >= max_hp):
                L.take_from_bag(run["bag"], item["id"])
                run["hp"] = L.heal(run["hp"], max_hp, item)
                save()
                st.rerun()
        else:
            col_use.caption("戦闘中に使えるよ")

    st.divider()
    if run.get("extra"):
        with st.container(border=True):
            st.markdown("### ⚠️ EXTRA STAGE")
            st.markdown("ただならぬ気配がする…… **？？？** が 行く手をはばんでいる！")
            st.caption("戦わずに「にげる」こともできるよ（負けにはならない）。")
            if st.button("⚔️ 立ち向かう", type="primary", width="stretch"):
                go_battle()
    else:
        enemy = L.run_enemy(run)
        final = run["stage"] == L.stage_count(run["difficulty"])
        col_img, col_text = st.columns([1, 3])
        col_img.image(str(story_assets.enemy_image_path(enemy)), width="stretch")
        with col_text:
            label = "FINAL STAGE" if final else f"ステージ{run['stage']}"
            st.markdown(f"**次の敵**：{label}　Lv.{enemy['lv']} {enemy['name']}")
            if enemy["gimmicks"]:
                st.caption("とくちょう：" + "・".join(
                    f"{story_data.STATUS_EFFECTS[g]['icon']}{story_data.STATUS_EFFECTS[g]['name']}" for g in enemy["gimmicks"]))
            if st.button(f"⚔️ {label} へ すすむ", type="primary", width="stretch"):
                go_battle()

    if st.button("🏠 ホームにもどる（続きから遊べるよ）", width="stretch"):
        go("home")


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
        common.hero("👑 全クリア！", f"{name} は {boss}を たおした！（{difficulty}）")
    else:
        common.hero("🏳️ 挑戦を 終えた", f"{name} ／ {difficulty} ／ ステージ{summary['cleared']}まで クリア")

    rewards = st.session_state.story_rewards
    if summary["outcome"] == "clear" and rewards:
        if not show_rewards(rewards):
            return
        if not rewards["allies"]:
            st.balloons()

    st.subheader("✨ アビリティ")
    if summary["ability_after"] > summary["ability_before"]:
        st.caption(f"{name} の アビリティが たまったよ！")
    if summary["new_abilities"]:
        st.success(f"🎊 新しいアビリティを {summary['new_abilities']}つ 解放した！")
    ability_gauges(summary["ally"], summary["ability_after"])

    st.subheader("🎒 アイテム")
    returned = summary["returned"]
    st.markdown("倉庫にもどった物：" + ("".join(item_icon(k, n) for k, n in returned.items()) or "なし"),
                unsafe_allow_html=True)

    if st.button("🏠 ホームに もどる", type="primary", width="stretch"):
        st.session_state.story_summary = None
        new_rewards(None)
        go("home")


{
    "home": view_home, "inventory": view_inventory, "guide": view_guide,
    "battle": view_battle, "between": view_between, "retry": view_retry,
    "extra_lost": view_extra_lost, "end": view_end,
}[st.session_state.story_view]()
