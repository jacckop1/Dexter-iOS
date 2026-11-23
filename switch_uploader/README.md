# Nintendo Switch IPA uploads — four remaining games

**Solateria 1.0.5 was already uploaded** and has been removed from the
upload manifest to avoid accidental duplicate delivery.

The following **four remaining games** are configured, with their exact
IPA URLs supplied by the user and their original icons and versions retained:

1. Ready or Nowhere — 1.0.0 (noord-store.com)
2. Mario vs. Donkey Kong — 1.0.1 (ipasoon.icu)
3. Cult of the Lamb — 1.5.27 (ipasoon.icu)
4. Super Mario 3D World + Bowser's Fury — 1.2.2 (ipasoon.icu)

The uploader only runs when the user manually chooses **Run workflow** in
**Actions -> Nintendo Switch IPA to Saved Messages**. The default batch is
`remaining_four`, which sequentially downloads, uploads, and deletes the
four files, one at a time. Other choices are `last_three` and four
individual game names, so a successful upload need not be duplicated if
a later one fails.

The IPA URLs, original names, versions, and image URLs are in
`switch_uploader/games.json`. The Telegram caption is fixed:

```text
لعبة نينتندو سويتش حصرية.

- تتطلب آيفون 16 فما فوق.
- تتطلب إصدار ios26 فما فوق.
- قد تحتوي تحميل داخلي.
```

All delivered filenames have the format
`Game Name - Version [ @iKiraPlus ].ipa`.

## Setup and limits

Configure GitHub Actions Secrets `TG_API_ID`, `TG_API_HASH` and
`TG_STRING_SESSION` for a personal Telegram Premium account.
The runner downloads each IPA with eight parallel 8-MiB HTTP Range requests,
retrying missing bytes on disconnect, then uses six concurrent 512-KiB
Telegram part lanes. Progress notices every 5%, with upload heartbeats
every 60 seconds. Transfer rates depend on the source and Telegram.

The `remaining_four` choice is **not a dry run**: when manually triggered,
it actually sends these four files to your Telegram Saved Messages.
Do not trigger two upload workflows concurrently with the same session.
A cancelled runner loses partial downloads and in-progress Telegram uploads.

This edit was committed with `[skip ci]` specifically to avoid launching
any automatic push-triggered workflow at the user's request. No upload or
source probe was manually dispatched as part of this change.
