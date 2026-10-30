"""算数・数学の問題をプログラムで作る（答えはかならず正しい）。

1つの単元＝問題を1問作る関数。返す形：
  {"q": 問題文（markdown・$...$ で数式）, "spec": 答え合わせの形（math_check.check へ）,
   "show": 正しい答え（表示用）, "explain": 解き方, "hint": 答えの書き方（あれば）}
"""
import cmath
import math
from fractions import Fraction as Fr

# ---------------------------------------------------------------------------
# 表示の小物
# ---------------------------------------------------------------------------


def ftex(v):
    """分数・整数を TeX に"""
    v = Fr(v)
    if v.denominator == 1:
        return str(v.numerator)
    sign = "-" if v < 0 else ""
    return rf"{sign}\frac{{{abs(v.numerator)}}}{{{v.denominator}}}"


def ftxt(v):
    v = Fr(v)
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"


def dec(v, nd=3):
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def poly(coefs, var="x"):
    """[a_n, ..., a_0]（高い次数から）→ TeX"""
    n = len(coefs) - 1
    out = ""
    for i, c in enumerate(coefs):
        p = n - i
        c = Fr(c)
        if c == 0:
            continue
        sign = "-" if c < 0 else "+"
        a = abs(c)
        body = ftex(a) if (a != 1 or p == 0) else ""
        if p >= 1:
            body += var + (f"^{{{p}}}" if p > 1 else "")
        out += (("-" if sign == "-" else "") if not out else f" {sign} ") + body
    return out or "0"


def ptxt(coefs, var="x"):
    """答えの表示用（ふつうの文字）"""
    return poly(coefs, var).replace("^{", "^").replace("}", "").replace(r"\frac{", "").replace("{", "/")


def lin(a, b, var="x"):
    return poly([a, b], var)


def num(value, **kw):
    return {"type": "num", "value": complex(value), **kw}


def R(rng, a, b, nonzero=False):
    while True:
        v = rng.randint(a, b)
        if not (nonzero and v == 0):
            return v


HINT_FRAC = "分数は 3/4 のように書いてね（約分してね）"
HINT_SQRT = "ルートは √3、2√3 のように書いてね（ルートの中はいちばん小さく）"

# ---------------------------------------------------------------------------
# 小学校（算数）
# ---------------------------------------------------------------------------


def g_add1(rng):
    a, b = R(rng, 2, 9), R(rng, 2, 9)
    while a + b < 11:
        a, b = R(rng, 2, 9), R(rng, 2, 9)
    return {"q": f"$${a} + {b}$$", "spec": num(a + b), "show": str(a + b),
            "explain": f"{a} に あと {10 - a} で 10。{b} を {10 - a} と {b - (10 - a)} にわけて、10 と {b - (10 - a)} で {a + b}。"}


def g_sub1(rng):
    a, b = R(rng, 11, 18), R(rng, 2, 9)
    while a - b >= 10 or a % 10 >= b:
        a, b = R(rng, 11, 18), R(rng, 2, 9)
    return {"q": f"$${a} - {b}$$", "spec": num(a - b), "show": str(a - b),
            "explain": f"10 から {b} をひくと {10 - b}。それと のこりの {a - 10} で {a - b}。"}


def g_add2(rng):
    if rng.random() < 0.5:
        a, b = R(rng, 15, 89), R(rng, 15, 89)
        return {"q": f"$${a} + {b}$$", "spec": num(a + b), "show": str(a + b), "explain": "一の位から 順に たし、10 をこえたら 十の位に 1 くり上げる。"}
    a = R(rng, 30, 99)
    b = R(rng, 11, a - 5)
    return {"q": f"$${a} - {b}$$", "spec": num(a - b), "show": str(a - b), "explain": "一の位から 順に ひき、ひけないときは 十の位から 1 くり下げる。"}


def g_kuku(rng):
    a, b = R(rng, 2, 9), R(rng, 2, 9)
    return {"q": rf"$${a} \times {b}$$", "spec": num(a * b), "show": str(a * b), "explain": f"{a}のだんの九九：{a}×{b}＝{a * b}"}


def g_unit2(rng):
    t = rng.randint(0, 2)
    if t == 0:
        a, b = R(rng, 1, 15), R(rng, 1, 9)
        return {"q": f"{a}cm{b}mm は 何mm？", "spec": num(a * 10 + b), "show": f"{a * 10 + b}mm", "explain": "1cm＝10mm。"}
    if t == 1:
        a, b = R(rng, 1, 9), R(rng, 1, 9)
        return {"q": f"{a}L{b}dL は 何dL？", "spec": num(a * 10 + b), "show": f"{a * 10 + b}dL", "explain": "1L＝10dL。"}
    a, b = R(rng, 1, 9), R(rng, 1, 99)
    return {"q": f"{a}m{b}cm は 何cm？", "spec": num(a * 100 + b), "show": f"{a * 100 + b}cm", "explain": "1m＝100cm。"}


def g_div3(rng):
    b, c = R(rng, 2, 9), R(rng, 1, 9)
    return {"q": rf"$${b * c} \div {b}$$", "spec": num(c), "show": str(c), "explain": f"{b}のだんの九九で、{b}×□＝{b * c} の □ をさがす。"}


def g_divr(rng):
    b, c = R(rng, 2, 9), R(rng, 1, 9)
    r = R(rng, 1, b - 1)
    a = b * c + r
    return {"q": rf"$${a} \div {b}$$（あまりも 答えよう）", "spec": {"type": "divmod", "value": (c, r)}, "show": f"{c}あまり{r}",
            "explain": f"{b}×{c}＝{b * c}、{a}−{b * c}＝{r}。あまり {r} は わる数 {b} より小さい。", "hint": "「7あまり2」のように書いてね"}


def g_mul3(rng):
    if rng.random() < 0.5:
        a, b = R(rng, 101, 999), R(rng, 2, 9)
    else:
        a, b = R(rng, 12, 99), R(rng, 12, 99)
    return {"q": rf"$${a} \times {b}$$", "spec": num(a * b), "show": str(a * b), "explain": "筆算で、位ごとにかけて たす。"}


def g_dec3(rng):
    a, b = R(rng, 11, 99), R(rng, 11, 99)
    if rng.random() < 0.5:
        return {"q": f"$${a / 10} + {b / 10}$$", "spec": num((a + b) / 10), "show": dec((a + b) / 10), "explain": "小数点の位置をそろえて、整数と同じように たす。"}
    a, b = max(a, b), min(a, b)
    return {"q": f"$${a / 10} - {b / 10}$$", "spec": num((a - b) / 10), "show": dec((a - b) / 10), "explain": "小数点の位置をそろえて、整数と同じように ひく。"}


def g_frac3(rng):
    d = R(rng, 5, 12)
    a, b = R(rng, 1, d - 2), 0
    b = R(rng, 1, d - 1 - a)
    if rng.random() < 0.5:
        return {"q": rf"$$\frac{{{a}}}{{{d}}} + \frac{{{b}}}{{{d}}}$$", "spec": num((a + b) / d), "show": f"{a + b}/{d}",
                "explain": "分母が同じなので、分子どうしを たす。", "hint": "分数は 3/4 のように書いてね"}
    a, b = max(a, b) + 1, min(a, b)
    return {"q": rf"$$\frac{{{a}}}{{{d}}} - \frac{{{b}}}{{{d}}}$$", "spec": num((a - b) / d), "show": f"{a - b}/{d}",
            "explain": "分母が同じなので、分子どうしを ひく。", "hint": "分数は 3/4 のように書いてね"}


def g_div4(rng):
    if rng.random() < 0.5:
        b, c = R(rng, 2, 9), R(rng, 12, 99)
    else:
        b, c = R(rng, 12, 39), R(rng, 3, 29)
    return {"q": rf"$${b * c} \div {b}$$", "spec": num(c), "show": str(c), "explain": "筆算で、上の位から 商をたてて かける → ひく → おろす をくり返す。"}


