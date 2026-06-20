"""Hybrid Tiered Edit Architecture — two-tier editing system.

Simple/targeted block edits route through an enhanced Gemini path (fast, <5s).
Complex/structural edits route through a real Devin API session (powerful,
minutes). Both paths include validation, context injection, and diff tracking.

The result is a new spec dict (+ metadata) the builder re-renders into a
preview the creator can accept or reject.
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field

from .llm import gemini_available, get_chat_model
from .schemas import Block, Lastenheft

logger = logging.getLogger(__name__)

# ── Edit-tier labels ─────────────────────────────────────────────────────────

TIER_SIMPLE = "simple"
TIER_COMPLEX = "complex"

# ── Complexity classifier ────────────────────────────────────────────────────

_COMPLEX_SELECTOR_KEYWORDS = re.compile(
    r"\b(add\s+chapter|remove\s+chapter|delete\s+chapter|new\s+chapter"
    r"|add\s+page|remove\s+page|delete\s+page|new\s+page"
    r"|restructure|reorganize|reorder|merge\s+chapter|split\s+chapter"
    r"|add\s+quiz|change\s+quiz|modify\s+quiz|update\s+quiz|remove\s+quiz"
    r"|compliance|regulation|policy|mandatory|certification"
    r"|move\s+block|swap\s+block|add\s+block|remove\s+block|delete\s+block"
    r"|multiple\s+block|several\s+block|all\s+block|every\s+block"
    r"|across\s+chapter|across\s+page|throughout)\b",
    re.IGNORECASE,
)

_SIMPLE_KEYWORDS = re.compile(
    r"\b(friendlier|simpler|shorter|longer|rephrase|reword|tone|example"
    r"|typo|fix\s+grammar|translate|summarize|summarise|clarify"
    r"|bold|italic|highlight|emphasize|emphasise)\b",
    re.IGNORECASE,
)


def classify_edit_complexity(instruction: str, selector: str | None) -> str:
    """Classify an edit as 'simple' or 'complex' using keyword heuristics.

    - Returns 'simple' for targeted block edits with straightforward instructions.
    - Returns 'complex' for spec-level edits, structural changes, quiz mods,
      multi-block changes, or compliance/policy references.
    """
    if not selector:
        return TIER_COMPLEX

    if _COMPLEX_SELECTOR_KEYWORDS.search(instruction):
        return TIER_COMPLEX

    if _SIMPLE_KEYWORDS.search(instruction):
        return TIER_SIMPLE

    # Short targeted instructions default to simple
    if len(instruction.split()) <= 20:
        return TIER_SIMPLE

    return TIER_COMPLEX


# ── Diff tracking ────────────────────────────────────────────────────────────


@dataclass
class BlockDiff:
    chapter: int
    page: int
    block: int
    action: str  # "changed" | "added" | "removed"
    old_type: str | None = None
    new_type: str | None = None


@dataclass
class EditDiff:
    changed: list[BlockDiff] = field(default_factory=list)
    summary: str = ""


def compute_edit_diff(old_spec: dict, new_spec: dict) -> EditDiff:
    """Compare two specs and return a structured diff of changed/added/removed blocks."""
    diffs: list[BlockDiff] = []
    old_chapters = old_spec.get("chapters", [])
    new_chapters = new_spec.get("chapters", [])

    max_chapters = max(len(old_chapters), len(new_chapters))
    for ci in range(max_chapters):
        old_ch = old_chapters[ci] if ci < len(old_chapters) else None
        new_ch = new_chapters[ci] if ci < len(new_chapters) else None
        if old_ch is None and new_ch is not None:
            for pi, page in enumerate(new_ch.get("pages", [])):
                for bi, blk in enumerate(page.get("blocks", [])):
                    diffs.append(BlockDiff(ci, pi, bi, "added", new_type=blk.get("type")))
            continue
        if new_ch is None and old_ch is not None:
            for pi, page in enumerate(old_ch.get("pages", [])):
                for bi, blk in enumerate(page.get("blocks", [])):
                    diffs.append(BlockDiff(ci, pi, bi, "removed", old_type=blk.get("type")))
            continue

        old_pages = (old_ch or {}).get("pages", [])
        new_pages = (new_ch or {}).get("pages", [])
        max_pages = max(len(old_pages), len(new_pages))
        for pi in range(max_pages):
            old_pg = old_pages[pi] if pi < len(old_pages) else None
            new_pg = new_pages[pi] if pi < len(new_pages) else None
            old_blocks = (old_pg or {}).get("blocks", [])
            new_blocks = (new_pg or {}).get("blocks", [])
            max_blocks = max(len(old_blocks), len(new_blocks))
            for bi in range(max_blocks):
                old_b = old_blocks[bi] if bi < len(old_blocks) else None
                new_b = new_blocks[bi] if bi < len(new_blocks) else None
                if old_b is None and new_b is not None:
                    diffs.append(BlockDiff(ci, pi, bi, "added", new_type=new_b.get("type")))
                elif new_b is None and old_b is not None:
                    diffs.append(BlockDiff(ci, pi, bi, "removed", old_type=old_b.get("type")))
                elif old_b != new_b:
                    diffs.append(BlockDiff(
                        ci, pi, bi, "changed",
                        old_type=old_b.get("type") if old_b else None,
                        new_type=new_b.get("type") if new_b else None,
                    ))

    changed = sum(1 for d in diffs if d.action == "changed")
    added = sum(1 for d in diffs if d.action == "added")
    removed = sum(1 for d in diffs if d.action == "removed")
    parts = []
    if changed:
        parts.append(f"{changed} block(s) changed")
    if added:
        parts.append(f"{added} block(s) added")
    if removed:
        parts.append(f"{removed} block(s) removed")
    summary = ", ".join(parts) or "no changes detected"

    return EditDiff(changed=diffs, summary=summary)


# ── Post-edit validation ─────────────────────────────────────────────────────

VALID_BLOCK_TYPES = {
    "heading", "paragraph", "list", "callout", "image", "video", "audio",
    "conversation", "dialogue", "chart", "flashcards", "dragdrop", "hotspot",
    "timeline", "accordion", "scenario", "minigame",
}


def validate_edited_spec(
    new_spec: dict,
    old_spec: dict | None = None,
    block_level: bool = False,
) -> list[str]:
    """Validate an edited spec and return a list of warning strings (empty = valid).

    Checks:
    - Block type validity, non-empty content
    - Quiz structural integrity (answerIndex bounds, passing_pct range)
    - Asset template links preserved
    - Chapter/page count preserved for block-level edits
    """
    warnings: list[str] = []
    chapters = new_spec.get("chapters", [])

    if not chapters:
        warnings.append("Spec has no chapters")
        return warnings

    if block_level and old_spec:
        old_chapters = old_spec.get("chapters", [])
        if len(chapters) != len(old_chapters):
            warnings.append(
                f"Chapter count changed ({len(old_chapters)} -> {len(chapters)}) "
                "during a block-level edit"
            )
        for ci, (old_ch, new_ch) in enumerate(
            zip(old_chapters, chapters, strict=False)
        ):
            old_pages = old_ch.get("pages", [])
            new_pages = new_ch.get("pages", [])
            if len(old_pages) != len(new_pages):
                warnings.append(
                    f"Chapter {ci} page count changed "
                    f"({len(old_pages)} -> {len(new_pages)}) during a block-level edit"
                )

    old_assets: set[str] = set()
    if old_spec:
        for ch in old_spec.get("chapters", []):
            for pg in ch.get("pages", []):
                for blk in pg.get("blocks", []):
                    asset = blk.get("asset")
                    if asset and asset.startswith("/resources/"):
                        old_assets.add(asset)

    for ci, ch in enumerate(chapters):
        quiz = ch.get("quiz", {})
        if quiz:
            pct = quiz.get("passing_pct", 80)
            if not (0 <= pct <= 100):
                warnings.append(f"Chapter {ci} quiz passing_pct={pct} out of range [0,100]")
            questions = quiz.get("questions", [])
            if not questions:
                warnings.append(f"Chapter {ci} quiz has no questions")
            for qi, q in enumerate(questions):
                opts = q.get("options", [])
                idx = q.get("answerIndex", 0)
                if not opts:
                    warnings.append(f"Chapter {ci} quiz Q{qi} has no options")
                elif idx < 0 or idx >= len(opts):
                    warnings.append(
                        f"Chapter {ci} quiz Q{qi} answerIndex={idx} "
                        f"out of bounds (options count={len(opts)})"
                    )

        for pi, pg in enumerate(ch.get("pages", [])):
            blocks = pg.get("blocks", [])
            if not blocks:
                warnings.append(f"Chapter {ci} page {pi} has no blocks")
            for bi, blk in enumerate(blocks):
                btype = blk.get("type", "")
                if not btype:
                    warnings.append(f"Block {ci}.{pi}.{bi} has no type")

                has_content = bool(
                    blk.get("text") or blk.get("items") or blk.get("data") or blk.get("asset")
                )
                if not has_content:
                    warnings.append(f"Block {ci}.{pi}.{bi} ({btype}) has no content")

    new_assets: set[str] = set()
    for ch in chapters:
        for pg in ch.get("pages", []):
            for blk in pg.get("blocks", []):
                asset = blk.get("asset")
                if asset and asset.startswith("/resources/"):
                    new_assets.add(asset)

    missing = old_assets - new_assets
    if missing:
        warnings.append(f"Asset template links removed: {', '.join(sorted(missing))}")

    return warnings


# ── System prompts ───────────────────────────────────────────────────────────

BLOCK_EDIT_SYSTEM = """You are editing ONE block of an interactive course. Rewrite the block to
satisfy the creator's request while keeping it implementation-ready for the same renderer.
Rules:
- Keep the same `type` unless the request clearly requires a different block type.
- Preserve the `asset` link and the `data` structure unless the request asks to change them.
- Keep it concise and on-topic. Return ONLY the single updated block as structured output.
- Maintain the same language/locale as the existing content.
- Do not add/remove chapters or pages — you are editing a single block only."""

SPEC_EDIT_SYSTEM = """You are editing an interactive course specification (the Lastenheft). Apply
the creator's requested change while preserving everything not affected by the request.
Keep the same structure: chapters -> pages -> blocks, plus each chapter's end-of-chapter quiz
(passing_pct=80, retryable). Keep all `asset` template links intact. Return the FULL updated
specification as structured output."""


# ── Helpers ──────────────────────────────────────────────────────────────────


def _parse_selector(selector: str | None) -> tuple[int, int, int] | None:
    """Parse a "chapter.page.block" index selector emitted by the renderer."""
    if not selector:
        return None
    parts = selector.split(".")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None


def _get_block(spec: dict, idx: tuple[int, int, int]) -> dict | None:
    c, p, b = idx
    try:
        return spec["chapters"][c]["pages"][p]["blocks"][b]
    except (KeyError, IndexError, TypeError):
        return None


# ── Context builder ──────────────────────────────────────────────────────────


def _build_context_string(
    company_name: str | None = None,
    audience: str | None = None,
    plan_summary: str | None = None,
    compliance_requirements: list[str] | None = None,
) -> str:
    """Build a context string for injecting into Gemini prompts."""
    parts: list[str] = []
    if company_name:
        parts.append(f"Company: {company_name}")
    if audience:
        parts.append(f"Target audience: {audience}")
    if plan_summary:
        parts.append(f"Course plan: {plan_summary}")
    if compliance_requirements:
        parts.append(f"Compliance requirements: {', '.join(compliance_requirements)}")
    return "\n".join(parts) if parts else "No additional context provided."


# ── Fast Gemini path (simple edits) ──────────────────────────────────────────


async def _gemini_edit_block(
    block: dict,
    instruction: str,
    target_text: str | None,
    context: str = "",
) -> dict | None:
    """Enhanced Gemini block edit with context injection + validation retry."""
    model = get_chat_model(temperature=0.4).with_structured_output(Block)

    system = BLOCK_EDIT_SYSTEM
    if context:
        system += f"\n\nCourse context:\n{context}"

    prompt = (
        f"Current block (JSON): {block}\n"
        f"Selected text: {target_text or 'N/A'}\n"
        f"Requested change: {instruction}\n"
        "Return the full updated block."
    )
    out = await model.ainvoke([("system", system), ("user", prompt)])
    if not isinstance(out, Block):
        return None

    result = out.model_dump(exclude_none=True)

    # Post-edit validation on the single block
    block_warnings = _validate_single_block(result)
    if block_warnings:
        logger.info("Block validation warnings, retrying: %s", block_warnings)
        retry_prompt = (
            f"The previous edit had validation issues: {'; '.join(block_warnings)}.\n"
            f"Original block: {block}\n"
            f"Your previous output: {result}\n"
            f"Requested change: {instruction}\n"
            "Fix the issues and return the corrected block."
        )
        retry_out = await model.ainvoke([("system", system), ("user", retry_prompt)])
        if isinstance(retry_out, Block):
            result = retry_out.model_dump(exclude_none=True)

    return result


def _validate_single_block(block: dict) -> list[str]:
    """Quick validation for a single edited block."""
    warnings: list[str] = []
    if not block.get("type"):
        warnings.append("Block has no type")
    has_content = bool(
        block.get("text") or block.get("items") or block.get("data") or block.get("asset")
    )
    if not has_content:
        warnings.append("Block has no content")
    return warnings


async def _gemini_edit_spec(
    spec: dict, instruction: str, target_text: str | None
) -> dict | None:
    model = get_chat_model(temperature=0.4).with_structured_output(Lastenheft)
    prompt = (
        f"Current specification (JSON): {spec}\n"
        f"Context / selected text: {target_text or 'N/A'}\n"
        f"Requested change: {instruction}\n"
        "Return the full updated specification."
    )
    out = await model.ainvoke([("system", SPEC_EDIT_SYSTEM), ("user", prompt)])
    if isinstance(out, Lastenheft) and out.chapters:
        return out.model_dump(exclude_none=True)
    return None


# ── Local fallback edits ─────────────────────────────────────────────────────


def _local_edit_block(block: dict, instruction: str) -> dict:
    """Deterministic offline edit: visibly fold the instruction into the block."""
    edited = copy.deepcopy(block)
    note = instruction.strip()
    if edited.get("text"):
        edited["text"] = f"{edited['text']} (Updated: {note})"
    elif edited.get("items"):
        edited["items"] = [*edited["items"], f"Updated: {note}"]
    else:
        edited["text"] = note
    return edited


def _local_edit_spec(spec: dict, instruction: str) -> dict:
    """Deterministic offline edit: add a callout reflecting the request."""
    edited = copy.deepcopy(spec)
    chapters = edited.get("chapters") or []
    if chapters and chapters[0].get("pages"):
        chapters[0]["pages"][0].setdefault("blocks", []).insert(
            0, {"type": "callout", "text": f"Updated: {instruction.strip()}"}
        )
    return edited


# ── Devin session path (complex edits) ───────────────────────────────────────


async def _devin_edit_spec(
    spec: dict,
    instruction: str,
    *,
    company_name: str | None = None,
    plan_summary: str | None = None,
    audience: str | None = None,
    compliance_requirements: list[str] | None = None,
) -> tuple[dict | None, str | None]:
    """Create a Devin API session for complex spec edits.

    Returns (new_spec_dict, devin_session_id).
    """
    from src.services.devin.client import DevinClient

    client = DevinClient()
    if not client.enabled:
        logger.info("Devin API not configured; skipping Devin edit path")
        return None, None

    context_parts: list[str] = []
    if company_name:
        context_parts.append(f"Company: {company_name}")
    if audience:
        context_parts.append(f"Target audience: {audience}")
    if plan_summary:
        context_parts.append(f"Course plan summary: {plan_summary}")
    if compliance_requirements:
        context_parts.append(f"Compliance requirements: {', '.join(compliance_requirements)}")
    context_block = "\n".join(context_parts) if context_parts else "No additional context."

    prompt = f"""You are editing an interactive e-learning course specification (Lastenheft).

