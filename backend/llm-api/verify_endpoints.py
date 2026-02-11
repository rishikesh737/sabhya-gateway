import os
# Set DB URL to sqlite for testing
os.environ["DATABASE_URL"] = "sqlite:///./sabhya_verify.db"
os.environ["SECRET_KEY"] = "test-secret-key-must-be-very-long-to-pass-validation-32chars"
os.environ["API_KEYS"] = "sk_legacy_test"
os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1,testserver"

from fastapi.testclient import TestClient
from app.main import app
from app.auth.security import create_access_token, Roles
import json

def run_tests():
    with TestClient(app) as client:
        print("\n--- Testing Legacy Auth ---")
        response = client.get("/health/live", headers={"Authorization": "Bearer sk_legacy_test"})
        if response.status_code == 200:
            print("Legacy Auth: PASS")
        else:
            print(f"Legacy Auth: FAIL ({response.status_code})")
            print(response.text)

        print("\n--- Testing JWT Auth ---")
        token = create_access_token(user_id="test_user", roles=[Roles.USER])
        response = client.get("/health/live", headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            print("JWT Auth: PASS")
        else:
            print(f"JWT Auth: FAIL ({response.status_code})")
            print(response.text)

        print("\n--- Testing Streaming Audit Log ---")
        # Using JWT
        token = create_access_token(user_id="test_user", roles=[Roles.USER])
        
        try:
            response = client.post(
                "/v1/chat/completions/stream",
                headers={"Authorization": f"Bearer {token}"},
                json={"messages": [{"role": "user", "content": "Hello"}], "model": "mistral"},
            )
            print(f"Stream Status: {response.status_code}")
        except Exception as e:
            print(f"Stream Exception: {e}")

        # Check if audit log was created (any audit log)
        # We need admin token to read logs
        admin_token = create_access_token(user_id="admin_user", roles=[Roles.ADMIN])
        try:
            logs_resp = client.get("/v1/audit/logs", headers={"Authorization": f"Bearer {admin_token}"})
            if logs_resp.status_code == 200:
                logs = logs_resp.json()
                if len(logs) > 0:
                    print(f"Audit Logs Found: {len(logs)} - PASS")
                    # print(f"Latest Log: {logs[0]}")
                else:
                    print("Audit Logs Found: 0 - FAIL (unless endpoint failed very early)")
            else:
                print(f"Read Logs Failed: {logs_resp.status_code}")
                # print(logs_resp.text)
        except Exception as e:
            print(f"Check Logs Exception: {e}")

if __name__ == "__main__":
    try:
        run_tests()
    finally:
        pass
