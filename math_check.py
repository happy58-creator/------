"""算数・数学の答え合わせ（入力をそろえて、数や式として比べる）。外部ライブラリは使わない。

書き方の例（スマホの全角でもOK）
  分数 3/4　帯分数 2と1/3　小数 0.25　ルート √3・2√3・√(x+1)・sqrt(3)　円周率 π
  累乗 x^2・x²　かけ算 2x・3(x+1)・2×3　複数の答え x=2, -3　±（x=±√3）
  不等式 x>3・x≧-2　座標 (2, -3)・x=1, y=2　複素数 3+2i
"""
import ast
import cmath
import math
import random
import re
import unicodedata
from fractions import Fraction

FUNCS = {"sqrt": cmath.sqrt, "sin": cmath.sin, "cos": cmath.cos, "tan": cmath.tan, "exp": cmath.exp, "log": cmath.log}
CONSTS = {"pi": math.pi, "e": math.e}
UNITS = ["cm**2", "cm**3", "m**2", "m**3", "km**2", "km/h", "km/時", "m/秒", "m/分", "cm³", "cm³", "cm²", "m²", "km²", "cm3", "cm2", "m3", "m2", "mm", "cm", "km", "dL", "mL", "kg",
         "度", "°", "円", "個", "人", "枚", "本", "通り", "分", "秒", "時間", "倍", "%", "％", "点", "回", "g", "L", "m"]


class BadInput(ValueError):
    pass


def normalize(text):
    t = str(text or "").replace("²", "^2").replace("³", "^3")           # NFKC で 2 にならないよう、先に置きかえる
    t = unicodedata.normalize("NFKC", t).strip()
    for a, b in (("−", "-"), ("ー", "-"), ("―", "-"), ("‐", "-"), ("–", "-"), ("×", "*"), ("÷", "/"), ("・", "*"),
                 ("^", "**"), ("²", "**2"), ("³", "**3"), ("π", "pi"), ("√", "sqrt"), ("≧", ">="), ("≦", "<="), ("≥", ">="), ("≤", "<="),
                 ("，", ","), ("、", ","), ("（", "("), ("）", ")"), (" ", ""), ("　", "")):
        t = t.replace(a, b)
    t = re.sub(r"(\d+)と(\d+)/(\d+)", r"(\1+\2/\3)", t)           # 帯分数 2と1/3
    t = re.sub(r"sqrt(\d+(?:\.\d+)?|[a-z])", r"sqrt(\1)", t)       # √3 → sqrt(3)
    return t


def strip_units(t):
    for u in sorted(UNITS, key=len, reverse=True):
        if t.endswith(u):
            return t[: -len(u)]
    return t


_TOKEN = re.compile(r"\d+\.\d+|\d+|sqrt|sin|cos|tan|exp|log|pi|[a-z]|\*\*|[-+*/(),]")


def _implicit_mult(t):
    """2x・3(x+1)・(x+1)(x-1)・2sqrt(3)・xpi などに * をおぎなう"""
    pos, toks = 0, []
    while pos < len(t):
        m = _TOKEN.match(t, pos)
        if not m:
            raise BadInput(f"読めない文字があるよ：{t[pos]}")
        toks.append(m.group())
        pos = m.end()
    out = []
    for tok in toks:
        if out:
            left, right = out[-1], tok
            left_val = re.fullmatch(r"[\d.]+|pi|[a-z]|\)", left) and left not in FUNCS
            right_val = re.fullmatch(r"[\d.]+|pi|[a-z]|\(", right) or right in FUNCS
            if left_val and right_val and not (re.fullmatch(r"[\d.]+", left) and re.fullmatch(r"[\d.]+", right)):
                out.append("*")
        out.append(tok)
    return "".join(out)


def to_python(text, imag=False):
    t = _implicit_mult(normalize(text))
    if imag:
        t = re.sub(r"(?<![a-z])i(?![a-z])", "1j", t)
    return t


def parse(text, imag=False):
    """式の木（ast）を返す"""
    src = to_python(text, imag)
    if not src:
        raise BadInput("答えが空だよ")
    try:
        tree = ast.parse(src, mode="eval").body
    except SyntaxError:
        raise BadInput("式の書き方が正しくないみたい")
    return tree


def evaluate(tree, x=None, y=None):
    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float, complex)):
            return n.value
        if isinstance(n, ast.Name):
            if n.id in CONSTS:
                return CONSTS[n.id]
            if n.id == "x" and x is not None:
                return x
            if n.id == "y" and y is not None:
                return y
            raise BadInput(f"「{n.id}」は使えないよ")
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                if b == 0:
                    raise BadInput("0でわっているよ")
                return a / b
            if isinstance(n.op, ast.Pow):
                if abs(b) > 50:
                    raise BadInput("大きすぎる累乗だよ")
                return a ** b
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS and len(n.args) == 1:
            return FUNCS[n.func.id](ev(n.args[0]))
        raise BadInput("式の書き方が正しくないみたい")
    try:
        v = ev(tree)
    except (OverflowError, ZeroDivisionError, ValueError) as e:
        if isinstance(e, BadInput):
            raise
        raise BadInput("計算できない式だよ")
    return complex(v)


