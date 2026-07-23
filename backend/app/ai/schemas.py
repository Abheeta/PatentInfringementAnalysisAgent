def disambiguation_schema(row_ids: list[int]) -> dict:
    return {
        "type": "object",
        "properties": {
            "row_id": {"type": ["integer", "null"], "enum": [*row_ids, None]},
            "needs_clarification": {"type": "boolean"},
            "question": {"type": ["string", "null"]},
        },
        "required": ["row_id", "needs_clarification", "question"],
    }


def proposal_schema(row_id: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "row_id": {"type": "integer", "enum": [row_id]},
            "no_evidence_found": {"type": "boolean"},
            "proposed_value": {"type": ["string", "null"]},
            "reasoning": {"type": ["string", "null"]},
            "confidence": {
                "type": ["string", "null"],
                "enum": ["Strong", "Moderate", "Weak", None],
            },
        },
        "required": [
            "row_id",
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
