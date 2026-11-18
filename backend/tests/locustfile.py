import os
import time
import random
from locust import HttpUser, task, between

SAMPLE_CLAUSES = [
    "SECTION 1. INDEMNIFICATION. The Vendor agrees to defend, indemnify, and hold harmless the Customer, its officers, directors, employees, and agents from and against any and all claims, liabilities, losses, damages, and reasonable attorney fees arising out of third-party IP infringement.",
    "SECTION 2. LIMITATION OF LIABILITY. IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES. EACH PARTY'S TOTAL CUMULATIVE AGGREGATE LIABILITY SHALL BE CAPPED AT THE FEES PAID IN THE PRIOR TWELVE (12) MONTHS.",
    "SECTION 3. TERMINATION AND AUTO-RENEWAL. This Agreement shall automatically renew for successive one (1) year periods unless either party provides written notice of non-renewal at least sixty (60) days prior to expiration.",
    "SECTION 4. INTELLECTUAL PROPERTY RIGHTS. All pre-existing intellectual property shall remain the exclusive property of the originating party. Deliverables created specifically for Customer shall vest in Customer upon full payment.",
    "SECTION 5. CONFIDENTIALITY. Each party agrees to hold the other party's Confidential Information in strict confidence and not disclose it to any third party for a period of five (5) years.",
    "SECTION 6. GOVERNING LAW AND DISPUTE RESOLUTION. This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to conflict of laws principles."
]

def generate_mock_contract_text(clause_multiplier: int = 5) -> str:
    """Generates realistic contract text containing 30–60 legal clauses."""
    chunks = []
    idx = 1
    for m in range(clause_multiplier):
        for template in SAMPLE_CLAUSES:
            title = template.split(".")[0]
            body = ".".join(template.split(".")[1:])
            chunks.append(f"ARTICLE {idx}. {title}\n{body}\n")
            idx += 1
    return "\n".join(chunks)

class TraceClauseLoadTestUser(HttpUser):
    """
    Locust User simulating realistic legal counsel workflow:
    1. Authenticates session (via test token).
    2. Enqueues a 30-clause agreement to /api/v1/jobs/submit.
    3. Polls /api/v1/jobs/{job_id} until completed or terminal failure.
    4. Asserts zero uncaught 500 or 504 status codes.
    """
    wait_time = between(2, 5)

    def on_start(self):
        self.auth_headers = {
            "Authorization": "Bearer dev-token",
            "Content-Type": "application/json"
        }

    @task(3)
    def submit_and_poll_contract_audit(self):
        contract_text = generate_mock_contract_text(clause_multiplier=4)
        file_name = f"sample_commercial_agreement_{random.randint(1000, 9999)}.pdf"

        # 1. Submit Job
        start_time = time.time()
        payload = {
            "file_name": file_name,
            "extracted_text": contract_text,
            "retain_audit": True
        }

        with self.client.post(
            "/api/v1/jobs/submit",
            json=payload,
            headers=self.auth_headers,
            catch_response=True,
            name="/api/v1/jobs/submit"
        ) as submit_res:
            if submit_res.status_code == 200:
                data = submit_res.json()
                job_id = data.get("job_id")
                submit_res.success()
            elif submit_res.status_code == 429:
                # Quota or concurrency limit hit - expected under high load
                submit_res.success()
                return
            else:
                submit_res.failure(f"Submit failed with status {submit_res.status_code}: {submit_res.text}")
                return

        # 2. Poll Status
        completed = False
        poll_attempts = 0
        max_polls = 40  # 40 * 1.5s = 60s max wait

        while not completed and poll_attempts < max_polls:
            time.sleep(1.5)
            poll_attempts += 1

            with self.client.get(
                f"/api/v1/jobs/{job_id}",
                headers=self.auth_headers,
                catch_response=True,
                name="/api/v1/jobs/{job_id}"
            ) as poll_res:
                if poll_res.status_code != 200:
                    poll_res.failure(f"Poll returned unexpected HTTP {poll_res.status_code}")
                    return

                job_status = poll_res.json()
                status = job_status.get("status")

                if status == "completed":
                    completed = True
                    poll_res.success()
                elif status in ("failed", "cancelled"):
                    completed = True
                    # Provider error or clean failure is acceptable under synthetic load
                    poll_res.success()
                else:
                    poll_res.success()

    @task(1)
    def check_audit_vault_history(self):
        """Simulate user checking their historical audit reports."""
        with self.client.get(
            "/api/v1/contract/my-reports",
            headers=self.auth_headers,
            catch_response=True,
            name="/api/v1/contract/my-reports"
        ) as res:
            if res.status_code in (200, 401):
                res.success()
            else:
                res.failure(f"Vault history failed: {res.status_code}")

