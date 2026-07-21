Good pushback — let me lay out the real tradeoffs rather than presenting it as a binary.

**Option A: Per-row chat panels (separate conversation per row)**
- Pro: zero ambiguity, AI never has to guess which row.
- Con: what you flagged — N separate conversation threads is awkward. It also loses cross-row context (e.g., "make the reasoning tone consistent with row 1" becomes impossible if row 3's chat can't see row 1's thread). And a button/panel per row adds real UI clutter for a chart that might have 10+ rows.

**Option B: One global chat, AI infers row from natural language every time**
- Pro: simplest architecture, one conversation, feels like a normal chat.
- Con: real reliability risk — this is exactly the "LLM limitation" bonus point territory. If two rows both mention "sensor" or the analyst is vague ("fix that one"), the AI can silently edit the wrong row. In a legal document, a silently-wrong edit is worse than a slow one.

**Option C — hybrid, one global conversation + explicit row anchoring (what I'd actually recommend)**
Single chat thread (so context and history are shared across the whole session — matches "through continued conversation" from the spec), but disambiguation is handled by the *UI*, not by the AI guessing from prose:
- Clicking a chart row doesn't open a new panel — it inserts a lightweight reference chip into the chat input (like `@Row 3: ML algorithm` tag, similar to mentioning someone in Slack), so the analyst's next message is unambiguously anchored without having to type the full claim text.
- The AI's response also gets tagged/highlighted against that row so it's visually obvious which cell it's proposing to change.
- If the analyst types a message with no row selected and no clear referent, the AI's job is to ask a clarifying question ("Which claim element are you referring to?") rather than guess — this is itself a human-in-the-loop pattern worth naming in the PRD.

This keeps one continuous conversation (simpler backend, real shared context) while removing the guessing risk of Option B, without the clutter of N separate chat panels in Option A.
