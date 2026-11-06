"""かけいぼ（家計簿）
教材アプリの中の、メニューに出ないページ（URL の最後が /kakeibo）。パスワードは secrets の KAKEIBO_PASSWORD。
画面はぜんぶ JavaScript（ui/index.html）。Python は「データを渡す」「操作を受けとって保存する」だけ。
  ・Python → 画面：記録・予算・サブスク・カテゴリ（args の data）と、保存が終わった操作の ID（done）
  ・画面 → Python：まだ保存されていない操作の列（queue）。同じ操作を2回保存しないよう ID で見分ける
保存は kb_store.py（Google スプレッドシート）、計算は kb_calc.py。"""
import hmac
import sys
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))      # このフォルダの kb_calc・kb_store を読む
import kb_calc as calc  # noqa: E402
import kb_store as store  # noqa: E402
from kb_ui import ui  # noqa: E402
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

# Streamlit の飾り（上のバー・右下のアイコン・サイドバー・余白）を消して、画面いっぱいに JavaScript の画面を出す
HIDE = """<style>
header, [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"], [data-testid="stSidebarNav"],
[data-testid="manage-app-button"], [data-testid="stAppDeployButton"], #MainMenu, footer,
[class*="viewerBadge"], [class*="_profileContainer"], [class*="_profilePreview"], [class*="_container_gzau3"], [class*="stDeployButton"] { display: none !important; }
html, body, .stApp { background: #f5f6f8 !important; overflow: hidden !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: none !important; }
iframe[title*="kakeibo_ui"] { position: fixed !important; inset: 0 !important; width: 100vw !important; height: 100vh !important; height: 100dvh !important;
  border: 0 !important; z-index: 999990 !important; background: #f5f6f8; }
</style>"""


def hide_badges():
    """教材と同じ：Streamlit Cloud の王冠マーク・作った人のアカウント表示などを JavaScript で消す（common.py のものを使う）"""
    try:
        import common
        st.html(common._HIDE_CLOUD_BADGES_JS, unsafe_allow_javascript=True)
    except Exception:
        pass


def secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return None


def gate():
    """パスワード（secrets に KAKEIBO_PASSWORD があるときだけ）"""
    pw = secret("KAKEIBO_PASSWORD")
    if not pw or st.session_state.get("kb_ok"):
        return
    hide_badges()
    st.markdown(HIDE.replace("overflow: hidden !important;", "") + """<style>
    .block-container { max-width: 380px !important; padding-top: 18vh !important; padding-left: 16px !important; padding-right: 16px !important; margin: 0 auto; }
    </style><div style="text-align:center;font-size:22px;font-weight:800;margin-bottom:12px">家計簿</div>""", unsafe_allow_html=True)
    with st.form("login"):
        v = st.text_input("パスワード", type="password")
        if st.form_submit_button("ひらく", type="primary", use_container_width=True):
            if hmac.compare_digest(v.encode(), str(pw).encode()):
                st.session_state.kb_ok = True
                st.rerun()
            st.error("パスワードがちがいます")
    st.stop()


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
        store.save("予算", [{"カテゴリ": r["カテゴリ"], "予算": calc.to_int(r["予算"])} for r in a["rows"] if calc.to_int(r["予算"]) > 0])
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
gate()
st.markdown(HIDE, unsafe_allow_html=True)
hide_badges()
ss = st.session_state
done = ss.setdefault("kb_done", [])
data = {
    "records": store.load("記録"), "budgets": store.load("予算"), "subs": store.load("サブスク"), "cats": categories(),
    "sheets": store.using_sheets(), "password": bool(secret("KAKEIBO_PASSWORD")),
}
val = ui(data=data, done=done[-200:], key="kb_ui", default=None)
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
        ss.kb_ok = False
        changed = True
    if changed:
        st.rerun()
