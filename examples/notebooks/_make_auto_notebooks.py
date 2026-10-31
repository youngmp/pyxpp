"""
Build notebooks 05-08 from the plain-Python AUTO examples in ../scripts, so
the two stay in sync.  The module docstring becomes the first markdown cell,
each commented section header becomes a markdown heading followed by a code
cell, and the file-saving lines are dropped.

    python _make_auto_notebooks.py
    jupyter nbconvert --to notebook --execute --inplace 0[5-8]_*.ipynb
"""
import ast
import re
from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"

JOBS = [
    ("05_auto_normal_forms", "auto_normal_forms.py", "5. AUTO on normal forms"),
    ("06_auto_two_parameter", "auto_two_parameter.py", "6. Two-parameter continuation"),
    ("07_auto_period_doubling", "auto_period_doubling.py", "7. Period doubling from a simulated orbit"),
    ("08_auto_maps", "auto_maps.py", "8. AUTO on maps"),
]

# lines that only make sense in a script
DROP = re.compile(r'^(import matplotlib$|matplotlib\.use\(|fig\.savefig\(|print\("wrote )')
# "# --- 1. title ---"   or   "# ----\n# 1. title\n# ----"
RULE = re.compile(r"^# -{3,}\s*(.*?)\s*-*\s*$")


def docstring_md(doc, title):
    """Docstring -> markdown: indented lines become fenced text blocks."""
    lines = [l for l in doc.strip("\n").splitlines() if not l.strip().startswith("Run:")]
    out, block = [f"# {title}", ""], []

    def flush():
        if block:
            out.extend(["```text", *block, "```"])
            block.clear()

    for l in lines:
        if l.startswith("  ") and l.strip():
            block.append(l)
        else:
            flush()
            out.append(l.replace("Writes ", "The script version writes "))
    flush()
    return "\n".join(out).strip()


def split_sections(code):
    """[(heading or None, code)]"""
    out, head, buf = [], None, []
    lines = code.splitlines()
    i = 0
    while i < len(lines):
        m = RULE.match(lines[i])
        if m:
            title = m.group(1)
            j = i + 1
            if not title and j < len(lines) and lines[j].startswith("# ") and \
                    j + 1 < len(lines) and RULE.match(lines[j + 1]):
                title = lines[j][2:].strip()
                i = j + 1
            if buf and "".join(buf).strip():
                out.append((head, "\n".join(buf).strip("\n")))
            head, buf = title, []
            i += 1
            continue
        if not DROP.match(lines[i]):
            buf.append(lines[i])
        i += 1
    if buf and "".join(buf).strip():
        out.append((head, "\n".join(buf).strip("\n")))
    return out


def build(script, title):
    src = (SCRIPTS / script).read_text()
    tree = ast.parse(src)
    doc = ast.get_docstring(tree)
    body_start = tree.body[1].lineno - 1          # first statement after the docstring
    code = "\n".join(src.splitlines()[body_start:])
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3",
                                 "language": "python"}
    nb.cells.append(nbf.v4.new_markdown_cell(docstring_md(doc, title)))
    sections = split_sections(code)
    show_at_end = "plt.subplots" not in sections[-1][1]
    if show_at_end:
        # don't let the inline backend show the empty figure where it is made
        sections = [(h, re.sub(r"^(fig, axs? = plt\.subplots\(.*\))$",
                               r"\1\nplt.close(fig)  # drawn into below, shown at the end",
                               c, flags=re.M)) for h, c in sections]
    for head, chunk in sections:
        if head:
            nb.cells.append(nbf.v4.new_markdown_cell(f"## {head}"))
        nb.cells.append(nbf.v4.new_code_cell(chunk))
    # a figure created in an earlier cell is only shown if asked for at the end
    if show_at_end:
        nb.cells.append(nbf.v4.new_markdown_cell("## The figure"))
        nb.cells.append(nbf.v4.new_code_cell("fig"))
    return nb


for name, script, title in JOBS:
    nbf.write(build(script, title), HERE / f"{name}.ipynb")
    print("wrote", name)
