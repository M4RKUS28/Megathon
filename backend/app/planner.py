from __future__ import annotations

from .schemas import CourseCreate


LEARNING_PRINCIPLES = [
    "Bloom's taxonomy",
    "learning by doing",
    "microlearning",
    "scenario-based learning",
    "spaced reinforcement",
    "practical workplace transfer",
]

KNOWLEDGE_PLACEHOLDERS = [
    "RAG retrieval",
    "company document search",
    "SOP search",
    "compliance search",
    "policy search",
    "wiki search",
    "Cala integration placeholder",
]


def _duration_split(total: int, parts: int) -> list[int]:
    base = max(1, total // parts)
    durations = [base for _ in range(parts)]
    diff = total - sum(durations)
    index = 0
    while diff != 0:
        if diff > 0:
            durations[index % parts] += 1
            diff -= 1
        elif durations[index % parts] > 1:
            durations[index % parts] -= 1
            diff += 1
        index += 1
    return durations


def generate_course_plan(request: CourseCreate) -> dict:
    chapter_templates = [
        ("Orientation and Risk Awareness", "remember", "Identify common hazards and required PPE before entering active work zones."),
        ("Safe Workflows in Context", "understand", "Explain how daily workflows, handoffs, and supervisor escalation reduce incidents."),
        ("Decision Practice and Incident Response", "apply", "Choose the safest response in realistic operational scenarios."),
        ("Reporting, Documentation, and Escalation", "analyze", "Classify incidents and near misses, then route reports with the right evidence."),
        ("Transfer Simulation and Certification", "evaluate", "Demonstrate readiness through an integrated scenario and final assessment."),
    ]
    durations = _duration_split(request.desired_duration_minutes, len(chapter_templates))
    chapters = []
    for index, ((title, bloom_level, outcome), duration) in enumerate(zip(chapter_templates, durations), start=1):
        chapters.append(
            {
                "id": f"chapter-{index}",
                "order": index,
                "title": title,
                "duration_minutes": duration,
                "bloom_level": bloom_level,
                "learning_outcome": outcome,
                "required_content": [
                    f"Company-specific examples for {request.company_context}",
                    "Policy references from RAG/company/SOP/compliance search placeholders",
                    "Short visual explanation followed by practice",
                ],
                "interaction": [
                    "branching scenario" if index in {3, 5} else "interactive diagram",
                    "flashcard reinforcement" if index % 2 == 0 else "process timeline",
                ],
                "quiz": {
                    "questions": 3,
                    "passing_threshold_percent": 80,
                    "retry_required_below_threshold": True,
                    "locks_next_chapter_until_passed": True,
                },
            }
        )
    return {
        "course_overview": {
            "title": request.title,
            "description": request.description,
            "audience": request.target_audience,
            "language": request.language,
            "difficulty": request.difficulty,
            "duration_minutes": request.desired_duration_minutes,
            "company_context": request.company_context,
        },
        "learning_objectives": [
            "Recognize job-relevant risks and required controls.",
            "Apply safe decision-making to realistic workplace scenarios.",
            "Complete incident and near-miss reporting with sufficient detail.",
            "Demonstrate compliance readiness through locked chapter quizzes.",
        ],
        "chapters": chapters,
        "required_content": [
            "Company policy excerpts and SOP references",
            "Visual examples for each workflow step",
            "Scenario prompts grounded in the target audience's daily work",
            "Knowledge placeholders for future retrieval integrations",
        ],
        "compliance_requirements": [
            request.compliance_requirements,
            "Each chapter quiz requires at least 80 percent to unlock the next chapter.",
            "All attempts, scores, retries, and completion states are tracked.",
        ],
        "practical_exercises": [
            "Hazard spotting with feedback",
            "Decision tree for escalation",
            "Incident report drafting",
            "Final transfer simulation",
        ],
        "assessment_strategy": {
            "chapter_quizzes": "Every chapter ends with an 80 percent threshold quiz.",
            "retry_logic": "Learners below 80 percent retry before progressing.",
            "score_history": "All quiz attempts are retained for reporting.",
            "completion": "Certificate unlocks only when every chapter is passed.",
        },
        "learning_principles": LEARNING_PRINCIPLES,
        "company_knowledge_placeholders": KNOWLEDGE_PLACEHOLDERS,
        "approval_required": True,
    }


def apply_chapter_edits(plan: dict, chapter_edits: list[dict] | None) -> dict:
    if not chapter_edits:
        return plan
    current_by_id = {chapter["id"]: chapter for chapter in plan.get("chapters", [])}
    edited_chapters = []
    for order, edit in enumerate(chapter_edits, start=1):
        existing = current_by_id.get(edit["id"], {"id": edit["id"]})
        updated = {**existing, "order": order, "title": edit["title"], "duration_minutes": edit["duration_minutes"]}
        edited_chapters.append(updated)
    plan = {**plan, "chapters": edited_chapters}
    plan["course_overview"]["duration_minutes"] = sum(chapter["duration_minutes"] for chapter in edited_chapters)
    return plan
