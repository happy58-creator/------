import streamlit as st

import common

common.setup_page("きょうざい・ゲームひろば", "🏠", home_link=False)

APPS = [
    ("べんきょう", [
        ("🧮", "計算マスター", "足し算・引き算・掛け算・割り算を25問チャレンジ。賞状PDFもできるよ！",
         "calc", ""),
        ("🧙‍♂️", "AI国語アドベンチャー", "好きな言葉からAIがお話とクイズを作ってくれる！",
         "kokugo", "AI"),
        ("⌨️", "AIタイピング", "1キーずつ判定する本格タイピング。5分以内なら ロボットを動かすプログラミングも！",
         "typing", "AI"),
        ("🔤", "AI英語チャレンジ", "単語コースと文コース。小1から大人まで、年れいに合わせた問題！",
         "english", "AI"),
        ("💻", "AIプログラミング教室", "Python・JavaScriptなどを、単語→文法→書いてみよう→クイズで学ぼう！",
         "programming", "AI"),
    ]),
    ("ゲーム", [
        ("⚡", "限界突破！連打ゲーム", "制限時間内にどれだけ連打できるかな？",
         "rapid", ""),
        ("✊", "じゃんけんゲーム", "コンピューターと勝負、または2人でたいせん！",
         "janken", ""),
        ("🎉", "くじ引き・じゅんばん決め", "あみだ風のドキドキ演出で決めよう。",
         "lottery", ""),
        ("♟️", "チェス", "駒をクリック・ドラッグで動かせる本格チェス。CPUは4段階、ヒントつき！",
         "chess", ""),
    ]),
    ("きろく", [
        ("📒", "せいせきの履歴", "これまでの点数やタイムを名前ごとに見られるよ。",
         "history", ""),
    ]),
]

common.hero("🏠 きょうざい・ゲームひろば", "あそびたいものを えらんでね！")

card_no = 0
for section, items in APPS:
    st.subheader(section)
    for row_start in range(0, len(items), 2):
        cols = st.columns(2)
        for col, (emoji, title, desc, page, tag) in zip(cols, items[row_start:row_start + 2]):
            with col, st.container(key=f"appcard-{card_no}"):
                card_no += 1
                tag_html = "<span class='tag ai'>🤖 AIつき</span>" if tag == "AI" else ""
                st.markdown(
                    f"<div class='topic-card'>{tag_html}<div class='emoji'>{emoji}</div>"
                    f"<h3>{title}</h3><p>{desc}</p></div>",
                    unsafe_allow_html=True,
                )
                st.page_link(common.PAGES[page], label="あそぶ", icon="▶️", use_container_width=True)

# カードのどこをクリックしても、中の「あそぶ」リンクを押したことにする（CSSだけだと環境によって効かないため）
st.html(
    """<script>
    (() => {
      const w = window;
      if (w.__kyouzaiCardClick) return;  // 登録は1回だけ
      w.__kyouzaiCardClick = true;
      document.addEventListener("click", (e) => {
        const card = e.target.closest('[class*="st-key-appcard-"]');
        if (!card || e.target.closest("a")) return;
        const link = card.querySelector('a[data-testid="stPageLink-NavLink"]') || card.querySelector("a");
        if (link) link.click();
      });
    })();
    </script>""",
    unsafe_allow_javascript=True,
)

st.divider()
st.caption("左のメニューからも好きなページに移動できるよ。AIつきのページを使うには GEMINI_API_KEY の設定が必要です。")
