# Lumenci Assistant — Claim Chart Chat Refinement: PRD

## Overview

Lumenci Assistant is an AI-powered chat interface for patent infringement analysis. Patent analysts upload claim charts (tables mapping patent claim elements to accused product features with supporting evidence), then use conversational AI to refine them — improving accuracy and strengthening evidence — before exporting to Word for legal proceedings. This document scopes and designs the **AI chat-based claim chart refinement experience**: the interaction where an analyst reviews an already-uploaded chart and iteratively improves it through conversation with the AI.

**Primary persona:** Expert patent attorney/analyst. Fluent in claim construction and what legally counts as "strong evidence." High-stakes output (feeds litigation filings). Wants speed, full control, and an audit trail — not hand-holding.

## Problem Statement

Patent analysts building infringement claim charts face two compounding problems: (1) constructing charts is slow, requiring manual cross-referencing between patent claims and scattered product documentation, and (2) AI-assisted first-draft reasoning is often inconsistent in quality — some mappings are well-supported, others are weak inferences stated with unwarranted confidence — which is risky when the output feeds directly into legal proceedings. Lumenci Assistant's chat interface exists to let an analyst rapidly audit, challenge, and strengthen an already-drafted claim chart through natural conversation, without silently trusting or having to manually rewrite AI output.

## User Stories

- As a patent analyst, I want to upload a claim chart and related product documentation so the AI has the same source material I'm working from.
- As a patent analyst, I want to set behavioral instructions for the AI (via presets and/or free text) so its refinement style matches how conservative or aggressive I want the analysis to be.
- As a patent analyst, I want to see, at a glance, which claim elements have weak evidentiary support so I know where to focus my time.
- As a patent analyst, I want to ask the AI to strengthen a specific row's reasoning or evidence by referencing it unambiguously, without retyping the full claim language.
- As a patent analyst, I want to review the AI's proposed change before it touches the chart, so I retain full control over what goes into a legal document.
- As a patent analyst, I want to iteratively steer a proposal ("shorter," "cite the doc directly") until it's right, without excessive re-confirmation friction once I'm actively directing the edit.
- As a patent analyst, I want to export the refined chart to Word so I can use it directly in legal filings.

## Core Features (MVP Scope)

**In scope:**
- Upload claim chart (.txt/.csv) + product docs (.txt) — real text ingestion, no complex parsing
- Setup step: preset instruction toggles (e.g., "flag inferential evidence," "prioritize technical docs over marketing copy," "be conservative") + optional free-text additional instructions
- 3-column claim chart display (Patent Claim Element / Accused Product Feature (Evidence) / AI Reasoning) with a per-row confidence badge (Strong / Moderate / Weak), AI-applied rubric based on evidence directness
- Single continuous chat thread for the session
- Click-a-row → inserts `@Row` reference chip into chat input for unambiguous targeting; AI asks a clarifying question if referent is ambiguous
- AI proposes changes in chat; first unprompted proposal requires explicit analyst accept before touching the chart; once analyst issues a "modify" instruction, subsequent revisions apply directly (visibly, reversible via reject/undo)
- Updated chart re-renders showing changes as they're accepted/applied
- Export to Word (.docx) of current chart state — real, working export
- Single chart per session, no persistence/save-and-resume, no auth

