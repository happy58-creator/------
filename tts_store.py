"""単語の AI 読み上げ（Gemini の TTS）。作った声は スプレッドシートの「声」タブに 保存して 使い回す。
- 読み上げモデルは 1日の回数が 少ない（1モデル 10回くらい）ので、10語を まとめて 1回で 読ませて、無音の所で 1語ずつに 切る。
- 一度 作った単語は、だれが 使っても 保存した声を そのまま 使う（回数を 使わない）。
- 作れないとき（回数切れ・切り分け失敗）は 何も 返さない → 画面は ブラウザの声に もどる。
「声」タブ：キー（単語の小文字|声の名前）・形式・音（data URL）・日時"""
import base64
import io
import re
import time
import wave

import numpy as np

import common
import history

SHEET = "声"
COLS = ["キー", "形式", "音", "日時"]
VOICE = "Achird"            # Friendly（やさしい 声）
TTS_MODELS = ["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]
MAX_WORDS = 10
CELL_MAX = 48000
OUT_RATE = 16000

_mem = {}                   # キー → data URL（このサーバーが 動いている間）
_index = {"t": 0, "rows": {}}   # キー → 行番号（スプレッドシート）


def key_of(word):
    return f"{re.sub(r'\s+', ' ', str(word).strip().lower())}|{VOICE}"


# ---------------------------------------------------------------- 置き場
def _ws():
    book = history._spreadsheet()
    if book is None:
        return None
    import gspread
    try:
        return book.worksheet(SHEET)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=SHEET, rows=500, cols=len(COLS))
        ws.append_row(COLS)
        return ws


def _rows(ws, fresh=False):
    if fresh or time.time() - _index["t"] > 600:
        col = ws.col_values(1)
        _index["rows"] = {k: i + 1 for i, k in enumerate(col) if i and k}
        _index["t"] = time.time()
    return _index["rows"]


def cached(words):
    """{単語: data URL}（保存してある分だけ）"""
    out, need = {}, {}
    for w in words:
        k = key_of(w)
        if k in _mem:
            out[w] = _mem[k]
        else:
            need[k] = w
    if not need:
        return out
    try:
        ws = _ws()
        if ws is None:
            return out
        rows = _rows(ws)
        hit = [(k, rows[k]) for k in need if k in rows]
        if hit:
            vals = ws.batch_get([f"C{r}" for _, r in hit])
            for (k, _), v in zip(hit, vals):
                url = (v[0][0] if v and v[0] else "")
                if url.startswith("data:audio"):
                    _mem[k] = url
                    out[need[k]] = url
    except Exception as e:
        print(f"[声] 読みこみ: {type(e).__name__}: {e}", flush=True)
    return out


def _save(pairs):
    for k, url in pairs:
        _mem[k] = url
    try:
        ws = _ws()
        if ws is None:
            return
        rows = _rows(ws, fresh=True)
        new = [[k, "audio/wav", url, time.strftime("%Y-%m-%d %H:%M:%S")] for k, url in pairs if k not in rows]
        if new:
            ws.append_rows(new, value_input_option="RAW")
            _index["t"] = 0
    except Exception as e:
        print(f"[声] 保存: {type(e).__name__}: {e}", flush=True)


