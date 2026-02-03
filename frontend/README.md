# Sābhya AI: Zero-Trust Secure LLM Gateway Frontend

**Sābhya AI** (Project Chakravyuha) is a governance-first interface designed for high-assurance data environments. It provides a disciplined, zero-trust window into the **Vajra LLM Gateway**, enforcing strict auditability, PII redaction, and policy compliance for generative AI interactions.

> **Note**: This is **not a chatbot**. This is a **security console** for governed inference.

---

## 🏛️ Architecture & Trust Model

Sābhya AI operates on a **"Trust but Verify"** model where the frontend assumes the network is hostile and the backend is the single source of truth.

```ascii
[ Operator ] <---> [ Sābhya UI (Zero-Trust) ] <---> [ Vajra Gateway ] <---> [ LLM ]
                          |                               ^
                          v                               |
                 [ Browser Storage ]             [ Audit Log DB ]
                    (State Only)                  (Truth Source)
```

### Core Guarantees
1.  **Transport ≠ Governance**: A `200 OK` network response from an LLM does *not* imply safety. The UI only marks a request as "Safe" (Green) after cross-referencing a valid cryptographic Audit Log.
2.  **Audit Supremacy**: If the Governance backend flags a request as **Blocked**, the UI suppresses the content—even if the LLM successfully generated text. Use of the system *requires* governance.
3.  **Fail Safe Uncertainty**: Use of missing data, partial logs, or network timeouts results in a **Yellow (Warning)** or **Grey (Pending)** state. The system never "fails open" to Green.
4.  **No Secrets in Browser**: Identity is asserted via a Declarative Access Gate. No passwords or API keys are stored in the client.

---

## 🚫 What This System Deliberately Does NOT Do

*   **No "User Management"**: Auth is handled upstream. Sābhya is an interface for authenticated sessions.
*   **No "Optimistic UI"**: We do not predict success. We wait for proof.
*   **No "Chat History" Persistence**: Sessions are ephemeral. History resets on reload to minimize surface area.

## 🚀 Key Features

*   **Adversarial State Handling**: Correctly visualizes Redaction, Blocking, and Latency without confusing the operator.
*   **Governance Stress Harness**: Built-in verification tool (`/test-governance`) to prove the UI cannot be tricked by malformed backend signals.
*   **Identity-Aware Gate**: Frontend-only session gating to acknowledge governed workspace entry.

## 📚 Documentation

*   [**Trust Model**](./docs/trust_model.md): Deep dive into why the UI cannot lie.
*   [**Guided Demo**](./docs/demo_walkthrough.md): Step-by-step verification script.
*   [**Threat Model**](./docs/threat_model_summary.md): Summary of addressed risks.

## 🛠️ Deployment

```bash
# Install Dependencies
npm install

# Start Development Server
npm run dev
# Access at http://localhost:3000
```
