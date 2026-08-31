"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import ChatArea from "@/components/ChatArea";

export default function Home() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  // Restore activeSessionId on initial load or from URL ?session= parameter
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const sessionFromUrl = params.get("session");
      if (sessionFromUrl) {
        setActiveSessionId(sessionFromUrl);
        localStorage.setItem("activeSessionId", sessionFromUrl);
      } else {
        const saved = localStorage.getItem("activeSessionId");
        if (saved) {
          setActiveSessionId(saved);
        }
      }
    }
  }, []);

  const handleSelectSession = (id: string | null) => {
    setActiveSessionId(id);
    if (id) {
      localStorage.setItem("activeSessionId", id);
    } else {
      localStorage.removeItem("activeSessionId");
    }
  };

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <Sidebar
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
      />
      <main className="flex-1 flex flex-col min-w-0">
        <ChatArea
          activeSessionId={activeSessionId}
          onSessionCreated={handleSelectSession}
        />
      </main>
    </div>
  );
}

