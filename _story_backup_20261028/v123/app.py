"""かけいぼ（家計簿）
教材アプリの中の、メニューに出ないページ（URL の最後が /kakeibo）。パスワードは secrets の KAKEIBO_PASSWORD。
画面：メニュー（色つきのボタン）・入力・カレンダー・レポート・予算・サブスク・記録一覧・カテゴリ・設定。
下には、いつも「入力・カレンダー・レポート・予算・メニュー」のボタン（フッター）。
チェックボックスやラジオボタンは使わず、ボタンで選ぶ。保存は kb_store.py、計算は kb_calc.py。"""
import hmac
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))      # このフォルダの kb_calc・kb_store を読む
import kb_calc as calc  # noqa: E402
import kb_store as store  # noqa: E402
from kb_calc import EXPENSE, INCOME, MONTHLY, YEARLY  # noqa: E402

try:
    st.set_page_config(page_title="かけいぼ", page_icon="💴", layout="centered")
except Exception:
    pass

# ---- 決まりごと ----
DEFAULT_CATS = {
    EXPENSE: [("🍽️", "食費"), ("🧴", "日用品"), ("👕", "衣服"), ("💄", "美容"), ("🥂", "交際費"), ("💊", "医療費"),
              ("📝", "教育費"), ("💡", "光熱費"), ("🚃", "交通費"), ("📱", "通信費"), ("🏠", "住居費"), ("🔁", "サブスク"), ("📦", "その他")],
    INCOME: [("💴", "給与"), ("🎁", "賞与"), ("💼", "副収入"), ("📦", "その他")],
}
# メニューのボタン（色は、いただいた見本の順）
TILES = [("入力", "✏️", "input", "#5068FF"), ("カレンダー", "📅", "calendar", "#02D6B2"), ("レポート", "📊", "report", "#36F8DD"),
         ("予算", "👛", "budget", "#3ED7F8"), ("サブスク", "🔁", "subs", "#4744CE"), ("記録の一覧", "📋", "list", "#787EF8"),
         ("カテゴリ", "🏷️", "cats", "#00B0FF"), ("設定", "⚙️", "settings", "#22CF7B")]
# フッター（下の5つのボタン）
FOOT = [("入力", ":material/edit:", "input"), ("カレンダー", ":material/calendar_month:", "calendar"),
        ("レポート", ":material/donut_large:", "report"), ("予算", ":material/account_balance_wallet:", "budget"),
        ("メニュー", ":material/more_horiz:", "home")]
ORANGE, GREEN, RED, BLUE = "#E8822D", "#3CB46E", "#E8572D", "#3A8FE0"
CHART_COLORS = ["#5068FF", "#02D6B2", "#E8822D", "#4744CE", "#00B0FF", "#22CF7B", "#787EF8", "#F2B33D", "#E8572D", "#3ED7F8", "#9B6BD8", "#8A9099", "#36C9A0"]
SOON_DAYS, YEARLY_SOON_DAYS = 7, 30     # サブスクの支払いを知らせる日数（年払いは早めに）
WEEK = "日月火水木金土"


def today():
    return datetime.now(ZoneInfo("Asia/Tokyo")).date()


def yen(n, sign=False):
    n = int(round(n))
    return (("+" if n > 0 else "-" if n < 0 else "") if sign else ("-" if n < 0 else "")) + f"¥{abs(n):,}"


def secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return None


def dlabel(d):
    return f"{d.year}年{d.month}月{d.day}日（{WEEK[(d.weekday() + 1) % 7]}）"


