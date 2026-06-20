"""Edit loop — apply a targeted change to an existing Lastenheft (spec).

The creator selects a block in the rendered course and describes a change in
plain language ("Edit with Devin"). We rewrite just that block — or, when no
block is selected, apply a spec-level instruction — using Gemini, falling back to
a deterministic local edit so the loop works offline. The result is a new spec
dict the builder re-renders into a preview the creator can accept or reject.

Enhanced with:
- Rich context injection (company, audience, plan summary, compliance)
- Conversation history for iterative refinement
- Post-edit validation with auto-retry
- Diff tracking between old and new specs
"""

from __future__ import annotations

import copy
import json
import logging

from .llm import gemini_available, get_chat_model
from .schemas import Block, Lastenheft

logger = logging.getLogger(__name__)

# ── System prompts with context placeholders ─────────────────────────────────

BLOCK_EDIT_SYSTEM = """You are editing ONE block of an interactive course.{context_section}

Rules:
- Keep the same `type` unless the request clearly requires a different block type.
- Preserve the `asset` link and the `data` structure unless the request asks to change them.
- Preserve structural integrity: quizzes, assets, and page structure must remain valid.
- Keep it concise and on-topic. Return ONLY the single updated block as structured output.
{compliance_section}{history_section}"""

SPEC_EDIT_SYSTEM = """You are editing an interactive course specification \
(the Lastenheft).{context_section}

Apply the creator's requested change while preserving everything not affected by the request.
Keep the same structure: chapters -> pages -> blocks, plus each chapter's end-of-chapter quiz
(passing_pct=80, retryable). Keep all `asset` template links intact.
- Do NOT remove chapters unless explicitly asked.
- Do NOT remove quizzes from chapters.
- Ensure all asset template_links from the original spec are preserved.
Return the FULL updated specification as structured output.
{compliance_section}{history_section}"""


def _build_context_section(
    company_name: str = "",
    audience: str = "",
    plan_summary: dict | None = None,
) -> str:
    parts: list[str] = []
    if company_name or audience:
        ctx = ""
        if company_name:
            ctx += f" for {company_name}"
        if audience:
            ctx += f", targeting {audience}"
        parts.append(f"\nYou are editing a course{ctx}.")
    if plan_summary:
        objectives = plan_summary.get("objectives", [])
        if objectives:
            obj_str = "; ".join(objectives[:5])
            parts.append(f"\nLearning objectives: {obj_str}")
    return "".join(parts)


def _build_compliance_section(compliance_requirements: list[str] | None = None) -> str:
    if not compliance_requirements:
        return ""
    reqs = "\n".join(f"- {r}" for r in compliance_requirements)
    return f"\nCompliance requirements (must NOT be violated):\n{reqs}\n"


def _build_history_section(edit_history: list[dict] | None = None) -> str:
    if not edit_history:
        return ""
    entries: list[str] = []
    for h in edit_history[-5:]:  # keep last 5 for context window
        prompt = h.get("prompt", "")
        status = h.get("status", "")
        entries.append(f"- \"{prompt}\" (status: {status})")
    history_str = "\n".join(entries)
    return f"\nPrevious edits on this target (for continuity):\n{history_str}\n"


def _format_system_prompt(
    template: str,
    company_name: str = "",
    audience: str = "",
    plan_summary: dict | None = None,
    compliance_requirements: list[str] | None = None,
    edit_history: list[dict] | None = None,
) -> str:
    return template.format(
        context_section=_build_context_section(company_name, audience, plan_summary),
        compliance_section=_build_compliance_section(compliance_requirements),
        history_section=_build_history_section(edit_history),
    )


# ── Validation ───────────────────────────────────────────────────────────────

