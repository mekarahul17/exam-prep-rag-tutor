from __future__ import annotations



import ast

import json

import logging

import math

import re

from contextlib import asynccontextmanager

from typing import Any



import sympy as sp

from fastapi import FastAPI, HTTPException

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

from mcp import ClientSession

from mcp.client.streamable_http import streamable_http_client

from common.llm_client import call_gemini



logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

MCP_URL = "http://127.0.0.1:8000/mcp"

MAX_EXPR = 300

MAX_POWER = 12

MAX_MATRIX = 8

_session: ClientSession | None = None



app = FastAPI(title="Exam Prep RAG Tutor",

              description="AI exam tutor with curriculum RAG and verified mathematics.",

              version="2.0.0")





@asynccontextmanager

async def lifespan(app: FastAPI):

    global _session

    try:

        async with streamable_http_client(MCP_URL) as (read, write, _):

            async with ClientSession(read, write) as session:

                await session.initialize()

                _session = session

                logger.info("Connected to MCP server")

                try:

                    yield

                finally:

                    _session = None

    except Exception:

        logger.exception("MCP connection failed")

        _session = None

        raise





app.router.lifespan_context = lifespan

app.add_middleware(

    CORSMiddleware,

    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],

    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],

)





class ChatRequest(BaseModel):

    student_id: str = Field(min_length=1, max_length=100)

    question: str = Field(min_length=1, max_length=5000)

    subject: str | None = Field(default=None, max_length=100)





# ---------------- SAFE SYMBOLIC PARSER ----------------



SYMS = {k: sp.Symbol(k) for k in

        ("x", "y", "z", "t", "n", "a", "b", "c", "r", "h")}

SYMS.update({"pi": sp.pi, "e": sp.E})

FUNCS = {

    "sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,

    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,

    "log": sp.log, "ln": sp.log, "exp": sp.exp, "abs": sp.Abs,

    "factorial": sp.factorial,

}





def normalize(s: str) -> str:

    for old, new in {

        "²": "^2", "³": "^3", "⁴": "^4", "−": "-", "–": "-",

        "×": "*", "·": "*", "÷": "/", "π": "pi", "√": "sqrt",

        "≤": "<=", "≥": ">=", "≠": "!=",

    }.items():

        s = s.replace(old, new)

    s = s.lower().replace("**", "^").strip()

    s = re.sub(r"(?<=[xyz])(?=**\(**)", "*", s)

    s = re.sub(r"(?<=**\)**)(?=[a-z0-9(])", "*", s)

    s = re.sub(r"(?<=\d)(?=**\(**)", "*", s)

    return s





def _ast_expr(node: ast.AST) -> sp.Expr:

    if isinstance(node, ast.Expression):

        return _ast_expr(node.body)

    if isinstance(node, ast.Constant):

        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):

            raise ValueError("Only numeric constants are allowed.")

        return sp.Rational(str(node.value))

    if isinstance(node, ast.Name):

        if node.id not in SYMS:

            raise ValueError(f"Unsupported symbol: {node.id}")

        return SYMS[node.id]

    if isinstance(node, ast.UnaryOp):

        v = _ast_expr(node.operand)

        if isinstance(node.op, ast.UAdd): return v

        if isinstance(node.op, ast.USub): return -v

        raise ValueError("Unsupported unary operator.")

    if isinstance(node, ast.BinOp):

        a, b = _ast_expr(node.left), _ast_expr(node.right)

        if isinstance(node.op, ast.Add): return a + b

        if isinstance(node.op, ast.Sub): return a - b

        if isinstance(node.op, ast.Mult): return a * b

        if isinstance(node.op, ast.Div):

            if b == 0: raise ValueError("Division by zero.")

            return a / b

        if isinstance(node.op, ast.Mod):

            if b == 0: raise ValueError("Modulo by zero.")

            return sp.Mod(a, b)

        if isinstance(node.op, ast.Pow):

            if b.is_number and b.is_real and abs(float(b)) > MAX_POWER:

                raise ValueError("Exponent exceeds the configured safety limit.")

            return a ** b

        raise ValueError("Unsupported operator.")

    if isinstance(node, ast.Call):

        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCS:

            raise ValueError("Unsupported function.")

        if node.keywords or len(node.args) != 1:

            raise ValueError("Use one positional argument for a function.")

        return FUNCS[node.func.id](_ast_expr(node.args[0]))

    raise ValueError("Invalid mathematical expression.")





