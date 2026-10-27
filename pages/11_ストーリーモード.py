"""ストーリーモード（全10ステージ）

流れ： ホーム（キャラ・難易度・装備・持ち込むアイテム） → 戦闘 → ステージ間の画面 → … → 終わり
数値は story_data.py、計算は story_logic.py、保存は story_profile.py にある。
"""
import streamlit as st

import common
import history
import story_assets
import story_battle
import story_data
import story_logic as L
import story_profile

common.setup_page("ストーリーモード", "⚔️")

USER = st.session_state.get("player_name") or "ななしさん"
STAT_NAMES = {"hp": "HP", "atk": "攻撃力", "def": "防御力"}
OUTCOME_NAMES = {"clear": "全クリア", "lose": "負け", "quit": "やめた"}

common.init_state({
    "story_view": "home",        # home / battle / between / end
    "story_ally": 1,
    "story_difficulty": "easy",
    "story_rewards": None,       # 直前のステージクリアでもらった物
    "story_chest_open": False,
    "story_summary": None,       # 挑戦が終わったときのまとめ
    "story_notice": None,
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
    history.log_once(
        "ストーリー", f"story-{run_id}",
        キャラ=L.get_ally(summary["ally"])["name"],
        難易度=L.get_difficulty(summary["difficulty"])["name"],
        結果=OUTCOME_NAMES[summary["outcome"]],
        クリアしたステージ=summary["cleared"],
        アビリティ=f"+{summary['ability_after'] - summary['ability_before']:g}",
    )


def end_run(outcome):
    """挑戦を終わらせて、終わりの画面へ"""
    run_id = profile["run"]["id"]
    summary = L.finish_run(profile, outcome)
    save()
    log_run(summary, run_id)
    st.session_state.story_summary = summary
    st.session_state.story_view = "end"


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

# 中断セーブせずに画面を閉じた挑戦は「やめた」扱いで終わらせる
if profile["run"] and st.session_state.get("story_run_id") != profile["run"]["id"]:
    end_run("quit")
    st.session_state.story_view = "home"
    st.session_state.story_notice = (
        "前の挑戦は、中断セーブをせずに画面を閉じたので「やめた」扱いにしたよ。"
        "拾ったアイテムはホームに入れたよ（持ちこんだアイテムはなくなったよ）。"
    )
if st.session_state.story_view in ("battle", "between") and not profile["run"]:
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
    return "・".join(f"{STAT_NAMES[s]}+{equip[s]}" for s in ("atk", "def", "hp") if equip[s])


def equip_label(equip):
    return f"{equip['icon']} {equip['name']}（{equip_text(equip)}）"


def item_label(item_id):
    item = L.get_item(item_id)
    return f"{item['icon']} {item['name']}"


def counts_text(counts):
    return "、".join(f"{item_label(k)} ×{v}" for k, v in counts.items() if v) or "なし"


def hp_bar(hp, max_hp):
    st.progress(min(1.0, max(0.0, hp / max_hp)), text=f"❤️ HP {L.display_hp(hp)} / {max_hp:g}")


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


def show_rewards(rewards):
    """ステージクリアでもらった物（宝箱は「あける」を押してから見せる）"""
    for lv in rewards["allies"]:
        col_icon, col_text = st.columns([1, 4])
        col_icon.image(str(story_assets.ASSET_DIR / "ally_icons" / L.get_ally(lv)["image"]), width=72)
        col_text.success(f"🤝 **{L.get_ally(lv)['name']}** が 仲間になった！")
    if not rewards["chests"]:
        st.caption("宝箱は 出なかった…")
        return
    if not st.session_state.story_chest_open:
        st.markdown(f"<div style='font-size:2.6rem;text-align:center'>{'🎁' * rewards['chests']}</div>",
                    unsafe_allow_html=True)
        if st.button(f"🎁 宝箱を あける（{rewards['chests']}こ）", width="stretch"):
            st.session_state.story_chest_open = True
            st.rerun()
        return
    found = [item_label(i) for i in rewards["items"]]
    found += [f"{item_label(i)}（かばんがいっぱいなので ホームへ）" for i in rewards["sent_home"]]
    found += [f"{equip_label(L.get_equipment(e))} → 倉庫へ" for e in rewards["equipment"]]
    st.info("🎁 宝箱の中身：\n\n" + "\n".join(f"- {f}" for f in found))


# ---------------------------------------------------------------------------
# ホーム
# ---------------------------------------------------------------------------
def view_home():
    common.hero("⚔️ ストーリーモード", "敵をタップして攻撃！ 10ステージを勝ちぬいて、終焉の創造主をたおそう。")
    notice = st.session_state.pop("story_notice", None)
    if notice:
        st.info(notice)

    suspended = profile["suspended"]
    if suspended:
        with st.container(border=True):
            st.markdown(
                f"📌 **中断セーブ**：{short_name(suspended['ally'])} ／ "
                f"{L.get_difficulty(suspended['difficulty'])['name']} ／ 次は ステージ{suspended['stage']}"
            )
            max_hp = L.ally_stats(suspended["ally"], profile)["hp"]
            hp_bar(suspended["hp"], max_hp)
            if st.button("▶️ つづきから あそぶ", type="primary", width="stretch"):
                run = L.resume_run(profile)
                save()
                st.session_state.story_run_id = run["id"]
                st.session_state.story_rewards = None
                st.session_state.story_view = "between"
                st.rerun()

    owned = L.owned_allies(profile)
    if st.session_state.story_ally not in owned:
        st.session_state.story_ally = 1
    st.subheader("🧑‍🤝‍🧑 キャラを えらぶ")
    lv = st.radio(
        "キャラ", owned, index=owned.index(st.session_state.story_ally),
        format_func=lambda v: f"Lv.{v} {short_name(v)}", horizontal=True, label_visibility="collapsed",
    )
    st.session_state.story_ally = lv

    col_img, col_info = st.columns([2, 3])
    with col_img:
        st.image(str(story_assets.ally_image_path(lv)), width="stretch")
    with col_info:
        st.markdown(f"#### {L.get_ally(lv)['name']}")
        show_stats(lv)
        ability_gauges(lv, L.ability_points(profile, lv))
        st.caption("アビリティは、挑戦が終わる（全クリアか負け）たびに少しずつたまるよ。")

    with st.expander(f"🛡️ そうび（{len(L.equipped_uids(profile, lv))} / {story_data.MAX_EQUIP_SLOTS}）",
                     expanded=bool(profile["equipment"])):
        view_equipment(lv)
    with st.expander(f"📖 なかま（{len(owned)} / {len(story_data.ALLIES)}）"):
        for ally in story_data.ALLIES:
            if ally["lv"] in owned:
                st.markdown(f"✅ Lv.{ally['lv']} {ally['name']}")
            else:
                cond = ally["unlock"]
                st.markdown(f"❔ Lv.{ally['lv']} ？？？ — {L.get_difficulty(cond['min_difficulty'])['name']}"
                            f"以上で ステージ{cond['stage']} をクリアすると、仲間になるかも")

    st.subheader("🎚️ 難易度")
    ids = [d["id"] for d in story_data.DIFFICULTIES]
    difficulty = st.radio(
        "難易度", ids, index=ids.index(st.session_state.story_difficulty),
        format_func=lambda d: L.get_difficulty(d)["name"], horizontal=True, label_visibility="collapsed",
    )
    st.session_state.story_difficulty = difficulty

    st.subheader("🎒 もっていく アイテム")
    carried = {}
    home_items = {k: v for k, v in profile["items"].items() if v > 0}
    if not home_items:
        st.caption("ホームに アイテムがないよ。宝箱から 手に入るよ。")
    for item in story_data.ITEMS:
        have = home_items.get(item["id"], 0)
        if have:
            carried[item["id"]] = st.number_input(
                f"{item['icon']} {item['name']}（ホームに {have}こ）", min_value=0, max_value=have, step=1,
                key=f"_story_carry_{item['id']}",
            )
    total = sum(carried.values())
    too_many = total > story_data.MAX_CARRY_ITEMS
    if home_items:
        (st.error if too_many else st.caption)(f"かばん：{total} / {story_data.MAX_CARRY_ITEMS}こ")

    st.divider()
    confirmed = True
    if suspended:
        confirmed = st.checkbox("中断セーブを消して、新しく始める（中断セーブの挑戦は「やめた」扱いになるよ）")
    if st.button("⚔️ しゅつじん！", type="primary", width="stretch", disabled=too_many or not confirmed):
        if suspended:
            dropped = L.drop_suspended(profile)
            log_run(dropped, suspended["id"])
        run = L.start_run(profile, lv, difficulty, carried)
        save()
        for item in story_data.ITEMS:
            st.session_state.pop(f"_story_carry_{item['id']}", None)
        st.session_state.story_run_id = run["id"]
        st.session_state.story_round += 1
        st.session_state.story_view = "battle"
        st.rerun()
    st.caption("負けたり やめたりすると、持ちこんだアイテムは なくなるよ。拾った物は ホームに入るよ。")


def view_equipment(lv):
    by_uid = L.equipment_by_uid(profile)
    if not by_uid:
        st.caption("まだ装備を持っていないよ。宝箱から 手に入るよ。")
        return
    key = f"_story_equip_{lv}"

    def on_change():
        try:
            L.set_equipment(profile, lv, st.session_state[key])
            save()
        except ValueError as e:
            st.session_state[key] = L.equipped_uids(profile, lv)
            st.session_state.story_notice_equip = str(e)

    st.session_state.setdefault(key, L.equipped_uids(profile, lv))
    st.multiselect(
        f"付ける装備（{story_data.MAX_EQUIP_SLOTS}つまで。同じ装備は2つ付けられないよ）",
        L.equip_choices(profile, lv),
        format_func=lambda uid: equip_label(L.get_equipment(by_uid[uid]["id"])),
        max_selections=story_data.MAX_EQUIP_SLOTS, key=key, on_change=on_change,
    )
    error = st.session_state.pop("story_notice_equip", None)
    if error:
        st.warning(error)
    owner = {uid: int(a) for a, uids in profile["equipped"].items() for uid in uids}
    rows = []
    for equip in story_data.EQUIPMENT:
        mine = [e["uid"] for e in profile["equipment"] if e["id"] == equip["id"]]
        if mine:
            users = sorted({short_name(owner[u]) for u in mine if u in owner})
            rows.append(f"- {equip_label(equip)} ×{len(mine)}" + (f"　（{'・'.join(users)} が使用中）" if users else ""))
    st.markdown("**倉庫**\n" + "\n".join(rows))


# ---------------------------------------------------------------------------
# 戦闘
# ---------------------------------------------------------------------------
def view_battle():
    run = profile["run"]
    round_id = st.session_state.story_round
    config = L.battle_config(round_id, run["stage"], run["difficulty"], run["ally"], run["hp"], profile, run["bag"])
    result = story_battle.battle(config, key=f"story_battle_{round_id}")
    if not result or result.get("round") != round_id:
        return
    for item_id, n in (result.get("used") or {}).items():
        try:
            L.take_from_bag(run["bag"], item_id, int(n))
        except (ValueError, KeyError):
            pass
    run["hp"] = result["ally_hp"]
    if result["result"] == "win":
        rewards = L.clear_stage(profile)
        save()
        st.session_state.story_rewards = rewards
        st.session_state.story_chest_open = False
        if rewards["finished"]:
            log_run(rewards["finished"], run["id"])
            st.session_state.story_summary = rewards["finished"]
            st.session_state.story_view = "end"
        else:
            st.session_state.story_view = "between"
    else:
        st.session_state.story_rewards = None
        end_run(result["result"])
    st.rerun()


# ---------------------------------------------------------------------------
# ステージ間の画面
# ---------------------------------------------------------------------------
def view_between():
    run = profile["run"]
    rewards = st.session_state.story_rewards
    max_hp = L.ally_stats(run["ally"], profile)["hp"]
    if rewards:
        enemy = L.get_enemy(rewards["stage"])
        common.hero(f"🎉 ステージ{rewards['stage']} クリア！", f"Lv.{enemy['lv']} {enemy['name']} を たおした！")
        if rewards["allies"]:
            st.balloons()
        show_rewards(rewards)
        if rewards["healed"] > 0:
            st.caption(f"休けいして HPが {L.display_hp(rewards['healed'])} 回復したよ。")
    else:
        common.hero(f"📌 ステージ{run['stage']} から つづき", f"{short_name(run['ally'])} ／ {L.get_difficulty(run['difficulty'])['name']}")

    hp_bar(run["hp"], max_hp)

    st.subheader("🎒 かばん")
    counts = L.bag_counts(run["bag"])
    if not counts:
        st.caption("かばんは からっぽ。")
    for item in story_data.ITEMS:
        n = counts.get(item["id"], 0)
        if not n:
            continue
        col_name, col_use = st.columns([3, 2])
        col_name.markdown(f"{item['icon']} {item['name']} ×{n}")
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
    enemy = L.get_enemy(run["stage"])
    col_img, col_text = st.columns([1, 3])
    col_img.image(str(story_assets.ASSET_DIR / "enemies" / enemy["image"]), width="stretch")
    with col_text:
        st.markdown(f"**次の敵**：ステージ{run['stage']}　Lv.{enemy['lv']} {enemy['name']}")
        if enemy["gimmicks"]:
            st.caption("とくちょう：" + "・".join(
                f"{story_data.STATUS_EFFECTS[g]['icon']}{story_data.STATUS_EFFECTS[g]['name']}" for g in enemy["gimmicks"]))
        if st.button(f"⚔️ ステージ{run['stage']} へ すすむ", type="primary", width="stretch"):
            st.session_state.story_round += 1
            st.session_state.story_view = "battle"
            st.rerun()

    col_save, col_quit = st.columns(2)
    with col_save:
        if st.button("💾 中断セーブして ホームへ", width="stretch"):
            L.suspend_run(profile)
            save()
            st.session_state.story_notice = "中断セーブしたよ。ホームの「つづきから あそぶ」で再開できるよ。"
            st.session_state.story_view = "home"
            st.rerun()
    with col_quit:
        with st.popover("🏳️ やめる", width="stretch"):
            st.write("やめると 負けと同じ扱いになるよ。持ちこんだアイテムはなくなり、アビリティもたまらないよ。")
            if st.button("やめる", type="primary", key="_story_quit"):
                end_run("quit")
                st.rerun()


# ---------------------------------------------------------------------------
# 挑戦の終わり
# ---------------------------------------------------------------------------
def view_end():
    summary = st.session_state.story_summary
    if not summary:
        st.session_state.story_view = "home"
        st.rerun()
    name = short_name(summary["ally"])
    difficulty = L.get_difficulty(summary["difficulty"])["name"]
    if summary["outcome"] == "clear":
        st.balloons()
        common.hero("👑 全クリア！", f"{name} は 終焉の創造主を たおした！（{difficulty}）")
    elif summary["outcome"] == "lose":
        common.hero("💀 やられてしまった…", f"{name} ／ {difficulty} ／ ステージ{summary['cleared']}まで クリア")
    else:
        common.hero("🏳️ 挑戦を やめた", f"{name} ／ {difficulty} ／ ステージ{summary['cleared']}まで クリア")

    rewards = st.session_state.story_rewards
    if summary["outcome"] == "clear" and rewards:
        show_rewards(rewards)

    st.subheader("✨ アビリティ")
    if summary["outcome"] == "quit":
        st.caption("やめた挑戦では、アビリティは たまらないよ。")
    elif summary["ability_after"] > summary["ability_before"]:
        st.caption(f"{name} の アビリティが たまったよ！")
    if summary["new_abilities"]:
        st.success(f"🎊 新しいアビリティを {summary['new_abilities']}つ 解放した！")
    ability_gauges(summary["ally"], summary["ability_after"])

    st.subheader("🎒 アイテム")
    st.markdown(f"ホームに入った物：{counts_text(summary['returned'])}")
    if summary["lost"]:
        st.markdown(f"なくなった物：{counts_text(summary['lost'])}")

    if st.button("🏠 ホームに もどる", type="primary", width="stretch"):
        st.session_state.story_view = "home"
        st.session_state.story_summary = None
        st.session_state.story_rewards = None
        st.rerun()


{"home": view_home, "battle": view_battle, "between": view_between, "end": view_end}[st.session_state.story_view]()
