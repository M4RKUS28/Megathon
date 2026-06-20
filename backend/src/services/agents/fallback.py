"""Deterministic, offline generators used when Gemini is not configured (or a
call fails). They keep the entire 5-phase pipeline runnable and demoable without
any external API, and produce schema-valid output.
"""

from __future__ import annotations

from .schemas import (
    AssetSpec,
    Block,
    CoursePlan,
    Lastenheft,
    Page,
    PlanChapter,
    Quiz,
    QuizQuestion,
    SpecChapter,
    StyleGuide,
)


def _slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")[:48] or "chapter"


def fallback_plan(brief: dict, company_name: str) -> CoursePlan:
    title = brief.get("title") or "Onboarding Course"
    topics = brief.get("topics") or [
        "Welcome & context",
        "Core concepts",
        "Tools & access",
        "Ways of working",
    ]
    audience = brief.get("audience", "new employees")
    blooms = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
    chapters = [
        PlanChapter(
            id=f"{i}-{_slug(t)}",
            title=t,
            objective=f"Understand {t.lower()} as it applies to {audience}.",
            competency=t,
            estimated_minutes=10 + 2 * i,
            key_points=[
                f"Why {t.lower()} matters at {company_name}",
                "What you need to get started",
                "Common pitfalls and how to avoid them",
            ],
            bloom_level=blooms[i % len(blooms)],
        )
        for i, t in enumerate(topics)
    ]
    return CoursePlan(
        title=title,
        description=brief.get("goals", f"An onboarding course for {audience}."),
        language=brief.get("language", "en"),
        difficulty=brief.get("difficulty", "beginner"),
        audience=audience,
        estimated_minutes=sum(c.estimated_minutes for c in chapters),
        objectives=[f"Be able to {c.objective[0].lower()}{c.objective[1:]}" for c in chapters],
        competencies=[c.competency for c in chapters],
        mandatory_topics=topics[:1],
        compliance_requirements=[],
        knowledge_sources=[],
        chapters=chapters,
    )


def _chapter_pages(
    chapter_title: str, ch_id: str, idx: int, company: str
) -> tuple[list[Page], list[AssetSpec]]:
    """Build several mixed-media pages for a chapter (never plain text, never a
    single long page). The end-of-chapter quiz is added by the caller."""
    title_lc = chapter_title.lower()
    hero_link = f"/resources/images/{idx:02d}-a"
    apply_link = f"/resources/images/{idx:02d}-b"
    chart_link = f"/resources/charts/{idx:02d}"
    assets = [
        AssetSpec(
            template_link=hero_link,
            type="image",
            dimensions="16:9",
            description=(
                f"Illustrative hero image for '{chapter_title}' at {company}: modern, "
                "friendly workplace scene, brand colors, soft lighting."
            ),
            purpose="Chapter intro / context image",
            alt_text=f"Hero image for {chapter_title}",
        ),
        AssetSpec(
            template_link=apply_link,
            type="image",
            dimensions="16:9",
            description=(
                f"People applying {title_lc} in a real {company} workplace situation: "
                "hands-on, step-by-step, brand colors."
            ),
            purpose="Applied example image",
            alt_text=f"Applying {title_lc} in practice",
        ),
    ]
    intro_page = Page(
        id=f"{ch_id}-p1",
        title="Introduction",
        content_goal=f"Orient the learner on {title_lc} and set expectations",
        learner_action="Read the overview, engage with the mentor dialogue",
        ui_treatment="hero splash with full-width image",
        estimated_minutes=2,
        blocks=[
            Block(
                type="image",
                asset=hero_link,
                text=chapter_title,
                interaction_goal="Set visual context for the chapter",
            ),
            Block(
                type="paragraph",
                text=(
                    f"This chapter introduces {title_lc} at {company}. "
                    "Work through each page, then pass the knowledge check to continue."
                ),
            ),
            Block(
                type="dialogue",
                interaction_goal="Build rapport and preview the learning journey",
                suggested_interaction="Animated speech bubbles appearing sequentially",
                data={
                    "turns": [
                        {"speaker": "Mentor", "text": f"Welcome! Let's cover {title_lc}."},
                        {"speaker": "You", "text": "Great — where do I start?"},
                        {
                            "speaker": "Mentor",
                            "text": "We'll go page by page: concepts first, then practice.",
                        },
                    ]
                },
            ),
        ],
    )
    concepts_page = Page(
        id=f"{ch_id}-p2",
        title="Key concepts",
        content_goal=f"Teach the core concepts of {title_lc}",
        learner_action="Study concepts, flip flashcards to self-test",
        ui_treatment="two-column: concepts left, flashcards right",
        estimated_minutes=3,
        blocks=[
            Block(
                type="list",
                items=[
                    f"Why {title_lc} matters",
                    "What you need to get started",
                    "Common pitfalls and how to avoid them",
                ],
                interaction_goal="Present core knowledge points",
            ),
            Block(
                type="flashcards",
                interaction_goal="Active recall of key terms",
                suggested_interaction="Flip-card animation with progress indicator",
                required_behavior="Cards must be flippable; track which were viewed",
                feedback_behavior="Show checkmark after card is flipped",
                data={
                    "cards": [
                        {"front": "Key term", "back": f"A concept central to {title_lc}."},
                        {"front": "Best practice", "back": "Follow the documented SOP."},
                    ]
                },
            ),
            Block(
                type="callout",
                text="Tip: revisit these concepts before the knowledge check.",
            ),
        ],
    )
    practice_page = Page(
        id=f"{ch_id}-p3",
        title="Apply it",
        content_goal=f"Let the learner practice applying {title_lc}",
        learner_action="Complete drag-drop exercise and review metrics chart",
        ui_treatment="interactive workspace with stacked activities",
        estimated_minutes=4,
        blocks=[
            Block(type="image", asset=apply_link, text=f"Applying {title_lc}"),
            Block(
                type="dragdrop",
                interaction_goal="Verify the learner can sequence steps correctly",
                required_behavior="Pairs snap into place; incorrect pairings bounce back",
                feedback_behavior="Green highlight on correct match, shake on incorrect",
                success_criterion="All pairs correctly matched",
                data={
                    "prompt": "Match each step to its description.",
                    "pairs": [
                        {"left": "Step 1", "right": "Prepare"},
                        {"left": "Step 2", "right": "Execute"},
                        {"left": "Step 3", "right": "Review"},
                    ],
                },
            ),
            Block(
                type="chart",
                asset=chart_link,
                interaction_goal="Visualise adoption trend to reinforce the message",
                suggested_interaction="Animate bars on scroll; tooltip on hover",
                data={
                    "chartType": "bar",
                    "title": f"{chapter_title}: key metrics",
                    "labels": ["Q1", "Q2", "Q3", "Q4"],
                    "datasets": [{"label": "Adoption", "data": [20, 45, 70, 90]}],
                },
            ),
            Block(
                type="callout",
                text=f"Key takeaway: {chapter_title} is part of how {company} works.",
            ),
        ],
    )
    return [intro_page, concepts_page, practice_page], assets


