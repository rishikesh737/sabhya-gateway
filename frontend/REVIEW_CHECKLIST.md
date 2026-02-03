# Sābhya AI: Reviewer Checklist

**Purpose**: This document guides external auditors (Security Engineers, Policy Fellows) on how to validatethe claims made by Sābhya AI.

---

## 1. Setup & Access
- [ ] **Run System**: `npm run dev` (Frontend) + `uvicorn app.main:app` (Backend).
- [ ] **Access Gate**: Verify accessing `http://localhost:3000` redirects to `/login`.
- [ ] **Harness**: Navigate to `http://localhost:3000/test-governance`.

## 2. Verifying Trust Invariants (The "Cannot Lie" Check)
*Use the Test Harness to verify these behaviors without needing to attack the backend.*

### A. The "Fail Safe" Invariant
**Claim**: *The system treats ambiguity as risk.*
- [ ] **Action**: In Harness, click **"Malformed / Null"**.
- [ ] **Verify**: UI shows **Yellow**. Warning says "Security metadata is incomplete."
- [ ] **Anti-Pattern**: Ensure UI **DOES NOT** show Green/Safe.

### B. The "Audit Supremacy" Invariant
**Claim**: *Governance signals override Transport payloads.*
- [ ] **Action**: In Harness, click **"Audit Blocking"**.
- [ ] **Verify**: UI shows **Red Alert**. Content text is **Hidden**.
- [ ] **Anti-Pattern**: Ensure the "Test response content" is **NOT** visible.

### C. The "Infinite Patience" Invariant
**Claim**: *The system waits indefinitely for proof.*
- [ ] **Action**: In Harness, click **"Pending (Slow DB)"**.
- [ ] **Verify**: UI shows **Grey (Pending)**.
- [ ] **Anti-Pattern**: Ensure UI **DOES NOT** timeout to Green after any duration.

## 3. Boundary Checks
- [ ] **Secrets**: Check `Application > Storage > Local/Session Storage`. ensure NO API keys or passwords are stored. Only `sabhya_session`.
- [ ] **Network**: Open DevTools Network tab. Ensure NO calls are made to external LLM providers (e.g., `openai.com`). All traffic must target `:8000`.

## 4. Common Misunderstandings (Reviewer Notes)
*   **"The UI feels slow."**: It is not slow; it is synchronized to the Audit DB write speed. This is intentional.
*   **"I can't see my old chats."**: History is not persisted to reduce liability.
*   **"The styling is boring."**: It is "Calm Authority". This is a design choice, not a lack of polish.
