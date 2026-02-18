"use client";

import KnowledgeBase from "@/components/KnowledgeBase";
import GovernanceLogs from "@/components/GovernanceLogs";
import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";
import {
  Terminal,
  FolderOpen,
  ShieldAlert,
  Settings,
  Send,
  PanelLeftClose,
  PanelLeft,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ChevronDown,
  BrainCircuit,
} from "lucide-react";

// ============================================================================
// Configuration
// ============================================================================
const API_BASE = "";
const API_KEY = "dev-key-1";

const headers = {
  Authorization: `Bearer ${API_KEY}`,
  "Content-Type": "application/json",
};

// Model options for dynamic routing
const MODEL_OPTIONS = [
  { id: "mistral:7b-instruct-q4_K_M", label: "Mistral 7B (Fast)", tier: "FAST" },
  { id: "llama3", label: "Llama 3 (Smart)", tier: "SMART" },
];

// ============================================================================
// Types
// ============================================================================
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  sources?: Source[];
  thought_process?: string;
}

interface Source {
  source: string;
  chunk_index: number;
}

type ViewId = "interact" | "knowledge" | "logs" | "settings";
type ProcessingState = "IDLE" | "PROCESSING" | "COMPLETED" | "ERROR";

// ============================================================================
// Sidebar Navigation
// ============================================================================
const navItems: { id: ViewId; label: string; icon: React.ReactNode }[] = [
  { id: "interact", label: "Interaction Panel", icon: <Terminal size={18} /> },
  { id: "logs", label: "Governance Logs", icon: <ShieldAlert size={18} /> },
  { id: "knowledge", label: "Knowledge Base", icon: <FolderOpen size={18} /> },
  { id: "settings", label: "Configuration", icon: <Settings size={18} /> },
];

