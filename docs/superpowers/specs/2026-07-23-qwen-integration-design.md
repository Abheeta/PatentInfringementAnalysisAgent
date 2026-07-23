# Qwen (Ollama) Integration — Design

Companion to `docs/superpowers/specs/2026-07-23-ai-design.md` (the contract
this implements) and `tasks.md` (Phases 12-14, "Backend — AI Integration").
Covers wiring the four stub AI features to a real local Ollama model,
replacing canned dummy output with real LLM calls, with no change to any
router or service signature.

## Scope

- **Provider:** Ollama only. `OpenRouterProvider` is out of scope for this
  pass — `LLMProvider` is still an abstract interface so it can be added
  later without touching call sites, but only `OllamaProvider` is built now.
- **Model:** `qwen2.5:3b` — this is what's actually pulled on the target
  machine (confirmed via `ollama list` against `localhost:11434`), not the
  `qwen2.5:7b` currently defaulted in `config.py`. That default changes as
  part of this work.
- **Constraint carried over from tasks.md:** routers, services, and the
  frontend do not change. Only `app/ai/*` files change (new provider/
  validation/baseline-prompt modules, and rewrites of the 4 files in
  `app/ai/features/`).

## 1. Provider abstraction — `app/ai/provider.py`

```python
class LLMUnavailableError(ApiError):
    """502 llm_unavailable. Subclasses ApiError so main.py's existing
    global exception handler catches it with zero router changes."""
    def __init__(self, message: str):
        super().__init__(502, "llm_unavailable", message)

class LLMProvider(ABC):
    def generate(self, messages: list[dict], schema: dict) -> dict: ...

class OllamaProvider(LLMProvider):
    def __init__(self, host: str, model: str, num_ctx: int, timeout: float): ...
    def generate(self, messages, schema) -> dict:
        # POST {host}/api/chat
        # body: {model, messages, format: schema, stream: False,
        #        options: {num_ctx}}
        # httpx.ConnectError / httpx.TimeoutException / non-200 status
        #   -> raise LLMUnavailableError
        # response["message"]["content"] parsed via json.loads
        #   -> json.JSONDecodeError also raises LLMUnavailableError
        #      (schema-constrained decoding makes this practically
        #      unreachable on Ollama, but the call is defensive)
        # returns the parsed dict

_provider_instance: LLMProvider | None = None

def get_provider() -> LLMProvider:
    """Module-level singleton, built from settings.LLM_PROVIDER. Tests
    monkeypatch this function (not construct providers directly) so
    FakeProvider can be injected without changing feature call sites."""
```

Timeout: a new `OLLAMA_TIMEOUT` setting (default 120s) — CPU-only local
generation with an 8192-token context budget can be slow, and the existing
`httpx` calls elsewhere in this codebase (`evidence_service.fetch_url`) use
a much shorter timeout that doesn't fit this use case.

## 2. Baseline prompt — `app/ai/baseline_prompt.py`

A single constant, `BASELINE_PROMPT`, holding the verbatim text from
ai-design.md §5. Nothing else — no per-feature logic lives here. The
classification feature's own added rubric (Strong/Moderate/Weak
definitions, ai-design §6.3) is appended by that feature specifically, not
folded into this shared constant, since it's not shared across all four
calls.

## 3. Validation + retry — `app/ai/validation.py`

```python
class StructuredOutputError(Exception):
    """Raised by a validate_fn when a response fails validation twice."""

def call_with_retry(
    provider: LLMProvider,
    messages: list[dict],
    schema: dict,
    validate_fn: Callable[[dict], None],  # raises ValueError on failure
    retry_note: str,
) -> dict:
    """Calls provider.generate once. If validate_fn raises, appends
    {"role": "user", "content": retry_note} to messages and calls once
    more. If validate_fn raises again, raises StructuredOutputError."""
```

Concrete `validate_fn`s, one per feature, matching ai-design §6's "beyond
the schema" rules:

- `validate_disambiguation_pairing` — `needs_clarification` true/false must
  pair with null/non-null `row_id`+`question` as specified in §6.1.
- `validate_proposal_pairing` — same pairing shape for
  `no_evidence_found` vs `proposed_value`/`reasoning`/`confidence`, used by
  both refinement proposal (§6.2) and regrounded correction (§6.5).
- `validate_classification_rowset` — returned `row_id`s must equal the
  session's full row-id set exactly (§6.3).
- `validate_verbatim_quote(evidence_pool: str)` — regrounded correction
  only (§6.5): when `no_evidence_found` is false, `proposed_value` must
  appear as an exact substring of `evidence_pool`.

