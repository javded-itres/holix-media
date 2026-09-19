from holix_media.config import load_media_config


def test_load_from_settings_list() -> None:
    cfg = load_media_config(
        {
            "enabled": True,
            "image_providers": [
                {
                    "id": "grok",
                    "type": "openai_images",
                    "base_url": "https://api.x.ai/v1",
                    "api_key_env": "XAI_API_KEY",
                    "model": "grok-2-image",
                }
            ],
        }
    )
    assert cfg.enabled
    assert cfg.provider("image") is not None
    assert cfg.provider("image").id == "grok"
    assert cfg.provider("image", "missing") is None
    assert cfg.provider("video") is None


def test_litellm_resolves_base_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LITELLM_API_BASE", "http://127.0.0.1:4000")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-litellm")
    cfg = load_media_config(
        {
            "image_providers": [
                {
                    "id": "litellm",
                    "type": "litellm",
                    "base_url": "",
                    "api_key_env": "LITELLM_API_KEY",
                    "model": "dall-e-3",
                }
            ]
        }
    )
    p = cfg.provider("image")
    assert p is not None
    assert p.type == "litellm"
    assert p.resolved_base_url.endswith("/v1")
    assert "4000" in p.resolved_base_url
    assert p.api_key == "sk-litellm"


def test_env_overrides_image(monkeypatch) -> None:
    monkeypatch.setenv("HOLIX_MEDIA_IMAGE_MODEL", "dall-e-3")
    monkeypatch.setenv("HOLIX_MEDIA_IMAGE_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("HOLIX_MEDIA_IMAGE_API_KEY_ENV", "OPENAI_API_KEY")
    cfg = load_media_config({})
    p = cfg.provider("image")
    assert p is not None
    assert p.model == "dall-e-3"
    assert p.type == "openai_images"
