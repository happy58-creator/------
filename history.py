"""成績の履歴を Google スプレッドシートに保存する（未設定なら手元の CSV に保存）。"""
import csv
import time
from pathlib import Path

import streamlit as st

LOCAL_DIR = Path(__file__).parent / "history"

# シート名 -> 列見出し（日時と名前は自動で先頭に付く）
SHEETS = {
    "計算": ["コース", "計算", "点数", "正解数", "詳細"],
    "連打": ["コース秒数", "回数", "回/秒", "ランク"],
    "国語": ["テーマ", "点数", "詳細"],
    "タイピング": ["種類", "テーマ", "モード", "ノーミス正解", "ミスした問題", "タイム秒", "点数", "年齢層", "詳細"],
    "漢字": ["学年", "モード", "年齢層", "点数", "正解数", "詳細"],
    "ログイン": ["操作", "種類"],
    "プログラミング": ["言語", "テーマ", "年齢層", "点数", "正解数", "詳細"],
    "英語": ["コース", "年齢層", "テーマ", "点数", "正解数", "詳細"],
    "チェス": ["あそびかた", "難易度", "結果", "手数"],
    "ストーリー": ["キャラ", "難易度", "結果", "クリアしたステージ", "アビリティ"],
}
BASE_COLUMNS = ["日時", "名前"]


def _spreadsheet():
    """secrets に gcp_service_account と SPREADSHEET_ID があれば接続する。なければ None。"""
    try:
        info = dict(st.secrets["gcp_service_account"])
        sheet_id = st.secrets["SPREADSHEET_ID"]
    except Exception:
        return None
    return _open_spreadsheet(tuple(sorted(info.items())), sheet_id)


@st.cache_resource(show_spinner=False)
def _open_spreadsheet(info_items, sheet_id):
    import gspread

    return gspread.service_account_from_dict(dict(info_items)).open_by_key(sheet_id)


_checked_headers = set()


def _worksheet(book, name):
    import gspread

    header = BASE_COLUMNS + SHEETS[name]
    try:
        ws = book.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=name, rows=1000, cols=len(header))
        ws.append_row(header)
        _checked_headers.add(name)
        return ws
    if name not in _checked_headers:
        # 前のバージョンで作ったタブに、あとから増えた列（詳細など）の見出しを足す
        current = ws.row_values(1)
        if current != header and current == header[: len(current)]:
            if ws.col_count < len(header):
                ws.add_cols(len(header) - ws.col_count)
            ws.update(range_name="A1", values=[header])
        _checked_headers.add(name)
    return ws


def _csv_path(name):
    return LOCAL_DIR / f"{name}.csv"


def _append_csv(name, row):
    LOCAL_DIR.mkdir(exist_ok=True)
    path = _csv_path(name)
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(BASE_COLUMNS + SHEETS[name])
        writer.writerow(row)


def log_result(sheet, who=None, **fields):
    """1回ぶんの結果を保存。保存先 "sheets" / "csv" を返す。ゲームは止めない。

    who を渡すと、その名前で記録する（ログイン失敗など、まだ名前が決まっていないとき用）。
    """
    row = [time.strftime("%Y-%m-%d %H:%M:%S"), who or st.session_state.get("player_name") or "ななしさん"]
    row += [fields.get(col, "") for col in SHEETS[sheet]]
    book = _spreadsheet()
    if book is not None:
        try:
            _worksheet(book, sheet).append_row(row, value_input_option="USER_ENTERED")
            return "sheets"
        except Exception as e:
            st.toast(f"スプレッドシートに保存できなかったので、パソコンのCSVに保存したよ：{e}", icon="⚠️")
    try:
        _append_csv(sheet, row)
        return "csv"
    except Exception:
        return None


def log_once(sheet, token, **fields):
    """同じ token の結果は1回しか保存しない（再描画で二重に記録しないため）。"""
    done = st.session_state.setdefault("history_logged", set())
    if token in done:
        return None
    done.add(token)
    return log_result(sheet, **fields)


def read_history(sheet):
    """履歴を行のリスト（見出し付きの dict）で返す。"""
    book = _spreadsheet()
    if book is not None:
        try:
            return _worksheet(book, sheet).get_all_records()
        except Exception:
            pass
    path = _csv_path(sheet)
    if path.exists():
        with path.open(encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    return []


def storage_label():
    return "Googleスプレッドシート" if _spreadsheet() is not None else "このパソコンのCSV（historyフォルダ）"
