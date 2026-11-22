# PUBG GL-only Telegram Premium IPA uploader

Uploads only **Pubg GL Hack 4.7.0** to your Telegram **Saved Messages**.
The fixed metadata in `premium_telegram/pubg_targets.json` specifies
the original IPA URL, game icon, and unchanged description. Previous versions
are never used.

Expected filename:
`Pubg GL Hack - 4.7.0 [ @iKiraPlus ].ipa`

## Configuration

Keep the three GitHub Actions Secrets: `TG_API_ID`, `TG_API_HASH`,
`TG_STRING_SESSION`. Do not share or log them. Do not start two workflows
using the same StringSession at the same time.

## One-click upload

Open **Actions -> Upload PUBG GL to Saved Messages -> Run workflow**,
uncheck `Verify only` and press **Run workflow** ONCE.

Automatic GL preflight tests run on this commit. They verify metadata, HTTP
Range support, source response size, and simulated interruptions without
using Telegram credentials or downloading the large IPA.

## Speed and resilience

- Uses three parallel HTTP Range connections with bounded 4 MiB ranges.
- When a request repeatedly fails or stalls, retries its missing bytes in
  smaller 1 MiB ranges with a shorter 18-second read timeout.
- Never re-downloads acknowledged bytes during the SAME GitHub runner job.
- GitHub logs show download and upload at 5% increments with speeds/ETA.
- MTProto upload uses four simultaneous 512 KiB part lanes, retrying only
  failed parts. Telegram account session stays on one GitHub runner.
- Source capacity, rate limits, and network can still throttle or prevent the
  transfer. A cancelled job or destroyed runner loses temporary download
  state: restarting GitHub Actions requires downloading again.

No automatic large-file upload is triggered by a commit. After successful
delivery, remove your sensitive Secrets and revoke the temporary Telegram
session in Telegram Settings > Devices.
