# Lumenci Assistant — AI Design (Updated: conversational `answer` intent)

Companion to `docs/superpowers/specs/2026-07-22-backend-design.md` (§3 there
points here) and `docs/superpowers/specs/2026-07-22-api-contracts.md`. Covers
everything inside the "AI black box" that the API contracts don't: how the
backend talks to Qwen, how conversation context/memory is assembled, and how
we get reliable structured data back out of the model.

This revision supersedes `docs/superpowers/specs/2026-07-23-ai-design.md`
§2 (context table), §6.1, §6.2, and §6.5. All other sections (§1, §3, §4, §5,
§6.3, §6.4) are unchanged and reproduced here for completeness.

This is the **second of two contracts** in this system:
- **Frontend ↔ Backend** (api-contracts.md) — the frontend never sees Qwen,
  prompts, or raw LLM output; it only sees already-parsed fields like
  `pending_value`/`pending_reasoning`/`pending_confidence`.
- **Backend ↔ LLM provider** (this doc) — what schema we ask Qwen for per
  feature, how we enforce it, and how we translate its output into the
  fields the first contract promises.

## Why this revision

The original §6.1/§6.2/§6.5 forced every analyst message into a rigid
propose/clarify pipeline with no room to just answer a question:

- **No row given** (§6.1): output was a boolean `needs_clarification`. The
  model could only ask "which row?" or silently resolve a row and
  immediately fall into a proposal — no way to just answer a general
  question.
- **Row given** (§6.2 / §6.5): output was a boolean `no_evidence_found`.
  Every row-tagged message was forced into "propose a change" or "say no
  evidence" — no way to just explain what's currently there.

This made the tool feel like a form wizard rather than something the
analyst can have a natural conversation with. The fix: add an explicit
`intent` field to both calls' schemas so "answer conversationally" is a
first-class option — still fully schema-constrained (no free-text/prose
parsing regression, no extra LLM round-trips; CPU-only Ollama is already
speed-constrained by prompt size, §3).

Design decisions this revision locks in:
- The router call's context grows to include the full evidence pool (not
  just the chart + recent messages), so it can ground general-question
  answers rather than guess or duck them.
- The flag/re-grounded-correction flow (§6.5) also gets the `answer`
  intent — a flagged row can still be asked about, not just corrected.
  `rows.flagged` stays `1` until a `propose` response actually completes;
  answering a question doesn't resolve the flag cycle.
- Row-turn answers are tagged to the row (`chat_messages.row_id` set),
  same as proposals — keeps that row's sub-thread coherent for follow-ups
  like "shorter."
- The router never guesses answer-vs-propose for a row-specific message —
  it only ever decides *which row* (`route`), *answers generally*
  (`answer`), or *asks which row* (`clarify`). Once a row is resolved
  (explicitly tagged by the analyst, or routed), the row-turn call
  independently decides `answer` vs `propose`, since it has the row's full
  detail + evidence + thread that the router doesn't.

## 1. Orchestration

No agent framework (e.g. LangGraph). Of the 4 actual LLM calls (§6 — opening
message turned out to need no LLM call at all, see §6.4), 3 are single-shot
with no branching (initial classification, refinement proposal, re-grounded
correction — the latter two share one "answer or propose or say no evidence"
shape, previously "propose or say no evidence"). Only the chat-message turn
has any branching, and it's one conditional fork: *no `row_id` given →
router (evidence-grounded) → if a row is needed and identifiable, route to
it; if ambiguous, ask and stop; if answerable directly, answer and stop →
else (row given/routed) → row-turn call decides answer vs. propose*.

A framework's main selling points don't apply here:
- **Durable human-in-the-loop pausing** (e.g. LangGraph's `interrupt()` +
  checkpointer) is already solved, in SQLite: a proposal sits in
  `pending_value` until `/accept` or `/reject` is called, entirely outside
  any in-process run. Adding a framework's checkpointer would be a second,
  redundant persistence mechanism for the same concept.
- **Multi-agent handoff, cyclic re-planning, long agentic loops** — none of
  the 5 features need this; the branching is one shallow fork.

Orchestration is plain Python functions: build prompt → call
`LLMProvider.generate()` → validate/parse structured output → act.

