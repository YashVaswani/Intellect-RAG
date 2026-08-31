"use client";

import { useState, useEffect, useRef } from "react";
import ChatInput from "./ChatInput";
import ChatMessage from "./ChatMessage";

interface ChatAreaProps {
  activeSessionId: string | null;
  onSessionCreated?: (id: string) => void;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
  sources?: any[];
  token_display?: string;
  model_used?: string;
  elapsed?: number;
}

export default function ChatArea({ activeSessionId, onSessionCreated }: ChatAreaProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [model, setModel] = useState("gemini-2.5-flash");
  const [isSending, setIsSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Format date timestamp cleanly
  const formatTime = (raw?: string) => {
    if (!raw) {
      return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: true });
    }
    try {
      const dateObj = new Date(raw.includes("Z") || raw.includes("+") ? raw : raw + "Z");
      if (isNaN(dateObj.getTime())) return raw;
      return dateObj.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: true });
    } catch {
      return raw;
    }
  };

  // Load messages when session changes
  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }

    const fetchMessages = async () => {
      try {
        const res = await fetch(`/api/chat/sessions/${activeSessionId}`);
        if (res.ok) {
          const data = await res.json();
          const formatted = data.messages.map((m: any, idx: number) => ({
            id: idx.toString(),
            role: m.role,
            content: m.content,
            timestamp: formatTime(m.timestamp),
            sources: m.sources,
            model_used: m.model_used,
            token_display: m.token_usage ? `${m.token_usage.total_tokens || 0} tokens` : undefined,
          }));
          setMessages(formatted);
        }
      } catch (err) {
        console.error("Failed to fetch messages", err);
      }
    };
    fetchMessages();
  }, [activeSessionId]);

  const handleSendMessage = async (text: string) => {
    const currentTimeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: true });

    const newUserMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: text,
      timestamp: currentTimeStr,
    };
    setMessages((prev) => [...prev, newUserMsg]);
    setIsSending(true);

    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      currentSessionId = "session_" + Date.now() + "_" + Math.random().toString(36).substring(7);
    }

    // Optimistic "thinking" placeholder
    const thinkingId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      { id: thinkingId, role: "assistant", content: "...", timestamp: currentTimeStr },
    ]);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: text,
          session_id: currentSessionId,
          model: model,
          stream: false,
        }),
      });

      if (!response.ok) throw new Error("Backend returned " + response.status);

      const data = await response.json();
      const respTimeStr = data.timestamp || new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: true });

      setMessages((prev) =>
        prev.map((m) =>
          m.id === thinkingId
            ? {
                id: thinkingId,
                role: "assistant",
                content: data.answer,
                timestamp: respTimeStr,
                sources: data.sources,
                model_used: data.model_used,
                token_display: data.token_display,
                elapsed: data.elapsed,
              }
            : m
        )
      );

      if (!activeSessionId && onSessionCreated) {
        onSessionCreated(currentSessionId);
      }
    } catch (error) {
      console.error(error);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === thinkingId
            ? {
                id: thinkingId,
                role: "assistant",
                content: "⚠️ Sorry, I couldn't connect to the backend. Make sure FastAPI is running on port 8000.",
                timestamp: currentTimeStr,
                model_used: "Error",
              }
            : m
        )
      );
    } finally {
      setIsSending(false);
    }
  };

  const modelLabel: Record<string, string> = {
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "llama-3.3-70b-versatile": "Llama 3.3 70B",
    "qwen-qwq-32b": "Qwen QWQ 32B",
    "deepseek-r1-distill-llama-70b": "DeepSeek R1 70B",
  };

  return (
    <div className="flex flex-col h-full bg-background relative">
      {/* Header */}
      <header className="h-14 flex items-center justify-between px-4 md:px-6 border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <div className="w-8 md:hidden" />
          <h1 className="text-lg font-semibold text-foreground">
            {activeSessionId ? "Chat" : "New Chat"}
          </h1>
        </div>

        {/* Model Selector */}
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="bg-card border border-border text-foreground text-sm rounded-md px-3 py-1.5 outline-none focus:ring-1 focus:ring-ring"
        >
          <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
          <option value="llama-3.3-70b-versatile">Llama 3.3 70B</option>
          <option value="qwen-qwq-32b">Qwen QWQ 32B</option>
          <option value="deepseek-r1-distill-llama-70b">DeepSeek R1 70B</option>
        </select>
      </header>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8 scroll-smooth">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto pb-20">
            <div className="w-16 h-16 bg-primary rounded-2xl flex items-center justify-center mb-6 shadow-lg shadow-primary/20">
              <span className="text-3xl text-primary-foreground font-bold">R</span>
            </div>
            <h2 className="text-2xl font-bold text-foreground mb-2">How can I help you today?</h2>
            <p className="text-muted-foreground text-sm">
              I can search your enterprise knowledge base, answer questions, and help analyze documents.
            </p>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto space-y-8 pb-10">
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                timestamp={msg.timestamp}
                sources={msg.sources}
                modelUsed={msg.model_used}
                tokenDisplay={msg.token_display}
                elapsed={msg.elapsed}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-4 md:p-6 bg-gradient-to-t from-background via-background to-transparent pt-10">
        <div className="max-w-4xl mx-auto">
          <ChatInput onSend={handleSendMessage} disabled={isSending} />
          <p className="text-center text-xs text-muted-foreground mt-3">
            Intellect RAG can make mistakes. Verify important information.
          </p>
        </div>
      </div>
    </div>
  );
}
