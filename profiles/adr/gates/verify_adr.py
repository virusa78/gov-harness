#!/usr/bin/env python3
"""ADR-G — static hygiene for decision records, lessons and their index.

Checks, in order: unique decision numbers, required sections in every record,
an index that lists exactly the records on disk, and lessons that carry a
non-empty rule line.

Section and lesson-field names are arguments, not assumptions: a repository
writes its records in its own language and this gate must not impose one.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path, PurePosixPath


RECORD_NAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
LINK = re.compile(r"\[[^\]]*]\(([^)]+)\)")
DEFAULT_SECTIONS = ("Status", "Context", "Decision", "Consequences")


def safe_relative(value: str, field: str) -> Path:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must stay inside the repository: {value}")
    return Path(*path.parts)


def headings(text: str) -> set[str]:
    return {
        line.lstrip("#").strip()
        for line in text.splitlines()
        if line.startswith("#")
    }


def section_is_populated(text: str, section: str) -> bool:
    """True when the section heading is followed by non-blank prose."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("#") and line.lstrip("#").strip() == section:
            for following in lines[index + 1 :]:
                if following.startswith("#"):
                    return False
                if following.strip():
                    return True
            return False
    return False


def check_records(
    decisions: Path, root: Path, sections: tuple[str, ...]
) -> tuple[list[str], dict[str, Path]]:
    findings: list[str] = []
    records: dict[str, Path] = {}
    by_number: dict[str, list[str]] = {}
    for path in sorted(decisions.iterdir()):
        if not path.is_file() or path.suffix != ".md" or path.name == "README.md":
            continue
        match = RECORD_NAME.match(path.name)
        if match is None:
            findings.append(f"record name is not NNNN-slug.md: {path.relative_to(root)}")
            continue
        records[path.name] = path
        by_number.setdefault(match.group(1), []).append(path.name)
    for number, names in sorted(by_number.items()):
        if len(names) > 1:
            findings.append(f"duplicate decision number {number}: {', '.join(sorted(names))}")
    for name, path in sorted(records.items()):
        text = path.read_text(encoding="utf-8", errors="replace")
        present = headings(text)
        for section in sections:
            if section not in present:
                findings.append(f"{name}: missing required section {section!r}")
            elif not section_is_populated(text, section):
                findings.append(f"{name}: section {section!r} is empty")
    return findings, records


def check_index(index: Path, root: Path, records: dict[str, Path]) -> list[str]:
    if not index.is_file():
        return [f"missing decision index: {index.relative_to(root)}"]
    text = index.read_text(encoding="utf-8", errors="replace")
    linked = {
        PurePosixPath(target.split("#", 1)[0]).name
        for target in LINK.findall(text)
        if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target)
    }
    findings = [
        f"decision missing from the index: {name}"
        for name in sorted(set(records) - linked)
    ]
    findings.extend(
        f"index links a decision that does not exist: {name}"
        for name in sorted(linked - set(records))
        if RECORD_NAME.match(name)
    )
    return findings


def check_lessons(lessons: Path, root: Path, field: str) -> list[str]:
    if not lessons.is_file():
        return [f"missing lessons file: {lessons.relative_to(root)}"]
    text = lessons.read_text(encoding="utf-8", errors="replace")
    entry = re.compile(r"^##\s+(\S+)", re.MULTILINE)
    matches = list(entry.finditer(text))
    findings: list[str] = []
    seen: set[str] = set()
    for index, match in enumerate(matches):
        identifier = match.group(1)
        if identifier in seen:
            findings.append(f"duplicate lesson identifier: {identifier}")
        seen.add(identifier)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        rule = re.search(rf"^{re.escape(field)}\s*(.*)$", body, re.MULTILINE)
        if rule is None:
            findings.append(f"lesson {identifier} has no {field!r} line")
        elif not rule.group(1).strip():
            findings.append(f"lesson {identifier} has an empty {field!r} line")
    return findings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--decisions", default="docs/architecture/decisions")
    parser.add_argument("--lessons", default="docs/LESSONS.md")
    parser.add_argument("--lesson-field", default="Rule:")
    parser.add_argument(
        "--section",
        action="append",
        help="required section heading; repeatable, replaces the defaults",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path(args.root).resolve()
    sections = tuple(args.section) if args.section else DEFAULT_SECTIONS
    try:
        decisions = root / safe_relative(args.decisions, "--decisions")
        lessons = root / safe_relative(args.lessons, "--lessons")
        if not decisions.is_dir():
            raise ValueError(f"decisions directory does not exist: {args.decisions}")
        findings, records = check_records(decisions, root, sections)
        findings.extend(check_index(decisions / "README.md", root, records))
        findings.extend(check_lessons(lessons, root, args.lesson_field))
    except (OSError, ValueError) as exc:
        print(f"ADR-G CONFIG: {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(f"ADR-G {finding}")
    print(f"ADR-G {len(findings)} finding(s) across {len(records)} decision(s)")
    return 2 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
