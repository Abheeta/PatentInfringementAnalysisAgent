"""Real implementation from the start — no LLM call, per ai-design.md §6.4.
The opening message states which rows came out Weak/Moderate, which is
fully known and deterministic the moment classification finishes.
"""


def compose_opening_message(rows: list[dict]) -> str:
    weak = [r for r in rows if r["confidence"] == "Weak"]
    moderate = [r for r in rows if r["confidence"] == "Moderate"]

    if not weak and not moderate:
        return "I've reviewed the chart — all rows look strongly supported."

    parts = []
    if weak:
        parts.append(_describe_group(weak, "Weak"))
    if moderate:
        parts.append(_describe_group(moderate, "Moderate"))

    return (
        "I've reviewed the chart. "
        + ", ".join(parts)
        + " — let me know if you'd like to work through them."
    )


def _describe_group(rows: list[dict], tier: str) -> str:
    ids = [r["id"] for r in rows]
    if len(ids) == 1:
        return f"Row {ids[0]} is {tier}"
    row_list = " and ".join(str(i) for i in ids) if len(ids) == 2 else (
        ", ".join(str(i) for i in ids[:-1]) + f" and {ids[-1]}"
    )
    return f"Rows {row_list} are {tier}"
