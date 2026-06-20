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
        ),
    ]
    intro_page = Page(
        id=f"{ch_id}-p1",
        title="Introduction",
        blocks=[
            Block(type="image", asset=hero_link, text=chapter_title),
            Block(
                type="paragraph",
                text=(
                    f"This chapter introduces {title_lc} at {company}. "
                    "Work through each page, then pass the knowledge check to continue."
                ),
            ),
            Block(
                type="dialogue",
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
        blocks=[
            Block(
                type="list",
                items=[
                    f"Why {title_lc} matters",
                    "What you need to get started",
                    "Common pitfalls and how to avoid them",
                ],
            ),
            Block(
                type="flashcards",
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
        blocks=[
            Block(type="image", asset=apply_link, text=f"Applying {title_lc}"),
            Block(
                type="dragdrop",
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
        chapters.append(
            SpecChapter(
                id=ch.id,
                title=ch.title,
                objective=ch.objective,
                pages=pages,
                quiz=Quiz(
                    passing_pct=80,
                    retryable=True,
                    questions=[
                        QuizQuestion(
                            question=f"What is the focus of '{ch.title}'?",
                            options=[ch.title, "Payroll", "Office snacks", "Parking"],
                            answerIndex=0,
                            explanation=f"This chapter is about {ch.title.lower()}.",
                        ),
                        QuizQuestion(
                            question=f"Which is a key point for {ch.title.lower()}?",
                            options=(ch.key_points or ["It matters"])[:1]
                            + ["Ignore the SOP", "Skip onboarding", "Guess"],
                            answerIndex=0,
                            explanation="Refer to the key points covered in this chapter.",
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
    )
