"""JavaScript で動くゲーム画面（Streamlit カスタムコンポーネント）。中身は web/ フォルダ。"""
from pathlib import Path

import streamlit.components.v1 as components

_WEB = Path(__file__).parent / "web"
_chess = components.declare_component("chess_game", path=str(_WEB / "chess"))
_typing = components.declare_component("typing_game", path=str(_WEB / "typing"))
_tap = components.declare_component("tap_game", path=str(_WEB / "tap"))
_kanji = components.declare_component("kanji_game", path=str(_WEB / "kanji"))
_amida = components.declare_component("amida_game", path=str(_WEB / "amida"))
_itpass = components.declare_component("itpass_study", path=str(_WEB / "itpass"))
_fe = components.declare_component("fe_study", path=str(_WEB / "fe"))
_calc = components.declare_component("calc_study", path=str(_WEB / "calc"))
_english = components.declare_component("english_study", path=str(_WEB / "english"))
# トップ画面の下のメニューとカレンダー（同じ JavaScript。iframe の名前を分けて、CSS で下のメニューだけ画面の下に固定する）
_home_footer = components.declare_component("home_footer", path=str(_WEB / "home"))
_home_calendar = components.declare_component("home_calendar", path=str(_WEB / "home"))


def chess_game(key="chess"):
    """チェス盤。ゲームが終わると結果の dict を返す（それまでは None）。"""
    return _chess(key=key, default=None)


def tap_game(duration, round, key):
    """連打ボタン。時間切れになると {"round", "clicks"} を返す（それまでは None）。"""
    return _tap(duration=duration, round=round, key=key, default=None)


def amida_game(key, **args):
    """あみだくじ。人数ぶんの names と mode("lot"=くじ引き / "rank"=じゅんい決め)、round(新しいゲームの番号)を渡す。"""
    return _amida(key=key, default=None, **args)


def kanji_game(key, **args):
    """漢字の書き取り。10字おわると {"type": "kanji_done", "round", "time", "results"} を返す（それまでは None）。"""
    return _kanji(key=key, default=None, **args)


def typing_game(app, key, **args):
    """app は "typing"（ローマ字タイピング）/ "code"（プログラミング）/ "sandbox"（じゆうモード）。"""
    return _typing(app=app, key=key, default=None, **args)


def itpass_study(key, **args):
    """ITパスポートの学習画面。1回分の結果 {"type": "log", ...} や AIへの質問 {"type": "ask", ...} を返す（それまでは None）。"""
    return _itpass(key=key, default=None, **args)


def home_footer(key, **args):
    """トップ画面の下のメニュー。押したタブ {"tab", "nonce"} を返す。"""
    return _home_footer(key=key, default=None, mode="footer", **args)


def home_calendar(key, **args):
    """学習のカレンダー。{"type": "day", "date"} か {"type": "month", "ym"}（どちらも nonce つき）を返す。"""
    return _home_calendar(key=key, default=None, mode="calendar", **args)


def fe_study(key, **args):
    """基本情報技術者試験の学習画面（ITパスポートと同じつくり）。結果 {"type": "log", ...} や AIへの質問 {"type": "ask", ...} を返す。"""
    return _fe(key=key, default=None, **args)


def calc_study(key, **args):
    """算数・数学マスター（練習問題と学ぶ）。たのみごと {"type": "start" / "check" / "ai" / "learned" / "example", "nonce", ...} を返す。"""
    return _calc(key=key, default=None, **args)


def english_study(key, **args):
    """AI英語チャレンジ。たのみごと {"type": "gen" / "log", "nonce", ...} を返す（js_page.serve で受ける）。"""
    return _english(key=key, default=None, **args)
