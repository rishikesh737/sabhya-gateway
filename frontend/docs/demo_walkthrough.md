# Sābhya AI: Guided Demo Walkthrough

**Purpose**: This script allows any operator to demonstrate the security and governance capabilities of Sābhya AI without improvisation. It proves the system's "Fail Safe" and "Audit Supremacy" behaviors.

**Prerequisites**:
- Frontend running on `http://localhost:3000`
- Backend running on `http://localhost:8000` (Optional for harness demo)

---

## Part 1: The Access Gate (Zero-Trust Identity)

1.  **Navigate** to `http://localhost:3000/`.
2.  **Observe**: You are immediately redirected to `/login`.
    *   *Explanation*: "The system employs a strict 'Default Deny' routing policy. No route is accessible without an established session hash."
3.  **Action**: Click **"Acknowledge & Enter"**.
4.  **Observe**: Transition to the main interface.
    *   *Explanation*: "This is a declarative access gate. We do not handle passwords in the browser to reduce the attack surface. Identity is asserted via the secure gateway."

## Part 2: The Trusted Interface (Main UI)

1.  **Observe**: The UI is Dark, Minimal, and "Calm".
    *   *Explanation*: "The interface is designed for high-stress security operations. It avoids playful interactions to maintain authority."
2.  **Action**: Click the **Settings (Gear)** icon in the header.
3.  **Observe**: The Identity is read-only (`System User`).
    *   *Explanation*: "The operator cannot impersonate other users. The session is immutable."
4.  **Navigate** back to **Home**.

## Part 3: Establishing Trust (The Happy Path)

1.  **Action**: Enter prompt `Hello Sābhya` and submit.
2.  **Observe**:
    *   **State 1 (0-1s)**: Response appears, but the Status is **Grey (Pending)**.
    *   **State 2 (1s+)**: Status turns **Green (Response Allowed)**.
    *   *Explanation*: "Notice the system did not turn Green immediately. It waited for the asynchronous Audit Log verification. We call this 'Infinite Patience'."

## Part 4: Adversarial Stress Test (The Harness)

*Navigate to `http://localhost:3000/test-governance`*

### Scenario A: The "Slow Audit" (Infinite Patience)
1.  **Click**: `Pending (Slow DB)`
2.  **Observe**:
    *   Right Sidebar: Skeleton Loading.
    *   Viewer: "Governance Verification Pending..." (Grey).
    *   *Key Point*: "The UI refuses to show Green/Safe. It holds this state indefinitely until proof arrives."

### Scenario B: PII Redaction (Known Risk)
1.  **Click**: `PII Redacted`
2.  **Observe**:
    *   Viewer Border: **Yellow**.
    *   Banner: "Notice: PII was detected..."
    *   *Key Point*: "The operator is explicitly warned that the content they are seeing has been altered by the DLP engine."

### Scenario C: Security Block (Audit Supremacy)
1.  **Click**: `Audit Blocking`
2.  **Observe**:
    *   Viewer: **Red Alert** ("Security Block").
    *   Content: **Hidden**.
    *   *Key Point*: "This is Audit Supremacy. Even if the LLM generated text, the Policy Engine denied release. The UI enforces this denial."

### Scenario D: Malformed Data (Fail Safe)
1.  **Click**: `Malformed / Null`
2.  **Observe**:
    *   Viewer: **Yellow** ("Security Status Unknown").
    *   Warning: "Security metadata is incomplete."
    *   *Key Point*: "If the backend sends `null` or bad data, the system defaults to Warning, never Safe. It is Fail Safe."

---

**End of Demo**: "This concludes the demonstration of Sābhya AI's governance guarantees. The system prioritizes Truth over Availability."