def parse_expr_safe(raw: str) -> sp.Expr:

    s = normalize(raw).replace("^", "**")

    s = re.sub(r"(?<=\d)(?=[a-z])", "*", s)

    if not s or len(s) > MAX_EXPR or not re.fullmatch(r"[0-9a-z_+**\-***/%^().,\s]+", s):

        raise ValueError("Expression is empty, too long, or contains unsupported characters.")

    try:

        return sp.simplify(_ast_expr(ast.parse(s, mode="eval")))

    except (SyntaxError, TypeError, ValueError, ZeroDivisionError) as exc:

        raise ValueError("Could not safely parse the expression.") from exc





def pack(category: str, method: str, answer: Any, steps: list[str],

         verified: bool | None = None) -> dict:

    return {"success": True, "category": category, "method": method,

            "answer": str(answer), "steps": steps, "verified": verified}





# ---------------- ALGEBRA / EQUATIONS ----------------



def solve_equation(q: str) -> dict | None:

    # Parse the first compact equality; do not treat prose as part of an expression.

    cleaned = re.sub(r"^\s*(?:solve|find|calculate|what is)\s+", "", normalize(q))

    m = re.search(r"([0-9a-z_+**\-***/%^().\s]{1,180}?)\s*=\s*"

                  r"([0-9a-z_+**\-***/%^().\s]{1,180}?)(?=$|[?.!,;])", cleaned)

    if not m:

        return None

    try:

        left, right = parse_expr_safe(m.group(1)), parse_expr_safe(m.group(2))

        symbols = sorted((left-right).free_symbols, key=lambda x: x.name)

        if not symbols:

            ok = sp.simplify(left-right) == 0

            return pack("algebra", "constant equality", ok,

                        [f"Left side: {left}", f"Right side: {right}"], bool(ok))

        x = symbols[0]

        sol = sp.solveset(sp.Eq(left, right), x, domain=sp.S.Complexes)

        if sol is sp.S.EmptySet:

            answer, verified = "No solution", True

        elif isinstance(sol, sp.FiniteSet):

            answer = sorted(map(sp.sstr, sol))

            verified = all(sp.simplify((left-right).subs(x, v)) == 0 for v in sol)

        else:

            answer, verified = sol, None

        return pack("algebra", "symbolic equation solving", answer,

                    [f"Equation: {sp.Eq(left, right)}",

                     f"Rearrange: {sp.expand(left-right)} = 0",

                     f"Solve for {x}: {answer}",

                     "Substitute finite solutions into the original equation."], verified)

    except Exception as exc:

        logger.debug("Equation parser skipped: %s", exc)

        return None





def solve_expression(q: str) -> dict | None:

    m = re.search(r"\b(simplify|expand|factor|evaluate|calculate)\s+(.+?)(?:[?.]|$)",

                  normalize(q))

    if not m: return None

    action, raw = m.group(1), m.group(2).strip()

    try:

        expr = parse_expr_safe(raw)

        if action == "expand": ans = sp.expand(expr)

        elif action == "factor": ans = sp.factor(expr)

        elif action == "evaluate": ans = sp.N(expr)

        elif action == "calculate": ans = sp.N(expr) if not expr.free_symbols else sp.simplify(expr)

        else: ans = sp.simplify(expr)

        return pack("algebra", action, ans,

                    [f"Expression: {expr}", f"Apply {action}.", f"Result: {ans}"], True)

    except Exception as exc:

        logger.debug("Expression solver skipped: %s", exc)

        return None





# ---------------- CALCULUS ----------------