## 2. Context & Memory Management

**No chat-history summarization.** This is a legal-evidentiary tool whose
core premise is "never fabricate, everything traceable" — having the model
compress its own past conversation and reason from that lossy summary is
exactly the wrong tradeoff, for a problem (context length) this app doesn't
actually have: one analyst, one working session, realistically dozens of
short messages.

**Context is assembled per call by filtering, not compressing**, using data
we already have:

| Call | Context included |
|---|---|
| Initial classification | Per row: `claim_element`, `product_feature`, `ai_reasoning` (unchanged from CSV) + full evidence pool |
| Opening chat message | Full just-classified chart (all rows + confidence) |
| Chat router (no `row_id`) | Full chart (claim elements + current evidence per row) + **full evidence pool** + last ~10 chat messages (session-wide, for pronoun-style references) |
| Row turn (refinement proposal / re-grounded correction) | The resolved row's own data + that row's tagged message sub-thread (`chat_messages WHERE row_id = X`) + full evidence pool + the analyst's current message |

The router's context now includes the full evidence pool (previously just
the chart + recent messages) so it can ground general-question `answer`
responses in the actual evidence, not only the chart summary — see §6.1.

**Evidence pool: full-stuffing, no retrieval/chunking layer.** Confirmed
scope: charts are 5-10 rows, evidence docs are small — the 5MB/file cap in
backend-design is a defensive ceiling, not the expected size. Sending the
full evidence pool on every call (now including the router call) is simple
and correct at this scale. If real usage ever grows past prototype scale,
revisit with a retrieval layer then — not building it preemptively.

## 3. Local Model Runtime Config (Ollama)

Ollama defaults `num_ctx` to 2048 regardless of what the model card
supports — this must be set explicitly or most of the context above gets
silently truncated. Target machine: CPU-only, 16GB RAM.

- `num_ctx: 8192` set explicitly (Modelfile or per-request `options`).
  Qwen2.5-7B uses grouped-query attention, so KV cache at this size is well
  under 1GB — RAM is not the binding constraint here.
- **Speed, not memory, is the real constraint on CPU-only.** Prefill time
  scales with how much context is sent, and there's no GPU to absorb that
  cost. At prototype scale (5-10 rows, small evidence) this stays
  reasonable; it's the reason we ruled out any strategy that would send
  large volumes of text per call — and why the router's new evidence-pool
  inclusion is scoped to this same prototype-scale assumption, not a
  blank check to keep growing context.
- OpenRouter's `qwen-2.5-72b-instruct` path remains valuable for *quality*
  (more reliable instruction-following/structured output), not because
  local can't fit the context — it can, at this scale.

## 4. Structured Output

**Goal:** every feature call needs to hand back machine-parseable data
(e.g. `row_id: 3`, `confidence: "Strong"`), not prose our code has to
interpret.

**Mechanism: schema-constrained decoding**, not just "JSON mode." Plain
JSON mode (`format: "json"`) only guarantees syntactically valid JSON — not
that the right fields are present or that `confidence` is one of
`Strong`/`Moderate`/`Weak` rather than something the model invented.
Schema-constrained decoding instead takes a real JSON Schema and constrains
generation token-by-token so the output *cannot* deviate from it.

- **Ollama (local):** supported directly — pass a JSON Schema as the
  `format` parameter instead of the string `"json"`. This is a guarantee,
  not a best-effort prompt instruction.
- **OpenRouter:** support depends on the underlying model route — some
  support the equivalent (`response_format: json_schema`), some don't.
  *(Open item: confirm support for whichever OpenRouter Qwen route we use;
  fall back to JSON-mode + prompt-described schema + retry-once-on-parse-
  failure for that provider if unsupported.)*

