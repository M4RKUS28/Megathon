from __future__ import annotations

import json


DEVIN_STRUCTURED_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["summary", "branch", "commit_sha", "build_status", "tests", "lint", "qa_notes"],
    "properties": {
        "summary": {"type": "string"},
        "branch": {"type": "string"},
        "commit_sha": {"type": "string"},
        "pr_url": {"type": ["string", "null"]},
        "build_status": {"type": "string"},
        "tests": {"type": "string"},
        "lint": {"type": "string"},
        "qa_notes": {"type": "string"},
    },
}


def _json_block(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def implementation_prompt(course: dict, plan: dict, spec: dict, asset_manifest: list[dict], settings: object) -> str:
    return f"""You are Devin acting as the autonomous implementation layer for CourseForge Devin.

Build the actual generated course app for this approved request. Work in this repository:
- Repo URL: {settings.devin_repo_url}
- Target base branch: {settings.devin_default_branch}
- Create a clear feature branch for the course implementation.
- Commit all generated course work with a clear message.

Use a standalone Vite + React + TypeScript course app under /generated/generated-course.
Required behavior:
- Implement locked sequential chapter navigation.
- Implement per-chapter quiz validation.
- Enforce an 80 percent pass threshold.
- Require retry below 80 percent.
- Unlock the next chapter only after the current chapter quiz passes.
- Track progress, attempts, completion state, score history, time spent, and local state persistence.
- Use placeholder asset links exactly as provided, such as /resources/images/img_001.
- Include interactive visual learning components in every chapter.
- The course must never be pure text.
- Make the UI polished, responsive, and suitable for a workplace training course.
- Run build/tests/lint where available and fix failures.

Approved course request:
{_json_block(course)}

Approved course plan:
{_json_block(plan)}

Lastenheft / implementation specification:
{_json_block(spec)}

Asset manifest:
{_json_block(asset_manifest)}

When finished, provide structured output with branch, commit SHA, PR URL if available, build status, test/lint results, and a concise summary."""


def asset_integration_prompt(course: dict, asset_map: list[dict], settings: object) -> str:
    return f"""You are Devin continuing the CourseForge Devin course build.

Repo URL: {settings.devin_repo_url}
Base branch: {settings.devin_default_branch}
Course: {course['title']}

Load this asset_map and integrate it into /generated/generated-course:
{_json_block(asset_map)}

Tasks:
- Search the generated course codebase.
- Replace every template_link with its final_url exactly.
- Preserve local fallback behavior if an asset URL is unavailable.
- Adjust layout and aspect ratios so visuals render cleanly.
- Run build/tests/lint where available.
- Commit the asset integration changes with a clear message.
- Report branch, commit SHA, PR URL if available, QA/build results, and a concise summary."""


def qa_prompt(course: dict, settings: object) -> str:
    return f"""You are Devin performing autonomous QA and fixes for the generated CourseForge Devin course app.

Repo URL: {settings.devin_repo_url}
Base branch: {settings.devin_default_branch}
Course: {course['title']}

Inspect /generated/generated-course and verify:
- chapter locking and sequential navigation
- 80 percent quiz pass threshold
- retry behavior below threshold
- progress tracking, completion state, score history, and local persistence
- every chapter contains at least one interaction
- every chapter ends with a quiz
- responsive desktop and mobile layout
- placeholder/final assets render without broken layout

Run build/tests/lint where available. Fix failures autonomously, commit changes, and report final status with branch, commit SHA, PR URL if available, build status, test/lint results, and concise QA notes."""
