# Nintendo Switch IPA uploads to personal Telegram Saved Messages

This one-off uploader runs ONLY on manually dispatched GitHub Actions and
presents an exclusive batch selector. It does not create a Telegram bot.

## Pick one batch in GitHub Actions

- `first_two`: **Solateria 1.0.5** + **Ready or Nowhere 1.0.0-1**
- `last_three`: **Mario vs. Donkey Kong 1.0.1** + **Cult of the Lamb 1.5.27** + **Super Mario 3D World + Bowser's Fury 1.2.2**

All five URLs and icons are in `switch_uploader/games.json` in that exact order.
The workflow validates the chosen batch and transfers only those selected.
Select the other batch in a separate run. Only one run is active at a time
because the workflow shares a personal Telegram StringSession.

## Fixed Telegram caption on every file

```text
لعبة نينتندو سويتش حصرية.

- تتطلب آيفون 16 فما فوق.
- تتطلب إصدار ios26 فما فوق.
- قد تحتوي تحميل داخلي.
```

Filenames are `Name - Version [ @iKiraPlus ].ipa`. Each file is sent as a
document with the given thumbnail (when available) to **Saved Messages**.

## Start

1. Ensure GitHub Actions is enabled for this repo, and the Actions Secrets
   `TG_API_ID`, `TG_API_HASH`, `TG_STRING_SESSION` are configured. They
   must be a **personal Premium account** session, not a bot.
2. Open **Actions > Nintendo Switch IPA to Saved Messages > Run workflow**.
3. Choose `first_two` or `last_three` and press **Run workflow** once.

No download is triggered by pushing this edit. The workflow tests the list
and batch selection before starting the network transfer. It will reject
sources without HTTP Range support or a reliable expected byte count.

## Throughput and constraints

The downloader uses up to **eight simultaneous 8-MiB HTTP Range connections**
per game (compared to three before); stalled ranges retry their missing
bytes, eventually switching to 1-MiB requests. The uploader uses **six
concurrent 512-KiB Telegram upload part lanes**, the maximum supported by
the included resilient_transfer implementation. Both show 5% progress
notices with average throughput and ETA.

Games are downloaded, uploaded and deleted one by one to fit typical
GitHub-hosted runner disk budgets. This is an intentional disk safeguard;
whole-game downloads are not parallel. Actual throughput depends on each
source, Cloudflare Worker behavior, Telegram, and GitHub network limits.
More parallel requests may trigger source rate limits; retry logic handles
many transient disconnects but does not guarantee delivery. No partial file
state survives cancellation or a new runner.

After both batches are delivered, remove the workflow and credentials,
and terminate the temporary session under Telegram Settings > Devices.