## Course Context
{context_block}

## Current Specification (JSON)
{spec}

## Edit Request
{instruction}

## Constraints
- Preserve quiz structure: each chapter must have a quiz with passing_pct=80, retryable=true
- Preserve all asset template links (paths starting with /resources/)
- Maintain chapter progression and page structure where possible
- Keep the same language/locale as the existing content
- Return the FULL updated specification

Apply the requested change and return the complete updated Lastenheft."""

    schema = Lastenheft.model_json_schema()

    try:
        session_id, output = await client.run(
            prompt,
            structured_output_schema=schema,
            title=f"Course edit: {instruction[:80]}",
            tags=["course-edit", "hybrid-tier"],
        )
        if isinstance(output, dict) and output.get("chapters"):
            return output, session_id
        logger.warning("Devin session %s returned invalid output", session_id)
        return None, session_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("Devin edit session failed: %s", exc)
        return None, None


# ── EditResult dataclass ─────────────────────────────────────────────────────


@dataclass
class EditResult:
    new_spec: dict
    devin_session_id: str | None = None
    edit_tier: str = TIER_SIMPLE
    diff: EditDiff | None = None
    validation_warnings: list[str] = field(default_factory=list)


# ── Unified edit function ────────────────────────────────────────────────────


async def generate_edited_spec(
    spec: dict,
    instruction: str,
    selector: str | None,
    target_text: str | None,
    *,
    company_name: str | None = None,
    plan_summary: str | None = None,
    compliance_requirements: list[str] | None = None,
    audience: str | None = None,
) -> EditResult:
    """Return an EditResult with the new spec and metadata.

    Routes edits through the appropriate tier:
    - 'simple' -> enhanced Gemini (fast, <5s)
    - 'complex' -> Devin session (powerful) -> Gemini fallback -> local fallback
    """
    old_spec = copy.deepcopy(spec)
    new_spec = copy.deepcopy(spec)
    tier = classify_edit_complexity(instruction, selector)
    idx = _parse_selector(selector)
    block = _get_block(new_spec, idx) if idx is not None else None
    devin_session_id: str | None = None
    context = _build_context_string(
        company_name=company_name,
        audience=audience,
        plan_summary=plan_summary,
        compliance_requirements=compliance_requirements,
    )

    if tier == TIER_SIMPLE and idx is not None and block is not None:
        # Fast Gemini path for targeted block edits
        updated: dict | None = None
        if gemini_available():
            try:
                updated = await _gemini_edit_block(block, instruction, target_text, context)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini block edit failed (%s); using local fallback", exc)
        if updated is None:
            updated = _local_edit_block(block, instruction)
        c, p, b = idx
        new_spec["chapters"][c]["pages"][p]["blocks"][b] = updated

    elif tier == TIER_COMPLEX:
        # Complex path: try Devin -> Gemini fallback -> local fallback
        edited: dict | None = None

        # Try Devin first
        edited, devin_session_id = await _devin_edit_spec(
            new_spec,
            instruction,
            company_name=company_name,
            plan_summary=plan_summary,
            audience=audience,
            compliance_requirements=compliance_requirements,
        )

        # Gemini fallback
        if edited is None and gemini_available():
            try:
                if idx is not None and block is not None:
                    updated_block = await _gemini_edit_block(
                        block, instruction, target_text, context,
                    )
                    if updated_block is not None:
                        c, p, b = idx
                        new_spec["chapters"][c]["pages"][p]["blocks"][b] = updated_block
                        edited = new_spec
                else:
                    edited = await _gemini_edit_spec(new_spec, instruction, target_text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini fallback edit failed (%s); using local fallback", exc)

        # Local fallback
        if edited is None:
            if idx is not None and block is not None:
                c, p, b = idx
                new_spec["chapters"][c]["pages"][p]["blocks"][b] = _local_edit_block(
                    block, instruction,
                )
                edited = new_spec
            else:
                edited = _local_edit_spec(new_spec, instruction)

        new_spec = edited

    else:
        # Simple edit without a valid block selector — treat as targeted Gemini
        if gemini_available():
            try:
                edited_spec = await _gemini_edit_spec(new_spec, instruction, target_text)
                if edited_spec is not None:
                    new_spec = edited_spec
                else:
                    new_spec = _local_edit_spec(new_spec, instruction)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini spec edit failed (%s); using local fallback", exc)
                new_spec = _local_edit_spec(new_spec, instruction)
        else:
            new_spec = _local_edit_spec(new_spec, instruction)

    # Post-edit validation
    is_block_edit = idx is not None and block is not None
    validation_warnings = validate_edited_spec(new_spec, old_spec, block_level=is_block_edit)

    # Compute diff
    diff = compute_edit_diff(old_spec, new_spec)

    return EditResult(
        new_spec=new_spec,
        devin_session_id=devin_session_id,
        edit_tier=tier,
        diff=diff,
        validation_warnings=validation_warnings,
    )
