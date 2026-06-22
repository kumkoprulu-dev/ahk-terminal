"""Tarayıcı kural dili (DSL) — güvenli parser + değerlendirici.

`eval` KULLANMAZ; kendi tokenizer / recursive-descent parser / AST değerlendiricimiz var.

Desteklenen örnekler:
    RSI(14) < 30
    EMA(20) > EMA(50) AND RSI(14) < 35
    MACD > Signal
    MACD Cross Up
    Volume > SMA(Volume, 20)
    Close > BollingerBands(20).Upper       # nokta ile çıktı seçimi
    ADX(14) > 25 AND NOT (RSI(14) > 70)

Her ifade pandas Series (sayısal) veya boole Series üretir. Tarayıcı motoru son barı kontrol eder.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.indicators import compute
from app.indicators._helpers import crossover, crossunder
from app.indicators.registry import REGISTRY

_FIELDS = {"open", "high", "low", "close", "volume", "hl2", "hlc3", "ohlc4"}
# MACD çıktılarına kısayol erişim
_SHORTCUTS = {
    "macd": ("MACD", "MACD"),
    "signal": ("MACD", "Signal"),
    "hist": ("MACD", "Hist"),
}


class DSLError(ValueError):
    pass


# ----------------------------- Tokenizer -----------------------------
_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<NUMBER>\d+\.\d+|\d+)
      | (?P<OP><=|>=|==|!=|<|>)
      | (?P<LPAREN>\()
      | (?P<RPAREN>\))
      | (?P<COMMA>,)
      | (?P<DOT>\.)
      | (?P<PLUS>\+)
      | (?P<MINUS>-)
      | (?P<STAR>\*)
      | (?P<SLASH>/)
      | (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)
    )
    """,
    re.VERBOSE,
)


@dataclass
class Tok:
    kind: str
    value: str


def tokenize(text: str) -> list[Tok]:
    pos = 0
    toks: list[Tok] = []
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise DSLError(f"Çözümlenemeyen karakter: {text[pos:pos+10]!r}")
        pos = m.end()
        kind = m.lastgroup
        toks.append(Tok(kind, m.group()))
    toks.append(Tok("EOF", ""))
    return toks


# ------------------------------- AST ---------------------------------
@dataclass
class Num:
    value: float


@dataclass
class Ref:
    name: str  # field veya kısayol (close, volume, macd, signal...)


@dataclass
class Call:
    name: str
    args: list
    output: str | None = None  # nokta ile seçilen çıktı kolonu


@dataclass
class BinOp:
    op: str
    left: object
    right: object


@dataclass
class Bool:
    op: str  # AND | OR
    left: object
    right: object


@dataclass
class Not:
    node: object


@dataclass
class Cross:
    direction: str  # up | down
    left: object
    right: object | None