def g_round(rng):
    n = R(rng, 1001, 99999)
    place = rng.choice([(10, "十"), (100, "百"), (1000, "千")])
    p, name = place
    if n < p * 10:
        n += p * 10
    ans = int(math.floor(n / p + 0.5)) * p
    return {"q": f"{n} を 四捨五入して、{name}の位までの がい数に しよう。", "spec": num(ans), "show": str(ans),
            "explain": f"{name}の位の 1つ下の位が 5以上なら切り上げ、4以下なら切り捨てる。"}


def g_area4(rng):
    if rng.random() < 0.3:
        a = R(rng, 3, 15)
        return {"q": f"1辺が {a}cm の 正方形の面積は？", "spec": num(a * a), "show": f"{a * a}cm²", "explain": "正方形の面積＝1辺×1辺。"}
    a, b = R(rng, 3, 20), R(rng, 3, 20)
    return {"q": f"たて {a}cm、横 {b}cm の 長方形の面積は？", "spec": num(a * b), "show": f"{a * b}cm²", "explain": "長方形の面積＝たて×横。"}


def g_decint(rng):
    a, b = R(rng, 11, 99), R(rng, 2, 9)
    if rng.random() < 0.5:
        return {"q": rf"$${a / 10} \times {b}$$", "spec": num(a * b / 10), "show": dec(a * b / 10), "explain": f"{a}×{b}＝{a * b} を計算して、小数点を1つ左へ。"}
    return {"q": rf"$${a * b / 10} \div {b}$$", "spec": num(a / 10), "show": dec(a / 10), "explain": f"{a * b}÷{b}＝{a} を計算して、小数点を1つ左へ。"}


def g_decdec(rng):
    a, b = R(rng, 11, 99), R(rng, 11, 49)
    if rng.random() < 0.5:
        return {"q": rf"$${a / 10} \times {b / 10}$$", "spec": num(a * b / 100), "show": dec(a * b / 100),
                "explain": f"{a}×{b}＝{a * b}。小数点以下のけたは 1＋1＝2けた なので {dec(a * b / 100)}。"}
    return {"q": rf"$${dec(a * b / 100)} \div {b / 10}$$", "spec": num(a / 10), "show": dec(a / 10),
            "explain": "わる数を整数にするため、わられる数とわる数の 小数点を同じだけ右へ動かしてから計算する。"}


def g_fracadd(rng):
    while True:
        b, d = R(rng, 2, 9), R(rng, 2, 9)
        if b == d:
            continue
        a, c = R(rng, 1, b - 1), R(rng, 1, d - 1)
        x, y = Fr(a, b), Fr(c, d)
        op = rng.choice("+-")
        if op == "-" and x <= y:
            x, y = y, x
        ans = x + y if op == "+" else x - y
        if ans > 0:
            break
    l = b * d // math.gcd(b, d)
    return {"q": rf"$${ftex(x)} {op} {ftex(y)}$$", "spec": num(ans, reduce=True), "show": ftxt(ans),
            "explain": f"分母を {l} にそろえて（通分して）から計算し、さいごに約分する。", "hint": HINT_FRAC}


def g_percent(rng):
    t = rng.randint(0, 2)
    base = rng.choice([20, 40, 50, 80, 120, 200, 250, 400, 500, 800])
    p = rng.choice([10, 15, 20, 25, 30, 40, 60, 75])
    part = base * p // 100
    if base * p % 100:
        part = base * p / 100
    if t == 0:
        return {"q": f"{base}人の {p}% は 何人？", "spec": num(part), "show": f"{dec(part)}人", "explain": f"くらべる量＝もとにする量×割合＝{base}×{p / 100}。"}
    if t == 1:
        return {"q": f"{dec(part)} は {base} の 何%？", "spec": num(p), "show": f"{p}%", "explain": f"割合＝くらべる量÷もとにする量＝{dec(part)}÷{base}＝{p / 100}。百分率にすると {p}%。"}
    return {"q": f"ある数の {p}% が {dec(part)} です。ある数は？", "spec": num(base), "show": str(base), "explain": f"もとにする量＝くらべる量÷割合＝{dec(part)}÷{p / 100}。"}


def g_average(rng):
    n = rng.randint(4, 6)
    avg = R(rng, 5, 80)
    vals = [avg + rng.randint(-6, 6) for _ in range(n - 1)]
    vals.append(avg * n - sum(vals))
    if vals[-1] <= 0:
        vals[-1] += n
        avg = sum(vals) / n
    s = "、".join(str(v) for v in vals)
    return {"q": f"{s} の 平均は？", "spec": num(sum(vals) / n), "show": dec(sum(vals) / n, 2), "explain": f"平均＝合計÷個数＝{sum(vals)}÷{n}。"}


def g_area5(rng):
    t = rng.randint(0, 2)
    a, h = R(rng, 3, 16), R(rng, 3, 16)
    if t == 0:
        return {"q": f"底辺 {a}cm、高さ {h}cm の 三角形の面積は？", "spec": num(a * h / 2), "show": f"{dec(a * h / 2)}cm²", "explain": "三角形の面積＝底辺×高さ÷2。"}
    if t == 1:
        return {"q": f"底辺 {a}cm、高さ {h}cm の 平行四辺形の面積は？", "spec": num(a * h), "show": f"{a * h}cm²", "explain": "平行四辺形の面積＝底辺×高さ。"}
    b = R(rng, 3, 16)
    return {"q": f"上底 {a}cm、下底 {b}cm、高さ {h}cm の 台形の面積は？", "spec": num((a + b) * h / 2), "show": f"{dec((a + b) * h / 2)}cm²",
            "explain": "台形の面積＝（上底＋下底）×高さ÷2。"}


def g_volume(rng):
    if rng.random() < 0.3:
        a = R(rng, 2, 12)
        return {"q": f"1辺が {a}cm の 立方体の体積は？", "spec": num(a ** 3), "show": f"{a ** 3}cm³", "explain": "立方体の体積＝1辺×1辺×1辺。"}
    a, b, c = R(rng, 2, 12), R(rng, 2, 12), R(rng, 2, 12)
    return {"q": f"たて {a}cm、横 {b}cm、高さ {c}cm の 直方体の体積は？", "spec": num(a * b * c), "show": f"{a * b * c}cm³", "explain": "直方体の体積＝たて×横×高さ。"}


def g_speed(rng):
    v, t = rng.choice([4, 5, 6, 12, 15, 40, 45, 50, 60, 80]), R(rng, 2, 6)
    d = v * t
    k = rng.randint(0, 2)
    if k == 0:
        return {"q": f"時速 {v}km で {t}時間 進むと、何km 進む？", "spec": num(d), "show": f"{d}km", "explain": "道のり＝速さ×時間。"}
    if k == 1:
        return {"q": f"{d}km を {t}時間 で進む速さは 時速何km？", "spec": num(v), "show": f"時速{v}km", "explain": "速さ＝道のり÷時間。"}
    return {"q": f"{d}km を 時速 {v}km で進むと、何時間 かかる？", "spec": num(t), "show": f"{t}時間", "explain": "時間＝道のり÷速さ。"}


def g_fracmul(rng):
    while True:
        x = Fr(R(rng, 1, 9), R(rng, 2, 9))
        y = Fr(R(rng, 1, 9), R(rng, 2, 9))
        if x.denominator > 1 and y.denominator > 1:
            break
    if rng.random() < 0.5:
        ans = x * y
        return {"q": rf"$${ftex(x)} \times {ftex(y)}$$", "spec": num(ans, reduce=True), "show": ftxt(ans),
                "explain": "分子どうし・分母どうしを かける（とちゅうで約分すると楽）。", "hint": HINT_FRAC}
    ans = x / y
    return {"q": rf"$${ftex(x)} \div {ftex(y)}$$", "spec": num(ans, reduce=True), "show": ftxt(ans),
            "explain": f"わる数の 逆数（{ftxt(1 / y)}）を かける。", "hint": HINT_FRAC}


