"""全ページ共通の見た目・ヘルパー。"""
import copy
import os
import unicodedata

import streamlit as st

GEMINI_MODEL = "gemini-3.6-flash"
HOME_PAGE = "home.py"

# (名前, ファイル, サイドバーの表示名, アイコン, URLの末尾)。URLは半角英数字にして、
# ファイル名の文字の形（Mac の濁点の分かれ方）に左右されないようにする。
PAGE_DEFS = [
    ("home", "home.py", "トップ", "🏠", ""),
    ("calc", "pages/0_計算マスター.py", "計算マスター", "🧮", "calc"),
    ("kokugo", "pages/5_国語.py", "AI国語", "🧙‍♂️", "kokugo"),
    ("typing", "pages/6_タイピング.py", "AIタイピング", "⌨️", "typing"),
    ("english", "pages/8_英語.py", "AI英語", "🔤", "english"),
    ("programming", "pages/9_プログラミング.py", "AIプログラミング", "💻", "programming"),
    ("rapid", "pages/1_限界突破ゲーム.py", "連打ゲーム", "⚡", "rapid"),
    ("janken", "pages/2_じゃんけんゲーム.py", "じゃんけん", "✊", "janken"),
    ("lottery", "pages/3_くじ引き・じゅんばん決めゲーム.py", "くじ引き", "🎉", "lottery"),
    ("chess", "pages/4_チェスVS.py", "チェス", "♟️", "chess"),
    ("history", "pages/7_履歴.py", "せいせきの履歴", "📒", "history"),
]
SECTIONS = {
    "": ["home"],
    "べんきょう": ["calc", "kokugo", "typing", "english", "programming"],
    "ゲーム": ["rapid", "janken", "lottery", "chess"],
    "きろく": ["history"],
}
PAGES = {}  # 名前 -> st.Page（教材.py が毎回つくる）

# Streamlit Cloud がアプリの外側の画面に出す「王冠マーク」と「作った人のアカウント表示」を消す。
# アプリと外側の画面は同じドメイン（〜.streamlit.app）なので、JavaScript から触れる。
_HIDE_CLOUD_BADGES_JS = """
<script>
(() => {
  const SELECTORS = [
    '[class*="viewerBadge"]', '[class*="profileContainer"]', '[class*="profilePreview"]',
    '[data-testid="stToolbarActions"]', '[data-testid="stMainMenu"]', '.stAppDeployButton',
  ];
  const hide = (doc) => {
    for (const sel of SELECTORS) {
      doc.querySelectorAll(sel).forEach((el) => el.style.setProperty("display", "none", "important"));
    }
  };
  const docs = [document];
  try { if (window.parent !== window) docs.push(window.parent.document); } catch (e) {}
  for (const doc of docs) {
    hide(doc);
    if (doc.defaultView.__kyouzaiBadgeObserver) continue;  // 監視は1画面に1つだけ
    let queued = false;
    const observer = new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; hide(doc); });
    });
    observer.observe(doc.body, { childList: true, subtree: true });
    doc.defaultView.__kyouzaiBadgeObserver = observer;
  }
})();
</script>
"""

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@400;700;900&display=swap');
/* アイコン（stIconMaterial）はアイコン用フォントのままにする。上書きすると「arrow_right」などの文字が出てしまう */
html, body, [class*="st-"]:not([data-testid="stIconMaterial"]), .stApp { font-family: 'Zen Maru Gothic', sans-serif; }
.block-container { max-width: 900px; padding-top: 2rem; padding-bottom: 4rem; }
/* 右上のツールバーのボタン（Fork・GitHub・メニュー）をかくす。
   サイドバーを開くボタンも stToolbar の中にあるので、stToolbar ごと消さない */
[data-testid="stToolbarActions"], [data-testid="stToolbarActionButton"], [data-testid="stMainMenu"],
.stAppDeployButton, [data-testid="stDecoration"] { display: none !important; }
[data-testid="stHeader"] { background: transparent; }

/* トップのカード全体をクリックで開く：リンクの当たり判定をカード全体に広げる */
[class*="st-key-appcard-"] { position: relative; cursor: pointer; transition: transform .1s ease; }
[class*="st-key-appcard-"]:hover { transform: translateY(-3px); }
[class*="st-key-appcard-"]:hover .topic-card { box-shadow: 0 8px 20px rgba(120, 80, 60, .18); }
[class*="st-key-appcard-"] [data-testid="stElementContainer"],
[class*="st-key-appcard-"] [data-testid="stPageLink"] { position: static !important; }
[class*="st-key-appcard-"] [data-testid="stPageLink-NavLink"]::after { content: ""; position: absolute; inset: 0; z-index: 2; }

