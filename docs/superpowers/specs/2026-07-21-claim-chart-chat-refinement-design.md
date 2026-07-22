# Lumenci Assistant — Claim Chart Chat Refinement: PRD

## Overview

Lumenci Assistant is an AI-powered chat interface for patent infringement analysis. Patent analysts upload claim charts (tables mapping patent claim elements to accused product features with supporting evidence), then use conversational AI to refine them — improving accuracy and strengthening evidence — before exporting to Word for legal proceedings. This document scopes and designs the **AI chat-based claim chart refinement experience**: the interaction where an analyst reviews an already-uploaded chart and iteratively improves it through conversation with the AI.

**Primary persona:** Expert patent attorney/analyst. Fluent in claim construction and what legally counts as "strong evidence." High-stakes output (feeds litigation filings). Wants speed, full control, and an audit trail — not hand-holding.

## Problem Statement

Patent analysts building infringement claim charts face two compounding problems: (1) constructing charts is slow, requiring manual cross-referencing between patent claims and scattered product documentation, and (2) AI-assisted first-draft reasoning is often inconsistent in quality — some mappings are well-supported, others are weak inferences stated with unwarranted confidence — which is risky when the output feeds directly into legal proceedings. Lumenci Assistant's chat interface exists to let an analyst rapidly audit, challenge, and strengthen an already-drafted claim chart through natural conversation, without silently trusting or having to manually rewrite AI output.

## User Stories

- As a patent analyst, I want to upload a claim chart and related product documentation, in whatever order and batches I want, so the AI has the same source material I'm working from.
- As a patent analyst, I want to explicitly trigger the AI's initial analysis once I've uploaded what I need, rather than have it fire automatically the moment a file lands, so I control when that pass runs.
- As a patent analyst, I want to draft and edit the AI's system prompt myself — at setup and later via a settings button in the chat window — so I have direct, ongoing control over its behavioral stance, not just a fixed set of presets.
- As a patent analyst, I want to see, at a glance, which claim elements have weak evidentiary support so I know where to focus my time.
- As a patent analyst, I want to ask the AI to strengthen a specific row's reasoning or evidence by referencing it unambiguously, without retyping the full claim language.
- As a patent analyst, I want to review the AI's proposed change before it touches the chart, so I retain full control over what goes into a legal document.
- As a patent analyst, I want to iteratively steer a proposal ("shorter," "cite the doc directly") until it's right, reviewing and accepting each revision as it comes back rather than retyping context each time.
- As a patent analyst, I want the AI to tell me upfront which rows have weak evidentiary support, without auto-drafting changes I didn't ask for, so I stay in control of what gets worked on.
- As a patent analyst, I want to undo the most recent change to a row so I can back out of an edit I didn't want.
- As a patent analyst, I want to export the refined chart to Word so I can use it directly in legal filings.

## Core Features (MVP Scope)

**In scope:**
- A new session is created automatically when the analyst starts; every upload, the chart, evidence, chat history, and export are scoped to that session (see Key Decisions). One session = one chart, start to finish; a new chart means a new session.
- Three separate, explicit upload/analysis actions rather than one combined upload step:
  - **Upload Claim Chart** — a 3-column CSV (Patent Claim Element / Accused Product Feature (Evidence) / AI Reasoning), pre-populated by the analyst's prior process. Real text ingestion, no complex parsing.
  - **Upload Evidence** — one or more `.txt` files and/or a link; repeatable, so the analyst can add sources in multiple batches before analyzing.
  - **Generate** — an explicit action the analyst takes once they've uploaded what they need (chart required, evidence optional), which triggers the AI's initial confidence-tier classification pass and posts the opening chat message. Nothing runs automatically the moment a file is uploaded.
