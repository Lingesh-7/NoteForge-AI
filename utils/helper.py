"""
utils/helper.py
===============
Utility functions shared across the graph nodes.
"""

from __future__ import annotations

import re


# ── Topic cleaning ────────────────────────────────────────────────────────────

_LEADING_ENUM = re.compile(r"^\s*(\d+[\).\-\s]+|[•\-\*]\s*)")


def clean_topics(text: str) -> list[str]:
    """
    Parse an LLM-generated topic list into a flat list of strings.

    Supported input styles
    ----------------------
    1. Simple numbered list:
          1. Fuzzy Logic
          2. Neural Networks

    2. Colon-separated with comma subtopics:
          Fuzzy Logic: Membership Functions, Fuzzy Sets
          → ["Fuzzy Logic - Membership Functions", "Fuzzy Logic - Fuzzy Sets"]

    3. Nested dash / bullet subtopics:
          Neural Networks
            - Perceptron
            - Backpropagation
          → ["Neural Networks - Perceptron", "Neural Networks - Backpropagation"]

    Returns
    -------
    list[str]
        Ordered, deduplicated list of topic strings, each ≤ 120 chars.
    """
    topics: list[str] = []
    seen:   set[str]  = set()

    current_parent: str = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Strip leading enumeration markers (1. / 1) / - / • / *)
        line = _LEADING_ENUM.sub("", line).strip()
        if not line:
            continue

        # Detect indented subtopic lines (original line had leading whitespace)
        is_indented = raw_line != raw_line.lstrip() and current_parent

        if is_indented:
            # This is a subtopic bullet under the current parent
            subtopics = [s.strip() for s in line.split(",") if s.strip()]
            for sub in subtopics:
                _add(topics, seen, f"{current_parent} - {sub}")
            continue

        if ":" in line:
            # "Main Topic: sub1, sub2, sub3"
            main, rest = line.split(":", 1)
            main = main.strip()
            current_parent = main

            subtopics = [s.strip() for s in rest.split(",") if s.strip()]
            if subtopics:
                for sub in subtopics:
                    _add(topics, seen, f"{main} - {sub}")
            else:
                # Colon but no subtopics listed on the same line
                _add(topics, seen, main)
        else:
            current_parent = line
            _add(topics, seen, line)

    return topics


def _add(topics: list[str], seen: set[str], entry: str) -> None:
    """Append *entry* to *topics* if it is non-empty, not a duplicate,
    and within the maximum allowed length."""
    entry = entry.strip()[:120]
    if entry and entry not in seen:
        seen.add(entry)
        topics.append(entry)