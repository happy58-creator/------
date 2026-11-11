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
    ] + ([] if BAND == "小" else [
        ("🖥️", "ITパスポート",
         "本番形式の模試（100問・120分・合否判定）、分野別の解説と問題演習、用語カード。シラバス Ver.6.5 対応。",
         "itpass", "AI"),
    ])),
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

import datetime
import html as _html

import auth
import history
import pdfgen
import web_games

OPEN_LABEL = by_band("あそぶ", "ひらく", "開く")
ss = st.session_state

# ---- 下のメニュー（学習・ゲーム・カレンダー・記録・設定） ----
TABS = [("study", by_band("べんきょう", "学習")), ("game", "ゲーム"), ("calendar", "カレンダー"), ("record", by_band("きろく", "記録")), ("settings", by_band("せってい", "設定"))]
TAB_KEYS = [k for k, _ in TABS]
ss.setdefault("home_tab", "study")
foot = web_games.home_footer("home_foot", tab=ss.home_tab, tabs=[{"key": k, "label": label} for k, label in TABS])
if isinstance(foot, dict) and foot.get("tab") in TAB_KEYS and foot.get("nonce") != ss.get("home_foot_nonce"):
    ss.home_foot_nonce = foot["nonce"]
    if foot["tab"] != ss.home_tab:
        ss.home_tab = foot["tab"]
        st.rerun()
tab = ss.home_tab

# 下のメニューを画面の下に固定（iframe）。中身が下のメニューに隠れないよう、下をあける
st.markdown("""<style>
iframe[title*="home_footer"] { position: fixed !important; left: 0 !important; right: 0 !important; bottom: 0 !important; width: 100vw !important;
  z-index: 99990 !important; border: 0 !important; background: transparent !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding-bottom: 120px !important; }
.home-day { background: #fff; border: 1px solid rgba(84,43,105,.12); border-radius: 14px; padding: 10px 14px; margin: 6px 0; }
.home-day b { color: #542b69; } .home-day small { color: #8a7f92; }
.home-day .sc { float: right; font-weight: 900; color: #7b3fa1; font-size: 1.1rem; }
</style>""", unsafe_allow_html=True)

TITLES = {
    "study": by_band(("📚 べんきょう", "やりたい べんきょうを えらんでね！"), ("📚 学習", "学習したい教材を選ぼう。"), ("📚 学習", "学習したい教材を選んでください。")),
    "game": by_band(("🎮 ゲーム", "あそびたい ゲームを えらんでね！"), ("🎮 ゲーム", "遊びたいゲームを選ぼう。"), ("🎮 ゲーム", "遊びたいゲームを選んでください。")),
    "calendar": by_band(("📅 カレンダー", "いつ なにを べんきょうしたか 見られるよ。"), ("📅 カレンダー", "いつ・何を学習したかを確認しよう。"), ("📅 カレンダー", "いつ・何を学習したかを確認できます。")),
    "record": by_band(("📒 きろく", "これまでの 点数を 見よう！"), ("📒 記録", "これまでの成績を振り返ろう。"), ("📒 記録", "これまでの成績を確認できます。")),
    "settings": by_band(("⚙️ せってい", ""), ("⚙️ 設定", ""), ("⚙️ 設定", "")),
}
common.hero(*TITLES[tab])


def cards(items):
    """教材・ゲームのカード（2列）"""
    for row_start in range(0, len(items), 2):
        cols = st.columns(2)
        for col, (emoji, title, desc, page, tag) in zip(cols, items[row_start:row_start + 2]):
            with col, st.container(key=f"appcard-{page}"):
                tag_html = f"<span class='tag ai'>🤖 {by_band('AIつき', 'AI搭載')}</span>" if tag == "AI" else ""
                st.markdown(f"<div class='topic-card'>{tag_html}<div class='emoji'>{emoji}</div><h3>{title}</h3><p>{desc}</p></div>",
                            unsafe_allow_html=True)
                if page in common.PAGES:
                    st.page_link(common.PAGES[page], label=OPEN_LABEL, icon="▶️", use_container_width=True)


# ---- カレンダー：だれが・いつ・何をして・何点だったか ----
SKIP_SHEETS = {"ログイン", "入力チェック"}


def subject_name(sheet):
    return {"計算": by_band("算数", "数学"), "ITパスポート": "ITパス", "学習": by_band("まなぶ", "学習"), "連打": "連打",
            "プログラミング": "プログラミング", "タイピング": "タイピング"}.get(sheet, sheet)


def what_text(sheet, r):
    """何をしたか（くわしく）"""
    pick = lambda *cols: "・".join(str(r.get(c)) for c in cols if str(r.get(c) or "").strip())
    detail = {
        "計算": pick("コース"), "国語": pick("科目", "テーマ"), "漢字": (f"{r.get('学年')}年生・" if r.get("学年") else "") + pick("モード"),
        "タイピング": pick("種類", "テーマ"), "プログラミング": pick("言語", "テーマ"), "英語": pick("コース", "テーマ"),
        "連打": (f"{r.get('コース秒数')}秒" if r.get("コース秒数") else ""), "チェス": pick("あそびかた", "難易度"),
        "ストーリー": pick("キャラ", "難易度"), "ITパスポート": pick("内容"), "学習": pick("教科", "単元名"),
    }.get(sheet, "")
    return subject_name(sheet) + (f"（{detail}）" if detail else "")


