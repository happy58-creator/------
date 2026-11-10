"""買い物リストの画面（ui/index.html。Vue で作った JavaScript の画面）を Streamlit の部品として登録する。
declare_component は「呼び出したモジュール」を調べるので、ページ（app.py）の中ではなく、ふつうに import されるこのファイルで登録する。"""
from pathlib import Path

import streamlit.components.v1 as components

ui = components.declare_component("kaimono_ui", path=str(Path(__file__).resolve().parent / "ui"))
