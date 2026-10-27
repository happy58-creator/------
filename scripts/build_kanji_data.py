"""漢字の練習データ（学年・読み・意味・書き順の線）を作る。1回だけ実行すればよい。

  python3 scripts/build_kanji_data.py [kanjidic2.xml.gz] [kanjivg.xml.gz]

  - 学年・読み・意味：KANJIDIC2（EDRDG, CC BY-SA 4.0）  https://www.edrdg.org/kanjidic/kanjd2index.html
  - 書き順の線：KanjiVG（CC BY-SA 3.0）                https://kanjivg.tagaini.net
ファイルを指定しなければ、上の配布元から自動でダウンロードする。
出力：data/kanji.json（小学校で習う漢字 1〜6年生）
"""
import gzip
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

KANJIDIC_URL = "https://www.edrdg.org/kanjidic/kanjidic2.xml.gz"
KANJIVG_URL = "https://github.com/KanjiVG/kanjivg/releases/download/r20260714/kanjivg-20260714.xml.gz"
GRADES = {1, 2, 3, 4, 5, 6}
OUT = Path(__file__).resolve().parent.parent / "data" / "kanji.json"


def read_gz(path_or_url):
    if str(path_or_url).startswith("http"):
        req = urllib.request.Request(path_or_url, headers={"User-Agent": "kyouzai-kanji-data-builder/1.0"})
        raw = urllib.request.urlopen(req, timeout=300).read()
    else:
        raw = Path(path_or_url).read_bytes()
    return gzip.decompress(raw)


def kun_text(reading):
    """「あ.ける」→「あ（ける）」、「-がわ」→「がわ」"""
    reading = reading.lstrip("-")
    if "." in reading:
        stem, tail = reading.split(".", 1)
        return f"{stem}（{tail.rstrip('-')}）"
    return reading.rstrip("-")


def main():
    dic_src = sys.argv[1] if len(sys.argv) > 1 else KANJIDIC_URL
    vg_src = sys.argv[2] if len(sys.argv) > 2 else KANJIVG_URL

    info = {}
    for ch in ET.fromstring(read_gz(dic_src)).iter("character"):
        grade = ch.findtext("misc/grade")
        if not grade or int(grade) not in GRADES:
            continue
        rm = ch.find("reading_meaning/rmgroup")
        kun = [kun_text(r.text) for r in rm.findall("reading[@r_type='ja_kun']")] if rm is not None else []
        on = [r.text for r in rm.findall("reading[@r_type='ja_on']")] if rm is not None else []
        meanings = [m.text for m in rm.findall("meaning") if not m.attrib] if rm is not None else []
        info[ch.findtext("literal")] = {"g": int(grade), "k": kun[:3], "o": on[:3], "m": meanings[:3]}
    print("KANJIDIC2：小学校の漢字", len(info), "字")

    strokes = {}
    for k in ET.fromstring(read_gz(vg_src)).iter("kanji"):
        ch = chr(int(k.get("id").split("_")[-1], 16))  # kvg:kanji_05c71 → 山
        if ch in info:
            strokes[ch] = [p.get("d") for p in k.iter("path") if p.get("d")]
    print("KanjiVG：書き順つき", len(strokes), "字")

    data = {}
    for ch, entry in info.items():
        if strokes.get(ch):
            entry["n"] = len(strokes[ch])
            entry["s"] = strokes[ch]
            data[ch] = entry
    missing = sorted(set(info) - set(data))
    print("データができた漢字", len(data), "字 / 書き順なし", missing)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("保存", OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
