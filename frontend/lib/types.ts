export type AppMode = "fixed" | "adaptive" | "temporal";

export interface SelectionStepEvent {
  type: "selection_step";
  step: number;
  sentence_id: string;
  sentence_text: string;
  source_doc: string;
  source_line: number;
  ot_cost: number;
  marginal_gain: number;
  coverage_pct: number;
  cumulative_tokens: number;
}

export interface SaturationEvent {
  type: "saturation_reached";
  step: number;
  final_ot_cost: number;
  final_coverage_pct: number;
  total_sentences_selected: number;
  total_tokens: number;
  stopping_reason: string;
}

export interface LLMTokenEvent {
  type: "llm_token";
  token: string;
}

export interface AnswerCompleteEvent {
  type: "answer_complete";
  answer: string;
  context_sentences: string[];
  total_context_tokens: number;
}

export type SSEEvent =
  | SelectionStepEvent
  | SaturationEvent
  | LLMTokenEvent
  | AnswerCompleteEvent
  | { type: "stream_error"; detail: string };

export interface SessionState {
  sessionId: string | null;
  documents: Array<{ filename: string; num_sentences: number }>;
  totalSentences: number;
}

export interface QueryState {
  status: "idle" | "encoding" | "selecting" | "answering" | "complete" | "error";
  steps: SelectionStepEvent[];
  saturation: SaturationEvent | null;
  answerTokens: string[];
  answer: string;
  contextSentences: string[];
}

export interface ComparisonResult {
  selected_sentences: Array<{
    sentence_text: string;
    source_doc: string;
    cosine_similarity: number;
  }>;
  total_tokens: number;
  internal_redundancy: number;
  llm_answer: string;
}

export interface DemoScenario {
  id: string;
  title: string;
  description: string;
  domain: string;
  query: string;
  optimal_mode: AppMode;
}

export interface QueryParams {
  epsilon: number;
  patience: number;
  k_max: number;
  k: number;
}

export interface SessionSummary {
  session_id: string;
  title: string;
  documents: string[];
  turn_count: number;
  created_at: string;
  updated_at: string;
}