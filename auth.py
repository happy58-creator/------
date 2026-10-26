"""ログイン（スプレッドシートの「ユーザー」タブ）とゲスト入場。"""
import re
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


def _enter(name, age, guest, admin=False):
    st.session_state["auth_name"] = name
    st.session_state["auth_admin"] = admin
    st.session_state["auth_guest"] = guest
    st.session_state["auth_age"] = age
    st.session_state["player_name"] = f"{name}（ゲスト）" if guest else name


def logout():
    for key in ("auth_name", "auth_guest", "auth_admin", "auth_age", "player_name"):
        st.session_state.pop(key, None)


def login_screen():
    import common

    common.hero("🏠 きょうざい・ゲームひろば", "はじめに、なまえを おしえてね！")
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