**Field-naming translation (a real gap the old backend-design had):** the
schema we ask the LLM for and the DB/API field names are not required to
match, and shouldn't be assumed to. Old backend-design used the LLM-facing
field `proposed_value`; the DB/API use `pending_value`/`pending_reasoning`/
`pending_confidence`. This doc's per-feature schemas (§6) are the source of
truth for LLM-facing field names; the mapping onto DB columns is explicit,
not by-convention-matching-name. The new `answer` field (§6.1, §6.2, §6.5)
maps directly to `chat_messages.content` with **no** translation — unlike
`reasoning`, which is never shown to the analyst raw, `answer` *is* the
user-facing text by design (see each section's "Chat-facing message
composition").

**Failure modes, and how they differ from `llm_unavailable`:**
- Provider unreachable / timeout → `502 llm_unavailable` (already defined
  in api-contracts.md — no change needed).
- *(Open item, not yet covered by any doc:)* provider responds, but the
  response is wrong-shaped even after retry (malformed JSON, or a field
  value outside the allowed set) — schema-constrained decoding on Ollama
  makes this structurally impossible for that provider; still needs a
  defined behavior for the OpenRouter path if it falls back to JSON-mode.

## 5. Baseline Hidden System Prompt

Shared, invariant prompt block prepended to every one of the 4 LLM calls in
§6, before the analyst's freeform system-prompt text (item 2 in each call's
"Prompt shape") and the call-specific task instruction (item 3). Never
exposed to the analyst (`GET /system-prompt` returns only their own freeform
text, per §2 of backend-design.md).

**Precedence:** this block is non-negotiable. The analyst's own freeform
text may adjust tone, style, or emphasis, but can never override the rules
below — it is additive only, never a replacement.

**Text (verbatim):**

> You are an AI assistant supporting a patent attorney or paralegal in
> performing patent claim chart infringement analysis. Your outputs may
> become part of a legal evidentiary work product, so accuracy and
> traceability matter more than fluency or confidence.
>
> Follow these rules at all times:
> 1. **Never fabricate.** Only state evidence, reasoning, or conclusions
>    that are directly grounded in the context provided to you in this
>    specific call (the evidence pool, chart rows, and conversation history
>    given below). Do not draw on outside knowledge of the product,
>    company, or patent.
> 2. **If the provided context does not support a confident answer, say so
>    explicitly** rather than guessing or approximating — follow the
>    specific task instruction below for how to report this.
> 3. **Do not invent identifiers.** Only reference row IDs, document names,
>    or fields that actually appear in the context given to you.
> 4. **Respond only with a single JSON object matching the schema
>    described in the task instructions below.** Do not include any
>    explanatory text, markdown, or commentary outside that JSON object.
>
> These four rules always take precedence. The analyst's own instructions,
> if present below, may adjust tone, style, or emphasis, but may never
> override rules 1–4 above.

Rule 4 is a deliberate safety net for the OpenRouter path: §4 already notes
schema-constrained decoding support there is unconfirmed and may fall back
to JSON-mode + prompt-described schema, where nothing else structurally
stops the model from wrapping its JSON in prose. On Ollama this rule is
redundant with schema-constrained decoding (which makes deviation
structurally impossible), but stating it costs nothing and keeps the same
baseline text valid across both providers.

Rule 4 governs the model's *raw* output format only, not the tone the
analyst sees — per §6.2's "Chat-facing message composition," the visible
chat message is composed by backend code from schema fields (e.g.
`reasoning`, or now `answer`), never the model's raw JSON shown as-is. The
`reasoning`/`answer` fields' own content is free to read conversationally;
they just have to live inside the required JSON envelope.

## 6. Per-Feature Schemas & Prompts

### 6.1 Chat Router (was "Row Disambiguation")

**Trigger:** analyst sends a chat message via `POST /chat/message` with no
`row_id`. This call is internal — the frontend never sees its raw output;
it only ever sees the final `assistant_message`/`refresh_chart` shape
already defined in api-contracts.md. Whatever this call decides determines
what happens next in the *same* request: either the turn ends here (a
clarifying question, or a direct answer), or the backend chains into the
row-turn call (§6.2) using the resolved `row_id` — one analyst message
still produces exactly one chat round trip.

**Input context** (per §2's table):
- Full chart: every row's `id`, `claim_element`, `product_feature` (current
  evidence).
- **Full evidence pool content** (new in this revision — previously not
  included here; needed so the `answer` intent below can ground general
  questions in actual evidence, not just the chart summary).
