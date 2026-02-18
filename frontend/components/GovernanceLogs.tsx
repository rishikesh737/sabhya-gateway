import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { AuditLog } from '../lib/types';

const GovernanceLogs: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const data = await api.getAuditLogs();
      setLogs(data);
      setError(null);
    } catch (err) {
      setError("Failed to fetch audit logs.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const downloadCSV = () => {
    if (logs.length === 0) return;
    const headers = ["Timestamp", "Endpoint", "Status", "Latency (ms)", "Tokens", "Risk Flags", "Request ID"];
    const rows = logs.map(log => [
      new Date(log.timestamp).toISOString(),
      log.endpoint,
      log.status_code,
      Math.round(log.latency_ms || 0),
      log.total_tokens || 0,
      log.pii_detected ? "PII BLOCKED" : "SAFE",
      log.request_id
    ].join(","));

    const csvContent = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sabhya_audit_logs_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full bg-[#0d1117] text-gray-300 p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold text-emerald-400">
          ⚡ Live Governance Audit <span className="text-xs bg-gray-800 px-2 py-1 rounded-full text-gray-400 ml-2">{logs.length} Events</span>
        </h2>
        <div className="flex gap-2">
          <button
            onClick={downloadCSV}
            disabled={logs.length === 0}
            className="flex items-center gap-2 px-3 py-1.5 bg-[#1f2937] hover:bg-[#374151] text-xs font-bold text-emerald-400 border border-emerald-500/30 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span>⬇</span> EXPORT CSV
          </button>
          <button onClick={fetchLogs} className="p-2 hover:bg-gray-800 rounded-full transition-colors text-gray-400">🔄</button>
        </div>
      </div>
      {error && <div className="text-red-400 mb-4 text-sm">{error}</div>}
      <div className="flex-1 overflow-auto border border-gray-800 rounded-lg bg-[#0d1117]">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-800/50 text-gray-400 sticky top-0">
            <tr>
              <th className="p-3 font-medium">TIMESTAMP</th>
              <th className="p-3 font-medium">ENDPOINT</th>
              <th className="p-3 font-medium">STATUS</th>
              <th className="p-3 font-medium">LATENCY</th>
              <th className="p-3 font-medium">TOKENS</th>
              <th className="p-3 font-medium">RISK FLAGS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {loading ? (
              <tr><td colSpan={6} className="p-8 text-center text-gray-500">Loading audit trail...</td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan={6} className="p-8 text-center text-gray-500">No audit logs found yet.</td></tr>
            ) : (
              logs.map((log) => (
                <tr key={log.request_id} className="hover:bg-gray-800/30 transition-colors">
                  <td className="p-3 font-mono text-xs text-gray-500">{new Date(log.timestamp).toLocaleString()}</td>
                  <td className="p-3 font-mono text-xs text-blue-400">{log.endpoint}</td>
                  <td className="p-3"><span className={`px-2 py-0.5 rounded text-xs font-medium ${log.status_code === 200 ? 'bg-emerald-900/30 text-emerald-400' : 'bg-red-900/30 text-red-400'}`}>{log.status_code}</span></td>
                  <td className="p-3 font-mono text-xs">{Math.round(log.latency_ms || 0)}ms</td>
                  <td className="p-3 font-mono text-xs">{log.total_tokens || '-'}</td>
                  <td className="p-3">{log.pii_detected ? <span className="text-red-400 text-xs">🚫 PII BLOCKED</span> : <span className="text-emerald-600 text-xs">✔ SAFE</span>}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
export default GovernanceLogs;