# ---------------------------------------------------------------- 音の 切り分け
def _split(pcm, rate, n):
    """続けて 読んだ 音を、無音の 長い所 n-1 か所で 切って n個にする。うまく 切れなければ None"""
    x = pcm.astype(np.float32)
    fr = max(1, rate // 100)                                  # 10ms ごとの 音の大きさ
    m = len(x) // fr
    if m < n * 10:
        return None
    rms = np.sqrt((x[: m * fr].reshape(m, fr) ** 2).mean(axis=1))
    thr = max(250.0, float(np.percentile(rms, 95)) * 0.06)
    loud = rms > thr
    idx = np.flatnonzero(loud)
    if not len(idx):
        return None
    a, b = idx[0], idx[-1]
    gaps, i = [], a                                          # 声と声の あいだの 無音（はじまり, 長さ）
    while i <= b:
        if not loud[i]:
            j = i
            while j <= b and not loud[j]:
                j += 1
            gaps.append((i, j - i))
            i = j
        else:
            i += 1
    if len(gaps) < n - 1:
        return None
    gaps.sort(key=lambda g: -g[1])
    cut, rest = gaps[: n - 1], gaps[n - 1:]
    if n > 1 and (min(g[1] for g in cut) < 25 or (rest and rest[0][1] > min(g[1] for g in cut) * 0.8)):
        return None                                           # 語と語の 間が はっきりしない
    bounds = [a] + sorted(s + l // 2 for s, l in cut) + [b + 1]
    out = []
    for s, e in zip(bounds, bounds[1:]):
        seg = loud[s:e]
        on = np.flatnonzero(seg)
        if not len(on):
            return None
        s2, e2 = s + on[0], s + on[-1] + 1
        lo, hi = max(0, (s2 - 8) * fr), min(len(x), (e2 + 10) * fr)   # 前 80ms・後ろ 100ms の 余白
        out.append(x[lo:hi])
    return out


def _wav_url(seg, rate):
    for out_rate in (OUT_RATE, 12000):
        k = int(len(seg) * out_rate / rate)
        y = np.interp(np.linspace(0, len(seg) - 1, k), np.arange(len(seg)), seg) if k > 1 else seg
        f = min(len(y) // 4, int(out_rate * 0.01))
        if f > 1:
            y[:f] *= np.linspace(0, 1, f)
            y[-f:] *= np.linspace(1, 0, f)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(out_rate)
            w.writeframes(np.clip(y, -32768, 32767).astype("<i2").tobytes())
        url = "data:audio/wav;base64," + base64.b64encode(buf.getvalue()).decode()
        if len(url) <= CELL_MAX:
            return url
    return None


# ---------------------------------------------------------------- 作る
def _make(words):
    from google.genai import types
    lines = "\n".join(f"{w}." for w in words)
    prompt = ("Synthesize speech only. This is a list of English words for a children's English class.\n"
              "Director's notes: a friendly, clear American English teacher. Say each word exactly once, in order, "
              "at a natural, slightly slow pace. Leave a long pause (about one second) after every word. "
              "Do not say anything else.\n\nTranscript:\n" + lines)
    client = common.get_gemini_client()
    res = client.models.generate_content(
        model=TTS_MODELS, contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)))))
    part = next(p for p in res.candidates[0].content.parts if getattr(p, "inline_data", None))
    data, mime = part.inline_data.data, part.inline_data.mime_type or ""
    if isinstance(data, str):
        data = base64.b64decode(data)
    m = re.search(r"rate=(\d+)", mime)
    rate = int(m.group(1)) if m else 24000
    if data[:4] == b"RIFF":                                   # WAV で 来たとき
        with wave.open(io.BytesIO(data)) as w:
            rate, data = w.getframerate(), w.readframes(w.getnframes())
    pcm = np.frombuffer(data, dtype="<i2")
    segs = _split(pcm, rate, len(words))
    if segs is None:
        print(f"[声] 切り分けに 失敗（{len(words)}語）", flush=True)
        return {}
    return {w: u for w, u in ((w, _wav_url(s, rate)) for w, s in zip(words, segs)) if u}


def voices(words):
    """{単語: data URL}。保存してある声＋ 足りない分を AI で 作る（1回）。作れなくても エラーに しない"""
    words = list(dict.fromkeys(str(w).strip() for w in words if str(w).strip() and len(str(w)) <= 40))[:MAX_WORDS]
    out = cached(words)
    need = [w for w in words if w not in out]
    if not need:
        return out
    try:
        made = _make(need)
    except Exception as e:
        print(f"[声] 作れなかった: {type(e).__name__}: {str(e)[:200]}", flush=True)
        made = {}
    if made:
        _save([(key_of(w), u) for w, u in made.items()])
        out.update(made)
    return out
