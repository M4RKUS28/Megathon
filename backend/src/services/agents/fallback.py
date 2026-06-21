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


# ── Interaction type rotation ─────────────────────────────────────────────────

_INTERACTION_ROTATION = [
    "scenario",
    "hotspot",
    "timeline",
    "accordion",
    "dragdrop",
    "flashcards",
]


def _make_interaction_block(
    interaction_type: str, title: str, title_lc: str, key_points: list[str]
) -> Block:
    """Generate a varied interaction block based on the rotation type."""
    kp = key_points or [f"Understanding {title_lc}", "Getting started", "Avoiding mistakes"]
    if interaction_type == "scenario":
        return Block(
            type="scenario",
            data={
                "prompt": (
                    f"A colleague asks you about {title_lc}. They are unsure how to get "
                    "started. What do you do?"
                ),
                "branches": [
                    {
                        "choice": (
                            "Explain the key principles and share the relevant "
                            "documentation"
                        ),
                        "result": (
                            "Great choice! Sharing knowledge and pointing to official "
                            "resources helps the whole team stay aligned and builds trust."
                        ),
                    },
                    {
                        "choice": "Tell them to figure it out on their own",
                        "result": (
                            "This misses an opportunity to build team capability. "
                            "A quick explanation now saves confusion later."
                        ),
                    },
                    {
                        "choice": "Guess at an answer without checking the documentation",
                        "result": (
                            "Guessing can spread misinformation. Always verify against "
                            "the official guidelines before advising others."
                        ),
                    },
                ],
            },
        )
    if interaction_type == "hotspot":
        return Block(
            type="hotspot",
            data={
                "prompt": f"Click on each area to learn more about {title_lc}.",
                "regions": [
                    {
                        "label": kp[0] if len(kp) > 0 else "Concept 1",
                        "detail": (
                            f"This is the foundation of {title_lc}. Understanding this "
                            "principle helps you make better decisions in your daily work."
                        ),
                    },
                    {
                        "label": kp[1] if len(kp) > 1 else "Concept 2",
                        "detail": (
                            "Knowing where to start is half the battle. Follow the "
                            "established guidelines and reach out to your team if unsure."
                        ),
                    },
                    {
                        "label": kp[2] if len(kp) > 2 else "Concept 3",
                        "detail": (
                            "Watch out for common mistakes. Most issues come from "
                            "skipping the preparation stage or not checking the latest "
                            "guidelines."
                        ),
                    },
                ],
            },
        )
    if interaction_type == "timeline":
        return Block(
            type="timeline",
            data={
                "title": f"The {title} process",
                "steps": [
                    {
                        "label": "Step 1: Prepare",
                        "detail": (
                            "Review the latest guidelines and gather the information "
                            "you need. Preparation prevents most common mistakes."
                        ),
                    },
                    {
                        "label": "Step 2: Execute",
                        "detail": (
                            "Follow the established process step by step. If something "
                            "is unclear, check the documentation or ask your team lead."
                        ),
                    },
                    {
                        "label": "Step 3: Review",
                        "detail": (
                            "Check your work against the expected outcomes. Self-review "
                            "catches most issues before they become problems."
                        ),
                    },
                    {
                        "label": "Step 4: Share & improve",
                        "detail": (
                            "Document what you learned and share with the team. "
                            "Continuous improvement is how best practices evolve."
                        ),
                    },
                ],
            },
        )
    if interaction_type == "accordion":
        return Block(
            type="accordion",
            data={
                "sections": [
                    {
                        "title": f"What is {title_lc}?",
                        "content": (
                            f"{title} is a core practice that ensures quality and "
                            "consistency across the organisation. It applies to everyone, "
                            "regardless of role or seniority."
                        ),
                    },
                    {
                        "title": "Why does it matter?",
                        "content": (
                            "It builds trust with customers and colleagues, reduces errors, "
                            "and ensures everyone is working from the same playbook. "
                            "Without it, teams drift apart and quality drops."
                        ),
                    },
                    {
                        "title": "How do I apply it?",
                        "content": (
                            "Follow the three-stage process: prepare, execute, review. "
                            "Always check the latest guidelines before you start, and "
                            "don't hesitate to ask your team for feedback."
                        ),
                    },
                    {
                        "title": "Common mistakes to avoid",
                        "content": (
                            "Skipping the preparation stage is the number one mistake. "
                            "Other common issues include not documenting your work, "
                            "not asking for help when stuck, and assuming you know the "
                            "latest process without checking."
                        ),
                    },
                ],
            },
        )
    if interaction_type == "dragdrop":
        pairs = []
        descriptions = [
            "Gather info and check the latest guidelines",
            "Follow the established process step by step",
            "Check results against expected outcomes",
            "Document lessons and share with the team",
        ]
        labels = (
            kp[:4] if len(kp) >= 4 else ["Prepare", "Execute", "Review", "Share"]
        )
        for label, desc in zip(labels, descriptions):
            pairs.append({"left": label, "right": desc})
        return Block(
            type="dragdrop",
            data={
                "prompt": f"Match each aspect of {title_lc} to its description.",
                "pairs": pairs,
            },
        )
    # flashcards (default)
    cards = []
    if len(kp) >= 3:
        cards = [
            {
                "front": f"What is {title_lc}?",
                "back": (
                    f"{title} is a core practice that ensures quality and consistency. "
                    "It applies to everyone in the organisation."
                ),
            },
            {
                "front": f"Why does {title_lc} matter?",
                "back": (
                    "It builds trust, reduces errors, and keeps everyone aligned. "
                    "Without it, quality and consistency suffer."
                ),
            },
            {
                "front": kp[0],
                "back": (
                    "This is the foundational principle. Understanding it helps you "
                    "make better decisions in your daily work."
                ),
            },
            {
                "front": kp[1],
                "back": (
                    "Knowing where to start is half the battle. Follow the established "
                    "guidelines and reach out if you need help."
                ),
            },
            {
                "front": kp[2],
                "back": (
                    "Most issues come from skipping preparation or not checking the "
                    "latest guidelines. Stay diligent and ask questions."
                ),
            },
        ]
    else:
        cards = [
            {
                "front": f"What is {title_lc}?",
                "back": (
                    "A core practice ensuring quality and consistency"
                    " across the organisation."
                ),
            },
            {
                "front": "What are the 3 stages?",
                "back": "Preparation, execution, and review.",
            },
            {
                "front": "What is the #1 mistake?",
                "back": "Skipping the preparation stage.",
            },
        ]
    return Block(type="flashcards", data={"cards": cards})


