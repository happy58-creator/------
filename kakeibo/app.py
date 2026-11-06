"""かけいぼ（家計簿）
教材アプリの中の、メニューに出ないページ（URL の最後が /kakeibo）。パスワードは secrets の KAKEIBO_PASSWORD。
入力・一覧・グラフ・予算・サブスク・設定の6つのタブ。保存は kb_store.py、計算は kb_calc.py。"""
import hmac
import sys
import uuid
from datetime import datetime
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

DEFAULT_CATS = {
    EXPENSE: ["食費", "日用品", "住まい", "水道・光熱", "通信", "交通", "医療", "教育", "娯楽", "衣服", "交際", "サブスク", "その他"],
    INCOME: ["給与", "賞与", "副収入", "その他"],
}
SOON_DAYS = 7          # この日数以内の支払いを、上に知らせる
YEARLY_SOON_DAYS = 30  # 年払いは、早めに知らせる

st.markdown("""<style>
/* 教材アプリのメニュー（サイドバー）は、このページでは出さない */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] { display: none !important; }
.block-container { padding-top: 1.6rem; padding-bottom: 3rem; }
div[data-testid="stMetricValue"] { font-size: 1.35rem; }
.kb-month { text-align: center; font-size: 1.25rem; font-weight: 700; padding-top: .35rem; }
.kb-row { display: flex; justify-content: space-between; gap: .5rem; font-size: .95rem; }
.kb-over { color: #d33; font-weight: 700; }
</style>""", unsafe_allow_html=True)


def today():
    return datetime.now(ZoneInfo("Asia/Tokyo")).date()


def yen(n):
    return f"¥{int(round(n)):,}"


def secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return None


# ---- パスワード（secrets に KAKEIBO_PASSWORD があるときだけ） ----
def gate():
    pw = secret("KAKEIBO_PASSWORD")
    if not pw or st.session_state.get("kb_ok"):
        return
    st.title("💴 かけいぼ")
    with st.form("login"):
        v = st.text_input("パスワード", type="password")
        if st.form_submit_button("ひらく", type="primary", use_container_width=True):
            if hmac.compare_digest(v.encode(), str(pw).encode()):
                st.session_state.kb_ok = True
                st.rerun()
            st.error("パスワードがちがいます")
    st.stop()


def categories(kind):
    names = [r["名前"] for r in store.load("カテゴリ") if r["種類"] == kind and r["名前"]]
    return names or DEFAULT_CATS[kind]


gate()
records = store.load("記録")
subs = store.load("サブスク")
budgets = store.load("予算")
if "month" not in st.session_state:
    st.session_state.month = calc.ym(today())
month = st.session_state.month
month_recs = calc.in_month(records, month)

# ---- 見出し：月を切りかえる ----
st.title("💴 かけいぼ")
c1, c2, c3 = st.columns([1, 2, 1])
if c1.button("◀ 前の月", use_container_width=True):
    st.session_state.month = calc.shift_month(month, -1); st.rerun()
c2.markdown(f"<div class='kb-month'>{month[:4]}年 {int(month[5:])}月</div>", unsafe_allow_html=True)
if c3.button("次の月 ▶", use_container_width=True):
    st.session_state.month = calc.shift_month(month, 1); st.rerun()

# ---- もうすぐのサブスクの支払い（年払いは早めに） ----
for s in calc.upcoming(subs, today(), YEARLY_SOON_DAYS):
    n, yearly = s["あと何日"], s["周期"] == YEARLY
    if n > SOON_DAYS and not yearly:
        continue
    when = f"{-n}日すぎています" if n < 0 else "今日" if n == 0 else f"あと{n}日"
    st.warning(f"🔁 {'【年払い】' if yearly else ''}{s['名前']}　{yen(calc.to_int(s['金額']))}　{s['次の支払日']}（{when}）")

t = calc.totals(month_recs)
m1, m2, m3 = st.columns(3)
m1.metric("収入", yen(t["収入"]))
m2.metric("支出", yen(t["支出"]))
m3.metric("収支", yen(t["収支"]))

tab_in, tab_list, tab_chart, tab_budget, tab_sub, tab_set = st.tabs(["✏️ 入力", "📋 一覧", "📊 グラフ", "🎯 予算", "🔁 サブスク", "⚙️ 設定"])

# ---- 入力 ----
with tab_in:
    kind = st.radio("種類", [EXPENSE, INCOME], horizontal=True, key="in_kind")
    with st.form("entry", clear_on_submit=True):
        d = st.date_input("日付", value=today(), format="YYYY/MM/DD")
        amount = st.number_input("金額（円）", min_value=0, step=100, value=0)
        cat = st.selectbox("カテゴリ", categories(kind))
        memo = st.text_input("メモ（なくてもOK）")
        sent = st.form_submit_button("記録する", type="primary", use_container_width=True)
    if sent:
        if amount <= 0:
            st.error("金額を入れてください")
        else:
            store.append("記録", {"日付": d.isoformat(), "種類": kind, "金額": int(amount), "カテゴリ": cat, "メモ": memo})
            st.toast(f"記録しました：{cat} {yen(amount)}", icon="✅")
            st.rerun()
    recent = sorted(records, key=lambda r: (r["日付"], r["登録日時"]), reverse=True)[:5]
    if recent:
        st.caption("さいきんの記録")
        for r in recent:
            sign = "+" if r["種類"] == INCOME else "-"
            st.markdown(f"<div class='kb-row'><span>{r['日付'][5:].replace('-', '/')}　{r['カテゴリ']}　{r['メモ']}</span><span>{sign}{yen(calc.to_int(r['金額']))}</span></div>", unsafe_allow_html=True)

