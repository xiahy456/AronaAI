#!/usr/bin/env python3
"""Unit smoke for screenshot parse, redact, and last-8 prune."""

from __future__ import annotations

import base64
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.image_input import (
    ImagePayload,
    parse_optional_image,
    prune_screenshots,
    redact_image_fields,
    redact_request_json,
    save_screenshot,
    screenshot_files,
)

_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 16 + b"\xff\xd9"


def main() -> None:
    encoded = base64.b64encode(_JPEG).decode("ascii")
    payload = parse_optional_image(
        {"image": {"mime": "image/jpeg", "data": encoded}}
    )
    assert payload is not None
    assert payload.mime == "image/jpeg"
    assert payload.data == _JPEG

    assert parse_optional_image({"content": "hi"}) is None
    assert parse_optional_image({"image": "not-an-object"}) is None
    assert parse_optional_image({"image": {"mime": "image/jpeg", "data": "%%%"}}) is None
    too_big = base64.b64encode(b"\xff\xd8\xff" + b"x" * (4 * 1024 * 1024 + 8)).decode("ascii")
    assert parse_optional_image({"image": {"mime": "image/jpeg", "data": too_big}}) is None

    redacted = redact_image_fields(
        {
            "type": "chat",
            "content": "hello",
            "image": {"mime": "image/jpeg", "data": encoded},
        }
    )
    assert redacted["content"] == "hello"
    assert "redacted" in redacted["image"]["data"]
    assert encoded not in redacted["image"]["data"]

    raw = '{"type":"chat","image":{"mime":"image/jpeg","data":"%s"}}' % encoded
    redacted_raw = redact_request_json(raw)
    assert encoded not in (redacted_raw or "")
    assert "redacted" in (redacted_raw or "")

    vision_prompt = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "hi"},
                {"type": "image_url", "image_url": {"url": payload.data_url()}},
            ],
        }
    ]
    redacted_prompt = redact_image_fields(vision_prompt)
    url = redacted_prompt[0]["content"][1]["image_url"]["url"]
    assert "redacted" in url
    assert "base64," not in url

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        names: list[str] = []
        for i in range(9):
            item = ImagePayload(mime="image/jpeg", data=_JPEG + bytes([i]))
            saved = save_screenshot(directory, item, keep=8)
            assert saved is not None
            names.append(saved.name)
            time.sleep(0.02)
        kept = screenshot_files(directory)
        assert len(kept) == 8
        assert names[0] not in {path.name for path in kept}
        assert names[-1] in {path.name for path in kept}

        extra = directory / "screenshot_old.png"
        extra.write_bytes(b"\x89PNG\r\n\x1a\n")
        os.utime(extra, (1, 1))
        prune_screenshots(directory, keep=8)
        assert extra.exists() is False
        assert len(screenshot_files(directory)) == 8

    print("ok")


if __name__ == "__main__":
    main()
