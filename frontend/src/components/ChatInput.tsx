"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Paperclip, Mic } from "lucide-react";
import VoiceInputModal from "./VoiceInputModal";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [showVoiceModal, setShowVoiceModal] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // Auto-focus after send/modal close
  useEffect(() => {
    if (!disabled && !showVoiceModal && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [disabled, showVoiceModal]);

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input);
      setInput("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.focus();
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.nativeEvent.isComposing) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const formData = new FormData();
    for (let i = 0; i < e.target.files.length; i++) {
      formData.append("files", e.target.files[i]);
    }
    try {
      const res = await fetch("/api/documents/upload", {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        alert("File uploaded and ingested successfully! You can now ask questions about it.");
      } else {
        alert("Upload failed.");
      }
    } catch (error) {
      console.error(error);
      alert("Upload error.");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
      textareaRef.current?.focus();
    }
  };

  const handleVoiceTranscript = (text: string) => {
    setInput(prev => prev ? `${prev} ${text}` : text);
  };

  return (
    <>
      {/* Voice Recording Modal */}
      {showVoiceModal && (
        <VoiceInputModal
          onClose={() => setShowVoiceModal(false)}
          onTranscript={handleVoiceTranscript}
        />
      )}

      <div className="relative rounded-2xl border border-border bg-card shadow-sm overflow-hidden focus-within:ring-1 focus-within:ring-ring focus-within:border-ring transition-all">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message Intellect Assistant..."
          className="w-full max-h-[200px] resize-none bg-transparent py-4 pl-4 pr-12 text-foreground placeholder:text-muted-foreground focus:outline-none scrollbar-thin text-base"
          rows={1}
          disabled={disabled}
        />

        {/* Hidden File Input for Documents */}
        <input
          type="file"
          multiple
          className="hidden"
          ref={fileInputRef}
          onChange={handleFileUpload}
          accept=".pdf,.docx,.xlsx,.pptx,.txt,.csv,.md"
        />

        {/* Bottom Action Bar */}
        <div className="flex items-center justify-between px-3 pb-3">
          <div className="flex items-center gap-2">
            {/* Document upload */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-muted-foreground hover:text-foreground rounded-full hover:bg-secondary transition-colors"
              title="Attach File to Knowledge Base"
            >
              <Paperclip size={18} />
            </button>

            {/* Live voice recording */}
            <button
              type="button"
              onClick={() => setShowVoiceModal(true)}
              disabled={disabled}
              className="p-2 text-muted-foreground hover:text-foreground rounded-full hover:bg-secondary transition-colors disabled:opacity-50"
              title="Voice Input — Live Recording"
            >
              <Mic size={18} />
            </button>
          </div>

          <button
            onClick={handleSend}
            disabled={!input.trim() || disabled}
            className={`p-2 rounded-xl flex items-center justify-center transition-colors ${
              input.trim() && !disabled
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "bg-secondary text-muted-foreground cursor-not-allowed"
            }`}
          >
            <Send size={18} className={input.trim() && !disabled ? "mr-[-2px]" : ""} />
          </button>
        </div>
      </div>
    </>
  );
}
