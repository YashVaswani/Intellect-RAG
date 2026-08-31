"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Sparkles, FileText, Globe, Clock, Zap } from "lucide-react";

interface Source {
  source_file: string;
  page_number?: string;
  type?: string;
}

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
  sources?: Source[];
  modelUsed?: string;
  tokenDisplay?: string;
  elapsed?: number;
}

export default function ChatMessage({ 
  role, 
  content, 
  timestamp,
  sources, 
  modelUsed, 
  tokenDisplay,
  elapsed 
}: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <div className={`flex gap-4 md:gap-6 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-1 ${
        isUser ? "bg-secondary text-secondary-foreground" : "bg-primary text-primary-foreground"
      }`}>
        {isUser ? <User size={18} /> : <Sparkles size={18} />}
      </div>

      {/* Message Content */}
      <div className={`flex flex-col gap-2 max-w-[85%] ${isUser ? "items-end" : "items-start"}`}>
        <div className={`px-4 py-3 rounded-2xl ${
          isUser 
            ? "bg-secondary text-secondary-foreground rounded-tr-sm" 
            : "bg-transparent text-foreground"
        }`}>
          {isUser ? (
            <div className="whitespace-pre-wrap">{content}</div>
          ) : (
            <div className="prose prose-invert max-w-none prose-p:leading-relaxed prose-pre:bg-[#1e1e1e] prose-pre:border prose-pre:border-border">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* User Message Timestamp */}
        {isUser && timestamp && (
          <div className="flex items-center gap-1 text-[11px] text-muted-foreground/70 px-1">
            <Clock size={10} />
            <span>{timestamp}</span>
          </div>
        )}

        {/* Assistant Metadata (Sources, Timestamp, Model, Tokens) */}
        {!isUser && (
          <div className="flex flex-col gap-3 mt-2 w-full">
            {/* Sources List (Deduplicated & Clean) */}
            {(() => {
              if (!sources || sources.length === 0) return null;
              
              // Deduplicate sources by (file_name, page_number)
              const seen = new Set<string>();
              const unique: Source[] = [];
              for (const src of sources) {
                const key = `${src.source_file}_${src.page_number || ""}`;
                if (!seen.has(key)) {
                  seen.add(key);
                  unique.push(src);
                }
              }

              const displaySources = unique.slice(0, 4);
              const remainingCount = unique.length - 4;

              return (
                <div className="flex flex-wrap items-center gap-2">
                  {displaySources.map((src, idx) => (
                    <div 
                      key={idx} 
                      className="flex items-center gap-2 px-3 py-1.5 bg-card border border-border rounded-lg text-xs hover:bg-secondary transition-colors cursor-pointer"
                    >
                      {src.type === "live_web" ? (
                        <Globe size={14} className="text-blue-400" />
                      ) : (
                        <FileText size={14} className="text-red-400" />
                      )}
                      <span className="truncate max-w-[160px]" title={src.source_file}>
                        {src.source_file}
                      </span>
                      {src.page_number && src.page_number !== "N/A" && src.page_number !== "Web" && (
                        <span className="text-muted-foreground border-l border-border pl-2">
                          Pg {src.page_number}
                        </span>
                      )}
                    </div>
                  ))}
                  {remainingCount > 0 && (
                    <div className="px-2.5 py-1 bg-secondary/60 text-muted-foreground border border-border rounded-lg text-xs">
                      +{remainingCount} more sources
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Technical Metadata */}
            {(modelUsed || tokenDisplay || elapsed || timestamp) && (
              <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground pt-2">
                {timestamp && (
                  <div className="flex items-center gap-1 text-muted-foreground/80">
                    <Clock size={12} />
                    <span>{timestamp}</span>
                  </div>
                )}
                {modelUsed && (
                  <div className="flex items-center gap-1">
                    <Sparkles size={12} />
                    <span>{modelUsed}</span>
                  </div>
                )}
                {elapsed && (
                  <div className="flex items-center gap-1">
                    <span>{elapsed.toFixed(2)}s</span>
                  </div>
                )}
                {tokenDisplay && (
                  <div className="flex items-center gap-1">
                    <Zap size={12} />
                    <span>{tokenDisplay.replace("📊 Tokens: ", "")}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