# ---- 見た目 ----
def css(extra=""):
    st.markdown(f"""<style>
/* 教材アプリのメニュー（サイドバー）は、このページでは出さない */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] {{ display: none !important; }}
.block-container {{ max-width: 640px; padding-top: 1.2rem; padding-bottom: 7.5rem; }}
/* 横に並べたボタンは、スマホでも縦に積まない */
[class*="st-key-kb_row"] [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: .5rem; }}
[class*="st-key-kb_row"] [data-testid="stColumn"], [class*="st-key-kb_row"] [data-testid="column"] {{ min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }}
/* フッター */
.st-key-kb_foot {{ position: fixed; z-index: 1000; left: 50%; transform: translateX(-50%); bottom: calc(env(safe-area-inset-bottom, 0px) + 10px);
  width: min(94vw, 600px); background: rgba(255,255,255,.97); border-radius: 34px; padding: 6px 8px;
  box-shadow: 0 6px 24px rgba(0,0,0,.14), 0 0 0 1px rgba(0,0,0,.05); }}
.st-key-kb_foot [data-testid="stHorizontalBlock"] {{ gap: 2px !important; }}
.st-key-kb_foot button {{ width: 100%; border: 0 !important; background: transparent !important; box-shadow: none !important; border-radius: 26px;
  flex-direction: column; gap: 0; padding: 8px 0 6px; min-height: 0; color: #333 !important; }}
.st-key-kb_foot button p {{ font-size: .72rem; font-weight: 700; white-space: nowrap; }}
.st-key-kb_foot button [data-testid="stIconMaterial"] {{ font-size: 1.55rem; }}
/* メニューの色つきボタン */
[class*="st-key-kb_tile"] button {{ width: 100%; height: 108px; border: 0 !important; border-radius: 16px; color: #fff !important;
  flex-direction: column; gap: .2rem; box-shadow: 0 4px 12px rgba(0,0,0,.12); }}
[class*="st-key-kb_tile"] button p {{ font-size: 1.05rem; font-weight: 800; }}
[class*="st-key-kb_tile"] button span[data-testid="stIconEmoji"], [class*="st-key-kb_tile"] button > div > span {{ font-size: 1.7rem; }}
/* 入力：カテゴリのボタン */
[class*="st-key-kb_cat"] button {{ width: 100%; height: 78px; flex-direction: column; gap: 0; border-radius: 10px; background: #fff; }}
[class*="st-key-kb_cat"] button p {{ font-size: .86rem; }}
[class*="st-key-kb_cat"] button span[data-testid="stIconEmoji"], [class*="st-key-kb_cat"] button > div > span {{ font-size: 1.6rem; }}
/* 支出・収入の切りかえ */
.st-key-kb_kind {{ background: #f1f1f1; border-radius: 30px; padding: 4px; }}
.st-key-kb_kind button {{ width: 100%; border: 0 !important; border-radius: 26px; background: transparent !important; box-shadow: none !important; }}
.st-key-kb_kind button p {{ font-weight: 800; color: #777; }}
/* 大きな決定ボタン */
.st-key-kb_submit button {{ width: 100%; height: 56px; border-radius: 30px; border: 0 !important; background: {ORANGE} !important; color: #fff !important; }}
.st-key-kb_submit button p {{ font-size: 1.1rem; font-weight: 800; }}
/* 月・日の見出し */
.kb-head {{ background: #fdf6e3; border-radius: 10px; text-align: center; padding: .45rem .3rem; font-weight: 800; font-size: 1.15rem; }}
.kb-head small {{ font-weight: 500; font-size: .75rem; color: #666; }}
[class*="st-key-kb_arrow"] button {{ border: 0 !important; background: transparent !important; box-shadow: none !important; padding: 0 .4rem; }}
[class*="st-key-kb_arrow"] button p {{ font-size: 1.6rem; color: #888; }}
/* アイコンを文字の上に（ボタンの中を縦並びに） */
.st-key-kb_foot button, .st-key-kb_foot button > div, [class*="st-key-kb_tile"] button, [class*="st-key-kb_tile"] button > div,
[class*="st-key-kb_cat"] button, [class*="st-key-kb_cat"] button > div {{ display: flex; flex-direction: column !important; align-items: center; justify-content: center; }}
input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button {{ -webkit-appearance: none; margin: 0; }}
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {{ display: none !important; }}
.kb-title {{ text-align: center; font-weight: 800; font-size: 1.2rem; margin: .2rem 0 .6rem; }}
.kb-sum {{ display: flex; justify-content: space-around; text-align: center; padding: .5rem 0; background: #fff; border-radius: 12px; }}
.kb-sum div span {{ display: block; font-size: .8rem; color: #555; }}
.kb-sum div b {{ font-size: 1.25rem; }}
.kb-row {{ display: flex; justify-content: space-between; align-items: center; gap: .6rem; padding: .55rem .2rem; border-bottom: 1px solid #eee; }}
.kb-row .l {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.kb-row .r {{ white-space: nowrap; font-weight: 700; }}
.kb-bar {{ height: 9px; background: #eee; border-radius: 6px; overflow: hidden; margin: .3rem 0 .1rem; }}
.kb-bar > i {{ display: block; height: 100%; border-radius: 6px; }}
/* カレンダー */
.kb-cal {{ width: 100%; border-collapse: collapse; table-layout: fixed; background: #fff; }}
.kb-cal th {{ background: #e9e9e9; font-weight: 500; font-size: .85rem; padding: .25rem 0; }}
.kb-cal td {{ border: 1px solid #e3e3e3; vertical-align: top; height: 64px; padding: 3px 4px; font-size: .8rem; }}
.kb-cal td.out {{ background: #f4f4f4; color: #aaa; }}
.kb-cal td.today {{ background: #fdf6e3; font-weight: 800; }}
.kb-cal .sun {{ color: {RED}; }} .kb-cal .sat {{ color: {BLUE}; }}
.kb-cal .inc {{ color: {BLUE}; font-size: .66rem; display: block; text-align: right; }}
.kb-cal .exp {{ color: {RED}; font-size: .66rem; display: block; text-align: right; }}
.kb-day {{ font-weight: 800; margin: .8rem 0 .1rem; color: #444; }}
{extra}
</style>""", unsafe_allow_html=True)


