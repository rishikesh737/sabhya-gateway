import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { AuditLog } from "@/lib/types";
import { Copy, ShieldAlert, ShieldCheck, Clock } from "lucide-react";

interface AuditSidebarProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    auditLog: AuditLog | null;
    isLoading: boolean;
    auditError?: boolean; // Test Case 4: Audit Endpoint Down
}

export function AuditSidebar({ open, onOpenChange, auditLog, isLoading, auditError }: AuditSidebarProps) {
    return (
        <Sheet open={open} onOpenChange={onOpenChange} modal={false}>
            <SheetContent side="right" className="w-[400px] border-l border-border bg-background p-0 shadow-2xl sm:max-w-[450px]">
                <SheetHeader className="border-b border-border bg-slate-950/50 p-6">
                    <SheetTitle className="text-lg font-semibold">Request Metadata</SheetTitle>
                </SheetHeader>
                <ScrollArea className="h-[calc(100vh-80px)] p-6">
                    {isLoading ? (
                        <div className="space-y-4">
                            <div className="h-8 w-3/4 animate-pulse rounded bg-slate-800" />
                            <div className="h-24 w-full animate-pulse rounded bg-slate-800" />
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <Clock className="h-3 w-3 animate-spin" />
                                <span>Fetching authoritative governance record...</span>
                            </div>
                        </div>
                    ) : auditError ? (
                        <div className="flex h-40 flex-col items-center justify-center gap-2 rounded border border-yellow-500/20 bg-yellow-500/5 p-4 text-center">
                            <ShieldAlert className="h-8 w-8 text-yellow-500 opacity-50" />
                            <p className="font-medium text-yellow-500">Audit Service Unavailable</p>
                            <p className="text-xs text-muted-foreground">Governance verification failed. Metrics may be incomplete.</p>
                        </div>
                    ) : auditLog ? (
                        <div className="space-y-8">

                            {/* Security Status Block */}
                            <div className="space-y-3">
                                <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Security Status</h3>
                                {auditLog.request_blocked ? (
                                    <div className="flex items-start gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-4">
                                        <ShieldAlert className="mt-0.5 h-5 w-5 text-destructive" />
                                        <div>
                                            <p className="font-medium text-destructive">Blocked</p>
                                            <p className="text-xs text-destructive/80">Policy violation triggered</p>
                                        </div>
                                    </div>
                                ) : auditLog.pii_detected ? (
                                    <div className="flex items-start gap-3 rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-4">
                                        <ShieldAlert className="mt-0.5 h-5 w-5 text-yellow-500" />
                                        <div>
                                            <p className="font-medium text-yellow-500">PII Redacted</p>
                                            <p className="text-xs text-yellow-500/80">Data masked by DLP engine</p>
                                        </div>
                                    </div>
                                ) : (auditLog.request_blocked === null || auditLog.request_blocked === undefined || auditLog.pii_detected === null || auditLog.pii_detected === undefined) ? (
                                    <div className="flex items-start gap-3 rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-4">
                                        <ShieldAlert className="mt-0.5 h-5 w-5 text-yellow-500" />
                                        <div>
                                            <p className="font-medium text-yellow-500">Security Unknown</p>
                                            <p className="text-xs text-yellow-500/80">Audit metadata incomplete.</p>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex items-start gap-3 rounded-lg border border-green-500/50 bg-green-500/10 p-4">
                                        <ShieldCheck className="mt-0.5 h-5 w-5 text-green-500" />
                                        <div>
                                            <p className="font-medium text-green-500">Clean Request</p>
                                            <p className="text-xs text-green-500/80">No violations detected</p>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Metrics Block */}
                            <div className="space-y-3">
                                <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Performance & Tokens</h3>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="rounded-md border border-border bg-slate-900/50 p-3">
                                        <p className="text-xs text-muted-foreground">Latency</p>
                                        <p className="font-mono text-lg font-medium">
                                            {auditLog.latency_ms !== undefined && auditLog.latency_ms !== null
                                                ? `${auditLog.latency_ms.toFixed(0)} ms`
                                                : "Unavailable"}
                                        </p>
                                    </div>
                                    <div className="rounded-md border border-border bg-slate-900/50 p-3">
                                        <p className="text-xs text-muted-foreground">Total Tokens</p>
                                        <p className="font-mono text-lg font-medium">
                                            {auditLog.total_tokens !== undefined && auditLog.total_tokens !== null
                                                ? auditLog.total_tokens
                                                : "Unavailable"}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Traceability */}
                            <div className="space-y-3">
                                <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Traceability</h3>
                                <div className="rounded-md border border-border bg-slate-900/50 p-3">
                                    <p className="text-xs text-muted-foreground">Request ID</p>
                                    <code className="break-all text-xs font-mono text-slate-300">{auditLog.request_id}</code>
                                </div>
                                <div className="rounded-md border border-border bg-slate-900/50 p-3">
                                    <p className="text-xs text-muted-foreground">Model</p>
                                    <p className="text-sm text-slate-300">{auditLog.model}</p>
                                </div>
                            </div>

                        </div>
                    ) : (
                        <div className="flex h-40 flex-col items-center justify-center gap-2 text-muted-foreground">
                            <ShieldCheck className="h-8 w-8 opacity-20" />
                            <p className="text-sm">Select a request to view audit details</p>
                        </div>
                    )}
                </ScrollArea>
            </SheetContent>
        </Sheet>
    )
}
