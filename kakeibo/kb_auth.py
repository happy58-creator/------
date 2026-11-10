"""家計簿と買い物リストで共通のログイン。
パスワードは secrets の KAKEIBO_PASSWORD。一度入ると24時間つづく（ブラウザに「ログインの証明」を保存）。
同じ教材アプリの中のページなので、家計簿で入れば買い物リストにもそのまま入れる（逆も同じ）。"""
import hashlib
import hmac
import time

import streamlit as st

LOGIN_HOURS = 24      # 一度ログインしたら、この時間はパスワードなしで開ける


def secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return None


def hide_badges():
    """教材と同じ：Streamlit Cloud の王冠マーク・作った人のアカウント表示などを JavaScript で消す（common.py のものを使う）"""
    try:
        import common
        st.html(common._HIDE_CLOUD_BADGES_JS, unsafe_allow_javascript=True)
    except Exception:
        pass


def hide_css(iframe_name, fullscreen=True):
    """Streamlit の飾り（上のバー・右下のアイコン・サイドバー・余白）を消して、画面いっぱいに JavaScript の画面を出す"""
    frame = (f"""iframe[title*="{iframe_name}"] {{ position: fixed !important; inset: 0 !important; width: 100vw !important; height: 100vh !important; height: 100dvh !important;
  border: 0 !important; z-index: 999990 !important; background: #f5f6f8; }}""" if fullscreen else f"""iframe[title*="{iframe_name}"] {{ display: none !important; }}""")
    return f"""<style>
header, [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"], [data-testid="stSidebarNav"],
[data-testid="manage-app-button"], [data-testid="stAppDeployButton"], #MainMenu, footer,
[class*="viewerBadge"], [class*="_profileContainer"], [class*="_profilePreview"], [class*="_container_gzau3"], [class*="stDeployButton"] {{ display: none !important; }}
html, body, .stApp {{ background: #f5f6f8 !important; {"overflow: hidden !important;" if fullscreen else ""} }}
.block-container, [data-testid="stMainBlockContainer"] {{ padding: 0 !important; max-width: none !important; }}
{frame}
</style>"""


def make_token(pw, exp):
    """ログインの証明（期限つき）。パスワードを鍵にした署名なので、パスワードを変えると前の証明は使えなくなる"""
    sig = hmac.new(str(pw).encode(), f"kakeibo:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{exp}.{sig}"


def token_ok(pw, token):
    try:
        exp, sig = str(token).split(".", 1)
        return int(exp) > time.time() and hmac.compare_digest(make_token(pw, int(exp)), f"{exp}.{sig}")
    except Exception:
        return False


def gate(ui, title, iframe_name):
    """パスワード（secrets に KAKEIBO_PASSWORD があるときだけ）。ui はそのページの JavaScript の部品（保存した証明を読むのに使う）"""
    ss = st.session_state
    pw = secret("KAKEIBO_PASSWORD")
    if not pw:
        return
    if ss.get("kb_ok") and token_ok(pw, ss.get("kb_token")):
        return
    ss.kb_ok = False
    # ?kt=証明 つきで来たら、その証明で入る（同じパスワードで作った証明）
    try:
        kt = st.query_params.get("kt")
    except Exception:
        kt = None
    if kt and token_ok(pw, kt):
        ss.kb_ok, ss.kb_token = True, kt
        try:
            del st.query_params["kt"]
        except Exception:
            pass
        return
    # ブラウザに保存した証明（クッキー）が、まだ期限内ならそのまま入る
    try:
        cookie = st.context.cookies.get("kb_token")
    except Exception:
        cookie = None
    if cookie and cookie != ss.get("kb_ignore") and token_ok(pw, cookie):
        ss.kb_ok, ss.kb_token = True, cookie
        return
    hide_badges()
    # クッキーが届かない環境のために、画面の中の保存（localStorage）も見にいく（見えない部品）
    probe = ui(mode="probe", key="kb_probe", default=None)
    if isinstance(probe, dict) and probe.get("token") and token_ok(pw, probe["token"]):
        ss.kb_ok, ss.kb_token = True, probe["token"]
        st.rerun()
    st.markdown(hide_css(iframe_name, fullscreen=False) + f"""<style>
    .block-container {{ max-width: 380px !important; padding-top: 18vh !important; padding-left: 16px !important; padding-right: 16px !important; margin: 0 auto; }}
    </style><div style="text-align:center;font-size:22px;font-weight:800;margin-bottom:12px">{title}</div>""", unsafe_allow_html=True)
    with st.form("login"):
        v = st.text_input("パスワード", type="password")
        if st.form_submit_button("ひらく", type="primary", use_container_width=True):
            if hmac.compare_digest(v.encode(), str(pw).encode()):
                ss.kb_ok = True
                ss.kb_token = make_token(pw, int(time.time()) + LOGIN_HOURS * 3600)
                st.rerun()
            st.error("パスワードがちがいます")
    st.stop()


def logout():
    ss = st.session_state
    ss.kb_ignore = ss.get("kb_token")       # ログアウトしたあとは、同じ証明で入りなおさない
    ss.kb_ok, ss.kb_token = False, None