.hero {
    padding: 1.6rem 1.25rem; border-radius: 1.4rem; text-align: center;
    margin-bottom: 1.2rem; box-shadow: 0 6px 18px rgba(120, 80, 60, .10);
    background: linear-gradient(135deg, #fff1dc, #ffe2e7 55%, #e9e8ff);
}
.hero h1 { margin: 0; color: #542b69; font-weight: 900; font-size: 2rem; line-height: 1.3; }
.hero p { margin: .5rem 0 0; color: #584b62; }

.topic-card {
    border-radius: 1.2rem; padding: 1.1rem 1.1rem .4rem; margin-bottom: .25rem; min-height: 13rem;
    border: 1px solid rgba(120, 80, 60, .12); background: #ffffff;
    box-shadow: 0 4px 12px rgba(120, 80, 60, .08);
}
.topic-card .emoji { font-size: 2.4rem; line-height: 1; }
.topic-card h3 { margin: .4rem 0 .2rem; font-size: 1.15rem; color: #3a2e39; }
.topic-card p { margin: 0 0 .5rem; font-size: .9rem; color: #6b5d68; min-height: 2.7em; }
.tag { display:inline-block; font-size:.72rem; font-weight:700; padding:.1rem .6rem;
       border-radius:99px; background:#ffe9d6; color:#b4531f; margin-bottom:.2rem; }
.tag.ai { background:#e6e3ff; color:#4a3fb0; }

div.stButton > button, div.stDownloadButton > button,
div[data-testid="stFormSubmitButton"] > button {
    min-height: 2.9rem; border-radius: .9rem; font-weight: 700;
    transition: transform .08s ease, box-shadow .15s ease;
}
div.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0,0,0,.12); }
div[data-testid="stMetric"] {
    padding: .8rem 1rem; border: 1px solid rgba(120, 80, 60, .15);
    border-radius: 1rem; background: #ffffff;
}
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 1.1rem; }
.big-center { text-align:center; font-weight:900; line-height:1.2; }
</style>
"""


def setup_page(title, icon, layout="centered", home_link=True):
    """set_page_config + 共通CSS + サイドバーのトップへ戻るリンク。各ページの最初に呼ぶ。"""
    st.set_page_config(page_title=title, page_icon=icon, layout=layout)
    st.markdown(_CSS, unsafe_allow_html=True)
    import auth  # 循環importを避けるため関数内で読み込む

    auth.gate(is_home=not home_link)
    with st.sidebar:
        if home_link:
            if "home" in PAGES:
                st.page_link(PAGES["home"], label="トップにもどる", icon="🏠")
        auth.sidebar_user()
        st.html(_HIDE_CLOUD_BADGES_JS, unsafe_allow_javascript=True)


def build_navigation():
    """サイドバーのメニューとページを登録して返す（教材.py から呼ぶ）。"""
    for key, path, title, icon, url_path in PAGE_DEFS:
        PAGES[key] = st.Page(page_file(path), title=title, icon=icon, url_path=url_path, default=(key == "home"))
    return st.navigation({section: [PAGES[k] for k in keys] for section, keys in SECTIONS.items()})


def page_file(path):
    """ページのファイル名を、ディスク上の実際の書き方にそろえる。

    Mac では「ゲ」が「ケ＋゛」のように分かれて保存されることがあり、
    そのままの名前だと st.page_link がページを見つけられない。
    """
    folder, name = os.path.split(path)
    target = unicodedata.normalize("NFC", name)
    try:
        for found in os.listdir(os.path.join(os.path.dirname(__file__), folder)):
            if unicodedata.normalize("NFC", found) == target:
                return os.path.join(folder, found)
    except OSError:
        pass
    return path


def age_level_index(count):
    """ログイン中の年齢から、年齢層ラジオ（小1〜2 … 大人）の初期位置を返す。"""
    age = st.session_state.get("auth_age")
    if age is None:
        return 0
    limits = (8, 10, 12, 15, 18)
    return next((i for i, limit in enumerate(limits) if age <= limit), count - 1)


def hero(title, subtitle=""):
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f"<div class='hero'><h1>{title}</h1>{sub}</div>", unsafe_allow_html=True)


def init_state(defaults):
    """未設定のキーだけ初期化する。"""
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(value)


def reset_state(prefix, defaults):
    """prefix で始まるキーだけ消して初期値に戻す（他ページの状態は触らない）。"""
    for key in [k for k in st.session_state.keys() if k.startswith(prefix)]:
        del st.session_state[key]
    init_state(defaults)


def get_gemini_client():
    """APIキーは .streamlit/secrets.toml の GEMINI_API_KEY か環境変数から読む。"""
    from google import genai

    key = None
    try:
        key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        pass
    key = key or os.environ.get("GEMINI_API_KEY")
    if not key:
        st.error(
            "AIのカギ（GEMINI_API_KEY）が見つからないよ。"
            " `.streamlit/secrets.toml` に `GEMINI_API_KEY = \"...\"` を書いてね。"
        )
        st.stop()
    return genai.Client(api_key=key)
