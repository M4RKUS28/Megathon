from __future__ import annotations


def build_course_spec(course: dict, plan: dict) -> tuple[str, dict, list[dict]]:
    chapters = plan.get("chapters", [])
    screens = [
        "Course shell with chapter sidebar, top progress bar, learner status, and responsive mobile drawer.",
        "Chapter lesson screen with visual media area, compact learning chunks, and one required interaction.",
        "Chapter quiz screen with 80 percent pass threshold, retry state, attempt history, and locked next navigation.",
        "Progress dashboard showing completion state, scores, retries, and time-spent placeholders.",
        "Completion and certificate screen unlocked only after all chapter quizzes pass.",
    ]
    interaction_rotation = [
        "hotspot hazard spotting",
        "flashcard check",
        "branching decision tree",
        "drag and drop process ordering",
        "timeline simulation",
    ]
    chapter_specs = []
    asset_manifest = []
    for index, chapter in enumerate(chapters, start=1):
        template_link = f"/resources/images/img_{index:03d}"
        interaction = interaction_rotation[(index - 1) % len(interaction_rotation)]
        chapter_specs.append(
            {
                "chapter_id": chapter["id"],
                "title": chapter["title"],
                "duration_minutes": chapter["duration_minutes"],
                "screen_flow": [
                    "intro visual",
                    "microlearning content",
                    interaction,
                    "scenario reflection",
                    "locked quiz",
                ],
                "media_placeholders": [template_link],
                "interaction": {
                    "type": interaction,
                    "requirements": [
                        "must require learner input before quiz unlock",
                        "must provide immediate feedback",
                        "must persist completion locally",
                    ],
                },
                "quiz": {
                    "question_count": max(3, chapter.get("quiz", {}).get("questions", 3)),
                    "passing_threshold_percent": 80,
                    "retry_required": True,
                    "unlock_next_on_pass": True,
                },
            }
        )
        asset_manifest.append(
            {
                "template_link": template_link,
                "type": "image",
                "dimensions": "16:9",
                "description": f"Polished training visual for {chapter['title']} in the context of {course['company_context']}. Show realistic work setting, key safety cues, and clear foreground action.",
                "purpose": f"Chapter {index} hero and interaction support visual.",
            }
        )
        asset_manifest.append(
            {
                "template_link": f"/resources/icons/icon_{index:03d}",
                "type": "icon",
                "dimensions": "1:1",
                "description": f"Simple operational icon for {chapter['title']}.",
                "purpose": f"Sidebar and progress marker for chapter {index}.",
            }
        )
    spec = {
        "product": "CourseForge Devin generated course app",
        "course_title": course["title"],
        "screens": screens,
        "navigation_behavior": {
            "chapter_sidebar": True,
            "locked_sequential_navigation": True,
            "next_chapter_unlock_rule": "current chapter quiz score >= 80",
            "local_state_persistence": "localStorage",
        },
        "visual_style": {
            "tone": "clean operational SaaS training interface",
            "layout": "responsive, sidebar on desktop, drawer/stack on mobile",
            "animations": "subtle progress and interaction feedback transitions",
        },
        "critical_learning_rules": [
            "The course must never be pure text.",
            "Every chapter must contain at least one interaction.",
            "Every chapter ends with a quiz.",
            "Passing threshold is 80 percent.",
            "Below 80 percent requires retry.",
            "Next chapter unlocks only after passing the current chapter quiz.",
            "Show progress, attempts, completion state, and score history.",
        ],
        "chapters": chapter_specs,
        "reporting": {
            "track": ["page progress", "chapter completion", "quiz attempts", "score history", "time spent", "drop-off point"],
            "certificate": "show when all chapters complete",
        },
        "responsive_behavior": "No overlapping UI; compact controls on mobile; text wraps cleanly inside controls.",
    }
    markdown_lines = [
        f"# Lastenheft: {course['title']}",
        "",
        "## Screens",
        *[f"- {screen}" for screen in screens],
        "",
        "## Learning Rules",
        *[f"- {rule}" for rule in spec["critical_learning_rules"]],
        "",
        "## Chapters",
    ]
    for chapter in chapter_specs:
        markdown_lines.extend(
            [
                f"### {chapter['title']}",
                f"- Duration: {chapter['duration_minutes']} minutes",
                f"- Interaction: {chapter['interaction']['type']}",
                f"- Quiz: {chapter['quiz']['question_count']} questions, {chapter['quiz']['passing_threshold_percent']} percent threshold",
                f"- Media: {', '.join(chapter['media_placeholders'])}",
            ]
        )
    return "\n".join(markdown_lines), spec, asset_manifest
