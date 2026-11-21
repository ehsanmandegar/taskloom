"""One-off migration: turn the hand-coloured styles.css into Radix Themes tokens.

* drops the hand-written `html[data-theme="dark"]` override blocks (dark mode now comes from the tokens)
* maps every hex colour to a Radix scale step by hue family, lightness and what the property is used for
  (background / text / border), so light AND dark look right without per-theme rules.

Usage: python scripts/tokenize_css.py src/styles.css
"""

import colorsys
import re
import sys
from pathlib import Path

DARK = 'data-theme="dark"'


# ---------------------------------------------------------------- rule-level parsing (handles @media nesting)
def split_blocks(css: str):
    """Yield (prelude, body) for each top-level block, plus ('', text) for loose text such as @import."""
    i, n = 0, len(css)
    while i < n:
        brace = css.find("{", i)
        semi = css.find(";", i)
        if brace == -1:
            if css[i:].strip():
                yield css[i:], None
            return
        if 0 <= semi < brace and css[i:semi].lstrip().startswith("@"):
            yield css[i:semi + 1], None
            i = semi + 1
            continue
        depth, j = 1, brace + 1
        while j < n and depth:
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            j += 1
        yield css[i:brace], css[brace + 1:j - 1]
        i = j


def strip_dark(css: str) -> str:
    out = []
    for prelude, body in split_blocks(css):
        if body is None:
            out.append(prelude)
            continue
        head = prelude.strip()
        if head.startswith("@"):
            inner = strip_dark(body)
            if inner.strip():
                out.append(f"{head}{{{inner}}}")
            continue
        kept = [s for s in (x.strip() for x in head.split(",")) if DARK not in s]
        if kept:
            out.append(f"{','.join(kept)}{{{body}}}")
    return "".join(out)


# ----------------------------------------------------------------------------------------- colour mapping
def parse_hex(token: str):
    h = token[1:]
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[k:k + 2], 16) / 255 for k in (0, 2, 4))
    alpha = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return r, g, b, alpha


def classify(r, g, b):
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    hue, light, sat = hue * 360, light * 100, sat * 100
    if sat < 16 or (light > 94 and sat < 35):
        family = "gray"
    elif 70 <= hue < 175:
        family = "accent"          # the green brand colour
    elif hue < 18 or hue >= 335:
        family = "red"
    elif hue < 48:
        family = "orange"
    elif hue < 70:
        family = "amber"
    elif 175 <= hue < 270:
        family = "blue"
    else:
        family = "purple"
    return family, light, sat


def step(value, table):
    for limit, token in table:
        if value >= limit:
            return token
    return table[-1][1]


BACKGROUND = [(98.5, 2), (96, 2), (93, 3), (90, 4), (86.5, 5), (82, 6), (72, 7), (60, 8), (0, 9)]
BORDER = [(93, 4), (88, 5), (83, 6), (74, 7), (58, 8), (0, 9)]
TEXT = [(65, 9), (50, 10), (0, 11)]


def token(family, light, kind, sat):
    if kind == "text":
        if light >= 85:
            return "var(--accent-contrast)"
        if family == "gray":
            return f"var(--gray-{12 if light < 30 else 11 if light < 52 else 10 if light < 70 else 9})"
        return f"var(--{family}-{11 if light < 52 else 9})"
    if kind == "border":
        return f"var(--{family}-{step(light, BORDER)})"
    # background
    if family == "gray" and light >= 98.5:
        return "var(--color-panel-solid)"
    if light < 26 and sat < 22:
        return None  # near-black consoles / code blocks stay dark in both themes
    if light < 50:
        return f"var(--{family}-9)" if family != "gray" else "var(--gray-11)"
    return f"var(--{family}-{step(light, BACKGROUND)})"


def kind_of(prop: str):
    prop = prop.strip().lower()
    if prop.startswith(("border", "outline")) or prop in {"column-rule", "stroke"}:
        return "border"
    if prop in {"color", "fill", "caret-color", "text-decoration-color"}:
        return "text"
    if prop.startswith("background"):
        return "background"
    return None  # shadows, filters, ... keep their literal colours


HEX = re.compile(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3,4}\b")
DECL = re.compile(r"([a-zA-Z-]+)\s*:\s*([^;{}]+)")


def convert_value(prop: str, value: str) -> str:
    kind = kind_of(prop)
    if kind is None or "url(" in value:
        return value

    def repl(match):
        r, g, b, alpha = parse_hex(match.group(0))
        family, light, sat = classify(r, g, b)
        mapped = token(family, light, kind, sat)
        if mapped is None:
            return match.group(0)
        if alpha < 0.98:
            return f"color-mix(in srgb,{mapped} {round(alpha * 100)}%,transparent)"
        return mapped

    return HEX.sub(repl, value)


def convert(css: str) -> str:
    out = []
    for prelude, body in split_blocks(css):
        if body is None:
            out.append(prelude)
            continue
        head = prelude.strip()
        if head.startswith("@"):
            out.append(f"{head}{{{convert(body)}}}" if head.startswith("@media") else f"{head}{{{body}}}")
            continue
        if re.match(r"^(@|:root)", head) and head != ":root":
            out.append(f"{head}{{{body}}}")
            continue
        if "syntax-" in head:  # the code viewer keeps its fixed editor palette in both themes
            out.append(f"{head}{{{body}}}")
            continue
        out.append(f"{head}{{{DECL.sub(lambda m: f'{m.group(1)}:{convert_value(m.group(1), m.group(2))}', body)}}}")
    return "\n".join(out)


def main(path: Path):
    css = path.read_text(encoding="utf-8")
    css = re.sub(r"@import url\([^)]*\);?", "", css)  # fonts are bundled through @fontsource now
    before = len(HEX.findall(css))
    stripped = strip_dark(css)
    converted = convert(stripped)
    # cream page/panel backgrounds were mapped to amber: use neutral surfaces instead
    converted = re.sub(r"(background(?:-color)?:)var\(--(?:amber|orange)-[1-4]\)", r"var(--gray-2)", converted)
    converted = re.sub(r"(background(?:-color)?:)var\(--(?:amber|orange)-5\)", r"var(--gray-3)", converted)
    converted = converted.replace("var(--amber-2)", "var(--color-panel-solid)")
    path.write_text(converted + "\n", encoding="utf-8")
    print(f"hex colours: {before} -> {len(HEX.findall(converted))}; "
          f"size {len(css)} -> {len(converted)}; dark blocks removed: {css.count(DARK) - stripped.count(DARK)} selectors")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