def validate_edited_spec(
    old_spec: dict, new_spec: dict, edit_type: str
) -> list[str]:
    """Validate an edited spec against structural rules.

    Returns a list of validation warnings (empty = valid).
    """
    warnings: list[str] = []

    if edit_type == "block":
        # For block edits: verify the block has a valid type, text/data not empty
        new_chapters = new_spec.get("chapters", [])
        for ci, ch in enumerate(new_chapters):
            for pi, page in enumerate(ch.get("pages", [])):
                for bi, block in enumerate(page.get("blocks", [])):
                    if not block.get("type"):
                        warnings.append(
                            f"Block at {ci}.{pi}.{bi} is missing a valid 'type'"
                        )
                    if (
                        not block.get("text")
                        and not block.get("data")
                        and not block.get("items")
                        and not block.get("asset")
                    ):
                        warnings.append(
                            f"Block at {ci}.{pi}.{bi} has no text, data, items, or asset"
                        )
        # Verify asset links preserved
        old_assets = _collect_asset_links(old_spec)
        new_assets = _collect_asset_links(new_spec)
        missing_assets = old_assets - new_assets
        if missing_assets:
            warnings.append(
                f"Asset links removed: {', '.join(sorted(missing_assets))}"
            )

    elif edit_type == "spec":
        old_chapters = old_spec.get("chapters", [])
        new_chapters = new_spec.get("chapters", [])

        # Verify chapter count unchanged (unless that was the point)
        if len(new_chapters) != len(old_chapters):
            warnings.append(
                f"Chapter count changed from {len(old_chapters)} to {len(new_chapters)} "
                f"(only acceptable if explicitly requested)"
            )

        # Verify quiz exists per chapter
        for ci, ch in enumerate(new_chapters):
            quiz = ch.get("quiz")
            if not quiz or not quiz.get("questions"):
                warnings.append(f"Chapter {ci} is missing quiz questions")

        # Verify passing_pct in valid range
        for ci, ch in enumerate(new_chapters):
            quiz = ch.get("quiz", {})
            pct = quiz.get("passing_pct", 80)
            if not (1 <= pct <= 100):
                warnings.append(
                    f"Chapter {ci} quiz passing_pct={pct} is out of range (1-100)"
                )

        # Verify answerIndex in bounds
        for ci, ch in enumerate(new_chapters):
            quiz = ch.get("quiz", {})
            for qi, q in enumerate(quiz.get("questions", [])):
                options = q.get("options", [])
                answer_idx = q.get("answerIndex", 0)
                if answer_idx < 0 or answer_idx >= len(options):
                    warnings.append(
                        f"Chapter {ci} quiz question {qi}: answerIndex={answer_idx} "
                        f"out of bounds (options count: {len(options)})"
                    )

        # Verify all asset template_links from old spec still present
        old_assets = _collect_asset_links(old_spec)
        new_assets = _collect_asset_links(new_spec)
        missing_assets = old_assets - new_assets
        if missing_assets:
            warnings.append(
                f"Asset template_links removed: {', '.join(sorted(missing_assets))}"
            )

    return warnings


def _collect_asset_links(spec: dict) -> set[str]:
    """Collect all asset/template_link references from a spec."""
    links: set[str] = set()
    for ch in spec.get("chapters", []):
        for page in ch.get("pages", []):
            for block in page.get("blocks", []):
                if block.get("asset"):
                    links.add(block["asset"])
    # Also check asset_manifest
    for asset in spec.get("asset_manifest", []):
        if asset.get("template_link"):
            links.add(asset["template_link"])
    return links


# ── Diff tracking ────────────────────────────────────────────────────────────

def compute_edit_diff(old_spec: dict, new_spec: dict) -> dict:
    """Compute a structured diff between old and new specs.

    Returns:
        blocks_changed: list of block selectors that changed
        blocks_added: list of new blocks
        blocks_removed: list of removed blocks
        summary: human-readable summary of changes
    """
    old_blocks = _index_blocks(old_spec)
    new_blocks = _index_blocks(new_spec)

    old_keys = set(old_blocks.keys())
    new_keys = set(new_blocks.keys())

    blocks_added = sorted(new_keys - old_keys)
    blocks_removed = sorted(old_keys - new_keys)
    blocks_changed: list[str] = []

    for key in sorted(old_keys & new_keys):
        if old_blocks[key] != new_blocks[key]:
            blocks_changed.append(key)

    # Build human-readable summary
    summary_parts: list[str] = []
    if blocks_changed:
        summary_parts.append(f"{len(blocks_changed)} block(s) modified")
    if blocks_added:
        summary_parts.append(f"{len(blocks_added)} block(s) added")
    if blocks_removed:
        summary_parts.append(f"{len(blocks_removed)} block(s) removed")

    # Check chapter-level changes
    old_chapters = old_spec.get("chapters", [])
    new_chapters = new_spec.get("chapters", [])
    if len(new_chapters) != len(old_chapters):
        summary_parts.append(
            f"chapters: {len(old_chapters)} -> {len(new_chapters)}"
        )

    summary = "; ".join(summary_parts) if summary_parts else "No structural changes detected"

    return {
        "blocks_changed": blocks_changed,
        "blocks_added": blocks_added,
        "blocks_removed": blocks_removed,
        "summary": summary,
    }


def _index_blocks(spec: dict) -> dict[str, dict]:
    """Index all blocks by their chapter.page.block selector."""
    index: dict[str, dict] = {}
    for ci, ch in enumerate(spec.get("chapters", [])):
        for pi, page in enumerate(ch.get("pages", [])):
            for bi, block in enumerate(page.get("blocks", [])):
                key = f"{ci}.{pi}.{bi}"
                index[key] = block
    return index


