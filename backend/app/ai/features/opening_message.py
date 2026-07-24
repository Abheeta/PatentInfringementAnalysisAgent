"""Real implementation from the start — no LLM call, per ai-design.md §6.4.
The opening message states which rows came out Weak/Moderate, which is
fully known and deterministic the moment classification finishes.
"""

from app.ai.row_display import display_offset, to_display_id


def compose_opening_message(rows: list[dict]) -> str:
    weak = [r for r in rows if r["confidence"] == "Weak"]
    moderate = [r for r in rows if r["confidence"] == "Moderate"]

    if not weak and not moderate:
        return "I've reviewed the chart — all rows look strongly supported."

    offset = display_offset(rows)
    parts = []
    if weak:
        parts.append(_describe_group(weak, "Weak", offset))
    if moderate:
        parts.append(_describe_group(moderate, "Moderate", offset))

    return (
        "I've reviewed the chart. "
        + ", ".join(parts)
        + " — let me know if you'd like to work through them."
    )


def _describe_group(rows: list[dict], tier: str, offset: int) -> str:
    ids = [to_display_id(offset, r["id"]) for r in rows]
    if len(ids) == 1:
        return f"Row {ids[0]} is {tier}"
    row_list = " and ".join(str(i) for i in ids) if len(ids) == 2 else (
        ", ".join(str(i) for i in ids[:-1]) + f" and {ids[-1]}"
    )
    return f"Rows {row_list} are {tier}"
