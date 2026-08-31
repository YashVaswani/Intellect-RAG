"use client";

import Sidebar from "@/components/Sidebar";
import { Upload, FileText, Trash2, Search, ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState, useEffect, useRef } from "react";

interface Document {
  name: string;
  type?: string;
  file_type?: string;
  chunks?: number;
  chunk_count?: number;
  date?: string;
  ingested_at?: string;
}

export default function KnowledgeBase() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocs = async () => {
    try {
      const res = await fetch("/api/documents");
      const data = await res.json();
      setDocs(data.documents || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    
    setUploading(true);
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
        // Refresh document list
        fetchDocs();
      } else {
        alert("Upload failed.");
      }
    } catch (error) {
      console.error("Upload error", error);
      alert("Error uploading file.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDelete = async (docName: string) => {
    if (!confirm(`Are you sure you want to delete ${docName}?`)) return;
    try {
      await fetch(`/api/documents/${docName}`, { method: "DELETE" });
      setDocs(docs.filter(d => d.name !== docName));
    } catch (e) {
      console.error("Delete error", e);
    }
  };

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <Sidebar />
      
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <div className="max-w-5xl mx-auto w-full p-8 space-y-8">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/" className="p-2 hover:bg-secondary rounded-full transition-colors md:hidden">
                <ArrowLeft size={20} />
              </Link>
              <div>
                <h1 className="text-3xl font-bold">Knowledge Base</h1>
                <p className="text-muted-foreground mt-1">Manage documents available to the AI assistant</p>
              </div>
            </div>
            
            <input 
              type="file" 
              multiple 
              className="hidden" 
              ref={fileInputRef} 
              onChange={handleFileChange}
              accept=".pdf,.docx,.xlsx,.pptx,.txt,.csv,.md,.mp3,.wav"
            />
            
            <button 
              onClick={handleUploadClick}
              disabled={uploading}
              className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg hover:bg-primary/90 transition-colors shadow-sm disabled:opacity-50"
            >
              {uploading ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
              <span>{uploading ? "Uploading..." : "Upload Documents"}</span>
            </button>
          </div>

          {/* Search and Filter */}
          <div className="flex gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={18} />
              <input 
                type="text" 
                placeholder="Search documents..." 
                className="w-full pl-10 pr-4 py-2.5 bg-card border border-border rounded-lg focus:outline-none focus:ring-1 focus:ring-ring text-sm"
              />
            </div>
          </div>

          {/* Document List */}
          <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="bg-secondary/50 text-muted-foreground">
                <tr>
                  <th className="px-6 py-4 font-medium">Document Name</th>
                  <th className="px-6 py-4 font-medium">Type</th>
                  <th className="px-6 py-4 font-medium">Chunks</th>
                  <th className="px-6 py-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading ? (
                  <tr><td colSpan={4} className="px-6 py-8 text-center text-muted-foreground">Loading documents...</td></tr>
                ) : docs.length === 0 ? (
                  <tr><td colSpan={4} className="px-6 py-8 text-center text-muted-foreground">No documents uploaded yet.</td></tr>
                ) : docs.map((doc, idx) => (
                  <tr key={idx} className="hover:bg-secondary/30 transition-colors group">
                    <td className="px-6 py-4 flex items-center gap-3">
                      <FileText size={18} className="text-muted-foreground" />
                      <span className="font-medium text-foreground">{doc.name}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2.5 py-1 bg-secondary text-secondary-foreground rounded-md text-xs font-medium">
                        {doc.file_type || doc.type || "unknown"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-muted-foreground">{doc.chunk_count || doc.chunks || 0}</td>
                    <td className="px-6 py-4 text-right">
                      <button 
                        onClick={() => handleDelete(doc.name)}
                        className="text-muted-foreground hover:text-destructive transition-colors opacity-0 group-hover:opacity-100 p-2"
                      >
                        <Trash2 size={18} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