def fallback_lastenheft(plan: CoursePlan, company_name: str, primary_color: str) -> Lastenheft:
    chapters: list[SpecChapter] = []
    manifest: list[AssetSpec] = []
    for i, ch in enumerate(plan.chapters):
        pages, assets = _chapter_pages(ch.title, ch.id, i, company_name)
        manifest.extend(assets)
        learning_points = ch.key_points or [f"Understand {ch.title.lower()}"]
        chapters.append(
            SpecChapter(
                id=ch.id,
                title=ch.title,
                objective=ch.objective,
                pages=pages,
                learning_points=learning_points,
                estimated_minutes=ch.estimated_minutes,
                competency=ch.competency,
                bloom_level=ch.bloom_level,
                quiz=Quiz(
                    passing_pct=80,
                    retryable=True,
                    assessment_id=f"quiz-{ch.id}",
                    chapter_ref=ch.id,
                    competency_assessed=ch.competency or ch.title,
                    questions=[
                        QuizQuestion(
                            question=f"What is the focus of '{ch.title}'?",
                            options=[ch.title, "Payroll", "Office snacks", "Parking"],
                            answerIndex=0,
                            explanation=f"This chapter is about {ch.title.lower()}.",
                            bloom_level="remember",
                            learning_point_ref=learning_points[0] if learning_points else "",
                        ),
                        QuizQuestion(
                            question=f"Which is a key point for {ch.title.lower()}?",
                            options=(ch.key_points or ["It matters"])[:1]
                            + ["Ignore the SOP", "Skip onboarding", "Guess"],
                            answerIndex=0,
                            explanation="Refer to the key points covered in this chapter.",
                            bloom_level="understand",
                            learning_point_ref=learning_points[0] if learning_points else "",
                        ),
                    ],
                ),
            )
        )
    return Lastenheft(
        title=plan.title,
        description=plan.description,
        companyName=company_name,
        primaryColor=primary_color,
        language=plan.language,
        passing_pct=80,
        chapters=chapters,
        asset_manifest=manifest,
        target_audience=plan.audience,
        difficulty=plan.difficulty,
        estimated_minutes=plan.estimated_minutes,
        style_guide=StyleGuide(tone="friendly and professional"),
    )