# ---- 一覧 ----
with tab_list:
    if not month_recs:
        st.info("この月の記録はまだありません")
    else:
        rows = sorted(month_recs, key=lambda r: (r["日付"], r["登録日時"]), reverse=True)
        df = pd.DataFrame([{"日付": r["日付"][5:].replace("-", "/"), "種類": r["種類"], "カテゴリ": r["カテゴリ"],
                            "金額": ("+" if r["種類"] == INCOME else "-") + yen(calc.to_int(r["金額"])), "メモ": r["メモ"]} for r in rows])
        st.dataframe(df, hide_index=True, use_container_width=True)
        with st.expander("記録を消す"):
            labels = {r["ID"]: f"{r['日付']}　{r['カテゴリ']}　{yen(calc.to_int(r['金額']))}　{r['メモ']}" for r in rows}
            pick = st.selectbox("消す記録", list(labels), format_func=lambda i: labels[i])
            if st.button("この記録を消す", type="secondary"):
                store.save("記録", [r for r in records if r["ID"] != pick])
                st.toast("消しました", icon="🗑️")
                st.rerun()

# ---- グラフ ----
with tab_chart:
    cats = calc.by_category(month_recs, EXPENSE)
    st.subheader("この月の支出の内わけ")
    if not cats:
        st.info("この月の支出はまだありません")
    else:
        dfc = pd.DataFrame({"カテゴリ": list(cats), "金額": list(cats.values())})
        try:
            import altair as alt
            pie = alt.Chart(dfc).mark_arc(innerRadius=55).encode(
                theta=alt.Theta("金額:Q"), color=alt.Color("カテゴリ:N", sort=list(cats), legend=alt.Legend(title=None)),
                tooltip=["カテゴリ", alt.Tooltip("金額:Q", format=",")])
            st.altair_chart(pie, use_container_width=True)
        except ImportError:
            st.bar_chart(dfc.set_index("カテゴリ"))
        total = sum(cats.values())
        for c, v in cats.items():
            st.markdown(f"<div class='kb-row'><span>{c}</span><span>{yen(v)}（{v / total:.0%}）</span></div>", unsafe_allow_html=True)
    st.subheader("この1年の収入と支出")
    dft = pd.DataFrame(calc.trend(records, month, 12)).set_index("月")
    st.bar_chart(dft, stack=False, color=["#3c9a5f", "#d9534f"])

# ---- 予算 ----
with tab_budget:
    status = calc.budget_status(month_recs, budgets)
    if not status:
        st.info("予算はまだありません。下の表で、カテゴリごとの1か月の予算を入れてください")
    else:
        tb, tu = sum(s["予算"] for s in status), sum(s["使った"] for s in status)
        st.markdown(f"**予算の合計 {yen(tb)} のうち {yen(tu)} 使用（残り {yen(tb - tu)}）**")
        for s in status:
            over = s["残り"] < 0
            left = f"<span class='kb-over'>⚠ {yen(-s['残り'])} オーバー</span>" if over else f"残り {yen(s['残り'])}"
            st.markdown(f"<div class='kb-row'><span>{s['カテゴリ']}　{yen(s['使った'])} / {yen(s['予算'])}</span><span>{left}</span></div>", unsafe_allow_html=True)
            st.progress(min(1.0, s["割合"]))
    with st.expander("予算を決める", expanded=not status):
        have = {b["カテゴリ"]: calc.to_int(b["予算"]) for b in budgets}
        dfb = pd.DataFrame([{"カテゴリ": c, "予算": have.get(c, 0)} for c in categories(EXPENSE)])
        edited = st.data_editor(dfb, hide_index=True, use_container_width=True, disabled=["カテゴリ"],
                                column_config={"予算": st.column_config.NumberColumn("1か月の予算（円）", min_value=0, step=1000)}, key="budget_editor")
        if st.button("予算を保存", type="primary"):
            store.save("予算", [{"カテゴリ": r["カテゴリ"], "予算": calc.to_int(r["予算"])} for r in edited.to_dict("records") if calc.to_int(r["予算"]) > 0])
            st.toast("保存しました", icon="✅")
            st.rerun()

