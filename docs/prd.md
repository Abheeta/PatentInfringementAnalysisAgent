# Lumenci Assistant — Product Requirements Document

## Problem Statement

Patent infringement claim charts — mapping each claim element to accused-product
evidence — are built and defended by hand today. An analyst reads a claim
element, searches product specs/teardowns/manuals for supporting evidence,
writes a reasoning note, and judges how strong that evidence is, one row at a
time, across every claim in the patent. It's slow, and the judgment work
(is this evidence *directly* supporting, merely implied, or absent?) is
repeated fresh for every row with no assistance.

Lumenci Assistant takes a first pass at that judgment automatically: given a
claim chart and a pool of evidence documents, it classifies each row's
confidence (Strong/Moderate/Weak), and lets the analyst interrogate,
correct, and refine that first pass conversationally — instead of
re-researching by hand — while keeping every claim chart cell under explicit
human control, since these charts become legal evidentiary work product and
nothing the AI proposes can land unreviewed.

## User Stories

- As a patent analyst, I want to upload a claim chart and my evidence
  documents once and get an initial Strong/Moderate/Weak classification for
  every row, so I don't start each row's analysis from a blank page.
- As a patent analyst, I want to ask the assistant about a specific row by
  clicking on it, so I don't have to re-describe which claim element I mean.
- As a patent analyst, I want to challenge a weak or moderate row and have
  the assistant search the evidence pool for a better citation, so I can
  strengthen the chart without manually re-reading every document.
- As a patent analyst, I want every AI-proposed change shown as a pending
  edit I can accept, reject, or ask to be revised, so nothing enters the
  chart without my explicit sign-off.
- As a patent analyst, I want to flag a row I believe is wrong and explain
  why, and have the assistant re-scan the evidence and quote it verbatim,
  so corrections are traceable back to a real source, not a paraphrase.
- As a patent analyst, I want to undo the last accepted change to a row,
  so a bad accept doesn't require me to manually re-enter the old value.
- As a patent analyst, I want to add more evidence mid-session and have the
  assistant retry a row that previously had no supporting evidence, so
  new documents don't require restarting the whole analysis.
- As a patent analyst, I want to export the chart to Word at any point after
  generation, so I can share or file the current state without waiting on
  every pending proposal to be resolved first.
- As a patent analyst, I want to add my own standing instructions (e.g. "be
  conservative about Strong ratings"), so the assistant's judgment matches
  how my team actually grades evidence.

## Core Features

**In MVP scope**
- Chart upload (3-column CSV: claim element / product feature / AI reasoning)
  and repeatable evidence upload (`.txt` files and/or URLs).
- One-time initial classification pass over the whole chart (Strong/Moderate/
  Weak + a reasoning note per row), seeding a deterministic opening chat
  message summarizing what needs attention.
- Freeform chat, with or without an explicit row reference (`@Row` chip):
  - **Answer** — the assistant answers a question directly from the chart
    and evidence pool, with no chart mutation.
  - **Propose** — the assistant proposes a specific row's new evidence text,
    reasoning, and confidence tier, grounded in the evidence pool.
  - **Clarify** — if a message seems row-specific but the row is ambiguous,
    the assistant asks which row before doing anything else.
  - **No evidence found** — if no row proposal can be grounded in the
    evidence pool, the assistant says so and asks for more evidence, instead
    of guessing.
- Explicit Accept / Reject / Modify on every proposal; nothing is written to
  a row's live values without an explicit Accept. Modify re-enters the same
  chat flow with the row re-attached, so a revised proposal goes through the
  same gate again.
- Single-step Undo per row, back to the last accepted value.
- Flag flow: marks a row as under re-review and requires the assistant's
  next correction on that row to be an **exact verbatim quote** from the
  evidence pool (or an explicit "no evidence found"), a stricter grounding
  bar than a normal chat proposal.
- Analyst-editable freeform system prompt, layered on top of (never
  overriding) a hidden baseline instruction that enforces no-fabrication,
  traceability, and structured output.
- Export to `.docx` at any time after generation, always reflecting the
  chart's current on-screen state (pending cells export as their current,
  unaccepted value).

**Out of scope for MVP**
- User accounts / authentication — a session is an isolation boundary, not
  an identity.
- Multi-analyst collaboration on the same session (no concurrent-edit
  conflict handling, no comments/mentions between people).
- Multi-page or JS-rendered URL evidence fetching (single-page HTTP GET +
  HTML-to-text only; no crawling).
- File formats beyond CSV (chart) and `.txt`/URL (evidence) — e.g. PDF, DOCX,
  or image evidence ingestion.
- Chat history summarization or long-term memory across sessions — each
  session's context is assembled by filtering the current session's own
  data, not compressed or carried into other sessions.
- Retrieval/chunking over the evidence pool — full-stuffing only, scoped to
  prototype-scale charts (5–10 rows, small evidence docs).
- Multi-step autonomous agent behavior (e.g. the assistant independently
  re-searching the web, chaining multiple proposals without being asked).
- Editing the claim chart's claim-element column itself — only the evidence
  (`product_feature`), reasoning, and confidence are ever proposed/changed.

## Key Decisions

1. **Every chart mutation requires an explicit human Accept — the assistant
   can never write to a row's live values on its own.** This is a
   legal-evidentiary tool; an unreviewed AI edit landing silently in a claim
   chart is a worse failure mode than a slower workflow. Proposals sit in a
   `pending_*` state until Accept/Reject/Modify, and even the flag-flow's
   stricter verbatim-quote requirement still ends at a pending state, not a
   direct write. The one exception is the one-time initial classification
   pass, which sets `confidence` directly — that's a starting assumption,
   not a claim of fact about the analyst's chart, and every value it sets
   remains just as editable through the normal proposal flow afterward.

