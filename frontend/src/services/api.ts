import type { Message, Status, Source } from "../types/chat";

const API_URL = import.meta.env.VITE_API_URL || "/api";

export async function getStatus(): Promise<Status> {
  const response = await fetch(`${API_URL}/status`);
  if (!response.ok) throw new Error("Backend unavailable");
  return response.json();
}

export async function chat(message: string, history: Message[]) {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      history: history.slice(-20).map((item) => ({ role: item.role, content: item.content })),
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "The assistant request failed");
  }
  return response.json() as Promise<{ answer: string; sources: Source[]; model?: string; fallback: boolean }>;
}