**Failure-path decision (judgment call — ai-design leaves the "then-error"
half of "retry-once-then-error" unspecified beyond "treated as a
structured-output failure"):**

- Classification, disambiguation, refinement proposal: a second
  consecutive validation failure raises `LLMUnavailableError` (502
  `llm_unavailable`). This reuses the one error surface the frontend
  already has to handle for "AI didn't work" rather than inventing a new
  error code needing frontend changes.
- Regrounded correction only: ai-design §6.5 explicitly defines a
  different fallback for its second failure — **converge to
  `no_evidence_found: true`** rather than erroring, since that's an
  already-valid, already-handled outcome (`chat_service._run_proposal`
  already has a branch for it).

## 4. Feature rewrites — `app/ai/features/*.py`

Each file keeps its exact current call signature. Each:
1. Pulls context via existing service functions (`chart_service.get_rows`/
   `get_row`, `evidence_service.get_evidence_pool`,
   `session_service.get_system_prompt`) — no new service functions needed.
2. Builds `messages`: baseline prompt + analyst's system prompt (system
   role), then task instruction + context sections (user role), per each
   call's "Prompt shape" in ai-design §6.
3. Builds the schema from the existing `app/ai/schemas.py` functions
   (already present, unchanged).
4. Calls `validation.call_with_retry(get_provider(), messages, schema,
   validate_fn, retry_note)`.
5. Returns the parsed dict — same shape the stub returned, so
   `chat_service.py` and `chart_router.py` need no changes.

| File | Calls | Retry note (on validation failure) |
|---|---|---|
| `initial_classification.py` | `classify_all(sid)` | "Your response didn't include exactly one classification per row in this chart — return one entry per row id, no duplicates, none missing." |
| `disambiguation.py` | `resolve_row(sid, message, history)` | "Your response's needs_clarification value didn't match its row_id/question fields — if needs_clarification is true, row_id and question must follow that pairing; if false, the opposite." |
| `refinement_proposal.py` | `propose(sid, row_id, message)` | Same pairing-mismatch note, proposal-worded. |
| `regrounded_correction.py` | `correct(sid, row_id, message)` | On pairing failure: same as proposal. On verbatim failure specifically: "Your last answer wasn't found verbatim in the source text — quote the exact line from the evidence pool, do not paraphrase." |

`opening_message.py` is unchanged — it was already a real (non-stub)
implementation per ai-design §6.4.

## 5. Config changes (`app/config.py`)

- `OLLAMA_MODEL` default: `"qwen2.5:7b"` → `"qwen2.5:3b"` (matches what's
  actually installed; still overridable via env var).
- New `OLLAMA_TIMEOUT` setting, default `120.0` (seconds).

## 6. Testing — `tests/fakes.py`, `tests/test_ai_features.py`

`tests/fakes.py`: `FakeProvider(LLMProvider)` — constructed with a list of
canned response dicts (or exceptions) and returns them in sequence across
successive `generate()` calls, so a test can script "first call returns an
invalid pairing, second call (the retry) returns a valid one" or "both
calls invalid" without touching real Ollama.

`tests/test_ai_features.py`: unit tests per feature, monkeypatching
`app.ai.provider.get_provider` to return a `FakeProvider`, covering:
- Happy path (single valid call).
- Retry-then-succeed (first call fails validation, second succeeds).
- Retry-then-fail (both fail) — asserts `LLMUnavailableError` for
  classification/disambiguation/proposal, asserts `no_evidence_found: True`
  for regrounded correction.
- Regrounded correction's verbatim check specifically (valid quote passes,
  paraphrase fails and retries, still-failing paraphrase converges to
  `no_evidence_found`).

## 7. Manual verification (done when, per tasks.md Phase 12/15)

After the unit tests pass, one manual end-to-end run against the real
local Ollama instance: upload a chart + evidence, `/generate`, a chat
message that needs disambiguation, one that resolves directly to a row, a
flag→correction cycle — confirming real (non-dummy) model output flows
through the exact same endpoints Phase 11 already proved work against
stubs.

## Out of scope

- `OpenRouterProvider` (deferred to a later pass, per user's earlier
  answer).
- The `confidence_reasoning` DB column gap noted as an "open item" in
  ai-design §6.3 — classification's `reasoning` field is still generated
  by the model and still discarded by `chart_service.apply_classifications`,
  identical to today's stub behavior. Out of scope since it needs a
  service/DB change, which this pass explicitly excludes.
