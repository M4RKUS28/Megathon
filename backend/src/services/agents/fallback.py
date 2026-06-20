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
    intro_audio = f"/resources/audio/{idx:02d}-p1"
    concepts_audio = f"/resources/audio/{idx:02d}-p2"
    practice_audio = f"/resources/audio/{idx:02d}-p3"
    convo_turns = [
        ("mentor", "Mentor", f"Welcome! Let's cover {title_lc} together."),
        ("you", "You", "Great — where do I start?"),
        ("mentor", "Mentor", "We'll go page by page: the key concepts first, then practice."),
        ("you", "You", "Sounds good. I'm ready when you are."),
    ]
    convo_audio = [f"/resources/audio/{idx:02d}-c{n}" for n in range(1, len(convo_turns) + 1)]
    hero_desc = (
        f"Illustrative hero image for '{chapter_title}' at {company}: modern, "
        "friendly workplace scene, brand colors, soft lighting."
    )
    apply_desc = (
        f"People applying {title_lc} in a real {company} workplace situation: "
        "hands-on, step-by-step, brand colors."
    )
    intro_narration = (
        f"Welcome to {chapter_title}. In this chapter you will learn what {title_lc} "
        f"means at {company} and why it matters for your day-to-day work. We will go "
        "step by step: first the key concepts, then how to apply them in practice. "
        "Take your time on each page, and when you are ready, the knowledge check at "
        "the end lets you confirm what you have learned."
    )
    concepts_narration = (
        f"Let's look at the key concepts behind {title_lc}. There are three things to "
        f"remember: why {title_lc} matters, what you need to get started, and the "
        "common pitfalls to avoid. Keep these in mind as we move on — they are the "
        "foundation for everything that follows, and they will come back in the "
        "knowledge check."
    )
    practice_narration = (
        f"Now let's put {title_lc} into practice. You'll match each step to what it "
        "does, and see how the key metrics improve over time as adoption grows. The "
        f"takeaway is simple: {title_lc} is part of how {company} works, and applying "
        "it well makes a real difference. Try the interactions on this page before you "
        "continue."
    )
    assets = [
        AssetSpec(
            template_link=hero_link,
            type="image",
            dimensions="16:9",
            description=hero_desc,
            purpose="Chapter intro / context image",
            alt_text=f"Hero image for {chapter_title}",
            usage_context=f"image block on Introduction page in chapter '{chapter_title}'",
        ),
        AssetSpec(
            template_link=apply_link,
            type="image",
            dimensions="16:9",
            description=apply_desc,
            purpose="Applied example image",
            alt_text=f"Applying {title_lc} at {company}",
            usage_context=f"image block on Apply it page in chapter '{chapter_title}'",
        ),
        AssetSpec(
            template_link=chart_link,
            type="diagram",
            dimensions="4:3",
            description=f"Bar chart showing key metrics for {chapter_title} (Q1-Q4 adoption).",
            purpose="Data visualisation for chapter metrics",
            alt_text=f"{chapter_title} key metrics chart",
            usage_context=f"chart block on Apply it page in chapter '{chapter_title}'",
        ),
        AssetSpec(
            template_link=intro_audio,
            type="audio",
            description=intro_narration,
            purpose="Spoken narration for the introduction page",
            alt_text=f"Narration: Introduction to {chapter_title}",
            usage_context=f"audio block on Introduction page in chapter '{chapter_title}'",
        ),
        AssetSpec(
            template_link=concepts_audio,
            type="audio",
            description=concepts_narration,
            purpose="Spoken narration for the key concepts page",
            alt_text=f"Narration: Key concepts of {title_lc}",
            usage_context=f"audio block on Key concepts page in chapter '{chapter_title}'",
        ),
        AssetSpec(
            template_link=practice_audio,
            type="audio",
            description=practice_narration,
            purpose="Spoken narration for the apply-it page",
            alt_text=f"Narration: Applying {title_lc}",
            usage_context=f"audio block on Apply it page in chapter '{chapter_title}'",
        ),
        *(
            AssetSpec(
                template_link=link,
                type="audio",
                description=text,
                purpose="Conversation line narration",
                alt_text=f"{name}: {text[:80]}",
                usage_context=f"conversation turn on Introduction page in chapter '{chapter_title}'",
                voice="Puck" if pid == "you" else None,
            )
            for (pid, name, text), link in zip(convo_turns, convo_audio)
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
                type="conversation",
                data={
                    "personas": [
                        {
                            "id": "mentor",
                            "name": "Mentor",
                            "role": "Your guide",
                            "side": "left",
                            "avatar": "f-3",
                        },
                        {
                            "id": "you",
                            "name": "You",
                            "role": "New colleague",
                            "side": "right",
                            "avatar": "m-4",
                        },
                    ],
                    "turns": [
                        {"persona": pid, "text": text, "audio": link}
                        for (pid, _name, text), link in zip(convo_turns, convo_audio)
                    ],
                },
            ),
            Block(type="audio", asset=intro_audio, text=intro_narration),
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
            Block(type="audio", asset=concepts_audio, text=concepts_narration),
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
                type="minigame",
                data={
                    "game": "order",
                    "title": "Sequence sprint",
                    "prompt": f"Put the {chapter_title.lower()} workflow in the right order.",
                    "steps": [
                        "Prepare the right context and access",
                        "Execute the task using the documented process",
                        "Review the outcome and capture what changed",
                        "Share the result with the people who need it",
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
            Block(type="audio", asset=practice_audio, text=practice_narration),
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
