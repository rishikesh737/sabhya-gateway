# Sābhya AI: Trust Model & UI Invariants

This document formalizes the security guarantees provided by the Sābhya AI frontend. It defines the "Rules of Engagement" between the operator and the interface, ensuring that the UI never misrepresents the security state of the system options.

## 1. Core Philosophy: Why The UI Cannot Lie

In standard web applications, a successful HTTP response (`200 OK`) is treated as success. In Sābhya AI, **Transport Success ≠ Governance Success**.

An LLM might successfully generate a response that contains a **Secret Key** or **PII**. The Gateway might block this, or redact it. If the UI blindly displays the `200 OK` body, it violates the governance policy.

Therefore, Sābhya AI implements **Audit Supremacy**: The Audit Log (Governance Layer) is the authoritative source of truth, not the HTTP Response (Transport Layer).

## 2. UX Invariants (Non-Negotiable)

### Invariant A: No Green Without Audit
*   **Rule**: The UI shall NEVER display a Green "Safe/Operational" state until a valid, complete `AuditLog` record matching the current `RequestID` is retrieved and verified.
*   **Implication**: If the Audit Log is slow (latency), the UI remains **Grey (Pending)** completely indefinitely. It never "times out" into a success state.

### Invariant B: Audit Supremacy
*   **Rule**: In the event of a conflict between the content returned by the API and the status reported by the Audit Log, the Audit Log wins.
*   **Example**: 
    *   API returns: `200 OK` with body `"Here is the secret..."`
    *   Audit Log returns: `request_blocked: true`
    *   **UI Result**: **RED (Blocked)**. Content is hidden.

### Invariant C: Fail Safe on Uncertainty
*   **Rule**: If security metadata is missing, malformed, or `null`, the system assumes the state is **Unsafe**.
*   **Logic**: `pii_detected: null` -> **Yellow (Warning)**. `null !== safe`.

### Invariant D: Identity Isolation
*   **Rule**: Metrics and Audit data are strictly scoped to the *current* interactive session.
*   **Action**: Sending a new prompt immediately clears all previous verification indicators to prevent "Attribute Bleed" from a previous clean request to a new malicious one.

## 3. Failure → UI Mapping Table

| Backend State | Audit Signal | UI State | Why? |
| :--- | :--- | :--- | :--- |
| **Success** | `blocked: false`, `pii: false` | 🟢 **Green (Safe)** | Proven safe by signed audit log. |
| **Slow DB** | *Log Missing* | ⚪ **Grey (Pending)** | "Infinite Patience" prevents false confidence. |
| **Logic Err** | `pii: null` | 🟡 **Yellow (Unknown)** | "Fail Safe" logic treats ambiguity as risk. |
| **Redacted** | `pii: true` | 🟡 **Yellow (Redacted)** | Operator needs to know content was altered. |
| **Blocked** | `blocked: true` | 🔴 **Red (Blocked)** | Governance enforcement override. |
| **Down** | *5 Retries Failed* | 🟡 **Yellow (Unavailable)**| Degraded state. Assurance impossible. |

## 4. Test Verification
These invariants are programmatically testable via the `/test-governance` harness, which forces the UI into these specific data states without requiring backend fault injection.
