"""Maps real row ids to 1-based display ids (and back) for prompts where the
model has to match the analyst's plain-English row references (e.g. "the
third row"). Rows are guaranteed contiguous per session, so display id is
just the offset from the lowest row id in the set — same scheme as the
frontend's toDisplayRowId.
"""


def display_offset(rows: list[dict]) -> int:
    return min(r["id"] for r in rows)


def to_display_id(offset: int, row_id: int) -> int:
    return row_id - offset + 1


def to_real_id(offset: int, display_id: int) -> int:
    return display_id + offset - 1