- Setup step: a blank text editor where the analyst drafts the system prompt in their own words — no preset toggles, nothing prewritten. Available any time before clicking Generate. This text is appended to a fixed hidden baseline prompt (see Key Decisions) to form the full system prompt sent with every LLM call.
- Settings button in the chat window lets the analyst reopen and edit this system prompt at any point during the session, not just at setup. Edits apply to all subsequent turns; existing chat history and chart state are untouched. No prompt files, no multi-document prompt management.
- Split-pane layout: claim chart (left) always visible alongside the chat (right), so chart state and conversation are visible simultaneously
- 3-column claim chart display (Patent Claim Element / Accused Product Feature (Evidence) / AI Reasoning) with a per-row confidence badge (Strong / Moderate / Weak), AI-applied rubric based on evidence directness. The initial classification pass only assigns the confidence tier — it reads the analyst's pre-populated evidence/reasoning columns rather than rewriting them.
- Once Generate completes, the AI posts an unprompted opening chat message identifying which rows are Weak/Moderate — it flags, it does not pre-draft fixes for them unprompted; the analyst initiates all refinement requests
- Single continuous chat thread for the session
- Analyst can send a chat message with no row selected; the AI uses its full chart context to determine which row is meant. Clicking a row first inserts an `@Row` chip as a convenience for speed/precision, not a requirement. Either way, if the AI isn't confident which row is meant, it asks a clarifying question rather than guessing.
- AI proposes changes in chat; the proposal is also reflected inline in the affected chart cell in a pending visual state, with inline Accept / Modify / Reject controls mirroring the chat-based flow
- Every proposal — first or revised — requires explicit analyst Accept before it touches the chart; there is no auto-apply. "Modify" inserts that row's `@Row` chip into chat so the analyst can give feedback, and the AI's revised proposal goes back into the same pending state, requiring another explicit Accept.
- Updated chart re-renders showing changes as they're accepted/applied. Accept commits the evidence, reasoning, and confidence tier together as one unit — a proposal never updates the evidence text while leaving a stale reasoning/confidence badge behind.
- Single-step undo per row, stored in SQLite: each row retains its current (evidence, reasoning, confidence) and the immediately preceding (evidence, reasoning, confidence) as one atomic unit — undoing never reverts the evidence text without also reverting the reasoning/badge that went with it. A persistent Undo control next to every row is enabled only when a prior applied value exists; clicking it shows a confirmation prompt before reverting. Undoing again with no prior value stored is a no-op with a clear message.
- When the AI cannot find supporting evidence, it asks in-chat for another document upload or a URL (via the same repeatable Upload Evidence action); backend performs a real minimal fetch (HTTP GET + HTML-to-text extraction, single page, no crawling/JS rendering) and treats the result as a new evidence source
- A dedicated flag icon next to every row (separate from Accept/Reject/Modify/Undo) lets the analyst mark AI-proposed evidence as factually wrong. Clicking it deterministically triggers a re-scan of that session's full evidence pool for that claim element — the AI itself does the re-reading and finding, but the *trigger* is deterministic: it fires on the flag click, not on the AI detecting "wrong"/"incorrect" language in chat, which could be missed. After the flag click, that row's `@Row` chip appears in chat so the analyst can describe the issue; the AI's corrected response must quote the exact source line it found, and re-enters the normal pending/Accept flow like any other proposal (fallback: treat as a normal "modify" with no re-grounding step, if build time is constrained)
- Export to Word (.docx) of current chart state — real, working export
- Session-scoped state, no auth; persistence is limited to the current session's chart, evidence pool, chat history, and single-step undo data (see Key Decisions) — no saved/resumable list of past sessions

