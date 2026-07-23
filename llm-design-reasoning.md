 Where we are so far:
  1. Orchestration = "what code decides what
  happens next in a conversation turn." We
  decided: no framework (no LangGraph) — just
  plain Python functions, because our
  branching is shallow (basically one fork:
  "did the AI understand which row you meant,
  or does it need to ask?").
  2. Memory/context = "what information gets
  fed to the model on each call." We decided:
  no summarization (risky for a
  legal-evidence tool — compressing
  conversation history can quietly drop
  details); instead, filter by row (row_id in
  the chat table) so each call only sees
  what's relevant to that row, plus the whole
  chart/evidence since your files are small
  (5-10 rows).

  Next topic: structured output — how do we
  get the AI to reliably return something our
  code can act on, not just prose?

  Every one of our 5 AI features needs the
  model to hand back machine-readable data,
  not a paragraph. Example: when the AI
  resolves which row a message is about, our
  backend needs an actual number (row_id: 3)
  it can look up in the database — not "I
  think you mean the memory row." When it
  proposes a fix, our code needs to split
  that into three separate pieces (the new
  evidence text, the reasoning, the
  confidence tier) to store in three separate
  database columns.

  There are three ways to get an LLM to do
  this reliably, roughly from "hopeful" to
  "enforced":

  1. Just ask nicely, in the prompt.
  ("Respond only with JSON matching this
  shape: {...}") The model usually complies,
  but nothing stops it from adding a sentence
  before the JSON, using the wrong field
  name, or occasionally breaking the format.
  You then have to parse the text and handle
  failures (this is what the old
  backend-design already sketched: parse, and
  retry once with "that wasn't valid JSON"
  if it fails).
  2. JSON mode. Both Ollama and OpenRouter
  support a format: json / response_format
  setting that forces the model's output to
  be syntactically valid JSON at the decoding
  level (the model literally cannot emit
  broken JSON) — but it doesn't guarantee the
  JSON has the fields you asked for, just
  that it parses. Combine this with #1 (still
  describe the shape in the prompt) for a
  big reliability jump with almost no extra
  work.
  3. Tool/function calling. You define the
  exact shape (field names, types) as a
  formal "tool schema," and the API is told
  to call that tool instead of writing free
  text. This is the most reliable of the
  three, but Qwen's tool-calling support
  through Ollama and through OpenRouter can
  be inconsistent between models/providers,
  and it's a bit more code to wire up
  (defining schemas, handling the tool-call
  response format, which differs from a
  normal chat message).

  For a prototype using Qwen through two
  different providers, my instinct is #2
  (JSON mode + describing the shape
  in-prompt), with the retry-on-parse-failure
  fallback from #1 — it's a one-line
  addition per call, meaningfully more
  reliable than prompting alone, and avoids
  the extra plumbing and
  provider-inconsistency risk of real
  tool-calling. Does that make sense, or do
  you want me to go deeper on how
  tool-calling would actually look before
  deciding?



  
  Contract 1 — Frontend ↔ Backend (already fully documented). This is what api-contracts.md
  covers: the HTTP JSON shapes between the React app and FastAPI. The frontend never sees Qwen,
  prompts, or raw LLM output at all — it only ever sees already-cleaned-up things like
  pending_value/pending_reasoning/pending_confidence on a row, or assistant_message.content in
  a chat response. From the frontend's point of view, the AI is a black box behind the API.

  Contract 2 — Backend ↔ LLM provider (not written down anywhere yet — this is the ai-design
  doc's job). This is everything inside that black box: what exact JSON we ask Qwen for on each
  of the 5 features, how we enforce it actually comes back that shape, and how we translate
  the LLM's raw output into the columns/fields Contract 1 promises the frontend.

  What's already locked in (from api-contracts.md) that constrains what we're about to design:
  - The final shapes the backend must produce, e.g. assistant_message {id, role, content,
  row_id, created_at}, and rows carrying pending_value/pending_reasoning/pending_confidence.
  - The failure surface visible to the frontend when the LLM is totally unreachable: 502
  llm_unavailable on /generate and /chat/message. So "the LLM API is down" is already covered.

  What's genuinely missing — and it's missing because it's supposed to live in ai-design.md,
  not api-contracts.md:
  1. The schema we actually ask Qwen for, per feature (e.g., does the model call it
  proposed_value internally, or pending_value? — we caught this exact naming mismatch earlier:
  the old backend-design's prompt used proposed_value, the DB/API use pending_value. Nobody has
  written the translation step.)
  2. How we enforce the model returns that schema — this is the structured-output mechanism we
  just discussed (schema-constrained decoding vs. JSON-mode vs. retry).
  3. What happens when the LLM responds but the response is wrong-shaped (not merely
  unreachable) — e.g. malformed JSON even after one retry, or a confidence value that isn't one
  of the three allowed strings. llm_unavailable only covers "couldn't reach/get a response
  from the provider at all," not "got a response but it's garbage." That's a gap even the
  current API contract doesn't close — we need to decide: does that also become
  llm_unavailable, or a distinct error, or a safe fallback value?
  4. The actual prompt content for each of the 5 features (classification, opening message,
  disambiguation, refinement proposal, re-grounded correction) — what exactly goes in, in what
  order, with what instructions.

  So: nothing's wrong with api-contracts.md, it just intentionally stops at the boundary of the
  black box. Everything in that second list is what we're building in the ai-design doc. Want
  to start with #1+#2 (define one concrete schema + enforcement mechanism, end to end, for a
  single feature like disambiguation, as a template) so you can see the whole shape once before
  we repeat it for the other four?