# One-off Telegram Premium IPA uploader

This folder is a **standalone manual GitHub Actions tool**. It does not modify the existing Dexter iOS build, does not run a Telegram bot, and does not modify the private `ikiraplus/dlbot` Vercel project.

## What it does

1. A manually triggered GitHub Action verifies a real, personal Telegram Premium session.
2. When `verify_only = false`, it downloads one direct IPA URL to the temporary runner disk, checks file size and available storage, then uploads the IPA using MTProto.
3. Sends from **your personal Premium account** to `me` (Saved Messages) or `@ikiraplus1`.
4. Deletes the downloaded file automatically with the runner's temporary directory when finished.

**No bot token. No Vercel. No Github artifact upload. Nothing is added to Releases.**

## Configure GitHub Secrets (you must do this yourself)

Repository -> **Settings -> Secrets and variables -> Actions -> New repository secret**:

- `TG_API_ID`: your Telegram application API ID from https://my.telegram.org/apps
- `TG_API_HASH`: your Telegram application API hash
- `TG_STRING_SESSION`: login session generated locally, see below
- `PREMIUM_SOURCE_URL` (optional): direct download URL stored in a Secret rather than exposed as a workflow input

Do **not** commit a session or paste it into an issue, workflow log, or a chat. A StringSession can grant access to your Telegram account. Do not run a session-generation script on GitHub Actions.

### Generate session on your **own computer** only

Install Python 3.12 or newer, clone the repository, and run:

```bash
python -m pip install -r premium_telegram/requirements.txt
python premium_telegram/generate_session.py
```

The script asks for API ID/API Hash and initiates a Telegram login (code/2FA prompts). Paste the resulting `TG_STRING_SESSION` **only in the GitHub Secret value**, never in GitHub source files or messages.

## Run workflow

Go to **Actions -> Telegram Premium IPA (manual) -> Run workflow** on `main`.

1. Initially leave **Verify only = true**. The job will validate your session and Premium status without downloading anything.
2. For the actual transfer set **Verify only = false**.
3. Fill a direct IPA `url` (or leave it blank to use the optional `PREMIUM_SOURCE_URL` Secret).
4. Optional: fill `file_name` if the URL doesn't end in `.ipa`.
5. Destination: `me` for Saved Messages or `@ikiraplus1` if your account is allowed to publish there.

The `url` workflow input can be visible to people who can see workflow runs. Prefer `PREMIUM_SOURCE_URL` Secret for token-bearing/signed links, especially if you make the repository public.

## Limits and warnings

- The workflow expects one **HTTP/HTTPS direct URL** and a file with extension `.ipa`.
- It requires a server-provided known file size. HTTP Range allows download resume between retries; other sources restart from zero after a broken transfer.
- It uses Telegram MTProto parts of 512 KiB and limits the file to 8000 parts = **4,194,304,000 bytes**. Actual acceptance depends on Telegram's current account/server limits. A 3.8 GiB IPA is within this configured ceiling.
- Telegram may expire uploaded parts after a while; speed and file host reliability are important.
- Workflow time limit is 330 minutes, below GitHub's 6-hour job ceiling. A slow transfer can still fail.
- The standard Ubuntu runner's disk must have sufficient free space; this is checked before download.
- The script has not been tested against a real 3.8GB transfer until you configure Secrets and run it.
- **Keep the repo private if possible.** In a public repository, write-access users can change workflows to misuse Secrets; never enable untrusted code or PR-triggered secret access for this job.
- For a channel destination, your personal account must have posting permission.
- Never upload files you do not have permission to distribute.

## Cleanup after the 1-2 files

1. Confirm the files have arrived in Telegram.
2. Delete `TG_STRING_SESSION`, `TG_API_ID`, `TG_API_HASH`, and any `PREMIUM_SOURCE_URL` from GitHub Actions Secrets.
3. In Telegram Settings -> Devices, terminate the temporary session created for this uploader.
4. Delete only this workflow and `premium_telegram/` or delete the entire repository **only if you are sure you don't need the existing Dexter iOS project**. Deleting this repository also deletes its iOS source code and build workflows.

**Your original `ikiraplus/dlbot` repository remains untouched.**

## QR login in GitHub Codespaces (no Termux / PC required)

From this repository, click **Code -> Codespaces -> Create codespace on main**.
Then open the Codespaces terminal and enter:

```bash
python -m pip install -r premium_telegram/requirements.txt
python premium_telegram/qr_session.py
```

Enter your `API ID` and `API Hash`. The terminal will display a QR code. **On a separate phone with your Telegram account already logged in**, open Telegram **Settings -> Devices -> Link Desktop Device** and scan the QR. Approve login and, if requested, enter your two-step password in the private terminal. Copy the resulting `TG_STRING_SESSION` into **Repository Settings -> Secrets and variables -> Actions**. Never post it publicly.

**Only one phone?** QR scanning your own phone's browser is generally impractical. Use the login-code method instead, in the same Codespace terminal:

```bash
python premium_telegram/generate_session.py
```

It prompts for phone number, Telegram login code and optional two-step password. You do **not** need a second device for this approach.

For security, **do not run QR/session generation via GitHub Actions**: public logs can expose login credentials. Close and delete your Codespace when finished, and after the one-off upload terminate that Telegram session via **Settings -> Devices**.

## JSON metadata, caption and thumbnail (new)

You can now upload one IPA with its original description and an icon thumbnail **from a JSON file**. In Actions -> Run workflow, set **Verify only = false**, leave **url** blank, and fill **json_source** with either a public direct HTTPS JSON URL or a relative repository file path, e.g. `premium_telegram/input.json`. Set `app_selector` if the JSON contains multiple apps (name, ID, or 1-based index). The file must exist in the repository before running the workflow. You can also store a private JSON URL in `PREMIUM_METADATA_URL` repository Secret instead of entering it into the workflow input.