def score_text(sheet, r):
    v = lambda c: str(r.get(c) if r.get(c) is not None else "").strip()
    if sheet == "連打":
        return f"{v('回数')}回" if v("回数") else ""
    if sheet in ("チェス", "ストーリー"):
        return v("結果")
    if sheet == "ITパスポート":
        return f"{v('点数')}点" if v("点数") else (f"{v('正解数')}/{v('問題数')}問" if v("問題数") else "")
    if sheet == "学習":
        return ""
    return f"{v('点数')}点" if v("点数") else ""


@st.cache_data(ttl=300, show_spinner=False)
def all_records():
    """全部の教材の記録（5分ごとに読みなおす。スプレッドシートへの問い合わせをへらす）"""
    out = []
    for sheet in history.SHEETS:
        if sheet in SKIP_SHEETS:
            continue
        try:
            rows = history.read_history(sheet)
        except Exception:
            rows = []
        for r in rows:
            when = to_japan(str(r.get("日時") or ""))
            if when:
                out.append({**{k: ("" if v is None else v) for k, v in r.items()}, "_sheet": sheet, "_when": when})
    return out


def to_japan(when):
    """記録の日時は、サーバーの時計（Streamlit Cloud は世界標準時）で書かれている。日本の時刻になおす"""
    import time
    try:
        dt = datetime.datetime.strptime(when[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            dt = datetime.datetime.strptime(when[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            return ""
    shift = 9 * 3600 - time.localtime().tm_gmtoff        # サーバーが日本時間なら 0
    return (dt + datetime.timedelta(seconds=shift)).strftime("%Y-%m-%d %H:%M:%S")


def calendar_tab():
    admin = auth.is_admin()
    me = ss.get("player_name") or ""
    with st.spinner(by_band("きろくを よんでいるよ…", "記録を読みこんでいます…")):
        recs = [r for r in all_records() if admin or str(r.get("名前")) == me]
    from zoneinfo import ZoneInfo
    today = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).date()
    ss.setdefault("cal_ym", today.strftime("%Y-%m"))
    ss.setdefault("cal_sel", today.isoformat())
    ym = ss.cal_ym
    days = {}
    for r in recs:
        if r["_when"].startswith(ym):
            days.setdefault(r["_when"][:10], []).append({"t": subject_name(r["_sheet"]), "n": str(r.get("名前") or "")})
    val = web_games.home_calendar("home_cal", ym=ym, days=days, admin=admin, sel=ss.cal_sel, today=today.isoformat())
    if isinstance(val, dict) and val.get("nonce") and val["nonce"] != ss.get("cal_nonce"):
        ss.cal_nonce = val["nonce"]
        if val.get("type") == "month" and val.get("ym"):
            ss.cal_ym = val["ym"]
            st.rerun()
        if val.get("type") == "day" and val.get("date"):
            ss.cal_sel = val["date"]
            st.rerun()

    sel = ss.cal_sel
    items = sorted([r for r in recs if r["_when"].startswith(sel)], key=lambda r: r["_when"])
    y, m, d = (int(x) for x in sel.split("-"))
    st.subheader(f"{m}月{d}日" + by_band(" の きろく", "の記録"))
    if not items:
        st.caption(by_band("この日の きろくは ないよ。", "この日の記録はありません。"))
    for k, r in enumerate(items):
        t = r["_when"][11:16]
        who = f"{_html.escape(str(r.get('名前')))}　" if admin else ""
        score = score_text(r["_sheet"], r)
        st.markdown(f"<div class='home-day'><span class='sc'>{_html.escape(score)}</span><small>{m}月{d}日 {t}</small><br>"
                    f"{who}<b>{_html.escape(what_text(r['_sheet'], r))}</b></div>", unsafe_allow_html=True)
        if str(r.get("詳細") or "").strip():
            pdf = pdfgen.pdf_from_history(r)
            if pdf is not None:
                import base64
                data = base64.b64encode(pdf).decode("ascii")
                st.html(f'<button type="button" class="pdf-open" data-pdf="{data}">📄 PDFを見る</button>', unsafe_allow_javascript=True)
    if admin:
        st.caption("管理者なので、みんなの記録を表示しています。")


def settings_tab():
    name = ss.get("auth_name") or ss.get("player_name") or ""
    with st.container(border=True):
        st.markdown(f"👤 **{name}**" + ("（ゲスト）" if ss.get("auth_guest") else "") + by_band(" さん", " さん")
                    + ("　🛡️管理者" if auth.is_admin() else ""))
        if ss.get("auth_age") is not None:
            st.caption(f"年齢：{ss.get('auth_age')}さい" if BAND == "小" else f"年齢：{ss.get('auth_age')}歳")
        if st.button(by_band("ログアウト", "ログアウト"), key="home_logout", use_container_width=True):
            auth.logout()
            st.rerun()
    st.caption(by_band("左のメニューからも 好きなページに いけるよ。", "左のメニューからも各ページに移動できます。")
               + " AI" + by_band("つき", "搭載") + "のページを使うには GEMINI_API_KEY の設定が必要です。")


SECTION = {"study": APPS[0][1], "game": APPS[1][1], "record": APPS[2][1]}
if tab in SECTION:
    cards(SECTION[tab])
elif tab == "calendar":
    calendar_tab()
else:
    settings_tab()

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