def solve_calculus(q: str) -> dict | None:

    text, x = normalize(q), SYMS["x"]

    patterns = [

        (r"\b(?:differentiate|derivative of|find derivative of)\s+(.+?)(?:\s+with respect to x|$|[?.])", "diff"),

        (r"\b(?:integrate|integration of|find integral of)\s+(.+?)(?:\s+with respect to x|$|[?.])", "integrate"),

    ]

    for pattern, action in patterns:

        m = re.search(pattern, text)

        if m:

            try:

                expr = parse_expr_safe(m.group(1))

                ans = sp.diff(expr, x) if action == "diff" else sp.integrate(expr, x)

                valid = sp.simplify(sp.diff(ans, x)-expr) == 0 if action == "integrate" else True

                suffix = "" if action == "diff" else " + C"

                return pack("calculus", "differentiation" if action == "diff" else "indefinite integration",

                            f"{ans}{suffix}",

                            [f"Given expression: {expr}",

                             "Apply the relevant calculus rules.",

                             f"Result: {ans}{suffix}"], valid)

            except Exception as exc:

                logger.debug("Calculus parser skipped: %s", exc)

    m = re.search(r"\blimit\s+(.+?)\s+as\s+x\s+(?:approaches|tends to)\s+([+**\-**]?\w+)", text)

    if m:

        try:

            expr = parse_expr_safe(m.group(1))

            p = {"infinity": sp.oo, "oo": sp.oo, "-infinity": -sp.oo, "-oo": -sp.oo}.get(m.group(2))

            if p is None: p = parse_expr_safe(m.group(2))

            ans = sp.limit(expr, x, p)

            return pack("calculus", "limit", ans,

                        [f"Function: {expr}", f"x approaches {p}.", f"Limit: {ans}"], None)

        except Exception as exc:

            logger.debug("Limit solver skipped: %s", exc)

    return None





# ---------------- SEQUENCES ----------------



def solve_sequence(q: str) -> dict | None:

    m = re.search(r"(?:sequence|series)\s*[:**\-**]?\s*((?:-?\d+(?:**\.**\d+)?\s*,\s*){2,}-?\d+(?:**\.**\d+)?)",

                  normalize(q))

    if not m: return None

    vals = [sp.Rational(v.strip()) for v in m.group(1).split(",")]

    d = [sp.simplify(vals[i+1]-vals[i]) for i in range(len(vals)-1)]

    if len(set(d)) == 1:

        ans = vals[-1] + d[0]

        return pack("sequences", "arithmetic progression", ans,

                    [f"Terms: {vals}", f"Common difference: {d[0]}",

                     f"Next term = {vals[-1]} + {d[0]} = {ans}"], True)

    if all(v != 0 for v in vals[:-1]):

        ratios = [sp.simplify(vals[i+1]/vals[i]) for i in range(len(vals)-1)]

        if len(set(ratios)) == 1:

            ans = vals[-1]*ratios[0]

            return pack("sequences", "geometric progression", ans,

                        [f"Terms: {vals}", f"Common ratio: {ratios[0]}",

                         f"Next term = {vals[-1]} × {ratios[0]} = {ans}"], True)

    return None





# ---------------- ARITHMETIC WORD PROBLEMS ----------------



