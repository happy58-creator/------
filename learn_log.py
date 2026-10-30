"""「まなぶ」でまなんだ単元の記録（まなんだ ✓）。履歴の「学習」シートに残し、次に開いても ✓ が出る。"""
import streamlit as st

import history


def _key(subject):
    return f"learned_{subject}"


def learned(subject):
    """いまの人が まなんだ単元id の集合（最初の1回だけシートを読み、あとはセッションに置いておく）"""
    key = _key(subject)
    if key not in st.session_state:
        me = st.session_state.get("player_name") or "ななしさん"
        try:
            rows = history.read_history("学習")
        except Exception:
            rows = []
        st.session_state[key] = {str(r.get("単元")) for r in rows
                                 if str(r.get("名前")) == me and str(r.get("教科")) == subject}
    return st.session_state[key]


def mark(subject, grade, unit_id, unit_name):
    """まなんだ ✓ をつける（1つの単元は1回だけ記録する）"""
    done = learned(subject)
    if unit_id in done:
        return False
    history.log_result("学習", 教科=subject, 学年=grade, 単元=unit_id, 単元名=unit_name)
    done.add(unit_id)
    return True
