import streamlit as st

import common

common.setup_page("きょうざい・ゲームひろば", "🏠", home_link=False)

APPS = [
    ("べんきょう", [
        ("🧮", "計算マスター", "足し算・引き算・掛け算・割り算を25問チャレンジ。賞状PDFもできるよ！",
         "pages/0_計算マスター.py", ""),
        ("🧙‍♂️", "AI国語アドベンチャー", "好きな言葉からAIがお話とクイズを作ってくれる！",
         "pages/5_国語.py", "AI"),
        ("⌨️", "AIタイピング", "テーマに合わせたタイピング問題。5分以内なら裏メニューも！",
         "pages/6_タイピング.py", "AI"),
    ]),
    ("ゲーム", [
        ("⚡", "限界突破！連打ゲーム", "制限時間内にどれだけ連打できるかな？",
         "pages/1_限界突破ゲーム.py", ""),
        ("✊", "じゃんけんゲーム", "コンピューターと勝負、または2人でたいせん！",
         "pages/2_じゃんけんゲーム.py", ""),
        ("🎉", "くじ引き・じゅんばん決め", "あみだ風のドキドキ演出で決めよう。",
         "pages/3_くじ引き・じゅんばん決めゲーム.py", ""),
        ("♟️", "チェス", "CPU戦も2人プレイもOK。むずかしさも選べるよ。",
         "pages/4_チェスVS.py", ""),
    ]),
]

common.hero("🏠 きょうざい・ゲームひろば", "あそびたいものを えらんでね！")

for section, items in APPS:
    st.subheader(section)
    for row_start in range(0, len(items), 2):
        cols = st.columns(2)
        for col, (emoji, title, desc, page, tag) in zip(cols, items[row_start:row_start + 2]):
            with col:
                tag_html = "<span class='tag ai'>🤖 AIつき</span>" if tag == "AI" else ""
                st.markdown(
                    f"<div class='topic-card'>{tag_html}<div class='emoji'>{emoji}</div>"
                    f"<h3>{title}</h3><p>{desc}</p></div>",
                    unsafe_allow_html=True,
                )
                st.page_link(page, label="あそぶ", icon="▶️", use_container_width=True)

st.divider()
st.caption("左のメニューからも好きなページに移動できるよ。AIつきのページを使うには GEMINI_API_KEY の設定が必要です。")
