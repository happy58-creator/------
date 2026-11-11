"""JavaScript で動くゲーム画面（Streamlit カスタムコンポーネント）。中身は web/ フォルダ。"""
from pathlib import Path

import streamlit.components.v1 as components

_WEB = Path(__file__).parent / "web"
_chess = components.declare_component("chess_game", path=str(_WEB / "chess"))
_typing = components.declare_component("typing_game", path=str(_WEB / "typing"))
_tap = components.declare_component("tap_game", path=str(_WEB / "tap"))
_kanji = components.declare_component("kanji_game", path=str(_WEB / "kanji"))
_amida = components.declare_component("amida_game", path=str(_WEB / "amida"))


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