- Last ~10 `chat_messages` for this session (raw, unsummarized).
- The analyst's new message (the one being resolved).

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "intent": {"type": "string", "enum": ["route", "clarify", "answer"]},
    "row_id": {"type": ["integer", "null"], "enum": [<actual row ids in this session, or null>]},
    "question": {"type": ["string", "null"]},
    "answer": {"type": ["string", "null"]}
  },
  "required": ["intent", "row_id", "question", "answer"]
}
```
The `row_id` enum is **built per-request** from this session's actual row
ids (plus `null`) — not a generic integer, same as before. This means the
model cannot hallucinate a row ID that doesn't exist in this chart;
schema-constrained decoding rules it out structurally, not just via a
post-hoc check.

**Validation beyond the schema** (schema can't express this
conditionally, so it's checked in code after generation):
- `intent == "route"` → `row_id` must be non-null (a real row from this
  session); `question` and `answer` must both be `null`.
- `intent == "clarify"` → `row_id` and `answer` must be `null`; `question`
  must be non-null.
- `intent == "answer"` → `row_id` and `question` must be `null`; `answer`
  must be non-null.
- A response violating these pairings is treated the same as a schema
  failure (§4's retry-once-then-error path), not silently accepted.

**Prompt shape:**
1. Hidden baseline instruction (see §5).
2. Analyst's freeform system-prompt text.
3. Task instruction: "Given the chart, evidence pool, and recent
   conversation below, decide how to handle the analyst's latest message.
   If it asks to review, refine, or correct a specific row's evidence and
   you can tell which row it means, respond with intent `route` and that
   row's id. If a specific row seems intended but you can't tell which one,
   respond with intent `clarify` and a clarifying question. If it's a
   general question you can answer directly and accurately from the chart
   and evidence already given below — not a request to change any specific
   row — respond with intent `answer` and a grounded answer. Never guess;
   if you cannot answer confidently from the given context, prefer
   `clarify` or `route` over fabricating an answer."
4. Chart context (row id + claim element + current evidence, all rows).
5. Full evidence pool content.
6. Last ~10 messages.
7. The analyst's new message.

**On `route`:** no DB write from this call itself — it only determines the
`row_id` that gets passed into the row-turn call next (§6.2). Nothing in
`rows` or `chat_messages` is touched until that next call runs. Critically,
`route` only ever means "this message is about row X" — it does **not**
imply the row-turn call must propose a change; that call independently
decides `answer` vs `propose` using richer per-row context the router
doesn't have.

**On `clarify`:** the `question` becomes the assistant's chat reply —
appended to `chat_messages` (`role=assistant`, `row_id=null`) and returned
as `assistant_message` with `refresh_chart: false`, matching the existing
api-contracts.md example for this case. Turn ends here; no chart mutation.

**On `answer` (new):** the `answer` becomes the assistant's chat reply —
appended to `chat_messages` (`role=assistant`, `row_id=null`) and returned
as `assistant_message` with `refresh_chart: false`. Turn ends here; no
chart mutation, no row resolution forced. Unlike `reasoning` elsewhere in
this doc, `answer` is composed for the analyst as-is (no code-side
rewording) — see §4's field-naming note.

### 6.2 Row Turn (was "Refinement Proposal")

**Trigger:** a `row_id` is resolved for the current turn — either given
directly (analyst clicked a row / used the `@Row` chip / clicked Modify) or
resolved by §6.1's router call via `route`. Also the call used for
"Modify": per the PRD, Modify just re-inserts the `@Row` chip and
re-enters this same normal message flow — there is no separate "revision"
call.

**This call, not the router, decides whether the analyst wants an answer
or a proposed change.** The router's job stops at "this message is about
row X"; this call has the row's full detail, evidence pool, and its own
conversation sub-thread, which is what's actually needed to judge intent
correctly.

**Input context** (per §2's table):
- The resolved row's own data: `claim_element`, current `product_feature`,
  current `ai_reasoning`, current `confidence`.
- That row's own tagged message sub-thread: `chat_messages WHERE row_id =
  <resolved id>` — this is what makes iterative steering ("shorter," "cite
  the doc directly") work; without it, a follow-up like "shorter" has
  nothing to be shorter *than*. It's also what lets a follow-up "answer"
  reply be answered consistently with what was already discussed.
- Full evidence pool content (confirmed fine at prototype scale, §2).
- The analyst's current message.

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "row_id": {"type": "integer", "enum": [<resolved row id — single value, forces the model to echo the row it's actually addressing>]},
    "intent": {"type": "string", "enum": ["answer", "propose"]},
    "answer": {"type": ["string", "null"]},
    "no_evidence_found": {"type": ["boolean", "null"]},
    "proposed_value": {"type": ["string", "null"]},
    "reasoning": {"type": ["string", "null"]},
    "confidence": {"type": ["string", "null"], "enum": ["Strong", "Moderate", "Weak", null]}
  },
  "required": ["row_id", "intent", "answer", "no_evidence_found", "proposed_value", "reasoning", "confidence"]
}
```
`row_id`'s enum is pinned to the single already-resolved ID (not a list of
valid rows, unlike §6.1) — this call never chooses a row, it only ever
acts on the one it's given, and schema-constrained decoding forces it to
echo that back rather than drift to a different row.

