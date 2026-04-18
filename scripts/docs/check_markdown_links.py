#!/usr/bin/env python3
"""Jednoduchy audit internych Markdown odkazov v repozitari."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {
    ".git",
    ".idea",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "archive",
}

LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")


def iter_markdown_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def normalize_anchor(text: str) -> str:
    value = text.strip().lower()
    value = re.sub(r"`", "", value)
    value = re.sub(r"[^\w\- ]", "", value)
    value = re.sub(r"\s+", "-", value).strip("-")
    return value


def extract_anchors(md_file: Path) -> Set[str]:
    anchors: Set[str] = set()
    counts: Dict[str, int] = {}

    for raw in md_file.read_text(encoding="utf-8").splitlines():
        match = HEADING_RE.match(raw)
        if not match:
            continue

        heading = match.group(1)
        heading = re.sub(r"\s+#*$", "", heading).strip()
        base = normalize_anchor(heading)
        if not base:
            continue

        n = counts.get(base, 0)
        counts[base] = n + 1
        anchor = base if n == 0 else f"{base}-{n}"
        anchors.add(anchor)

    return anchors


def parse_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    return target


def is_external(target: str) -> bool:
    return target.startswith("http://") or target.startswith("https://") or target.startswith("mailto:")


def validate_link(source: Path, target: str, anchor_cache: Dict[Path, Set[str]]) -> List[str]:
    errors: List[str] = []

    if not target or is_external(target):
        return errors

    if target.startswith("#"):
        anchor = target[1:]
        anchors = anchor_cache.setdefault(source, extract_anchors(source))
        if anchor and anchor not in anchors:
            errors.append(f"{source}: neexistujuca kotva #{anchor}")
        return errors

    if "#" in target:
        rel_part, anchor = target.split("#", 1)
    else:
        rel_part, anchor = target, ""

    rel_part = rel_part.strip()
    if not rel_part:
        return errors

    resolved = (source.parent / rel_part).resolve()
    if not resolved.exists():
        errors.append(f"{source}: neexistujuci ciel odkazu {target}")
        return errors

    if anchor:
        anchors = anchor_cache.setdefault(resolved, extract_anchors(resolved))
        if anchor not in anchors:
            errors.append(f"{source}: v subore {resolved} neexistuje kotva #{anchor}")

    return errors


def main() -> int:
    md_files = sorted(iter_markdown_files(REPO_ROOT))
    anchor_cache: Dict[Path, Set[str]] = {}
    problems: List[str] = []

    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = parse_target(match.group(1))
            problems.extend(validate_link(md_file, target, anchor_cache))

    if problems:
        print("Markdown audit zlyhal. Nalezene problemy:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print(f"Markdown audit OK. Skontrolovanych suborov: {len(md_files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