# ---- パスワード（secrets に KAKEIBO_PASSWORD があるときだけ） ----
def gate():
    pw = secret("KAKEIBO_PASSWORD")
    if not pw or st.session_state.get("kb_ok"):
        return
    css()
    st.markdown("<div class='kb-title'>💴 かけいぼ</div>", unsafe_allow_html=True)
    with st.form("login"):
        v = st.text_input("パスワード", type="password")
        if st.form_submit_button("ひらく", type="primary", use_container_width=True):
            if hmac.compare_digest(v.encode(), str(pw).encode()):
                st.session_state.kb_ok = True
                st.rerun()
            st.error("パスワードがちがいます")
    st.stop()


# ---- データ ----
def categories(kind):
    rows = [(r.get("アイコン") or "📦", r["名前"]) for r in store.load("カテゴリ") if r["種類"] == kind and r["名前"]]
    return rows or DEFAULT_CATS[kind]


def icon_of(kind, name):
    return dict((n, i) for i, n in categories(kind)).get(name, "📦")


def go(view):
    st.session_state.kb_view = view


def month_nav(key):
    """‹ 2026年11月 › の見出し"""
    import calendar as _c
    month = st.session_state.kb_month
    y, m = int(month[:4]), int(month[5:])
    end = _c.monthrange(y, m)[1]
    with st.container(key=f"kb_row_{key}"):
        a, b, c = st.columns([1, 6, 1], vertical_alignment="center")
        with a, st.container(key=f"kb_arrow_{key}_p"):
            st.button("‹", key=f"{key}_prev", on_click=lambda: st.session_state.update(kb_month=calc.shift_month(month, -1)))
        b.markdown(f"<div class='kb-head'>{y}年 {m}月 <small>（{m}月1日 − {m}月{end}日）</small></div>", unsafe_allow_html=True)
        with c, st.container(key=f"kb_arrow_{key}_n"):
            st.button("›", key=f"{key}_next", on_click=lambda: st.session_state.update(kb_month=calc.shift_month(month, 1)))


def sum_box(t):
    st.markdown(f"<div class='kb-sum'><div><span>収入</span><b style='color:{BLUE}'>{yen(t['収入'])}</b></div>"
                f"<div><span>支出</span><b style='color:{RED}'>{yen(t['支出'])}</b></div>"
                f"<div><span>合計</span><b style='color:{BLUE if t['収支'] >= 0 else RED}'>{yen(t['収支'], True)}</b></div></div>", unsafe_allow_html=True)


def sub_alerts(subs):
    for s in calc.upcoming(subs, today(), YEARLY_SOON_DAYS):
        n, yearly = s["あと何日"], s["周期"] == YEARLY
        if n > SOON_DAYS and not yearly:
            continue
        when = f"{-n}日すぎています" if n < 0 else "今日" if n == 0 else f"あと{n}日"
        st.warning(f"🔁 {'【年払い】' if yearly else ''}{s['名前']}　{yen(calc.to_int(s['金額']))}　{s['次の支払日'].replace('-', '/')}（{when}）")


