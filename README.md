# holix-media

MIT-расширение [Holix](https://github.com/javded-itres/Holix): агент **генерирует изображения и видео** через подключаемые модели и **отправляет файлы в Telegram и MAX**.

Лицензия: [MIT](LICENSE).

## Что умеет

| Возможность | Как |
|-------------|-----|
| Картинка | tool `generate_image` / слэш `/imagine` |
| Видео | tool `generate_video` / слэш `/video` |
| Провайдеры | OpenAI Images, OpenAI Videos, xAI (тот же `openai_images`), любой HTTP JSON |
| Мессенджеры | файл пишется в `workspace/media/`, затем `send_chat_files` (альбом Telegram / вложение MAX) |
| CLI | `holix media providers`, `holix media imagine "…"`, `holix media video "…"` |

Holix core **не** форкается: пакет ставится рядом и находится через entry points.

## Требования

- Python 3.12+
- Holix ≥ 1.1.0 и `holix-sdk`
- Ключ выбранного API (например `OPENAI_API_KEY` или `XAI_API_KEY`)

## Подключение

### 1. Установить пакет в окружение Holix

```bash
git clone https://github.com/javded-itres/holix-media.git
cd holix-media

# тот же venv / uv, что и Holix
uv pip install -e .
# или
pip install -e .
```

Проверка:

```bash
holix extensions list
holix extensions agent-list
# должны быть строки  media
```

### 2. Ключи в профиле

`~/.holix/profiles/<профиль>/.env` или `~/.holix/global/.env`:

```bash
OPENAI_API_KEY=sk-...
# и/или
XAI_API_KEY=xai-...
```

### 3. Настроить модели

При первом запуске агента Holix запишет дефолты в:

`~/.holix/profiles/<профиль>/extension_settings/media.yaml`

Отредактируйте провайдеров:

```yaml
enabled: true
auto_send: true
output_subdir: media

image_providers:
  - id: openai
    type: openai_images
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    model: dall-e-3
    size: 1024x1024
  - id: grok
    type: openai_images
    base_url: https://api.x.ai/v1
    api_key_env: XAI_API_KEY
    model: grok-2-image

video_providers:
  - id: openai
    type: openai_videos
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    model: sora-2
    path: /videos
```

Первый элемент списка — провайдер по умолчанию. В tool можно передать `provider: grok`.

Переменные окружения (перекрывают YAML):

| Env | Смысл |
|-----|--------|
| `HOLIX_MEDIA_ENABLED` | вкл/выкл |
| `HOLIX_MEDIA_AUTO_SEND` | сразу слать файл в чат Telegram/MAX |
| `HOLIX_MEDIA_IMAGE_TYPE` | `openai_images` / `http_json` |
| `HOLIX_MEDIA_IMAGE_BASE_URL` | например `https://api.x.ai/v1` |
| `HOLIX_MEDIA_IMAGE_MODEL` | `dall-e-3`, `grok-2-image`, … |
| `HOLIX_MEDIA_IMAGE_API_KEY_ENV` | имя переменной с ключом |
| `HOLIX_MEDIA_VIDEO_*` | то же для видео |

### 4. Перезапустить агента / gateway

```bash
# TUI
holix tui

# мессенджеры (профиль production и т.п.)
holix -p production gateway restart
```

В чате: «нарисуй красного кота» или `/imagine красный кот`. Агент вызывает `generate_image`, сохраняет PNG в `workspace/media/` и при `auto_send: true` шлёт вложение в Telegram/MAX.

Если отправка не сработала, агент должен вызвать core-tool `send_chat_files` с путём к файлу.

### 5. Drop-in без pip (опционально)

```text
~/.holix/profiles/<профиль>/extensions/media/
  agent.py          # скопировать пакет или symlink на holix_media/
  holix.plugin.json
  settings.default.yaml
```

Удобнее ставить wheel/editable, как выше.

### 6. Production (VDS)

```bash
# на сервере, в venv Holix
uv pip install -e /opt/extensions/holix-media
# ключи в /var/lib/holix/profiles/production/.env
systemctl restart holix-gateway@production
holix -p production extensions agent-list
```

Не копируйте ключи в git. Прод — через ваш обычный деплой расширений, не hotfix файлов Holix core.

## Типы провайдеров

### `openai_images`

`POST {base_url}/images/generations` (DALL·E, gpt-image, xAI Grok Image). Ответ: `b64_json` или `url`.

### `openai_videos`

`POST {base_url}/videos` (Sora-совместимые шлюзы). Если в ответе `id` — опрос `GET /videos/{id}` до URL/файла.

### `http_json`

Любой HTTP API:

```yaml
- id: custom
  type: http_json
  base_url: https://api.example.com
  api_key_env: EXAMPLE_API_KEY
  model: my-model
  path: /v1/generate
  json_body:
    prompt: "{{prompt}}"
    model: "{{model}}"
  url_json_path: data.0.url
  # или b64_json_path: data.0.b64
```

Плейсхолдеры: `{{prompt}}`, `{{model}}`, `{{size}}`, `{{kind}}`.

## CLI

```bash
holix media providers
holix media imagine "кот в космосе" --provider grok
holix media video "волны на закате"
```

Файлы пишутся в текущий workspace (`media/`).

## Разработка

```bash
uv pip install -e ".[dev]"
pytest -q
```

## License

MIT — see [LICENSE](LICENSE).
