import type { Message, Status, Source } from "../types/chat";

const configuredApiUrl = window.PROPERTYIQ_API_URL || import.meta.env.VITE_API_URL || "/api";
const API_URL = configuredApiUrl.replace(/\/+$/, "");

async function responseError(response: Response, fallback: string): Promise<Error> {
  const body = await response.json().catch(() => null);
  return new Error(typeof body?.detail === "string" ? body.detail : `${fallback} (HTTP ${response.status})`);
}

function networkError(error: unknown): Error {
  if (error instanceof TypeError) {
    return new Error("Cannot reach the PropertyIQ API. Check the deployed API URL and backend CORS settings.");
  }
  return error instanceof Error ? error : new Error("The assistant request failed");
}

export async function getStatus(): Promise<Status> {
  try {
    const response = await fetch(`${API_URL}/status`);
    if (!response.ok) throw await responseError(response, "Backend unavailable");
    return response.json();
  } catch (error) {
    throw networkError(error);
  }
}

export async function chat(message: string, history: Message[]) {
  try {
    const response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        history: history.slice(-20).map((item) => ({ role: item.role, content: item.content })),
      }),
    });
    if (!response.ok) throw await responseError(response, "The assistant request failed");
    return await response.json() as { answer: string; sources: Source[]; model?: string; fallback: boolean };
  } catch (error) {
    throw networkError(error);
  }
}
