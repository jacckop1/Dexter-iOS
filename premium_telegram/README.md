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