// ============================================================================
// Main Dashboard Component (SOC Constitutional Design)
// ============================================================================
export default function SabhyaDashboard() {
  const [activeView, setActiveView] = useState<ViewId>("interact");
  const [isConnected, setIsConnected] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // ===== INTERACTION PANEL STATE =====
  const [promptInput, setPromptInput] = useState("");
  const [selectedModel, setSelectedModel] = useState(MODEL_OPTIONS[0].id);
  const [processingState, setProcessingState] = useState<ProcessingState>("IDLE");
  const [responseOutput, setResponseOutput] = useState<string | null>(null);
  const [piiWarning, setPiiWarning] = useState(false);

  // ===== CHAT HISTORY & STREAMING STATE =====
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentSources, setCurrentSources] = useState<Source[]>([]);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // ===== PERSISTENCE =====
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("sabhya_chat_history_v1");
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) {
            setChatHistory(parsed);
          }
        } catch (error) {
          console.error("Failed to load history:", error);
        }
      }
    }
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined" && chatHistory.length > 0) {
      localStorage.setItem("sabhya_chat_history_v1", JSON.stringify(chatHistory));
    }
  }, [chatHistory]);




  // ===== SUBMIT REQUEST WITH STREAMING =====
  const submitRequest = async () => {
    if (!promptInput.trim() || processingState === "PROCESSING") return;

    const userMessage: ChatMessage = {
      role: "user",
      content: promptInput,
      timestamp: new Date().getTime(),
    };

    // Add user message to history
    setChatHistory((prev) => [...prev, userMessage]);
    setProcessingState("PROCESSING");
    setStreamingText("");
    setIsStreaming(true);
    setCurrentSources([]);
    setPiiWarning(false);

    const currentPrompt = promptInput;
    setPromptInput(""); // Clear input immediately

    try {
      // Build full conversation for context
      const fullMessages = [
        ...chatHistory.map((m) => ({ role: m.role, content: m.content })),
        { role: "user", content: currentPrompt },
      ];

      const res = await fetch(`${API_BASE}/v1/chat/completions/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          model: selectedModel,
          messages: fullMessages,
        }),
      });

      if (!res.ok) {
        const errorMessage = getErrorMessage(res.status, await res.text());
        setProcessingState("ERROR");
        setResponseOutput(`ERROR: ${errorMessage}`);
        setIsStreaming(false);
        toast.error("Request Failed", { description: errorMessage });
        return;
      }

      // Process SSE stream
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = "";

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") continue;

              try {
                const parsed = JSON.parse(data);

                if (parsed.error) {
                  setProcessingState("ERROR");
                  setResponseOutput(`ERROR: ${parsed.error}`);
                  setIsStreaming(false);
                  toast.error("Request Blocked", { description: parsed.error });
                  return;
                }

                if (parsed.token) {
                  fullContent += parsed.token;
                  setStreamingText(fullContent);
                }

                if (parsed.done) {
                  // Extract thought process if present
                  let thoughtProcess: string | undefined;
                  const thoughtMatch = fullContent.match(/<thought>([\s\S]*?)<\/thought>/);
                  if (thoughtMatch) {
                    thoughtProcess = thoughtMatch[1].trim();
                    fullContent = fullContent.replace(/<thought>[\s\S]*?<\/thought>/, "").trim();
                  }

                  // Strip outer markdown blocks
                  fullContent = fullContent
                    .replace(/^```(?:markdown|txt)?\n?/i, "")
                    .replace(/```$/, "")
                    .trim();

                  // Handle metadata
                  let sources = parsed.sources;
                  if (sources && sources.length > 0) {
                    setCurrentSources(sources);
                  } else {
                    sources = currentSources;
                  }

                  if (parsed.pii_detected) {
                    setPiiWarning(true);
                    toast.warning("PII Detected", { description: "Sensitive data pattern flagged." });
                  }

                  // Add assistant response to history
                  const assistantMessage: ChatMessage = {
                    role: "assistant",
                    content: fullContent,
                    thought_process: thoughtProcess,
                    timestamp: new Date().getTime(),
                    sources: sources.length > 0 ? sources : undefined,
                  };
                  setChatHistory((prev) => [...prev, assistantMessage]);

                  setResponseOutput(fullContent);
                  setProcessingState("COMPLETED");
                  setIsStreaming(false);
                  setIsConnected(true);

                  if (chatContainerRef.current) {
                    chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
                  }

                  return;
                }
              } catch {
                // Skip invalid JSON
              }
            }
          }
        }
      }
    } catch (_err: unknown) {
      setProcessingState("ERROR");
      setResponseOutput("ERROR: CONNECTION FAILED — Backend unreachable.");
      setIsStreaming(false);
      setIsConnected(false);
      toast.error("Connection Error", { description: "Could not reach the backend server." });
    }
  };

  // ===== CLEAR CHAT =====
  const clearOutput = () => {
    setProcessingState("IDLE");
    setResponseOutput(null);
    setPiiWarning(false);
    setPromptInput("");
    setChatHistory([]);
    setStreamingText("");
    setCurrentSources([]);
  };

  // ===== HELPERS =====
  const getErrorMessage = (status: number, body?: string): string => {
    switch (status) {
      case 400:
        return "BAD REQUEST (400) — Invalid request format.";
      case 401:
        return "UNAUTHORIZED (401) — Invalid or missing API key.";
      case 403:
        return "FORBIDDEN (403) — Access denied. Check API key permissions.";
      case 404:
        return "NOT FOUND (404) — Endpoint does not exist.";
      case 429:
        return "RATE LIMIT EXCEEDED (429) — Maximum 50 requests per minute. Try again later.";
      case 500:
        return "SERVER ERROR (500) — Internal backend failure. Contact administrator.";
      case 502:
        return "BAD GATEWAY (502) — LLM inference service unreachable. Is Ollama running?";
      case 503:
        return "SERVICE UNAVAILABLE (503) — Backend temporarily overloaded.";
      default:
        return `HTTP ERROR (${status})${body ? ` — ${body.slice(0, 100)}` : ""}`;
    }
  };

  // ===== RENDER =====
  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-mono">
      {/* ===== LEFT SIDEBAR ===== */}
      <aside
        className={`flex flex-col border-r border-slate-800 bg-slate-900 transition-all duration-200 ${sidebarCollapsed ? "w-14" : "w-56"
          }`}
      >
        {/* Brand Header */}
        <div className="flex items-center gap-2 border-b border-slate-800 p-3">
          <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center bg-slate-800 text-sm font-bold text-slate-300">
            S
          </div>
          {!sidebarCollapsed && (
            <div className="overflow-hidden">
              <h1 className="text-sm font-bold text-slate-100 tracking-wide">SABHYA AI</h1>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Governance Gateway</p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-1">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              title={sidebarCollapsed ? item.label : undefined}
              className={`flex w-full items-center gap-2 px-3 py-2.5 text-xs font-medium transition ${activeView === item.id
                ? "bg-slate-800 text-slate-100 border-l-2 border-cyan-500"
                : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200 border-l-2 border-transparent"
                } ${sidebarCollapsed ? "justify-center" : ""}`}
            >
              {item.icon}
              {!sidebarCollapsed && <span className="uppercase tracking-wide">{item.label}</span>}
            </button>
          ))}
        </nav>

        {/* Collapse Toggle */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="m-1 flex items-center justify-center gap-2 p-2 text-slate-500 hover:bg-slate-800 hover:text-slate-300"
        >
          {sidebarCollapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
        </button>

        {/* Connection Status */}
        <div className="border-t border-slate-800 p-3">
          <div className={`flex items-center gap-2 ${sidebarCollapsed ? "justify-center" : ""}`}>
            <div className={`h-2 w-2 ${isConnected ? "bg-emerald-500" : "bg-red-500"}`}></div>
            {!sidebarCollapsed && (
              <span className={`text-[10px] uppercase tracking-wider ${isConnected ? "text-emerald-500" : "text-red-500"}`}>
                {isConnected ? "Connected" : "Disconnected"}
              </span>
            )}
          </div>
        </div>
      </aside>

      {/* ===== MAIN CONTENT ===== */}
      <main className="flex-1 overflow-hidden bg-slate-950">
        {/* ===== INTERACTION PANEL VIEW ===== */}
        <div className={`flex h-full flex-col ${activeView === "interact" ? "block" : "hidden"}`}>
          {/* Header */}
          <div className="border-b border-slate-800 bg-slate-900/50 px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="flex items-center gap-2 text-sm font-bold text-slate-100 uppercase tracking-wider">
                  <Terminal size={16} className="text-cyan-500" />
                  Interaction Panel
                </h2>
                <p className="text-[11px] text-slate-500 mt-1">Request/Response Interface — Governed Inference</p>
              </div>
              <div className="flex items-center gap-3">
                {/* Model Selector */}
                <div className="relative">
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="appearance-none bg-slate-800 border border-slate-700 text-slate-200 text-xs px-3 py-2 pr-8 focus:outline-none focus:border-cyan-500"
                  >
                    {MODEL_OPTIONS.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
                </div>
                {/* Guardrails Badge */}
                <div className="flex items-center gap-1.5 bg-emerald-900/30 border border-emerald-800 px-3 py-1.5">
                  <Shield size={12} className="text-emerald-500" />
                  <span className="text-[10px] text-emerald-400 uppercase tracking-wider font-bold">Guardrails: Active</span>
                </div>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 flex flex-col p-6 gap-4 overflow-hidden">
            {/* PII Warning Banner */}
            {piiWarning && (
              <div className="flex items-center gap-3 bg-red-950/50 border border-red-800 px-4 py-3">
                <AlertTriangle size={18} className="text-red-500" />
                <span className="text-sm text-red-400 font-medium">
                  ⚠️ PII PATTERN DETECTED IN REQUEST — Data flagged in audit log
                </span>
              </div>
            )}

            {/* Input Zone */}
            <div className="flex flex-col gap-2">
              <label className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">Input Zone</label>
              <textarea
                value={promptInput}
                onChange={(e) => setPromptInput(e.target.value)}
                placeholder="Enter request prompt..."
                disabled={processingState === "PROCESSING"}
                className="h-32 w-full bg-slate-900 border border-slate-700 px-4 py-3 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan-500 resize-none disabled:opacity-50"
              />
              <div className="flex items-center gap-3">
                <button
                  onClick={submitRequest}
                  disabled={processingState === "PROCESSING" || !promptInput.trim()}
                  className="flex items-center gap-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 disabled:text-slate-500 px-5 py-2.5 text-xs font-bold uppercase tracking-wider transition"
                >
                  <Send size={14} />
                  Submit Request
                </button>
                <button
                  onClick={clearOutput}
                  className="px-4 py-2.5 text-xs font-medium text-slate-400 hover:text-slate-200 uppercase tracking-wider"
                >
                  Clear
                </button>
              </div>
            </div>

            {/* Status Banner */}
            <div className="flex items-center gap-3">
              {processingState === "IDLE" && (
                <div className="flex items-center gap-2 text-slate-500">
                  <Clock size={14} />
                  <span className="text-xs uppercase tracking-wider">[IDLE] — Awaiting request</span>
                </div>
              )}
              {processingState === "PROCESSING" && (
                <div className="flex items-center gap-2 text-amber-500">
                  <div className="h-3 w-3 border-2 border-amber-500 border-t-transparent animate-spin"></div>
                  <span className="text-xs uppercase tracking-wider font-bold">[PROCESSING] — Inference in progress</span>
                </div>
              )}
              {processingState === "COMPLETED" && (
                <div className="flex items-center gap-2 text-emerald-500">
                  <CheckCircle2 size={14} />
                  <span className="text-xs uppercase tracking-wider font-bold">[COMPLETED] — Response received</span>
                </div>
              )}
              {processingState === "ERROR" && (
                <div className="flex items-center gap-2 text-red-500">
                  <AlertTriangle size={14} />
                  <span className="text-xs uppercase tracking-wider font-bold">[ERROR] — Request failed</span>
                </div>
              )}
            </div>

            {/* Chat History / Output Zone */}
            <div className="flex-1 flex flex-col gap-2 min-h-0">
              <label className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">
                Conversation {chatHistory.length > 0 && `(${chatHistory.length} messages)`}
              </label>
              <div
                ref={chatContainerRef}
                className="flex-1 overflow-auto bg-slate-900 border border-slate-700 p-4 space-y-4"
              >
                {chatHistory.length === 0 && !isStreaming && (
                  <div className="text-slate-500 text-sm italic">
                    {/* Conversation will appear here. Send a message to begin. */}
                  </div>
                )}

                {chatHistory.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex flex-col gap-2 ${msg.role === "user" ? "items-end" : "items-start"}`}
                  >
                    <div
                      className={`max-w-[80%] px-4 py-3 text-sm ${msg.role === "user"
                        ? "bg-cyan-900/50 border border-cyan-700 text-cyan-100"
                        : "bg-slate-800 border border-slate-700 text-slate-200"
                        }`}
                    >
                      <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 font-bold">
                        {msg.role === "user" ? "You" : "Sabhya AI"}
                      </div>

                      {/* Thought Process Accordion */}
                      {msg.thought_process && (
                        <details className="mb-3">
                          <summary className="cursor-pointer text-xs text-slate-500 hover:text-cyan-400 flex items-center gap-1.5 select-none transition-colors outline-none group">
                            <BrainCircuit size={12} className="group-hover:text-cyan-400" />
                            <span className="font-medium tracking-wide">Thinking Process</span>
                          </summary>
                          <div className="mt-2 p-3 bg-slate-950/50 border border-slate-700/50 rounded text-xs text-slate-400 font-mono whitespace-pre-wrap leading-relaxed">
                            {msg.thought_process}
                          </div>
                        </details>
                      )}

                      <div className="whitespace-pre-wrap">{msg.content}</div>

                      {/* Source Citations */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-slate-600">
                          <div className="text-[10px] text-emerald-400 uppercase tracking-wider font-bold mb-1">
                            📚 Sources Used
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {[...new Set(msg.sources.map(s => s.source))].map((source, i) => (
                              <span
                                key={i}
                                className="text-[10px] bg-emerald-900/30 border border-emerald-800 px-2 py-0.5 text-emerald-400"
                              >
                                {source}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="text-[9px] text-slate-600">
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                ))}

                {/* Streaming Response */}
                {/* Streaming Response Area */}
                {isStreaming && streamingText && (
                  <div className="flex flex-col gap-2 items-start w-full">
                    {(() => {
                      // Check for thought tags (start, content, and optional end)
                      const thoughtMatch = streamingText.match(/<thought>([\s\S]*?)(?:<\/thought>|$)([\s\S]*)/);

                      if (thoughtMatch) {
                        const thinkingContent = thoughtMatch[1];
                        const rawMain = thoughtMatch[2] || "";
                        const isThinkingDone = streamingText.includes("</thought>");

                        // Strip outer markdown blocks
                        const mainContent = rawMain
                          .replace(/^```(?:markdown|txt)?\n?/i, "")
                          .replace(/```$/, "")
                          .trim();

                        return (
                          <div className="max-w-[80%] flex flex-col gap-2">
                            {/* Live Thinking Process */}
                            <details className="mb-2" open={!isThinkingDone}>
                              <summary className={`cursor-pointer text-xs text-slate-500 flex items-center gap-1.5 ${!isThinkingDone ? "animate-pulse text-cyan-400" : ""}`}>
                                <BrainCircuit size={12} />
                                <span className="font-medium tracking-wide">
                                  {isThinkingDone ? "Thinking Process" : "Thinking..."}
                                </span>
                              </summary>
                              <div className="mt-2 p-3 bg-slate-950/50 border border-slate-700/50 rounded text-xs text-slate-400 font-mono whitespace-pre-wrap leading-relaxed">
                                {thinkingContent}
                                {!isThinkingDone && (
                                  <span className="inline-block w-1.5 h-3 bg-cyan-500 animate-pulse ml-1 align-middle"></span>
                                )}
                              </div>
                            </details>

                            {/* Main Content (appears after thinking closes) */}
                            {(mainContent || isThinkingDone) && (
                              <div className="px-4 py-3 text-sm bg-slate-800 border border-slate-700 text-slate-200">
                                <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 font-bold">
                                  Sabhya AI
                                </div>
                                <div className="whitespace-pre-wrap">
                                  {mainContent}
                                  {/* Cursor for main content */}
                                  <span className="inline-block w-2 h-4 bg-cyan-500 animate-pulse ml-1 align-middle"></span>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      }

                      // Default: No thought block detected yet (or simple response)
                      // Strip outer markdown blocks
                      const displayContent = streamingText
                        .replace(/^```(?:markdown|txt)?\n?/i, "")
                        .replace(/```$/, "")
                        .trim();

                      return (
                        <div className="max-w-[80%] px-4 py-3 text-sm bg-slate-800 border border-slate-700 text-slate-200">
                          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 font-bold">
                            Sabhya AI
                          </div>
                          <div className="whitespace-pre-wrap">{displayContent}</div>
                          <span className="inline-block w-2 h-4 bg-cyan-500 animate-pulse ml-1"></span>
                        </div>
                      );
                    })()}
                  </div>
                )}

                {/* Typing Indicator */}
                {isStreaming && !streamingText && (
                  <div className="flex items-center gap-2 text-slate-400">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></div>
                      <div className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></div>
                      <div className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></div>
                    </div>
                    <span className="text-xs">Processing...</span>
                  </div>
                )}

                {/* Current Sources (displayed after streaming completes) */}
                {currentSources.length > 0 && !isStreaming && (
                  <div className="bg-emerald-950/30 border border-emerald-800 p-3">
                    <div className="text-[10px] text-emerald-400 uppercase tracking-wider font-bold mb-2">
                      📚 Knowledge Sources Referenced
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {[...new Set(currentSources.map(s => s.source))].map((source, i) => (
                        <div
                          key={i}
                          className="text-xs bg-emerald-900/50 border border-emerald-700 px-3 py-1 text-emerald-300"
                        >
                          {source}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Error Display */}
                {processingState === "ERROR" && responseOutput && (
                  <div className="bg-red-950/50 border border-red-800 px-4 py-3 text-sm text-red-400">
                    {responseOutput}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ===== GOVERNANCE LOGS VIEW ===== */}
        {activeView === "logs" && (
          <div className="h-full border border-slate-700 rounded-lg overflow-hidden">
            <GovernanceLogs />
          </div>
        )}

        {/* ===== KNOWLEDGE BASE VIEW ===== */}
        {activeView === "knowledge" && (
          <div className="h-full border border-slate-700 rounded-lg overflow-hidden">
            <KnowledgeBase />
          </div>
        )}

        {/* ===== SETTINGS VIEW ===== */}
        <div className={`h-full overflow-y-auto p-6 ${activeView === "settings" ? "block" : "hidden"}`}>
          <div className="mb-6">
            <h2 className="flex items-center gap-2 text-sm font-bold text-slate-100 uppercase tracking-wider">
              <Settings size={16} className="text-cyan-500" />
              Configuration
            </h2>
            <p className="text-[11px] text-slate-500 mt-1">System parameters and connection settings</p>
          </div>

          <div className="max-w-lg space-y-4">
            <div className="border border-slate-800 bg-slate-900/50">
              <div className="bg-slate-900 border-b border-slate-800 px-4 py-3">
                <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">API Connection</h3>
              </div>
              <div className="p-4 space-y-3 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Endpoint:</span>
                  <span className="text-cyan-400">{API_BASE}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Rate Limit:</span>
                  <span className="text-slate-300">50 req/min</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Default Model:</span>
                  <span className="text-slate-300">{MODEL_OPTIONS[0].label}</span>
                </div>
              </div>
            </div>

            <div className="border border-slate-800 bg-slate-900/50">
              <div className="bg-slate-900 border-b border-slate-800 px-4 py-3">
                <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Security Settings</h3>
              </div>
              <div className="p-4 space-y-3 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">PII Detection:</span>
                  <span className="text-emerald-400">ENABLED</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Mode:</span>
                  <span className="text-slate-300">Passive (Flag Only)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Patterns:</span>
                  <span className="text-slate-300">Email, Phone, Credit Card</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
