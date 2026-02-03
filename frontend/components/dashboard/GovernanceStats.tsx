import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { AuditLog } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, Ban, Clock, CheckCircle } from "lucide-react";

export function GovernanceStats() {
    const [logs, setLogs] = useState<AuditLog[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchLogs = async () => {
        try {
            const data = await api.getRecentLogs(100);
            setLogs(data);
        } catch (e) {
            console.error("Failed to fetch logs", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLogs();
        // Refresh every 30s
        const interval = setInterval(fetchLogs, 30000);
        return () => clearInterval(interval);
    }, []);

    const stats = useMemo(() => {
        if (!logs.length) return { blocked24h: 0, p95: 0, health: "unknown" };

        const now = Date.now() / 1000; // python returns float seconds usually? Check models.py: time.time() -> matches. 
        // Wait, Time.time() in python is seconds. JS Date.now() is ms. 
        // We should assume AuditLog.timestamp is seconds (float).
        const oneDayAgo = now - 24 * 60 * 60;

        const recentLogs = logs.filter(l => l.timestamp > oneDayAgo);
        const blocked = recentLogs.filter(l => l.request_blocked).length;

        // P95 Latency
        const latencies = logs.map(l => l.latency_ms || 0).sort((a, b) => a - b);
        const p95Index = Math.floor(latencies.length * 0.95);
        const p95 = latencies.length ? latencies[p95Index] : 0;

        // Health Check
        let health = "green";
        const blockedRate = recentLogs.length ? (blocked / recentLogs.length) : 0;

        if (blockedRate > 0.10) health = "degraded"; // >10% blocked
        if (p95 > 5000) health = "degraded"; // Slow

        return { blocked24h: blocked, p95, health };
    }, [logs]);

    return (
        <div className="grid gap-4 md:grid-cols-3">

            <Card className="border-border bg-slate-900/50">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">System Health</CardTitle>
                    <Activity className={`h-4 w-4 ${stats.health === "green" ? "text-green-500" : "text-yellow-500"}`} />
                </CardHeader>
                <CardContent>
                    <div className={`text-2xl font-bold ${stats.health === "green" ? "text-green-500" : "text-yellow-500"}`}>
                        {stats.health === "green" ? "Operational" : "Degraded"}
                    </div>
                    <p className="text-xs text-muted-foreground">
                        Gateway services active
                    </p>
                </CardContent>
            </Card>

            <Card className="border-border bg-slate-900/50">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Blocked (24h)</CardTitle>
                    <Ban className="h-4 w-4 text-destructive" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold text-destructive">{stats.blocked24h}</div>
                    <p className="text-xs text-muted-foreground">
                        Policy violations prevented
                    </p>
                </CardContent>
            </Card>

            <Card className="border-border bg-slate-900/50">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">P95 Latency</CardTitle>
                    <Clock className="h-4 w-4 text-slate-400" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold text-slate-200">{stats.p95.toFixed(0)} ms</div>
                    <p className="text-xs text-muted-foreground">
                        Inference response time
                    </p>
                </CardContent>
            </Card>

        </div>
    );
}