def solve_arithmetic(q: str) -> dict | None:

    text = normalize(q)

    nums = [sp.Rational(v) for v in re.findall(r"(?<![a-z])\d+(?:**\.**\d+)?", text)]

    try:

        if ("percent" in text or "%" in text or "percentage" in text) and len(nums) >= 2:

            p, value = nums[:2]

            ans = p*value/100

            return pack("arithmetic", "percentage", ans,

                        [f"Find {p}% of {value}.", f"({p}/100) × {value} = {ans}"], True)

        if "simple interest" in text and len(nums) >= 3:

            p, r, t = nums[:3]

            si = p*r*t/100

            return pack("arithmetic", "simple interest", si,

                        [f"P={p}, R={r}%, T={t}", "SI = (P × R × T) / 100",

                         f"SI = {si}; total amount = {p+si}"], True)

        if "compound interest" in text and len(nums) >= 3:

            p, r, t = nums[:3]

            amount = p*(1+r/100)**t

            return pack("arithmetic", "annual compound interest", sp.simplify(amount-p),

                        [f"P={p}, R={r}%, T={t}", "A = P(1 + R/100)^T",

                         f"Amount = {amount}; CI = {sp.simplify(amount-p)}"], True)

        if ("average" in text or "mean" in text) and len(nums) >= 2:

            ans = sp.Rational(sum(nums), len(nums))

            return pack("statistics", "mean", ans,

                        [f"Values: {nums}", "Mean = sum / count", f"Mean = {ans}"], True)

        if ("profit" in text or "loss" in text) and len(nums) >= 2:

            cp, sp_ = nums[:2]

            if cp == 0: return pack("arithmetic", "profit/loss", "Undefined: cost price is zero.", [], False)

            diff = sp_-cp

            label = "Profit" if diff > 0 else "Loss" if diff < 0 else "No profit or loss"

            pct = abs(diff)/cp*100

            return pack("arithmetic", "profit and loss", f"{label} = {abs(diff)} ({pct}%)",

                        [f"Cost price={cp}; selling price={sp_}",

                         f"Difference = SP - CP = {diff}", f"Percentage = |difference|/CP × 100 = {pct}%"], True)

        if "speed" in text and "time" in text and len(nums) >= 2:

            distance, duration = nums[:2]

            if duration <= 0: return pack("arithmetic", "speed", "Time must be positive.", [], False)

            ans = distance/duration

            return pack("arithmetic", "speed-distance-time", ans,

                        [f"Distance={distance}; time={duration}", "Speed = distance / time", f"Speed={ans}"], True)

    except Exception as exc:

        logger.debug("Arithmetic solver skipped: %s", exc)

    return None





# ---------------- GEOMETRY ----------------



def solve_geometry(q: str) -> dict | None:

    text = normalize(q)

    nums = [sp.Rational(v) for v in re.findall(r"(?<![a-z])-?\d+(?:**\.**\d+)?", text)]

    if not nums: return None

    try:

        if "circle" in text and ("area" in text or "circumference" in text):

            r = nums[0]

            if r < 0: raise ValueError("Radius cannot be negative.")

            method, ans = ("circumference", 2*sp.pi*r) if "circumference" in text else ("area", sp.pi*r**2)

            formula = "C = 2πr" if method == "circumference" else "A = πr²"

        elif "rectangle" in text and ("area" in text or "perimeter" in text) and len(nums) >= 2:

            l, w = nums[:2]

            if min(l,w) < 0: raise ValueError("Dimensions cannot be negative.")

            method, ans = ("perimeter", 2*(l+w)) if "perimeter" in text else ("area", l*w)

            formula = "P = 2(l+w)" if method == "perimeter" else "A = l × w"

        elif "square" in text and ("area" in text or "perimeter" in text):

            a = nums[0]

            if a < 0: raise ValueError("Side cannot be negative.")

            method, ans = ("perimeter", 4*a) if "perimeter" in text else ("area", a**2)

            formula = "P = 4a" if method == "perimeter" else "A = a²"

        elif "triangle" in text and "area" in text and len(nums) >= 2:

            b, h = nums[:2]

            if min(b,h) < 0: raise ValueError("Dimensions cannot be negative.")

            method, ans, formula = "triangle area", b*h/2, "A = 1/2 × base × height"

        elif "cube" in text and ("volume" in text or "surface area" in text):

            a = nums[0]

            if a < 0: raise ValueError("Side cannot be negative.")

            method, ans = ("surface area", 6*a**2) if "surface area" in text else ("volume", a**3)

            formula = "SA = 6a²" if "surface area" in text else "V = a³"

        else:

            return None

        return pack("geometry", method, ans,

                    [f"Given measurements: {nums}", formula, f"Answer = {ans}"], True)

    except Exception as exc:

        return pack("geometry", "geometry calculation", str(exc), [], False)





# ---------------- TRIGONOMETRY ----------------



def solve_trigonometry(q: str) -> dict | None:

    m = re.search(r"\b(sin|cos|tan)\s***\(**\s*(-?\d+(?:**\.**\d+)?)\s*(degrees?|deg|°)?\s***\)**",

                  normalize(q))

    if not m: return None

    fn, raw, unit = m.groups()

    angle = sp.Rational(raw)

    rad = angle*sp.pi/180 if unit else angle

    ans = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan}[fn](rad)

    ans = sp.simplify(ans)

    if ans in (sp.zoo, sp.nan, sp.oo, -sp.oo):

        return pack("trigonometry", fn, "Undefined", [f"{fn} is undefined at this angle."], False)

    return pack("trigonometry", f"{fn} evaluation", ans,

                [f"Angle = {angle}{' degrees' if unit else ' radians'}",

                 f"Radians = {rad}", f"{fn}({angle}) = {ans}"], True)





