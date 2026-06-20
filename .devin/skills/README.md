# Frontend Design Skills

Agent Skills installed for frontend design work on the Nexora frontend
(React 18 + Vite + Tailwind CSS v4 + Mantine).

Skills are auto-discovered by the agent and can also be invoked manually with
`/<skill-name>`. Each skill lives in its own folder with a `SKILL.md` plus any
supporting files.

## Installed skills

| Skill | Invoke | What it does |
| --- | --- | --- |
| `frontend-design` | `/frontend-design` | Aesthetic direction, typography, layout, and copy guidance for building/reshaping UI without generic "AI slop" defaults. Primary skill for this project. |
| `webapp-testing` | `/webapp-testing` | Playwright toolkit to verify UI, debug behavior, capture screenshots, and read browser logs. Pairs with `frontend-design`'s screenshot-and-self-critique workflow. Requires Python + Playwright. |
| `theme-factory` | `/theme-factory` | 10 preset color/font theme systems (plus on-the-fly theme generation). See `theme-factory/theme-showcase.pdf`. |
| `web-artifacts-builder` | `/web-artifacts-builder` | React + Tailwind + shadcn/ui patterns for complex HTML artifacts. Note: this project uses Mantine, not shadcn/ui, so use selectively for architecture/patterns. |

## Source & licensing

Vendored from Anthropic's official skills repository:

- Repo: https://github.com/anthropics/skills
- Commit: `57546260929473d4e0d1c1bb75297be2fdfa1949` (2026-06-09)

Each skill retains its original `LICENSE.txt`. Refer to those files for terms.

## Updating

To update a skill, re-copy its folder from a fresh clone of
`anthropics/skills` and bump the commit reference above.
