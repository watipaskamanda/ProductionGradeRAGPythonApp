// frontend/src/types/api.ts

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  metadata?: EnterpriseQueryResponse;
}

export interface EnterpriseQueryResponse {
  question: string;
  answer: string;
  markdown_table?: string;
  chart_config?: ChartConfig;
  suggested_visualizations?: string[];
  suggested_prompts?: string[];
  metadata: QueryMetadata;
  debug_info?: DebugInfo;
  // New fields for raw data table rendering
  raw_data?: {
    columns: string[];
    rows: any[][];
    total_count: number;
  };
}

export interface ChartConfig {
  type: 'bar_chart' | 'line_chart' | 'pie_chart' | 'table';
  data: { [key: string]: number | string };
  title: string;
  x_label: string;
  y_label: string;
}

export interface QueryMetadata {
  analysis_type: string;
  visualization_type: string;
  has_chart: boolean;
  complexity_score: number;
  auto_debug_triggered: boolean;
  // Additional metadata for table rendering
  row_count?: number;
  columns?: string[];
  tenant_id?: string;
  active_table?: string;
}

export interface DebugInfo {
  sql: string;
  plan: object;
  execution_steps: string[];
  validation_results: object;
  complexity_reason?: string;
}

export interface DBQueryRequest {
  question: string;
  chat_history?: { role: string; content: string }[];
  currency?: string;
  debug_mode?: boolean;
  user_level?: 'business' | 'analyst' | 'developer';
}