def close(a, b, tol=1e-9):
    return abs(complex(a) - complex(b)) <= tol * max(1.0, abs(complex(b)))


def value_of(text, imag=False):
    t = strip_units(normalize(text))
    t = re.sub(r"^[a-z]=", "", t)
    return evaluate(parse(t, imag))


def _has_unreduced_fraction(text):
    for a, b in re.findall(r"(?<![\d.])(\d+)/(\d+)(?![\d.])", normalize(text)):
        if math.gcd(int(a), int(b)) > 1:
            return True
    return False


def _has_unsimplified_sqrt(text):
    t = normalize(text)
    for n in re.findall(r"sqrt\((\d+)\)", t):
        n = int(n)
        if any(n % (k * k) == 0 for k in range(2, int(n ** 0.5) + 1)):
            return True
    return bool(re.search(r"/\(?[\d*]*sqrt", t))       # 分母にルートが残っている


def _top_is_sum(tree):
    return isinstance(tree, ast.BinOp) and isinstance(tree.op, (ast.Add, ast.Sub))


def _split_answers(text):
    t = strip_units(normalize(text))
    t = re.sub(r"[a-z]=", "", t)
    parts = [p for p in re.split(r",|または|or|と(?!\d+/)", t) if p]
    out = []
    for p in parts:
        if "±" in p:
            out += [p.replace("±", "+", 1), p.replace("±", "-", 1)]
        else:
            out.append(p)
    return out


SAMPLE_X = (0.37, 1.29, -1.71, 2.53, -0.83)


def check(spec, text):
    """(正解か, ひとこと)。spec はもんだい側が決める答えの形"""
    kind = spec["type"]
    if not str(text or "").strip():
        return False, "（未入力）"
    try:
        if kind == "num":
            v = value_of(text, spec.get("imag", False))
            ok = close(v, spec["value"])
            if ok and spec.get("reduce") and _has_unreduced_fraction(text):
                return False, "答えは合っているけど、約分しよう"
            if ok and spec.get("simplify") and _has_unsimplified_sqrt(text):
                return False, "答えは合っているけど、ルートの中を小さくするか、分母を有理化しよう"
            return ok, ""
        if kind == "divmod":
            nums = [int(n) for n in re.findall(r"\d+", normalize(text))]
            return nums == list(spec["value"]), ""
        if kind == "nums":
            got = [value_of(p, spec.get("imag", False)) for p in _split_answers(text)]
            want = list(spec["value"])
            if len(got) != len(want):
                return False, f"答えは{len(want)}つだよ"
            rest = list(want)
            for g in got:
                hit = next((w for w in rest if close(g, w)), None)
                if hit is None:
                    return False, ""
                rest.remove(hit)
            if spec.get("simplify") and _has_unsimplified_sqrt(text):
                return False, "答えは合っているけど、ルートの中を小さくしよう"
            return True, ""
        if kind == "point":
            t = normalize(text)
            nums = re.findall(r"[xy]=([^,]+)", t) if "=" in t else t.strip("()").split(",")
            if len(nums) != len(spec["value"]):
                return False, f"({', '.join('□' for _ in spec['value'])}) の形で書こう"
            return all(close(value_of(n), w) for n, w in zip(nums, spec["value"])), ""
        if kind == "ineq":
            t = normalize(text)
            m = re.fullmatch(r"x(<=|>=|<|>)(.+)", t) or re.fullmatch(r"(.+?)(<=|>=|<|>)x", t)
            if not m:
                return False, "x>3 のような形で書こう"
            if m.re.pattern.startswith("x"):
                op, val = m.group(1), m.group(2)
            else:
                flip = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}
                val, op = m.group(1), flip[m.group(2)]
            want_op, want_val = spec["value"]
            return op == want_op and close(value_of(val), want_val), ""
        if kind in ("expr", "antideriv"):
            t = strip_units(normalize(text))
            t = re.sub(r"^(y|y'|f\(x\)|f'\(x\)|F\(x\))=", "", t)
            t = re.sub(r"\+C$", "", t) if kind == "antideriv" else t
            tree = parse(t)
            f = spec["value"]          # 正しい式（python の関数）
            diffs = [evaluate(tree, x=x) - f(x) for x in SAMPLE_X]
            if kind == "expr":
                ok = all(close(d, 0, 1e-7) for d in diffs)
            else:
                ok = all(close(d, diffs[0], 1e-7) for d in diffs)    # 定数のちがいはOK
            if ok and spec.get("form") == "factored" and _top_is_sum(tree):
                return False, "式は同じだけど、かけ算の形（因数分解した形）で書こう"
            if ok and spec.get("form") == "expanded" and "(" in t:
                return False, "式は同じだけど、かっこをはずした形で書こう"
            return ok, ""
    except BadInput as e:
        return False, str(e)
    raise ValueError(kind)
