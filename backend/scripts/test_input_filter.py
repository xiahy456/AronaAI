#!/usr/bin/env python3
"""Assert is_unusable_user_text rejects ASR dirty text and keeps normal chat."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.input_filter import is_unusable_user_text  # noqa: E402


def main() -> None:
    dirty = [
        "",
        "   ",
        None,
        "[Tencent Speech Recognizer]Didnt recognize vailable content!",
        "[Tencent Speech Recognizer]Audio data is null!",
        "Didnt recognize anything useful",
        "Request failed: timeout",
    ]
    clean = [
        "晚上好呀，阿洛娜。",
        "我在摸鱼。",
        "草莓牛奶好喝吗？",
        "hello",
    ]
    fails: list[str] = []
    for item in dirty:
        if not is_unusable_user_text(item):  # type: ignore[arg-type]
            fails.append(f"expected unusable: {item!r}")
    for item in clean:
        if is_unusable_user_text(item):
            fails.append(f"expected usable: {item!r}")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        raise SystemExit(1)
    print("OK: is_unusable_user_text cases passed")


if __name__ == "__main__":
    main()
