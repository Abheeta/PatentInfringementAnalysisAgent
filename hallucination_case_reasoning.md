There are really more than two if you want them, but let me explain the two I offered and then a third middle option.

**Option 1: Treat it as the same accept/reject/modify flow, no special logic**
"Wrong evidence" is just one more reason an analyst might say "modify." The AI proposes something, the analyst says it's factually inaccurate, the AI produces a correction, and — per our graduated trust model — since the analyst is now actively directing the correction, it applies directly (visible diff, reversible). Nothing new to build: same state machine, same UI, just a different reason for the correction in the message text. Simple, but it trusts the AI's "corrected" answer exactly as much as it trusts a "make it shorter" edit — the system doesn't distinguish "stylistic tweak" from "you hallucinated a quote that doesn't exist."

**Option 2: Special-case it — force re-grounding against the source**
Because "wrong evidence" specifically means the AI *fabricated or misquoted* something (this is the hallucination bonus-point failure mode, not a taste disagreement), the system requires the AI to re-scan the actual uploaded document/URL text before it's allowed to re-propose — i.e., it can't just take the analyst's correction at face value and free-associate a fix; it has to re-derive the quote from the real source text. This is more building work (you'd need the backend to re-run a grounding/retrieval step specifically on evidence-correction turns) but it directly demonstrates you understand *why* evidence hallucination is dangerous and designed a mechanism against it, not just a UI convention.

**Option 3 (middle ground I didn't offer, but exists):** No new backend mechanism, but a *UI/prompting* distinction — when an analyst's message implies a factual correction (e.g., contains "wrong," "incorrect," "doesn't say that"), the AI's system prompt instructs it to explicitly quote the exact source line it's now relying on in its response, so the analyst can visually verify the correction against the source rather than trusting AI prose. Cheaper than Option 2 (no real re-fetch step, just a response-format requirement) but still adds a verification signal Option 1 lacks.

Locked flow for "wrong evidence" correction: analyst flags
  evidence as inaccurate → backend re-scans the actual
  uploaded doc/URL text for the claim element in question →
  AI's correction response must include the exact quoted
  source line it found → correction applies directly to the
  chart (per the graduated trust model, since the analyst's
  correction counts as permission) → visible diff.

  Fallback noted: if this proves too heavy to build in the
  time available, we rewind to Option 1 (treat it as a normal
  modify, no re-grounding step) — noting that as an explicit
  fallback in the plan is reasonable given the 24-hour
  constraint.

  Now the second edge case — "undo a previous refinement."
  This mostly overlaps with the reject/undo mechanism we
  already have, but worth pinning down precisely:
  