# ---------------- STATISTICS / PROBABILITY ----------------



def _data_values(q: str) -> list[sp.Rational] | None:

    m = re.search(r"(?:data|values|numbers)\s*(?:are|:)?\s*((?:-?\d+(?:**\.**\d+)?\s*,\s*)+-?\d+(?:**\.**\d+)?)",

                  normalize(q))

    if not m: return None

    vals = [sp.Rational(v.strip()) for v in m.group(1).split(",")]

    return vals if 1 <= len(vals) <= 30 else None





def solve_statistics(q: str) -> dict | None:

    vals = _data_values(q)

    if not vals: return None

    text = normalize(q)

    if "median" in text:

        ordered = sorted(vals); n = len(ordered); mid = n//2

        ans = ordered[mid] if n%2 else (ordered[mid-1]+ordered[mid])/2

        method = "median"

    elif "mode" in text:

        counts = {v: vals.count(v) for v in set(vals)}

        high = max(counts.values())

        ans = sorted(v for v,c in counts.items() if c == high) if high > 1 else "No mode"

        method = "mode"

    elif "variance" in text or "standard deviation" in text:

        mean = sp.Rational(sum(vals), len(vals))

        var = sp.simplify(sum((v-mean)**2 for v in vals)/len(vals))

        ans = sp.sqrt(var) if "standard deviation" in text else var

        method = "population standard deviation" if "standard deviation" in text else "population variance"

    else:

        ans, method = sp.Rational(sum(vals), len(vals)), "mean"

    return pack("statistics", method, ans,

                [f"Data: {vals}", f"Calculate {method} using the given observations.",

                 f"{method.title()} = {ans}"], True)





def solve_probability(q: str) -> dict | None:

    text = normalize(q)

    m = re.search(r"probability\s+(?:of\s+)?(?:getting\s+)?(\d+)\s+(?:favourable|favorable)\s+(?:out of|from)\s+(\d+)", text)

    if not m:

        m = re.search(r"(\d+)\s+favourable outcomes?\s+out of\s+(\d+)", text)

    if not m: return None

    good, total = map(int, m.groups())

    if total <= 0 or good < 0 or good > total:

        return pack("probability", "classical probability", "Invalid outcome counts.",

                    ["Require total > 0 and 0 ≤ favourable outcomes ≤ total outcomes."], False)

    ans = sp.Rational(good, total)

    return pack("probability", "classical probability", ans,

                [f"Favourable outcomes = {good}", f"Total outcomes = {total}",

                 f"P(E) = favourable / total = {ans}"], True)





# ---------------- MATRICES / VECTORS ----------------



def solve_matrix(q: str) -> dict | None:

    text = normalize(q)

    m = re.search(r"(?:determinant|det|inverse)\s*(**\[\[**.*?**\]\]**)", text)

    if not m: return None

    try:

        raw = ast.literal_eval(m.group(1))

        if not isinstance(raw, list) or not raw or len(raw) > MAX_MATRIX:

            raise ValueError("Matrix size is outside supported limits.")

        if any(not isinstance(row, list) or len(row) != len(raw) for row in raw):

            raise ValueError("Matrix must be square.")

        if any(len(row) > MAX_MATRIX for row in raw):

            raise ValueError("Matrix is too large.")

        mat = sp.Matrix(raw)

        if "inverse" in text:

            if mat.det() == 0:

                return pack("matrices", "inverse", "No inverse: matrix is singular.",

                            [f"Determinant = {mat.det()}"], True)

            ans, method = mat.inv(), "matrix inverse"

        else:

            ans, method = mat.det(), "determinant"

        return pack("matrices", method, ans,

                    [f"Matrix = {mat}", f"Result = {ans}"], True)

    except Exception as exc:

        return pack("matrices", "matrix operation", f"Invalid matrix: {exc}",

                    ["Use a square numeric matrix, e.g. [[1,2],[3,4]]."], False)





