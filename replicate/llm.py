"""A minimal OpenAI-compatible chat-completions client (standard library only).

Used by the minimal loop, the judge and the agenda labeller in this folder. Set the endpoint and key with
environment variables; nothing is hardcoded:

    OPENAI_BASE_URL   e.g. https://openrouter.ai/api/v1 (the route we used for every non-OpenAI model)
    OPENAI_API_KEY    your key

Extra keyword arguments go into the request body unchanged, so provider-specific fields work, such as OpenRouter's
provider pin: chat(..., provider={"order": ["DeepInfra"], "allow_fallbacks": False}). See EXPERIMENTS.md,
"Shared design", for the routes and pins we used.
"""
import json
import os
import time
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    pass


def chat(model, messages, tools=None, tool_choice=None, retries=3, timeout=600, **params):
    """One chat-completions call. Returns {"message": assistant message dict, "usage": dict, "finish_reason": str,
    "provider": str or None, "model": served model or None}. Retries transport errors `retries` times."""
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise LLMError("set OPENAI_API_KEY (and OPENAI_BASE_URL for a non-OpenAI endpoint)")
    body = {"model": model, "messages": messages, **params}
    if tools:
        body["tools"] = tools
    if tool_choice is not None:
        body["tool_choice"] = tool_choice
    req = urllib.request.Request(base + "/chat/completions", json.dumps(body).encode(),
                                 {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.loads(r.read())
            if not out.get("choices"):
                raise LLMError(f"no choices in response: {str(out.get('error') or out)[:300]}")
            ch = out["choices"][0]
            return {"message": ch.get("message") or {}, "usage": out.get("usage") or {},
                    "finish_reason": ch.get("finish_reason"), "provider": out.get("provider"),
                    "model": out.get("model")}
        except (urllib.error.URLError, TimeoutError, LLMError, json.JSONDecodeError) as e:
            err = e
            time.sleep(3 * (attempt + 1))
    raise LLMError(f"{model}: {type(err).__name__}: {err}")
