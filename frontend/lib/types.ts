export interface AuditLog {
    request_id: string;
    timestamp: number;
    user_hash: string;
    model: string;
    status_code: number;
    latency_ms: number | null;
    prompt_tokens: number | null;
    completion_tokens: number | null;
    total_tokens: number | null;
    pii_detected: boolean | null;
    request_blocked: boolean | null;
}

export interface ChatMessage {
    role: "system" | "user" | "assistant";
    content: string;
}

export interface ChatRequest {
    model: string;
    messages: ChatMessage[];
    // Stream is always false for this version as per guidelines
}

export interface ChatResponse {
    id: string;
    object: string;
    created: number;
    model: string;
    choices: {
        index: number;
        message: ChatMessage;
        finish_reason: string;
    }[];
    usage: {
        prompt_tokens: number;
        completion_tokens: number;
        total_tokens: number;
    };
}

export interface GovernanceMetrics {
    total_requests: number;
    blocked_requests: number;
    p95_latency: number;
    system_health: "green" | "degraded" | "down";
}
