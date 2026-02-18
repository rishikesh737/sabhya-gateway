import { ChatRequest, ChatResponse, AuditLog } from "./types";

const API_URL = ""; // Empty because we rely on Next.js proxy in next.config.mjs

class ApiService {
    private getHeaders(isFormData: boolean = false): HeadersInit {
        const token = typeof window !== 'undefined' ? localStorage.getItem("token") : null;
        const headers: Record<string, string> = {};

        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        // Do NOT set Content-Type for FormData; browser sets it with boundary automatically
        if (!isFormData) {
            headers["Content-Type"] = "application/json";
        }

        return headers;
    }

    private async fetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        try {
            const response = await fetch(`${API_URL}${endpoint}`, options);

            if (response.status === 401) {
                console.error("Unauthorized! Redirecting to login...");
                if (typeof window !== 'undefined') window.location.href = "/login";
                throw new Error("Unauthorized");
            }

            if (!response.ok) {
                const errorBody = await response.text();
                throw new Error(`API Error ${response.status}: ${errorBody}`);
            }

            return await response.json();
        } catch (error) {
            console.error("Fetch error:", error);
            throw error;
        }
    }

    async chat(request: ChatRequest): Promise<ChatResponse> {
        return this.fetch<ChatResponse>("/v1/chat/completions", {
            method: "POST",
            headers: this.getHeaders(),
            body: JSON.stringify(request),
        });
    }

    async getAuditLogs(): Promise<AuditLog[]> {
        return this.fetch<AuditLog[]>("/v1/audit/logs", {
            method: "GET",
            headers: this.getHeaders(),
        });
    }

    async getDocuments(): Promise<{ documents: string[] }> {
        return this.fetch<{ documents: string[] }>("/rag/documents", {
            method: "GET",
            headers: this.getHeaders(),
        });
    }

    async uploadDocument(file: File): Promise<unknown> {
        const formData = new FormData();
        formData.append("file", file);

        return this.fetch("/v1/documents", {
            method: "POST",
            headers: this.getHeaders(true), // true = isFormData
            body: formData,
        });
    }

    async deleteDocument(filename: string): Promise<unknown> {
        return this.fetch(`/rag/documents/${encodeURIComponent(filename)}`, {
            method: "DELETE",
            headers: this.getHeaders(),
        });
    }
}

export const api = new ApiService();
