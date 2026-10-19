"""Tutor agent: clear explanations, examples, and worked reasoning."""

from collections.abc import Callable, Sequence
import ast
import operator
import re

from .common import build_agent_prompt

AnswerFunction = Callable[[str], str]

TUTOR_INSTRUCTIONS = (
    "You are the Tutor Agent. Answer the learner's actual question directly. "
    "Explain the key idea in short ordered steps, define unfamiliar terms, and add a simple example when useful. "
    "Show calculation steps and correct misunderstandings kindly. Use only facts supported by the supplied search "
    "sources; say when they do not support a conclusion. Keep the response concise and finish with one optional "
    "check question or tiny practice task. If supplied passages carry filename and page labels, cite those exact "
    "labels for document-based facts and never invent a page reference."
)

_SIMPLE_ARITHMETIC = re.compile(
    r"^\s*(?:what\s+is\s+)?(\d+(?:\.\d+)?\s*(?:\+|-|\*|×|/|÷)\s*\d+(?:\.\d+)?)(?:\s*[?=])?\s*$",
    re.IGNORECASE,
)
_ARITHMETIC_OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _simple_arithmetic_answer(question: str) -> str | None:
    """Handle one safe arithmetic operation locally without a search request."""
    match = _SIMPLE_ARITHMETIC.fullmatch(question)
    if not match:
        return None
    expression = match.group(1).replace("×", "*").replace("÷", "/")
    try:
        tree = ast.parse(expression, mode="eval").body
        if not isinstance(tree, ast.BinOp) or type(tree.op) not in _ARITHMETIC_OPERATORS:
            return None
        if not isinstance(tree.left, ast.Constant) or not isinstance(tree.right, ast.Constant):
            return None
        if type(tree.left.value) not in (int, float) or type(tree.right.value) not in (int, float):
            return None
        left, right = float(tree.left.value), float(tree.right.value)
        if max(abs(left), abs(right)) > 1_000_000 or (isinstance(tree.op, ast.Div) and right == 0):
            return None
        result = _ARITHMETIC_OPERATORS[type(tree.op)](left, right)
        if not abs(result) <= 1_000_000_000:
            return None
        formatted = str(int(result)) if result.is_integer() else f"{result:.8g}"
        return f"The answer is {formatted}.\n\n1. Work out {expression}: {formatted}.\n2. Try this one: {formatted} + 1."
    except (SyntaxError, ZeroDivisionError, OverflowError, ValueError):
        return None


def respond(question: str, answer: AnswerFunction, history: Sequence[dict] = ()) -> str:
    """Create a tutor answer through the injected existing provider."""
    arithmetic_answer = _simple_arithmetic_answer(question)
    if arithmetic_answer is not None:
        return arithmetic_answer
    return answer(build_agent_prompt(TUTOR_INSTRUCTIONS, question, history))
