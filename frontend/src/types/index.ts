export type ConfidenceTier = "Strong" | "Moderate" | "Weak";

export interface Row {
  id: number;
  claim_element: string;
  product_feature: string;
  ai_reasoning: string;
  confidence: ConfidenceTier | null;
  flagged: boolean;
  pending_value: string | null;
  pending_reasoning: string | null;
  pending_confidence: ConfidenceTier | null;
  previous_product_feature: string | null;
  previous_ai_reasoning: string | null;
  previous_confidence: ConfidenceTier | null;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  row_id: number | null;
  created_at: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
}

export class ApiError extends Error {
  code: string;

  constructor(body: ApiErrorBody) {
    super(body.message);
    this.code = body.code;
  }
}
