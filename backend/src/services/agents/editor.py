"""Edit loop — apply a targeted change to an existing Lastenheft (spec).

The creator selects a block in the rendered course and describes a change in
plain language ("Edit with Devin"). We rewrite just that block — or, when no
block is selected, apply a spec-level instruction — using Gemini, falling back to
a deterministic local edit so the loop works offline. The result is a new spec
dict the builder re-renders into a preview the creator can accept or reject.
"""

from __future__ import annotations

import copy
import logging

from .llm import gemini_available, get_chat_model
from .schemas import Block, Lastenheft

logger = logging.getLogger(__name__)

BLOCK_EDIT_SYSTEM = """You are editing ONE block of an interactive course. Rewrite the block to
satisfy the creator's request while keeping it implementation-ready for the same renderer.
Rules:
- Keep the same `type` unless the request clearly requires a different block type.
- Preserve the `asset` link and the `data` structure unless the request asks to change them.
- Keep it concise and on-topic. Return ONLY the single updated block as structured output."""

SPEC_EDIT_SYSTEM = """You are editing an interactive course specification (the Lastenheft). Apply
the creator's requested change while preserving everything not affected by the request.
Keep the same structure: chapters -> pages -> blocks, plus each chapter's end-of-chapter quiz
(passing_pct=80, retryable). Keep all `asset` template links intact. Return the FULL updated
specification as structured output."""


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


async def _gemini_edit_block(
    block: dict, instruction: str, target_text: str | None
) -> dict | None:
    model = get_chat_model(temperature=0.4).with_structured_output(Block)
    prompt = (
        f"Current block (JSON): {block}\n"
        f"Selected text: {target_text or 'N/A'}\n"
        f"Requested change: {instruction}\n"
        "Return the full updated block."
    )
    out = await model.ainvoke([("system", BLOCK_EDIT_SYSTEM), ("user", prompt)])
    if isinstance(out, Block):
        return out.model_dump(exclude_none=True)
    return None


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


def _local_edit_spec(spec: dict, instruction: str) -> dict:
    """Deterministic offline edit: add a callout reflecting the request."""
    edited = copy.deepcopy(spec)
    chapters = edited.get("chapters") or []
    if chapters and chapters[0].get("pages"):
        chapters[0]["pages"][0].setdefault("blocks", []).insert(
            0, {"type": "callout", "text": f"Updated: {instruction.strip()}"}
        )
    return edited


async def generate_edited_spec(
    spec: dict,
    instruction: str,
    selector: str | None,
    target_text: str | None,
) -> dict:
    """Return a NEW spec dict with the requested edit applied.

    When `selector` ("chapter.page.block") points at a real block, only that
    block is rewritten; otherwise the whole spec is edited.
    """
    new_spec = copy.deepcopy(spec)
    idx = _parse_selector(selector)
    block = _get_block(new_spec, idx) if idx is not None else None

    if idx is not None and block is not None:
        updated: dict | None = None
        if gemini_available():
            try:
                updated = await _gemini_edit_block(block, instruction, target_text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini block edit failed (%s); using local fallback", exc)
        if updated is None:
            updated = _local_edit_block(block, instruction)
        c, p, b = idx
        new_spec["chapters"][c]["pages"][p]["blocks"][b] = updated
        return new_spec

    # No specific block selected -> spec-level edit.
    if gemini_available():
        try:
            edited = await _gemini_edit_spec(new_spec, instruction, target_text)
            if edited is not None:
                return edited
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini spec edit failed (%s); using local fallback", exc)
    return _local_edit_spec(new_spec, instruction)
