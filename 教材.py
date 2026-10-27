"""入口。サイドバーのメニューを作って、選ばれたページを動かす（トップ画面の中身は home.py）。"""
import sys
from pathlib import Path

# 公開先（Streamlit Cloud）では、更新(push)のあとも、前の版の部品(common.py など)がメモリに残ることがある。
# そのまま新しい home.py が動くと「ページが見つからない」などのエラーになるので、
# .py ファイルが更新されていたら、部品を読み直す。
_HERE = Path(__file__).resolve().parent
_STAMP = max(p.stat().st_mtime for p in _HERE.glob("*.py"))
if getattr(sys, "_kyouzai_code_stamp", None) != _STAMP:
    for _name in ("common", "auth", "history", "pdfgen", "web_games"):
        sys.modules.pop(_name, None)
    sys._kyouzai_code_stamp = _STAMP

import common  # noqa: E402

common.build_navigation().run()
