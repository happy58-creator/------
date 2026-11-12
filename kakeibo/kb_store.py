"""保存のしくみ。
secrets に gcp_service_account と KAKEIBO_SPREADSHEET_ID があれば Google スプレッドシートに、
なければ手元の CSV（data フォルダ）に保存する（CSV は試す用。Streamlit Cloud では再起動で消える）。
シートは「表の名前」ごとに1枚。1行目が列見出し。

Google への問い合わせ（1分に読み60回・書き60回まで）をへらすため：
  ・表の中身は、アプリの中に「写し」を持つ（5分たつか、アプリが再起動するまで読み直さない）。
    保存したときは、その表の写しだけを差しかえる（全部の表を読み直さない）。写しは家計簿・買い物リスト・夫婦の両方で共通
  ・シートの場所は、一度調べたら覚えておく
  ・表を書きかえるときは、1回の書きこみですませる（前より短くなった分は空の行で上書きする）"""
import csv
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

TABLES = {
    "記録": ["ID", "日付", "種類", "金額", "カテゴリ", "メモ", "登録日時", "支払方法"],     # 支払方法：現金・クレカ（支出だけ）
    "予算": ["カテゴリ", "予算", "表示"],                                                  # 表示が "0" の項目は予算の画面に出さない
    "サブスク": ["ID", "名前", "金額", "周期", "次の支払日", "支払日の日", "カテゴリ", "メモ"],
    "カテゴリ": ["種類", "名前", "アイコン"],
    "積立": ["ID", "名前", "支払", "開始月", "並び", "メモ", "合計額", "月額", "前回支払日", "目安"],     # 目安：固定・逆算
    "積立記録": ["ID", "項目ID", "月", "種類", "金額"],       # 種類：積立（その月から先の毎月の額）・支払（払った額）・補填（払った額）
    "アイコン名": ["キー", "名前"],          # アイコンに自分でつけた名前（レポートの見出し）
    # 買い物リスト（shopping/）
    "買い物": ["ID", "品名", "ジャンル", "メモ", "店舗ID", "済", "登録日時", "優先"],        # 優先：空・1（優先）・2（最優先）
    "店舗": ["ID", "店名", "緯度", "経度", "並び", "別名"],      # 別名：地図でちがう書き方のときの名前（例：無印、MUJI）
    "価格記録": ["ID", "品名", "店舗ID", "店名", "値段", "量", "単位", "入数", "単価", "基準", "基準量", "日付", "メモ"],   # 買い物リストの「計算」で残した値段（単価＝基準量あたりの税込の値段）
    "支店": ["ID", "店舗ID", "支店名", "緯度", "経度", "規模"],   # お店の中の店舗（例：無印良品 → イオンモール福岡店）。規模：大1km・中600m・小300m（空は中）
    "買い物ジャンル": ["名前", "アイコン", "並び"],
    "買い物の記憶": ["キー", "品名", "ジャンル", "更新"],         # 品名とジャンルの組み合わせ（次に同じ品名を入れたら、そのジャンルを選ぶ）
    "レシートの記憶": ["キー", "品名", "カテゴリ", "更新"],      # 家計簿のレシート読み取り：レシートの書き方（キー）→ 直した品名・カテゴリ（次から自動で直す）
    "購入記録": ["ID", "日時", "品ID", "品名", "ジャンル", "店舗ID", "店名", "値段", "量", "単位", "入数", "税", "価格ID"],   # 「買った」にした日時・近くの登録店（カレンダー）。値段〜はカレンダーで入れた値段（価格ID＝価格記録のID）
}
_CHECKED = set()      # 列見出しを確かめたシート
LOCAL_DIR = Path(__file__).parent / "data"
CACHE_SECONDS = 300   # 写しを使う時間（スプレッドシートを直接さわったときは、これだけたつと画面に出る）


def using_sheets():
    try:
        return bool(st.secrets["gcp_service_account"]) and bool(st.secrets["KAKEIBO_SPREADSHEET_ID"])
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _book():
    import gspread
    return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"])).open_by_key(st.secrets["KAKEIBO_SPREADSHEET_ID"])