# =========================================================================
# 画面
# =========================================================================
def view_home(records, subs):
    st.markdown("<div class='kb-title'>💴 かけいぼ</div>", unsafe_allow_html=True)
    month = calc.ym(today())
    st.caption(f"今月（{int(month[5:])}月）")
    sum_box(calc.totals(calc.in_month(records, month)))
    sub_alerts(subs)
    st.write("")
    extra = "".join(f".st-key-kb_tile_{v} button {{ background: {c} !important; }}" + (f".st-key-kb_tile_{v} button p {{ color: #134 !important; }}" if v in ("report", "budget") else "")
                    for _, _, v, c in TILES)
    st.markdown(f"<style>{extra}</style>", unsafe_allow_html=True)
    for k in range(0, len(TILES), 2):
        with st.container(key=f"kb_row_tiles{k}"):
            cols = st.columns(2)
            for col, (label, icon, view, _) in zip(cols, TILES[k:k + 2]):
                with col, st.container(key=f"kb_tile_{view}"):
                    st.button(label, icon=icon, key=f"tile_{view}", on_click=go, args=(view,))


def view_input():
    ss = st.session_state
    kind = ss.setdefault("kb_kind", EXPENSE)
    ss.setdefault("kb_date", today())
    ss.setdefault("kb_amount", None)
    cats = categories(kind)
    if ss.get("kb_cat") not in [n for _, n in cats]:
        ss.kb_cat = cats[0][1]
    # 支出・収入
    st.markdown(f"<style>.st-key-kb_kind_{'exp' if kind == EXPENSE else 'inc'} button {{ background: #fff !important; box-shadow: 0 1px 4px rgba(0,0,0,.12) !important; }}"
                f".st-key-kb_kind_{'exp' if kind == EXPENSE else 'inc'} button p {{ color: {ORANGE if kind == EXPENSE else BLUE} !important; }}</style>", unsafe_allow_html=True)
    with st.container(key="kb_kind"), st.container(key="kb_row_kind"):
        a, b = st.columns(2)
        with a, st.container(key="kb_kind_exp"):
            st.button("支出", key="kind_exp", on_click=lambda: ss.update(kb_kind=EXPENSE))
        with b, st.container(key="kb_kind_inc"):
            st.button("収入", key="kind_inc", on_click=lambda: ss.update(kb_kind=INCOME))
    # 日付（‹ ›で1日ずつ）
    with st.container(key="kb_row_date"):
        a, b, c = st.columns([1, 6, 1], vertical_alignment="center")
        with a, st.container(key="kb_arrow_dp"):
            st.button("‹", key="day_prev", on_click=lambda: ss.update(kb_date=ss.kb_date - timedelta(days=1)))
        b.date_input("日付", key="kb_date", format="YYYY/MM/DD", label_visibility="collapsed")
        with c, st.container(key="kb_arrow_dn"):
            st.button("›", key="day_next", on_click=lambda: ss.update(kb_date=ss.kb_date + timedelta(days=1)))
    st.caption(dlabel(ss.kb_date))
    st.text_input("メモ", key="kb_memo", placeholder="未入力")
    st.number_input("収入（円）" if kind == INCOME else "支出（円）", min_value=0, step=100, key="kb_amount", placeholder="0")
    st.markdown("**カテゴリー**")
    sel = ss.kb_cat
    st.markdown(f"<style>[class*='st-key-kb_cat_'] button {{ border: 1px solid #ddd !important; }}"
                f".st-key-kb_cat_{cats.index(next(c for c in cats if c[1] == sel))} button {{ border: 2.5px solid #888 !important; background: #fafafa !important; }}</style>", unsafe_allow_html=True)
    for k in range(0, len(cats), 3):
        with st.container(key=f"kb_row_cat{k}"):
            cols = st.columns(3)
            for j, (col, (ic, name)) in enumerate(zip(cols, cats[k:k + 3])):
                with col, st.container(key=f"kb_cat_{k + j}"):
                    st.button(name, icon=ic, key=f"cat_{kind}_{k + j}", on_click=lambda n=name: ss.update(kb_cat=n))
    st.button("＋ カテゴリーの編集・追加", key="to_cats", on_click=go, args=("cats",))
    with st.container(key="kb_submit"):
        st.button(f"{kind}を入力する", key="submit", on_click=add_record)
    msg = ss.pop("kb_msg", None)
    if msg:
        (st.error if msg.startswith("⚠") else st.success)(msg)