def g_ratio(rng):
    a, b, k = R(rng, 1, 9), R(rng, 1, 9), R(rng, 2, 9)
    while math.gcd(a, b) != 1 or a == b:
        a, b = R(rng, 1, 9), R(rng, 1, 9)
    if rng.random() < 0.5:
        return {"q": f"$${a}:{b} = {a * k}:x$$ の x は？", "spec": num(b * k), "show": str(b * k), "explain": f"{a}を{k}倍すると{a * k}。同じように {b}×{k}。"}
    return {"q": f"$${a * k}:{b * k}$$ を いちばん簡単な比に しよう。", "spec": {"type": "point", "value": (a, b)}, "show": f"{a}:{b}",
            "explain": f"両方を最大公約数 {k} でわる。", "hint": "「2:3」や「(2,3)」のように書いてね", "ratio": True}


def g_circle(rng):
    r = R(rng, 2, 12)
    if rng.random() < 0.5:
        return {"q": f"半径 {r}cm の 円の面積は？（円周率は 3.14）", "spec": num(r * r * 3.14), "show": f"{dec(r * r * 3.14, 2)}cm²", "explain": "円の面積＝半径×半径×3.14。"}
    return {"q": f"直径 {2 * r}cm の 円の まわりの長さは？（円周率は 3.14）", "spec": num(2 * r * 3.14), "show": f"{dec(2 * r * 3.14, 2)}cm", "explain": "円周＝直径×3.14。"}


def g_propo(rng):
    a = R(rng, 2, 9)
    x1, x2 = R(rng, 1, 6), R(rng, 7, 12)
    if rng.random() < 0.5:
        return {"q": f"y は x に比例し、x＝{x1} のとき y＝{a * x1} です。x＝{x2} のときの y は？", "spec": num(a * x2), "show": str(a * x2),
                "explain": f"y＝きまった数×x。きまった数は {a * x1}÷{x1}＝{a}。"}
    k = a * x1 * x2
    return {"q": f"y は x に反比例し、x＝{x1} のとき y＝{k // x1} です。x＝{x2} のときの y は？", "spec": num(k / x2, reduce=True),
            "show": ftxt(Fr(k, x2)), "explain": f"x×y＝きまった数＝{k}。y＝{k}÷{x2}。", "hint": HINT_FRAC}


# ---------------------------------------------------------------------------
# 中学校（数学）
# ---------------------------------------------------------------------------


def _signed(v):
    return f"({v})" if v < 0 else str(v)


def g_posneg(rng):
    t = rng.randint(0, 3)
    a, b, c = R(rng, -12, 12, True), R(rng, -12, 12, True), R(rng, -9, 9, True)
    if t == 0:
        ans = a + b - c
        return {"q": f"$${a} + {_signed(b)} - {_signed(c)}$$", "spec": num(ans), "show": str(ans), "explain": "ひく数は 符号を変えて たす。"}
    if t == 1:
        ans = a * b
        return {"q": rf"$${_signed(a)} \times {_signed(b)}$$", "spec": num(ans), "show": str(ans), "explain": "同じ符号の積は＋、ちがう符号の積は−。"}
    if t == 2:
        return {"q": rf"$${_signed(a * b)} \div {_signed(b)}$$", "spec": num(a), "show": str(a), "explain": "同じ符号の商は＋、ちがう符号の商は−。"}
    p = rng.choice([2, 3])
    base = R(rng, -5, -2)
    ans = base ** p + a
    return {"q": f"$$({base})^{p} + {_signed(a)}$$", "spec": num(ans), "show": str(ans), "explain": f"累乗を先に計算：({base})^{p}＝{base ** p}。"}


def g_moji(rng):
    a, b, c, d = R(rng, -9, 9, True), R(rng, -9, 9, True), R(rng, -9, 9, True), R(rng, -9, 9, True)
    k = R(rng, 2, 5)
    if rng.random() < 0.5:
        A, B = a + c, b + d
        return {"q": f"$$({lin(a, b)}) + ({lin(c, d)})$$", "spec": {"type": "expr", "value": lambda x, A=A, B=B: A * x + B, "form": "expanded"},
                "show": ptxt([A, B]), "explain": "かっこをはずして、x の項どうし・数の項どうしをまとめる。", "hint": "2x+3 のように書いてね"}
    A, B = k * a - c, k * b - d
    return {"q": f"$${k}({lin(a, b)}) - ({lin(c, d)})$$", "spec": {"type": "expr", "value": lambda x, A=A, B=B: A * x + B, "form": "expanded"},
            "show": ptxt([A, B]), "explain": "分配法則でかっこをはずす（−( ) は符号が全部変わる）。", "hint": "2x+3 のように書いてね"}


def g_lineq(rng):
    x = R(rng, -9, 9)
    a, c = R(rng, -9, 9, True), R(rng, -9, 9, True)
    while a == c:
        c = R(rng, -9, 9, True)
    b = R(rng, -15, 15)
    d = a * x + b - c * x
    return {"q": f"$${lin(a, b)} = {lin(c, d)}$$ を解こう。", "spec": num(x), "show": f"x={x}",
            "explain": f"x の項を左、数を右へ移項：{a - c}x＝{d - b}、x＝{x}。", "hint": "x=3 のように書いてね"}


def g_hirei(rng):
    a = R(rng, -6, 6, True)
    x = R(rng, -5, 5, True)
    if rng.random() < 0.5:
        return {"q": f"y は x に比例し、x＝{x} のとき y＝{a * x} です。y を x の式で表そう。",
                "spec": {"type": "expr", "value": lambda t, a=a: a * t}, "show": f"y={ptxt([a, 0])}", "explain": f"y＝ax に代入：{a * x}＝a×({x})、a＝{a}。", "hint": "y=3x のように書いてね"}
    k = a * x
    return {"q": f"y は x に反比例し、x＝{x} のとき y＝{a} です。y を x の式で表そう。",
            "spec": {"type": "expr", "value": lambda t, k=k: k / t}, "show": f"y={k}/x", "explain": f"y＝a/x に代入：a＝xy＝{k}。", "hint": "y=6/x のように書いてね"}


def g_siki2(rng):
    t = rng.randint(0, 1)
    if t == 0:
        a, b, c, d = R(rng, -9, 9, True), R(rng, -9, 9, True), R(rng, -9, 9, True), R(rng, -9, 9, True)
        A, B = a + c, b + d
        return {"q": f"$$({poly([a, b, 0])}) - ({poly([-c, -d, 0])})$$",
                "spec": {"type": "expr", "value": lambda x, A=A, B=B: A * x * x + B * x, "form": "expanded"}, "show": ptxt([A, B, 0]),
                "explain": "−( ) は符号を変えてかっこをはずし、同類項をまとめる。", "hint": "3x^2-2x のように書いてね"}
    a, b, c = R(rng, 2, 9), R(rng, 2, 6), R(rng, 2, 6)
    return {"q": rf"$${a * b}x^{{3}} \div {a}x$$", "spec": {"type": "expr", "value": lambda x, k=b: k * x * x}, "show": f"{b}x^2",
            "explain": f"係数は {a * b}÷{a}＝{b}、文字は x³÷x＝x²。", "hint": "3x^2 のように書いてね"}


def g_simul(rng):
    x, y = R(rng, -6, 6), R(rng, -6, 6)
    while True:
        a, b, c, d = R(rng, -5, 5, True), R(rng, -5, 5, True), R(rng, -5, 5, True), R(rng, -5, 5, True)
        if a * d - b * c != 0:
            break
    e, f = a * x + b * y, c * x + d * y

    def eq(p, q, r):
        return f"{lin(p, 0)} {'+' if q > 0 else '-'} {abs(q) if abs(q) != 1 else ''}y = {r}"
    return {"q": rf"$$\begin{{cases}} {eq(a, b, e)} \\ {eq(c, d, f)} \end{{cases}}$$ を解こう。",
            "spec": {"type": "point", "value": (x, y)}, "show": f"x={x}, y={y}",
            "explain": "加減法（どちらかの文字の係数をそろえてたす・ひく）か、代入法で1つの文字を消す。", "hint": "x=1, y=2 のように書いてね"}


