export interface Source {
  title: string;
  url: string;
  website: string;
  relevance: number;
  excerpt: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  fallback?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  updatedAt: number;
}

export interface Status {
  backend: "ok";
  knowledge_base: "ready" | "empty";
  ai_model_configured: boolean;
  document_count: number;
  source_websites: string[];
}
