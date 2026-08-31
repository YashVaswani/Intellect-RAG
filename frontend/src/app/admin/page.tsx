"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import { Activity, Shield, Database, Cpu } from "lucide-react";

export default function AdminPanel() {
  const [stats, setStats] = useState<any>(null);

  const fetchAdminData = async () => {
    try {
      const statsRes = await fetch("/api/admin/stats");
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <Sidebar />
      
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <div className="max-w-6xl mx-auto w-full p-8 space-y-8">
          
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-3">
                <Shield className="text-primary" size={32} />
                Admin Dashboard
              </h1>
              <p className="text-muted-foreground mt-1">System status and configuration</p>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-card border border-border p-5 rounded-xl flex items-center gap-4">
              <div className="p-3 bg-green-500/10 text-green-500 rounded-lg"><Activity size={24} /></div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Queries Today</p>
                <p className="text-2xl font-bold">{stats?.today_queries || 0}</p>
              </div>
            </div>
            <div className="bg-card border border-border p-5 rounded-xl flex items-center gap-4">
              <div className="p-3 bg-purple-500/10 text-purple-500 rounded-lg"><Database size={24} /></div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Sessions</p>
                <p className="text-2xl font-bold">{stats?.total_sessions || 0}</p>
              </div>
            </div>
            <div className="bg-card border border-border p-5 rounded-xl flex items-center gap-4">
              <div className="p-3 bg-orange-500/10 text-orange-500 rounded-lg"><Cpu size={24} /></div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Messages</p>
                <p className="text-2xl font-bold">{stats?.total_messages || 0}</p>
              </div>
            </div>
            <div className="bg-card border border-border p-5 rounded-xl flex items-center gap-4">
              <div className="p-3 bg-blue-500/10 text-blue-500 rounded-lg"><Database size={24} /></div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Cache Entries</p>
                <p className="text-2xl font-bold">{stats?.cache?.active_entries || 0}</p>
              </div>
            </div>
          </div>

          {/* System Status */}
          <div className="space-y-6">
            <h2 className="text-xl font-semibold">System Status</h2>
            <div className="bg-card border border-border rounded-xl p-1 divide-y divide-border max-w-md">
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                  <span className="font-medium">FastAPI Backend</span>
                </div>
                <span className="text-xs text-muted-foreground bg-secondary px-2 py-1 rounded">Online</span>
              </div>
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                  <span className="font-medium">Gemini & Groq</span>
                </div>
                <span className="text-xs text-muted-foreground bg-secondary px-2 py-1 rounded">Online</span>
              </div>
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                  <span className="font-medium">Qdrant Vector DB</span>
                </div>
                <span className="text-xs text-muted-foreground bg-secondary px-2 py-1 rounded">Online</span>
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