# ── Fallback plan ─────────────────────────────────────────────────────────────


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

    # Topic-specific key points, subtopics, and interaction suggestions.
    _topic_meta: dict[str, dict] = {
        "Welcome & context": {
            "key_points": [
                f"The history and mission of {company_name}",
                f"How {company_name} is structured (teams, departments, reporting lines)",
                "Company culture and core values",
                "Your role within the bigger picture",
                "Key contacts and where to get help",
            ],
            "subtopics": [
                "Company history and milestones",
                "Organisational structure",
                "Core values and culture",
                "Your first week checklist",
                "Key contacts and support channels",
            ],
            "interactions": ["accordion", "hotspot", "timeline"],
            "dialogue_appropriate": False,
            "chart_appropriate": False,
        },
        "Core concepts": {
            "key_points": [
                f"The fundamental principles that drive {company_name}",
                "Industry terminology you will encounter daily",
                "How these concepts connect to your specific role",
                "The difference between good and great execution",
                "Resources for deepening your understanding",
            ],
            "subtopics": [
                "Foundational principles",
                "Key terminology and definitions",
                "Role-specific application",
                "Quality standards",
                "Continuous learning resources",
            ],
            "interactions": ["flashcards", "scenario", "dragdrop"],
            "dialogue_appropriate": False,
            "chart_appropriate": False,
        },
        "Tools & access": {
            "key_points": [
                f"The core tools and platforms used at {company_name}",
                "How to get access and set up your accounts",
                "Security best practices (passwords, 2FA, data handling)",
                "Common workflows and shortcuts",
                "Troubleshooting: who to contact when things break",
            ],
            "subtopics": [
                "Core tool overview",
                "Account setup and access",
                "Security and data handling",
                "Daily workflows",
                "Troubleshooting and support",
            ],
            "interactions": ["hotspot", "timeline", "dragdrop"],
            "dialogue_appropriate": False,
            "chart_appropriate": True,
        },
        "Ways of working": {
            "key_points": [
                f"How teams collaborate at {company_name}",
                "Communication norms (meetings, async, escalation)",
                "Feedback culture: giving and receiving constructive feedback",
                "Work-life balance and flexibility policies",
                "How to raise issues and suggest improvements",
            ],
            "subtopics": [
                "Collaboration and teamwork",
                "Communication best practices",
                "Feedback and growth",
                "Work-life balance",
                "Continuous improvement",
            ],
            "interactions": ["scenario", "accordion"],
            "dialogue_appropriate": True,
            "chart_appropriate": False,
        },
    }

    chapters = []
    for i, t in enumerate(topics):
        meta = _topic_meta.get(t, {})
        kp = meta.get("key_points", [
            f"Why {t.lower()} matters at {company_name}",
            "What you need to get started",
            "Common pitfalls and how to avoid them",
            f"How {t.lower()} connects to your daily work",
            "Resources for going deeper",
        ])
        subtopics = meta.get("subtopics", [
            f"Overview of {t.lower()}",
            "Key principles",
            "Practical application",
            "Common challenges",
            "Next steps",
        ])
        interactions = meta.get("interactions", [
            _INTERACTION_ROTATION[i % len(_INTERACTION_ROTATION)],
        ])
        chapters.append(
            PlanChapter(
                id=f"{i}-{_slug(t)}",
                title=t,
                objective=f"Understand {t.lower()} as it applies to {audience}.",
                competency=t,
                estimated_minutes=10 + 2 * i,
                key_points=kp,
                bloom_level=blooms[i % len(blooms)],
                subtopics=subtopics,
                min_pages=5,
                suggested_interactions=interactions,
                dialogue_appropriate=meta.get("dialogue_appropriate", False),
                chart_appropriate=meta.get("chart_appropriate", False),
                depth="standard",
            )
        )
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
        primary_format="expository",
        content_density="rich",
        style_notes=[
            "Use direct, substantive instruction — not conversation-driven content",
            "Include varied interactions in every chapter",
            "Charts only when real data supports them",
        ],
    )


