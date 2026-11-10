"""買い物リスト
教材アプリの中の、メニューに出ないページ（URL の最後が /kaimono）。家計簿と同じパスワード・同じログイン。
画面はぜんぶ JavaScript（ui/ の Vue）。Python は「データを渡す」「操作を受けとって保存する」だけ（家計簿と同じしくみ）。
保存は家計簿の kb_store.py（同じ Google スプレッドシートの「買い物」「店舗」「買い物ジャンル」シート）。"""
import sys
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                       # km_ui
sys.path.insert(0, str(HERE.parent / "kakeibo"))    # 家計簿の kb_store・kb_auth を使う
import kb_store as store  # noqa: E402
if "購入記録" not in getattr(store, "TABLES", {}):     # 更新のあと、前の版の kb_store がメモリに残っていたら読み直す
    import importlib
    store = importlib.reload(store)
import kb_auth as auth  # noqa: E402
from km_ui import ui  # noqa: E402

try:
    st.set_page_config(page_title="買い物リスト", page_icon="🛒", layout="wide", initial_sidebar_state="collapsed")
except Exception:
    pass

# はじめから入れておくジャンル（名前・アイコン）
DEFAULT_GENRES = [("肉", "meat"), ("野菜", "carrot"), ("魚", "fish"), ("果物", "apple"), ("卵・乳製品", "egg"), ("豆腐・納豆", "tofu"), ("米・麺", "rice"),
                  ("パン", "bread"), ("ラーメン", "bowl"), ("調味料", "bottle"), ("冷凍", "snow"), ("お菓子", "candy"), ("ジュース", "juice"),
                  ("お酒", "beer"), ("日用品", "daily"), ("その他", "box")]
TABLES = ("買い物", "店舗", "買い物ジャンル", "買い物の記憶", "購入記録")


def genres():
    rows = store.load("買い物ジャンル")
    return rows or [{"名前": n, "アイコン": "i:" + i, "並び": str(k)} for k, (n, i) in enumerate(DEFAULT_GENRES)]


# =========================================================================
auth.gate(ui, "買い物リスト", "kaimono_ui")
st.markdown(auth.hide_css("kaimono_ui"), unsafe_allow_html=True)
auth.hide_badges()
ss = st.session_state
done = ss.setdefault("kb_done", [])
data = {"items": store.load("買い物"), "stores": store.load("店舗"), "genres": genres(), "memory": store.load("買い物の記憶"), "history": store.load("購入記録"),
        "sheets": store.using_sheets(), "password": bool(auth.secret("KAKEIBO_PASSWORD"))}
val = ui(data=data, done=done[-200:], token=ss.get("kb_token") or "", key="km_ui", default=None)
if isinstance(val, dict):
    changed = False
    for a in val.get("queue") or []:
        if a.get("id") in done:
            continue
        try:
            if a.get("type") == "save_table" and a.get("table") in TABLES:      # 表ごと書きかえる
                store.save(a["table"], [{c: r.get(c, "") for c in store.TABLES[a["table"]]} for r in a.get("rows") or []])
        except Exception as e:      # 保存できなかったときは、画面の上に知らせる（操作は捨てない）
            st.toast(f"保存できませんでした：{e}", icon="⚠️")
            break
        done.append(a["id"])
        changed = True
    if val.get("logout") and val["logout"] not in done:
        done.append(val["logout"])
        auth.logout()
        changed = True
    if val.get("go") and val.get("gid") not in done:      # 家計簿へ（同じアプリの中のページ）
        done.append(val.get("gid"))
        st.switch_page("kakeibo/app.py")
    if changed:
        st.rerun()
