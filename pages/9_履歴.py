import pandas as pd
import streamlit as st

import auth
import common
import history
import pdfgen

common.setup_page("せいせきの履歴", "📒")
common.hero("📒 せいせきの履歴", "これまでの記録を見よう！")

st.caption(f"保存先：{history.storage_label()}")

ADMIN_ONLY = {"ログイン", "入力チェック"}   # ログインの記録・ふざけた入力の記録は管理者だけ
sheet_names = [s for s in history.SHEETS if s not in ADMIN_ONLY or auth.is_admin()]
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

shown = df.drop(columns=["詳細"], errors="ignore")
st.dataframe(shown.iloc[::-1], use_container_width=True, hide_index=True)

# --- そのときの問題・答え・点数を、結果PDFと同じ形で出す ---
if "詳細" in df.columns:
    st.subheader("📄 そのときの結果をPDFで見る")
    records = [r for r in df.iloc[::-1].to_dict("records") if str(r.get("詳細") or "").strip()]
    if not records:
        st.caption("PDFにできる記録は、まだありません（詳細つきで記録されたものだけ出せます）。")
    else:
        def label(r):
            extra = r.get("言語") or r.get("コース") or r.get("種類") or ""
            return f"{r['日時']}　{r['名前']}　{r.get('点数', '')}点　{extra}"

        picked = st.selectbox("どの回の結果？（新しい順）", range(len(records)), format_func=lambda i: label(records[i]))
        pdf = pdfgen.pdf_from_history(records[picked])
        if pdf is None:
            st.warning("この記録は詳細が読みこめませんでした。")
        else:
            common.pdf_preview_button(
                pdf,
            )

st.download_button(
    "📥 CSVでダウンロード", shown.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"履歴_{sheet}.csv", mime="text/csv",
)
