"""ログイン（スプレッドシートの「ユーザー」タブ）とゲスト入場。"""
import os
import re
import secrets
import time
import unicodedata
from datetime import date

import streamlit as st

import history

USERS_SHEET = "ユーザー"
USERS_HEADER = ["名前", "パスワード", "誕生日", "管理者"]
ADMIN_MARKS = {"○", "◯", "〇", "1", "true", "yes", "y", "はい", "管理者", "admin"}
MAX_FAILS = 5
LOCK_SECONDS = 300
SESSION_SECONDS = int(os.environ.get("SESSION_SECONDS", 3600))  # ログイン状態を保つ時間（ログイン後1時間）
COOKIE_NAME = "kyouzai_token"
COOKIE_MAX_AGE = 86400  # クッキー自体は1日残す。1時間の期限はサーバー側で判定する（期限切れも記録できる）


def _norm(text):
    return unicodedata.normalize("NFKC", str(text or "")).strip()


def _norm_name(text):
    return _norm(text).replace(" ", "").replace("　", "").lower()


def _norm_password(text):
    t = _norm(text)
    return t.zfill(4) if t.isdigit() else t  # シートで 0508 が 508 になっても合わせる


def is_admin_row(row):
    """「管理者」列に ○ / 1 / TRUE / はい などが入っていれば管理者。"""
    return _norm(row.get("管理者")).lower() in ADMIN_MARKS


def parse_birthday(text):
    """「2015/5/8」「2015-05-08」「2015年5月8日」を date にする。年が無ければ None。"""
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", _norm(text))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def age_on(birthday, today=None):
    today = today or date.today()
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))


def _birthday_password(text):
    """誕生日から MMDD のパスワードを作る（パスワード列が空のときの代わり）。"""
    m = re.search(r"(\d{1,2})\D+(\d{1,2})\D*$", _norm(text))
    return f"{int(m.group(1)):02d}{int(m.group(2)):02d}" if m else ""


@st.cache_data(ttl=60, show_spinner=False)
def _load_users():
    book = history._spreadsheet()
    if book is None:
        return None
    import gspread

    try:
        ws = book.worksheet(USERS_SHEET)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=USERS_SHEET, rows=200, cols=len(USERS_HEADER))
        ws.append_row(USERS_HEADER)
    return ws.get_all_records()


def users_available():
    try:
        return _load_users() is not None
    except Exception:
        return False


@st.cache_resource
def _fail_table():
    return {}


def _check_login(name, password):
    """(ユーザー情報 or None, メッセージ)"""
    key = _norm_name(name)
    fails = _fail_table()
    count, until = fails.get(key, (0, 0.0))
    if until > time.time():
        return None, f"まちがいが続いたので、{int((until - time.time()) // 60) + 1}分ほど待ってからやりなおしてね。"
    try:
        users = _load_users() or []
    except Exception:
        return None, "ユーザー名簿を読みこめなかったよ。しばらくしてからもう一度ためしてね。"
    for row in users:
        if _norm_name(row.get("名前")) != key or not key:
            continue
        expected = _norm_password(row.get("パスワード")) or _birthday_password(row.get("誕生日"))
        if expected and _norm_password(password) == expected:
            fails.pop(key, None)
            return row, ""
    count += 1
    fails[key] = (count, time.time() + LOCK_SECONDS if count >= MAX_FAILS else 0.0)
    return None, "なまえかパスワードがちがうよ。"


def is_admin():
    return bool(st.session_state.get("auth_admin")) and not st.session_state.get("auth_guest")


def is_logged_in():
    return bool(st.session_state.get("auth_name"))


@st.cache_resource
def _token_store():
    """ブラウザーに持たせた合言葉(トークン) -> ログイン情報。サーバーのメモリ上だけに置く。"""
    return {}


def _kind(guest, admin):
    return "ゲスト" if guest else ("管理者" if admin else "登録ユーザー")


def _log(action, who=None, kind="-"):
    history.log_result("ログイン", who=who, 操作=action, 種類=kind)


def _set_session(name, age, guest, admin, expires):
    st.session_state["auth_name"] = name
    st.session_state["auth_admin"] = admin
    st.session_state["auth_guest"] = guest
    st.session_state["auth_age"] = age
    st.session_state["auth_expires"] = expires
    st.session_state["player_name"] = f"{name}（ゲスト）" if guest else name


def _enter(name, age, guest, admin=False):
    """ログイン成功。1時間は再読み込みしてもログインしたままにする。"""
    expires = time.time() + SESSION_SECONDS
    store = _token_store()
    for old in [t for t, v in store.items() if v["expires"] < time.time()]:
        del store[old]
    token = secrets.token_urlsafe(32)
    store[token] = {"name": name, "age": age, "guest": guest, "admin": admin, "expires": expires}
    _set_session(name, age, guest, admin, expires)
    st.session_state["auth_token"] = token
    st.session_state["auth_cookie_cmd"] = ("set", token)
    _log("ログイン", kind=_kind(guest, admin))


def logout(action="ログアウト", notice=None):
    if st.session_state.get("auth_name"):
        _log(action, kind=_kind(st.session_state.get("auth_guest"), st.session_state.get("auth_admin")))
    _token_store().pop(st.session_state.get("auth_token"), None)
    for key in ("auth_name", "auth_guest", "auth_admin", "auth_age", "auth_expires", "auth_token", "player_name"):
        st.session_state.pop(key, None)
    st.session_state["auth_cookie_cmd"] = ("clear", "")
    if notice:
        st.session_state["auth_notice"] = notice


