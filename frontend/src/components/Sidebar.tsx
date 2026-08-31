"use client";
import { useState, useEffect } from "react";
import {
  MessageSquare,
  Plus,
  Settings,
  Database,
  Menu,
  X,
  Trash2,
  Share2,
  Check,
  Pencil,
} from "lucide-react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";

interface SidebarProps {
  activeSessionId?: string | null;
  onSelectSession?: (id: string | null) => void;
}

interface Session {
  id: string;
  title: string;
  pinned?: number;
}

export default function Sidebar({ activeSessionId, onSelectSession }: SidebarProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [copiedSessionId, setCopiedSessionId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>("");
  const router = useRouter();
  const pathname = usePathname();

  const fetchSessions = async () => {
    try {
      const res = await fetch("/api/chat/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [activeSessionId]);

  const handleNewChat = () => {
    localStorage.removeItem("activeSessionId");
    if (onSelectSession) onSelectSession(null);
    if (pathname !== "/") {
      router.push("/");
    }
    if (window.innerWidth < 768) setIsOpen(false);
  };

  const handleSelect = (id: string) => {
    if (editingSessionId) return;
    localStorage.setItem("activeSessionId", id);
    if (onSelectSession) onSelectSession(id);
    if (pathname !== "/") {
      router.push("/");
    }
    if (window.innerWidth < 768) setIsOpen(false);
  };

  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this chat session?")) return;

    try {
      const res = await fetch(`/api/chat/sessions/${id}`, { method: "DELETE" });
      if (res.ok) {
        if (activeSessionId === id) {
          localStorage.removeItem("activeSessionId");
          if (onSelectSession) onSelectSession(null);
        }
        fetchSessions();
      }
    } catch (err) {
      console.error("Failed to delete session", err);
    }
  };

  const handleShareSession = async (e: React.MouseEvent, session: Session) => {
    e.stopPropagation();
    try {
      const shareUrl = `${window.location.origin}/?session=${session.id}`;
      await navigator.clipboard.writeText(shareUrl);
      setCopiedSessionId(session.id);
      setTimeout(() => setCopiedSessionId(null), 2000);
    } catch (err) {
      console.error("Failed to copy share link", err);
    }
  };

  const handleStartRename = (e: React.MouseEvent, session: Session) => {
    e.stopPropagation();
    setEditingSessionId(session.id);
    setEditingTitle(session.title);
  };

  const handleSaveRename = async (id: string) => {
    if (!editingTitle.trim()) {
      setEditingSessionId(null);
      return;
    }
    try {
      const res = await fetch(`/api/chat/sessions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: editingTitle.trim() }),
      });
      if (res.ok) {
        setEditingSessionId(null);
        fetchSessions();
      }
    } catch (err) {
      console.error("Failed to rename session", err);
    }
  };

  return (
    <>
      {/* Mobile Menu Toggle */}
      <button
        className="md:hidden fixed top-4 left-4 z-50 p-2 rounded-md bg-card border border-border text-foreground shadow-sm"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Sidebar Container */}
      <div
        className={`fixed md:static inset-y-0 left-0 z-40 flex flex-col h-full bg-[#111111] w-[260px] text-primary-foreground transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        {/* Logo / App Name — Clicking returns to Home New Chat */}
        <div
          onClick={handleNewChat}
          className="px-4 pt-5 pb-3 flex items-center gap-2 cursor-pointer group"
        >
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center flex-shrink-0 group-hover:scale-105 transition-transform">
            <span className="text-base text-primary-foreground font-bold">R</span>
          </div>
          <span className="text-sm font-semibold text-white group-hover:text-primary transition-colors">Intellect RAG</span>
        </div>

        {/* New Chat Button */}
        <div className="px-4 pb-3">
          <button
            onClick={handleNewChat}
            className="flex items-center gap-2 w-full px-3 py-2.5 rounded-md bg-transparent border border-gray-700 hover:bg-gray-800 transition-colors"
          >
            <Plus size={16} />
            <span className="text-sm font-medium">New Chat</span>
          </button>
        </div>

        {/* Chat History List */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5 scrollbar-thin">
          <div className="px-2 py-1 mb-1 flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Recent Chats</span>
          </div>

          {sessions.length === 0 ? (
            <div className="px-2 py-4 text-xs text-gray-500 italic text-center">No chats yet — start a new one!</div>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => handleSelect(session.id)}
                className={`group flex items-center justify-between w-full px-2.5 py-2 rounded-md transition-colors cursor-pointer ${
                  activeSessionId === session.id ? "bg-gray-800 text-white" : "hover:bg-gray-800/60 text-gray-400 hover:text-white"
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  <MessageSquare
                    size={15}
                    className={activeSessionId === session.id ? "text-white flex-shrink-0" : "text-gray-500 flex-shrink-0 group-hover:text-gray-300"}
                  />
                  {editingSessionId === session.id ? (
                    <input
                      type="text"
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleSaveRename(session.id);
                        if (e.key === "Escape") setEditingSessionId(null);
                      }}
                      onBlur={() => handleSaveRename(session.id)}
                      autoFocus
                      className="bg-gray-900 text-white text-sm px-1.5 py-0.5 rounded border border-primary outline-none w-full"
                    />
                  ) : (
                    <span className="text-sm truncate font-normal">
                      {session.title}
                    </span>
                  )}
                </div>

                {/* Session Action Buttons (Rename, Share & Delete) */}
                {editingSessionId !== session.id && (
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => handleStartRename(e, session)}
                      title="Rename chat"
                      className="p-1 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      onClick={(e) => handleShareSession(e, session)}
                      title="Share chat link"
                      className="p-1 rounded text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
                    >
                      {copiedSessionId === session.id ? (
                        <Check size={13} className="text-green-400" />
                      ) : (
                        <Share2 size={13} />
                      )}
                    </button>
                    <button
                      onClick={(e) => handleDeleteSession(e, session.id)}
                      title="Delete chat"
                      className="p-1 rounded text-gray-400 hover:text-red-400 hover:bg-gray-700 transition-colors"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Bottom Actions */}
        <div className="p-3 border-t border-gray-800 space-y-0.5">
          <Link href="/knowledge" className="flex items-center gap-3 w-full px-2 py-2.5 rounded-md hover:bg-gray-800 transition-colors text-left text-gray-400">
            <Database size={16} />
            <span className="text-sm font-medium">Knowledge Base</span>
          </Link>
          <Link href="/admin" className="flex items-center gap-3 w-full px-2 py-2.5 rounded-md hover:bg-gray-800 transition-colors text-left text-gray-400">
            <Settings size={16} />
            <span className="text-sm font-medium">Admin Panel</span>
          </Link>
        </div>
      </div>

      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="md:hidden fixed inset-0 z-30 bg-black/50"
          onClick={() => setIsOpen(false)}
        />
      )}
    </>
  );
}


