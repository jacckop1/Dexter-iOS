#!/usr/bin/env python3
"""Run only on your own computer. Never paste the session into a chat or commit it."""

import getpass
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession


def main() -> None:
    api_id_text = os.getenv("TG_API_ID") or input("API ID (my.telegram.org/apps): ").strip()
    api_hash = os.getenv("TG_API_HASH") or getpass.getpass("API Hash: ").strip()
    if not api_id_text.isdecimal() or not api_hash:
        raise SystemExit("Missing API ID or API Hash")
    print("Telegram will ask for your phone number, login code, and 2FA password if enabled.")
    with TelegramClient(StringSession(), int(api_id_text), api_hash) as client:
        me = client.get_me()
        if not me or getattr(me, "bot", False):
            raise SystemExit("A personal account is required")
        print("Connected. Do not share the next line with anyone.")
        print("\nTG_STRING_SESSION (copy into GitHub Actions secret ONLY):")
        print(client.session.save())
        print("\nAfter using this temporary project, revoke this session in Telegram Devices.")


if __name__ == "__main__":
    main()
