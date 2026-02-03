import { AlertCircle, CheckCircle2, ShieldAlert, Shield, ServerCrash, Clock } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ChatResponse, AuditLog } from "@/lib/types";
import { GatewayError } from "@/lib/api";

interface ResponseViewerProps {
    response: ChatResponse | null;
    error: GatewayError | null;
    isLoading: boolean;
    auditLog: AuditLog | null; // C. Redaction UX Requirement
}

export function ResponseViewer({ response, error, isLoading, auditLog }: ResponseViewerProps) {
    // Loading State
    if (isLoading) {
        return (
            <div className="flex w-full flex-col gap-4 rounded-lg border border-border bg-slate-900/20 p-6 animate-pulse">
                <div className="flex items-center gap-3">
                    <div className="h-6 w-6 rounded-full bg-slate-800" />
                    <div className="h-4 w-32 rounded bg-slate-800" />
                </div>
                <div className="space-y-2">
                    <div className="h-4 w-full rounded bg-slate-800" />
                    <div className="h-4 w-5/6 rounded bg-slate-800" />
                    <div className="h-4 w-4/6 rounded bg-slate-800" />
                </div>
            </div>
        );
    }

    // D. Error Taxonomy Handling
    if (error) {
        let icon = <ShieldAlert className="h-5 w-5" />;
        let title = "Request Blocked";
        let style = "border-destructive/50 bg-destructive/10 text-destructive";

        if (error.type === "RATE_LIMIT") {
            icon = <Clock className="h-5 w-5" />;
            title = "Rate Limit Exceeded";
            style = "border-orange-500/50 bg-orange-500/10 text-orange-500";
        } else if (error.type === "UPSTREAM") {
            icon = <ServerCrash className="h-5 w-5" />;
            title = "Upstream Failure";
            style = "border-yellow-500/50 bg-yellow-500/10 text-yellow-500";
        }

        return (
            <Alert variant="destructive" className={style}>
                {icon}
                <AlertTitle className="mb-2 text-lg font-semibold">{title}</AlertTitle>
                <AlertDescription className="text-sm opacity-90">
                    {error.message}
                </AlertDescription>
            </Alert>
        );
    }

    // Ready State
    if (!response) {
        return (
            <div className="flex h-[400px] flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border bg-slate-900/10 text-center text-muted-foreground">
                <div className="rounded-full bg-slate-900 p-4">
                    <CheckCircle2 className="h-8 w-8 opacity-20" />
                </div>
                <div>
                    <p className="font-medium">Ready for Inference</p>
                    <p className="text-sm opacity-60">Enter a prompt to begin security scanning and generation.</p>
                </div>
            </div>
        );
    }

    const content = response.choices[0]?.message.content || "";

    // Test Case 1 & 2: Pending vs Redacted vs Allowed
    // If Response is 200 OK, but Audit Log is missing -> PENDING (Neutral), not Safe.
    const isPending = !auditLog;
    const isRedacted = auditLog?.pii_detected;

    const borderColor = isPending ? 'border-border' : isRedacted ? 'border-yellow-500/30' : 'border-green-500/30';
    const bgColor = isPending ? 'bg-slate-900/30' : isRedacted ? 'bg-yellow-500/5' : 'bg-green-500/5';
    const textColor = isPending ? 'text-muted-foreground' : isRedacted ? 'text-yellow-500' : 'text-green-500';
    const statusText = isPending ? 'Governance Verification Pending...' : isRedacted ? 'Response Redacted' : 'Response Allowed';
    const Icon = isPending ? Clock : isRedacted ? Shield : CheckCircle2;

    return (
        <div className={`group relative rounded-lg border p-6 transition-all ${borderColor} ${bgColor}`}>

            <div className="mb-4 flex items-center justify-between border-b border-white/5 pb-4">
                <div className="flex items-center gap-2">
                    <Icon className={`h-3.5 w-3.5 ${textColor}`} />
                    <span className={`text-xs font-medium uppercase tracking-wider ${textColor}`}>
                        {statusText}
                    </span>
                </div>
                <span className="text-xs text-muted-foreground">
                    {response.model} • {isPending ? "Calculating tokens..." : `${response.usage.total_tokens} tokens`}
                </span>
            </div>

            <div className="prose prose-invert max-w-none text-sm leading-relaxed text-slate-200">
                <p className="whitespace-pre-wrap">{content}</p>
            </div>

            {isRedacted && (
                <div className="mt-4 rounded bg-yellow-500/10 p-2 text-xs text-yellow-500">
                    <span className="font-bold">Notice:</span> PII was detected and redacted from this response to comply with data protection policies.
                </div>
            )}

            {isPending && (
                <div className="mt-4 flex items-center gap-2 rounded bg-slate-800/50 p-2 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3 animate-pulse" />
                    <span>Waiting for authoritative audit record...</span>
                </div>
            )}
        </div>
    );
}
