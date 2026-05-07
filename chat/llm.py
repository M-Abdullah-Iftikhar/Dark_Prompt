"""Thin wrapper around `gradio_client.Client` for the local LLM.

The model is exposed via a Gradio space (e.g. an ngrok-style `*.gradio.live`
URL when running on Kaggle). The signature on the gradio side is:

    generate(instruction: str, max_tokens: int, temperature: float) -> str

so we wrap it with a stable Python interface and translate every failure
mode into one of the error codes the JS frontend already handles:
`llm_unreachable`, `llm_timeout`, `llm_error`, `llm_bad_response`.

The Client object is cached per-URL because instantiating it does an
introspection round-trip — slow if we did it on every request.
"""
from __future__ import annotations

import threading

from django.conf import settings


class LLMError(Exception):
    """Base class for everything raised at the call site."""
    code = "llm_error"

    def __init__(self, detail: str = ""):
        super().__init__(detail or self.code)
        self.detail = detail or self.code


class LLMUnreachable(LLMError):
    code = "llm_unreachable"


class LLMTimeout(LLMError):
    code = "llm_timeout"


class LLMBadResponse(LLMError):
    code = "llm_bad_response"


LANG_ASM = "asm"
LANG_C   = "c"

_client_lock = threading.Lock()
_client_cache: dict = {}   # url -> Client


def _backend_for(lang: str):
    """Return (url, api_name) for the given conversation language."""
    lang = (lang or LANG_ASM).lower()
    if lang == LANG_C:
        url      = (getattr(settings, "LLM_API_URL_C",  "") or "").strip()
        api_name = (getattr(settings, "LLM_API_NAME_C", "/generate") or "/generate")
    else:
        url      = (getattr(settings, "LLM_API_URL",    "") or "").strip()
        api_name = (getattr(settings, "LLM_API_NAME",   "/generate") or "/generate")
    return url, api_name


def is_language_available(lang: str) -> bool:
    """True iff the env has a URL configured for this language."""
    url, _ = _backend_for(lang)
    return bool(url)


def _get_client(url: str):
    """Return a cached gradio_client.Client for `url`. One client per URL."""
    if not url:
        raise LLMUnreachable("LLM URL is not configured for this conversation's language.")
    with _client_lock:
        cached = _client_cache.get(url)
        if cached is not None:
            return cached
        try:
            from gradio_client import Client
        except ImportError as exc:
            raise LLMError("gradio_client is not installed. Run: pip install gradio_client") from exc
        try:
            client = Client(url, verbose=False)
        except Exception as exc:
            msg = str(exc) or "could not reach Gradio space"
            raise LLMUnreachable(msg) from exc
        _client_cache[url] = client
        return client


def reset_client(url: str = None):
    """Drop a cached client (or all of them). Used when a tunnel rotates."""
    with _client_lock:
        if url is None:
            _client_cache.clear()
        else:
            _client_cache.pop(url, None)


def generate(instruction: str, *, max_tokens: int, temperature: float, language: str = LANG_ASM) -> str:
    """Call the Gradio `/generate` endpoint for the given language.

    Raises one of the LLM* exceptions on any failure path. Callers translate
    those into the JsonResponse error envelope the JS frontend expects.
    """
    url, api_name = _backend_for(language)
    if not url:
        raise LLMUnreachable(f"No LLM backend configured for language={language!r}.")
    client = _get_client(url)

    # Gradio side expects (instruction, max_tokens, temperature) — note order.
    try:
        result = client.predict(
            instruction,
            int(max_tokens),
            float(temperature),
            api_name=api_name,
        )
    except Exception as exc:
        # gradio_client surfaces httpx errors and AppErrors. We sniff the
        # exception name + message rather than depend on those classes.
        name = type(exc).__name__.lower()
        msg = (str(exc) or "").strip()
        if "timeout" in name or "timeout" in msg.lower():
            raise LLMTimeout(msg or "Gradio request timed out") from exc
        if any(k in name for k in ("connect", "network", "remoteproto", "remotedisconnect")):
            # The shared URL has rotated, the kaggle notebook stopped, etc.
            reset_client(url)
            raise LLMUnreachable(msg or "Could not reach Gradio space") from exc
        raise LLMError(msg or "Gradio backend error") from exc

    if result is None:
        raise LLMBadResponse("Gradio returned no output.")
    if isinstance(result, (list, tuple)) and result:
        # Some Gradio interfaces return a tuple of outputs — take the first.
        result = result[0]
    return str(result)
