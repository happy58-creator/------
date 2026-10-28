"""ログイン（スプレッドシートの「ユーザー」タブ）。ゲスト用アカウントで入ったときだけ、なまえと年齢を聞く。

ログイン状態は、最後に使ってから1時間（SESSION_SECONDS）保つ。再読み込みや、画面を閉じて開き直したときも続く。

しくみ：
- ログインすると、なまえ・期限などを入れた「合言葉（トークン）」を作り、サーバーだけが知っている鍵で署名する。
  中身は署名で守られているので、サーバーのメモリに何も置かなくてよい（アプリが再起動・更新されても消えない）。
- トークンはブラウザーに保存する（クッキーと localStorage の両方）。保存と読み出しは、小さな部品
  web/auth_bridge/（画面には何も出ない）で行う。クッキーがサーバーに届く環境では、st.context.cookies からも読む。
- 使うたびに期限を延ばし、30分ごとにトークンを作り直して保存し直す。期限はトークンの中にあるので、
  1時間をすぎたトークンは署名が正しくても使えない（「期限切れ」として記録して消す）。
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import unicodedata
from datetime import date
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import history

USERS_SHEET = "ユーザー"
USERS_HEADER = ["名前", "パスワード", "誕生日", "管理者"]
ADMIN_MARKS = {"○", "◯", "〇", "1", "true", "yes", "y", "はい", "管理者", "admin"}
MAX_FAILS = 5
LOCK_SECONDS = 300
SESSION_SECONDS = int(os.environ.get("SESSION_SECONDS", 3600))  # 最後にアクセスしてから、ログイン状態を保つ時間（1時間）
COOKIE_REFRESH_SECONDS = 1800  # クッキーを延ばし直す間隔
COOKIE_NAME = "kyouzai_token"
COOKIE_MAX_AGE = 86400  # クッキー自体は1日残す（使うたびに延ばし直す）。1時間の期限はトークンの中で判定する（期限切れも記録できる）
_bridge = components.declare_component("auth_bridge", path=str(Path(__file__).resolve().parent / "web" / "auth_bridge"))
GUEST_ACCOUNT_NAMES = {"ゲスト", "げすと", "guest"}  # 名簿でこの名前のアカウントはゲスト用


def _norm(text):
    return unicodedata.normalize("NFKC", str(text or "")).strip()


def _norm_name(text):
    return _norm(text).replace(" ", "").replace("　", "").lower()


def _norm_password(text):
    t = _norm(text)
    return t.zfill(4) if t.isdigit() else t  # シートで 0508 が 508 になっても合わせる


def is_guest_row(row):
    """名簿の「名前」がゲスト用の名前（ゲスト / guest）なら、ゲスト用アカウント。"""
    return _norm_name(row.get("名前")) in GUEST_ACCOUNT_NAMES


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


# ---------------------------------------------------------------------------
# 署名つきトークン
# ---------------------------------------------------------------------------
@st.cache_resource
def _secret_key():
    """署名の鍵。secrets の AUTH_SECRET → サービスアカウントの秘密鍵から作る → 手元のファイル の順に使う"""
    try:
        if "AUTH_SECRET" in st.secrets:
            return str(st.secrets["AUTH_SECRET"]).encode()
        if "gcp_service_account" in st.secrets:
            return hashlib.sha256(("kyouzai-auth:" + str(st.secrets["gcp_service_account"]["private_key"])).encode()).digest()
    except Exception:
        pass
    path = Path(__file__).resolve().parent / ".auth_secret"
    try:
        if not path.exists():
            path.write_text(secrets.token_hex(32), encoding="utf-8")
        return path.read_text(encoding="utf-8").strip().encode()
    except OSError:
        return b"kyouzai-fallback-key"  # 書き込めない環境の最後の手段（再起動するとログインは切れる）


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(name, age, guest, admin, expires, key=None):
    """ログイン情報に署名したトークン（「本文.署名」の形）"""
    body = _b64(json.dumps({"n": name, "a": age, "g": bool(guest), "ad": bool(admin), "exp": int(expires),
                            "r": secrets.token_hex(4)}, ensure_ascii=False, separators=(",", ":")).encode())
    sig = _b64(hmac.new(key or _secret_key(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_token(token, key=None):
    """トークンを確かめて中身を返す。署名が合わなければ None（期限切れかどうかは呼ぶ側で exp を見る）"""
    try:
        body, sig = str(token).split(".")
        good = _b64(hmac.new(key or _secret_key(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        data = json.loads(_unb64(body))
        return {"name": data["n"], "age": data.get("a"), "guest": bool(data.get("g")),
                "admin": bool(data.get("ad")), "expires": float(data["exp"])}
    except Exception:
        return None


@st.cache_resource
def _revoked():
    """ログアウトしたトークン（期限まで覚えておく。再起動で消えても、ブラウザー側も消しているので問題ない）"""
    return {}


def _forget(token):
    """この画面ではもう使わないトークン（期限切れ・ログアウトしたもの）"""
    st.session_state.setdefault("_auth_dead", set()).add(token)


def _bridge_reply():
    """部品からの返事 {"token": 保存されているトークン, "done": 最後に実行した指示の番号}。まだなければ None"""
    reply = st.session_state.get("auth_bridge")
    return reply if isinstance(reply, dict) else None


def _stored_token():
    """ブラウザーに保存されているトークン。まだ部品から返事がないときは None、保存されていなければ ""。"""
    try:
        cookie = st.context.cookies.get(COOKIE_NAME)
    except Exception:
        cookie = None
    if cookie:
        return cookie
    reply = _bridge_reply()
    if reply is None or st.session_state.get("_auth_bridge_ignore"):
        return None if reply is None else ""
    return reply.get("token") or ""


def _render_bridge():
    """トークンを保存・削除・読み出しする部品を出す（画面には何も出ない）"""
    cmd = st.session_state.get("auth_cookie_cmd")
    reply = _bridge_reply()
    if cmd and reply and reply.get("done") == cmd[2]:        # ブラウザーが実行し終えた指示は消す
        st.session_state.pop("auth_cookie_cmd", None)
        st.session_state.pop("_auth_bridge_ignore", None)
        cmd = None
    args = {"name": COOKIE_NAME, "max_age": COOKIE_MAX_AGE}
    if cmd:
        args.update({"cmd": cmd[0], "token": cmd[1], "nonce": cmd[2]})
    _bridge(**args, key="auth_bridge", default=None)


def session_alive():
    """このあとのページ表示でログイン中になるか（メニューを出すかどうかの判定用。画面には何も出さない）。"""
    if is_logged_in():
        return time.time() <= st.session_state.get("auth_expires", 0)
    entry = read_token(_stored_token()) if _stored_token() else None
    return bool(entry) and entry["expires"] > time.time()


def _kind(guest, admin):
    return "ゲスト" if guest else ("管理者" if admin else "登録ユーザー")


def _log(action, who=None, kind="-"):
    history.log_result("ログイン", who=who, 操作=action, 種類=kind)


def _save_cmd(action, token=""):
    """ブラウザーへの保存・削除の指示（部品が実行したら消える）"""
    st.session_state["auth_cookie_cmd"] = (action, token, secrets.token_hex(4))


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
    token = make_token(name, age, guest, admin, expires)
    _set_session(name, age, guest, admin, expires)
    st.session_state["auth_token"] = token
    st.session_state["auth_cookie_at"] = time.time()
    _save_cmd("set", token)
    _log("ログイン", kind=_kind(guest, admin))


def logout(action="ログアウト", notice=None):
    if st.session_state.get("auth_name"):
        _log(action, kind=_kind(st.session_state.get("auth_guest"), st.session_state.get("auth_admin")))
    revoked = _revoked()
    for old in [t for t, exp in revoked.items() if exp < time.time()]:
        del revoked[old]
    for token in (st.session_state.get("auth_token"), _stored_token()):   # いまのトークンと、開いたときのクッキー
        if token:
            revoked[token] = time.time() + SESSION_SECONDS + 60
            _forget(token)
    for key in ("auth_name", "auth_guest", "auth_admin", "auth_age", "auth_expires", "auth_token", "player_name"):
        st.session_state.pop(key, None)
    st.session_state["_auth_bridge_ignore"] = True   # 消し終わるまで、前に読んだトークンは使わない
    _save_cmd("clear")
    if notice:
        st.session_state["auth_notice"] = notice


def _touch():
    """アクセスがあるたびに期限を「いまから1時間後」に延ばす（最後にアクセスしてから1時間）。"""
    now = time.time()
    expires = now + SESSION_SECONDS
    st.session_state["auth_expires"] = expires
    # トークンの中の期限も延ばすため、30分ごとに作り直してブラウザーに保存し直す
    if now - st.session_state.get("auth_cookie_at", 0) > COOKIE_REFRESH_SECONDS:
        ss = st.session_state
        token = make_token(ss["auth_name"], ss.get("auth_age"), ss.get("auth_guest"), ss.get("auth_admin"), expires)
        ss["auth_token"] = token
        ss["auth_cookie_at"] = now
        _save_cmd("set", token)


def _try_restore():
    """再読み込みしたあとでも、1時間以内なら、クッキーのトークンでログイン状態に戻す。"""
    token = _stored_token()
    if not token or token in _revoked() or token in st.session_state.get("_auth_dead", ()):
        return
    entry = read_token(token)
    if not entry:
        _forget(token)
        _save_cmd("clear")          # 鍵が変わった・こわれたトークンは消す
        return
    if entry["expires"] > time.time():
        _set_session(entry["name"], entry["age"], entry["guest"], entry["admin"], entry["expires"])
        st.session_state["auth_token"] = token
        st.session_state["auth_cookie_at"] = 0     # すぐに作り直して、期限を延ばしたものを保存する
    else:  # 1時間をすぎたトークン：記録を残して、ブラウザーからも消す
        who = f"{entry['name']}（ゲスト）" if entry["guest"] else entry["name"]
        _log("期限切れ", who=who, kind=_kind(entry["guest"], entry["admin"]))
        _forget(token)
        _save_cmd("clear")
        st.session_state["_auth_bridge_ignore"] = True
        st.session_state["auth_notice"] = "さいごに使ってから1時間たったので、もういちどログインしてね。"


def login_screen():
    import common

    common.hero("🏠 きょうざい・ゲームひろば", "はじめに、なまえを おしえてね！")
    notice = st.session_state.pop("auth_notice", None)
    if notice:
        st.warning(notice)
    if st.session_state.get("auth_guest_pending"):
        _guest_profile_form()
        return

    if not users_available():
        st.info("ログイン名簿（スプレッドシート）がまだつながっていないよ。先生に きいてね。")
    with st.form("auth_login_form"):
        name = st.text_input("なまえ")
        password = st.text_input("パスワード（誕生日 4けた　例：1月19日 → 0119）", type="password", max_chars=8)
        go = st.form_submit_button("ログイン", type="primary", use_container_width=True)
    if go:
        row, message = _check_login(name, password)
        if row is None and users_available() and "待って" not in message:
            _load_users.clear()  # 名簿に追加したばかりでも通るよう、1回だけ読み直す
            row, message = _check_login_no_count(name, password) or (None, message)
        if row is None:
            _log("ログインロック中" if "待って" in message else "ログイン失敗", who=_norm(name) or "（なまえなし）")
            st.error(message)
        elif is_guest_row(row):
            # ゲスト用アカウント：つぎの画面で なまえと年齢を聞いてから入る
            st.session_state["auth_guest_pending"] = True
            st.rerun()
        else:
            birthday = parse_birthday(row.get("誕生日"))
            _enter(_norm(row["名前"]), age_on(birthday) if birthday else None, guest=False, admin=is_admin_row(row))
            st.rerun()


def _guest_profile_form():
    """ゲスト用アカウントでログインしたあと、その人の なまえと年齢を入れてもらう。"""
    st.success("🙋 ゲストで ログインしたよ！ あなたの なまえと ねんれいを おしえてね。")
    with st.form("auth_guest_form"):
        name = st.text_input("なまえ", key="auth_guest_name")
        age = st.number_input("ねんれい", min_value=3, max_value=120, value=8, step=1)
        go = st.form_submit_button("はじめる", type="primary", use_container_width=True)
    st.caption("ゲストの成績は「なまえ（ゲスト）」として記録されるよ。")
    if go:
        if not _norm(name):
            st.warning("なまえを入れてね！")
        elif _norm_name(name) in GUEST_ACCOUNT_NAMES:
            st.warning("「ゲスト」ではなく、あなたの なまえを入れてね！")
        else:
            st.session_state.pop("auth_guest_pending", None)
            _enter(_norm(name), int(age), guest=True)
            st.rerun()
    if st.button("↩️ ログイン画面に もどる"):
        st.session_state.pop("auth_guest_pending", None)
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
    if is_logged_in() and time.time() > st.session_state.get("auth_expires", 0):
        logout("期限切れ", notice="さいごに使ってから1時間たったので、もういちどログインしてね。")
    if not is_logged_in():
        _try_restore()
    if is_logged_in():
        _touch()
    _render_bridge()                 # 保存・削除の指示を出し、保存されているトークンを読む
    if is_logged_in():
        return
    if _stored_token() is None:
        # ブラウザーに保存されたトークンの返事を待っているところ（返事が来たら自動で読み直して、ログインしたままにする）
        st.caption("ログイン状態を たしかめています…")
    if is_home:
        login_screen()
    else:
        import common

        common.hero("🔒 ログインしてね", "はじめに トップ画面で なまえを入れてね。")
        if "home" in common.PAGES:
            st.page_link(common.PAGES["home"], label="トップ画面へ", icon="🏠", use_container_width=True)
    st.stop()


def sidebar_user():
    name = st.session_state.get("auth_name", "")
    st.markdown(f"👤 **{name}**" + ("（ゲスト）" if st.session_state.get("auth_guest") else "") + " さん"
                + ("　🛡️管理者" if is_admin() else ""))
    if st.button("ログアウト", key="auth_logout", use_container_width=True):
        logout()
        st.rerun()