**Out of scope (with rationale):**
- Claim chart *generation* from scratch — chart arrives pre-populated via upload; chat only refines existing rows (confirmed by the assignment's own framing: "upload claim charts... then use chat to refine them")
- Multi-chart session management / history / save-load
- Complex file parsing (PDF, DOCX ingestion, OCR) — plain text only
- Authentication/user accounts
- Multi-user collaboration (e.g., attorney-reviews-paralegal workflow) — single-analyst session only
- Per-row separate chat panels — single thread with row-anchoring instead

## Key Decisions

1. **Human-in-the-loop gating on AI writes, with a graduated trust model.** Rather than either "AI never touches the chart without accept" (safe but tedious) or "AI freely edits, analyst reverts" (fast but risky for legal content), we gate only the *first unprompted* AI proposal — once the analyst is actively directing revisions via "modify," that instruction itself is the permission, and further changes apply directly with visible diffs and easy undo. This balances legal-safety (nothing an analyst hasn't reviewed lands unreviewed) against conversational friction (no redundant re-confirmation once the analyst is already steering).
2. **Row disambiguation via UI-assisted mention, not AI inference.** Instead of trusting the LLM to guess which chart row a vague message refers to (a known LLM weak point — ambiguous references risk silently editing the wrong claim element), row targeting is resolved by the UI: clicking a row inserts an explicit `@Row` chip. This keeps one shared conversational thread (context persists across rows) while removing a real failure mode.
3. **Confidence tiers (Strong/Moderate/Weak) surfaced explicitly, not left implicit in reasoning prose.** LLMs state weak inferences with the same confident tone as strong ones. Making the AI self-apply and visually surface a confidence rubric turns an implicit risk into a scannable triage signal, directly shaping how analysts prioritize their limited review time.

## Acceptance Criteria

- Given a valid .txt/.csv claim chart and product doc, when uploaded, the app displays a 3-column chart with a confidence badge on every row
- Given the setup step, the analyst can select preset instruction toggles and/or enter free-text instructions before entering the chat
- Given a chat message referencing a row via the `@Row` chip, the AI's response addresses that row specifically and does not modify any other row
- Given a chat message with no row selected and an ambiguous referent, the AI asks a clarifying question instead of guessing
- Given an AI's first unprompted proposal, the chart is not modified until the analyst explicitly accepts
- Given an analyst "modify" instruction following a proposal, the AI's next revision is applied directly to the chart and is visibly diffed/marked as changed
- Given a rejected or undone change, the chart reverts to its prior state exactly
- Given a chart in any state, clicking Export produces a downloadable .docx reflecting the exact current chart content
- Given no upload has occurred, the chat and chart views are inaccessible/empty (no crash, clear empty state)

## Success Metrics

- Avg. time to refine a full chart via chat vs. manual editing baseline
- % of AI-proposed suggestions accepted as-is (first proposal) vs. requiring modification
- % of chart rows upgraded in confidence tier (Weak→Moderate/Strong) per session
- Analyst-reported trust/confidence in exported output (post-session rating)
- Export completion rate (% of sessions that reach a successful Export)
- Chat feature adoption rate (% of chart sessions where chat is used at all)
- Avg. messages per session
- Drop-off rate across the upload → chat → export funnel

## Technical Approach (Prototype)

- **Backend:** small server, holds LLM API key server-side, handles LLM calls and .docx generation (e.g., `python-docx` or Node `docx`)
- **Frontend:** React app — upload UI, setup/instructions step, chart table, chat panel
- **LLM:** used for (a) initial confidence-tier classification per row on upload, (b) chat-based refinement proposals, (c) row-reference disambiguation clarifying questions
- **State:** in-memory/session only, no database, no auth
- **Export:** backend generates a .docx from current chart state on demand, returned to frontend as a file download

## Bonus-Point Coverage (for reviewer visibility)

- **LLM limitations in chat contexts:** addressed via confidence tiers (surfacing inferential vs. direct evidence), UI-anchored row references (removing ambiguous-referent guessing), and gated writes (preventing unreviewed fabricated edits from silently landing).
- **Chat-specific quality evaluation:** confidence-tier shift per session, % proposals accepted without modification, analyst trust rating — proposed as concrete, measurable proxies for "is the chat actually improving legal analysis quality."
- **Human-in-the-loop conversational patterns:** graduated accept-gate (first proposal always reviewed; explicit "modify" instruction as ongoing permission), reject/undo always available, AI asks rather than guesses on ambiguous referents.
- **Creative chat UX:** Slack-style `@Row` mention chip for anchoring chat to a specific claim element without a cluttered per-row chat panel.
