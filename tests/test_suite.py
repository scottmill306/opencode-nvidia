"""
Test Suite for OpenCode NVIDIA Systems
Implements Unit, Integration, and Performance tests against the FastAPI backend.

Run unit tests normally:
    pytest opencode-nvidia/tests/test_suite.py

Run including live integration/performance tests:
    INTEGRATION_TESTS=1 pytest opencode-nvidia/tests/test_suite.py
"""

import os
import pytest
import concurrent.futures
import tracemalloc
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

# sys.path is configured by conftest.py in this directory
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Flag: set INTEGRATION_TESTS=1 to run tests that require a live service
INTEGRATION_TESTS = os.environ.get("INTEGRATION_TESTS") == "1"

# -----------------------------------------------------------------------------
# 1. UNIT TESTS: Security Scanner (via /security/scan endpoint)
# -----------------------------------------------------------------------------

class TestSecurityScanner:
    """Tests for the /security/scan endpoint's vulnerability detection."""

    def test_detects_eval_usage(self):
        """Must detect unsafe eval() calls."""
        response = client.post("/security/scan", json={
            "code": "user_input = input()\nresult = eval(user_input)",
            "language": "python"
        })
        assert response.status_code == 200
        data = response.json()
        assert any("eval" in v["description"].lower() for v in data["vulnerabilities"])
        assert any(v["severity"] == "high" for v in data["vulnerabilities"])

    def test_detects_hardcoded_password(self):
        """Must detect hardcoded password patterns."""
        response = client.post("/security/scan", json={
            "code": "password = 'supersecret123'",
            "language": "python"
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["vulnerabilities"]) > 0
        assert data["risk_level"] == "critical"

    def test_clean_code_passes(self):
        """Safe code should generate no vulnerabilities."""
        response = client.post("/security/scan", json={
            "code": "import os\npath = os.getenv('HOME')",
            "language": "python"
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["vulnerabilities"]) == 0
        assert data["risk_level"] == "low"

    def test_risk_level_critical_for_critical_severity(self):
        """Risk level must be 'critical' when a critical vulnerability is present."""
        response = client.post("/security/scan", json={
            "code": "password = 'abc'",
            "language": "python"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] == "critical"

    def test_risk_level_high_for_eval(self):
        """Risk level must be 'high' when only high-severity issues exist."""
        response = client.post("/security/scan", json={
            "code": "result = eval('1+1')",
            "language": "python"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] == "high"

# -----------------------------------------------------------------------------
# 2. UNIT TESTS: Code Generation endpoint (mocked Triton)
# -----------------------------------------------------------------------------

class TestCodeGeneration:
    """Tests for the /generate and /complete endpoints with mocked Triton."""

    def _mock_triton_response(self, generated_text="def hello(): pass", tokens=5):
        """Return a mock httpx response that looks like a Triton reply."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "output_text": generated_text,
            "tokens_generated": tokens,
        }
        return mock_resp

    def test_generate_returns_generated_code(self):
        """POST /generate must return generated_code in the response."""
        mock_resp = self._mock_triton_response("def add(a, b): return a + b", tokens=8)
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            response = client.post("/generate", json={
                "prompt": "Write an add function",
                "max_tokens": 64
            })
        assert response.status_code == 200
        data = response.json()
        assert "generated_code" in data
        assert data["generated_code"] == "def add(a, b): return a + b"
        assert data["tokens_generated"] == 8
        assert data["model_name"] == "CodeLlama-7B"

    def test_generate_503_on_triton_unavailable(self):
        """POST /generate must return 503 when Triton is unreachable."""
        import httpx
        with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=httpx.RequestError("connection refused"))):
            response = client.post("/generate", json={"prompt": "test"})
        assert response.status_code == 503

    def test_complete_delegates_to_generate(self):
        """POST /complete must behave like /generate."""
        mock_resp = self._mock_triton_response("pass")
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            response = client.post("/complete", json={"prompt": "def foo():"})
        assert response.status_code == 200
        assert "generated_code" in response.json()

# -----------------------------------------------------------------------------
# 3. UNIT TESTS: Refactor endpoint
# -----------------------------------------------------------------------------

class TestRefactor:
    """Tests for the /refactor endpoint."""

    def test_refactor_returns_expected_fields(self):
        """POST /refactor must return refactored_code, improvements, and performance_gain."""
        response = client.post("/refactor", json={"prompt": "for i in range(len(arr)): arr[i] *= 2"})
        assert response.status_code == 200
        data = response.json()
        assert "refactored_code" in data
        assert "improvements" in data
        assert isinstance(data["improvements"], list)
        assert "performance_gain" in data

# -----------------------------------------------------------------------------
# 4. UNIT TESTS: Root & Health endpoints
# -----------------------------------------------------------------------------

class TestInfrastructure:
    """Tests for root and health-check endpoints."""

    def test_root_returns_version(self):
        """GET / must return version info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "endpoints" in data

    def test_health_reports_components(self):
        """GET /health must include api and triton_server component status."""
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=MagicMock(status_code=200))):
            response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "api" in data["components"]
        assert "triton_server" in data["components"]

# -----------------------------------------------------------------------------
# 5. PERFORMANCE / INTEGRATION TESTS (skipped unless INTEGRATION_TESTS=1)
# -----------------------------------------------------------------------------

@pytest.mark.skipif(not INTEGRATION_TESTS, reason="Set INTEGRATION_TESTS=1 to run live performance tests")
class TestPerformance:
    """Load testing scenarios against a live service on http://localhost:8000."""

    def test_concurrent_requests(self):
        """Handle 50 concurrent requests without crashing."""
        def make_request():
            return httpx.post(
                "http://localhost:8000/security/scan",
                json={"code": "x = 1", "language": "python"},
                timeout=10,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in futures]

        assert all(r.status_code == 200 for r in results)

    def test_memory_usage_stabilises(self):
        """Ensure repeated security scans don't leak memory in the test process."""
        tracemalloc.start()

        for _ in range(100):
            client.post("/security/scan", json={"code": "x = 1", "language": "python"})

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Peak should not exceed 3x current usage; a higher ratio suggests a leak
        assert peak < current * 3, "Potential memory leak detected"

# -----------------------------------------------------------------------------
# Run Tests
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
