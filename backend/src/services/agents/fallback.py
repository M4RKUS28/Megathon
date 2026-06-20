"""Deterministic, offline generators used when Gemini is not configured (or a
call fails). They keep the entire 5-phase pipeline runnable and demoable without
any external API, and produce schema-valid output.
"""

from __future__ import annotations

from .schemas import (
    AssessmentRequirement,
    AssetNeed,
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
    chapter_title: str, ch_id: str, idx: int, company: str, key_points: list[str]
) -> tuple[list[Page], list[AssetSpec]]:
    """Build several mixed-media pages for a chapter (never plain text, never a
    single long page). The end-of-chapter quiz is added by the caller."""
    title_lc = chapter_title.lower()
    hero_link = f"/resources/images/{idx:02d}-a"
    apply_link = f"/resources/images/{idx:02d}-b"
    chart_link = f"/resources/charts/{idx:02d}"
    hero_desc = (
        f"Illustrative hero image for '{chapter_title}' at {company}: modern, "
        "friendly workplace scene, brand colors, soft lighting."
    )
    apply_desc = (
        f"People applying {title_lc} in a real {company} workplace situation: "
        "hands-on, step-by-step, brand colors."
    )
    assets = [
        AssetSpec(
            template_link=hero_link,
            type="image",
            dimensions="16:9",
            description=hero_desc,
            purpose="Chapter intro / context image",
            alt_text=f"Hero image for {chapter_title}",
        ),
        AssetSpec(
            template_link=apply_link,
            type="image",
            dimensions="16:9",
            description=apply_desc,
            purpose="Applied example image",
            alt_text=f"Applying {title_lc} in practice",
        ),
    ]

    intro_page = Page(
        id=f"{ch_id}-p1",
        title="Introduction",
        learning_goal=f"Understand why {title_lc} matters at {company}.",
        content_goals=[
            f"Context: why {company} prioritises {title_lc}",
            f"Overview of {title_lc} in daily operations",
            "What you will learn and do in this chapter",
        ],
        learner_action=(
            "Reads the context paragraph, views the hero image, and follows "
            "a mentor dialogue that sets expectations for the chapter."
        ),
        ui_treatment=(
            "Full-width hero image at top, paragraph below, followed by a "
            "speech-bubble dialogue component with mentor avatar."
        ),
        worked_example=(
            f"Alex, a new hire at {company}, arrives for their first day and is "
            f"introduced to {title_lc} during orientation. The mentor walks them "
            "through why it matters and what to expect."
        ),
        recommended_interaction=(
            "dialogue — a two-person conversation grounds the topic in a real "
            "human interaction, making the intro relatable rather than lecture-like."
        ),
        required_behavior=(
            "Hero image renders at full width; dialogue component auto-scrolls "
            "through turns with a subtle typing animation; Next button enabled "
            "after the last turn."
        ),
        feedback_behavior="No interactive input on this page; purely expository.",
        success_criterion=(
            "Image loads, dialogue renders all turns, learner can proceed to "
            "page 2."
        ),
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
                    "Work through each page, then pass the knowledge check "
                    "to continue."
                ),
            ),
            Block(
                type="dialogue",
                interaction_goal="Build rapport and preview the learning journey",
                suggested_interaction="Animated speech bubbles appearing sequentially",
                data={
                    "turns": [
                        {
                            "speaker": "Mentor",
                            "text": f"Welcome! Let's cover {title_lc}.",
                        },
                        {"speaker": "You", "text": "Great \u2014 where do I start?"},
                        {
                            "speaker": "Mentor",
                            "text": (
                                "We'll go page by page: concepts first, "
                                "then practice."
                            ),
                        },
                    ]
                },
            ),
        ],
        asset_needs=[
            AssetNeed(
                template_link=hero_link,
                type="image",
                description=hero_desc,
            ),
        ],
    )

    concepts_page = Page(
        id=f"{ch_id}-p2",
        title="Key concepts",
        learning_goal=(
            f"Identify and explain the core principles of {title_lc}."
        ),
        content_goals=key_points or [
            f"Why {title_lc} matters",
            "What you need to get started",
            "Common pitfalls and how to avoid them",
        ],
        learner_action=(
            "Reviews the key points list, flips through flashcards to test "
            "recall, and reads the tip callout."
        ),
        ui_treatment=(
            "Bulleted list with icons, followed by a horizontal flashcard "
            "carousel, and a highlighted callout box."
        ),
        worked_example=(
            f"At {company}, a common pitfall in {title_lc} is skipping the "
            "documentation step. The flashcards highlight the correct "
            "terminology and the best-practice workflow."
        ),
        recommended_interaction=(
            "flashcards — active recall via flip cards reinforces terminology "
            "better than passive reading."
        ),
        required_behavior=(
            "Each flashcard flips on click/tap with a smooth CSS transform; "
            "all cards must be flipped at least once before the Next button "
            "enables."
        ),
        feedback_behavior=(
            "Flashcards: front shows the term, back reveals the definition. "
            "No scoring; the act of flipping is the engagement."
        ),
        success_criterion=(
            "All flashcards flipped; learner can articulate the key terms."
        ),
        estimated_minutes=3,
        blocks=[
            Block(
                type="list",
                items=key_points or [
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
                        {
                            "front": "Key term",
                            "back": f"A concept central to {title_lc}.",
                        },
                        {
                            "front": "Best practice",
                            "back": "Follow the documented SOP.",
                        },
                    ]
                },
            ),
            Block(
                type="callout",
                text=(
                    "Tip: revisit these concepts before the knowledge check."
                ),
            ),
        ],
        asset_needs=[],
    )

    practice_page = Page(
        id=f"{ch_id}-p3",
        title="Apply it",
        learning_goal=(
            f"Apply {title_lc} concepts by matching steps and interpreting data."
        ),
        content_goals=[
            f"Hands-on practice with {title_lc} workflow steps",
            "Data interpretation via an adoption-rate chart",
            f"Consolidation: why {chapter_title} matters at {company}",
        ],
        learner_action=(
            "Drags step labels to their correct descriptions, then reviews "
            "a bar chart showing adoption metrics."
        ),
        ui_treatment=(
            "Context image at top, drag-drop interaction in the centre, "
            "Chart.js bar chart below, and a callout summary."
        ),
        worked_example=(
            f"The drag-drop mirrors a real {company} workflow: Prepare the "
            "environment, Execute the task, Review the results. The chart "
            "shows how adoption of this practice grew over four quarters."
        ),
        recommended_interaction=(
            "dragdrop + chart — drag-drop tests procedural knowledge; the "
            "chart adds a data-literacy element and visual variety."
        ),
        required_behavior=(
            "Drag-drop: items snap to targets; incorrect items bounce back "
            "with a shake animation; all pairs must match before Next "
            "enables. Chart: renders as a responsive bar chart with hover "
            "tooltips."
        ),
        feedback_behavior=(
            "Drag-drop: correct match shows green outline; wrong match "
            "shakes the item back. Chart: hover reveals exact value."
        ),
        success_criterion=(
            "All 3 drag-drop pairs matched correctly; chart renders with "
            "4 bars and tooltips."
        ),
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
                    "datasets": [
                        {"label": "Adoption", "data": [20, 45, 70, 90]}
                    ],
                },
            ),
            Block(
                type="callout",
                text=(
                    f"Key takeaway: {chapter_title} is part of how "
                    f"{company} works."
                ),
            ),
        ],
        asset_needs=[
            AssetNeed(
                template_link=apply_link,
                type="image",
                description=apply_desc,
            ),
        ],
    )
    return [intro_page, concepts_page, practice_page], assets


