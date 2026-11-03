"""Zero-Vendor-SDK Direct HTTP/2 SSE Streaming Adapters (Gemini, Groq, OpenAI)."""
import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any
import httpx

logger = logging.getLogger("intelliq.llm.adapters")

# Module-scoped singleton client for connection pooling across warm Lambda invocations
_ASYNC_HTTP_CLIENT: httpx.AsyncClient | None = None
_CLIENT_LOOP: asyncio.AbstractEventLoop | None = None


def get_async_http_client() -> httpx.AsyncClient:
    """Return or initialize connection-pooled HTTP/2 AsyncClient bound to current event loop."""
    global _ASYNC_HTTP_CLIENT, _CLIENT_LOOP
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _ASYNC_HTTP_CLIENT is None or _ASYNC_HTTP_CLIENT.is_closed or _CLIENT_LOOP != current_loop:
        _CLIENT_LOOP = current_loop
        _ASYNC_HTTP_CLIENT = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
    return _ASYNC_HTTP_CLIENT


# -----------------------------------------------------------------------------
# Google Gemini Direct REST SSE Adapter (Free Tier Primary)
# -----------------------------------------------------------------------------
async def stream_gemini(
    api_key: str,
    model: str,
    system_instruction: str,
    prompt: str,
    response_schema: dict[str, Any] | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream structured tokens from Google Gemini REST API using Server-Sent Events.
    Bypasses google-genai / google-generativeai SDKs completely ($0 overhead, <15MB package).
    """
    client = get_async_http_client()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}"

    # Build multimodal content parts (Gemini supports image/audio/video and application/pdf)
    parts: list[dict[str, Any]] = []

    supported_mimes = {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/heic",
        "image/heif",
        "audio/wav",
        "audio/mp3",
        "audio/mpeg",
        "audio/aac",
        "audio/ogg",
        "video/mp4",
        "video/quicktime",
    }

    if attachments:
        for att in attachments:
            base64_data = att.get("base64_data")
            mime_type = (att.get("mime_type") or "").strip().lower()
            name = (att.get("name") or "").lower()

            # Attempt MIME recovery from file extension
            if mime_type in ("", "application/octet-stream"):
                if name.endswith(".pdf"):
                    mime_type = "application/pdf"
                elif name.endswith(".png"):
                    mime_type = "image/png"
                elif name.endswith((".jpg", ".jpeg")):
                    mime_type = "image/jpeg"
                elif name.endswith(".webp"):
                    mime_type = "image/webp"

            if mime_type == "image/jpg":
                mime_type = "image/jpeg"

            # Only append valid binary multi-modal parts to Gemini inline_data
            if base64_data and mime_type in supported_mimes:
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64_data,
                    }
                })

    parts.append({"text": prompt})

    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
    }

    if system_instruction:
        body["system_instruction"] = {
            "parts": [{"text": system_instruction}]
        }

    generation_config: dict[str, Any] = {
        "temperature": 0.2,
        "maxOutputTokens": 8192,
        "thinkingConfig": {
            "thinkingBudget": 0,
        },
    }

    if response_schema:
        generation_config["responseMimeType"] = "application/json"
        # Gemini schema specification
        generation_config["responseSchema"] = response_schema

    body["generationConfig"] = generation_config

    async with client.stream("POST", url, json=body, headers={"Content-Type": "application/json"}) as response:
        if response.status_code != 200:
            error_text = await response.aread()
            raise RuntimeError(f"Gemini API error (HTTP {response.status_code}): {error_text.decode('utf-8', errors='replace')}")

        data_buffer: list[str] = []
        async for line in response.aiter_lines():
            line_str = line.strip()
            if not line_str:
                if data_buffer:
                    full_payload = "\n".join(data_buffer)
                    data_buffer = []
                    try:
                        chunk = json.loads(full_payload)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            content = candidates[0].get("content", {})
                            part_list = content.get("parts", [])
                            for p in part_list:
                                text_chunk = p.get("text", "")
                                if text_chunk:
                                    yield text_chunk
                    except json.JSONDecodeError:
                        continue
                continue

            if line.startswith("data: "):
                data_buffer.append(line[6:])
            elif data_buffer:
                data_buffer.append(line)

        # Flush any trailing buffered frame
        if data_buffer:
            full_payload = "\n".join(data_buffer)
            try:
                chunk = json.loads(full_payload)
                candidates = chunk.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    part_list = content.get("parts", [])
                    for p in part_list:
                        text_chunk = p.get("text", "")
                        if text_chunk:
                            yield text_chunk
            except json.JSONDecodeError:
                pass


# -----------------------------------------------------------------------------
# Groq / OpenAI Compatible REST SSE Adapter (Free Tier Secondary)
# -----------------------------------------------------------------------------
async def stream_openai_compatible(
    endpoint_url: str,
    api_key: str,
    model: str,
    system_instruction: str,
    prompt: str,
    response_schema: dict[str, Any] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream from Groq Cloud or OpenAI-compatible endpoint with strict JSON format."""
    client = get_async_http_client()
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 8192,
    }

    if response_schema:
        body["response_format"] = {
            "type": "json_object"
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with client.stream("POST", endpoint_url, json=body, headers=headers) as response:
        if response.status_code != 200:
            error_text = await response.aread()
            raise RuntimeError(f"OpenAI-compatible error (HTTP {response.status_code}): {error_text.decode('utf-8', errors='replace')}")

        async for line in response.aiter_lines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                except json.JSONDecodeError:
                    continue