def g_linfunc(rng):
    a, b = R(rng, -5, 5, True), R(rng, -9, 9)
    x1, x2 = R(rng, -4, 0), R(rng, 1, 5)
    return {"q": f"2点 ({x1}, {a * x1 + b})、({x2}, {a * x2 + b}) を通る 直線の式は？",
            "spec": {"type": "expr", "value": lambda x, a=a, b=b: a * x + b}, "show": f"y={ptxt([a, b])}",
            "explain": f"傾き＝yの増加量÷xの増加量＝{a * (x2 - x1)}÷{x2 - x1}＝{a}。y＝{a}x＋b に1点を代入して b＝{b}。", "hint": "y=2x+3 のように書いてね"}


def g_angle(rng):
    n = R(rng, 5, 12)
    if rng.random() < 0.5:
        return {"q": f"{n}角形の 内角の和は 何度？", "spec": num(180 * (n - 2)), "show": f"{180 * (n - 2)}°", "explain": f"内角の和＝180°×(n−2)＝180×{n - 2}。"}
    n = rng.choice([5, 6, 8, 9, 10, 12, 15, 18, 20])
    return {"q": f"正{n}角形の 1つの外角は 何度？", "spec": num(Fr(360, n)), "show": f"{ftxt(Fr(360, n))}°", "explain": f"外角の和はいつも 360°。360÷{n}。"}


def g_prob2(rng):
    t = rng.randint(0, 2)
    if t == 0:
        s = R(rng, 3, 11)
        cnt = sum(1 for i in range(1, 7) for j in range(1, 7) if i + j == s)
        p = Fr(cnt, 36)
        return {"q": f"大小2つのさいころを投げるとき、出た目の和が {s} になる確率は？", "spec": num(p, reduce=True), "show": ftxt(p),
                "explain": f"目の出方は全部で 36通り。和が {s} になるのは {cnt}通り。", "hint": HINT_FRAC}
    if t == 1:
        cnt = sum(1 for i in range(1, 7) for j in range(1, 7) if (i * j) % 2 == 0)
        p = Fr(cnt, 36)
        return {"q": "大小2つのさいころを投げるとき、出た目の積が 偶数になる確率は？", "spec": num(p, reduce=True), "show": ftxt(p),
                "explain": "積が奇数になるのは 両方奇数の 3×3＝9通り。1−9/36。", "hint": HINT_FRAC}
    r, w = R(rng, 2, 5), R(rng, 1, 4)
    p = Fr(r, r + w)
    return {"q": f"赤玉 {r}個、白玉 {w}個 が入った袋から1個取り出すとき、赤玉である確率は？", "spec": num(p, reduce=True), "show": ftxt(p),
            "explain": f"全部で {r + w}個、そのうち赤は {r}個。", "hint": HINT_FRAC}


def g_expand(rng):
    a, b = R(rng, -9, 9, True), R(rng, -9, 9, True)
    k = rng.choice([1, 1, 2, 3])
    coefs = [k, k * b + a, a * b]
    return {"q": f"$$({lin(k, a)})({lin(1, b)})$$ を展開しよう。", "spec": {"type": "expr", "value": lambda x, c=coefs: c[0] * x * x + c[1] * x + c[2], "form": "expanded"},
            "show": ptxt(coefs), "explain": "分配法則で、すべての組み合わせをかけてたす。", "hint": "x^2+3x+2 のように書いてね"}


def g_factor(rng):
    a, b = R(rng, -9, 9, True), R(rng, -9, 9, True)
    if rng.random() < 0.25:
        a, b = a, -a
    coefs = [1, a + b, a * b]
    return {"q": f"$${poly(coefs)}$$ を因数分解しよう。", "spec": {"type": "expr", "value": lambda x, a=a, b=b: (x + a) * (x + b), "form": "factored"},
            "show": f"(x{a:+d})(x{b:+d})", "explain": f"かけて {a * b}、たして {a + b} になる2つの数（{a} と {b}）をさがす。", "hint": "(x+2)(x-3) のように書いてね"}


def _simp_sqrt(n):
    out, k = 1, 2
    while k * k <= n:
        while n % (k * k) == 0:
            out *= k
            n //= k * k
        k += 1
    return out, n


def g_sqrt(rng):
    t = rng.randint(0, 2)
    if t == 0:
        k, m = R(rng, 2, 6), rng.choice([2, 3, 5, 6, 7])
        n = k * k * m
        return {"q": rf"$$\sqrt{{{n}}}$$ を $a\sqrt{{b}}$ の形にしよう。", "spec": num(math.sqrt(n), simplify=True), "show": f"{k}√{m}",
                "explain": f"{n}＝{k}²×{m} なので {k}√{m}。", "hint": HINT_SQRT}
    if t == 1:
        m = rng.choice([2, 3, 5])
        a, b = R(rng, 1, 4), R(rng, 1, 4)
        A, B = a * a * m, b * b * m
        return {"q": rf"$$\sqrt{{{A}}} + \sqrt{{{B}}}$$", "spec": num(math.sqrt(A) + math.sqrt(B), simplify=True), "show": f"{a + b}√{m}",
                "explain": f"√{A}＝{a}√{m}、√{B}＝{b}√{m}。同じルートどうし たす。", "hint": HINT_SQRT}
    m = rng.choice([2, 3, 5, 6])
    a = R(rng, 1, 6) * m
    return {"q": rf"$$\frac{{{a}}}{{\sqrt{{{m}}}}}$$ の分母を有理化しよう。", "spec": num(a / math.sqrt(m), simplify=True), "show": f"{a // m}√{m}",
            "explain": f"分母と分子に √{m} をかける：{a}√{m}/{m}。", "hint": HINT_SQRT}


def g_quad(rng):
    if rng.random() < 0.6:
        a, b = R(rng, -9, 9), R(rng, -9, 9)
        while a == b:
            b = R(rng, -9, 9)
        coefs = [1, -(a + b), a * b]
        return {"q": f"$${poly(coefs)} = 0$$ を解こう。", "spec": {"type": "nums", "value": [a, b]}, "show": f"x={a}, {b}",
                "explain": f"因数分解すると (x{-a:+d})(x{-b:+d})＝0。", "hint": "x=2, -3 のように 2つ書いてね"}
    while True:
        b, c = R(rng, -6, 6), R(rng, -6, 6)
        dsc = b * b - 4 * c
        if dsc > 0 and int(math.isqrt(dsc)) ** 2 != dsc:
            break
    k, m = _simp_sqrt(dsc)
    r1, r2 = (-b + math.sqrt(dsc)) / 2, (-b - math.sqrt(dsc)) / 2
    show = f"x=({-b}±{'' if k == 1 else k}√{m})/2"
    if k % 2 == 0 and b % 2 == 0:
        show = f"x={-b // 2}±{'' if k // 2 == 1 else k // 2}√{m}"
    return {"q": f"$${poly([1, b, c])} = 0$$ を解こう。", "spec": {"type": "nums", "value": [r1, r2], "simplify": True}, "show": show,
            "explain": "解の公式 x＝(−b±√(b²−4ac))/2a を使う。", "hint": "x=(-3±√5)/2 や x=1±√2 のように書いてね"}


def g_func2(rng):
    a = R(rng, -4, 4, True)
    p, q = R(rng, -4, 2), 0
    q = p + R(rng, 1, 4)
    return {"q": f"関数 $$y = {poly([a, 0, 0])}$$ で、x が {p} から {q} まで増加するときの 変化の割合は？", "spec": num(a * (p + q)), "show": str(a * (p + q)),
            "explain": f"変化の割合＝yの増加量÷xの増加量＝({a * q * q}−({a * p * p}))÷({q}−({p}))＝{a * (p + q)}。"}


