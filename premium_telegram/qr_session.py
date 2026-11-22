#!/usr/bin/env python3
"""Interactive QR login inside a PRIVATE GitHub Codespace terminal.

Never run this in GitHub Actions or paste the resulting session into chat/logs.
"""

import asyncio
import getpass
import os
import sys

import qrcode
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession


def show_qr(url: str) -> None:
    code = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=1,
    )
    code.add_data(url)
    code.make(fit=True)
    print("\nScan ONLY inside Telegram > Settings > Devices > Link Desktop Device:\n")
    code.print_ascii(out=sys.stdout, invert=True)
    print("\nKeep this terminal open while approving login.\n", flush=True)


async def login() -> None:
    id_text = os.getenv("TG_API_ID") or input("Telegram API ID: ").strip()
    api_hash = os.getenv("TG_API_HASH") or getpass.getpass("Telegram API Hash: ").strip()
    if not id_text.isdecimal() or not api_hash:
        raise SystemExit("Please provide a valid API ID and API Hash")

    client = TelegramClient(StringSession(), int(id_text), api_hash, connection_retries=5)
    await client.connect()
    try:
        qr = await client.qr_login()
        for attempt in range(4):
            show_qr(qr.url)
            try:
                await qr.wait()
                break
            except SessionPasswordNeededError:
                password = getpass.getpass("Telegram 2-step verification password: ")
                await client.sign_in(password=password)
                break
            except asyncio.TimeoutError:
                if attempt == 3:
                    raise RuntimeError("QR login expired after 4 attempts") from None
                print("QR expired; generating another...", flush=True)
                await qr.recreate()

        me = await client.get_me()
        if not me or getattr(me, "bot", False):
            raise RuntimeError("You must sign in to a PERSONAL account, not a bot")
        print("Login successful!\n")
        print("Copy the next value into GitHub Actions Secret TG_STRING_SESSION ONLY:")
        print(client.session.save())
        print("\nDO NOT commit or share it. Delete this Codespace and revoke the device after use.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(login())
    except KeyboardInterrupt:
        raise SystemExit("\nCancelled")