**Validation beyond the schema:**
- `intent == "answer"` → `answer` must be non-null; `no_evidence_found`,
  `proposed_value`, `reasoning`, and `confidence` must all be `null`.
- `intent == "propose"` → `answer` must be `null`. Same pairing rule as
  before on `no_evidence_found`: if `true` → `proposed_value`,
  `reasoning`, `confidence` all `null`; if `false` → `proposed_value` and
  `reasoning` non-null, `confidence` one of the three tiers (already
  enforced by the schema's enum).
- Grounding requirement (checked at the prompt-instruction level, not
  mechanically enforceable by schema): both `answer` content and
  `proposed_value`/`reasoning` must be traceable to the evidence pool
  content actually provided — this call does **not** require a verbatim
  quote for either (that stricter rule is specific to §6.5's re-grounded
  `propose` path).

**Prompt shape:**
1. Hidden baseline instruction (see §5).
2. Analyst's freeform system-prompt text.
3. Task instruction: "Given this row's claim element, its current
   evidence and reasoning, the full evidence pool, and this row's own
   conversation history, decide whether the analyst's latest message is a
   question about this row (respond with intent `answer`, grounded in the
   evidence, without proposing a change) or a request for a change or
   improvement to this row's evidence (respond with intent `propose`: an
   improved evidence value + reasoning + confidence tier grounded in the
   evidence pool, or state that no supporting evidence was found). Address
   only this row."
4. Row context (claim element, current evidence/reasoning/confidence).
5. Full evidence pool content.
6. This row's tagged message sub-thread.
7. The analyst's current message.

**DB/API mapping** (unchanged from the original for the `propose` path;
this is where the earlier naming gap gets closed explicitly):
- LLM field `proposed_value` → DB/API `pending_value`.
- LLM field `reasoning` → DB/API `pending_reasoning`.
- LLM field `confidence` → DB/API `pending_confidence`.
- LLM field `answer` → `chat_messages.content` directly, no translation
  (see §4).
- These are **not** matched by convention/same-name assumption — the
  mapping is an explicit step in code, since the two schemas are allowed to
  diverge (and already have, once, before we caught it).

**Chat-facing message composition:**
- `intent == "propose"`, `no_evidence_found == false`: `reasoning` is not
  shown to the analyst verbatim as-is; the visible
  `assistant_message.content` is composed in code (e.g. `"Proposing an
  update to row {id}: {reasoning}"`), so wording consistency doesn't depend
  on the model phrasing a user-facing sentence correctly.
- `intent == "propose"`, `no_evidence_found == true`: the chat message is a
  fixed template (`"I couldn't find supporting evidence for row {id} in
  the uploaded docs. Can you upload another document or provide a URL?"`),
  not LLM-authored.
- `intent == "answer"` (new): the chat message is `answer` as-is — this
  field's whole purpose is to be the user-facing reply, unlike `reasoning`.
  Tagged to the row (`chat_messages.row_id = {id}`), same as a proposal
  message, so the row's own sub-thread stays coherent for later follow-ups.

**Result:**
- `intent == "propose"`, `no_evidence_found == false` → row's `pending_*`
  columns set, `refresh_chart: true`.
- `intent == "propose"`, `no_evidence_found == true` → no DB write,
  `refresh_chart: false`.
