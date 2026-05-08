"""Offline-corpus fallback for when the Gradio LLM endpoint is unreachable.

If `llm_backend.generate()` raises (network down, Kaggle tunnel rotated,
HF Space cold, etc.) we don't want to dead-end the user with a 502. Instead
we pick a curated sample from `FallbackCodes/Codes_ASM/` (or `Codes_C/`),
hand it back as if it were a fresh generation, and let the rest of the
pipeline (Groq explain_code, analyse, compile, MITRE pills…) run normally.

Selection strategy:
  1. Tokenise the user's prompt; drop common stop-words.
  2. Score each candidate filename by how many tokens it shares with the prompt.
  3. Pick the highest-scoring candidate (random tiebreak); on a zero score,
     pick uniformly at random.

The directory scan is cheap (~20 files for ASM, ~120 for C) so we re-scan
on every miss rather than caching — keeps things stateless.
"""
from __future__ import annotations

import logging
import random
import re
from pathlib import Path
from typing import Optional, Tuple

from django.conf import settings

log = logging.getLogger("chat.fallback")

_FALLBACK_ROOT = Path(settings.BASE_DIR) / "FallbackCodes"

# Words too generic to bias selection — they show up in nearly every prompt.
_STOP_WORDS = frozenset({
    "a", "an", "the", "this", "that", "these", "those",
    "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "of", "for", "to", "from", "with", "without",
    "and", "or", "but", "so", "as", "if", "then", "than",
    "i", "we", "you", "they", "it", "me", "us", "them",
    "my", "our", "your", "their", "its",
    "code", "generate", "write", "create", "make", "give", "build",
    "please", "can", "could", "would", "should", "want", "need",
    "some", "any", "all", "one", "two", "more",
    "using", "use", "uses", "used",
    "asm", "assembly", "c",  # the language itself is implied by the directory
})


def _list_files(language: str) -> list[Path]:
    lang = (language or "asm").lower()
    if lang == "c":
        directory = _FALLBACK_ROOT / "Codes_C"
        suffix = ".c"
    else:
        directory = _FALLBACK_ROOT / "Codes_ASM"
        suffix = ".asm"
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() == suffix
    )


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t}


def _score(stem: str, prompt_terms: set[str]) -> int:
    return len(_tokens(stem) & prompt_terms)


def _scan_c_line(line: str, in_block: bool) -> tuple[int, int, int, bool]:
    """Walk a C source line and return (opens, closes, leading_closes, in_block_after).

    `leading_closes` counts `}` that appear before any other non-whitespace
    character — those should dedent THE CURRENT line. The other braces only
    affect indent of the NEXT line. String / char / line-comment / block-
    comment regions are skipped so braces inside them don't shift indent.
    """
    i, n = 0, len(line)
    opens = closes = leading_closes = 0
    seen_non_close = False
    in_string = in_char = in_line_comment = False
    while i < n:
        c = line[i]
        nxt = line[i + 1] if i + 1 < n else ""
        if in_block:
            if c == "*" and nxt == "/":
                in_block = False
                i += 2
                continue
            i += 1
            continue
        if in_line_comment:
            break  # comments end at EOL
        if in_string:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if in_char:
            if c == "\\":
                i += 2
                continue
            if c == "'":
                in_char = False
            i += 1
            continue
        if c == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if c == "/" and nxt == "*":
            in_block = True
            i += 2
            continue
        if c == '"':
            in_string = True
            i += 1
            continue
        if c == "'":
            in_char = True
            i += 1
            continue
        if c == "{":
            opens += 1
            seen_non_close = True
        elif c == "}":
            closes += 1
            if not seen_non_close:
                leading_closes += 1
        elif not c.isspace():
            seen_non_close = True
        i += 1
    return opens, closes, leading_closes, in_block


def _is_case_or_default(stripped: str) -> bool:
    return (
        stripped.startswith("case ")
        or stripped.startswith("case\t")
        or stripped == "default:"
        or stripped.startswith("default:")
    )


def reindent_c(text: str) -> str:
    """Re-indent C source by brace-tracking. Leaves multi-line block comments
    and preprocessor directives alone; case/default labels dedent by one
    relative to the surrounding switch's body (Linux-kernel style).

    This is a heuristic — it does NOT format-wrap long lines, normalise
    spacing inside expressions, or split joined statements. It just fixes
    indentation when the source has none, which is the common failure mode
    in our corpus."""
    indent = "    "
    out: list[str] = []
    depth = 0
    in_block_comment = False

    for raw in text.split("\n"):
        if not raw.strip():
            out.append("")
            continue

        # Preserve original whitespace for lines that BEGIN inside a block
        # comment (the conventional `* …` decoration would otherwise be lost).
        if in_block_comment:
            out.append(raw.rstrip())
            _, _, _, in_block_comment = _scan_c_line(raw, in_block_comment)
            continue

        opens, closes, leading_closes, in_block_after = _scan_c_line(raw, in_block_comment)
        line_depth = max(0, depth - leading_closes)
        stripped = raw.lstrip().rstrip()

        if stripped.startswith("#"):
            # Preprocessor directives always flush-left.
            out.append(stripped)
        elif _is_case_or_default(stripped):
            out.append(indent * max(0, line_depth - 1) + stripped)
        else:
            out.append(indent * line_depth + stripped)

        depth = max(0, depth + opens - closes)
        in_block_comment = in_block_after

    return "\n".join(out)


def pick_fallback(prompt: str, language: str) -> Optional[Tuple[str, str]]:
    """Return (filename, file_contents) for a fallback code sample, or None
    if the directory is empty / unreadable."""
    files = _list_files(language)
    if not files:
        return None

    prompt_terms = _tokens(prompt) - _STOP_WORDS

    if prompt_terms:
        scored = [(p, _score(p.stem, prompt_terms)) for p in files]
        best_score = max(s for _, s in scored)
        if best_score > 0:
            top = [p for p, s in scored if s == best_score]
            chosen = random.choice(top)
        else:
            chosen = random.choice(files)
    else:
        chosen = random.choice(files)

    try:
        text = chosen.read_text(encoding="utf-8", errors="replace")
    except Exception:
        log.exception("Failed reading fallback %s", chosen)
        return None

    # Many of the C samples ship with no indentation; re-flow them so the
    # frontend code-block reader doesn't render a flat wall of statements.
    # ASM files are column-conventional, leave them untouched.
    if (language or "asm").lower() == "c":
        text = reindent_c(text)

    return chosen.name, text