# ----------------------------- Parser --------------------------------
class Parser:
    def __init__(self, toks: list[Tok]):
        self.toks = toks
        self.i = 0

    def peek(self) -> Tok:
        return self.toks[self.i]

    def next(self) -> Tok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def _is_kw(self, kw: str) -> bool:
        t = self.peek()
        return t.kind == "IDENT" and t.value.lower() == kw

    def parse(self):
        node = self.parse_or()
        if self.peek().kind != "EOF":
            raise DSLError(f"Beklenmeyen ifade: {self.peek().value!r}")
        return node

    def parse_or(self):
        node = self.parse_and()
        while self._is_kw("or"):
            self.next()
            node = Bool("OR", node, self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_not()
        while self._is_kw("and"):
            self.next()
            node = Bool("AND", node, self.parse_not())
        return node

    def parse_not(self):
        if self._is_kw("not"):
            self.next()
            return Not(self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_additive()
        # Cross Up / Cross Down
        if self._is_kw("cross"):
            self.next()
            d = self.peek()
            if d.kind != "IDENT" or d.value.lower() not in ("up", "down", "above", "below"):
                raise DSLError("'Cross' sonrası 'Up' veya 'Down' bekleniyor")
            self.next()
            direction = "up" if d.value.lower() in ("up", "above") else "down"
            # RHS opsiyonel: yoksa MACD->Signal, değilse 0
            if self.peek().kind in ("EOF", "RPAREN") or self._is_kw("and") or self._is_kw("or"):
                return Cross(direction, left, None)
            return Cross(direction, left, self.parse_additive())
        if self.peek().kind == "OP":
            op = self.next().value
            right = self.parse_additive()
            return BinOp(op, left, right)
        return left

    def parse_additive(self):
        node = self.parse_term()
        while self.peek().kind in ("PLUS", "MINUS"):
            op = self.next().value
            node = BinOp(op, node, self.parse_term())
        return node

    def parse_term(self):
        node = self.parse_factor()
        while self.peek().kind in ("STAR", "SLASH"):
            op = self.next().value
            node = BinOp(op, node, self.parse_factor())
        return node

    def parse_factor(self):
        t = self.peek()
        if t.kind == "NUMBER":
            self.next()
            return Num(float(t.value))
        if t.kind == "MINUS":
            self.next()
            return BinOp("-", Num(0.0), self.parse_factor())
        if t.kind == "LPAREN":
            self.next()
            node = self.parse_or()
            if self.next().kind != "RPAREN":
                raise DSLError("Kapanış parantezi ')' eksik")
            return node
        if t.kind == "IDENT":
            return self.parse_ident()
        raise DSLError(f"Beklenmeyen sembol: {t.value!r}")

    def parse_ident(self):
        name = self.next().value
        node: object
        if self.peek().kind == "LPAREN":
            self.next()
            args = []
            if self.peek().kind != "RPAREN":
                args.append(self.parse_arg())
                while self.peek().kind == "COMMA":
                    self.next()
                    args.append(self.parse_arg())
            if self.next().kind != "RPAREN":
                raise DSLError(f"{name}(...) kapanış parantezi eksik")
            node = Call(name, args)
        else:
            node = Ref(name)
        # nokta ile çıktı seçimi: BollingerBands(20).Upper
        if self.peek().kind == "DOT":
            self.next()
            out = self.next()
            if out.kind != "IDENT":
                raise DSLError("'.' sonrası çıktı adı bekleniyor")
            if isinstance(node, Ref):
                node = Call(node.name, [], output=out.value)
            else:
                node.output = out.value  # type: ignore[attr-defined]
        return node

    def parse_arg(self):
        # argüman: alan adı (close/volume) veya sayı veya iç içe çağrı
        t = self.peek()
        if t.kind == "IDENT" and t.value.lower() in _FIELDS and self.toks[self.i + 1].kind != "LPAREN":
            self.next()
            return Ref(t.value)
        return self.parse_additive()


def parse(text: str):
    if not text or not text.strip():
        raise DSLError("Boş kural")
    return Parser(tokenize(text)).parse()


# --------------------------- Evaluator -------------------------------
def _series(df: pd.DataFrame, node) -> pd.Series:
    val = _eval(df, node)
    if isinstance(val, (int, float)):
        return pd.Series(val, index=df.index, dtype=float)
    return val


def _eval(df: pd.DataFrame, node):
    if isinstance(node, Num):
        return node.value

    if isinstance(node, Ref):
        key = node.name.lower()
        if key in _FIELDS:
            from app.indicators._helpers import src
            return src(df, key)
        if key in _SHORTCUTS:
            ind, out = _SHORTCUTS[key]
            return compute(ind, df)[out]
        # parametresiz gösterge referansı (örn. RSI -> RSI())
        if node.name.upper() in REGISTRY:
            res = compute(node.name, df)
            return res.iloc[:, 0]
        raise DSLError(f"Bilinmeyen alan/gösterge: {node.name}")

    if isinstance(node, Call):
        return _eval_call(df, node)

    if isinstance(node, BinOp):
        left = _series(df, node.left)
        right = _series(df, node.right)
        op = node.op
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return left / right.replace(0, np.nan)
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        raise DSLError(f"Bilinmeyen operatör: {op}")

    if isinstance(node, Bool):
        left = _bool_series(df, node.left)
        right = _bool_series(df, node.right)
        return (left & right) if node.op == "AND" else (left | right)

    if isinstance(node, Not):
        return ~_bool_series(df, node.node)

    if isinstance(node, Cross):
        left = _series(df, node.left)
        if node.right is None:
            # MACD Cross Up -> Signal; aksi halde 0 çizgisi
            if isinstance(node.left, (Ref, Call)) and getattr(node.left, "name", "").upper() == "MACD":
                right = compute("MACD", df)["Signal"]
            else:
                right = pd.Series(0.0, index=df.index)
        else:
            right = _series(df, node.right)
        return crossover(left, right) if node.direction == "up" else crossunder(left, right)

    raise DSLError(f"Değerlendirilemeyen düğüm: {node}")


def _eval_call(df: pd.DataFrame, node: Call) -> pd.Series:
    spec = REGISTRY.get(node.name.upper())
    if spec is None:
        # SMA(Volume,20) gibi: kısayol değil ama bilinmeyen -> hata
        if node.name.lower() in _SHORTCUTS:
            ind, out = _SHORTCUTS[node.name.lower()]
            return compute(ind, df)[out]
        raise DSLError(f"Bilinmeyen gösterge: {node.name}")

    params: dict = {}
    numeric_params = [p for p in spec.params if p.type != "source"]
    source_param = next((p for p in spec.params if p.type == "source"), None)
    num_idx = 0
    for arg in node.args:
        if isinstance(arg, Ref) and arg.name.lower() in _FIELDS:
            if source_param is not None:
                params[source_param.name] = arg.name.lower()
            continue
        val = _eval(df, arg)
        if isinstance(val, pd.Series):
            raise DSLError(f"{node.name} parametresi sayısal olmalı")
        if num_idx < len(numeric_params):
            params[numeric_params[num_idx].name] = val
            num_idx += 1
    res = compute(node.name, df, params)
    if node.output:
        if node.output not in res.columns:
            raise DSLError(f"{node.name} çıktısı yok: {node.output}")
        return res[node.output]
    return res.iloc[:, 0]


def _bool_series(df: pd.DataFrame, node) -> pd.Series:
    val = _eval(df, node)
    if isinstance(val, pd.Series) and val.dtype == bool:
        return val
    if isinstance(val, pd.Series):
        return val != 0
    return pd.Series(bool(val), index=df.index)


def evaluate(df: pd.DataFrame, text: str) -> pd.Series:
    """Kuralı değerlendirir, boole Series döner (her bar için True/False)."""
    ast = parse(text)
    return _bool_series(df, ast)
