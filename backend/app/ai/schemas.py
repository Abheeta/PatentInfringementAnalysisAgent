def router_schema(row_ids: list[int]) -> dict:
    return {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": ["route", "clarify", "answer"]},
            "row_id": {"type": ["integer", "null"], "enum": [*row_ids, None]},
            "question": {"type": ["string", "null"]},
            "answer": {"type": ["string", "null"]},
        },
        "required": ["intent", "row_id", "question", "answer"],
    }


def row_turn_schema(row_id: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "row_id": {"type": "integer", "enum": [row_id]},
            "intent": {"type": "string", "enum": ["answer", "propose"]},
            "answer": {"type": ["string", "null"]},
            "no_evidence_found": {"type": ["boolean", "null"]},
            "proposed_value": {"type": ["string", "null"]},
            "reasoning": {"type": ["string", "null"]},
            "confidence": {
                "type": ["string", "null"],
                "enum": ["Strong", "Moderate", "Weak", None],
            },
        },
        "required": [
            "row_id",
            "intent",
            "answer",
            "no_evidence_found",
            "proposed_value",
            "reasoning",
            "confidence",
        ],
    }


def classification_schema(row_ids: list[int]) -> dict:
    return {
        "type": "object",
        "properties": {
            "classifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "row_id": {"type": "integer", "enum": row_ids},
                        "confidence": {
                            "type": "string",
                            "enum": ["Strong", "Moderate", "Weak"],
                        },
                        "reasoning": {"type": "string"},
                    },
                    "required": ["row_id", "confidence", "reasoning"],
                },
            }
        },
        "required": ["classifications"],
    }
