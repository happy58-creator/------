import streamlit as st

import common

common.setup_page("きょうざい・ゲームひろば", "🏠", home_link=False)

BAND = common.age_band()   # "小"（小学生・年齢がわからない）/ "中"（中学生）/ "高"（高校生以上・管理者）


def by_band(small, middle=None, high=None):
    """年齢に合わせた表記をえらぶ（中・高を省くと、ひとつ下と同じ）"""
    middle = middle or small
    return {"小": small, "中": middle, "高": high or middle}[BAND]


APPS = [
    (by_band("べんきょう", "学習"), [
        ("🧮", by_band("算数マスター", "数学マスター"),
         by_band("学年に合わせた 算数の10問チャレンジ。とき方つき・賞状PDFもできるよ！",
                 "方程式・関数・確率など、中学数学を単元ごとに10問チャレンジ。解き方つき。",
                 "数学I・A・II・B・C・IIIを単元ごとに10問演習。答えの形（約分・有理化など）まで判定、解き方つき。"),
         "calc", ""),
        ("🧙‍♂️", by_band("AI国語アドベンチャー", "AI国語"),
         by_band("すきな言葉から AIがお話と問題を作ってくれる！ 漢字の読み書きと読解に挑戦しよう。",
                 "テーマに合わせてAIが文章と問題を作成。「現代文中心」と「古典中心」から選べるよ。",
                 "現代の国語・言語文化・論理国語・文学国語・国語表現・古典探究から選んで演習。古典は原文を収録。"),
         "kokugo", "AI"),
        ("✍️", by_band("漢字のかきとり", "漢字の書き取り"),
         by_band("指やペンで書いて、書き順・形をチェック！ タブレットやスマホでも使えるよ。",
                 "指やペンで書いて、筆順と字形をチェック。タブレット・スマホにも対応。"),
         "kanji", ""),
        ("⌨️", "AIタイピング",
         by_band("1キーずつ判定する本格タイピング。5分以内なら ロボットを動かすプログラミングも！",
                 "1キーずつ判定する本格タイピング。5分以内にクリアすると、ロボット操作のプログラミングにも挑戦できる。"),
         "typing", "AI"),
        ("🔤", by_band("AI英語チャレンジ", "AI英語"),
         by_band("単語コースと文コース。年れいに合わせた問題が出るよ！",
                 "単語コースと文コース。学年に合わせた問題をAIが作成。",
                 "単語コースと文コース。レベルに合わせた問題をAIが作成（大人まで対応）。"),
         "english", "AI"),
        ("💻", "AIプログラミング教室",
         by_band("Python・JavaScriptなどを、たんご→ぶんぽう→書いてみよう→クイズで学ぼう！",
                 "Python・JavaScriptなどを、用語 → 文法 → 実際に書く → クイズの順に学習。"),
         "programming", "AI"),
    ]),
    ("ゲーム", [
        ("⚡", "限界突破！連打ゲーム", by_band("制限時間内にどれだけ連打できるかな？", "制限時間内に何回連打できるか挑戦！"),
         "rapid", ""),
        ("⚔️", "ストーリーモード",
         by_band("敵をタップして たおそう！ 仲間・装備・アイテムを集めて ステージに挑戦。",
                 "敵をタップして倒すバトル。仲間・装備・アイテムを集めて、高難度ステージに挑戦。"),
         "story", ""),
        ("✊", "じゃんけんゲーム", by_band("コンピューターと勝負、または2人でたいせん！", "コンピューターと勝負、または2人で対戦。"),
         "janken", ""),
        ("🎉", by_band("くじ引き・じゅんばん決め", "くじ引き・順番決め"),
         by_band("あみだ風のドキドキ演出で決めよう。", "あみだ風の演出で、くじ引きや順番を決められる。"),
         "lottery", ""),
        ("♟️", "チェス", by_band("駒をクリック・ドラッグで動かせる本格チェス。CPUは4段階、ヒントつき！",
                                 "クリック・ドラッグで操作する本格チェス。CPUは4段階、ヒントつき。"),
         "chess", ""),
    ]),
    (by_band("きろく", "記録"), [
        ("📒", by_band("せいせきの履歴", "成績の履歴"),
         by_band("これまでの点数やタイムを 名前ごとに見られるよ。", "これまでの点数やタイムを振り返ろう。", "これまでの点数やタイムを確認できます。"),
         "history", ""),
    ]),
]

common.hero(*by_band(("🏠 きょうざい・ゲームひろば", "あそびたいものを えらんでね！"),
                     ("🏠 教材・ゲーム広場", "学習したい教材や、遊びたいゲームを選ぼう。"),
                     ("🏠 教材・ゲーム広場", "学習したい教材やゲームを選んでください。")))
OPEN_LABEL = by_band("あそぶ", "ひらく", "開く")

card_no = 0
for section, items in APPS:
    st.subheader(section)
    for row_start in range(0, len(items), 2):
        cols = st.columns(2)
        for col, (emoji, title, desc, page, tag) in zip(cols, items[row_start:row_start + 2]):
            with col, st.container(key=f"appcard-{card_no}"):
                card_no += 1
                tag_html = f"<span class='tag ai'>🤖 {by_band('AIつき', 'AI搭載')}</span>" if tag == "AI" else ""
                st.markdown(
                    f"<div class='topic-card'>{tag_html}<div class='emoji'>{emoji}</div>"
                    f"<h3>{title}</h3><p>{desc}</p></div>",
                    unsafe_allow_html=True,
                )
                if page in common.PAGES:
                    st.page_link(common.PAGES[page], label=OPEN_LABEL, icon="▶️", use_container_width=True)

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
st.caption(by_band("左のメニューからも好きなページに移動できるよ。AIつきのページを使うには GEMINI_API_KEY の設定が必要です。",
                   "左のメニューからも各ページに移動できます。AI搭載のページを使うには GEMINI_API_KEY の設定が必要です。"))
