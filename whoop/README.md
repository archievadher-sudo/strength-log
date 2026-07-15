# WHOOP auto-sync

A daily GitHub Action pulls WHOOP data (recovery, sleep, strain, workouts) via the
WHOOP v2 API and commits `docs/whoop_data.json`, which the dashboard fetches.

## One-time setup (you do this once)

1. **Create a WHOOP app** at <https://developer.whoop.com> → *Developer Dashboard* → **Create app**:
   - **Redirect URI:** `https://archievadher-sudo.github.io/strength-log/whoop-callback.html`
   - **Scopes:** `read:recovery`, `read:sleep`, `read:workout`, `read:cycles`, `read:profile`, `offline`
   - Copy the **Client ID** and **Client Secret**.

2. **Mint a refresh token** (locally):
   ```bash
   WHOOP_CLIENT_ID=<id> python3 whoop/mint_token.py url      # open the printed URL, log in, approve
   # you land on the callback page showing a CODE — copy it, then:
   WHOOP_CLIENT_ID=<id> WHOOP_CLIENT_SECRET=<secret> python3 whoop/mint_token.py exchange <CODE>
   # prints your REFRESH TOKEN
   ```

3. **Add repo secrets** (Settings → Secrets and variables → Actions → *New repository secret*):
   - `WHOOP_CLIENT_ID`
   - `WHOOP_CLIENT_SECRET`
   - `WHOOP_REFRESH_TOKEN`  (from step 2)
   - `GH_PAT` — a fine-grained Personal Access Token scoped to this repo with **Secrets: Read and write**
     (needed so the Action can save the rotated refresh token each run).

4. Run the workflow once manually (Actions → *WHOOP sync* → **Run workflow**) to backfill.
   After that it runs daily.

## Notes
- WHOOP **rotates refresh tokens** — each refresh invalidates the old one. `fetch.py` writes the new
  token to `new_refresh_token.txt` immediately, and the workflow saves it back to the `WHOOP_REFRESH_TOKEN`
  secret (that's what `GH_PAT` is for).
- History size can be bounded with the `WHOOP_START` secret/var (ISO date, e.g. `2026-06-01`); default = all.