# ── Fallback Lastenheft ──────────────────────────────────────────────────────


def _chapter_pages(
    ch: PlanChapter, idx: int, company: str
) -> tuple[list[Page], list[AssetSpec]]:
    """Build 5+ varied, substantive pages per chapter driven by key_points and
    subtopics. The end-of-chapter quiz is added by the caller."""
    title = ch.title
    title_lc = title.lower()
    key_points = ch.key_points or [
        f"Why {title_lc} matters",
        "What you need to get started",
        "Common pitfalls and how to avoid them",
        f"How {title_lc} connects to your role",
        "Resources for going deeper",
    ]
    subtopics = ch.subtopics or [
        f"Overview of {title_lc}",
        "Key principles",
        "Practical application",
        "Common challenges",
        "Next steps",
    ]
    interactions = ch.suggested_interactions or [
        _INTERACTION_ROTATION[idx % len(_INTERACTION_ROTATION)]
    ]

    pages: list[Page] = []
    assets: list[AssetSpec] = []
    seen_assets: set[str] = set()
    audio_counter = 0

    def _next_audio() -> str:
        nonlocal audio_counter
        audio_counter += 1
        return f"/resources/audio/{idx:02d}-p{audio_counter}"

    def _track_asset(link: str, atype: str, desc: str, purpose: str) -> None:
        if link not in seen_assets:
            seen_assets.add(link)
            assets.append(
                AssetSpec(
                    template_link=link,
                    type=atype,
                    dimensions="16:9",
                    description=desc.strip(),
                    purpose=purpose,
                )
            )

    # ── Page 1: Introduction ──────────────────────────────────────────────
    hero_link = f"/resources/images/{idx:02d}-hero"
    intro_audio = _next_audio()
    _track_asset(
        hero_link, "image",
        f"Modern illustration: the concept of {title_lc} in a {company} context. "
        "Clean, professional design with brand colours.",
        "Chapter intro hero image",
    )
    _track_asset(intro_audio, "audio", (
        f"Welcome to {title}. In this chapter you will learn what {title_lc} means "
        f"at {company} and why it matters for your day-to-day work. We will start "
        f"with the key concepts, look at real examples, and then you will get "
        f"hands-on practice. Take your time on each page and try the interactive "
        f"exercises as you go."
    ), "Spoken narration for the introduction page")
    pages.append(
        Page(
            id=f"{ch.id}-p1",
            title="Introduction",
            blocks=[
                Block(type="image", asset=hero_link,
                      text=f"Modern illustration of {title_lc} in a {company} workplace"),
                Block(type="heading", text=title),
                Block(type="paragraph", text=(
                    f"In this chapter, you will learn what {title_lc} means at {company}, "
                    f"why it matters for your role, and how to apply it in practice. "
                    f"{title} is one of the foundational areas for anyone working at "
                    f"{company}, whether you are brand new or transitioning to a new team."
                )),
                Block(type="callout", text=(
                    f"By the end of this chapter, you should be able to explain {title_lc} "
                    f"to a colleague and identify at least two ways it impacts your "
                    "daily work."
                )),
                Block(type="list", items=[
                    f"What {title_lc} is and why {company} prioritises it",
                    "The key principles you need to know",
                    "How to apply it — with real examples",
                    "Common mistakes and how to avoid them",
                ]),
                Block(type="audio", asset=intro_audio, text=(
                    f"Welcome to {title}. In this chapter you will learn what {title_lc} "
                    f"means at {company} and why it matters for your day-to-day work. "
                    f"We will start with the key concepts, look at real examples, and "
                    f"then you will get hands-on practice. Take your time on each page "
                    f"and try the interactive exercises as you go."
                )),
            ],
        )
    )

    # ── Page 2: Core Concepts ─────────────────────────────────────────────
    concepts_audio = _next_audio()
    kp_display = key_points[:5] if len(key_points) >= 5 else key_points
    _track_asset(concepts_audio, "audio", (
        f"Let's look at the core concepts behind {title_lc}. There are "
        f"{len(kp_display)} key principles to remember. "
        + " ".join(
            f"Number {i + 1}: {kp.lower()}."
            for i, kp in enumerate(kp_display)
        )
        + " Keep these in mind as we move to the deeper topics."
    ), "Spoken narration for the core concepts page")
    pages.append(
        Page(
            id=f"{ch.id}-p2",
            title="Core Concepts",
            blocks=[
                Block(type="heading", text=f"Understanding {title}"),
                Block(type="paragraph", text=(
                    f"Let's break down {title_lc} into its core components. Each of the "
                    f"principles below is something you will encounter regularly at "
                    f"{company}. Understanding them now will save you time and prevent "
                    "common mistakes later."
                )),
                Block(type="list", items=kp_display),
                Block(type="paragraph", text=(
                    f"The first principle — {kp_display[0].lower()} — is the foundation. "
                    "Without understanding why this matters, the rest of the chapter "
                    "won't stick. Think about how this connects to your specific role "
                    "and the work you do every day."
                )),
                Block(type="callout", text=(
                    f"Key insight: {title} is not just a policy or a checklist — it is "
                    f"how {company} delivers quality and maintains trust."
                )),
                Block(type="audio", asset=concepts_audio, text=(
                    f"Let's look at the core concepts behind {title_lc}. There are "
                    f"{len(kp_display)} key principles to remember. "
                    + " ".join(
                        f"Number {i + 1}: {kp.lower()}."
                        for i, kp in enumerate(kp_display)
                    )
                    + " Keep these in mind as we move on."
                )),
            ],
        )
    )

    # ── Page 3: Deep Dive / How It Works ──────────────────────────────────
    process_img = f"/resources/images/{idx:02d}-process"
    deep_audio = _next_audio()
    subtopic_items = subtopics[:5] if len(subtopics) >= 5 else subtopics
    _track_asset(
        process_img, "image",
        f"Diagram showing the key process or workflow for {title_lc}: clear steps, "
        f"arrows connecting stages, in {company} brand colours.",
        "Process diagram for deep dive page",
    )
    _track_asset(deep_audio, "audio", (
        f"Now that you know the principles, let's see how {title_lc} works day to day. "
        "The process typically involves preparation, execution, and review. "
        "The most common mistake people make is skipping the preparation stage. "
        f"At {company}, spending a few minutes preparing can save an hour of rework."
    ), "Spoken narration for the deep dive page")
    pages.append(
        Page(
            id=f"{ch.id}-p3",
            title="How It Works",
            blocks=[
                Block(type="heading", text=f"How {title} Works in Practice"),
                Block(type="paragraph", text=(
                    f"Now that you know the principles, let's see how {title_lc} works "
                    f"day to day at {company}. Whether you are in a technical, creative, "
                    "or operational role, the underlying process is similar."
                )),
                Block(type="list", items=[
                    f"{st} — understanding this helps you apply {title_lc} more effectively"
                    for st in subtopic_items[:4]
                ]),
                Block(type="paragraph", text=(
                    f"The most common mistake people make is skipping preparation. "
                    f"At {company}, we have found that spending even 10 minutes preparing "
                    "can save an hour of rework later. Always start by checking the "
                    "latest guidelines and verifying your assumptions."
                )),
                Block(type="image", asset=process_img,
                      text=f"Diagram: the key stages of {title_lc} at {company}"),
                Block(type="audio", asset=deep_audio, text=(
                    f"Here's how {title_lc} works in practice. The underlying process "
                    f"involves preparation, execution, and review. The most important "
                    f"thing to remember is not to skip preparation. Taking a few minutes "
                    "upfront to check the guidelines can save you a lot of rework later."
                )),
            ],
        )
    )

    # ── Page 4: Real-World Example + Primary Interaction ──────────────────
    example_img = f"/resources/images/{idx:02d}-example"
    example_audio = _next_audio()
    primary_interaction = (
        interactions[0]
        if interactions
        else _INTERACTION_ROTATION[idx % len(_INTERACTION_ROTATION)]
    )
    interaction_block = _make_interaction_block(primary_interaction, title, title_lc, key_points)
    _track_asset(
        example_img, "image",
        f"Realistic workplace scene showing {title_lc} being applied at {company}. "
        "People collaborating, looking at screens or documents, natural and authentic.",
        "Real-world example image",
    )
    _track_asset(example_audio, "audio", (
        f"Now let's see {title_lc} in action. The interactive exercise on this page "
        f"puts you in a realistic scenario. Try it out — there is no wrong answer at "
        "this stage, just practice. The goal is to build familiarity so you feel "
        "confident when you encounter these situations for real."
    ), "Spoken narration for the example page")
    pages.append(
        Page(
            id=f"{ch.id}-p4",
            title="Real-World Example",
            blocks=[
                Block(type="heading", text=f"{title} in Action"),
                Block(type="paragraph", text=(
                    f"Let's see {title_lc} applied in a realistic situation. This example "
                    f"is based on common scenarios at {company}. Pay attention to the "
                    "decisions being made and think about what you would do in the "
                    "same situation."
                )),
                Block(type="image", asset=example_img,
                      text=f"Realistic workplace scene: {title_lc} at {company}"),
                interaction_block,
                Block(type="callout", text=(
                    f"Remember: the goal is not perfection on your first try. It's about "
                    f"building the habit of applying {title_lc} consistently and asking "
                    "for help when you need it."
                )),
                Block(type="audio", asset=example_audio, text=(
                    f"Now let's see {title_lc} in action. The interactive exercise on "
                    "this page puts you in a realistic scenario. Try it out — there is "
                    "no wrong answer at this stage, just practice."
                )),
            ],
        )
    )

    # ── Page 5: Practice with secondary interaction ───────────────────────
    practice_audio = _next_audio()
    secondary_type = (
        interactions[1] if len(interactions) > 1
        else _INTERACTION_ROTATION[(idx + 3) % len(_INTERACTION_ROTATION)]
    )
    secondary_block = _make_interaction_block(secondary_type, title, title_lc, key_points)
    _track_asset(practice_audio, "audio", (
        f"Time for some more practice with {title_lc}. This exercise focuses on "
        "reinforcing what you have learned so far. Take your time and think through "
        "each option carefully."
    ), "Spoken narration for the practice page")
    pages.append(
        Page(
            id=f"{ch.id}-p5",
            title="Practice & Apply",
            blocks=[
                Block(type="heading", text=f"Practise {title}"),
                Block(type="paragraph", text=(
                    f"Now it's your turn to practise. The exercise below tests your "
                    f"understanding of {title_lc} in a different way. This is about "
                    "reinforcing the concepts you have learned, not memorising them. "
                    "Think through each option carefully."
                )),
                secondary_block,
                Block(type="paragraph", text=(
                    f"After completing this exercise, think about one concrete situation "
                    f"from your own work where {title_lc} applies. Having a personal "
                    "example ready will help you remember these concepts long-term."
                )),
                Block(type="callout", text=(
                    f"Pro tip: Discuss {title_lc} with a colleague this week. Teaching "
                    "someone else is one of the best ways to solidify your understanding."
                )),
                Block(type="audio", asset=practice_audio, text=(
                    f"Time for more practice with {title_lc}. This exercise reinforces "
                    "what you have learned. Take your time and think through each option."
                )),
            ],
        )
    )

    # ── Optional: Conversation page (only if dialogue_appropriate) ────────
    if ch.dialogue_appropriate:
        convo_audio_links = [f"/resources/audio/{idx:02d}-c{n}" for n in range(1, 7)]
        turns_data = [
            (
                "mentor",
                f"I noticed you have been looking into {title_lc}."
                " How is it going?",
            ),
            (
                "you",
                "Pretty well. I understand the basics, but I'm"
                " not sure how to handle tricky situations.",
            ),
            (
                "mentor",
                "That's completely normal. The key is to always"
                " check the guidelines first. What specifically"
                " are you unsure about?",
            ),
            (
                "you",
                "Mainly when to escalate versus handling it"
                " myself.",
            ),
            (
                "mentor",
                "Good question. If you are unsure, it is always"
                " better to ask. There is no penalty for"
                " checking, but there can be consequences for"
                " guessing.",
            ),
            (
                "you",
                "That makes sense. I'll make sure to check first"
                " and ask when I'm uncertain.",
            ),
        ]
        for link, (_, text) in zip(convo_audio_links, turns_data):
            _track_asset(
                link, "audio", text,
                "Conversation line narration",
            )
        convo_page_id = f"{ch.id}-p{len(pages) + 1}"
        pages.append(
            Page(
                id=convo_page_id,
                title="In Conversation",
                blocks=[
                    Block(type="heading", text=f"Talking About {title}"),
                    Block(type="paragraph", text=(
                        f"Let's see how a conversation about {title_lc} might play out "
                        "between a new team member and their mentor. Click through each "
                        "speech bubble to follow the dialogue."
                    )),
                    Block(
                        type="conversation",
                        data={
                            "personas": [
                                {
                                    "id": "mentor",
                                    "name": "Alex",
                                    "role": "Team Lead",
                                    "side": "left",
                                    "avatar": "f-3",
                                },
                                {
                                    "id": "you",
                                    "name": "Jordan",
                                    "role": "New team member",
                                    "side": "right",
                                    "avatar": "m-4",
                                },
                            ],
                            "turns": [
                                {"persona": pid, "text": text, "audio": link}
                                for link, (pid, text) in zip(convo_audio_links, turns_data)
                            ],
                        },
                    ),
                    Block(type="callout", text=(
                        "Notice how Alex encourages checking the guidelines rather than "
                        "guessing. This is the standard approach — always verify first."
                    )),
                ],
            )
        )

    # ── Recap Page ────────────────────────────────────────────────────────
    recap_audio = _next_audio()
    _track_asset(recap_audio, "audio", (
        f"That wraps up {title}. Let's quickly recap the key takeaways. "
        f"{title} is a core part of how {company} operates. "
        + " ".join(kp_display[:3])
        + ". Consistency matters more than perfection. "
        "Now take the knowledge check to continue to the next chapter."
    ), "Spoken narration for the recap page")
    recap_page_id = f"{ch.id}-p{len(pages) + 1}"
    pages.append(
        Page(
            id=recap_page_id,
            title="Recap & Key Takeaways",
            blocks=[
                Block(type="heading", text=f"{title}: Key Takeaways"),
                Block(type="paragraph", text=(
                    f"Let's recap what you have learned about {title_lc}. These are the "
                    "essential points to remember as you move forward."
                )),
                Block(type="list", items=[
                    f"{title} is a core part of how {company} operates",
                    (
                        f"Key principle: {kp_display[0].lower()}"
                        if kp_display
                        else "Understand the fundamentals"
                    ),
                    "Follow the process: prepare, execute, review",
                    "Ask for help when you are unsure — checking is always better than guessing",
                    "Consistency matters more than perfection",
                ]),
                Block(type="callout", text=(
                    "You are now ready for the knowledge check. You need to score at "
                    "least 80% to unlock the next chapter. You can retry if needed — "
                    "review the pages above if you want to refresh your memory first."
                )),
                Block(type="audio", asset=recap_audio, text=(
                    f"That wraps up {title}. Remember the key takeaways: {title} is "
                    f"central to how {company} works. Follow the process, ask when "
                    "unsure, and aim for consistency. Now take the knowledge check."
                )),
            ],
        )
    )

    return pages, assets



def fallback_lastenheft(plan: CoursePlan, company_name: str, primary_color: str) -> Lastenheft:
    chapters: list[SpecChapter] = []
    manifest: list[AssetSpec] = []
    for i, ch in enumerate(plan.chapters):
        pages, assets = _chapter_pages(ch, i, company_name)
        manifest.extend(assets)
        kp = ch.key_points or [ch.title]
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
                            options=(kp[:1])
                            + ["Ignore the guidelines", "Skip onboarding", "Guess"],
                            answerIndex=0,
                            explanation="Refer to the key points covered in this chapter.",
                        ),
                        QuizQuestion(
                            question=(
                                f"What should you do if you are unsure about "
                                f"{ch.title.lower()}?"
                            ),
                            options=[
                                "Check the guidelines and ask your team",
                                "Guess and hope for the best",
                                "Ignore it and move on",
                                "Wait until someone tells you",
                            ],
                            answerIndex=0,
                            explanation=(
                                "Always check the official guidelines and ask your team "
                                "when you are uncertain."
                            ),
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
