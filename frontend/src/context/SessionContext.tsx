import {
  createContext,
  Dispatch,
  ReactNode,
  useContext,
  useReducer,
} from "react";
import { ChatMessage, Row } from "../types";

export interface SessionState {
  sessionId: string | null;
  chartUploaded: boolean;
  generated: boolean;
  chart: { rows: Row[] };
  chatMessages: ChatMessage[];
  pendingRowId: number | null;
  systemPromptDraft: string;
}

const initialState: SessionState = {
  sessionId: null,
  chartUploaded: false,
  generated: false,
  chart: { rows: [] },
  chatMessages: [],
  pendingRowId: null,
  systemPromptDraft: "",
};

export type SessionAction =
  | { type: "SESSION_CREATED"; sessionId: string }
  | { type: "CHART_UPLOADED" }
  | { type: "EVIDENCE_UPLOADED" }
  | { type: "GENERATED"; openingMessage: ChatMessage }
  | { type: "CHART_REFRESHED"; rows: Row[] }
  | { type: "MESSAGE_SENT"; message: ChatMessage }
  | { type: "MESSAGE_RECEIVED"; message: ChatMessage }
  | { type: "ROW_CHIP_STAGED"; rowId: number | null }
  | { type: "SYSTEM_PROMPT_SAVED"; text: string };

function reducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case "SESSION_CREATED":
      return { ...state, sessionId: action.sessionId };
    case "CHART_UPLOADED":
      return { ...state, chartUploaded: true };
    case "EVIDENCE_UPLOADED":
      return state;
    case "GENERATED":
      return {
        ...state,
        generated: true,
        chatMessages: [...state.chatMessages, action.openingMessage],
      };
    case "CHART_REFRESHED":
      return { ...state, chart: { rows: action.rows } };
    case "MESSAGE_SENT":
      return { ...state, chatMessages: [...state.chatMessages, action.message] };
    case "MESSAGE_RECEIVED":
      return {
        ...state,
        chatMessages: [...state.chatMessages, action.message],
        pendingRowId: null,
      };
    case "ROW_CHIP_STAGED":
      return { ...state, pendingRowId: action.rowId };
    case "SYSTEM_PROMPT_SAVED":
      return { ...state, systemPromptDraft: action.text };
    default:
      return state;
  }
}

const StateContext = createContext<SessionState>(initialState);
const DispatchContext = createContext<Dispatch<SessionAction>>(() => {});

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <StateContext.Provider value={state}>
      <DispatchContext.Provider value={dispatch}>
        {children}
      </DispatchContext.Provider>
    </StateContext.Provider>
  );
}

export function useSessionState() {
  return useContext(StateContext);
}

export function useSessionDispatch() {
  return useContext(DispatchContext);
}
