"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import InteractionPanel from "../components/InteractionPanel";
import GovernanceLogs from "../components/GovernanceLogs";
import KnowledgeBase from "../components/KnowledgeBase";

export default function Home() {
  const [activeTab, setActiveTab] = useState("interaction");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const router = useRouter();

  useEffect(() => {
    // Check token immediately on mount
    const token = localStorage.getItem("token");
    if (!token) {
      router.replace("/login"); // Use replace to prevent 'back' button access
    } else {
      setIsAuthenticated(true);
    }
  }, [router]);

  // STRICT GUARD: Don't render ANYTHING until authenticated
  if (!isAuthenticated) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[#0d1117]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin"></div>
          <div className="text-emerald-500 font-mono text-sm tracking-widest">VERIFYING ACCESS...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full bg-[#0d1117] text-gray-300 font-sans overflow-hidden">
      {/* --- Sidebar Navigation --- */}
      <aside className="w-64 flex-shrink-0 border-r border-gray-800 bg-[#161b22] flex flex-col">
        <div className="p-4 border-b border-gray-800 flex items-center gap-3">
          <div className="w-8 h-8 bg-emerald-900/50 text-emerald-400 rounded-md flex items-center justify-center font-bold border border-emerald-500/30">S</div>
          <div>
            <h1 className="font-bold text-gray-100 tracking-tight">SĀBHYA AI</h1>
            <div className="text-[10px] text-emerald-500 font-mono mt-0.5">GOVERNANCE GATEWAY</div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          <SidebarItem active={activeTab === "interaction"} onClick={() => setActiveTab("interaction")} icon=">_" label="INTERACTION PANEL" />
          <SidebarItem active={activeTab === "governance"} onClick={() => setActiveTab("governance")} icon="🛡" label="GOVERNANCE LOGS" />
          <SidebarItem active={activeTab === "knowledge"} onClick={() => setActiveTab("knowledge")} icon="📂" label="KNOWLEDGE BASE" />
          <SidebarItem active={activeTab === "config"} onClick={() => setActiveTab("config")} icon="⚙" label="CONFIGURATION" />
        </nav>

        <div className="p-4 border-t border-gray-800">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            CONNECTED: LOCALHOST
          </div>
          <button 
            onClick={() => {
              localStorage.removeItem("token");
              router.push("/login");
            }}
            className="mt-3 w-full text-left text-xs text-red-400 hover:text-red-300 transition-colors"
          >
            [ LOGOUT ]
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0 bg-[#0d1117]">
        <header className="h-14 border-b border-gray-800 flex items-center justify-between px-6 bg-[#0d1117]">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span className="text-emerald-500">_</span>
            {activeTab === "interaction" && "Request/Response Interface — Governed Inference"}
            {activeTab === "governance" && "Audit Trail — Real-time Compliance Monitoring"}
            {activeTab === "knowledge" && "RAG Context — Vector Database Management"}
          </div>
          <div className="flex items-center gap-3">
            <div className="bg-[#1f2937] text-gray-300 text-xs px-3 py-1.5 rounded border border-gray-700 font-mono">Mistral 7B (Fast)</div>
            <div className="flex items-center gap-1.5 bg-emerald-900/20 text-emerald-400 text-xs px-3 py-1.5 rounded border border-emerald-500/30 font-bold tracking-wide">
              <span className="text-sm">🛡</span> GUARDRAILS: ACTIVE
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-hidden relative">
          {activeTab === "interaction" && <InteractionPanel />}
          {activeTab === "governance" && <GovernanceLogs />}
          {activeTab === "knowledge" && <KnowledgeBase />}
          {activeTab === "config" && (
            <div className="p-12 text-center text-gray-500">
              <div className="text-4xl mb-4">⚙</div>
              <p>System Configuration</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function SidebarItem({ active, onClick, icon, label }: any) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded text-xs font-bold tracking-wide transition-all duration-200 ${
        active 
          ? "bg-emerald-600/10 text-emerald-400 border-l-2 border-emerald-500" 
          : "text-gray-400 hover:bg-[#1f2937] hover:text-gray-200 border-l-2 border-transparent"
      }`}
    >
      <span className="text-sm opacity-80">{icon}</span>
      {label}
    </button>
  );
}