**Out of scope (with rationale):**
- Claim chart *generation* from scratch — chart arrives pre-populated via upload; chat only refines existing rows (confirmed by the assignment's own framing: "upload claim charts... then use chat to refine them")
- A saved/resumable dashboard of past sessions — a session is an isolation boundary for one chart's lifecycle, not a persisted, revisitable project
- Complex file parsing (PDF, DOCX ingestion, OCR) — plain text only
- Authentication/user accounts
- Multi-user collaboration (e.g., attorney-reviews-paralegal workflow) — single-analyst session only
- Per-row separate chat panels — single thread with row-anchoring instead

## Key Decisions

1. **Human-in-the-loop gating on every AI write, no auto-apply tier.** Rather than "AI freely edits after the analyst starts steering" (fast but risky for legal content), every proposal — the first unprompted one and every subsequent revision after a "modify" — lands in the same pending state and requires an explicit Accept before it touches the chart. This prioritizes legal-safety (nothing an analyst hasn't reviewed lands unreviewed, ever) over saving a click during active steering; Modify itself stays fast since it just re-opens the chat loop for that row.
2. **Row disambiguation via AI inference over full chart context, with UI-assisted mention as a shortcut.** The AI has the full chart as context and resolves which row a message refers to itself; clicking a row is a convenience that inserts an explicit `@Row` chip for speed/precision, not a requirement to target a row at all. If the AI isn't confident which row is meant, it asks a clarifying question instead of guessing — removing the real failure mode (silently editing the wrong claim element) without forcing a click on every message.
3. **Confidence tiers (Strong/Moderate/Weak) surfaced explicitly, not left implicit in reasoning prose.** LLMs state weak inferences with the same confident tone as strong ones. Making the AI self-apply and visually surface a confidence rubric turns an implicit risk into a scannable triage signal, directly shaping how analysts prioritize their limited review time.
4. **Single-step undo, not full revision history — and it covers the whole row, not just the evidence cell.** Rather than retaining every prior version of a row, each row keeps only its current (evidence, reasoning, confidence) and the immediately preceding one, persisted in SQLite as one atomic unit. Committing all three together on Accept/Undo prevents a real correctness bug: reverting evidence text alone while leaving the reasoning/badge pointed at the newer (undone) state. This preserves the core safety-net property — no edit is unrecoverably lost the moment after it's applied — without building a multi-version history UI, which is more than the assignment's scope requires.
5. **Freeform, analyst-authored system prompt over fixed presets, layered on a hidden baseline.** A true system prompt is just text attached to every turn — so rather than offering fixed preset toggles, the analyst writes it themselves in a blank editor (available at setup and reopenable via a settings button in the chat window). To keep the product's core mechanics (confidence tiers, row-targeting, evidence-quoting on corrections) working even if the analyst writes nothing, this text is appended to a fixed hidden baseline prompt rather than replacing it outright. Editing the prompt mid-session applies to subsequent turns only — chat history and chart state are left untouched, since a system prompt is context for future turns, not part of the conversation record.
6. **Session-scoped isolation instead of one implicit global chart.** Rather than assuming a single chart lives in the database for the app's whole lifetime, every upload/chart/evidence/chat/undo record is scoped by an explicit `session_id`, created automatically the moment the analyst starts. This costs almost nothing over the implicit-singleton approach but removes an awkward edge case (what happens if the analyst tries to start a second chart) by making "start a new chart" simply mean "start a new session," with no auth or saved-session list required.
7. **Explicit Generate step instead of analysis firing automatically on upload.** Splitting upload into three actions — Upload Claim Chart, Upload Evidence (repeatable), Generate — instead of one combined upload call gives the analyst control over when the (potentially slow, local-model-driven) initial classification pass runs, and lets them add evidence in multiple batches first rather than being forced to gather everything before a single upload click.

## Edge Cases

These three edge cases are required flowchart branches in the user flow diagram and correspond to concrete failure modes of using an LLM for legal evidentiary analysis:

1. **AI gives wrong evidence (analyst flags it, not chat-detected).** The AI misquotes or fabricates evidence text. The analyst clicks a dedicated flag icon next to the row — separate from Accept/Reject/Modify/Undo — which deterministically triggers a re-scan of that session's full evidence pool for that claim element; the *trigger* is deterministic (it always fires on the flag click), but the matching itself is the AI re-reading the evidence text and finding the right line, not a keyword algorithm. This does not depend on the AI detecting "wrong"/"incorrect" language in chat, since that detection could be missed and silently skip the safeguard. After the flag click, that row's `@Row` chip appears in chat so the analyst can describe the issue. The AI's corrected response must include the exact quoted source line it found, so the analyst can visually verify the correction against the real source rather than trusting AI prose. If no supporting line exists anywhere in the pool, this converges with edge case 3 below (AI cannot find evidence) rather than fabricating a correction. The correction re-enters the normal pending flow and requires an explicit Accept like any other proposal, with a visible diff. *Fallback if under time pressure:* treat this identically to a normal "modify" instruction, without the re-grounding step.
2. **User wants to undo a previous refinement.** Every applied change to a row overwrites that row's stored "previous (evidence, reasoning, confidence)" slot (in SQLite) as one atomic unit. A persistent Undo control next to the row is enabled whenever a prior applied value exists. Clicking it shows a confirmation prompt; confirming reverts the row to that prior (evidence, reasoning, confidence) together and clears the undo slot. A second consecutive undo on the same row is a no-op with a clear message, not an error, since only one prior version is retained.
3. **AI cannot find evidence.** When the AI has no basis in the uploaded documents to support or strengthen a claim element, it says so explicitly in chat and asks the analyst for more source material — either another document upload or a URL. If given a URL, the backend performs a real (but minimal) fetch: an HTTP GET followed by HTML-to-text extraction of that single page (no crawling, no JS rendering). The extracted text is then treated as an additional evidence source for that row, same as an uploaded document.

## Acceptance Criteria

- Given the analyst starts the app, a new session is created automatically and every subsequent action is scoped to it
- Given a session with a claim chart uploaded, the analyst can upload evidence files/links multiple times, in any batch size, before clicking Generate
- Given a session with a claim chart uploaded, clicking Generate (with or without evidence uploaded) displays a 3-column chart with a confidence badge on every row, without regenerating the analyst's pre-populated evidence/reasoning text
- Given no claim chart uploaded yet in a session, Upload Evidence and Generate are both unavailable/rejected with a clear message (order enforced)
- Given the setup step, the analyst can draft a freeform system prompt any time before Generate, with no prewritten/preset content
- Given a session in progress, the analyst can open the settings button in the chat window, edit the system prompt, and have it apply starting with the next turn, without altering existing chat history or chart state
- Given a chat message referencing a row via the `@Row` chip, the AI's response addresses that row specifically and does not modify any other row
- Given a chat message with no row selected and an ambiguous referent, the AI asks a clarifying question instead of guessing
- Given any AI proposal — first or revised — the chart is not modified until the analyst explicitly accepts
- Given an analyst "modify" instruction following a proposal, the AI's revised proposal re-enters the same pending state on that row's cell, requiring another explicit Accept before it touches the chart
- Given an accepted or undone change, the row's evidence, reasoning, and confidence badge update or revert together as one unit — never independently
- Given a rejected or undone change, the chart reverts to its prior state exactly
- Given a row with an applied change, clicking Undo shows a confirmation prompt, and confirming reverts the row to its immediately prior (evidence, reasoning, confidence)
- Given a row that was just undone (or never changed), the Undo control is disabled/a further undo attempt is a no-op with a clear message
- Given an analyst clicks the dedicated flag icon on a row (not a chat message) to mark its evidence as factually wrong, the session's evidence pool is re-scanned and the AI's corrected response quotes the exact source line found, then re-enters the normal pending flow requiring explicit Accept
- Given the AI has no supporting evidence for a row (whether during a normal proposal or a flag re-scan), it asks the analyst in-chat for another document or a URL rather than fabricating a mapping
- Given a URL is provided in response to that request, the backend fetches and extracts its text content and adds it to the session's evidence pool
- Given a chart in any state after Generate has run, clicking Export produces a downloadable .docx reflecting the exact current chart content
- Given no claim chart has been uploaded yet, the chat and chart views are inaccessible/empty (no crash, clear empty state)

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

- **Backend:** small server, holds LLM API key server-side, handles LLM calls, URL fetch/extraction, DB access, and .docx generation (e.g., `python-docx` or Node `docx`); all state scoped by an explicit `session_id`
- **Frontend:** React app — Upload Claim Chart / Upload Evidence / Generate as three separate actions, setup step (freeform system prompt editor), split-pane chart (left) + chat (right) with a settings button for reopening/editing the system prompt mid-session, inline pending-proposal controls on chart cells
- **LLM:** used for (a) initial confidence-tier classification per row on Generate, (b) opening chat message flagging weak rows, (c) chat-based refinement proposals, (d) row-reference disambiguation clarifying questions, (e) re-grounded evidence corrections; every call sends the fixed hidden baseline prompt plus the analyst's current freeform system prompt text
- **State:** SQLite database storing sessions and, per session, its chart rows (each with current (evidence, reasoning, confidence) plus one previous triplet for single-step undo), evidence pool, and chat history; no auth, no cross-session save/resume
- **Export:** backend generates a .docx from current chart state on demand, returned to frontend as a file download

## Bonus-Point Coverage (for reviewer visibility)

- **LLM limitations in chat contexts:** addressed via confidence tiers (surfacing inferential vs. direct evidence), row-reference clarifying questions when the AI isn't confident (removing silent-wrong-row-edit risk without forcing a click on every message), and gated writes on every proposal (preventing unreviewed fabricated edits from silently landing).
- **Chat-specific quality evaluation:** confidence-tier shift per session, % proposals accepted without modification, analyst trust rating — proposed as concrete, measurable proxies for "is the chat actually improving legal analysis quality."
- **Human-in-the-loop conversational patterns:** every proposal (first and revised) always requires explicit Accept, reject/undo always available with confirmation on undo, AI asks rather than guesses on ambiguous referents, and evidence-correctness flagging is a deterministic UI action rather than relying on the AI to detect "wrong" language in chat.
- **Creative chat UX:** Slack-style `@Row` mention chip for anchoring chat to a specific claim element without a cluttered per-row chat panel; click-to-insert is a convenience layered on top of AI-side referent inference, not a requirement.