def g_pyth(rng):
    a, b = R(rng, 1, 9), R(rng, 1, 9)
    c2 = a * a + b * b
    k, m = _simp_sqrt(c2)
    show = str(k) if m == 1 else f"{'' if k == 1 else k}√{m}"
    return {"q": f"直角をはさむ2辺が {a}cm と {b}cm の 直角三角形の 斜辺の長さは？", "spec": num(math.sqrt(c2), simplify=True), "show": f"{show}cm",
            "explain": f"三平方の定理：斜辺²＝{a}²＋{b}²＝{c2}。", "hint": HINT_SQRT}


# ---------------------------------------------------------------------------
# 高校 数学I
# ---------------------------------------------------------------------------


def g_ineq1(rng):
    a, c = R(rng, -6, 6, True), R(rng, -6, 6, True)
    while a == c:
        c = R(rng, -6, 6, True)
    b, d = R(rng, -12, 12), R(rng, -12, 12)
    op = rng.choice(["<", ">", "<=", ">="])
    k = a - c
    val = Fr(d - b, k)
    flip = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}
    res_op = op if k > 0 else flip[op]
    tex = {"<": "<", ">": ">", "<=": r"\leqq", ">=": r"\geqq"}
    return {"q": f"不等式 $${lin(a, b)} {tex[op]} {lin(c, d)}$$ を解こう。", "spec": {"type": "ineq", "value": (res_op, float(val))},
            "show": f"x{res_op.replace('<=', '≦').replace('>=', '≧')}{ftxt(val)}",
            "explain": f"移項して {k}x {op} {d - b}。" + ("負の数でわるので不等号の向きが変わる。" if k < 0 else ""), "hint": "x>3、x≦-1/2 のように書いてね"}


def g_vertex(rng):
    a, p, q = R(rng, -3, 3, True), R(rng, -5, 5), R(rng, -9, 9)
    coefs = [a, -2 * a * p, a * p * p + q]
    return {"q": f"放物線 $$y = {poly(coefs)}$$ の 頂点の座標は？", "spec": {"type": "point", "value": (p, q)}, "show": f"({p}, {q})",
            "explain": f"平方完成すると y＝{a}(x{-p:+d})²{q:+d}。", "hint": "(2, -3) のように書いてね"}


def g_maxmin(rng):
    p, q = R(rng, -2, 4), R(rng, -6, 6)
    lo, hi = sorted(rng.sample(range(-3, 7), 2))
    f = lambda x: (x - p) ** 2 + q
    kind = rng.choice(["最大値", "最小値"])
    if kind == "最小値":
        ans = q if lo <= p <= hi else min(f(lo), f(hi))
    else:
        ans = max(f(lo), f(hi))
    coefs = [1, -2 * p, p * p + q]
    return {"q": f"$${lo} \\leqq x \\leqq {hi}$$ における 関数 $$y = {poly(coefs)}$$ の {kind}は？", "spec": num(ans), "show": str(ans),
            "explain": f"y＝(x{-p:+d})²{q:+d}。軸 x＝{p} と 定義域の位置から考える。"}


def g_disc(rng):
    a, b, c = R(rng, 1, 3), R(rng, -8, 8), R(rng, -6, 6)
    d = b * b - 4 * a * c
    n = 2 if d > 0 else (1 if d == 0 else 0)
    return {"q": f"2次方程式 $${poly([a, b, c])} = 0$$ の 実数解の個数は？", "spec": num(n), "show": f"{n}個",
            "explain": f"判別式 D＝b²−4ac＝{d}。D>0 なら2個、D＝0 なら1個、D<0 なら0個。"}


TRIG = {0: ("0", "1", "0"), 30: ("1/2", "√3/2", "√3/3"), 45: ("√2/2", "√2/2", "1"), 60: ("√3/2", "1/2", "√3"),
        90: ("1", "0", None), 120: ("√3/2", "-1/2", "-√3"), 135: ("√2/2", "-√2/2", "-1"), 150: ("1/2", "-√3/2", "-√3/3"), 180: ("0", "-1", "0")}


def g_trig(rng):
    while True:
        deg = rng.choice(list(TRIG))
        fn = rng.randint(0, 2)
        if TRIG[deg][fn] is not None:
            break
    name = ["sin", "cos", "tan"][fn]
    val = [math.sin, math.cos, math.tan][fn](math.radians(deg))
    return {"q": rf"$$\{name} {deg}^\circ$$ の値は？", "spec": num(round(val, 12), simplify=True), "show": TRIG[deg][fn],
            "explain": "単位円や 30°・45°・60° の直角三角形の辺の比から考える。", "hint": "√3/2 や -1/2 のように書いてね"}


def g_cosine(rng):
    b, c = R(rng, 2, 8), R(rng, 2, 8)
    ang = rng.choice([60, 120])
    a2 = b * b + c * c - 2 * b * c * math.cos(math.radians(ang))
    a2 = round(a2)
    k, m = _simp_sqrt(a2)
    show = str(k) if m == 1 else f"{'' if k == 1 else k}√{m}"
    return {"q": f"△ABC で b＝{b}、c＝{c}、A＝{ang}° のとき、a は？", "spec": num(math.sqrt(a2), simplify=True), "show": show,
            "explain": f"余弦定理 a²＝b²＋c²−2bc cosA＝{a2}。", "hint": HINT_SQRT}


def g_data(rng):
    n = 5
    vals = [R(rng, 1, 10) for _ in range(n)]
    while sum(vals) % n:
        vals[-1] = R(rng, 1, 10)
    m = sum(vals) / n
    var = sum((v - m) ** 2 for v in vals) / n
    s = "、".join(map(str, vals))
    if rng.random() < 0.4:
        return {"q": f"データ {s} の 平均値は？", "spec": num(m), "show": dec(m), "explain": "平均値＝合計÷個数。"}
    return {"q": f"データ {s} の 分散は？", "spec": num(var), "show": dec(var, 3), "explain": f"平均 {dec(m)} からの差の2乗の平均。", "hint": "小数や分数で書いてね"}


# ---------------------------------------------------------------------------
# 高校 数学A
# ---------------------------------------------------------------------------


def g_perm(rng):
    n, r = R(rng, 4, 9), 0
    r = R(rng, 2, min(4, n - 1))
    if rng.random() < 0.5:
        ans = math.perm(n, r)
        return {"q": f"{n}人の中から {r}人を選んで 1列に並べる並べ方は 何通り？", "spec": num(ans), "show": f"{ans}通り", "explain": f"{n}P{r}＝{ans}。"}
    ans = math.comb(n, r)
    return {"q": f"{n}人の中から {r}人を選ぶ選び方は 何通り？", "spec": num(ans), "show": f"{ans}通り", "explain": f"{n}C{r}＝{ans}。"}


def g_probA(rng):
    t = rng.randint(0, 1)
    if t == 0:
        r, w, k = R(rng, 3, 6), R(rng, 2, 5), 2
        p = Fr(math.comb(r, k), math.comb(r + w, k))
        return {"q": f"赤玉 {r}個、白玉 {w}個 の袋から 同時に2個取り出すとき、2個とも赤玉である確率は？", "spec": num(p, reduce=True), "show": ftxt(p),
                "explain": f"{r}C2 ÷ {r + w}C2。", "hint": HINT_FRAC}
    n, k = rng.choice([3, 4, 5]), 0
    k = R(rng, 1, n - 1)
    p = Fr(math.comb(n, k), 2 ** n)
    return {"q": f"硬貨を {n}回投げるとき、表がちょうど {k}回出る確率は？", "spec": num(p, reduce=True), "show": ftxt(p),
            "explain": f"反復試行：{n}C{k}×(1/2)^{n}。", "hint": HINT_FRAC}


def g_gcd(rng):
    g = R(rng, 2, 12)
    a, b = g * R(rng, 2, 9), g * R(rng, 2, 9)
    while a == b:
        b = g * R(rng, 2, 9)
    if rng.random() < 0.5:
        return {"q": f"{a} と {b} の 最大公約数は？", "spec": num(math.gcd(a, b)), "show": str(math.gcd(a, b)), "explain": "素因数分解するか、ユークリッドの互除法を使う。"}
    l = a * b // math.gcd(a, b)
    return {"q": f"{a} と {b} の 最小公倍数は？", "spec": num(l), "show": str(l), "explain": f"最小公倍数＝{a}×{b}÷最大公約数({math.gcd(a, b)})。"}


