from __future__ import annotations

import base64
from typing import Any

import pytest
from holix_media.config import MediaProvider
from holix_media.providers import generate_image, generate_video


class FakeHttp:
    def __init__(self, posts: list[dict[str, Any]], gets: dict[str, bytes] | None = None) -> None:
        self.posts = list(posts)
        self.gets = dict(gets or {})
        self.post_calls: list[str] = []

    async def post_json(self, url: str, *, headers, json, timeout=120.0):
        self.post_calls.append(url)
        if not self.posts:
            raise RuntimeError("unexpected POST " + url)
        return self.posts.pop(0)

    async def get_json(self, url: str, *, headers, timeout=60.0):
        return {"status": "completed", "url": "https://cdn.example/v.mp4"}

    async def get_bytes(self, url: str, *, headers=None, timeout=120.0):
        if url in self.gets:
            return self.gets[url], "image/png"
        if url.endswith(".mp4"):
            return b"mp4-bytes", "video/mp4"
        return b"img-bytes", "image/png"


@pytest.mark.asyncio
async def test_litellm_images_uses_openai_path(monkeypatch) -> None:
    monkeypatch.setenv("LITELLM_API_KEY", "sk-proxy")
    http = FakeHttp([{"data": [{"url": "https://cdn.example/a.png"}]}], gets={"https://cdn.example/a.png": b"IMG"})
    spec = MediaProvider(
        id="litellm",
        kind="image",
        type="litellm",
        base_url="http://127.0.0.1:4000/v1",
        api_key_env="LITELLM_API_KEY",
        model="openai/dall-e-3",
    )
    blob = await generate_image(spec, "cat", http=http)
    assert blob.data == b"IMG"
    assert blob.source_url == "https://cdn.example/a.png"
    assert "/images/generations" in http.post_calls[0]


@pytest.mark.asyncio
async def test_openai_images_b64(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    png = base64.b64encode(b"PNGDATA").decode()
    http = FakeHttp([{"data": [{"b64_json": png}]}])
    spec = MediaProvider(
        id="openai",
        kind="image",
        type="openai_images",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        model="dall-e-3",
    )
    blob = await generate_image(spec, "a cat", http=http)
    assert blob.data == b"PNGDATA"
    assert blob.mime == "image/png"
    assert http.post_calls[0].endswith("/images/generations")


@pytest.mark.asyncio
async def test_openai_images_url(monkeypatch) -> None:
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    http = FakeHttp(
        [{"data": [{"url": "https://cdn.example/a.png"}]}],
        gets={"https://cdn.example/a.png": b"IMG"},
    )
    spec = MediaProvider(
        id="grok",
        kind="image",
        type="openai_images",
        base_url="https://api.x.ai/v1",
        api_key_env="XAI_API_KEY",
        model="grok-2-image",
    )
    blob = await generate_image(spec, "logo", http=http)
    assert blob.data == b"IMG"


@pytest.mark.asyncio
async def test_http_json_url_path(monkeypatch) -> None:
    monkeypatch.setenv("CUSTOM_KEY", "k")
    http = FakeHttp(
        [{"result": {"file": "https://cdn.example/out.png"}}],
        gets={"https://cdn.example/out.png": b"OUT"},
    )
    spec = MediaProvider(
        id="custom",
        kind="image",
        type="http_json",
        base_url="https://api.example.com",
        api_key_env="CUSTOM_KEY",
        model="m1",
        extra={
            "path": "/v1/gen",
            "json_body": {"prompt": "{{prompt}}", "model": "{{model}}"},
            "url_json_path": "result.file",
        },
    )
    blob = await generate_image(spec, "sunset", http=http)
    assert blob.data == b"OUT"


@pytest.mark.asyncio
async def test_openai_videos_direct_url(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    http = FakeHttp([{"url": "https://cdn.example/v.mp4"}])
    spec = MediaProvider(
        id="openai",
        kind="video",
        type="openai_videos",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        model="sora-2",
    )
    blob = await generate_video(spec, "waves", http=http)
    assert blob.data == b"mp4-bytes"
    assert "video" in blob.mime