- `intent == "answer"` (new) → no DB write to `pending_*`, `refresh_chart:
  false`, assistant message tagged to the row.

### 6.3 Initial Classification

*(Unchanged from the original design — reproduced for completeness.)*

**Trigger:** `POST /generate`, once per session (`generated` flips 0→1).

**Batching decision:** one call for the whole chart, not one call per row.
Old backend-design left "batching strategy... still to be finalized" open;
now that scale is confirmed (5-10 rows, small evidence), a single call is
both simpler and cheaper than 5-10 separate round trips, and gives the
model the full evidence pool once instead of repeating it per call.

**Input context:** every row's `claim_element`, `product_feature`,
`ai_reasoning` (all unchanged from the CSV) + the full evidence pool.

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "classifications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "row_id": {"type": "integer", "enum": [<all row ids in this session>]},
          "confidence": {"type": "string", "enum": ["Strong", "Moderate", "Weak"]},
          "reasoning": {"type": "string"}
        },
        "required": ["row_id", "confidence", "reasoning"]
      }
    }
  },
  "required": ["classifications"]
}
```

**Validation beyond the schema:** the returned set of `row_id`s must equal
this session's full row-id set exactly — one entry per row, no duplicates,
none missing. A mismatch is treated as a structured-output failure (§4's
retry-once path), not silently patched (e.g. by defaulting missing rows to
`Weak`).

**Prompt shape:**
1. Hidden baseline instruction (see §5), plus this call's own added rubric:
   Strong = evidence directly states the claim element; Moderate = evidence
   implies it, requires inference; Weak = evidence is tangential or absent.
2. Analyst's freeform system-prompt text.
3. Task instruction: "Classify the confidence tier for every row below,
   based on evidence directness. Do not rewrite the evidence or reasoning
   text — classification only. For each row, also give a short `reasoning`
   explaining the confidence tier: for `Strong`, a brief one-line
   justification is enough; for `Moderate` or `Weak`, explain what's
   missing or merely implied so the analyst knows what to go check."
4. Full chart (all rows' claim element / evidence / reasoning).
5. Full evidence pool.

**`reasoning` is new output, not a rewrite of `ai_reasoning`.** This is the
model's justification for the *confidence tier it assigned*, distinct from
the row's existing `ai_reasoning` (the CSV-sourced evidence reasoning,
which this call still never touches — see backend-design.md §2). Brief for
`Strong`, more explanatory for `Moderate`/`Weak`, per the task instruction
above.

**DB/API mapping:** unlike §6.2, this **writes directly to `rows.confidence`
for each row** — there is no pending/Accept step for the initial pass. This
matches the PRD: the initial classification pass assigns confidence
outright; human-in-the-loop gating applies to *chat-driven* proposals
(§6.2, §6.5), not this one-time setup pass. *(Open item: `reasoning` has no
DB column yet — backend-design.md's `rows` table needs one, e.g.
`confidence_reasoning`, plus a corresponding field in api-contracts.md's
`GET /chart` row shape, before this can be surfaced to the analyst.)*

**Result:** feeds directly into §6.4 within the same `/generate` request —
by the time this call returns, every row's live `confidence` is set, and
the opening message is generated next in the same handler.

### 6.4 Opening Chat Message

*(Unchanged from the original design — reproduced for completeness.)*

**Design decision: no LLM call for this feature.** The opening message
only needs to state which rows came out Weak/Moderate from §6.3 — that's
data already fully known and deterministic the moment classification
finishes, not something requiring synthesis or judgment. Following the
same principle from §6.2 (don't trust the model to author consistent
user-facing prose when the content is fully derivable), this is composed
in code directly from the classification result:

```
"I've reviewed the chart. {rows} — let me know if you'd like to work through them."
```
where `{rows}` lists each Weak/Moderate row by claim element (e.g. "Rows 3
and 7 are Weak, row 5 is Moderate"), grouped by tier, in row order. If
every row classified Strong, a fixed alternate message is used instead
(e.g. "I've reviewed the chart — all rows look strongly supported.").

This reduces the "5 LLM-driven features" from the PRD/backend-design to
**4 actual LLM calls** — the 5th (opening message) is now a deterministic
template. Net effect: one fewer place where model output needs validation,
for a feature that had no real judgment to make in the first place.

**DB/API mapping:** appended to `chat_messages` (`role=assistant`,
`row_id=null`), returned as `opening_message` in `POST /generate`'s
response — matches api-contracts.md's existing shape unchanged.

### 6.5 Re-grounded Correction (flag flow)

**Trigger:** per the corrected flow (backend-design §2), flagging a row
only posts a system note and marks the row as awaiting correction — it's
the analyst's **next** chat message (tagged to that row) that actually
triggers this call. Reuses §6.2's shape exactly (including the `answer`/
`propose` intent split), with one added constraint and one added piece of
state.

**New state needed:** the `rows` schema needs a way to know "this row is
mid-re-scan, awaiting the analyst's description of what's wrong" — needed
so the backend picks *this* prompt variant instead of §6.2's normal one for
the row's next message. `rows.flagged` (boolean, default 0) — set to 1 by
`POST /flag`. Cleared back to 0 **only when a `propose` response completes**
(success or `no_evidence_found` — the flagged cycle is "handled" the
moment the AI actually attempts the re-grounding, independent of whether
the analyst later Accepts or Rejects that response). **New in this
revision:** if the analyst's tagged message instead resolves to
`intent == "answer"` (e.g. "why was this flagged?"), `rows.flagged` stays
`1` — answering a question doesn't resolve the flag cycle, since the
analyst still hasn't described the correction. Now added to
`backend-design.md` §2's schema, `api-contracts.md`'s `GET /chart` row
shape, and `POST /flag`'s error table (`409 already_flagged` if called
again while already 1), and reflected in `frontend-design.md`'s `ChartRow`
as a `FlaggedBanner`.

**Input context:** identical to §6.2 (resolved row's data, its tagged
message sub-thread, full evidence pool, analyst's current message) plus
`rows.flagged = 1` being what routes here instead of §6.2.

**Output schema:** identical to §6.2's (including `intent`/`answer`), with
one added constraint — when `intent == "propose"` and
`no_evidence_found == false`, `proposed_value` must be an **exact verbatim
quote**, not a paraphrase, per the PRD's flag-flow requirement. This
verbatim requirement does **not** apply to `intent == "answer"` responses.

**Validation beyond the schema (stronger than §6.2's, only on the
`propose` path):**
- Same intent pairing rules as §6.2.
- **Verbatim check, mechanically verifiable — not just trusted, and only
  when `intent == "propose"` and `no_evidence_found == false`:**
  `proposed_value` must appear as an exact substring somewhere in the
  concatenated evidence pool content. This is a real code-level check (not
  a prompt instruction we hope the model follows) — if it fails, treat it
  as a structured-output failure (§4's retry-once path, with an explicit
  correction message like "your last answer wasn't found verbatim in the
  source text"); if it fails twice, converge on `no_evidence_found: true`
  rather than surfacing a fabricated-looking quote. This fallback only
  applies to the `propose` path — an `answer` response that fails the
  intent-pairing check still goes through the normal retry-once-then-error
  path (§4), since there's no "no evidence found" fallback that makes
  sense for a plain answer.

**Prompt shape:** same as §6.2, with the task instruction amended: "...the
analyst has flagged this row's evidence as potentially wrong. If their
latest message describes what's wrong, treat this as intent `propose`:
find and quote the relevant line **verbatim** from the evidence pool — do
not paraphrase; if no supporting line exists anywhere in the pool, state
that no evidence was found. If their latest message is instead a question
(e.g. asking why the row was flagged, or what the current evidence says),
treat this as intent `answer` and answer directly — the row remains
flagged until they actually describe the correction."

**DB/API mapping:** identical to §6.2 for both intents (`answer` →
untranslated chat message tagged to the row, no DB write; `propose` →
`pending_*` columns, `refresh_chart` true/false) — a completed `propose`
response re-enters the normal pending flow and requires an explicit Accept
like any other proposal, per the PRD. Also clears `rows.flagged` back to 0
only on a completed `propose` response (success or `no_evidence_found`),
regardless of the analyst's later Accept/Reject; an `answer` response
leaves `rows.flagged` at 1.
