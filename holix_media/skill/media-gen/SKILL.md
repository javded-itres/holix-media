---
name: media-gen
description: Generate images and short videos, then deliver them to Telegram/MAX chats.
---

# Media generation

When the user asks to **нарисуй**, **сгенерируй картинку**, **imagine**, **make a video**, **сделай ролик**:

1. Call `generate_image` or `generate_video` with a clear prompt (language of the user).
2. The tool writes a file under workspace `media/` and, in Telegram/MAX, tries to **send the attachment**.
3. If the tool result does not contain `Sent N file(s)`, call `send_chat_files` with the saved path.
4. Never paste base64. Never claim the user received the file unless send_chat_files / generate_* reported a send.

Optional `provider` argument selects a configured backend (see extension settings `image_providers` / `video_providers`).
