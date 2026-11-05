import os
import sys
from pathlib import Path

# Add backend directory to sys.path so 'app' is importable
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient

# Set test environment flags before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["ALLOW_DEMO_AUTH"] = "true"
os.environ["SECRET_KEY"] = "test_secret_key_at_least_32_characters_long_for_security_123"
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_sample_key"
os.environ["RAZORPAY_KEY_SECRET"] = "rzp_test_sample_secret"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "rzp_test_webhook_secret_key"

from app.main import app
from app.core.config import settings
from app.core.security import get_current_user, AuthenticatedUser

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer dev-token"}

@pytest.fixture
def user_a():
    return AuthenticatedUser(id="user-a-uuid-1111", email="user_a@test.com")

@pytest.fixture
def user_b():
    return AuthenticatedUser(id="user-b-uuid-2222", email="user_b@test.com")
