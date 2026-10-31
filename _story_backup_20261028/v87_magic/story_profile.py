"""ストーリーモードの保存（ログインした名前ごとに1つのプロフィール）

読み込みと保存は load_profile / save_profile の2つだけで行う。
成績の履歴と同じ Google スプレッドシートの「ストーリー保存」タブに、1人1行の JSON で置く。
スプレッドシートが未設定なら、手元の history/story/ フォルダに JSON ファイルで置く。
"""
import json
import re
import time

import history
import story_logic

SHEET = "ストーリー保存"
HEADER = ["名前", "データ", "更新日時"]
LOCAL_DIR = history.LOCAL_DIR / "story"


def _worksheet(book):
    import gspread

    try:
        return book.worksheet(SHEET)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=SHEET, rows=200, cols=len(HEADER))
        ws.append_row(HEADER)
        return ws


def _local_path(user_id):
    safe = re.sub(r'[\\/:*?"<>|\s]', "_", user_id)
    return LOCAL_DIR / f"{safe}.json"


def load_profile(user_id):
    """プロフィールを読み込む。なければ新しいプロフィール"""
    book = history._spreadsheet()
    raw = None
    if book is not None:
        ws = _worksheet(book)
        names = ws.col_values(1)
        if user_id in names:
            raw = ws.cell(names.index(user_id) + 1, 2).value
    else:
        path = _local_path(user_id)
        if path.exists():
            raw = path.read_text(encoding="utf-8")
    return story_logic.normalize_profile(json.loads(raw) if raw else None)


def save_profile(user_id, data):
    """プロフィールを保存する"""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    book = history._spreadsheet()
    if book is not None:
        ws = _worksheet(book)
        names = ws.col_values(1)
        if user_id in names:
            row = names.index(user_id) + 1
            ws.update(range_name=f"B{row}:C{row}", values=[[text, stamp]], value_input_option="RAW")
        else:
            ws.append_row([user_id, text, stamp], value_input_option="RAW")
        return
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    _local_path(user_id).write_text(text, encoding="utf-8")
