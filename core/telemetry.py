# core/telemetry.py
"""
Arize Observability & OpenTelemetry Instrumentation Engine
Integrates Arize Phoenix / OpenInference for Groq LLM tracing,
capturing:
- Query trajectory & agent spans
- Prompt, completion, and total token counts
- Exact wall-clock latency per LLM inference and query lifecycle
- Fail-safe non-blocking telemetry (zero crash on network timeouts)
"""
import os
import time
from typing import Dict, Any, Optional
from contextvars import ContextVar
from contextlib import contextmanager

# Active context tracking
_current_telemetry: ContextVar[Optional[Dict[str, Any]]] = ContextVar("_current_telemetry", default=None)

_arize_initialized = False
_arize_tracer_provider = None


def get_arize_key() -> str:
    """Retrieves Arize / Phoenix API key from environment (.env)."""
    return (
        os.getenv("Arize_Key") or
        os.getenv("ARIZE_API_KEY") or
        os.getenv("PHOENIX_API_KEY") or
        ""
    ).strip().strip("'\"")


def is_arize_configured() -> bool:
    """Returns True if a valid Arize key is configured."""
    key = get_arize_key()
    return bool(key and not key.startswith("ak_your_key"))


def _is_local_collector_running(host: str = "127.0.0.1", port: int = 4317) -> bool:
    """Checks if a local OpenTelemetry collector is listening."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=0.15):
            return True
    except Exception:
        return False


def init_arize_telemetry() -> bool:
    """
    Initializes Arize Phoenix / OpenTelemetry tracer provider
    and auto-instruments Groq client calls.
    """
    global _arize_initialized, _arize_tracer_provider
    if _arize_initialized:
        return True

    key = get_arize_key()
    if not key:
        return False

    project_name = os.getenv("PHOENIX_PROJECT_NAME", "AgenticRMS-University-Portal")
    space_id = (os.getenv("SPACE_ID") or os.getenv("ARIZE_SPACE_ID") or "").strip().strip("'\"")
    endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "").strip()

    try:
        from openinference.instrumentation.groq import GroqInstrumentor

        # Configure environment for Phoenix / OpenInference
        os.environ["PHOENIX_API_KEY"] = key
        os.environ["ARIZE_API_KEY"] = key
        if space_id:
            os.environ["ARIZE_SPACE_ID"] = space_id
            os.environ["SPACE_ID"] = space_id

        if space_id:
            try:
                from arize.otel import register, Endpoint
                endpoint_val = Endpoint.ARIZE_EUROPE if not endpoint else endpoint
                _arize_tracer_provider = register(
                    space_id=space_id,
                    api_key=key,
                    project_name=project_name,
                    endpoint=endpoint_val
                )
            except Exception:
                from phoenix.otel import register
                target_endpoint = endpoint or "https://otlp.eu-west-1a.arize.com/v1"
                headers = {"space_id": space_id, "api_key": key}
                _arize_tracer_provider = register(
                    project_name=project_name,
                    api_key=key,
                    endpoint=target_endpoint,
                    headers=headers,
                    auto_instrument=True,
                    batch=True,
                    set_global_tracer_provider=True,
                    verbose=False
                )

            # Instrument LangChain and Groq with the Arize provider
            try:
                from openinference.instrumentation.langchain import LangChainInstrumentor
                LangChainInstrumentor().instrument(tracer_provider=_arize_tracer_provider)
            except Exception:
                pass

            try:
                from openinference.instrumentation.groq import GroqInstrumentor
                GroqInstrumentor().instrument(tracer_provider=_arize_tracer_provider)
            except Exception:
                pass
        elif endpoint:
            from phoenix.otel import register
            _arize_tracer_provider = register(
                project_name=project_name,
                api_key=key,
                endpoint=endpoint,
                auto_instrument=True,
                batch=True,
                set_global_tracer_provider=True,
                verbose=False
            )
            try:
                from openinference.instrumentation.langchain import LangChainInstrumentor
                LangChainInstrumentor().instrument(tracer_provider=_arize_tracer_provider)
            except Exception:
                pass
            try:
                from openinference.instrumentation.groq import GroqInstrumentor
                GroqInstrumentor().instrument(tracer_provider=_arize_tracer_provider)
            except Exception:
                pass
        elif _is_local_collector_running():
            from phoenix.otel import register
            _arize_tracer_provider = register(
                project_name=project_name,
                api_key=key,
                auto_instrument=True,
                batch=True,
                set_global_tracer_provider=True,
                verbose=False
            )
            GroqInstrumentor().instrument(tracer_provider=_arize_tracer_provider)
        else:
            # Prevent spamming connection refused when no local collector is open
            os.environ["OTEL_TRACES_EXPORTER"] = "none"
            GroqInstrumentor().instrument()

        _arize_initialized = True
        return True
    except Exception as e:
        try:
            from openinference.instrumentation.groq import GroqInstrumentor
            GroqInstrumentor().instrument()
            _arize_initialized = True
            return True
        except Exception:
            pass
        return False


def get_current_telemetry() -> Optional[Dict[str, Any]]:
    """Returns the currently active query telemetry state if within a tracking context."""
    return _current_telemetry.get()


def record_llm_call(
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    latency_ms: float,
    model: str = ""
):
    """Accumulates token metrics and execution latency into the active query context."""
    ctx = _current_telemetry.get()
    if ctx is not None:
        ctx["prompt_tokens"] += int(prompt_tokens or 0)
        ctx["completion_tokens"] += int(completion_tokens or 0)
        ctx["total_tokens"] += int(total_tokens or (prompt_tokens + completion_tokens))
        ctx["llm_latency_ms"] += float(latency_ms or 0.0)
        ctx["llm_calls"] += 1
        ctx["models"].append(model)

        tracker = ctx.get("tracker")
        if tracker:
            tracker.prompt_tokens = ctx["prompt_tokens"]
            tracker.completion_tokens = ctx["completion_tokens"]
            tracker.total_tokens = ctx["total_tokens"]


@contextmanager
def track_query_telemetry(tracker=None):
    """
    Context manager that tracks total tokens, LLM calls,
    and wall-clock duration for an entire user query.
    """
    start_time = time.perf_counter()
    telemetry_state = {
        "start_time": start_time,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "llm_latency_ms": 0.0,
        "llm_calls": 0,
        "models": [],
        "tracker": tracker,
        "arize_active": is_arize_configured()
    }
    token = _current_telemetry.set(telemetry_state)
    try:
        yield telemetry_state
    finally:
        total_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        telemetry_state["latency_ms"] = total_time_ms
        if tracker:
            tracker.prompt_tokens = telemetry_state["prompt_tokens"]
            tracker.completion_tokens = telemetry_state["completion_tokens"]
            tracker.total_tokens = telemetry_state["total_tokens"]
            tracker.latency_ms = total_time_ms
        _current_telemetry.reset(token)


def instrument_groq_client(client_instance):
    """
    Wraps client.chat.completions.create to automatically measure
    prompt tokens, completion tokens, total tokens, and latency for every call.
    """
    if getattr(client_instance, "_is_telemetry_instrumented", False):
        return client_instance

    orig_create = client_instance.chat.completions.create

    def instrumented_create(*args, **kwargs):
        t0 = time.perf_counter()
        res = orig_create(*args, **kwargs)
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        try:
            usage = getattr(res, "usage", None)
            p_tok = getattr(usage, "prompt_tokens", 0) or 0
            c_tok = getattr(usage, "completion_tokens", 0) or 0
            t_tok = getattr(usage, "total_tokens", 0) or (p_tok + c_tok)
            model_name = kwargs.get("model", "")
            record_llm_call(
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                total_tokens=t_tok,
                latency_ms=duration_ms,
                model=model_name
            )
        except Exception:
            pass

        return res

    client_instance.chat.completions.create = instrumented_create
    client_instance._is_telemetry_instrumented = True
    return client_instance


def flush_telemetry():
    """Flushes buffered OpenTelemetry spans to Arize Cloud."""
    global _arize_tracer_provider
    if _arize_tracer_provider and hasattr(_arize_tracer_provider, "force_flush"):
        try:
            _arize_tracer_provider.force_flush(timeout_millis=2000)
        except Exception:
            pass
