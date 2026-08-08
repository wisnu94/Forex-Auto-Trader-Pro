#!/usr/bin/env python3
"""
Minimal example script for a GitHub App workflow.
- Build a JWT from APP_PRIVATE_KEY & APP_ID
- Get the installation for the current repo
- Create an installation access token
- Call the repos API with the installation token (verify access)

Environment variables required (set as repository secrets or in workflow env):
- APP_ID: numeric GitHub App ID
- APP_PRIVATE_KEY: PEM private key content (multi-line)
- GITHUB_REPOSITORY: owner/repo (provided by Actions)
- OPENAI_API_KEY: optional, if you will call OpenAI

This script intentionally prints status codes and responses for debugging.
"""

import os
import time
import jwt  # PyJWT
import requests
import sys

OWNER_REPO = os.getenv("GITHUB_REPOSITORY")  # e.g. "wisnu94/Forex-Auto-Trader-Pro"
APP_ID = os.getenv("APP_ID")
APP_PRIVATE_KEY = os.getenv("APP_PRIVATE_KEY")

if not OWNER_REPO or not APP_ID or not APP_PRIVATE_KEY:
    print("Missing one of required env vars: GITHUB_REPOSITORY, APP_ID, APP_PRIVATE_KEY")
    sys.exit(2)

try:
    owner, repo = OWNER_REPO.split("/")
except Exception:
    print("GITHUB_REPOSITORY is malformed. Expected 'owner/repo'.")
    sys.exit(2)

# 1) Create JWT for app authentication (RS256)
now = int(time.time())
payload = {
    "iat": now - 60,
    "exp": now + (9 * 60),  # max 10 minutes
    "iss": APP_ID
}

# APP_PRIVATE_KEY must be the PEM content. PyJWT in newer versions returns a str for encode.
try:
    jwt_token = jwt.encode(payload, APP_PRIVATE_KEY, algorithm="RS256")
except Exception as e:
    print("Failed to create JWT:", e)
    sys.exit(3)

headers_app = {
    "Authorization": f"Bearer {jwt_token}",
    "Accept": "application/vnd.github+json"
}

# 2) Get installation id for this repo
url_install = f"https://api.github.com/repos/{owner}/{repo}/installation"
print("GET", url_install)
r = requests.get(url_install, headers=headers_app)
print("->", r.status_code)
if r.status_code != 200:
    print("Failed to get installation info. Response:", r.status_code, r.text)
    sys.exit(3)
installation = r.json()
installation_id = installation.get("id")
print("installation_id:", installation_id)

# 3) Create installation access token
url_token = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
print("POST", url_token)
r2 = requests.post(url_token, headers=headers_app)
print("->", r2.status_code)
if r2.status_code != 201:
    print("Failed to create installation token. Response:", r2.status_code, r2.text)
    sys.exit(4)
inst_token = r2.json().get("token")
print("Got installation token (length):", len(inst_token) if inst_token else 0)

# 4) Use installation token to call repo API
headers_inst = {
    "Authorization": f"token {inst_token}",
    "Accept": "application/vnd.github+json"
}
url_repo = f"https://api.github.com/repos/{owner}/{repo}"
r3 = requests.get(url_repo, headers=headers_inst)
print("GET", url_repo, "->", r3.status_code)
try:
    print(r3.json())
except Exception:
    print("Response not JSON or empty body")

if r3.status_code != 200:
    print("Install token could not access repo; check App permissions and installation scope.")
    sys.exit(5)

print("Success: installation token can access repo.")
