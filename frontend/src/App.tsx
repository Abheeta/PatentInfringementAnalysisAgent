import { useEffect, useState } from "react";
import { createSession, getSystemPrompt } from "./api/client";
import { ApiError } from "./types";
import { useSessionDispatch, useSessionState } from "./context/SessionContext";
import { MainScreen } from "./components/MainScreen";
import { Button } from "./components/ui/button";
import { TooltipProvider } from "./components/ui/tooltip";

const SESSION_STORAGE_KEY = "sessionId";

async function startNewSession(): Promise<string> {
  const { session_id } = await createSession();
  localStorage.setItem(SESSION_STORAGE_KEY, session_id);
  return session_id;
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

        if (existing) {
          try {
            // Lightweight, side-effect-free probe: confirms the backend
            // still knows this session before trusting localStorage's copy
            // (e.g. after a dev-db reset, the stored id can point at a
            // session that no longer exists, which otherwise 404s on
            // every subsequent call with no recovery path).
            await getSystemPrompt(existing);
            sessionId = existing;
          } catch (err) {
            if (err instanceof ApiError && err.code === "session_not_found") {
              sessionId = await startNewSession();
            } else {
              throw err;
            }
          }
        } else {
          sessionId = await startNewSession();
        }

        dispatch({ type: "SESSION_CREATED", sessionId });
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
