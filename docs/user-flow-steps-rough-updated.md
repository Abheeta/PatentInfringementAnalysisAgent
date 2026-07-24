# User Flow

> **Assistant** refers to the Qwen model powering the app's analysis and chat.

1. **Session starts.** Opening the app loads the latest pre-existing session from the DB if any, if there are no sessions in the DB, a new session is created and started; every subsequent action (upload, generate, chat, export) is scoped to this session.

2. **Upload claim chart.** The Analyst can get started by uploading a the Claim Chart using "Upload Claim Chart" and uploads a CSV — a 3-column file (Patent Claim Element / Accused Product Feature (Evidence) / AI Reasoning).

3. **Upload Evidence.** Analyst clicks "Upload Evidence" and selects one or more `.txt` files and/or supplies a link. This action is repeatable — the analyst can add more sources in additional batches.

4. **Generate.** Once the Claim Chart and Evidence is uploaded, the Analyst clicks on Generate, that triggers an Initial Classification Analysis by the Assistant.

5. **Initial Classification.** The uploaded Claim Chart and Evidence is sent to the Assistant which compares the Claim Element and Evidence and classifies its first analysis on whether the evidence is Strong, Moderate or Weak.

6. **Chat Interface and Claim Chart Interface.** Once the Analyst has hit Generate, the Assistant returns the classified chart and the Screen loads the Claim Chart with Classification in the left panel and on the right panel, the Chat Box loads with the Assistant triggering the first message.

7. **System Prompt.** A baseline system prompt (hidden) is already set that instructs the Assistant to perform initial classification, and handle edge cases like asking the analyst to upload missing evidence, asking the analyst to specify the particular row they're referring to, and to propose updates to the AI reasoning column and Evidence if needed and also instructions on what to do if the analyst finds that the AI is giving the wrong evidence.

8. **Chat Interactions.**

   - **Editable Analyst Prompt.** On top of the baseline system prompt that is hidden, the Analyst can choose to provide additional instructions, which appends to the existing System Prompt, using the Settings button. This is completely optional.
   - **Sending a Message.** The Analyst can chat with the Assistant in various ways.
     - They can ask clarifying questions about the chart/evidence uploaded.
     - The Analyst can ask questions about a particular row by clicking on the row in the Chart UI. This inserts a Row ID chip to the conversation, much like how you can @mention someone in Slack.
     - The Analyst can simply chat with the Assistant, improving their understanding of the particular patent.
   - **Uploading further evidence.** The Analyst can upload more evidence as txt or URL.
   - **Export.** An "Export to Word" action is always available once Generate has run, with no other precondition — the analyst does not need to resolve pending proposals first. Export generates a `.docx` from the chart's exact current state at that moment; any pending (not-yet-accepted) cell exports as its current, unaccepted value, same as if no proposal had been made on it.

9. **Chart Interactions.** The Analyst can interact with the Chart Interface in the following flows:

   - **Select a Row.** The Analyst can select a row which inserts the row id chip in the chat.
   - **Accept/Reject/Modify Proposal.** When the Assistant proposes an update, the proposal is shown as a pending edit directly in that row's chart cell and the Analyst can accept, reject, or modify the proposal.
     - **Accept.** The chart cell updates to the new value; the row's previous value is saved as the single undo slot; the pending state clears.
     - **Reject.** The chart cell reverts to showing the current (unchanged) value; the pending state clears; nothing is saved to the undo slot since nothing was applied.
     - **Modify.** Clicking Modify inserts that row's `@Row` chip into the chat input; the analyst then types their feedback/instructions as a normal chat message (same mechanic as directly clicking a row). The AI's revised proposal goes back into the same pending state on the chart — it requires another explicit Accept (or Reject/Modify again) before it touches the chart. Every proposal, first or revised, always requires explicit Accept; there is no "auto-apply after Modify" behavior.
   - **Undo.** A persistent button next to every row, enabled whenever a previous applied (accepted) value exists for that row, disabled/no-op otherwise. Clicking Undo shows a confirmation prompt; confirming reverts the row to its previous value and clears the undo slot (single-step undo — a second consecutive undo has nothing left to revert to).
   - **Flag an AI Reasoning/Wrong Evidence.** The Analyst can flag a row which triggers the Assistant to ask what was wrong with the row and offer corrections once the Analyst answers.

10. **No evidence found (edge case).** Instead of proposing a change, the AI states it found no supporting evidence in the uploaded docs for that row and asks the analyst, in chat, for more evidence — either re-uploading an evidence document or providing a URL.

11. **New evidence supplied.** The analyst re-uploads a document or provides a URL (same "Upload Evidence" action/endpoint as step 3, usable again mid-session). A re-uploaded document is ingested as text; a URL is fetched by the backend (HTTP GET + HTML-to-text extraction, single page, no crawling/JS rendering). Either way, the result is treated as a new evidence source, added to the session's evidence pool.

12. **AI retries the proposal.** With the new evidence source available, the AI attempts the proposal again — re-entering the normal pending flow (step 9).

13. **Start a New Session.** If the Analyst wants to abandon the current session and start a fresh one, they can do so by clicking on New Session.
