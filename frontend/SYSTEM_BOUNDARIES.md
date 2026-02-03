# Sābhya AI: System Boundaries (Scope Lock)

**Purpose**: This document explicitly defines the boundaries of the Sābhya AI project to prevent scope creep and align expectations.

---

## 🔒 Hard Boundaries (The "Never" List)
*The following features are structurally incompatible with our Zero-Trust philosophy and will **NEVER** be implemented in this codebase:*

1.  **Client-Side Analytics**: We do not track operator mouse movements or engagement. (Privacy Risk).
2.  **Optimistic UI Updates**: We never show a message as "Sent/Received/Safe" before backend confirmation. (Trust Risk).
3.  **Third-Party Auth Providers**: No "Login with Google/GitHub". Identity must be federated via the secure Gateway only.
4.  **Markdown/HTML Rendering in Prompts**: We treat all user input as plain text to prevent XSS/Injection vectors.

## 🚧 Backend Dependencies (The "Not Us" List)
*Features often requested that are strictly Backend responsibilities:*

*   **Model Selection**: The frontend displays what the backend returns (`model` field). We do not hardcode model lists.
*   **Rate Limits**: We display 429 errors; we do not implement client-side throttling buckets.
*   **DLP/Redaction Logic**: The frontend *displays* redaction; it does not *perform* regex redaction.

## 🔮 Future Work (v2.0+)
*Features acknowledged but deferred:*

*   **Streaming Support**: Currently disabled. v2.0 will require a new "Streaming Audit" protocol.
*   **Role-Based Access Control (RBAC) UI**: Admin panels for configuring policy rules.
*   **Export to PDF**: For audit trail reporting.

---
**Status**: This scope is **LOCKED** for v1.0.