def g_base(rng):
    n = R(rng, 5, 60)
    b = rng.choice([2, 3, 5])
    digits = ""
    m = n
    while m:
        digits = str(m % b) + digits
        m //= b
    if rng.random() < 0.5:
        return {"q": f"{b}進法で表された数 $${digits}_{{({b})}}$$ を 10進法で表そう。", "spec": num(n), "show": str(n), "explain": f"各位の数×{b}の累乗 を たす。"}
    return {"q": f"10進法の {n} を {b}進法で表そう。", "spec": num(int(digits)), "show": digits, "explain": f"{b} でわっていき、あまりを下から並べる。", "hint": "数字だけ書いてね"}


# ---------------------------------------------------------------------------
# 高校 数学II
# ---------------------------------------------------------------------------


def g_binom(rng):
    n = R(rng, 4, 7)
    a, b = R(rng, 1, 3), R(rng, -3, 3, True)
    k = R(rng, 1, n - 1)
    coef = math.comb(n, k) * a ** k * b ** (n - k)
    return {"q": f"$$({lin(a, b)})^{{{n}}}$$ の展開式における $x^{{{k}}}$ の係数は？", "spec": num(coef), "show": str(coef),
            "explain": f"一般項 ₙCᵣ({a}x)ʳ({b})ⁿ⁻ʳ で r＝{k}：{n}C{k}×{a}^{k}×({b})^{n - k}＝{coef}。"}


def g_complex2(rng):
    a, b, c, d = R(rng, -5, 5), R(rng, -5, 5, True), R(rng, -5, 5), R(rng, -5, 5, True)
    z = complex(a, b) * complex(c, d)
    return {"q": f"$$({a} {'+' if b > 0 else '-'} {abs(b)}i)({c} {'+' if d > 0 else '-'} {abs(d)}i)$$ を計算しよう。", "spec": num(z, imag=True),
            "show": f"{int(z.real)}{int(z.imag):+d}i", "explain": "i²＝−1 を使って展開する。", "hint": "3+2i のように書いてね"}


def g_vieta(rng):
    a, b = R(rng, -6, 6), R(rng, -6, 6)
    k = R(rng, 1, 3)
    coefs = [k, -k * (a + b), k * a * b]
    t = rng.randint(0, 2)
    if t == 0:
        return {"q": f"2次方程式 $${poly(coefs)} = 0$$ の2つの解を α, β とするとき、α＋β は？", "spec": num(a + b), "show": str(a + b), "explain": "解と係数の関係：α＋β＝−b/a。"}
    if t == 1:
        return {"q": f"2次方程式 $${poly(coefs)} = 0$$ の2つの解を α, β とするとき、αβ は？", "spec": num(a * b), "show": str(a * b), "explain": "解と係数の関係：αβ＝c/a。"}
    return {"q": f"2次方程式 $${poly(coefs)} = 0$$ の2つの解を α, β とするとき、α²＋β² は？", "spec": num(a * a + b * b), "show": str(a * a + b * b),
            "explain": "α²＋β²＝(α＋β)²−2αβ。"}


def g_addition(rng):
    pairs = [(45, 30, "+"), (45, 30, "-"), (60, 45, "+"), (60, 45, "-")]
    A, B, op = rng.choice(pairs)
    fn = rng.choice(["sin", "cos"])
    ang = A + B if op == "+" else A - B
    val = getattr(math, fn)(math.radians(ang))
    shows = {("sin", 75): "(√6+√2)/4", ("sin", 15): "(√6-√2)/4", ("cos", 75): "(√6-√2)/4", ("cos", 15): "(√6+√2)/4",
             ("sin", 105): "(√6+√2)/4", ("cos", 105): "(√2-√6)/4"}
    return {"q": rf"加法定理を使って $$\{fn} {ang}^\circ$$ の値を求めよう。", "spec": num(val), "show": shows[(fn, ang)],
            "explain": f"{ang}°＝{A}°{op}{B}° として加法定理を使う。", "hint": "(√6+√2)/4 のように書いてね"}


def g_explog(rng):
    t = rng.randint(0, 2)
    if t == 0:
        b = rng.choice([2, 3, 5])
        n = R(rng, 2, 5)
        return {"q": rf"$$\log_{{{b}}} {b ** n}$$ の値は？", "spec": num(n), "show": str(n), "explain": f"{b ** n}＝{b}^{n} なので {n}。"}
    if t == 1:
        b = rng.choice([2, 3])
        m, n = R(rng, 2, 4), R(rng, 2, 5)
        big = b ** n * m
        return {"q": rf"$$\log_{{{b}}} {big} - \log_{{{b}}} {m}$$ の値は？", "spec": num(n), "show": str(n),
                "explain": f"log の差は 商の log：log_{b}({big}÷{m})＝log_{b}{b ** n}＝{n}。"}
    base, e, frac = rng.choice([(2, 2, Fr(3, 2)), (2, 3, Fr(2, 3)), (3, 2, Fr(3, 2)), (3, 3, Fr(2, 3)), (2, 4, Fr(3, 4)), (2, 4, Fr(1, 2))])
    a = base ** e
    ans = base ** int(e * frac)
    return {"q": f"$${a}^{{{ftex(frac)}}}$$ の値は？", "spec": num(ans), "show": str(ans),
            "explain": f"{a}＝{base}^{e} なので {base}^({e}×{ftxt(frac)})＝{base}^{int(e * frac)}。"}


def g_deriv(rng):
    a, b, c, d = R(rng, -4, 4, True), R(rng, -6, 6), R(rng, -9, 9), R(rng, -9, 9)
    if rng.random() < 0.5:
        return {"q": f"$$f(x) = {poly([a, b, c, d])}$$ の 導関数 $f'(x)$ は？",
                "spec": {"type": "expr", "value": lambda x, a=a, b=b, c=c: 3 * a * x * x + 2 * b * x + c}, "show": f"f'(x)={ptxt([3 * a, 2 * b, c])}",
                "explain": "(xⁿ)'＝nxⁿ⁻¹ を項ごとに使う。", "hint": "3x^2-2x+1 のように書いてね"}
    p = R(rng, -3, 3)
    slope = 3 * a * p * p + 2 * b * p + c
    return {"q": f"$$y = {poly([a, b, c, d])}$$ の、x＝{p} における 接線の傾きは？", "spec": num(slope), "show": str(slope),
            "explain": f"y'＝{ptxt([3 * a, 2 * b, c])} に x＝{p} を代入。"}


def g_integ(rng):
    a, b, c = R(rng, -3, 3), R(rng, -6, 6), R(rng, -9, 9)
    lo, hi = sorted(rng.sample(range(-2, 4), 2))
    F = lambda x: Fr(a, 1) * x ** 3 + Fr(b, 2) * x ** 2 + c * x
    val = F(hi) - F(lo)
    return {"q": rf"$$\int_{{{lo}}}^{{{hi}}} \left({poly([3 * a, b, c])}\right) dx$$ を計算しよう。", "spec": num(val, reduce=True), "show": ftxt(val),
            "explain": f"不定積分 F(x)＝{ptxt([a, Fr(b, 2), c, 0])} を求め、F({hi})−F({lo})。", "hint": HINT_FRAC}


# ---------------------------------------------------------------------------
# 高校 数学B
# ---------------------------------------------------------------------------


def g_arith(rng):
    a, d, n = R(rng, -10, 20), R(rng, -5, 7, True), R(rng, 8, 30)
    if rng.random() < 0.5:
        return {"q": f"初項 {a}、公差 {d} の等差数列の 第{n}項は？", "spec": num(a + (n - 1) * d), "show": str(a + (n - 1) * d), "explain": "aₙ＝a＋(n−1)d。"}
    s = n * (2 * a + (n - 1) * d) // 2
    return {"q": f"初項 {a}、公差 {d} の等差数列の 初項から第{n}項までの和は？", "spec": num(s), "show": str(s), "explain": "Sₙ＝n{2a＋(n−1)d}/2。"}