def solve_vector(q: str) -> dict | None:

    m = re.search(r"(?:dot product|dot)\s*(**\[**[^**\]**]+**\]**)\s*(?:and|,)\s*(**\[**[^**\]**]+**\]**)",

                  normalize(q))

    if not m: return None

    try:

        a, b = ast.literal_eval(m.group(1)), ast.literal_eval(m.group(2))

        if not isinstance(a,list) or not isinstance(b,list) or not a or len(a)!=len(b):

            raise ValueError("Vectors must have equal non-zero dimensions.")

        ans = sum(sp.sympify(x)*sp.sympify(y) for x,y in zip(a,b))

        return pack("vectors", "dot product", ans,

                    [f"Vectors: {a} and {b}", "Multiply corresponding entries and add.",

                     f"Dot product = {ans}"], True)

    except Exception as exc:

        return pack("vectors", "dot product", f"Invalid vectors: {exc}", [], False)









# ---------------- NUMBER THEORY / RATIOS / COMBINATORICS ----------------



def solve_number_theory(q: str) -> dict | None:

    text = normalize(q)

    nums = [int(v) for v in re.findall(r"(?<![a-z])-?\d+", text)]

    if ("hcf" in text or "gcd" in text or "gcf" in text) and len(nums) >= 2:

        from math import gcd

        vals = [abs(v) for v in nums[:10]]

        ans = vals[0]

        for v in vals[1:]:

            ans = gcd(ans, v)

        return pack("number_system", "HCF/GCD", ans,

                    [f"Numbers: {vals}", "Find the greatest common divisor.", f"HCF = {ans}"], True)

    if ("lcm" in text) and len(nums) >= 2:

        from math import gcd

        vals = [abs(v) for v in nums[:10]]

        ans = vals[0]

        for v in vals[1:]:

            ans = 0 if ans == 0 or v == 0 else abs(ans*v)//gcd(ans, v)

        return pack("number_system", "LCM", ans,

                    [f"Numbers: {vals}", "Use LCM(a,b) = |a×b| / HCF(a,b).", f"LCM = {ans}"], True)

    if "ratio" in text and "common ratio" not in text and len(nums) >= 2:

        from math import gcd

        a, b = nums[:2]

        if a < 0 or b < 0 or (a == 0 and b == 0):

            return pack("arithmetic", "ratio", "Invalid ratio values.", [], False)

        g = gcd(a, b) or 1

        ans = f"{a//g}:{b//g}"

        return pack("arithmetic", "ratio simplification", ans,

                    [f"Original ratio = {a}:{b}", f"Divide both terms by HCF {g}.", f"Simplified ratio = {ans}"], True)

    return None





def solve_combinatorics(q: str) -> dict | None:

    text = normalize(q)

    m = re.search(r"\b(\d+)\s*([pc])\s*(\d+)\b", text)

    if not m:

        m = re.search(r"\b(?:permutation|combination)\s+(?:of\s+)?(\d+)\s+(?:choose|from|taken\s+)?(\d+)\b", text)

        if m:

            n, r = map(int, m.groups())

            kind = "c" if "combination" in text else "p"

        else:

            return None

    else:

        n, kind, r = int(m.group(1)), m.group(2), int(m.group(3))

    if n < 0 or r < 0 or r > n:

        return pack("combinatorics", "permutation/combination", "Require n ≥ r ≥ 0.", [], False)

    ans = math.factorial(n)//math.factorial(n-r) if kind == "p" else math.factorial(n)//(math.factorial(r)*math.factorial(n-r))

    label = "permutation" if kind == "p" else "combination"

    formula = "nPr = n!/(n-r)!" if kind == "p" else "nCr = n!/[r!(n-r)!]"

    return pack("combinatorics", label, ans,

                [f"n = {n}, r = {r}", formula, f"Answer = {ans}"], True)





