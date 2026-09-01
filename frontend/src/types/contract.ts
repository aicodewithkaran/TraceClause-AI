export interface ClauseAnalysis {
  clause_number: number;
  clause_name: string;
  original_text: string;
  risk_level: 'High' | 'Medium' | 'Low';
  risk_explanation: string;
  suggested_counter_language: string;
  category?: string;
}

export interface AnalysisSummary {
  total_clauses: number;
  high_risks: number;
  medium_risks: number;
  low_risks: number;
  overall_risk_score: string;
}

export interface ContractAnalysisResponse {
  file_name: string;
  extracted_text: string;
  summary: AnalysisSummary;
  clauses: ClauseAnalysis[];
}

export interface DocumentExtractResponse {
  filename: string;
  file_type: string;
  char_count: number;
  clause_count: number;
  text_preview: string;
  extracted_text: string;
}

export interface ChatQueryRequest {
  contract_text: string;
  question: string;
  contract_id?: string;
}

export interface ChatQueryResponse {
  answer: string;
  citations: string[];
}