def _flush_cookie():
    """ブラウザーのクッキーを、保存・削除する（JavaScript を1回だけ出す）。"""
    cmd = st.session_state.pop("auth_cookie_cmd", None)
    if not cmd:
        return
    action, token = cmd
    max_age = COOKIE_MAX_AGE if action == "set" else 0
    value = token if action == "set" else ""
    st.html(
        f"""<script>
        document.cookie = "{COOKIE_NAME}={value}; max-age={max_age}; path=/; SameSite=Lax" +
          (location.protocol === "https:" ? "; Secure" : "");
        </script>""",
        unsafe_allow_javascript=True,
    )


def _try_restore():
    """再読み込みしたあとでも、1時間以内なら、クッキーのトークンでログイン状態に戻す。"""
    try:
        token = st.context.cookies.get(COOKIE_NAME)
    except Exception:
        return
    entry = _token_store().get(token) if token else None
    if not entry:
        return
    if entry["expires"] > time.time():
        _set_session(entry["name"], entry["age"], entry["guest"], entry["admin"], entry["expires"])
        st.session_state["auth_token"] = token
    else:  # 1時間をすぎたトークン：記録を残して、クッキーも消す
        _token_store().pop(token, None)
        who = f"{entry['name']}（ゲスト）" if entry["guest"] else entry["name"]
        _log("期限切れ", who=who, kind=_kind(entry["guest"], entry["admin"]))
        st.session_state["auth_cookie_cmd"] = ("clear", "")
        st.session_state["auth_notice"] = "ログインしてから1時間たったので、もういちどログインしてね。"
        _flush_cookie()


def login_screen():
    import common

    common.hero("🏠 きょうざい・ゲームひろば", "はじめに、なまえを おしえてね！")
    notice = st.session_state.pop("auth_notice", None)
    if notice:
        st.warning(notice)
    tab_login, tab_guest = st.tabs(["🔑 ログイン", "🙋 ゲストで入る"])

    with tab_login:
        if not users_available():
            st.info("ログイン名簿（スプレッドシート）がまだつながっていないよ。いまは「ゲストで入る」を使ってね。")
        with st.form("auth_login_form"):
            name = st.text_input("なまえ")
            password = st.text_input("パスワード（誕生日 4けた　例：5月8日 → 0508）", type="password", max_chars=8)
            go = st.form_submit_button("ログイン", type="primary", use_container_width=True)
        if go:
            row, message = _check_login(name, password)
            if row is None and users_available() and "待って" not in message:
                _load_users.clear()  # 名簿に追加したばかりでも通るよう、1回だけ読み直す
                row, message = _check_login_no_count(name, password) or (None, message)
            if row is None:
                _log("ログインロック中" if "待って" in message else "ログイン失敗", who=_norm(name) or "（なまえなし）")
                st.error(message)
            else:
                birthday = parse_birthday(row.get("誕生日"))
                _enter(_norm(row["名前"]), age_on(birthday) if birthday else None, guest=False, admin=is_admin_row(row))
                st.rerun()

    with tab_guest:
        with st.form("auth_guest_form"):
            name = st.text_input("なまえ", key="auth_guest_name")
            age = st.number_input("ねんれい", min_value=3, max_value=120, value=8, step=1)
            go = st.form_submit_button("ゲストで入る", use_container_width=True)
        st.caption("ゲストの成績は「なまえ（ゲスト）」として記録されるよ。")
        if go:
            if not _norm(name):
                st.warning("なまえを入れてね！")
            else:
                _enter(_norm(name), int(age), guest=True)
                st.rerun()


def _check_login_no_count(name, password):
    """名簿を読み直したあとの再判定。失敗回数は増やさない。"""
    key = _norm_name(name)
    for row in _load_users() or []:
        if _norm_name(row.get("名前")) == key and key:
            expected = _norm_password(row.get("パスワード")) or _birthday_password(row.get("誕生日"))
            if expected and _norm_password(password) == expected:
                _fail_table().pop(key, None)
                return row, ""
    return None


def gate(is_home):
    """ログインしていなければログイン画面（トップ）か案内（他ページ）を出して止める。"""
    _flush_cookie()
    if is_logged_in() and time.time() > st.session_state.get("auth_expires", 0):
        logout("期限切れ", notice="ログインしてから1時間たったので、もういちどログインしてね。")
        _flush_cookie()
    if not is_logged_in():
        _try_restore()
    if is_logged_in():
        return
    if is_home:
        login_screen()
    else:
        import common

        common.hero("🔒 ログインしてね", "はじめに トップ画面で なまえを入れてね。")
        try:
            st.page_link(common.HOME_PAGE, label="トップ画面へ", icon="🏠", use_container_width=True)
        except st.errors.StreamlitAPIException:
            st.info("トップ画面（教材.py）から入りなおしてね。")
    st.stop()


def sidebar_user():
    name = st.session_state.get("auth_name", "")
    st.markdown(f"👤 **{name}**" + ("（ゲスト）" if st.session_state.get("auth_guest") else "") + " さん"
                + ("　🛡️管理者" if is_admin() else ""))
    if st.button("ログアウト", key="auth_logout", use_container_width=True):
        logout()
        st.rerun()