def add_record():
    ss = st.session_state
    amount = ss.get("kb_amount") or 0
    if amount <= 0:
        ss.kb_msg = "⚠ 金額を入れてください"
        return
    store.append("記録", {"日付": ss.kb_date.isoformat(), "種類": ss.kb_kind, "金額": int(amount), "カテゴリ": ss.kb_cat, "メモ": ss.get("kb_memo", "")})
    ss.kb_msg = f"記録しました：{ss.kb_date.month}/{ss.kb_date.day}　{ss.kb_cat}　{yen(amount)}"
    ss.kb_amount = None
    ss.kb_memo = ""


def view_calendar(records):
    st.markdown("<div class='kb-title'>カレンダー</div>", unsafe_allow_html=True)
    month_nav("cal")
    month = st.session_state.kb_month
    days = calc.by_day(records)
    t0 = today()
    head = "".join(f"<th class='{'sun' if i == 0 else 'sat' if i == 6 else ''}'>{w}</th>" for i, w in enumerate(WEEK))
    body = ""
    for week in calc.month_weeks(month):
        body += "<tr>"
        for i, d in enumerate(week):
            cls = []
            if calc.ym(d) != month:
                cls.append("out")
            if d == t0:
                cls.append("today")
            v = days.get(d.isoformat(), {})
            amt = (f"<span class='inc'>{v[INCOME]:,}</span>" if v.get(INCOME) else "") + (f"<span class='exp'>{v[EXPENSE]:,}</span>" if v.get(EXPENSE) else "")
            num = f"<span class='{'sun' if i == 0 else 'sat' if i == 6 else ''}'>{d.day}</span>"
            body += f"<td class='{' '.join(cls)}'>{num}{amt}</td>"
        body += "</tr>"
    st.markdown(f"<table class='kb-cal'><tr>{head}</tr>{body}</table>", unsafe_allow_html=True)
    month_recs = calc.in_month(records, month)
    sum_box(calc.totals(month_recs))
    # 日ごとの記録（新しい日から）
    by = {}
    for r in sorted(month_recs, key=lambda r: (r["日付"], r["登録日時"]), reverse=True):
        by.setdefault(r["日付"], []).append(r)
    for d, rs in by.items():
        st.markdown(f"<div class='kb-day'>{dlabel(calc.to_date(d))}</div>", unsafe_allow_html=True)
        for r in rs:
            inc = r["種類"] == INCOME
            st.markdown(f"<div class='kb-row'><span class='l'>{icon_of(r['種類'], r['カテゴリ'])} {r['カテゴリ']}　<span style='color:#888'>{r['メモ']}</span></span>"
                        f"<span class='r' style='color:{BLUE if inc else RED}'>{yen(calc.to_int(r['金額']) * (1 if inc else -1), True)}</span></div>", unsafe_allow_html=True)


