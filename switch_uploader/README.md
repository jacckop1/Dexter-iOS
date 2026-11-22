# One-off Nintendo Switch IPA uploader

This is the **only** workflow installed for this one-off batch. It runs only
when manually started in GitHub Actions. It sends IPA documents to **your
own Telegram Saved Messages** using a **personal Telegram Premium session**,
not a Telegram bot.

## Fixed caption (identical for every game)

```text
لعبة نينتندو سويتش حصرية.

- تتطلب آيفون 16 فما فوق.
- تتطلب إصدار ios26 فما فوق.
- قد تحتوي تحميل داخلي.
```

File naming: `Game Name - Version [ @iKiraPlus ].ipa`

Populate `switch_uploader/games.json` with game entries (name, version, URL,
optional icon URL). Example:

```json
{
  "games": [
    {
      "name": "Example Game",
      "version": "1.0",
      "url": "https://example.com/example.ipa",
      "icon": "https://example.com/icon.png"
    }
  ]
}
```

The placeholder file has an empty list until actual links arrive. Uploading
requires a known content length and HTTP Range support. A source that lacks
Range is rejected before downloading a multi-GB IPA.

## Credentials and execution

Store `TG_API_ID`, `TG_API_HASH`, and `TG_STRING_SESSION` as GitHub Actions
**repository secrets**. If previously deleted, create a fresh Telegram
session and add the secrets again. Do not send the session string in chat.

Go to **Actions -> Nintendo Switch IPA to Saved Messages -> Run workflow**,
uncheck `Verify only`, and submit once. Each game downloads and uploads
in turn on ONE GitHub runner and ONE Telegram session. Each file is
automatically removed after its upload to keep disk usage low.

Progress is logged in 5% intervals for download and MTProto uploads.
Network disconnects retry the current HTTP Range / 512-KiB Telegram part
within the same running job. Cancelling the job or losing the GitHub runner
loses locally downloaded chunks; they do not persist between job runs.
GitHub Actions runner and Telegram have size and time limits. Actual speed
depends on the host, runner and bandwidth; no delivery is guaranteed.

The previous Dexter iOS application source files remain intact. The old
Telegram upload and iOS-build workflows are NOT restored. After completion,
remove this temporary workflow, delete stored secrets and terminate the
Telegram session if no longer needed.
