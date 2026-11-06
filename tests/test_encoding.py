"""Every text file is opened with an explicit encoding.

Windows' default encoding isn't UTF-8, so CI runs the Linux tests with `-X warn_default_encoding -W
error::EncodingWarning`. A plain local `pytest` doesn't, and a call without `encoding=` reached CI four times
(the last one on 2026-11-06). This finds those calls in the source, with or without the flag.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).parent.parent
TEXT_IO = {"open", "read_text", "write_text"}


def calls_without_encoding(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name not in TEXT_IO:
            continue
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in ("webbrowser", "os"):
            continue  # not files
        strings = [a.value for a in [*node.args, *(k.value for k in node.keywords)]
                   if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if any("b" in s for s in strings if len(s) <= 3):  # binary mode ("rb", "wb", "ab")
            continue
        if "encoding" not in {k.arg for k in node.keywords}:
            found.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    return found


def test_text_files_are_opened_with_an_explicit_encoding() -> None:
    sources = [*ROOT.glob("*.py"), *(p for d in ("idle_runner", "tests", "packaging") for p in (ROOT / d).rglob("*.py"))]
    assert [hit for path in sources for hit in calls_without_encoding(path)] == []
