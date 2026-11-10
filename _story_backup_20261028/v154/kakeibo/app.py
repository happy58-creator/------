"""かけいぼ（家計簿）
教材アプリの中の、メニューに出ないページ（URL の最後が /kakeibo）。パスワードは secrets の KAKEIBO_PASSWORD。
画面はぜんぶ JavaScript（ui/index.html）。Python は「データを渡す」「操作を受けとって保存する」だけ。
  ・Python → 画面：記録・予算・カテゴリ・積立（args の data）と、保存が終わった操作の ID（done）
  ・画面 → Python：まだ保存されていない操作の列（queue）。同じ操作を2回保存しないよう ID で見分ける
保存は kb_store.py（Google スプレッドシート）、計算は kb_calc.py。"""
import sys
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))      # このフォルダの kb_calc・kb_store を読む
import kb_calc as calc  # noqa: E402
import kb_store as store  # noqa: E402
if "買い物" not in getattr(store, "TABLES", {}) or not hasattr(store, "_memo"):     # 更新のあと、前の版の kb_store がメモリに残っていたら読み直す
    import importlib
    store = importlib.reload(store)
from kb_ui import ui  # noqa: E402
import kb_auth as auth  # noqa: E402       # ログイン（買い物リストと共通）
from kb_calc import EXPENSE, INCOME  # noqa: E402

try:
    st.set_page_config(page_title="家計簿", page_icon="💴", layout="wide", initial_sidebar_state="collapsed")
except Exception:
    pass

DEFAULT_CATS = {
    EXPENSE: [("🍽️", "食費"), ("🧴", "日用品"), ("👕", "衣服"), ("💄", "美容"), ("🥂", "交際費"), ("💊", "医療費"),
              ("📝", "教育費"), ("💡", "光熱費"), ("🚃", "交通費"), ("📱", "通信費"), ("🏠", "住居費"), ("🔁", "サブスク"), ("📦", "その他")],
    INCOME: [("💴", "給与"), ("🎁", "賞与"), ("💼", "副収入"), ("📦", "その他")],
}

def categories():
    rows = [{"種類": r["種類"], "名前": r["名前"], "アイコン": r.get("アイコン") or "📦"} for r in store.load("カテゴリ") if r["名前"]]
    for kind, defaults in DEFAULT_CATS.items():
        if not any(r["種類"] == kind for r in rows):
            rows += [{"種類": kind, "名前": n, "アイコン": i} for i, n in defaults]
    return rows


def pick(table, row):
    return {c: row.get(c, "") for c in store.TABLES[table]}


def apply(a):
    """画面からの操作を1つ保存する"""
    t = a.get("type")
    if t == "add_record":
        store.append("記録", pick("記録", a["rec"]))
    elif t == "delete_record":
        store.save("記録", [r for r in store.load("記録") if r["ID"] != a["rid"]])
    elif t == "save_budgets":
        store.save("予算", [{"カテゴリ": r["カテゴリ"], "予算": calc.to_int(r.get("予算")), "表示": "0" if str(r.get("表示")) == "0" else ""}
                            for r in a["rows"] if calc.to_int(r.get("予算")) > 0 or str(r.get("表示")) == "0"])
    elif t == "save_table" and a.get("table") in ("積立", "積立記録", "アイコン名"):        # 積立は表ごと書きかえる
        store.save(a["table"], [pick(a["table"], r) for r in a.get("rows") or []])
    elif t == "add_sub":
        store.append("サブスク", pick("サブスク", a["row"]))
    elif t == "update_sub":
        store.save("サブスク", [pick("サブスク", a["row"]) if s["ID"] == a["row"]["ID"] else s for s in store.load("サブスク")])
    elif t == "delete_sub":
        store.save("サブスク", [s for s in store.load("サブスク") if s["ID"] != a["sid"]])
    elif t == "pay_sub":
        subs = store.load("サブスク")
        s = next((x for x in subs if x["ID"] == a["sid"]), None)
        if s:
            today = calc.to_date(s["次の支払日"])
            rec, nxt = calc.pay_sub(s, today)
            store.append("記録", {**rec, "ID": a.get("rid", "")})
            store.save("サブスク", [pick("サブスク", nxt) if x["ID"] == s["ID"] else x for x in subs])
    elif t == "save_cats":
        store.save("カテゴリ", [{"種類": r["種類"], "名前": r["名前"], "アイコン": r.get("アイコン") or "📦"} for r in a["rows"] if r.get("名前")])


# =========================================================================
auth.gate(ui, "家計簿", "kakeibo_ui")
st.markdown(auth.hide_css("kakeibo_ui"), unsafe_allow_html=True)
auth.hide_badges()
ss = st.session_state
done = ss.setdefault("kb_done", [])
data = {
    "records": store.load("記録"), "budgets": store.load("予算"), "cats": categories(),
    "tsumi": store.load("積立"), "tlog": store.load("積立記録"), "inames": store.load("アイコン名"),
    "shopping": True,       # 買い物リスト（同じアプリの /kaimono）へのボタンを出す
    "sheets": store.using_sheets(), "password": bool(auth.secret("KAKEIBO_PASSWORD")),
}
val = ui(data=data, done=done[-200:], token=ss.get("kb_token") or "", key="kb_ui", default=None)
if isinstance(val, dict):
    changed = False
    for a in val.get("queue") or []:
        if a.get("id") in done:
            continue
        try:
            apply(a)
        except Exception as e:      # 保存できなかったときは、画面の上に知らせる（操作は捨てない）
            st.toast(f"保存できませんでした：{e}", icon="⚠️")
            break
        done.append(a["id"])
        changed = True
    if val.get("logout") and val["logout"] not in done:
        done.append(val["logout"])
        auth.logout()
        changed = True
    if val.get("go") and val.get("gid") not in done:      # 買い物リストへ（同じアプリの中のページ）
        done.append(val.get("gid"))
        st.switch_page("shopping/app.py")
    if changed:
        st.rerun()
