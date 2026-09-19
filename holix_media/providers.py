"""Pluggable media backends: OpenAI-compatible images/videos and generic JSON HTTP."""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from holix_media.config import MediaProvider, json_path
from holix_media.http import HttpTransport, HttpxTransport


@dataclass(frozen=True, slots=True)
class MediaBlob:
    data: bytes
    mime: str
    filename: str
    source_url: str | None = None


class MediaProviderError(RuntimeError):
    pass


def _auth_headers(provider: MediaProvider) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = provider.api_key
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _join(base: str, path: str) -> str:
    root = (base or "").rstrip("/") + "/"
    rel = (path or "").lstrip("/")
    return urljoin(root, rel)


def _fill_template(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, str):
        out = value
        for key, val in mapping.items():
            out = out.replace("{{" + key + "}}", val)
        return out
    if isinstance(value, dict):
        return {k: _fill_template(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill_template(v, mapping) for v in value]
    return value


async def generate_image(
    provider: MediaProvider,
    prompt: str,
    *,
    http: HttpTransport | None = None,
    size: str | None = None,
) -> MediaBlob:
    transport = http or HttpxTransport()
    kind = provider.type.strip().lower()
    if kind in {"openai_images", "openai", "dalle", "litellm", "litellm_images"}:
        return await _openai_images(provider, prompt, transport, size=size)
    if kind in {"http_json", "http"}:
        return await _http_json(provider, prompt, transport, kind="image")
    raise MediaProviderError(f"Unknown image provider type: {provider.type}")


async def generate_video(
    provider: MediaProvider,
    prompt: str,
    *,
    http: HttpTransport | None = None,
    duration_s: int | None = None,
) -> MediaBlob:
    transport = http or HttpxTransport()
    kind = provider.type.strip().lower()
    if kind in {"openai_videos", "openai", "sora", "litellm", "litellm_videos"}:
        return await _openai_videos(provider, prompt, transport, duration_s=duration_s)
    if kind in {"http_json", "http"}:
        return await _http_json(provider, prompt, transport, kind="video")
    raise MediaProviderError(f"Unknown video provider type: {provider.type}")


async def _openai_images(
    provider: MediaProvider,
    prompt: str,
    http: HttpTransport,
    *,
    size: str | None,
) -> MediaBlob:
    if not provider.api_key:
        raise MediaProviderError(f"API key missing ({provider.api_key_env or 'api_key'})")
    base = provider.resolved_base_url or provider.base_url
    if not base:
        raise MediaProviderError("base_url is empty (set LITELLM_API_BASE or image provider base_url)")
    url = _join(base, "/images/generations")
    body: dict[str, Any] = {
        "model": provider.model or "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": size or provider.size or "1024x1024",
    }
    # DALL·E accepts b64; LiteLLM / gpt-image / Grok often reject response_format.
    ptype = provider.type.strip().lower()
    if ptype not in {"litellm", "litellm_images"} and "dall-e" in (provider.model or "").lower():
        body["response_format"] = "b64_json"
    data = await http.post_json(url, headers=_auth_headers(provider), json=body, timeout=180.0)
    items = data.get("data")
    if not isinstance(items, list) or not items:
        raise MediaProviderError(f"No image in response: {json.dumps(data)[:400]}")
    item = items[0] if isinstance(items[0], dict) else {}
    b64 = item.get("b64_json") or item.get("b64")
    if b64:
        raw = base64.b64decode(str(b64))
        return MediaBlob(raw, "image/png", _filename("png"), source_url=None)
    remote = item.get("url")
    if not remote:
        raise MediaProviderError("Image response has neither b64_json nor url")
    raw, mime = await http.get_bytes(str(remote), timeout=180.0)
    ext = "jpg" if "jpeg" in mime else "png" if "png" in mime else "webp"
    return MediaBlob(raw, mime or "image/png", _filename(ext), source_url=str(remote))


async def _openai_videos(
    provider: MediaProvider,
    prompt: str,
    http: HttpTransport,
    *,
    duration_s: int | None,
) -> MediaBlob:
    if not provider.api_key:
        raise MediaProviderError(f"API key missing ({provider.api_key_env or 'api_key'})")
    base = provider.resolved_base_url or provider.base_url
    if not base:
        raise MediaProviderError("base_url is empty (set LITELLM_API_BASE or video provider base_url)")
    url = _join(base, str(provider.extra.get("path") or "/videos"))
    body: dict[str, Any] = {
        "model": provider.model or "sora-2",
        "prompt": prompt,
    }
    if duration_s:
        body["seconds"] = int(duration_s)
    data = await http.post_json(url, headers=_auth_headers(provider), json=body, timeout=180.0)
    blob = await _blob_from_payload(data, http, headers=_auth_headers(provider), kind="video")
    if blob is not None:
        return blob
    job_id = str(data.get("id") or "")
    if not job_id:
        raise MediaProviderError(f"Video job id missing: {json.dumps(data)[:400]}")
    poll = str(provider.extra.get("poll_path") or "/videos/{id}")
    status_url = _join(base, poll.replace("{id}", job_id))
    for _ in range(60):
        await asyncio.sleep(3.0)
        status = await http.get_json(status_url, headers=_auth_headers(provider), timeout=60.0)
        state = str(status.get("status") or "").lower()
        blob = await _blob_from_payload(
            status, http, headers=_auth_headers(provider), kind="video"
        )
        if blob is not None:
            return blob
        if state in {"failed", "error", "cancelled"}:
            raise MediaProviderError(f"Video job {state}: {json.dumps(status)[:400]}")
    raise MediaProviderError("Video generation timed out")


async def _http_json(
    provider: MediaProvider,
    prompt: str,
    http: HttpTransport,
    *,
    kind: str,
) -> MediaBlob:
    if provider.api_key_env and not provider.api_key:
        raise MediaProviderError(f"API key missing ({provider.api_key_env})")
    mapping = {
        "prompt": prompt,
        "model": provider.model,
        "size": provider.size,
        "kind": kind,
    }
    path = str(provider.extra.get("path") or "/")
    url = _join(provider.resolved_base_url or provider.base_url, path)
    body = _fill_template(provider.extra.get("json_body") or {"prompt": "{{prompt}}"}, mapping)
    if not isinstance(body, dict):
        raise MediaProviderError("http_json json_body must be an object")
    data = await http.post_json(url, headers=_auth_headers(provider), json=body, timeout=180.0)
    b64_path = str(provider.extra.get("b64_json_path") or "")
    url_path = str(provider.extra.get("url_json_path") or "")
    if b64_path:
        b64 = json_path(data, b64_path)
        if b64:
            raw = base64.b64decode(str(b64))
            ext = "mp4" if kind == "video" else "png"
            mime = "video/mp4" if kind == "video" else "image/png"
            return MediaBlob(raw, mime, _filename(ext), source_url=None)
    if url_path:
        remote = json_path(data, url_path)
        if remote:
            raw, mime = await http.get_bytes(str(remote), timeout=180.0)
            ext = "mp4" if kind == "video" else "png"
            return MediaBlob(
                raw,
                mime or ("video/mp4" if kind == "video" else "image/png"),
                _filename(ext),
                source_url=str(remote),
            )
    blob = await _blob_from_payload(data, http, headers=_auth_headers(provider), kind=kind)
    if blob is None:
        raise MediaProviderError(f"Could not parse media from JSON: {json.dumps(data)[:400]}")
    return blob


async def _blob_from_payload(
    data: dict[str, Any],
    http: HttpTransport,
    *,
    headers: dict[str, str],
    kind: str,
) -> MediaBlob | None:
    b64 = json_path(data, "b64_json") or json_path(data, "data.0.b64_json")
    if b64:
        raw = base64.b64decode(str(b64))
        ext = "mp4" if kind == "video" else "png"
        mime = "video/mp4" if kind == "video" else "image/png"
        return MediaBlob(raw, mime, _filename(ext), source_url=None)
    remote = (
        json_path(data, "url")
        or json_path(data, "data.0.url")
        or json_path(data, "output.url")
        or json_path(data, "video_url")
        or json_path(data, "image_url")
    )
    if remote:
        raw, mime = await http.get_bytes(str(remote), headers=headers, timeout=180.0)
        ext = "mp4" if kind == "video" else "png"
        return MediaBlob(
            raw,
            mime or ("video/mp4" if kind == "video" else "image/png"),
            _filename(ext),
            source_url=str(remote),
        )
    return None


def _filename(ext: str) -> str:
    import time

    stamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{stamp}.{ext}"
