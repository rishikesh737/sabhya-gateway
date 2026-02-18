"use client";

import { useState } from "react";
import { ResponseViewer } from "@/components/interaction/ResponseViewer";
import { AuditSidebar } from "@/components/layout/AuditSidebar";
import { AuditLog, ChatResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ShieldAlert, Shield, Clock, CheckCircle2 } from "lucide-react";

// Mock Data Generators relative to "Chakravyuha" specs
const mockResponse: ChatResponse = {
    id: "test-uuid",
    object: "chat.completion",
    created: Date.now(),
    model: "mistral:7b-instruct",
    choices: [{
        index: 0,
        message: { role: "assistant", content: "This is a test response content. It should be hidden if blocked." },
        finish_reason: "stop"
    }],
    usage: { prompt_tokens: 10, completion_tokens: 20, total_tokens: 30 }
};

const mockAuditClean: AuditLog = {
    request_id: "test-uuid",
    timestamp: Date.now() / 1000,
    user_hash: "system",
    model: "mistral:7b-instruct",
    status_code: 200,
    latency_ms: 150,
    prompt_tokens: 10,
    completion_tokens: 20,
    total_tokens: 30,
    pii_detected: false,
    request_blocked: false
};

export default function GovernanceTestPage() {
    const [selectedScenario, setSelectedScenario] = useState<string>("clean");

    // Scenario Logic
    let currentLog: AuditLog | null = null;
    let auditError = false;

    switch (selectedScenario) {
        case "clean":
            currentLog = mockAuditClean;
            break;
        case "pending":
            currentLog = null; // Scenario 1: Pending
            break;
        case "timeout":
            currentLog = null;
            auditError = true; // Scenario 2: Unavailable
            break;
        case "redacted":
            currentLog = { ...mockAuditClean, pii_detected: true }; // Scenario 3: PII
            break;
        case "blocked":
            currentLog = { ...mockAuditClean, request_blocked: true, status_code: 400 }; // Scenario 4: Blocked
            break;
        case "malformed":
            currentLog = { ...mockAuditClean, pii_detected: null, request_blocked: null }; // Scenario 5: Unknown
            break;
    }

    return (
        <div className="flex h-screen flex-col bg-slate-950 p-6 text-slate-100">
            <h1 className="mb-6 text-2xl font-bold tracking-tight">Phase 7: Governance Stress Test Harness</h1>

            <div className="grid grid-cols-12 gap-6">

                {/* Controls */}
                <Card className="col-span-3 border-slate-800 bg-slate-900">
                    <CardHeader>
                        <CardTitle className="text-sm font-medium uppercase tracking-wider text-slate-400">Adversarial Scenarios</CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-2">
                        <Button variant={selectedScenario === "clean" ? "default" : "secondary"} onClick={() => setSelectedScenario("clean")} className="justify-start">
                            <CheckCircle2 className="mr-2 h-4 w-4 text-green-500" /> Clean Request
                        </Button>
                        <Button variant={selectedScenario === "pending" ? "default" : "secondary"} onClick={() => setSelectedScenario("pending")} className="justify-start">
                            <Clock className="mr-2 h-4 w-4 text-slate-400" /> Pending (Slow DB)
                        </Button>
                        <Button variant={selectedScenario === "timeout" ? "default" : "secondary"} onClick={() => setSelectedScenario("timeout")} className="justify-start">
                            <ShieldAlert className="mr-2 h-4 w-4 text-yellow-500" /> Audit Timeout
                        </Button>
                        <Button variant={selectedScenario === "redacted" ? "default" : "secondary"} onClick={() => setSelectedScenario("redacted")} className="justify-start">
                            <Shield className="mr-2 h-4 w-4 text-yellow-500" /> PII Redacted
                        </Button>
                        <Button variant={selectedScenario === "blocked" ? "default" : "secondary"} onClick={() => setSelectedScenario("blocked")} className="justify-start">
                            <ShieldAlert className="mr-2 h-4 w-4 text-destructive" /> Audit Blocking
                        </Button>
                        <Button variant={selectedScenario === "malformed" ? "default" : "secondary"} onClick={() => setSelectedScenario("malformed")} className="justify-start">
                            <ShieldAlert className="mr-2 h-4 w-4 text-orange-500" /> Malformed / Null
                        </Button>
                    </CardContent>
                </Card>

                {/* Response Viewer Area */}
                <div className="col-span-6 space-y-6">
                    <Card className="border-border bg-slate-900">
                        <CardHeader><CardTitle className="text-sm">Response Viewer State</CardTitle></CardHeader>
                        <CardContent>
                            <ResponseViewer
                                response={mockResponse}
                                error={null}
                                isLoading={false}
                                auditLog={currentLog}
                            />
                        </CardContent>
                    </Card>

                    <div className="rounded-md border border-dashed border-slate-800 p-4 text-xs text-slate-500">
                        <p className="font-mono">Current State:</p>
                        <pre>{JSON.stringify({ selectedScenario, auditError, auditLog: currentLog }, null, 2)}</pre>
                    </div>
                </div>

                {/* Sidebar Preview */}
                <div className="col-span-3">
                    <p className="mb-2 text-xs font-medium text-slate-500">Sidebar Preview (Always Active)</p>
                    <div className="relative h-[600px] overflow-hidden rounded-lg border border-slate-800 bg-background">
                        <AuditSidebar
                            open={true}
                            onOpenChange={() => { }}
                            auditLog={currentLog}
                            isLoading={!currentLog && !auditError}
                            auditError={auditError}
                        />
                    </div>
                </div>

            </div>
        </div>
    );
}