2. **No retrieval layer — the full evidence pool is sent on every relevant
   call.** Given confirmed prototype scale (5–10 row charts, small evidence
   documents) and a CPU-only local model where prefill time (not memory) is
   the real constraint, a retrieval/chunking layer would add complexity to
   solve a context-length problem this app doesn't actually have yet. This
   is an explicit choice to revisit if usage grows past prototype scale, not
   a permanent architectural stance.
3. **Local, small model; no agent framework.** The assistant runs on a small
   open model (Qwen 2.5) locally rather than a large hosted one, and is
   built with plain, straightforward logic rather than a heavyweight
   AI-agent framework. The assistant's job is a handful of well-defined
   conversational moves (classify, answer, propose, ask for clarification)
   — not open-ended autonomous planning.

4. **Two-layer system prompt: a fixed baseline, plus the analyst's own
   editable instructions on top.** Every AI call is guided by two layers,
   not one:
   - **Baseline (hidden, fixed).** A non-negotiable set of rules — never
     fabricate, only use what's actually in the evidence given, say so
     explicitly when the evidence doesn't support a confident answer, never
     invent row IDs or document names. This is the same for every analyst,
     every session, and isn't shown or editable — it's the floor the tool
     guarantees no matter who's using it.
   - **Analyst prompt (visible, editable).** Analysts can add their own
     standing instructions — e.g. "be conservative, only mark Strong if the
     wording nearly matches" — via Settings. This shapes tone, strictness,
     and emphasis, and persists for the session.

   The two layers are strictly additive, not equal-weight: the analyst's
   text can adjust how the assistant behaves within the rules, but can
   never turn off a rule.

   *Why this matters as a product decision:* different analysts/teams grade
   evidence differently, so a one-size-fits-all prompt would fight their
   judgment on borderline calls. But this is a legal-evidentiary tool —
   letting custom instructions weaken the no-fabrication guarantee would
   undermine the one thing that makes the tool trustworthy. Two layers get
   both: real per-analyst customization, with a floor that never moves.

## Acceptance Criteria

- Uploading a valid 3-column CSV creates one row per data row (header row
  excluded) with `claim_element`, `product_feature`, and `ai_reasoning`
  populated exactly as given; a CSV with any row not matching 3 columns is
  rejected with `malformed_csv` and no rows are created.
- Uploading evidence is possible before, during, or after chart upload, and
  can be called repeatedly; each call adds exactly one document (file or
  URL) to the pool without overwriting prior uploads.
- Clicking Generate exactly once succeeds and sets every row's `confidence`
  to one of `Strong`/`Moderate`/`Weak` (never null, never a fourth value); a
  second Generate call on the same session is rejected with
  `already_generated` and does not re-run classification.
- After Generate, the chat panel contains exactly one assistant message
  (the opening message) whose content lists every Weak/Moderate row, or a
  fixed all-Strong message if none exist.
- Sending a chat message with an explicit `row_id` never mutates any other
  row — a proposal, answer, or "no evidence found" reply from that turn is
  scoped only to the given row.
- Sending a chat message with no `row_id` that is genuinely ambiguous
  between two or more rows results in a clarifying question and zero chart
  mutation — not a guessed row.
- A proposal is never applied to a row's live values without a separate,
  explicit `accept` call; `reject` clears the pending state and leaves live
  values byte-for-byte unchanged; calling `accept`/`reject` with no pending
  proposal returns `no_pending_proposal` and changes nothing.
- Undo is only available immediately after an Accept, reverts the row to
  its exact pre-accept values, and is unavailable (`no_undo_available`) the
  second time in a row it's attempted without an intervening Accept.
- Flagging a row sets it into a state where the *next* correction proposal
  for that row is rejected (retried once, then converged to
  `no_evidence_found`) unless `pending_value` appears as an exact substring
  of the concatenated evidence pool; flagged state clears only when that
  `propose`-intent response completes, not when an `answer`-intent response
  is given.
- Export succeeds any time after Generate has run, regardless of pending
  proposals, and every pending (unaccepted) cell appears in the exported
  `.docx` using its current, unaccepted value.
- A `502 llm_unavailable` from any AI-backed endpoint leaves all chart and
  chat state exactly as it was before the call — no partial writes.

## Success Metrics

- **Proposal acceptance rate:** how often analysts Accept an AI proposal
  outright vs. Reject or Modify it — a good signal of whether the
  assistant's first answer is actually trustworthy.
- **Rows resolved without manual escalation:** how many Weak/Moderate rows
  get fixed through chat vs. how many the analyst gives up on and resolves
  by hand — shows whether the conversational flow is actually doing its job.
- **Undo rate:** how often analysts undo something they just accepted —
  a high rate would mean people are accepting proposals they don't really
  trust.
- **Sessions that reach Generate:** of the sessions created, how many
  actually get a chart uploaded, evidence uploaded, and Generate clicked —
  a basic signal that the upload flow isn't the thing tripping people up.
- **"No evidence found" rate:** how often the assistant comes up empty on a
  row — high numbers usually just mean the evidence pool is missing
  something, so this is more a coverage check than a model-quality one.
- **Chat messages per session:** rough proxy for how much back-and-forth it
  actually takes to get a chart into shape — useful mainly as a baseline to
  compare against as the prompts/flow change.
- **Sessions that reach Export:** of the sessions that ran Generate, how
  many actually get exported — the real signal that a session produced
  something usable, not just experimented with.
