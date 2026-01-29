# LLM SaaS Venture

A secure, scalable, and auditable Large Language Model (LLM) platform designed for enterprise environments. This project provides a chat interface backed by a hardened API gateway and a local inference engine.

## 1. Architecture

The system follows a three-tier microservices architecture:

1.  **Frontend (UI):** A **Streamlit** application that provides a user-friendly chat interface. It communicates exclusively with the Backend API.
2.  **Backend (API Gateway):** A **FastAPI** service that acts as the secure entry point. It handles authentication, rate limiting, request validation, and structured logging before forwarding requests to the inference engine.
3.  **Inference Engine:** **Ollama** running locally within the cluster (or pod). It hosts and executes the LLM models (e.g., Mistral, TinyLlama) to generate responses.

**Flow:** `User` -> `Streamlit UI` -> `FastAPI Gateway` -> `Ollama`

## 2. Security Features

This project prioritizes security and is designed to run in strict environments like OpenShift.

*   **Hardened Containers:**
    *   **Non-Root User:** The API runs as a non-privileged user (UID 10001) to mitigate potential container breakout attacks.
    *   **Minimal Base Image:** Built on `python:3.12-slim` to reduce the attack surface.
*   **Read-Only Filesystem:**
    *   The container's root filesystem is mounted as **Read-Only**.
    *   Writeable areas are strictly limited to explicit `tmpfs` mounts (e.g., `/tmp`) for necessary temporary files, ensuring no persistent malware can hide in the container image at runtime.
*   **Privilege Dropping:**
    *   All Linux capabilities are dropped (`drop: ["ALL"]`), preventing the process from performing privileged system operations.
    *   `allowPrivilegeEscalation: false` prevents the process from gaining new privileges.

## 3. How to Run Locally (Podman)

You can run the entire stack locally using Podman.

### Prerequisites
*   Podman
*   Python 3.12 (for local development, optional)

### Steps

1.  **Build the Backend Image:**
    ```bash
    cd backend/llm-api
    podman build -t localhost/llm-api:chat .
    ```

2.  **Create a Pod:**
    Create a pod to share the network namespace between containers (allowing them to talk via `localhost`).
    ```bash
    podman pod create --name llm-pod -p 8000:8000 -p 8501:8501
    ```

3.  **Run Ollama (Inference):**
    ```bash
    podman run -d --pod llm-pod --name ollama \
      -v ollama_data:/root/.ollama \
      docker.io/ollama/ollama:latest
    ```
    *Note: You may need to pull a model first: `podman exec -it ollama ollama pull mistral:7b-instruct-q4_K_M`*

4.  **Run the Backend API:**
    ```bash
    podman run -d --pod llm-pod --name llm-api \
      --read-only \
      --tmpfs /tmp \
      --env OLLAMA_HOST=localhost \
      --env API_KEYS=secret-key \
      localhost/llm-api:chat
    ```

5.  **Run the Frontend:**
    ```bash
    cd frontend
    pip install -r requirements.txt
    streamlit run app.py
    ```

## 4. How to Run on OpenShift

The project includes Kubernetes/OpenShift manifests in the `infra/k8s/` directory.

1.  **Create a Project (Namespace):**
    ```bash
    oc new-project llm-venture
    ```

2.  **Apply Configuration & Secrets:**
    *   Copy `infra/k8s/secrets.example.yaml` to `infra/k8s/secrets.yaml` and add your actual API keys.
    ```bash
    oc apply -f infra/k8s/secrets.yaml
    oc apply -f infra/k8s/pvc.yaml
    oc apply -f infra/k8s/ollama-init.yaml
    ```

3.  **Deploy the Stack:**
    ```bash
    oc apply -f infra/k8s/llm-stack.yaml
    ```

This will deploy a Pod containing both the API and Ollama, utilizing shared storage for models and a read-only filesystem configuration for security.

## 5. Governance & Auditability

To satisfy enterprise compliance and audit requirements, the system enforces strict logging standards:

*   **Raw JSON Logs:** The Backend API uses `structlog` to emit all logs in a structured JSON format.
*   **Audit Trail:** Every interaction is logged with high-fidelity details, including:
    *   Timestamp (ISO format)
    *   User Hash (Anonymized identity)
    *   Model Requested
    *   Response Time / Duration
    *   Error Details (if any)

**Why JSON?**
JSON logs are machine-readable, making them instantly ingestible by SIEM (Security Information and Event Management) tools like Splunk, Datadog, or ELK Stack. This allows security teams to query, visualize, and alert on usage patterns or anomalies without complex parsing rules.
```
