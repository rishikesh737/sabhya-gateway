import { ChatRequest, ChatResponse, AuditLog } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

// D. Error Taxonomy
export class GatewayError extends Error {
    constructor(message: string, public type: "BLOCKED" | "RATE_LIMIT" | "UPSTREAM" | "GATEWAY_OFFLINE" | "UNKNOWN") {
        super(message);
        this.name = "GatewayError";
    }
}

class ApiService {
    private async fetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        const headers = {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${API_KEY}`,
            ...options.headers,
        };

        try {
            const response = await fetch(`${API_URL}${endpoint}`, {
                ...options,
                headers,
            });

            if (!response.ok) {
                let errorType: "BLOCKED" | "RATE_LIMIT" | "UPSTREAM" | "GATEWAY_OFFLINE" | "UNKNOWN" = "UNKNOWN";

                if (response.status === 400) errorType = "BLOCKED";
                else if (response.status === 429) errorType = "RATE_LIMIT";
                else if (response.status === 502 || response.status === 503 || response.status === 504) errorType = "UPSTREAM";

                let errorDetail = `HTTP error! status: ${response.status}`;
                try {
                    const body = await response.json();
                    if (body.detail) errorDetail = body.detail;
                } catch (_) { }

                throw new GatewayError(errorDetail, errorType);
            }

            return response.json();
        } catch (error) {
            if (error instanceof GatewayError) throw error;
            // Distinguish Network/Fetch failures
            throw new GatewayError("Gateway Unreachable (Network Down)", "GATEWAY_OFFLINE");
        }
    }

    async sendChat(payload: ChatRequest, requestId?: string): Promise<ChatResponse> {
        const headers: Record<string, string> = {};
        if (requestId) {
            headers["X-Request-ID"] = requestId;
        }

        return this.fetch<ChatResponse>("/v1/chat/completions", {
            method: "POST",
            body: JSON.stringify(payload),
            headers,
        });
    }

    // A. Audit log timing - Robust implementation with Retries
    async getAuditLog(requestId: string, attempts = 5, delay = 1000): Promise<AuditLog | null> {
        for (let i = 0; i < attempts; i++) {
            try {
                // Scope: Fetch specific request ID via list filtering (backend limitation workaround)
                // Ideally backend should support GET /v1/audit/logs/{id}
                const logs = await this.getRecentLogs(50);
                const log = logs.find((l) => l.request_id === requestId);

                if (log) return log;

                // Wait before retry
                if (i < attempts - 1) await new Promise(r => setTimeout(r, delay));
            } catch (e) {
                console.error(`Attempt ${i + 1} failed to fetch audit log`, e);
                if (i < attempts - 1) await new Promise(r => setTimeout(r, delay));
            }
        }
        return null;
    }

    async getRecentLogs(limit: number = 50): Promise<AuditLog[]> {
        return this.fetch<AuditLog[]>(`/v1/audit/logs?limit=${limit}`);
    }

    async getMetrics(): Promise<string> {
        const headers = { "Authorization": `Bearer ${API_KEY}` };
        const response = await fetch(`${API_URL}/metrics`, { headers });
        return response.text();
    }
}

export const api = new ApiService();
