# Nintendo Switch IPA: five pending games, two batches, no thumbnails

**Solateria was previously delivered and is excluded from this manifest.**

The five configured games are sent sequentially as IPA documents to the
authorized personal Telegram Premium account's **Saved Messages**.

## Batch options (ONLY TWO)

`first_two`:
1. Ready or Nowhere — 1.0.0
2. Air Strike Command Tactical Assault Operation — 1.0.0

`last_three`:
3. Mario vs. Donkey Kong — 1.0.1
4. Cult of the Lamb — 1.5.27
5. Super Mario 3D World + Bowser's Fury — 1.2.2

Source URLs are the exact user-supplied links in `switch_uploader/games.json`.
The four previously configured icon URLs remain as metadata; Air Strike
has no icon URL because none was provided. **The uploader never downloads
an icon, sends a cover-photo message or sets a Telegram document thumbnail**.
It sends only each IPA document with the formatted name, in the order above.

Every IPA filename follows `Game Name - Version [ @iKiraPlus ].ipa`.
The Telegram caption remains:

```text
لعبة نينتندو سويتش حصرية.

- تتطلب آيفون 16 فما فوق.
- تتطلب إصدار ios26 فما فوق.
- قد تحتوي تحميل داخلي.
```

## Manual upload only

Go to **Actions -> Nintendo Switch IPA to Saved Messages -> Run workflow**,
then choose one of exactly two options: `first_two` or `last_three`.
`first_two` is the default. **No upload runs automatically on git push.**
The commit is marked `[skip ci]` so the source diagnostic is not triggered
by this update. Do not run two workflows concurrently with the same
Telegram StringSession.

The three repository secrets `TG_API_ID`, `TG_API_HASH`,
`TG_STRING_SESSION` must be configured for your personal Premium account.
Files are downloaded/uploaded sequentially and removed from local disk
between games. Ranged downloading and Telegram parts include retries.
A cancelled GitHub runner loses unfinished file progress, and transfer
speed depends on both the source server and Telegram.