def g_geom(rng):
    a, r, n = R(rng, 1, 5), rng.choice([2, 3, -2]), R(rng, 4, 8)
    if rng.random() < 0.5:
        return {"q": f"初項 {a}、公比 {r} の等比数列の 第{n}項は？", "spec": num(a * r ** (n - 1)), "show": str(a * r ** (n - 1)), "explain": "aₙ＝a・rⁿ⁻¹。"}
    s = a * (r ** n - 1) // (r - 1)
    return {"q": f"初項 {a}、公比 {r} の等比数列の 初項から第{n}項までの和は？", "spec": num(s), "show": str(s), "explain": "Sₙ＝a(rⁿ−1)/(r−1)。"}


def g_sigma(rng):
    n = R(rng, 5, 20)
    a, b = R(rng, 1, 4), R(rng, -3, 5)
    if rng.random() < 0.5:
        s = a * n * (n + 1) // 2 + b * n
        return {"q": rf"$$\sum_{{k=1}}^{{{n}}} ({lin(a, b, 'k')})$$ を計算しよう。", "spec": num(s), "show": str(s),
                "explain": "Σk＝n(n+1)/2、Σ(定数)＝定数×n を使う。"}
    s = n * (n + 1) * (2 * n + 1) // 6
    return {"q": rf"$$\sum_{{k=1}}^{{{n}}} k^2$$ を計算しよう。", "spec": num(s), "show": str(s), "explain": "Σk²＝n(n+1)(2n+1)/6。"}


def g_expect(rng):
    if rng.random() < 0.5:
        n, p = R(rng, 10, 100), rng.choice([Fr(1, 2), Fr(1, 3), Fr(1, 4), Fr(1, 5), Fr(1, 6)])
        e = n * p
        return {"q": f"確率変数 X が 二項分布 B({n}, {ftxt(p)}) に従うとき、X の期待値（平均）は？", "spec": num(e, reduce=True), "show": ftxt(e),
                "explain": "二項分布 B(n, p) の期待値は np。", "hint": HINT_FRAC}
    vals = sorted(rng.sample(range(1, 10), 3))
    e = Fr(sum(vals), 3)
    return {"q": f"X が {vals[0]}、{vals[1]}、{vals[2]} の値を それぞれ確率 1/3 でとるとき、X の期待値は？", "spec": num(e, reduce=True), "show": ftxt(e),
            "explain": "期待値＝Σ（値×確率）。", "hint": HINT_FRAC}


# ---------------------------------------------------------------------------
# 高校 数学C
# ---------------------------------------------------------------------------


def g_vec(rng):
    a1, a2, b1, b2 = R(rng, -5, 5), R(rng, -5, 5), R(rng, -5, 5), R(rng, -5, 5)
    if rng.random() < 0.5:
        ip = a1 * b1 + a2 * b2
        return {"q": rf"$$\vec{{a}} = ({a1}, {a2}),\ \vec{{b}} = ({b1}, {b2})$$ のとき、内積 $\vec{{a}} \cdot \vec{{b}}$ は？", "spec": num(ip), "show": str(ip),
                "explain": "内積＝a₁b₁＋a₂b₂。"}
    while a1 == 0 and a2 == 0:
        a1, a2 = R(rng, -5, 5), R(rng, -5, 5)
    s = a1 * a1 + a2 * a2
    k, m = _simp_sqrt(s)
    show = str(k) if m == 1 else f"{'' if k == 1 else k}√{m}"
    return {"q": rf"$$\vec{{a}} = ({a1}, {a2})$$ の 大きさ $|\vec{{a}}|$ は？", "spec": num(math.sqrt(s), simplify=True), "show": show,
            "explain": "|a|＝√(a₁²＋a₂²)。", "hint": HINT_SQRT}


def g_cplane(rng):
    if rng.random() < 0.5:
        a, b = rng.choice([(3, 4), (5, 12), (6, 8), (1, 1), (2, 2), (1, 2), (2, 3)])
        a, b = a * rng.choice([1, -1]), b * rng.choice([1, -1])
        s = a * a + b * b
        k, m = _simp_sqrt(s)
        show = str(k) if m == 1 else f"{'' if k == 1 else k}√{m}"
        return {"q": f"複素数 z＝{a}{b:+d}i の 絶対値 |z| は？", "spec": num(math.sqrt(s), simplify=True), "show": show, "explain": "|a+bi|＝√(a²＋b²)。", "hint": HINT_SQRT}
    z, deg = rng.choice([("1+i", 45), ("-1+i", 135), ("√3+i", 30), ("1+√3i", 60), ("-√3+i", 150), ("i", 90), ("-1", 180)])
    return {"q": f"複素数 z＝{z} の 偏角 θ（0°≦θ<360°）は 何度？", "spec": num(deg), "show": f"{deg}°", "explain": "複素数平面上の点の位置から、実軸の正の向きとのなす角を考える。"}


# ---------------------------------------------------------------------------
# 高校 数学III
# ---------------------------------------------------------------------------


def g_limit(rng):
    t = rng.randint(0, 2)
    if t == 0:
        a, b, c, d = R(rng, 1, 6), R(rng, -5, 5), R(rng, 1, 6), R(rng, -5, 5)
        v = Fr(a, c)
        return {"q": rf"$$\lim_{{n \to \infty}} \frac{{{poly([a, b, 1], 'n')}}}{{{poly([c, d, 2], 'n')}}}$$ は？", "spec": num(v, reduce=True), "show": ftxt(v),
                "explain": "分母の最高次 n² で分子・分母をわる。", "hint": HINT_FRAC}
    if t == 1:
        k = R(rng, 2, 7)
        return {"q": rf"$$\lim_{{x \to 0}} \frac{{\sin {k}x}}{{x}}$$ は？", "spec": num(k), "show": str(k), "explain": f"sin{k}x/x＝{k}・sin{k}x/({k}x) → {k}×1。"}
    a = R(rng, -5, 5, True)
    return {"q": rf"$$\lim_{{x \to {a}}} \frac{{x^2 - {a * a}}}{{x {'-' if a > 0 else '+'} {abs(a)}}}$$ は？", "spec": num(2 * a), "show": str(2 * a),
            "explain": f"分子を (x{-a:+d})(x{a:+d}) と因数分解して約分 → x{a:+d} に x＝{a} を代入。"}


def g_deriv3(rng):
    t = rng.randint(0, 2)
    k = R(rng, 2, 5)
    if t == 0:
        return {"q": f"$$y = \\sin {k}x$$ の 導関数は？", "spec": {"type": "expr", "value": lambda x, k=k: k * cmath.cos(k * x)}, "show": f"y'={k}cos({k}x)",
                "explain": "合成関数の微分：(sin u)'＝cos u・u'。", "hint": "3cos(3x) のように書いてね"}
    if t == 1:
        return {"q": f"$$y = e^{{{k}x}}$$ の 導関数は？", "spec": {"type": "expr", "value": lambda x, k=k: k * cmath.exp(k * x)}, "show": f"y'={k}e^({k}x)",
                "explain": "(eᵘ)'＝eᵘ・u'。", "hint": "2e^(2x) のように書いてね"}
    return {"q": "$$y = x \\log x$$ の 導関数は？（log は自然対数）", "spec": {"type": "expr", "value": lambda x: cmath.log(x) + 1},
            "show": "y'=log(x)+1", "explain": "積の微分：(fg)'＝f'g＋fg'。", "hint": "log(x)+1 のように書いてね"}


