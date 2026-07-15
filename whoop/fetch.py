#!/usr/bin/env python3
"""Daily WHOOP sync — refresh token, pull v2 data, write docs/whoop_data.json.

Env (from GitHub Action secrets):
  WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET, WHOOP_REFRESH_TOKEN
Optional:
  WHOOP_START  ISO date (e.g. 2026-06-01) to bound history; default = all.

Writes:
  docs/whoop_data.json      the data the dashboard fetches
  new_refresh_token.txt     the rotated refresh token (workflow saves it back)

NOTE: refresh tokens ROTATE — every refresh invalidates the old one. We write
new_refresh_token.txt immediately after refreshing so the workflow can persist
it even if a later fetch step fails.
"""
import os, json, datetime, urllib.parse, urllib.request, urllib.error

BASE      = "https://api.prod.whoop.com/developer/v2"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
OUT_JSON  = os.path.join(os.path.dirname(__file__), "..", "docs", "whoop_data.json")
OUT_TOKEN = os.path.join(os.path.dirname(__file__), "..", "new_refresh_token.txt")


def refresh():
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": os.environ["WHOOP_REFRESH_TOKEN"],
        "client_id": os.environ["WHOOP_CLIENT_ID"],
        "client_secret": os.environ["WHOOP_CLIENT_SECRET"],
        "scope": "offline",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = json.load(urllib.request.urlopen(req))
    # persist the rotated refresh token ASAP
    with open(OUT_TOKEN, "w") as f:
        f.write(r["refresh_token"])
    return r["access_token"]


def get_all(access, path, params=None):
    """Follow WHOOP pagination (limit<=25, next_token) and return all records."""
    out, nt = [], None
    while True:
        p = dict(params or {})
        p["limit"] = 25
        if nt:
            p["nextToken"] = nt
        url = f"{BASE}{path}?" + urllib.parse.urlencode(p)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access}"})
        r = json.load(urllib.request.urlopen(req))
        out += r.get("records", [])
        nt = r.get("next_token") or r.get("nextToken")
        if not nt:
            break
    return out


def get_one(access, path):
    req = urllib.request.Request(f"{BASE}{path}", headers={"Authorization": f"Bearer {access}"})
    return json.load(urllib.request.urlopen(req))


def main():
    access = refresh()
    params = {}
    if os.environ.get("WHOOP_START"):
        params["start"] = os.environ["WHOOP_START"] + "T00:00:00.000Z"

    data = {
        "fetched": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"),
        "recovery":  get_all(access, "/recovery", params),
        "sleep":     get_all(access, "/activity/sleep", params),
        "cycle":     get_all(access, "/cycle", params),
        "workout":   get_all(access, "/activity/workout", params),
    }
    try:
        data["profile"] = get_one(access, "/user/profile/basic")
    except urllib.error.HTTPError:
        data["profile"] = None

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(data, f)
    print(f"wrote {OUT_JSON}: "
          f"{len(data['recovery'])} recovery, {len(data['sleep'])} sleep, "
          f"{len(data['cycle'])} cycle, {len(data['workout'])} workout records")


if __name__ == "__main__":
    main()
