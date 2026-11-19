import { useEffect, useRef, useState } from "react";
import { Building2, ChevronRight, CirclePlus, ExternalLink, Menu, Send, Sparkles, Trash2, X } from "lucide-react";
import { chat, getStatus } from "./services/api";
import type { Conversation, Message, Source, Status } from "./types/chat";

const STORAGE_KEY = "propertyiq.conversations.v1";

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isSource(value: unknown): value is Source {
  if (!isRecord(value)) return false;
  return typeof value.title === "string"
    && typeof value.url === "string"
    && typeof value.website === "string"
    && typeof value.relevance === "number"
    && typeof value.excerpt === "string";
}

function isMessage(value: unknown): value is Message {
  if (!isRecord(value)) return false;
  return typeof value.id === "string"
    && (value.role === "user" || value.role === "assistant")
    && typeof value.content === "string"
    && (value.sources === undefined || (Array.isArray(value.sources) && value.sources.every(isSource)))
    && (value.fallback === undefined || typeof value.fallback === "boolean");
}

function parseConversation(value: unknown): Conversation | null {
  if (!isRecord(value) || typeof value.id !== "string" || typeof value.title !== "string") return null;
  if (!Array.isArray(value.messages) || typeof value.updatedAt !== "number") return null;
  if (!value.messages.every(isMessage)) return null;
  return {
    id: value.id,
    title: value.title,
    messages: value.messages,
    updatedAt: value.updatedAt,
  };
}

function loadChatState(): ChatState {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return { conversations: [], activeConversationId: null };
    const parsed: unknown = JSON.parse(stored);
    if (!isRecord(parsed) || !Array.isArray(parsed.conversations)) {
      throw new Error("Stored conversation data has an invalid format");
    }

    const conversations = parsed.conversations
      .map(parseConversation)
      .filter((conversation): conversation is Conversation => conversation !== null)
      .sort((left, right) => right.updatedAt - left.updatedAt);
    const savedActiveId = parsed.activeConversationId;
    const activeConversationId = typeof savedActiveId === "string"
      && conversations.some((conversation) => conversation.id === savedActiveId)
      ? savedActiveId
      : conversations[0]?.id ?? null;

    return { conversations, activeConversationId };
  } catch (error) {
    console.error("Could not load saved conversations:", error);
    return { conversations: [], activeConversationId: null };
  }
}

function conversationTitle(message: string): string {
  const title = message.trim();
  return title.length > 38 ? `${title.slice(0, 38)}...` : title;
}

const suggestions = [
  "What are the latest publicly listed DarGlobal projects?",
  "Tell me about properties available in Riyadh.",
  "Compare two DarGlobal developments.",
  "What amenities are mentioned for projects?",
];