# ── Parsing / helpers ────────────────────────────────────────────────────────

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


# ── Gemini edit functions ────────────────────────────────────────────────────

async def _gemini_edit_block(
    block: dict,
    instruction: str,
    target_text: str | None,
    system_prompt: str,
) -> dict | None:
    model = get_chat_model(temperature=0.4).with_structured_output(Block)
    prompt = (
        f"Current block (JSON): {json.dumps(block)}\n"
        f"Selected text: {target_text or 'N/A'}\n"
        f"Requested change: {instruction}\n"
        "Return the full updated block."
    )
    out = await model.ainvoke([("system", system_prompt), ("user", prompt)])
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
    spec: dict,
    instruction: str,
    target_text: str | None,
    system_prompt: str,
) -> dict | None:
    model = get_chat_model(temperature=0.4).with_structured_output(Lastenheft)
    prompt = (
        f"Current specification (JSON): {json.dumps(spec)}\n"
        f"Context / selected text: {target_text or 'N/A'}\n"
        f"Requested change: {instruction}\n"
        "Return the full updated specification."
    )
    out = await model.ainvoke([("system", system_prompt), ("user", prompt)])
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


# ── Main entry point ─────────────────────────────────────────────────────────

async def generate_edited_spec(
    spec: dict,
    instruction: str,
    selector: str | None,
    target_text: str | None,
    *,
    company_name: str = "",
    plan_summary: dict | None = None,
    compliance_requirements: list[str] | None = None,
    audience: str = "",
    edit_history: list[dict] | None = None,
) -> dict:
    """Return a NEW spec dict with the requested edit applied.

    When `selector` ("chapter.page.block") points at a real block, only that
    block is rewritten; otherwise the whole spec is edited.

    Enhanced parameters:
        company_name: Name of the company this course is for.
        plan_summary: Dict with objectives, competencies, etc from the plan.
        compliance_requirements: List of compliance rules that must not be violated.
        audience: Target audience description.
        edit_history: List of previous edit dicts (prompt, status) for context.
    """
    new_spec = copy.deepcopy(spec)
    idx = _parse_selector(selector)
    block = _get_block(new_spec, idx) if idx is not None else None

    if idx is not None and block is not None:
        # Block-level edit
        system_prompt = _format_system_prompt(
            BLOCK_EDIT_SYSTEM,
            company_name=company_name,
            audience=audience,
            plan_summary=plan_summary,
            compliance_requirements=compliance_requirements,
            edit_history=edit_history,
        )
        updated: dict | None = None
        if gemini_available():
            try:
                updated = await _gemini_edit_block(
                    block, instruction, target_text, system_prompt
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini block edit failed (%s); using local fallback", exc)

        if updated is None:
            updated = _local_edit_block(block, instruction)

        # Validate and retry once if needed
        c, p, b = idx
        new_spec["chapters"][c]["pages"][p]["blocks"][b] = updated
        validation_warnings = validate_edited_spec(spec, new_spec, "block")
        if validation_warnings and gemini_available():
            logger.info("Block edit validation warnings: %s; retrying", validation_warnings)
            try:
                retry_instruction = (
                    f"{instruction}\n\n"
                    f"IMPORTANT: Fix these validation issues: {'; '.join(validation_warnings)}"
                )
                retried = await _gemini_edit_block(
                    block, retry_instruction, target_text, system_prompt
                )
                if retried is not None:
                    new_spec["chapters"][c]["pages"][p]["blocks"][b] = retried
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini block retry failed (%s); keeping first result", exc)

        return new_spec

    # No specific block selected -> spec-level edit.
    system_prompt = _format_system_prompt(
        SPEC_EDIT_SYSTEM,
        company_name=company_name,
        audience=audience,
        plan_summary=plan_summary,
        compliance_requirements=compliance_requirements,
        edit_history=edit_history,
    )
    if gemini_available():
        try:
            edited = await _gemini_edit_spec(
                new_spec, instruction, target_text, system_prompt
            )
            if edited is not None:
                # Validate and retry once if needed
                validation_warnings = validate_edited_spec(spec, edited, "spec")
                if validation_warnings:
                    logger.info("Spec edit validation warnings: %s; retrying", validation_warnings)
                    try:
                        retry_instruction = (
                            f"{instruction}\n\n"
                            f"IMPORTANT: Fix these validation issues: "
                            f"{'; '.join(validation_warnings)}"
                        )
                        retried = await _gemini_edit_spec(
                            new_spec, retry_instruction, target_text, system_prompt
                        )
                        if retried is not None:
                            return retried
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Gemini spec retry failed (%s); keeping first result", exc
                        )
                return edited
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini spec edit failed (%s); using local fallback", exc)
    return _local_edit_spec(new_spec, instruction)
