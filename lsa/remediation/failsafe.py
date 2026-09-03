from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib import error, request


def clean_json_response(raw_text: str) -> dict[str, Any]:
    """Extracts and parses JSON from raw LLM output, stripping code fences if present."""
    text = raw_text.strip()
    if text.startswith("```"):
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        raise ValueError(f"Parsed JSON is not an object/dict: {type(data)}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON response: {exc} | Raw text: {text[:200]}") from exc


def get_available_ai_providers() -> dict[str, bool]:
    """Returns boolean availability of AI providers without logging or touching credentials."""
    anthropic_ready = bool(os.environ.get("ANTHROPIC_API_KEY"))
    openai_ready = bool(os.environ.get("OPENAI_API_KEY"))
    gemini_ready = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    agentapi_bin = shutil.which("agentapi") or "/Users/gani/.gemini/antigravity/bin/agentapi"
    antigravity_ready = os.path.exists(agentapi_bin) and (
        bool(os.environ.get("ANTIGRAVITY_LS_ADDRESS")) or os.path.exists("/Applications/Antigravity.app")
    )
    return {
        "anthropic": anthropic_ready,
        "openai": openai_ready,
        "gemini": gemini_ready,
        "antigravity": antigravity_ready,
        "deterministic": True,
    }


def call_anthropic_json(
    *,
    system: str,
    user_prompt: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("No Anthropic API key available.")
    selected_model = model or os.environ.get("INTENT_GUARD_MODEL") or "claude-3-5-sonnet-latest"
    url = (base_url or os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
    body = {
        "model": selected_model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    }
    req = request.Request(f"{url}/v1/messages", data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout_seconds) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
    blocks = res_data.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return clean_json_response(text)


def call_openai_json(
    *,
    system: str,
    user_prompt: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("No OpenAI API key available.")
    selected_model = model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    body = {
        "model": selected_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    req = request.Request(f"{url}/chat/completions", data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout_seconds) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
    choices = res_data.get("choices") or []
    if not choices:
        raise ValueError("OpenAI returned no completion choices.")
    text = choices[0].get("message", {}).get("content", "")
    return clean_json_response(text)


def call_gemini_json(
    *,
    system: str,
    user_prompt: str,
    model: str | None = None,
    api_key: str | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise ValueError("No Gemini/Google API key available.")
    selected_model = model or os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={key}"
    full_prompt = f"{system}\n\nTask Input:\n{user_prompt}"
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": full_prompt}],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }
    req = request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout_seconds) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
    candidates = res_data.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini returned no candidate outputs.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    return clean_json_response(text)


def call_antigravity_json(
    *,
    system: str,
    user_prompt: str,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    """Invokes Antigravity local agentapi as a zero-cloud-token fallback provider."""
    agentapi_bin = shutil.which("agentapi") or "/Users/gani/.gemini/antigravity/bin/agentapi"
    if not os.path.exists(agentapi_bin):
        raise FileNotFoundError(f"Antigravity agentapi binary not found at {agentapi_bin}")

    prompt = (
        f"{system}\n\n"
        f"Input:\n{user_prompt}\n\n"
        f"IMPORTANT: Return ONLY valid JSON matching the requested schema. No markdown explanations outside JSON."
    )
    cmd = [agentapi_bin, "new-conversation", "--model=flash_lite", "--title=IntentGuardAudit", prompt]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    if res.returncode != 0:
        raise RuntimeError(f"Antigravity agentapi exited with code {res.returncode}: {res.stderr.strip()}")

    init_payload = json.loads(res.stdout)
    cid = init_payload.get("response", {}).get("newConversation", {}).get("conversationId")
    if not cid:
        raise ValueError(f"Failed to obtain conversationId from agentapi: {res.stdout}")

    transcript_path = Path(f"/Users/gani/.gemini/antigravity/brain/{cid}/.system_generated/logs/transcript.jsonl")
    start_t = time.time()
    raw_content = None

    try:
        while time.time() - start_t < timeout_seconds:
            if transcript_path.exists():
                try:
                    for line in transcript_path.read_text(encoding="utf-8").splitlines():
                        if not line.strip():
                            continue
                        step = json.loads(line)
                        if step.get("source") == "MODEL" and step.get("type") == "PLANNER_RESPONSE" and step.get("status") == "DONE":
                            raw_content = step.get("content")
                            break
                except Exception:
                    pass
            if raw_content:
                break
            time.sleep(0.25)
    finally:
        # Strict cleanup to adhere to workspace rules (no runtime artifacts left behind)
        shutil.rmtree(f"/Users/gani/.gemini/antigravity/brain/{cid}", ignore_errors=True)
        conv_dir = Path("/Users/gani/.gemini/antigravity/conversations")
        if conv_dir.exists():
            for f in conv_dir.glob(f"{cid}*"):
                if f.is_dir():
                    shutil.rmtree(f, ignore_errors=True)
                else:
                    f.unlink(missing_ok=True)

    if not raw_content:
        raise TimeoutError(f"Antigravity response timed out after {timeout_seconds}s for conversation {cid}")

    return clean_json_response(raw_content)


def call_ai_json_with_failsafe(
    *,
    system: str,
    user_prompt: str,
    preferred_provider: str | None = None,
    timeout_seconds: float = 20.0,
) -> tuple[dict[str, Any], str]:
    """Attempts providers in sequence with automatic failsafe:
    1. Preferred provider (if specified and credentialed)
    2. Anthropic (if ANTHROPIC_API_KEY set)
    3. OpenAI (if OPENAI_API_KEY set)
    4. Gemini (if GEMINI_API_KEY or GOOGLE_API_KEY set)
    5. Antigravity (if agentapi and environment present)

    Returns:
        (parsed_json_dict, provider_name_that_succeeded)
    """
    providers_ready = get_available_ai_providers()
    candidates: list[str] = []

    if preferred_provider and providers_ready.get(preferred_provider):
        candidates.append(preferred_provider)

    for p in ["anthropic", "openai", "gemini", "antigravity"]:
        if p not in candidates and providers_ready.get(p):
            candidates.append(p)

    errors: list[str] = []
    for prov in candidates:
        try:
            if prov == "anthropic":
                return call_anthropic_json(system=system, user_prompt=user_prompt, timeout_seconds=timeout_seconds), "anthropic"
            elif prov == "openai":
                return call_openai_json(system=system, user_prompt=user_prompt, timeout_seconds=timeout_seconds), "openai"
            elif prov == "gemini":
                return call_gemini_json(system=system, user_prompt=user_prompt, timeout_seconds=timeout_seconds), "gemini"
            elif prov == "antigravity":
                return call_antigravity_json(system=system, user_prompt=user_prompt, timeout_seconds=timeout_seconds), "antigravity"
        except Exception as exc:
            errors.append(f"{prov}: {type(exc).__name__}: {exc}")

    raise RuntimeError(f"All available AI providers failed: {'; '.join(errors) if errors else 'No AI credentials or providers available'}")