def g_integ3(rng):
    t = rng.randint(0, 2)
    if t == 0:
        k = R(rng, 1, 4)
        return {"q": rf"$$\int_0^{{\pi}} \sin {k}x \, dx$$ を計算しよう。", "spec": num((1 - math.cos(k * math.pi)) / k, reduce=True),
                "show": ftxt(Fr(1 - (-1) ** k, k)), "explain": f"∫sin{k}x dx＝−cos{k}x/{k}。", "hint": HINT_FRAC}
    if t == 1:
        n = R(rng, 2, 5)
        return {"q": rf"$$\int_1^{{e^{{{n}}}}} \frac{{1}}{{x}} \, dx$$ を計算しよう。", "spec": num(n), "show": str(n), "explain": "∫1/x dx＝log|x|。log e^n − log 1。"}
    k = R(rng, 2, 4)
    return {"q": rf"$$\int_0^{{1}} e^{{{k}x}} \, dx$$ を計算しよう。", "spec": num((math.e ** k - 1) / k), "show": f"(e^{k}-1)/{k}",
            "explain": f"∫e^({k}x)dx＝e^({k}x)/{k}。", "hint": f"(e^{k}-1)/{k} のように書いてね"}


# ---------------------------------------------------------------------------
# 学年・科目と単元
# ---------------------------------------------------------------------------
UNITS = {
    # 小学校
    "add1": ("たし算（くり上がり）", g_add1), "sub1": ("ひき算（くり下がり）", g_sub1),
    "add2": ("2けたのたし算・ひき算", g_add2), "kuku": ("かけ算（九九）", g_kuku), "unit2": ("長さ・かさのたんい", g_unit2),
    "div3": ("わり算", g_div3), "divr": ("あまりのあるわり算", g_divr), "mul3": ("大きな数のかけ算", g_mul3),
    "dec3": ("小数のたし算・ひき算", g_dec3), "frac3": ("分数のたし算・ひき算（同じ分母）", g_frac3),
    "div4": ("わり算の筆算", g_div4), "round": ("がい数（四捨五入）", g_round), "area4": ("面積（長方形・正方形）", g_area4), "decint": ("小数×整数・小数÷整数", g_decint),
    "decdec": ("小数のかけ算・わり算", g_decdec), "fracadd": ("分数のたし算・ひき算（通分）", g_fracadd), "percent": ("割合と百分率", g_percent),
    "average": ("平均", g_average), "area5": ("図形の面積", g_area5), "volume": ("体積", g_volume), "speed": ("速さ", g_speed),
    "fracmul": ("分数のかけ算・わり算", g_fracmul), "ratio": ("比", g_ratio), "circle": ("円の面積・円周", g_circle), "propo": ("比例と反比例", g_propo),
    # 中学校
    "posneg": ("正負の数", g_posneg), "moji": ("文字式の計算", g_moji), "lineq": ("一次方程式", g_lineq), "hirei": ("比例と反比例の式", g_hirei),
    "siki2": ("式の計算", g_siki2), "simul": ("連立方程式", g_simul), "linfunc": ("一次関数", g_linfunc), "angle": ("多角形の角", g_angle), "prob2": ("確率", g_prob2),
    "expand": ("式の展開", g_expand), "factor": ("因数分解", g_factor), "sqrt": ("平方根", g_sqrt), "quad": ("二次方程式", g_quad),
    "func2": ("関数 y＝ax²", g_func2), "pyth": ("三平方の定理", g_pyth),
    # 数学I
    "ineq1": ("一次不等式", g_ineq1), "vertex": ("2次関数のグラフ（頂点）", g_vertex), "maxmin": ("2次関数の最大・最小", g_maxmin),
    "disc": ("2次方程式の解の個数（判別式）", g_disc), "trig": ("三角比の値", g_trig), "cosine": ("余弦定理", g_cosine), "data": ("データの分析", g_data),
    # 数学A
    "perm": ("順列・組合せ", g_perm), "probA": ("確率", g_probA), "gcd": ("約数と倍数", g_gcd), "base": ("n進法", g_base),
    # 数学II
    "binom": ("二項定理", g_binom), "complex2": ("複素数の計算", g_complex2), "vieta": ("解と係数の関係", g_vieta), "addition": ("三角関数（加法定理）", g_addition),
    "explog": ("指数・対数", g_explog), "deriv": ("微分", g_deriv), "integ": ("積分（定積分）", g_integ),
    # 数学B
    "arith": ("等差数列", g_arith), "geom": ("等比数列", g_geom), "sigma": ("Σ（和の記号）", g_sigma), "expect": ("期待値・二項分布", g_expect),
    # 数学C
    "vec": ("平面ベクトル", g_vec), "cplane": ("複素数平面", g_cplane),
    # 数学III
    "limit": ("極限", g_limit), "deriv3": ("いろいろな関数の微分", g_deriv3), "integ3": ("いろいろな関数の積分", g_integ3),
}

SANSU = {
    "小1": ["add1", "sub1"],
    "小2": ["add2", "kuku", "unit2"],
    "小3": ["div3", "divr", "mul3", "dec3", "frac3"],
    "小4": ["div4", "round", "area4", "decint"],
    "小5": ["decdec", "fracadd", "percent", "average", "area5", "volume", "speed"],
    "小6": ["fracmul", "ratio", "circle", "propo"],
    "中1": ["posneg", "moji", "lineq", "hirei"],
    "中2": ["siki2", "simul", "linfunc", "angle", "prob2"],
    "中3": ["expand", "factor", "sqrt", "quad", "func2", "pyth"],
}

COURSES = {
    "sansu": {"name": "算数", "grades": ["小1", "小2", "小3", "小4", "小5", "小6"], "desc": "計算・図形・割合など、くらしで使う算数"},
    "sugaku": {"name": "数学", "grades": ["中1", "中2", "中3"], "desc": "文字式・方程式・関数・確率など"},
    "m1": {"name": "数学I", "grades": ["高1"], "units": ["expand", "factor", "ineq1", "vertex", "maxmin", "disc", "trig", "cosine", "data"],
           "desc": "2次関数・三角比・データの分析など"},
    "mA": {"name": "数学A", "grades": ["高1"], "units": ["perm", "probA", "gcd", "base"], "desc": "場合の数・確率・整数の性質"},
    "m2": {"name": "数学II", "grades": ["高2", "高3"], "units": ["binom", "complex2", "vieta", "addition", "explog", "deriv", "integ"],
           "desc": "複素数・三角関数・指数対数・微分積分"},
    "mB": {"name": "数学B", "grades": ["高2", "高3"], "units": ["arith", "geom", "sigma", "expect"], "desc": "数列・統計的な推測"},
    "mC": {"name": "数学C", "grades": ["高2", "高3"], "units": ["vec", "cplane"], "desc": "ベクトル・複素数平面"},
    "m3": {"name": "数学III", "grades": ["高2", "高3"], "units": ["limit", "deriv3", "integ3"], "desc": "極限・いろいろな関数の微分積分"},
}


def courses_for(grade):
    return [cid for cid, c in COURSES.items() if grade in c["grades"]]


def units_for(course_id, grade):
    """その学年・科目の単元。算数・数学は、その学年と1つ前の学年の単元（復習）"""
    c = COURSES[course_id]
    if "units" in c:
        return list(c["units"])
    order = list(SANSU)
    i = order.index(grade)
    now = SANSU[grade]
    prev = SANSU[order[i - 1]] if i > 0 and order[i - 1][0] == grade[0] else []
    return now + [u for u in prev if u not in now]


def current_units(course_id, grade):
    """「いろいろ（まとめ）」で使う単元（その学年のものだけ）"""
    c = COURSES[course_id]
    return list(c["units"]) if "units" in c else list(SANSU[grade])


def make_set(unit_ids, rng, n=10):
    """unit_ids の中から n 問（同じ問題はくり返さない）。単元が複数なら順にまぜる"""
    out, seen = [], set()
    tries = 0
    while len(out) < n and tries < n * 40:
        uid = unit_ids[len(out) % len(unit_ids)] if len(unit_ids) > 1 else unit_ids[0]
        tries += 1
        q = UNITS[uid][1](rng)
        if q["q"] in seen:
            continue
        seen.add(q["q"])
        q["unit"] = uid
        out.append(q)
    return out