@st.cache_resource(show_spinner=False)
def _memo():
    """アプリ全体で共通の入れもの：表の写し・シートの場所"""
    return {"rows": {}, "at": {}, "ws": {}, "lock": threading.Lock()}


def _sheet(name):
    import gspread
    ws = _memo()["ws"].get(name)
    if ws is not None and name in _CHECKED:
        return ws                                  # 一度調べたシートは、もう問い合わせない
    book = _book()
    try:
        ws = book.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=name, rows=100, cols=len(TABLES[name]))
        ws.update([TABLES[name]], "A1")
        _CHECKED.add(name)
        _memo()["ws"][name] = ws
        return ws
    if name not in _CHECKED:
        # 列がふえたとき（例：記録に「支払方法」）は、今のデータを新しい列の順に並べなおす（データは消えない）
        values = ws.get_all_values()
        cols = TABLES[name]
        if values and values[0] != cols:
            head = values[0]
            rows = [[(r[head.index(c)] if c in head and head.index(c) < len(r) else "") for c in cols] for r in values[1:] if any(r)]
            ws.clear()
            ws.update([cols] + rows, "A1")
        _CHECKED.add(name)
    _memo()["ws"][name] = ws
    return ws


def _clean(name, rows):
    """写しに入れる形（すべて文字。スプレッドシートから読んだときと同じ形）"""
    cols = TABLES[name]
    return [{c: ("" if r.get(c) is None else str(r.get(c))) for c in cols} for r in rows]


def _read(name):
    cols = TABLES[name]
    if using_sheets():
        rows = _sheet(name).get_all_values()
    else:
        path = LOCAL_DIR / f"{name}.csv"
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as f:
            rows = list(csv.reader(f))
    if not rows:
        return []
    head = rows[0]
    return [{c: (r[head.index(c)] if c in head and head.index(c) < len(r) else "") for c in cols} for r in rows[1:] if any(r)]


def load(name):
    """表の中身（dict の一覧）。写しがあれば、それを使う（Google に問い合わせない）"""
    m = _memo()
    if name not in m["rows"] or time.time() - m["at"].get(name, 0) > CACHE_SECONDS:
        m["rows"][name] = _read(name)
        m["at"][name] = time.time()
    return [dict(r) for r in m["rows"][name]]


def _keep(name, rows):
    m = _memo()
    m["rows"][name] = rows
    m["at"][name] = time.time()


def save(name, rows):
    """表をまるごと書きかえる（書きこみは1回。その表の写しも差しかえる）"""
    cols = TABLES[name]
    rows = _clean(name, rows)
    values = [cols] + [[r[c] for c in cols] for r in rows]
    m = _memo()
    with m["lock"]:
        if using_sheets():
            ws = _sheet(name)
            before = m["rows"].get(name)
            if before is not None and len(before) > len(rows):        # 前より短くなった分は、空の行で上書き（消す問い合わせをしない）
                values += [[""] * len(cols) for _ in range(len(before) - len(rows))]
            if before is None:                                        # 前の長さがわからないときだけ、消してから書く
                ws.clear()
            ws.update(values, "A1", value_input_option="RAW")
        else:
            LOCAL_DIR.mkdir(exist_ok=True)
            with (LOCAL_DIR / f"{name}.csv").open("w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerows(values)
        _keep(name, rows)


def append(name, row):
    """1行たす（ID と登録日時は自動）"""
    row = dict(row)
    if "ID" in TABLES[name] and not row.get("ID"):
        row["ID"] = uuid.uuid4().hex[:10]
    if "登録日時" in TABLES[name]:
        row["登録日時"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    if using_sheets():
        current = load(name)                                          # 写し（たいていは問い合わせなし）
        m = _memo()
        with m["lock"]:
            _sheet(name).append_row([("" if row.get(c) is None else str(row.get(c))) for c in TABLES[name]], value_input_option="RAW")
            _keep(name, _clean(name, current) + _clean(name, [row]))
    else:
        save(name, load(name) + [row])
    return row
