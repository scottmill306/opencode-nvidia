# End-User Failpoints & Recovery Strategies

This document identifies critical points where the user experience may degrade ("failpoints") and defines the **graceful degradation** or **recovery** strategies to maintain trust and usability.

## 1. Latency Failpoints (The "Waiting Game")

| Failpoint | Symptom | Threshold | User Impact | Recovery Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Cold Start** | First suggestion takes > 5s | > 2000ms | User abandons feature | **Pre-warming**: Keep model warm with dummy requests. Show "Initializing AI..." spinner immediately. |
| **High Load** | Streaming tokens stutter or pause | TTFT > 500ms | Breaks flow state | **Queue Feedback**: Show "Heavy load, queuing your request..." with estimated wait time. Fallback to smaller/faster model (e.g., StarCoder-1B). |
| **Context Retrieval** | "Thinking..." spins indefinitely | RAG query > 1s | User thinks system is broken | **Timeout & Local Fallback**: If Vector DB times out, return completion based *only* on current file context with a disclaimer: "Limited context mode." |

## 2. Quality & Accuracy Failpoints (The "Hallucination Trap")

| Failpoint | Symptom | Detection Method | User Impact | Recovery Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Hallucinated Imports** | Code uses non-existent libraries | Static Analysis (Post-gen) | Code fails to run | **Self-Correction Loop**: Detect missing import → Re-prompt model to fix → Show fixed version. Label as "Verified". |
| **Security Vulnerability** | Generated code has CVE (e.g., hardcoded keys) | SecCoder Scan | Security breach risk | **Block & Educate**: Do not show vulnerable code. Show warning: "Potential security risk detected. Here is a safe alternative." |
| **Context Mismatch** | Suggestion ignores project style/naming | Embedding Similarity Check | Code doesn't fit repo | **Style Adapter**: Low similarity score triggers re-generation with explicit style constraints from `style_guide.md`. |

## 3. Infrastructure & Resource Failpoints (The "Crash")

| Failpoint | Symptom | Trigger | User Impact | Recovery Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **GPU OOM (Out of Memory)** | Request fails with 500 Error | Batch size too large | Workflow interruption | **Dynamic Batching Reduction**: Auto-retry with batch_size=1. If still fails, return error: "Model busy, try again in a moment." |
| **Triton Server Crash** | Connection refused | Pod eviction/Crash | Total outage | **Circuit Breaker**: IDE plugin detects failure → Disables AI features gracefully → Shows "AI Services Unavailable" in status bar (no popups). |
| **Vector DB Corruption** | Semantic search returns garbage | Index corruption | Wrong context provided | **Fallback to Keyword Search**: If cosine similarity scores are anomalously low, switch to simple text grep for context retrieval. |

## 4. User Interaction Failpoints (The "Misunderstanding")

| Failpoint | Symptom | Cause | User Impact | Recovery Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Ambiguous Prompt** | Generic/boilerplate code | Vague user input | Wasted time | **Clarification UI**: If confidence score < 0.6, show quick-pick menu: "Did you mean: A) API Call B) Database Model?" |
| **Infinite Loop Gen** | Model repeats code forever | Sampling temp too high | Hangs IDE | **Token Limit Hard Stop**: Enforce `max_tokens`. If repetition detected (n-gram check), cut off stream and show "Generation stopped due to repetition." |

## 5. Implementation: The "Graceful Degradation" Middleware

Implement a middleware layer in the FastAPI backend to handle these failpoints automatically.

```python
# middleware/failpoint_handler.py

import time
from fastapi import Request, Response
from starlette.middleware.base import BaseMiddleware

class FailpointHandler(BaseMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Check Latency
            duration = time.time() - start_time
            if duration > 1.0: # 1000ms threshold
                response.headers["X-Latency-Warning"] = "high"
                # Log for observability
                print(f"Slow response: {duration}s for {request.url.path}")
            
            return response

        except GPUOutOfMemoryError:
            # Strategy: Retry with smaller batch or fallback model
            return self._fallback_response(request, "GPU Memory Full. Switching to lightweight model.")
        
        except ContextRetrievalError:
            # Strategy: Ignore context, proceed with local file only
            return self._proceed_limited_context(request)
            
        except Exception as e:
            # Generic Circuit Breaker
            return self._circuit_breaker_response()

    def _fallback_response(self, request, msg):
        return JSONResponse({"status": "degraded", "message": msg}, status_code=200)
    
    def _circuit_breaker_response(self):
        return JSONResponse({"status": "unavailable", "message": "AI Service temporarily unavailable"}, status_code=503)
```

## 6. Monitoring & Alerting (Observability)

To proactively catch failpoints before users complain:

1.  **Metrics to Track**:
    *   `p99_latency`: Time to first token.
    *   `error_rate_by_type`: OOM vs Timeout vs Model Error.
    *   `acceptance_rate`: % of suggestions accepted by users (Quality proxy).
    *   `fallback_trigger_count`: How often we switch to limited mode.

2.  **Alert Thresholds**:
    *   If `p99_latency` > 500ms for 5 mins → Page On-Call.
    *   If `acceptance_rate` drops < 20% → Model Drift Detected (Trigger re-eval).
    *   If `GPU_Utilization` > 95% for 10 mins → Scale Up HPA.

## 7. User Feedback Loop (The "Human in the Loop")

Every failpoint recovery should offer a feedback mechanism:
*   **Thumbs Down**: "Why was this suggestion bad?" (Options: Too slow, Wrong logic, Insecure, Hallucinated).
*   **Auto-Telemetry**: When a fallback occurs, silently log the event (anonymized) to improve the fallback logic.
