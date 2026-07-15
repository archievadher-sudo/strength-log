#!/usr/bin/env python3
"""One-time WHOOP OAuth helper — run locally to mint the first refresh token.

WHOOP redirect URIs must be https:// (not http://localhost), so we use the
site's callback page to receive the auth code, then exchange it here.

Usage:
  1. Create a WHOOP app at https://developer.whoop.com (see README), with
     redirect URI:  https://archievadher-sudo.github.io/strength-log/whoop-callback.html
  2. Print the authorize URL and open it in your browser:
        WHOOP_CLIENT_ID=xxx python3 whoop/mint_token.py url
     Log in, approve. You'll land on the callback page showing a CODE.
  3. Exchange the code for tokens:
        WHOOP_CLIENT_ID=xxx WHOOP_CLIENT_SECRET=yyy python3 whoop/mint_token.py exchange <CODE>
     It prints your REFRESH TOKEN — add it as the WHOOP_REFRESH_TOKEN repo secret.
"""
import os, sys, json, urllib.parse, urllib.request

AUTH_URL  = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
REDIRECT  = "https://archievadher-sudo.github.io/strength-log/whoop-callback.html"
SCOPES    = "read:recovery read:sleep read:workout read:cycles read:profile offline"

def authorize_url():
    q = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": os.environ["WHOOP_CLIENT_ID"],
        "redirect_uri": REDIRECT,
        "scope": SCOPES,
        "state": "strengthlog-oauth-0001",
    })
    return f"{AUTH_URL}?{q}"

def exchange(code):
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT,
        "client_id": os.environ["WHOOP_CLIENT_ID"],
        "client_secret": os.environ["WHOOP_CLIENT_SECRET"],
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = json.load(urllib.request.urlopen(req))
    return r

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "url"
    if cmd == "url":
        print("\nOpen this URL, log in, and approve:\n")
        print(authorize_url())
        print("\nThen copy the CODE from the callback page and run:\n"
              "  WHOOP_CLIENT_ID=.. WHOOP_CLIENT_SECRET=.. python3 whoop/mint_token.py exchange <CODE>\n")
    elif cmd == "exchange":
        tok = exchange(sys.argv[2])
        print("\n=== SUCCESS ===")
        print("REFRESH TOKEN (add as repo secret WHOOP_REFRESH_TOKEN):\n")
        print(tok["refresh_token"])
        print("\n(access token is short-lived; the workflow mints fresh ones from the refresh token)")
    else:
        print("usage: mint_token.py [url | exchange <CODE>]")
