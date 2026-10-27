import pandas as pd
import streamlit as st

import auth
import common
import history

common.setup_page("せいせきの履歴", "📒")
common.hero("📒 せいせきの履歴", "これまでの記録を見よう！")

st.caption(f"保存先：{history.storage_label()}")

sheet_names = [s for s in history.SHEETS if s != "ログイン" or auth.is_admin()]  # ログインの記録は管理者だけ
sheet = st.radio("ゲームを選んでね", sheet_names, horizontal=True)
rows = history.read_history(sheet)
if not rows:
    st.info("まだ記録がないよ。ゲームをあそぶと、ここに残るよ！")
    st.stop()

df = pd.DataFrame(rows)
me = st.session_state.get("player_name")
if auth.is_admin():
    names = ["みんな"] + sorted(df["名前"].astype(str).unique())
    who = st.selectbox("だれの記録？（管理者はぜんいん見られます）", names)
    if who != "みんな":
        df = df[df["名前"].astype(str) == who]
else:
    st.caption(f"{me} さんの記録だけ表示しています。")
    df = df[df["名前"].astype(str) == me]
    if df.empty:
        st.info("まだ記録がないよ。ゲームをあそぶと、ここに残るよ！")
        st.stop()

c1, c2 = st.columns(2)
c1.metric("あそんだ回数", f"{len(df)} 回")
score_col = next((c for c in ("点数", "回数", "ノーミス正解") if c in df.columns), None)
if score_col:
    scores = pd.to_numeric(df[score_col], errors="coerce")
    c2.metric(f"ベスト（{score_col}）", f"{scores.max():g}" if scores.notna().any() else "—")
    if scores.notna().sum() >= 2:
        st.line_chart(pd.DataFrame({score_col: scores.values}, index=df["日時"].values))

st.dataframe(df.iloc[::-1], use_container_width=True, hide_index=True)
st.download_button(
    "📥 CSVでダウンロード", df.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"履歴_{sheet}.csv", mime="text/csv",
)