def solve_inequality(q: str) -> dict | None:

    text = re.sub(r"^\s*(?:solve|find)\s+", "", normalize(q))

    m = re.search(r"([0-9a-z_+**\-***/%^().\s]{1,120}?)\s*(<=|>=|<|>)\s*([0-9a-z_+**\-***/%^().\s]{1,120}?)(?=$|[?.!,;])", text)

    if not m:

        return None

    try:

        left, right = parse_expr_safe(m.group(1)), parse_expr_safe(m.group(3))

        syms = sorted((left-right).free_symbols, key=lambda x: x.name)

        if len(syms) != 1:

            return None

        x = syms[0]

        rel = {"<": sp.Lt, ">": sp.Gt, "<=": sp.Le, ">=": sp.Ge}[m.group(2)](left, right)

        ans = sp.solve_univariate_inequality(rel, x, relational=False)

        return pack("algebra", "inequality solving", ans,

                    [f"Inequality: {rel}", f"Solve for {x} over the real numbers.",

                     f"Solution set = {ans}"], None)

    except Exception as exc:

        logger.debug("Inequality solver skipped: %s", exc)

        return None





def solve_ap_gp_formula(q: str) -> dict | None:

    text = normalize(q)

    nth = re.search(r"\b(\d+)(?:th|st|nd|rd)\s+term\b|\bn\s*=\s*(\d+)", text)

    n = int(next(g for g in nth.groups() if g)) if nth else None

    first = re.search(r"(?:first term|initial term)\s*(?:is|=)?\s*(-?\d+)", text)

    ap_d = re.search(r"(?:common difference|difference)\s*(?:is|=)?\s*(-?\d+)", text)

    gp_r = re.search(r"(?:common ratio)\s*(?:is|=)?\s*(-?\d+)", text)



    if n is not None and first and (" ap " in f" {text} " or "arithmetic progression" in text) and ap_d:

        a, d = int(first.group(1)), int(ap_d.group(1))

        if n <= 0:

            return pack("sequences", "AP nth term", "n must be positive.", [], False)

        ans = a + (n-1)*d

        return pack("sequences", "AP nth term", ans,

                    [f"First term a={a}, common difference d={d}, n={n}",

                     "a_n = a + (n-1)d", f"a_{n} = {a} + ({n}-1)×{d} = {ans}"], True)



    if n is not None and first and (" gp " in f" {text} " or "geometric progression" in text) and gp_r:

        a, r = int(first.group(1)), int(gp_r.group(1))

        if n <= 0:

            return pack("sequences", "GP nth term", "n must be positive.", [], False)

        ans = a * r**(n-1)

        return pack("sequences", "GP nth term", ans,

                    [f"First term a={a}, common ratio r={r}, n={n}",

                     "a_n = ar^(n-1)", f"a_{n} = {a}×{r}^{n-1} = {ans}"], True)

    return None





# ---------------- UNIFIED DISPATCHER ----------------



def solve_math_question(question: str) -> dict | None:

    if not isinstance(question, str) or not question.strip():

        return None

    for fn in (solve_calculus, solve_ap_gp_formula, solve_sequence,

               solve_number_theory, solve_combinatorics, solve_inequality,

               solve_arithmetic, solve_geometry, solve_trigonometry,

               solve_statistics, solve_probability, solve_matrix,

               solve_vector, solve_equation, solve_expression):

        try:

            output = fn(question)

            if output is not None:

                return output

        except Exception:

            logger.exception("Mathematics handler failed: %s", fn.__name__)

    return None





# Run using:

# python -c "from client.app import run_math_self_tests; print(run_math_self_tests())"

