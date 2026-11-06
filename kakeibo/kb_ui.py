"""JavaScript の画面（ui/index.html）を Streamlit の部品として登録する。
declare_component は「呼び出したモジュール」を調べるので、st.navigation のページ（app.py）の中ではなく、
ふつうに import されるこのファイルで登録する。"""
from pathlib import Path

import streamlit.components.v1 as components

ui = components.declare_component("kakeibo_ui", path=str(Path(__file__).resolve().parent / "ui"))
