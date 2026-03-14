"""
Markdown normalization helpers for LLM-generated content.
"""
from __future__ import annotations

import re

FENCE_PATTERN = re.compile(r"^(\s*)(`{3,}|~{3,})")


def normalize_markdown(text: str) -> str:
    """Trim accidental four-space indents while preserving fenced code blocks."""
    if not text:
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    output: list[str] = []
    in_fence = False
    fence_char = ""

    for raw_line in lines:
        line = raw_line.expandtabs(4)
        fence_match = FENCE_PATTERN.match(line)
        if fence_match:
            token_char = fence_match.group(2)[0]
            if not in_fence:
                in_fence = True
                fence_char = token_char
            elif token_char == fence_char:
                in_fence = False
                fence_char = ""
            output.append(line.rstrip())
            continue

        if not line.strip():
            output.append("")
            continue

        if not in_fence and line.startswith("    "):
            line = line[4:]

        output.append(line.rstrip())

    return "\n".join(output)