def run_math_self_tests() -> dict:

    cases = [

        ("Solve 2x^2 - 3x + 1 = 0", "algebra"),

        ("Solve 2x + 5 = 15", "algebra"),

        ("Simplify (x+1)(x-1)", "algebra"),

        ("Differentiate x^3 + 2x^2 + 4x", "calculus"),

        ("Integrate 3*x^2 + 2*x", "calculus"),

        ("Sequence: 2, 5, 8, 11", "sequences"),

        ("Find 20 percent of 250", "arithmetic"),

        ("Find simple interest for 1000 at 5 percent for 2 years", "arithmetic"),

        ("Find area of circle radius 7", "geometry"),

        ("Find area of rectangle 8 and 5", "geometry"),

        ("Find sin(30 degrees)", "trigonometry"),

        ("Find median of data: 1, 3, 5, 7, 9", "statistics"),

        ("Find probability of getting 2 favourable outcomes out of 6", "probability"),

        ("Find determinant [[1,2],[3,4]]", "matrices"),

        ("Find dot product [1,2,3] and [4,5,6]", "vectors"),

        ("Solve x^2 + 1 = 0", "algebra"),

        ("Find HCF of 12 and 18", "number_system"),

        ("Find LCM of 4 and 6", "number_system"),

        ("Simplify ratio 12:18", "arithmetic"),

        ("Find 5C2", "combinatorics"),

        ("Find 5P2", "combinatorics"),

        ("Solve x > 2", "algebra"),

    ]

    failures = []

    for question, category in cases:

        got = solve_math_question(question)

        if not got or not got.get("success") or got.get("category") != category:

            failures.append({"question": question, "expected": category, "actual": got})

    return {"total": len(cases), "passed": len(cases)-len(failures),

            "failed": len(failures), "failures": failures}





# ---------------- API ----------------



@app.get("/health")

async def health():

    return {"status": "ok", "mcp_connected": _session is not None, "version": app.version}





@app.post("/chat")

async def chat(request: ChatRequest):

    if _session is None:

        raise HTTPException(status_code=503,

                            detail="MCP server is not connected. Start it first.")

    question = request.question.strip()

    if not question:

        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    try:

        retrieved = await _session.call_tool(

            "search_curriculum",

            {"query": question, "subject": request.subject,

             "student_id": request.student_id},

        )

        if getattr(retrieved, "isError", False):
            error_details = "\n".join(
                item.text
                for item in (retrieved.content or [])
                if hasattr(item, "text") and item.text
            )

            logger.error(
                "MCP search_curriculum error details: %s",
                error_details or repr(retrieved)
            )

            raise RuntimeError(
                f"Curriculum retrieval failed: {error_details or repr(retrieved)}"
            )

        chunks = [item.text.strip() for item in (retrieved.content or [])

                  if hasattr(item, "text") and item.text and item.text.strip()]

        context = "\n\n".join(chunks) or (

            "No relevant study material was retrieved. Do not claim curriculum grounding."

        )

        math_result = solve_math_question(question)

        math_context = json.dumps(math_result, indent=2, ensure_ascii=False) if math_result else (

            "No deterministic result was generated. Solve cautiously and disclose ambiguity."

        )

        prompt = f"""

You are a careful examination tutor.



STUDENT QUESTION:

{question}



SUBJECT:

{request.subject or "Not specified"}



RETRIEVED CURRICULUM MATERIAL:

<context>

{context}

</context>



DETERMINISTIC MATHEMATICS RESULT:

<math_result>

{math_context}

</math_result>



INSTRUCTIONS:

1. Answer the exact question in simple, student-friendly language.

2. For mathematics, show the method and calculations step by step.

3. If a deterministic result is supplied, use its answer and steps; do not contradict it.

4. If verified is false, clearly explain that the calculation could not be verified.

5. If no deterministic result is supplied, solve cautiously and do not claim software verification.

6. Check signs, units, domains, constraints, special cases and division by zero.

7. State assumptions and missing information in word problems.

8. Use retrieved curriculum material as the primary source for syllabus explanations.

9. If retrieved material is insufficient, say so; never invent textbook citations or page numbers.

10. Separate general explanation from curriculum-supported claims.

11. Finish with a concise exam-revision takeaway.

12. Do not reveal internal implementation details.

"""

        answer = call_gemini(

            prompt=prompt,

            system=("You are a mathematically careful exam tutor. Prefer verified computation "

                    "over guessing. Never fabricate verification, citations, or missing conditions."),

            max_tokens=3000,

        )

        if not answer or not answer.strip():

            raise RuntimeError("Gemini returned an empty answer.")

        return {"question": question, "answer": answer.strip(),

                "context": context, "subject": request.subject,

                "math_verification": math_result}

    except HTTPException:

        raise

    except Exception as exc:

        logger.exception("Chat request failed")

        raise HTTPException(status_code=500,

                            detail="Unable to process the question. Check backend logs.") from exc

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(

        "client.app:app",

        host="127.0.0.1",

        port=8001,

        reload=False

    )
