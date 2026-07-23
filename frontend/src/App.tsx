import { useEffect, useState } from "react";
import { createSession, getChart, getChatHistory, getSystemPrompt } from "./api/client";
import { ApiError } from "./types";
import { useSessionDispatch, useSessionState } from "./context/SessionContext";
import { MainScreen } from "./components/MainScreen";
import { Button } from "./components/ui/button";
import { TooltipProvider } from "./components/ui/tooltip";

export const SESSION_STORAGE_KEY = "sessionId";

async function startNewSession(): Promise<string> {
  const { session_id } = await createSession();
  localStorage.setItem(SESSION_STORAGE_KEY, session_id);
  return session_id;
}

async function restoreSession(sessionId: string) {
  let chartUploaded = true;
  let rows: Awaited<ReturnType<typeof getChart>>["rows"] = [];
  try {
    ({ rows } = await getChart(sessionId));
  } catch (err) {
    if (err instanceof ApiError && err.code === "chart_not_uploaded") {
      chartUploaded = false;
    } else {
      throw err;
    }
  }

  const { messages } = await getChatHistory(sessionId);

  return { chartUploaded, generated: messages.length > 0, rows, chatMessages: messages };
}

function App() {
  const state = useSessionState();
  const dispatch = useSessionDispatch();
  const [initializing, setInitializing] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);

  useEffect(() => {
    async function initSession() {
      try {
        const existing = localStorage.getItem(SESSION_STORAGE_KEY);
        let sessionId: string;
        let systemPrompt: string;

        if (existing) {
          try {
            // Doubles as a side-effect-free probe: confirms the backend
            // still knows this session before trusting localStorage's copy
            // (e.g. after a dev-db reset, the stored id can point at a
            // session that no longer exists, which otherwise 404s on
            // every subsequent call with no recovery path).
            ({ system_prompt: systemPrompt } = await getSystemPrompt(existing));
            sessionId = existing;
          } catch (err) {
            if (err instanceof ApiError && err.code === "session_not_found") {
              sessionId = await startNewSession();
              ({ system_prompt: systemPrompt } = await getSystemPrompt(sessionId));
            } else {
              throw err;
            }
          }
        } else {
          sessionId = await startNewSession();
          ({ system_prompt: systemPrompt } = await getSystemPrompt(sessionId));
        }

        dispatch({ type: "SESSION_CREATED", sessionId });
        dispatch({ type: "SYSTEM_PROMPT_LOADED", text: systemPrompt });

        const restored = await restoreSession(sessionId);
        dispatch({ type: "STATE_RESTORED", ...restored });
      } catch (err) {
        setInitError(
          err instanceof Error
            ? err.message
            : "Could not reach the backend. Is it running?"
        );
      } finally {
        setInitializing(false);
      }
    }
    initSession();
  }, [dispatch]);

  if (initError) {
    return (
      <div className="flex h-screen items-center justify-center bg-background p-6">
        <div className="flex max-w-sm flex-col items-center gap-3 text-center">
          <p role="alert" className="text-sm text-muted-foreground">
            Failed to start session: {initError}
          </p>
          <Button onClick={() => window.location.reload()}>Retry</Button>
        </div>
      </div>
    );
  }

  if (initializing || !state.sessionId) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={200}>
      <MainScreen />
    </TooltipProvider>
  );
}

export default App;
