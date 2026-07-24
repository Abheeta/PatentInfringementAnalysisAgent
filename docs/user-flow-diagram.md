# User Flow Diagram

> Visual companion to [user-flow-steps-rough-updated.md](./user-flow-steps-rough-updated.md). **Assistant** = the Qwen model.

```mermaid
flowchart TD
    Start(["Open app"]) --> Session["Session starts\n(resumes last session, or creates a new one)"]

    Session --> UploadChart["Upload Claim Chart\n(CSV: Claim Element / Evidence / AI Reasoning)"]
    UploadChart --> UploadEvidence["Upload Evidence\n(.txt files and/or URLs)"]
    UploadEvidence --> Generate["Click Generate"]

    Generate --> Classify["Assistant runs Initial Classification\n(Strong / Moderate / Weak)"]
    Classify --> Loaded["Claim Chart (left) + Chat (right) load,\nAssistant sends first message"]

    Loaded --> Working{"Analyst works the session"}

    Working -->|"Chat with Assistant"| Chat["Ask questions, reference a row,\nadjust instructions via Settings"]
    Chat --> Working

    Working -->|"Upload more evidence"| MoreEvidence["Add evidence\n(repeatable any time)"]
    MoreEvidence --> Working

    Working -->|"Assistant proposes an update"| Proposal["Pending proposal shown on chart cell"]
    Proposal --> Decision{"Accept, Reject,\nor Modify?"}
    Decision -->|"Accept"| Accept["Cell updates;\nprevious value saved to undo slot"]
    Decision -->|"Reject"| Reject["Cell reverts to current value;\nnothing saved to undo"]
    Decision -->|"Modify"| ModifyMsg["Analyst sends feedback in chat"]
    ModifyMsg --> Proposal
    Accept --> Working
    Reject --> Working

    Working -->|"No evidence found"| NoEvidence["Assistant asks for more evidence\ninstead of proposing a change"]
    NoEvidence --> MoreEvidence2["Analyst supplies new evidence\n(document or URL)"]
    MoreEvidence2 --> Retry["Assistant retries the proposal"]
    Retry --> Proposal

    Working -->|"Undo a row"| Undo["Confirm undo →\nrow reverts to previous value"]
    Undo --> Working

    Working -->|"Flag a row"| Flag["Assistant asks what's wrong,\noffers a correction"]
    Flag --> Working

    Working -->|"Export anytime after Generate"| Export(["Export to Word (.docx)\nsnapshot of current chart state"])
    Export --> Working

    Working -->|"Start a new session"| NewSession(["New Session\n(current session abandoned)"])
    NewSession --> Session
```

## Reading the diagram

- The **Analyst works the session** diamond is the hub — chat, chart edits, evidence uploads, undo, flagging, and export can all happen in any order, any number of times, once the chart is generated.
- **Accept / Reject / Modify** is the only cycle with a hard rule: every proposal (first or revised) needs an explicit Accept before it touches the chart.
- **No evidence found** is the one edge case that loops back into the main proposal flow rather than ending the session — new evidence leads the Assistant to retry.