export default function App() {
  const [chatState, setChatState] = useState<ChatState>(loadChatState);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const conversationRef = useRef<HTMLElement>(null);
  const shouldAutoScroll = useRef(true);
  const { conversations, activeConversationId } = chatState;
  const activeConversation = conversations.find((item) => item.id === activeConversationId);
  const messages = activeConversation?.messages ?? [];
  const indexedSources = status?.source_websites ?? [];

  useEffect(() => {
    getStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(chatState));
    } catch (error) {
      console.error("Could not save conversations:", error);
    }
  }, [chatState]);

  useEffect(() => {
    const container = conversationRef.current;
    if (container && shouldAutoScroll.current) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  }, [messages, loading, activeConversationId]);

  function appendMessage(conversationId: string, message: Message, activate: boolean) {
    setChatState((current) => {
      const existing = current.conversations.find((item) => item.id === conversationId);
      const updated: Conversation = {
        id: conversationId,
        title: existing?.messages.length ? existing.title : conversationTitle(message.content),
        messages: [...(existing?.messages ?? []), message],
        updatedAt: Date.now(),
      };
      return {
        conversations: [updated, ...current.conversations.filter((item) => item.id !== conversationId)],
        activeConversationId: activate ? conversationId : current.activeConversationId,
      };
    });
  }

  async function sendMessage(text = input) {
    const value = text.trim();
    if (!value || loading) return;
    const conversationId = activeConversationId ?? crypto.randomUUID();
    const history = messages;
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content: value };
    shouldAutoScroll.current = true;
    appendMessage(conversationId, userMessage, true);
    setInput("");
    setLoading(true);
    try {
      const result = await chat(value, history);
      appendMessage(conversationId, {
        id: crypto.randomUUID(),
        role: "assistant",
        content: result.answer,
        sources: result.sources,
        fallback: result.fallback,
      }, false);
    } catch (error) {
      appendMessage(conversationId, {
        id: crypto.randomUUID(),
        role: "assistant",
        content: error instanceof Error ? error.message : "An unexpected error occurred.",
        fallback: true,
      }, false);
    } finally {
      setLoading(false);
    }
  }

  function startNewChat() {
    shouldAutoScroll.current = true;
    setChatState((current) => ({ ...current, activeConversationId: null }));
    setSidebarOpen(false);
  }

  function selectConversation(conversationId: string) {
    shouldAutoScroll.current = true;
    setChatState((current) => ({ ...current, activeConversationId: conversationId }));
    setSidebarOpen(false);
  }

  function deleteConversation(conversationId: string) {
    if (loading && conversationId === activeConversationId) return;
    if (conversationId === activeConversationId) shouldAutoScroll.current = true;
    setChatState((current) => {
      const remaining = current.conversations.filter((item) => item.id !== conversationId);
      return {
        conversations: remaining,
        activeConversationId: current.activeConversationId === conversationId
          ? remaining[0]?.id ?? null
          : current.activeConversationId,
      };
    });
  }

  function clearChat() {
    if (activeConversationId) deleteConversation(activeConversationId);
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Building2 size={21} /></div>
          <div><strong>PropertyIQ</strong><span>DarGlobal & Wasalt</span></div>
          <button className="icon-button close-sidebar" onClick={() => setSidebarOpen(false)} aria-label="Close sidebar"><X size={18} /></button>
        </div>
        <button className="new-chat" onClick={startNewChat}><CirclePlus size={18} /> New conversation</button>
        <div className="history">
          <p className="history-empty">Recent conversations</p>
          <div className="history-list">
            {conversations.map((conversation) => (
              <div
                key={conversation.id}
                className={`history-entry ${conversation.id === activeConversationId ? "active" : ""}`}
              >
                <button
                  className="history-item"
                  onClick={() => selectConversation(conversation.id)}
                  title={conversation.title}
                >
                  <span>{conversation.title}</span>
                </button>
                <button
                  className="delete-conversation"
                  onClick={() => deleteConversation(conversation.id)}
                  disabled={loading && conversation.id === activeConversationId}
                  aria-label={`Delete conversation: ${conversation.title}`}
                  title="Delete conversation"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        </div>
        <div className="system-status">
          <div><span className={`dot ${status ? "online" : "offline"}`} /> Backend <b>{status ? "Connected" : "Unavailable"}</b></div>
          <div><span className={`dot ${status?.knowledge_base === "ready" ? "online" : ""}`} /> Indexed <b title={indexedSources.join(", ") || "No indexed sources"}>{indexedSources.length ? `${indexedSources.join(", ")} (${status?.document_count ?? 0})` : "Empty"}</b></div>
          <div><span className={`dot ${status?.ai_model_configured ? "online" : ""}`} /> AI model <b>{status?.ai_model_configured ? "Configured" : "Not configured"}</b></div>
        </div>
      </aside>
      {sidebarOpen && <button className="backdrop" onClick={() => setSidebarOpen(false)} aria-label="Close menu" />}

      <main className="main-panel">
        <header>
          <button className="icon-button menu-button" onClick={() => setSidebarOpen(true)} aria-label="Open sidebar"><Menu size={20} /></button>
          <div className="title-block"><span>AI PROPERTY ASSISTANT</span><h1>Property intelligence</h1></div>
          {messages.length > 0 && <button className="clear-button" onClick={clearChat} disabled={loading}><Trash2 size={16} /> Clear chat</button>}
        </header>

        <section
          className="conversation"
          ref={conversationRef}
          onScroll={(event) => {
            const element = event.currentTarget;
            shouldAutoScroll.current = element.scrollHeight - element.scrollTop - element.clientHeight < 96;
          }}
        >
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon"><Sparkles size={28} /></div>
              <p className="eyebrow">PROPERTYIQ ASSISTANT</p>
              <h2>Explore exceptional properties<br />with confidence.</h2>
              <p className="welcome-copy">Ask about publicly available projects, locations, amenities, and property information from DarGlobal and Wasalt.</p>
              <div className="suggestions">
                {suggestions.map((suggestion) => (
                  <button key={suggestion} onClick={() => sendMessage(suggestion)}>
                    <span>{suggestion}</span><ChevronRight size={17} />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((message) => (
                <div key={message.id} className={`message ${message.role}`}>
                  {message.role === "assistant" && <div className="assistant-avatar"><Sparkles size={16} /></div>}
                  <div className="message-body">
                    <div className="message-text">{message.content}</div>
                    {message.sources && message.sources.length > 0 && (
                      <div className="sources">
                        <p>Sources</p>
                        {message.sources.map((source) => (
                          <a key={source.url} href={source.url} target="_blank" rel="noreferrer">
                            <span><b>{source.website}</b><small>{source.title}</small></span>
                            <ExternalLink size={15} />
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="message assistant">
                  <div className="assistant-avatar"><Sparkles size={16} /></div>
                  <div className="typing"><i /><i /><i /></div>
                </div>
              )}
            </div>
          )}
        </section>

        <footer className="composer">
          <div className="input-wrap">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask about properties, projects or locations..."
              rows={1}
            />
            <button onClick={() => sendMessage()} disabled={!input.trim() || loading} aria-label="Send message"><Send size={18} /></button>
          </div>
          <p>PropertyIQ uses publicly available sources and may not reflect current availability.</p>
        </footer>
      </main>
    </div>
  );
}
