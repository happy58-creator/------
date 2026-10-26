"""JavaScript で動くゲーム画面（Streamlit カスタムコンポーネント）。中身は web/ フォルダ。"""
from pathlib import Path

import streamlit.components.v1 as components

_WEB = Path(__file__).parent / "web"
_chess = components.declare_component("chess_game", path=str(_WEB / "chess"))
_typing = components.declare_component("typing_game", path=str(_WEB / "typing"))


def chess_game(key="chess"):
    """チェス盤。ゲームが終わると結果の dict を返す（それまでは None）。"""
    return _chess(key=key, default=None)


def typing_game(app, key, **args):
    """app は "typing"（ローマ字タイピング）/ "code"（プログラミング）/ "sandbox"（じゆうモード）。"""
    return _typing(app=app, key=key, default=None, **args)
