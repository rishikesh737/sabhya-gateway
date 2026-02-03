# Sābhya AI Release Notes

**Version**: v1.0 — "Chakravyuha"
**Status**: Frozen / Release Candidate 1
**Date**: 2026-02-01

---

## 🛡️ What is this Release?

**Sābhya AI (v1.0)** is the first stable release of the zero-trust frontend for the Vajra LLM Gateway.
This release shifts the paradigm of LLM interfaces from "User Experience First" to **"Governance First"**.

**Positioning Statement**:
> Sābhya AI is a **Governance Console**, not a chat interface. Unlike standard LLM clients that prioritize speed and fluidity, Sābhya strictly enforces a **"Trust but Verify"** architecture where transport success (`200 OK`) is never treated as governance success. It implements **infinite patience**, refusing to display content—no matter how fast it arrives—until a cryptographic audit log confirms compliance.

## ✨ Key Features (Included)

*   **Zero-Trust Architecture**: Assumes the network is hostile. Verify all packets via separate Audit Log channel.
*   **Declarative Access Gate**: Frontend-only identity assertion (`/auth/login`) acknowledging strict workspace entry.
*   **Adversarial UX State Machine**:
    *   **Infinite Patience**: Grey "Pending" state for slow audits.
    *   **Audit Supremacy**: Red "Blocked" state overrides any LLM content.
    *   **Fail Safe**: Yellow "Warning" state for missing/null security metadata.
*   **Governance Verification Harness**: Built-in test suite (`/test-governance`) to manually confirm fail-safe behaviors.
*   **Strict PII Redaction UI**: Explicit indicators when content has been altered by DLP engines.

## 🛑 Intentional Exclusions (Scope Lock)

To maintain security integrity, the following features are **explicitly excluded** from v1.0:
*   **User Management**: We do not handle password resets or registration flow.
*   **Chat History Persistence**: Sessions are ephemeral. Refreshing the tab clears the workspace. "No footprints left behind."
*   **Chatbot Personalities**: No avatars, no "thinking" animations, no friendly banter.
*   **Mobile Optimization**: Designed for desktop Security Operations Centers (SOC).

## ⚠️ Known Limitations

*   **Single-Session Volatility**: If the browser tab is closed, the session and request history are lost immediately (Feature, not Bug).
*   **Audit Latency**: If the backend DB is slow (>30s), the UI will remain in "Pending" state indefinitely. There is no timeout fallback.
*   **Manual Token Entry**: In this version, the Access Gate simulates authentication. True backend JWT integration is scheduled for v2.0.

---
*End of Release Notes.*