def fallback_lastenheft(plan: CoursePlan, company_name: str, primary_color: str) -> Lastenheft:
    chapters: list[SpecChapter] = []
    manifest: list[AssetSpec] = []
    for i, ch in enumerate(plan.chapters):
        pages, assets = _chapter_pages(
            ch.title, ch.id, i, company_name, ch.key_points
        )
        manifest.extend(assets)
        learning_points = ch.key_points or [f"Understand {ch.title.lower()}"]
        first_kp = (ch.key_points[0] if ch.key_points else ch.title).lower()
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
                            question=(
                                f"A colleague skips the {first_kp} step. "
                                "What is the most likely consequence?"
                            ),
                            options=[
                                "Non-compliance with the documented procedure",
                                "Faster project completion",
                                "No impact on quality",
                                "Automatic approval by the system",
                            ],
                            answerIndex=0,
                            explanation=(
                                f"Skipping {first_kp} violates the SOP and "
                                "can lead to compliance issues."
                            ),
                            bloom_level="remember",
                            learning_point_ref=learning_points[0] if learning_points else "",
                        ),
                        QuizQuestion(
                            question=(
                                f"Which action best demonstrates "
                                f"'{ch.title.lower()}' in practice?"
                            ),
                            options=[
                                f"Following the {company_name} SOP for {first_kp}",
                                "Improvising a new process without review",
                                "Delegating without documentation",
                                "Waiting for someone else to act",
                            ],
                            answerIndex=0,
                            explanation=(
                                "The documented SOP ensures consistency and "
                                "compliance."
                            ),
                            bloom_level="understand",
                            learning_point_ref=learning_points[0] if learning_points else "",
                        ),
                        QuizQuestion(
                            question=(
                                f"You notice a problem during the "
                                f"'{ch.title.lower()}' process. What should "
                                "you do first?"
                            ),
                            options=[
                                "Report it following the escalation procedure",
                                "Ignore it and continue",
                                "Fix it yourself without telling anyone",
                                "Post about it on social media",
                            ],
                            answerIndex=0,
                            explanation=(
                                "Proper escalation ensures the issue is "
                                "tracked and resolved."
                            ),
                            bloom_level="apply",
                            learning_point_ref=learning_points[0] if learning_points else "",
                        ),
                    ],
                ),
                assessment_requirements=AssessmentRequirement(
                    tested_goals=[
                        p.learning_goal for p in pages if p.learning_goal
                    ],
                    question_types=["multiple-choice"],
                    misconceptions_to_probe=[
                        f"Skipping {first_kp} has no consequences",
                        "Improvising is acceptable when no SOP exists",
                        "Problems can be ignored if they seem minor",
                    ],
                    minimum_questions=3,
                    passing_pct=80,
                    feedback_on_wrong=(
                        "Show the correct answer and a one-sentence "
                        "explanation referencing the relevant page."
                    ),
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
