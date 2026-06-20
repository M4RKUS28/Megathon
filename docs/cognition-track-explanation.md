# Cognition Track Explanation

CourseForge Devin is designed for the “Best Build with Devin” track by making Devin the system-of-record execution layer for course generation.

The product uses Devin as infrastructure:

- Approval triggers Devin automatically through the Devin API.
- Implementation, asset integration, and QA are separate Devin phases.
- The UI shows Devin sessions, statuses, prompts, transcripts, branches, commits, PRs, and QA outputs.
- The Evidence Ledger makes the autonomous workload visible to judges.
- The production path refuses to simulate Devin execution.

The local app handles product orchestration, planning, asset mapping, and reporting. Devin handles the load-bearing code generation and QA work in the configured repository.
