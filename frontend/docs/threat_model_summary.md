# Sābhya AI: Threat Model Summary

This document outlines the specific threats Sābhya AI is designed to mitigate at the User Interface level, and explicitly defines the boundaries of its protection.

## 1. Mitigated Threats (In-Scope)

| ID | Threat | Mitigation Strategy | Component |
| :--- | :--- | :--- | :--- |
| **UX-T1** | **False Confidence** (Operator assumes safety due to `200 OK`) | **Audit Supremacy**: UI requires explicit Audit Log confirmation before showing Green. | `ResponseViewer` |
| **UX-T2** | **Attribute Bleed** (Metadata from previous benign request applied to new malicious one) | **Identity Isolation**: Fresh UUID generation and state clearing on every submit. | `page.tsx` |
| **UX-T3** | **Hidden Redaction** (Content altered without operator knowledge) | **Explicit Signals**: Yellow "Redacted" state when `pii_detected` is observed. | `AuditSidebar` |
| **UX-T4** | **Policy Bypass** (Displaying blocked content) | **Block Enforcement**: Hiding content payload if `request_blocked` is true. | `ResponseViewer` |
| **UX-T5** | **Undefined State** (Backend sends nulls/malformed data) | **Fail Safe**: Treating `null/undefined` as "Unknown Risk" (Yellow). | `types.ts` |
| **UX-T6** | **Session Hijacking** (Lateral movement) | **Frontend Gate**: `sessionStorage` persistence only (cleared on tab close). | `AuthGuard` |

## 2. Out-of-Scope (Trusted Boundaries)

The following are **NOT** mitigated by the frontend and must be handled by the **Vajra Gateway**:

*   **Backend Compromise**: If the Gateway itself provides a falsified Audit Log (signed/valid format but lying), the Frontend will trust it.
*   **Browser Compromise**: Standard XSS/Malware on the operator's machine is outside the application's threat model.
*   **Network Man-in-the-Middle**: We rely on HTTPS transport security. Sābhya does not implement application-layer encryption on top of TLS.

## 3. Trust Assumptions

1.  **The Gateway is Truth**: We assume the `GET /v1/audit/logs` endpoint, when reachable, provides the authoritative policy decision.
2.  **The Operator is Honest but Fallible**: The UI prevents *mistakes*, not *malice*. A malicious operator can inspect Network tabs to see raw data. The UI's goal is to prevent accidental misuse.