# ---- サブスク ----
with tab_sub:
    st_tot = calc.sub_totals(subs)
    a1, a2 = st.columns(2)
    a1.metric("1か月あたり", yen(st_tot["月あたり"]))
    a2.metric("1年あたり", yen(st_tot["年あたり"]))
    soon = calc.upcoming(subs, today(), 31)
    if soon:
        st.subheader("近いうちの支払い")
        for s in soon:
            n = s["あと何日"]
            when = f"{-n}日すぎています" if n < 0 else "今日" if n == 0 else f"あと{n}日"
            with st.container(border=True):
                st.markdown(f"**{s['名前']}**　{yen(calc.to_int(s['金額']))}（{s['周期']}）<br>{s['次の支払日'].replace('-', '/')}　{when}", unsafe_allow_html=True)
                if st.button("支払った（家計簿に記録して、次の支払日へ）", key=f"pay_{s['ID']}", use_container_width=True):
                    rec, nxt = calc.pay_sub(s, today())
                    store.append("記録", rec)
                    store.save("サブスク", [({k: nxt.get(k) for k in store.TABLES["サブスク"]} if x["ID"] == s["ID"] else x) for x in subs])
                    st.toast(f"記録しました。次は {nxt['次の支払日']}", icon="✅")
                    st.rerun()
    with st.expander("サブスクを追加する", expanded=not subs):
        with st.form("sub_add", clear_on_submit=True):
            name = st.text_input("名前（例：動画サービス）")
            c1, c2 = st.columns(2)
            amt = c1.number_input("金額（円）", min_value=0, step=100, value=0)
            cyc = c2.radio("払い方", [MONTHLY, YEARLY], horizontal=True)
            nd = st.date_input("次の支払日", value=today(), format="YYYY/MM/DD")
            scat = st.selectbox("カテゴリ", categories(EXPENSE), index=categories(EXPENSE).index("サブスク") if "サブスク" in categories(EXPENSE) else 0)
            smemo = st.text_input("メモ（なくてもOK）")
            if st.form_submit_button("追加する", type="primary", use_container_width=True):
                if not name or amt <= 0:
                    st.error("名前と金額を入れてください")
                else:
                    store.append("サブスク", {"名前": name, "金額": int(amt), "周期": cyc, "次の支払日": nd.isoformat(), "支払日の日": nd.day, "カテゴリ": scat, "メモ": smemo})
                    st.toast("追加しました", icon="✅")
                    st.rerun()
    if subs:
        st.subheader("登録しているサブスク")
        st.caption("表の中で直して「保存」。行の左はしの □ を選んで 🗑 で消せます")
        dfs = pd.DataFrame([{**s, "金額": calc.to_int(s["金額"]), "次の支払日": calc.to_date(s["次の支払日"])} for s in subs])
        es = st.data_editor(dfs, hide_index=True, use_container_width=True, num_rows="dynamic", key="sub_editor",
                            column_order=["名前", "金額", "周期", "次の支払日", "カテゴリ", "メモ"],
                            column_config={"金額": st.column_config.NumberColumn("金額", min_value=0, step=100),
                                           "周期": st.column_config.SelectboxColumn("払い方", options=[MONTHLY, YEARLY], required=True),
                                           "次の支払日": st.column_config.DateColumn("次の支払日", format="YYYY/MM/DD"),
                                           "カテゴリ": st.column_config.SelectboxColumn("カテゴリ", options=categories(EXPENSE))})
        if st.button("サブスクの表を保存", type="primary"):
            out = []
            for r in es.to_dict("records"):
                if not r.get("名前"):
                    continue
                d = calc.to_date(r.get("次の支払日")) or today()
                old_day = calc.to_int(r.get("支払日の日"))
                out.append({"ID": r.get("ID") if isinstance(r.get("ID"), str) and r.get("ID") else uuid.uuid4().hex[:10],
                            "名前": r["名前"], "金額": calc.to_int(r.get("金額")), "周期": r.get("周期") or MONTHLY,
                            "次の支払日": d.isoformat(), "支払日の日": old_day if old_day and old_day >= d.day else d.day,
                            "カテゴリ": r.get("カテゴリ") or "サブスク", "メモ": r.get("メモ") or ""})
            store.save("サブスク", out)
            st.toast("保存しました", icon="✅")
            st.rerun()

# ---- 設定 ----
with tab_set:
    st.subheader("カテゴリ")
    st.caption("1行に1つずつ。上から順に、入力のときの選択肢に並びます")
    c1, c2 = st.columns(2)
    ex = c1.text_area("支出", "\n".join(categories(EXPENSE)), height=300)
    inc = c2.text_area("収入", "\n".join(categories(INCOME)), height=300)
    if st.button("カテゴリを保存", type="primary"):
        rows = [{"種類": EXPENSE, "名前": n.strip()} for n in ex.splitlines() if n.strip()] + \
               [{"種類": INCOME, "名前": n.strip()} for n in inc.splitlines() if n.strip()]
        store.save("カテゴリ", rows)
        st.toast("保存しました", icon="✅")
        st.rerun()
    st.divider()
    if store.using_sheets():
        st.caption("保存先：Google スプレッドシート")
    else:
        st.warning("いまは試し用の保存です（アプリを再起動すると消えます）。kakeibo/README.md の手順で Google スプレッドシートにつないでください")
    if secret("KAKEIBO_PASSWORD") and st.button("ログアウト"):
        st.session_state.kb_ok = False
        st.rerun()