This parser recognizes common AltStore-style and custom app metadata: top-level app objects, arrays, `apps`, `data.apps`, and common `ipaUrl`/`downloadURL`, `description`/`localizedDescription`, and `iconURL`/`icon` fields. It also looks at `versions[]` when no direct IPA URL exists. **The actual JSON schema must be reviewed before using a large file.** A multi-app file with no selector is rejected rather than uploading an arbitrary app.

The icon image is fetched and converted into a small JPEG before downloading the large IPA. It is passed to Telethon as a document `thumb`; Telegram may still decline or replace a custom document thumbnail. The full description is attached as the IPA caption up to Telegram's 1024 UTF-16-unit limit; any extra description is sent in a follow-up message (maximum 4096 units each). Nothing is intentionally truncated.

Always use `destination = me` to send to your own Saved Messages. **Never place secret-bearing JSON source links into a public workflow input or commit confidential JSON into a public repository.** `PREMIUM_METADATA_URL` can be used for a secret JSON URL.

To validate just the JSON parser without touching Telegram credentials:
```bash
python -m unittest discover -s premium_telegram -p test_metadata.py -v
```

## One-off PUBG GL / KR preset (from supplied jom (56).json)

**Use [Upload PUBG GL + KR to Saved Messages](../.github/workflows/telegram-premium-pubg.yml)** for the two specific games only. It does not need a JSON URL or additional secrets; `premium_telegram/pubg_targets.json` contains ONLY the two extracted current records from the provided 2026-11-22 user JSON.

- `game = both`: GL and KR as two separate sequential GitHub Actions jobs (one runner at a time).
- `game = gl` or `kr`: run one selected game if retry needed.
- `verify_only = true`: verifies account and runs parser tests, without any IPA download.
- `verify_only = false`: downloads/ships the current `ipaUrl` to **Saved Messages only**.

Only the whitelisted IDs **APP-5874636765** and **APP-1167550679** are allowed. The script rejects other game names, overrides, alternate upload destinations, or missing note/icon/version. It never looks at `previousVersions`.

The exact filenames are:
- `Pubg GL Hack - 4.7.0 [ @iKiraPlus ].ipa`
- `Pubg KR Hack - 4.7.0 [ @iKiraPlus ].ipa`

Their `note` is used verbatim as the document caption. Their `icon` is fetched and attached as a document thumbnail; Telegram ultimately controls its display. Neither file nor icon is added to GitHub Releases or artifacts. Files are removed from the temporary runner disk after the job. See original JSON `ipaUrl` links in `pubg_targets.json`.

**No live transfer has been started by this code change.** Run the manual workflow to upload. If one job fails, retry just that game; successful files should not be uploaded twice.

## Concurrent PUBG transfers and failure recovery (2026-11-22)

The PUBG preset uploads GL and KR **concurrently inside one GitHub runner using one Telegram StringSession and one shared TelegramClient**. This is intentional: using the same StringSession on two different runners can cause Telegram's AUTH_KEY_DUPLICATED and permanently revoke the key.

- Both IPA sources are downloaded concurrently on separate Python threads. HTTP Range is **mandatory**, and the downloader resumes from the byte already saved locally after a dropped connection, slow response, transient 5xx or 429. It never discards the partially downloaded file to restart from zero.
- After download, each game's MTProto upload has two in-flight part requests using the one shared client. Failed 512 KiB parts are retried with identical file ID and part index without restarting successful parts. Progress logs label the game (`[gl]` / `[kr]`).
- One GitHub runner must have enough **free space** for both IPAs plus 768 MiB overhead. A size check occurs before download. If it fails, run `gl` and `kr` one at a time.
- The 350-minute GitHub job time limit, 3-hour download retry budget and 3-hour Telegram upload retry budget remain. A cancelled job, a runner crash, a link that permanently expires, or Telegram's temporary file-part expiration cannot be prevented. **A new GitHub run cannot resume old temporary bytes**, because they were stored only on the previous runner; persistent object storage would be needed for that.
- Tests `test_resilient_transfer.py` and `test_telegram_part_retry.py` simulate an interrupted HTTP download and a failed Telegram part, with no live Telegram account needed.

### Start

Go to Actions -> Upload PUBG GL + KR to Saved Messages -> Run workflow. Select `game=both`, set `verify_only=false`, and dispatch once. The workflow will download both games and deliver each to Saved Messages under the specified exact filename, note and thumbnail. **Do not dispatch the generic uploader or a second PUBG workflow simultaneously using this same StringSession.** You can use `gl` or `kr` separately if one game needs retry. No live transfer has been started automatically just by editing the repository.

## Fast download and live progress (2026-11-22)

The PUBG uploader now uses **8 independent HTTP Range connections per game** (16 in total with `both`) on the GitHub-hosted Ubuntu runner. It downloads 32 MiB chunks directly into disjoint offsets of one sparse IPA, so there is no extra full-size temporary copy. A frozen / dropped connection retries the missing portion of its range from the last downloaded byte. This optimizes use of the bandwidth *available to the GitHub runner and source server*; it cannot choose a globally fastest network or bypass host throttling.

The GitHub Actions **step log** receives a visible `::notice` at **every 5%** of each game's download, with game label, transferred MiB, average MiB/s and estimated seconds remaining. Telegram-part upload progress is also logged every 5% for each game, using the same active session. The combined run may show interleaved GL/KR messages because both games transfer concurrently. These are log events / annotations, not a GitHub Actions dashboard progress bar. A new GitHub runner or cancelled job still cannot resume old bytes.
