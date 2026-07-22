# Lumenci Assistant — User Flow Diagram

Derived from the locked steps in `user-flow-steps.md`. Covers the main path (upload → setup → initial tagging → chat refinement loop → export) plus all edge-case branches (no evidence found, flagged-incorrect evidence, undo, mid-session system-prompt edit), each re-entering the central chat loop rather than dead-ending.

```mermaid
flowchart TD
    Start([Start]) --> Upload["1. Upload claim chart (.csv) + evidence docs (.txt)"]
    Upload --> Split["2. Split view loads: chart (left) + chat (right)"]
    Split --> Setup["3. Setup screen: analyst edits freeform instructions (hidden baseline always applies)"]
    Setup --> CloseSetup["4. Analyst closes setup"]
    CloseSetup --> InitialPass["5. AI reasoning pass: tags every row with a confidence tier"]
    InitialPass --> Opening["6. AI posts opening message flagging Weak/Moderate rows"]
    Opening --> Loop[[Chat Loop]]

    Loop --> SendMsg["7. Analyst sends a message (row click optional)"]
    SendMsg --> RefCheck{"8. AI confident which row?"}
    RefCheck -- No --> Clarify["AI asks a clarifying question"] --> Loop
    RefCheck -- Yes --> Propose["9. AI proposes a change based on the message"]

    Propose --> EvidenceCheck{"Evidence found?"}
    EvidenceCheck -- No --> AskEvidence["15. AI asks for more evidence: re-upload doc or URL"]
    AskEvidence --> SupplyEvidence["16. Analyst supplies a doc or URL"]
    SupplyEvidence --> ProcessEvidence["Backend ingests doc, or fetches+extracts URL, as new evidence source"]
    ProcessEvidence --> Propose

    EvidenceCheck -- Yes --> Pending["10. Pending edit shown in chart cell: Accept / Reject / Modify"]
    Pending -- Accept --> Apply["11. Chart updates; previous value saved as the undo slot"] --> Loop
    Pending -- Reject --> Discard["12. Chart reverts to current value; pending clears"] --> Loop
    Pending -- Modify --> ModifyChip["13. @Row chip inserted into chat; analyst gives feedback"] --> Propose

    Loop --> UndoClick["14. Analyst clicks Undo on a row"]
    UndoClick --> UndoConfirm{"Confirm undo?"}
    UndoConfirm -- Yes --> Revert["Row reverts to previous value; undo slot cleared"] --> Loop
    UndoConfirm -- No --> Loop

    Loop --> FlagClick["18. Analyst clicks the flag-evidence-incorrect icon on a row"]
    FlagClick --> Rescan["Backend re-scans the actual doc/URL text for that claim element"]
    Rescan --> FlagChip["19. @Row chip appears in chat; analyst describes the issue"]
    FlagChip --> Correction["AI's correction quotes the exact source line found"]
    Correction --> Pending

    Loop --> SettingsClick["Analyst opens settings: edits the freeform system prompt"]
    SettingsClick --> SettingsApply["Applies to subsequent turns only; chat history and chart are untouched"] --> Loop

    Loop --> ExportClick["20. Analyst clicks Export (always available, no precondition)"]
    ExportClick --> Generate["Backend generates .docx from the chart's current state (pending cells export as their current, unaccepted value)"]
    Generate --> Download["Download file"] --> End([End])
```
