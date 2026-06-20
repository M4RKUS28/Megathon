"""Spec quality gate — validates the Lastenheft before the build job.

Runs between Phase 2 (script writer) and Phase 2.5/3/4 (assets + build) to
catch the four main quality problems early:

  1. Conversation-heavy specs (too many dialogue blocks, too little substance)
  2. Forced / placeholder diagrams (generic chart data unrelated to the topic)
  3. Low interactivity (too few interactive block types)
  4. Thin content (not enough pages, blocks, or text per page)

The validator returns a ``ValidationResult`` with a pass/fail verdict, a list
of human-readable issues, and a metrics dict for observability. Currently used
as a **soft gate** (log + store metrics, never block the build), but the
interface is designed so it can be hardened into a rejection gate or fed back
into the script writer for re-generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
# Tuned to be lenient enough for valid courses but strict enough to flag the
# four target problems. All are per-course unless noted otherwise.

MIN_PAGES_PER_CHAPTER = 3
MIN_BLOCKS_PER_PAGE = 2  # excluding audio/narration blocks
MIN_TEXT_LENGTH = 40  # chars — minimum for a paragraph/callout/heading block
MAX_DIALOGUE_RATIO = 0.35  # dialogue blocks / total content blocks
MIN_INTERACTIVE_TYPES = 3  # distinct interactive block types across the course
MIN_INTERACTIVE_RATIO = 0.10  # interactive blocks / total content blocks

INTERACTIVE_TYPES = frozenset({
    "flashcards",
    "dragdrop",
    "hotspot",
    "timeline",
    "accordion",
    "scenario",
    "matching_game",
    "sorting_challenge",
    "fill_in_blank",
    "chart",
})

# Block types that count as "content" (everything except audio/narration which
# are supplementary spoken overlays, not visual content).
_AUDIO_TYPES = frozenset({"audio", "narration"})


@dataclass
class ValidationResult:
    """Outcome of a spec quality check."""

    passed: bool
    issues: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _is_placeholder_chart_data(data: dict | None) -> bool:
    """Detect obviously fabricated / generic chart data.

    Heuristics:
    - Generic quarter labels (Q1-Q4) with linearly increasing round values.
    - Identical datasets across chapters (caught at a higher level).
    """
    if not data:
        return False
    labels = data.get("labels", [])
    datasets = data.get("datasets", [])
    if not labels or not datasets:
        return False

    generic_labels = (
        labels == ["Q1", "Q2", "Q3", "Q4"]
        or labels == ["Jan", "Feb", "Mar", "Apr"]
        or labels == ["Week 1", "Week 2", "Week 3", "Week 4"]
    )
    if not generic_labels:
        return False

    for ds in datasets:
        values = ds.get("data", [])
        if not values or len(values) < 3:
            continue
        # All values divisible by 5 (round placeholder numbers)
        all_round = all(isinstance(v, (int, float)) and v % 5 == 0 for v in values)
        # Monotonically increasing (linear ramp-up pattern)
        monotonic = all(
            values[i] <= values[i + 1] for i in range(len(values) - 1)
        )
        if all_round and monotonic:
            return True

    return False


def _text_length(block: dict) -> int:
    """Return the approximate visible text length of a block."""
    text = block.get("text") or ""
    items = block.get("items") or []
    items_text = " ".join(str(it) for it in items)
    data = block.get("data") or {}
    # Count text from dialogue turns, scenario branches, etc.
    data_text = ""
    if isinstance(data, dict):
        turns = data.get("turns") or []
        for turn in turns:
            if isinstance(turn, dict):
                data_text += turn.get("text", "") + " "
        branches = data.get("branches") or []
        for branch in branches:
            if isinstance(branch, dict):
                data_text += branch.get("choice", "") + " "
                data_text += branch.get("outcome", "") + " "
        cards = data.get("cards") or []
        for card in cards:
            if isinstance(card, dict):
                data_text += card.get("front", "") + " "
                data_text += card.get("back", "") + " "
    return len(text) + len(items_text) + len(data_text)


# ── Main validator ────────────────────────────────────────────────────────────


def validate_spec(spec: dict) -> ValidationResult:
    """Validate a Lastenheft spec against quality thresholds.

    Returns a ``ValidationResult`` with pass/fail, human-readable issues, and
    metrics for observability logging.
    """
    issues: list[str] = []
    chapters = spec.get("chapters", [])

    total_content_blocks = 0
    dialogue_blocks = 0
    interactive_blocks = 0
    interactive_types_used: set[str] = set()
    thin_pages = 0
    total_pages = 0
    total_text_length = 0
    short_text_blocks = 0
    placeholder_charts = 0

    for ch in chapters:
        ch_title = ch.get("title", ch.get("id", "?"))
        pages = ch.get("pages", [])

        # ── Check: minimum pages per chapter ──────────────────────────────
        if len(pages) < MIN_PAGES_PER_CHAPTER:
            issues.append(
                f"Chapter '{ch_title}' has {len(pages)} page(s) "
                f"(need >= {MIN_PAGES_PER_CHAPTER})"
            )

        for page in pages:
            total_pages += 1
            blocks = page.get("blocks", [])
            page_title = page.get("title") or page.get("id", "?")

            # Separate content blocks from audio overlays
            content_blocks = [
                b for b in blocks if b.get("type") not in _AUDIO_TYPES
            ]

            # ── Check: minimum blocks per page ────────────────────────────
            if len(content_blocks) < MIN_BLOCKS_PER_PAGE:
                thin_pages += 1
                issues.append(
                    f"Page '{page_title}' in '{ch_title}' has "
                    f"{len(content_blocks)} content block(s) "
                    f"(need >= {MIN_BLOCKS_PER_PAGE})"
                )

            for block in content_blocks:
                total_content_blocks += 1
                btype = block.get("type", "")

                # Track dialogue ratio
                if btype == "dialogue":
                    dialogue_blocks += 1

                # Track interaction diversity
                if btype in INTERACTIVE_TYPES:
                    interactive_blocks += 1
                    interactive_types_used.add(btype)

                # Check text substance for prose blocks
                tlen = _text_length(block)
                total_text_length += tlen
                if btype in ("paragraph", "callout", "heading") and tlen < MIN_TEXT_LENGTH:
                    short_text_blocks += 1

                # Check for placeholder chart data
                if btype == "chart" and _is_placeholder_chart_data(block.get("data")):
                    placeholder_charts += 1
                    issues.append(
                        f"Chart in '{ch_title}' / '{page_title}' uses generic "
                        f"placeholder data (e.g. Q1-Q4 with round increasing "
                        f"values) — replace with topic-specific data or remove"
                    )

    # ── Global ratio checks ───────────────────────────────────────────────

    dialogue_ratio = (
        dialogue_blocks / total_content_blocks if total_content_blocks else 0.0
    )
    interactive_ratio = (
        interactive_blocks / total_content_blocks if total_content_blocks else 0.0
    )
    avg_text_per_page = (
        total_text_length / total_pages if total_pages else 0.0
    )

    if dialogue_ratio > MAX_DIALOGUE_RATIO:
        issues.insert(
            0,
            f"CONVERSATION-HEAVY: {dialogue_ratio:.0%} of content blocks are "
            f"dialogues (limit {MAX_DIALOGUE_RATIO:.0%}). Add more explanatory "
            f"content, examples, and interactions.",
        )

    if interactive_ratio < MIN_INTERACTIVE_RATIO and total_content_blocks > 0:
        issues.insert(
            0,
            f"LOW INTERACTIVITY: only {interactive_ratio:.0%} of blocks are "
            f"interactive (need >= {MIN_INTERACTIVE_RATIO:.0%}). Add more "
            f"flashcards, dragdrop, scenarios, timelines, etc.",
        )

    if len(interactive_types_used) < MIN_INTERACTIVE_TYPES:
        issues.insert(
            0,
            f"LOW VARIETY: {len(interactive_types_used)} interactive type(s) "
            f"used ({', '.join(sorted(interactive_types_used)) or 'none'}). "
            f"Need >= {MIN_INTERACTIVE_TYPES} distinct types.",
        )

    if short_text_blocks > 0:
        issues.append(
            f"{short_text_blocks} text block(s) have fewer than "
            f"{MIN_TEXT_LENGTH} characters — flesh them out."
        )

    # ── Build metrics dict ────────────────────────────────────────────────

    metrics = {
        "total_chapters": len(chapters),
        "total_pages": total_pages,
        "total_content_blocks": total_content_blocks,
        "dialogue_blocks": dialogue_blocks,
        "dialogue_ratio": round(dialogue_ratio, 3),
        "interactive_blocks": interactive_blocks,
        "interactive_ratio": round(interactive_ratio, 3),
        "interactive_types": sorted(interactive_types_used),
        "thin_pages": thin_pages,
        "short_text_blocks": short_text_blocks,
        "placeholder_charts": placeholder_charts,
        "avg_text_per_page": round(avg_text_per_page, 1),
    }

    # Pass if no HIGH-SEVERITY issues (the ones inserted at position 0 with
    # uppercase prefixes).  Per-page / per-block issues are informational.
    high_severity = [
        i
        for i in issues
        if i.startswith(("CONVERSATION-HEAVY", "LOW INTERACTIVITY", "LOW VARIETY"))
    ]
    passed = len(high_severity) == 0 and placeholder_charts == 0

    return ValidationResult(passed=passed, issues=issues, metrics=metrics)
