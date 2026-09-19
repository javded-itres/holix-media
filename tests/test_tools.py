from __future__ import annotations

from pathlib import Path

import pytest
from holix_media.config import MediaConfig, MediaProvider
from holix_media.providers import MediaBlob
from holix_media.tools import GenerateImageTool


class _Cfg:
    workspace_root: str


@pytest.mark.asyncio
async def test_generate_image_saves_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cfg = MediaConfig(
        enabled=True,
        auto_send=False,
        output_subdir="media",
        image_providers=(
            MediaProvider(
                id="openai",
                kind="image",
                type="openai_images",
                base_url="https://api.openai.com/v1",
                api_key_env="OPENAI_API_KEY",
                model="dall-e-3",
            ),
        ),
        video_providers=(),
    )
    agent = type("A", (), {})()
    agent.config = type("C", (), {"workspace_root": str(tmp_path)})()
    tool = GenerateImageTool(config=cfg, agent=agent)

    async def fake_gen(provider, prompt, **kwargs):
        return MediaBlob(b"PNG", "image/png", "pic.png")

    monkeypatch.setattr("holix_media.tools.generate_image", fake_gen)
    result = await tool.execute(prompt="a tree")
    assert "Saved image:" in result
    assert "file://" in result
    assert "[Open image]" in result
    files = list((tmp_path / "media").glob("*.png"))
    assert len(files) == 1
    assert files[0].read_bytes() == b"PNG"


@pytest.mark.asyncio
async def test_generate_image_requires_provider() -> None:
    cfg = MediaConfig(True, True, "media", (), ())
    tool = GenerateImageTool(config=cfg, agent=None)
    out = await tool.execute(prompt="x")
    assert out.startswith("Error:")


@pytest.mark.asyncio
async def test_generate_image_passes_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    src = tmp_path / "in.png"
    src.write_bytes(b"REF")
    cfg = MediaConfig(
        enabled=True,
        auto_send=False,
        output_subdir="media",
        image_providers=(
            MediaProvider(
                id="openai",
                kind="image",
                type="openai_images",
                base_url="https://api.openai.com/v1",
                api_key_env="OPENAI_API_KEY",
                model="dall-e-3",
            ),
        ),
        video_providers=(),
    )
    agent = type("A", (), {})()
    agent.config = type("C", (), {"workspace_root": str(tmp_path)})()
    tool = GenerateImageTool(config=cfg, agent=agent)
    seen: dict = {}

    async def fake_gen(provider, prompt, **kwargs):
        seen["refs"] = kwargs.get("references")
        return MediaBlob(b"PNG", "image/png", "pic.png")

    monkeypatch.setattr("holix_media.tools.generate_image", fake_gen)
    result = await tool.execute(prompt="оживи", references=[str(src)])
    assert "Saved image:" in result
    assert seen["refs"]
    assert seen["refs"][0].path == src.resolve()


@pytest.mark.asyncio
async def test_generate_image_missing_reference(tmp_path: Path) -> None:
    cfg = MediaConfig(
        True,
        False,
        "media",
        (
            MediaProvider(
                id="openai",
                kind="image",
                type="openai_images",
                base_url="https://api.openai.com/v1",
                api_key_env="OPENAI_API_KEY",
                model="x",
            ),
        ),
        (),
    )
    tool = GenerateImageTool(config=cfg, agent=None)
    out = await tool.execute(prompt="x", references=[str(tmp_path / "nope.png")])
    assert out.startswith("Error:")
