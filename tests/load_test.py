# Load Testing Script for OpenCode NVIDIA System
# Uses locust.io for distributed load testing

from locust import HttpUser, task, between, events
import time
import json
import random

class CodeGenerationUser(HttpUser):
    """Simulates developers requesting code completions."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    
    @task(3)
    def simple_completion(self):
        """Request simple code completion (most common)."""
        prompts = [
            "def add(",
            "import requests\n",
            "class User:",
            "for i in range(",
            "if __name__ == '__main__':",
        ]
        payload = {
            "prompt": random.choice(prompts),
            "max_tokens": 20,
            "temperature": 0.7
        }
        
        with self.client.post("/generate", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")
    
    @task(2)
    def context_aware_completion(self):
        """Request completion with repo context (medium load)."""
        payload = {
            "prompt": "def authenticate_user(username, password):",
            "context_files": [
                {"path": "models/user.py", "content": "class User: ..."},
                {"path": "db/session.py", "content": "def get_session(): ..."}
            ],
            "max_tokens": 50,
            "temperature": 0.5
        }
        
        self.client.post("/generate/context", json=payload)
    
    @task(1)
    def security_scan(self):
        """Request security analysis (heavy load)."""
        code_snippets = [
            "eval(user_input)",
            "os.system(cmd)",
            "SELECT * FROM users WHERE id=" + user_id,
            "password = 'admin123'",
        ]
        
        payload = {
            "code": random.choice(code_snippets),
            "language": "python"
        }
        
        self.client.post("/security/scan", json=payload)


class StressTestUser(HttpUser):
    """Aggressive load testing for breaking points."""
    
    wait_time = between(0.1, 0.5)
    
    @task
    def rapid_fire(self):
        """Send requests as fast as possible."""
        payload = {"prompt": "#", "max_tokens": 5}
        self.client.post("/generate", json=payload)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log slow requests."""
    if response_time > 1000:  # > 1 second
        print(f"WARNING: Slow request to {name}: {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Setup before test run."""
    print("Starting Load Test for OpenCode NVIDIA System...")
    print(f"Target: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Summary after test run."""
    print("\n=== Load Test Complete ===")
    print(f"Total Requests: {environment.stats.total.num_requests}")
    print(f"Failed Requests: {environment.stats.total.num_failures}")
    print(f"Avg Response Time: {environment.stats.total.avg_response_time:.2f}ms")
