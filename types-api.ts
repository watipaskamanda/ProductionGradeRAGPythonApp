// TypeScript Interfaces & API Types
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  metadata?: {
    sql?: string;
    plan?: Record<string, any>;
    chart_config?: ChartConfig;
    debug_info?: DebugInfo;
  };
}

export interface ChartConfig {
  type: 'bar_chart' | 'line_chart' | 'pie_chart';
  data: Record<string, number>;
  title: string;
  x_label: string;
  y_label: string;
  auto_detected?: boolean;
}

export interface DebugInfo {
  sql: string;
  plan: Record<string, any>;
  execution_steps: string[];
  validation_results: {
    passed: boolean;
    warnings: string[];
  };
  complexity_reason?: string;
}

export interface DBQueryRequest {
  question: string;
  chat_history: ChatMessage[];
  currency: 'MWK' | 'USD';
  debug_mode: boolean;
  user_level: 'business' | 'analyst' | 'developer';
}

export interface EnterpriseQueryResponse {
  question: string;
  answer: string;
  markdown_table?: string;
  chart_config?: ChartConfig;
  suggested_visualizations?: string[];
  metadata: {
    analysis_type: string;
    visualization_type: string;
    has_chart: boolean;
    complexity_score?: number;
    auto_debug_triggered?: boolean;
  };
  debug_info?: DebugInfo;
}

export interface DocumentQueryRequest {
  question: string;
  top_k: number;
}

export interface DocumentQueryResponse {
  answer: string;
  sources: string[];
  num_contexts: number;
}

export type AppMode = 'document' | 'database' | 'upload';
export type Currency = 'MWK' | 'USD';
export type UserLevel = 'business' | 'analyst' | 'developer';