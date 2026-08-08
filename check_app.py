#!/usr/bin/env python3
import os, time, sys, json
try:
    import jwt  # PyJWT
    import requests
except Exception as e:
    print("Missing Python deps. Run: pip install pyjwt[crypto] requests")
    sys.exit(1)

APP_ID = os.getenv("APP_ID")
APP_PRIVATE_KEY = os.getenv("APP_PRIVATE_KEY")
OWNER_REPO = os.getenv("GITHUB_REPOSITORY")  # e.g. "wisnu94/Forex-Auto-Trader-Pro"

if not APP_ID or not APP_PRIVATE_KEY or not OWNER_REPO:
    print("Missing env vars. Set APP_ID, APP_PRIVATE_KEY, and GITHUB_REPOSITORY.")
    sys.exit(1)

try:
    owner, repo = OWNER_REPO.split("/", 1)
except Exception:
    print("GITHUB_REPOSITORY is malformed. Expected 'owner/repo'.")
    sys.exit(1)

now = int(time.time())
payload = {"iat": now - 60, "exp": now + 9*60, "iss": APP_ID}
try:
    jwt_token = jwt.encode(payload, APP_PRIVATE_KEY, algorithm="RS256")
except Exception as e:
    print("Failed to create JWT:", e)
    sys.exit(2)

headers_app = {"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"}

# 1) installation info
url_install = f"https://api.github.com/repos/{owner}/{repo}/installation"
r = requests.get(url_install, headers=headers_app)
print("\nGET", url_install, "->", r.status_code)
try:
    print(json.dumps(r.json(), indent=2))
except:
    print(r.text)
if r.status_code != 200:
    print("STOP: cannot get installation for repo.")
    sys.exit(2)
installation_id = r.json().get("id")
print("installation_id:", installation_id)

# 2) create installation token
url_token = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
r2 = requests.post(url_token, headers=headers_app)
print("\nPOST", url_token, "->", r2.status_code)
try:
    j = r2.json()
    if isinstance(j, dict) and "token" in j:
        j2 = dict(j)
        j2["token"] = "<REDACTED>"
        print(json.dumps(j2, indent=2))
    else:
        print(json.dumps(j, indent=2))
except:
    print(r2.text)
if r2.status_code != 201:
    print("STOP: cannot create installation token.")
    sys.exit(3)

# 3) show permissions
permissions = r2.json().get("permissions")
print("\nToken permissions:", json.dumps(permissions, indent=2))

# 4) verify repo access with installation token
inst_token = r2.json().get("token")
headers_inst = {"Authorization": f"token {inst_token}", "Accept": "application/vnd.github+json"}
url_repo = f"https://api.github.com/repos/{owner}/{repo}"
r3 = requests.get(url_repo, headers=headers_inst)
print("\nGET", url_repo, "->", r3.status_code)
try:
    print(json.dumps(r3.json(), indent=2))
except:
    print(r3.text)
if r3.status_code != 200:
    print("Install token cannot access repo.")
    sys.exit(4)

print("\nOK: installation token can access repo.")