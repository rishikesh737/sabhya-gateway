"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { toast } from "sonner";
import {
  Terminal,
  FolderOpen,
  ShieldAlert,
  Settings,
  RefreshCw,
  Upload,
  Send,
  PanelLeftClose,
  PanelLeft,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ChevronDown,
} from "lucide-react";

// ============================================================================
// Configuration
// ============================================================================
const API_BASE = "http://localhost:8000";
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
interface AuditLog {
  request_id: string;
  timestamp: number;
  user_hash: string;
  model: string;
  endpoint: string;
  status_code: number;
  latency_ms: number;
  total_tokens: number;
  pii_detected: boolean;
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

  // ===== KNOWLEDGE BASE STATE =====
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<{ name: string; chunks: number; timestamp: number }[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ===== GOVERNANCE LOGS STATE =====
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [isLogsLoading, setIsLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);

  // ===== HYDRATION SAFETY (Prevent SSR/Client mismatch) =====
  const [isMounted, setIsMounted] = useState(false);
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // ===== FETCH LOGS FUNCTION =====
  const fetchLogs = useCallback(async () => {
    setIsLogsLoading(true);
    setLogsError(null);
    try {
      const res = await fetch(`${API_BASE}/v1/audit/logs?limit=100`, {
        headers: { Authorization: `Bearer ${API_KEY}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setLogs(data);
      setIsConnected(true);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setLogsError(message);
      setIsConnected(false);
    } finally {
      setIsLogsLoading(false);
    }
  }, []);

  // ===== INITIAL LOGS FETCH + AUTO-REFRESH (30s) =====
  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 30000);
    return () => clearInterval(interval);
  }, [fetchLogs]);

  // ===== SUBMIT REQUEST =====
  const submitRequest = async () => {
    if (!promptInput.trim() || processingState === "PROCESSING") return;

    setProcessingState("PROCESSING");
    setResponseOutput(null);
    setPiiWarning(false);

    try {
      const res = await fetch(`${API_BASE}/v1/chat/completions`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          model: selectedModel,
          messages: [{ role: "user", content: promptInput }],
        }),
      });

      // Handle specific HTTP error codes with user-friendly messages
      if (!res.ok) {
        const errorMessage = getErrorMessage(res.status, await res.text());
        setProcessingState("ERROR");
        setResponseOutput(`ERROR: ${errorMessage}`);
        toast.error("Request Failed", { description: errorMessage });
        setIsConnected(res.status !== 0);
        return;
      }

      const data = await res.json();
      const content = data.choices?.[0]?.message?.content || "No response received.";

      setResponseOutput(content);
      setProcessingState("COMPLETED");
      setIsConnected(true);

      // Check for PII flag from backend
      if (data.pii_detected) {
        setPiiWarning(true);
        toast.warning("PII Detected", { description: "Sensitive data pattern flagged in request." });
      }

      // Refresh logs after request
      fetchLogs();
    } catch (err: unknown) {
      // Network errors (no connection, DNS failure, etc.)
      setProcessingState("ERROR");
      setResponseOutput("ERROR: CONNECTION FAILED — Backend unreachable. Check network or server status.");
      setIsConnected(false);
      toast.error("Connection Error", { description: "Could not reach the backend server." });
    }
  };

  // ===== CLEAR OUTPUT =====
  const clearOutput = () => {
    setProcessingState("IDLE");
    setResponseOutput(null);
    setPiiWarning(false);
    setPromptInput("");
  };

  // ===== FILE UPLOAD =====
  const handleUpload = async (file: File) => {
    if (!file.name.endsWith(".pdf")) {
      toast.error("Invalid Format", { description: "Only PDF documents accepted." });
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/v1/documents`, {
        method: "POST",
        headers: { Authorization: `Bearer ${API_KEY}` },
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }

      const data = await res.json();
      setUploadedFiles((prev) => [
        { name: file.name, chunks: data.chunks_indexed || 0, timestamp: Date.now() },
        ...prev,
      ]);

      setIsConnected(true);
      toast.success("Document Indexed", {
        description: `${file.name} — ${data.chunks_indexed} chunks.`,
      });
      fetchLogs();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Upload failed";
      setIsConnected(false);
      toast.error("Indexing Failed", { description: message });
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
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

  const formatTimestamp = (ts: number) => {
    // Only format on client to prevent hydration mismatch
    if (!isMounted) return "—";
    return new Date(ts * 1000).toLocaleString("en-US", {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  };

  const getStatusBadge = (code: number) => {
    if (code >= 200 && code < 300) return <span className="text-emerald-500">OK</span>;
    if (code === 429) return <span className="text-amber-500">BLOCKED</span>;
    return <span className="text-red-500">FAIL</span>;
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

            {/* Output Zone */}
            <div className="flex-1 flex flex-col gap-2 min-h-0">
              <label className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">Output Zone</label>
              <pre
                className={`flex-1 overflow-auto bg-slate-900 border border-slate-700 px-4 py-3 text-sm whitespace-pre-wrap ${processingState === "ERROR" ? "text-red-400" : "text-slate-300"
                  }`}
              >
                {responseOutput || "// Response will appear here after processing completes."}
              </pre>
            </div>
          </div>
        </div>

        {/* ===== GOVERNANCE LOGS VIEW ===== */}
        <div className={`h-full flex flex-col ${activeView === "logs" ? "block" : "hidden"}`}>
          <div className="border-b border-slate-800 bg-slate-900/50 px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="flex items-center gap-2 text-sm font-bold text-slate-100 uppercase tracking-wider">
                  <ShieldAlert size={16} className="text-cyan-500" />
                  Governance Logs
                </h2>
                <p className="text-[11px] text-slate-500 mt-1">Audit trail — {logs.length} records — Auto-refresh: 30s</p>
              </div>
              <button
                onClick={fetchLogs}
                disabled={isLogsLoading}
                className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 px-4 py-2 text-xs font-medium text-slate-300 disabled:opacity-50"
              >
                <RefreshCw size={12} className={isLogsLoading ? "animate-spin" : ""} />
                {isLogsLoading ? "Loading..." : "Refresh"}
              </button>
            </div>
          </div>

          {/* Error State */}
          {logsError && (
            <div className="mx-6 mt-4 bg-red-950/50 border border-red-800 px-4 py-3 text-sm text-red-400">
              Error: {logsError}
            </div>
          )}

          {/* Table */}
          <div className="flex-1 overflow-auto p-6">
            <div className="border border-slate-800">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-900 border-b border-slate-800">
                    <th className="px-4 py-3 text-left text-slate-500 uppercase tracking-wider font-medium">Timestamp</th>
                    <th className="px-4 py-3 text-left text-slate-500 uppercase tracking-wider font-medium">User Hash</th>
                    <th className="px-4 py-3 text-left text-slate-500 uppercase tracking-wider font-medium">Model</th>
                    <th className="px-4 py-3 text-center text-slate-500 uppercase tracking-wider font-medium">Status</th>
                    <th className="px-4 py-3 text-center text-slate-500 uppercase tracking-wider font-medium">PII</th>
                    <th className="px-4 py-3 text-right text-slate-500 uppercase tracking-wider font-medium">Latency</th>
                    <th className="px-4 py-3 text-right text-slate-500 uppercase tracking-wider font-medium">Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {isLogsLoading && logs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-slate-500">
                        Loading audit records...
                      </td>
                    </tr>
                  ) : logs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-slate-500">
                        No audit records found.
                      </td>
                    </tr>
                  ) : (
                    logs.map((log, i) => (
                      <tr
                        key={log.request_id}
                        className={`border-b border-slate-800/50 hover:bg-slate-900/50 ${i % 2 === 0 ? "bg-slate-950" : "bg-slate-900/20"
                          }`}
                      >
                        <td className="px-4 py-2.5 text-slate-400 whitespace-nowrap">
                          {formatTimestamp(log.timestamp)}
                        </td>
                        <td className="px-4 py-2.5 text-slate-500">{log.user_hash}</td>
                        <td className="px-4 py-2.5 text-cyan-400">{log.model}</td>
                        <td className="px-4 py-2.5 text-center font-medium">{getStatusBadge(log.status_code)}</td>
                        <td className="px-4 py-2.5 text-center">
                          {log.pii_detected ? (
                            <span title="PII Detected"><Shield size={14} className="inline text-red-500" /></span>
                          ) : (
                            <span className="text-slate-700">—</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-right text-slate-400">{log.latency_ms.toFixed(0)}ms</td>
                        <td className="px-4 py-2.5 text-right text-slate-400">{log.total_tokens}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* ===== KNOWLEDGE BASE VIEW ===== */}
        <div className={`h-full overflow-y-auto p-6 ${activeView === "knowledge" ? "block" : "hidden"}`}>
          <div className="mb-6">
            <h2 className="flex items-center gap-2 text-sm font-bold text-slate-100 uppercase tracking-wider">
              <FolderOpen size={16} className="text-cyan-500" />
              Knowledge Base
            </h2>
            <p className="text-[11px] text-slate-500 mt-1">Document ingestion for RAG context — PDF only</p>
          </div>

          {/* Upload Zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`flex h-48 cursor-pointer flex-col items-center justify-center border-2 border-dashed transition ${isDragging
              ? "border-cyan-500 bg-cyan-500/5"
              : "border-slate-700 bg-slate-900/50 hover:border-slate-600"
              }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileSelect}
              className="hidden"
            />
            {isUploading ? (
              <div className="flex flex-col items-center gap-3">
                <div className="h-8 w-8 border-2 border-cyan-500 border-t-transparent animate-spin"></div>
                <p className="text-xs text-slate-400 uppercase tracking-wider">Indexing document...</p>
              </div>
            ) : (
              <>
                <Upload size={32} className="mb-3 text-slate-600" />
                <p className="text-sm text-slate-400">Drop PDF here or click to browse</p>
                <p className="mt-1 text-[10px] text-slate-600 uppercase tracking-wider">
                  Documents chunked and vectorized for retrieval
                </p>
              </>
            )}
          </div>

          {/* Indexed Documents */}
          {uploadedFiles.length > 0 && (
            <div className="mt-6 border border-slate-800">
              <div className="bg-slate-900 border-b border-slate-800 px-4 py-3">
                <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                  Indexed Documents ({uploadedFiles.length})
                </h3>
              </div>
              <div className="divide-y divide-slate-800/50">
                {uploadedFiles.map((file, i) => (
                  <div key={i} className="flex items-center justify-between px-4 py-3 bg-slate-950">
                    <div className="flex items-center gap-3">
                      <CheckCircle2 size={14} className="text-emerald-500" />
                      <span className="text-sm text-slate-300">{file.name}</span>
                    </div>
                    <span className="text-xs text-slate-500">{file.chunks} chunks</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

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