def view_report(records):
    st.markdown("<div class='kb-title'>レポート</div>", unsafe_allow_html=True)
    month_nav("rep")
    month = st.session_state.kb_month
    recs = calc.in_month(records, month)
    t = calc.totals(recs)
    st.markdown(f"<div style='text-align:center;background:#f4f4f4;border-radius:20px;padding:.35rem;font-weight:700'>"
                f"<span style='color:{GREEN}'>{yen(t['収入'])}</span> − <span style='color:{ORANGE}'>{yen(t['支出'])}</span> = {yen(t['収支'], True)}</div>", unsafe_allow_html=True)
    try:
        import altair as alt
    except ImportError:
        alt = None
    # 1年の収入（上・緑）と支出（下・オレンジ）
    tr = calc.trend(records, month, 12)
    rows = []
    for x in tr:
        lab = f"{int(x['月'][5:])}月"
        rows += [{"月": lab, "順": x["月"], "種類": INCOME, "金額": x["収入"] / 1000}, {"月": lab, "順": x["月"], "種類": EXPENSE, "金額": -x["支出"] / 1000}]
    dft = pd.DataFrame(rows)
    st.markdown(f"<div style='text-align:center;color:{GREEN};font-weight:700;margin-top:.8rem'>{month[:4]}年までの1年</div>", unsafe_allow_html=True)
    if alt:
        bars = alt.Chart(dft).mark_bar(size=16).encode(
            x=alt.X("月:N", sort=[f"{int(x['月'][5:])}月" for x in tr], title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("金額:Q", title="千円"),
            color=alt.Color("種類:N", scale=alt.Scale(domain=[INCOME, EXPENSE], range=[GREEN, ORANGE]), legend=None),
            tooltip=["月", "種類", alt.Tooltip("金額:Q", format=",.1f", title="千円")]).properties(height=220)
        st.altair_chart(bars, use_container_width=True)
    else:
        st.bar_chart(dft.pivot(index="月", columns="種類", values="金額"))
    # カテゴリ別（支出）：円グラフと一覧
    cats = calc.by_category(recs, EXPENSE)
    st.markdown("**この月の支出**")
    if not cats:
        st.info("この月の支出はまだありません")
        return
    dfc = pd.DataFrame({"カテゴリ": list(cats), "金額": list(cats.values())})
    if alt:
        pie = alt.Chart(dfc).mark_arc(innerRadius=58, outerRadius=105).encode(
            theta="金額:Q", color=alt.Color("カテゴリ:N", sort=list(cats), scale=alt.Scale(range=CHART_COLORS), legend=None),
            tooltip=["カテゴリ", alt.Tooltip("金額:Q", format=",")]).properties(height=230)
        st.altair_chart(pie, use_container_width=True)
    total = sum(cats.values())
    for i, (c, v) in enumerate(cats.items()):
        dot = f"<span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:{CHART_COLORS[i % len(CHART_COLORS)]};margin-right:6px'></span>"
        st.markdown(f"<div class='kb-row'><span class='l'>{dot}{icon_of(EXPENSE, c)} {c} <span style='color:#888'>({v / total:.0%})</span></span><span class='r'>{yen(v)}</span></div>", unsafe_allow_html=True)


def bar_html(rate, color):
    return f"<div class='kb-bar'><i style='width:{min(100, rate * 100):.1f}%;background:{color}'></i></div>"


def view_budget(records, budgets):
    ss = st.session_state
    st.markdown("<div class='kb-title'>予算</div>", unsafe_allow_html=True)
    month_nav("bud")
    recs = calc.in_month(records, ss.kb_month)
    used = calc.by_category(recs, EXPENSE)
    have = {b["カテゴリ"]: calc.to_int(b["予算"]) for b in budgets}
    cats = categories(EXPENSE)
    if ss.get("kb_bud_edit"):
        st.caption("1か月の予算（0 は「未設定」）")
        for ic, n in cats:
            st.number_input(f"{ic} {n}", min_value=0, step=1000, value=have.get(n, 0), key=f"bud_{n}")
        with st.container(key="kb_row_budbtn"):
            a, b = st.columns(2)
            if a.button("保存する", type="primary", use_container_width=True):
                store.save("予算", [{"カテゴリ": n, "予算": int(ss.get(f"bud_{n}") or 0)} for _, n in cats if (ss.get(f"bud_{n}") or 0) > 0])
                ss.kb_bud_edit = False
                st.rerun()
            b.button("やめる", use_container_width=True, on_click=lambda: ss.update(kb_bud_edit=False))
        return
    tb = sum(v for v in have.values() if v > 0)
    tu = sum(used.get(n, 0) for _, n in cats if have.get(n, 0) > 0)

    def row(title, budget, u, big=False):
        if budget > 0:
            left = budget - u
            right = f"<span style='color:{RED}'>{yen(-left)} オーバー</span>" if left < 0 else f"残り {yen(left)}"
            sub = f"{yen(u)} / {yen(budget)}"
            color = RED if left < 0 else (ORANGE if u / budget > 0.8 else GREEN)
            bar = bar_html(u / budget, color)
        else:
            right, sub, bar = "<span style='color:#999'>未設定</span>", (f"{yen(u)} 使用" if u else ""), bar_html(0, "#ccc")
        st.markdown(f"<div style='padding:.55rem .1rem;border-bottom:1px solid #eee'><div class='kb-row' style='border:0;padding:0'>"
                    f"<span class='l' style='font-weight:{800 if big else 600};font-size:{1.05 if big else .95}rem'>{title}</span><span class='r'>{right}</span></div>"
                    f"{bar}<div style='text-align:right;font-size:.75rem;color:#888'>{sub}</div></div>", unsafe_allow_html=True)
    row("予算合計", tb, tu, True)
    for ic, n in cats:
        row(f"{ic} {n}", have.get(n, 0), used.get(n, 0))
    st.write("")
    st.button("✏️ 予算を設定する", use_container_width=True, on_click=lambda: ss.update(kb_bud_edit=True))


def view_subs(subs):
    ss = st.session_state
    st.markdown("<div class='kb-title'>サブスク</div>", unsafe_allow_html=True)
    tot = calc.sub_totals(subs)
    st.markdown(f"<div class='kb-sum'><div><span>1か月あたり</span><b>{yen(tot['月あたり'])}</b></div><div><span>1年あたり</span><b>{yen(tot['年あたり'])}</b></div></div>", unsafe_allow_html=True)
    sub_alerts(subs)
    with st.popover("＋ サブスクを追加", use_container_width=True):
        sub_form("new", {})
    for s in sorted(subs, key=lambda x: x["次の支払日"]):
        d = calc.to_date(s["次の支払日"])
        n = (d - today()).days if d else None
        when = "" if n is None else f"{-n}日すぎています" if n < 0 else "今日" if n == 0 else f"あと{n}日"
        with st.container(border=True):
            st.markdown(f"<div class='kb-row' style='border:0;padding:0'><span class='l'><b>{s['名前']}</b>　<span style='color:#888'>{s['周期']}</span></span>"
                        f"<span class='r'>{yen(calc.to_int(s['金額']))}</span></div>"
                        f"<div style='font-size:.85rem;color:{RED if n is not None and n <= SOON_DAYS else '#666'}'>次の支払日 {s['次の支払日'].replace('-', '/')}　{when}</div>", unsafe_allow_html=True)
            with st.container(key=f"kb_row_sub_{s['ID']}"):
                a, b = st.columns(2)
                if a.button("支払った", key=f"pay_{s['ID']}", use_container_width=True, help="家計簿に記録して、次の支払日へ進めます"):
                    rec, nxt = calc.pay_sub(s, today())
                    store.append("記録", rec)
                    store.save("サブスク", [({k: nxt.get(k) for k in store.TABLES["サブスク"]} if x["ID"] == s["ID"] else x) for x in subs])
                    st.toast(f"記録しました。次は {nxt['次の支払日'].replace('-', '/')}", icon="✅")
                    st.rerun()
                with b.popover("編集", use_container_width=True):
                    sub_form(s["ID"], s)


def sub_form(sid, s):
    """サブスクの追加・編集（sid が "new" なら追加）"""
    subs = store.load("サブスク")
    cats = [n for _, n in categories(EXPENSE)]
    with st.form(f"sub_{sid}", clear_on_submit=(sid == "new")):
        name = st.text_input("名前（例：動画サービス）", value=s.get("名前", ""))
        amt = st.number_input("金額（円）", min_value=0, step=100, value=calc.to_int(s.get("金額")))
        cyc = st.selectbox("払い方", [MONTHLY, YEARLY], index=1 if s.get("周期") == YEARLY else 0)
        nd = st.date_input("次の支払日", value=calc.to_date(s.get("次の支払日")) or today(), format="YYYY/MM/DD")
        cat = st.selectbox("カテゴリ", cats, index=cats.index(s.get("カテゴリ")) if s.get("カテゴリ") in cats else (cats.index("サブスク") if "サブスク" in cats else 0))
        memo = st.text_input("メモ", value=s.get("メモ", ""))
        ok = st.form_submit_button("追加する" if sid == "new" else "保存する", type="primary", use_container_width=True)
        rm = st.form_submit_button("このサブスクを消す", use_container_width=True) if sid != "new" else False
    if ok:
        if not name or amt <= 0:
            st.error("名前と金額を入れてください")
            return
        row = {"名前": name, "金額": int(amt), "周期": cyc, "次の支払日": nd.isoformat(), "支払日の日": nd.day, "カテゴリ": cat, "メモ": memo}
        if sid == "new":
            store.append("サブスク", row)
        else:
            store.save("サブスク", [({**x, **row} if x["ID"] == sid else x) for x in subs])
        st.rerun()
    if rm:
        store.save("サブスク", [x for x in subs if x["ID"] != sid])
        st.rerun()


def view_list(records):
    st.markdown("<div class='kb-title'>記録の一覧</div>", unsafe_allow_html=True)
    month_nav("lst")
    recs = calc.in_month(records, st.session_state.kb_month)
    sum_box(calc.totals(recs))
    if not recs:
        st.info("この月の記録はまだありません")
        return
    by = {}
    for r in sorted(recs, key=lambda r: (r["日付"], r["登録日時"]), reverse=True):
        by.setdefault(r["日付"], []).append(r)
    for d, rs in by.items():
        st.markdown(f"<div class='kb-day'>{dlabel(calc.to_date(d))}</div>", unsafe_allow_html=True)
        for r in rs:
            inc = r["種類"] == INCOME
            with st.container(key=f"kb_row_rec_{r['ID']}"):
                a, b = st.columns([6, 1], vertical_alignment="center")
                a.markdown(f"<div class='kb-row'><span class='l'>{icon_of(r['種類'], r['カテゴリ'])} {r['カテゴリ']}　<span style='color:#888'>{r['メモ']}</span></span>"
                           f"<span class='r' style='color:{BLUE if inc else RED}'>{yen(calc.to_int(r['金額']) * (1 if inc else -1), True)}</span></div>", unsafe_allow_html=True)
                with b.popover("🗑"):
                    st.write("この記録を消しますか？")
                    if st.button("消す", key=f"del_{r['ID']}", type="primary"):
                        store.save("記録", [x for x in records if x["ID"] != r["ID"]])
                        st.rerun()


def view_cats():
    st.markdown("<div class='kb-title'>カテゴリー</div>", unsafe_allow_html=True)
    st.caption("1行に1つ。「絵文字 名前」の形で書くと、その絵文字がアイコンになります。上から順に並びます")
    ex = st.text_area("支出", "\n".join(f"{i} {n}" for i, n in categories(EXPENSE)), height=330)
    inc = st.text_area("収入", "\n".join(f"{i} {n}" for i, n in categories(INCOME)), height=150)
    if st.button("保存する", type="primary", use_container_width=True):
        rows = []
        for kind, text in ((EXPENSE, ex), (INCOME, inc)):
            for line in text.splitlines():
                parts = line.strip().split(maxsplit=1)
                if not parts:
                    continue
                if len(parts) == 2 and not parts[0][0].isalnum():
                    rows.append({"種類": kind, "名前": parts[1].strip(), "アイコン": parts[0]})
                else:
                    rows.append({"種類": kind, "名前": line.strip(), "アイコン": "📦"})
        store.save("カテゴリ", rows)
        st.toast("保存しました", icon="✅")
        st.rerun()


def view_settings():
    st.markdown("<div class='kb-title'>設定</div>", unsafe_allow_html=True)
    if store.using_sheets():
        st.success("保存先：Google スプレッドシート")
    else:
        st.warning("いまは試し用の保存です（アプリを再起動すると消えます）。kakeibo/README.md の手順で Google スプレッドシートにつないでください")
    st.caption(f"サブスクの知らせ：月払いは{SOON_DAYS}日前、年払いは{YEARLY_SOON_DAYS}日前から")
    if secret("KAKEIBO_PASSWORD") and st.button("ログアウト", use_container_width=True):
        st.session_state.kb_ok = False
        st.rerun()


def footer(view):
    active = view if view in [v for _, _, v in FOOT] else "home"
    st.markdown(f"<style>.st-key-kb_foot_{active} button {{ background: #ececec !important; }}"
                f".st-key-kb_foot_{active} button p, .st-key-kb_foot_{active} button [data-testid='stIconMaterial'] {{ color: {ORANGE} !important; }}</style>", unsafe_allow_html=True)
    with st.container(key="kb_foot"), st.container(key="kb_row_foot"):
        cols = st.columns(len(FOOT))
        for col, (label, icon, v) in zip(cols, FOOT):
            with col, st.container(key=f"kb_foot_{v}"):
                st.button(label, icon=icon, key=f"foot_{v}", on_click=go, args=(v,))


# =========================================================================
gate()
css()
ss = st.session_state
ss.setdefault("kb_view", "home")
ss.setdefault("kb_month", calc.ym(today()))
records = store.load("記録")
subs = store.load("サブスク")
budgets = store.load("予算")
view = ss.kb_view
if view == "input":
    view_input()
elif view == "calendar":
    view_calendar(records)
elif view == "report":
    view_report(records)
elif view == "budget":
    view_budget(records, budgets)
elif view == "subs":
    view_subs(subs)
elif view == "list":
    view_list(records)
elif view == "cats":
    view_cats()
elif view == "settings":
    view_settings()
else:
    view_home(records, subs)
footer(view)
