#!/usr/bin/env python3
"""Build the sandbox repository used to verify git history purging.

Everything created here is dummy data:
  * a tiny stdlib-only web API with config, tests and docs
  * ~100 commits across main / develop / version/* / feature/* / stg branches
  * merge commits that model a develop -> version/x -> main release flow
  * lightweight and annotated tags, some SSH-signed commits and one signed tag
  * fake secrets in made-up formats (never real provider formats)

Fresh random secret values are generated on every run and written ONLY to
<workdir>/planted.json, which must never be committed or pushed.

Usage:
  build_sandbox.py --workdir ~/purge-verify-work [--remote <git url>] [--push]

--push does a two-phase force push:
  phase A: develop (before the PR merges) + the two PR branches that will be
           merged, so the PRs can be opened while they are still unmerged
  phase B: everything (all branches and tags); stale remote branches are deleted
github_setup.sh opens the PRs between the two phases.
"""
import argparse
import base64
import gzip
import json
import os
import secrets
import shutil
import string
import subprocess
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

AUTHORS = [
    ("Dev Alpha", "dev-alpha@users.noreply.example.invalid"),
    ("Dev Beta", "dev-beta@users.noreply.example.invalid"),
    ("Dev Gamma", "dev-gamma@users.noreply.example.invalid"),
]
RELEASE_BOT = ("Release Bot", "release-bot@users.noreply.example.invalid")

ALNUM = string.ascii_letters + string.digits


# --------------------------------------------------------------------------
# fake secret formats (made up on purpose; see .gitleaks.toml)
# --------------------------------------------------------------------------
def fake_cloud_key():
    return "FAKESECRET_" + "".join(secrets.choice(ALNUM) for _ in range(32))


def fake_webhook_token():
    return "fakekey-" + secrets.token_hex(32)


def fake_db_password():
    # contains characters that change under URL encoding
    pool = ALNUM + "+/=@!"
    body = [secrets.choice(pool) for _ in range(17)]
    for ch in "+/@":  # guarantee at least these specials
        body.insert(secrets.randbelow(len(body) + 1), ch)
    return "FAKEPW-" + "".join(body)


def fake_client_secret():
    # prefix-less value: only detectable from its key name
    return "".join(secrets.choice(ALNUM) for _ in range(40))


def fake_key_block():
    raw = secrets.token_bytes(144)
    b64 = base64.b64encode(raw).decode()
    lines = [b64[i:i + 64] for i in range(0, len(b64), 64)]
    body = "\n".join(lines)
    return body, "-----BEGIN FAKE DUMMY KEY-----\n" + body + "\n-----END FAKE DUMMY KEY-----\n"


# --------------------------------------------------------------------------
class Repo:
    def __init__(self, path: Path, signing_key: Path):
        self.path = path
        self.signing_key = signing_key
        self.clock = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)
        self.author_idx = 0
        self.env = dict(os.environ)
        # keep the operator's personal git config out of the sandbox
        self.env["GIT_CONFIG_GLOBAL"] = "/dev/null"
        self.env["GIT_CONFIG_NOSYSTEM"] = "1"
        self.commit_count = 0

    def git(self, *args, check=True, capture=True, sign=False, who=None):
        env = dict(self.env)
        name, email = who or AUTHORS[self.author_idx % len(AUTHORS)]
        date = self.clock.strftime("%Y-%m-%dT%H:%M:%S%z")
        env.update(GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email,
                   GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=email,
                   GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        pre = ["git", "-C", str(self.path)]
        if sign:
            pre += ["-c", "gpg.format=ssh", "-c", f"user.signingkey={self.signing_key}"]
        r = subprocess.run(pre + list(args), env=env, text=True,
                           capture_output=capture)
        if check and r.returncode != 0:
            sys.exit(f"git {' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
        return (r.stdout or "").strip()

    def tick(self, hours=5):
        self.clock += timedelta(hours=hours)
        self.author_idx += 1

    def write(self, rel, content, mode="w"):
        p = self.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)

    def append(self, rel, content):
        p = self.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(content)

    def rm(self, rel):
        self.git("rm", "-q", "-r", rel)

    def commit(self, msg, sign=False, who=None):
        self.tick()
        self.git("add", "-A")
        args = ["commit", "-q", "-m", msg]
        if sign:
            args.insert(1, "-S")
        self.git(*args, sign=sign, who=who)
        self.commit_count += 1
        return self.git("rev-parse", "HEAD")

    def checkout(self, branch, start=None):
        if start:
            self.git("checkout", "-q", "-B", branch, start)
        else:
            self.git("checkout", "-q", branch)

    def merge(self, branch, msg, sign=False, who=None):
        self.tick(2)
        args = ["merge", "--no-ff", "-q", "-m", msg, branch]
        if sign:
            args.insert(1, "-S")
        self.git(*args, sign=sign, who=who)
        self.commit_count += 1
        return self.git("rev-parse", "HEAD")

    def tag(self, name, ref="HEAD", annotated=False, sign=False, msg=None):
        self.tick(1)
        if annotated:
            args = ["tag", "-a", name, "-m", msg or name, ref]
            if sign:
                args = ["tag", "-s", name, "-m", msg or name, ref]
            self.git(*args, sign=sign, who=RELEASE_BOT)
        else:
            self.git("tag", name, ref)


# --------------------------------------------------------------------------
# app content generators
# --------------------------------------------------------------------------
APP_SERVER = '''"""Tiny stdlib-only JSON API used as dummy content."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from app import handlers

ROUTES = {}


def route(path):
    def deco(fn):
        ROUTES[path] = fn
        return fn
    return deco


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        fn = ROUTES.get(self.path) or getattr(handlers, "ROUTES", {}).get(self.path)
        if fn is None:
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(fn()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


@route("/health")
def health():
    return {"status": "ok"}


def main(port=8080):
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
'''

AUTH_PY = '''"""Password helpers. Note: the word "password" appears a lot on purpose."""
import hashlib
import hmac
import os


def password_hash(password: str, salt: bytes = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + digest.hex()


def check_password(password: str, stored: str) -> bool:
    salt_hex, _ = stored.split(":")
    return hmac.compare_digest(password_hash(password, bytes.fromhex(salt_hex)), stored)


def is_weak_password(password: str) -> bool:
    return len(password) < 12 or password.lower() in {"password", "changeme"}
'''

TEST_AUTH = '''from app.auth import check_password, is_weak_password, password_hash


def test_password_roundtrip():
    stored = password_hash("correct horse battery staple")
    assert check_password("correct horse battery staple", stored)


def test_weak_password():
    assert is_weak_password("password")
'''


def handlers_header():
    return '"""Feature handlers (dummy)."""\nROUTES = {}\n'


def handler_block(i, name):
    return (f"\n\ndef {name}():\n    return {{\"feature\": \"{name}\", \"n\": {i}}}\n\n"
            f"ROUTES[\"/{name.replace('_', '-')}\"] = {name}\n")


def test_block(name):
    return (f"\n\ndef test_{name}():\n    from app import handlers\n"
            f"    assert handlers.{name}()[\"feature\"] == \"{name}\"\n")


FEATURE_NAMES = [
    "list_items", "get_item", "create_item", "update_item", "delete_item",
    "list_users", "get_user", "search_items", "export_csv", "import_csv",
    "list_orders", "get_order", "cancel_order", "list_tags", "add_tag",
    "remove_tag", "stats_daily", "stats_weekly", "audit_log", "feature_flags",
    "list_projects", "get_project", "archive_project", "list_comments", "add_comment",
    "notify_users", "list_webhooks", "rotate_tokens", "list_sessions", "end_session",
    "list_regions", "get_region", "quota_usage", "billing_preview", "list_reports",
    "get_report", "schedule_report", "list_jobs", "retry_job", "cancel_job",
]


def notebook(secret_value):
    nb = {
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": ["# Explore dummy data\n"]},
            {"cell_type": "code", "execution_count": 1, "metadata": {},
             "source": ["from config import settings\n", "print(settings.ANALYTICS_KEY)\n"],
             "outputs": [{"name": "stdout", "output_type": "stream",
                          "text": [secret_value + "\n"]}]},
        ],
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "nbformat": 4, "nbformat_minor": 5,
    }
    return json.dumps(nb, indent=1) + "\n"


# --------------------------------------------------------------------------
def build(workdir: Path):
    sandbox = workdir / "sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True)

    keydir = workdir / "keys"
    keydir.mkdir(exist_ok=True)
    signing_key = keydir / "signing_ed25519"
    if not signing_key.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "sandbox-signing",
                        "-f", str(signing_key)], check=True)
    pub = (keydir / "signing_ed25519.pub").read_text().split()
    allowed = keydir / "allowed_signers"
    allowed.write_text("".join(f"{e} namespaces=\"git\" {pub[0]} {pub[1]}\n"
                               for _, e in AUTHORS + [RELEASE_BOT]))

    # ---- secrets ----
    S = {
        "CLOUD_KEY": fake_cloud_key(),
        "WEBHOOK_TOKEN": fake_webhook_token(),
        "DB_PASSWORD": fake_db_password(),
        "SESSION_SECRET": fake_cloud_key(),
        "LEGACY_EXPORT_KEY": fake_cloud_key(),
        "STG_TOKEN": fake_webhook_token(),
        "B64_SECRET": fake_cloud_key(),
        "CLIENT_SECRET": fake_client_secret(),
        "NOTEBOOK_KEY": fake_cloud_key(),
        "BINARY_KEY": fake_cloud_key(),
        "PR_TEXT_KEY": fake_cloud_key(),
        "PR_B_KEY": fake_webhook_token(),
    }
    key_body, key_file = fake_key_block()
    S["KEY_FILE_BODY"] = key_body
    S["SHORT_PASSWORD"] = "password"
    db_pw_url = urllib.parse.quote(S["DB_PASSWORD"], safe="")
    b64_value = base64.b64encode(S["B64_SECRET"].encode()).decode()

    r = Repo(sandbox, signing_key)
    r.git("init", "-q", "-b", "main")
    r.git("config", "user.name", "Sandbox Builder")
    r.git("config", "user.email", "sandbox-builder@users.noreply.example.invalid")
    r.git("config", "gpg.ssh.allowedSignersFile", str(allowed))
    r.git("config", "commit.gpgsign", "false")

    marks = {}

    # ---------------- root ----------------
    r.write("README.md", "# Dummy Inventory API\n\nA tiny dummy web API used as test content.\n")
    r.write(".gitignore", "__pycache__/\n*.pyc\n")
    marks["root"] = r.commit("Initial commit", sign=True)

    # ---------------- develop ----------------
    r.checkout("develop", "main")
    r.write("app/__init__.py", "")
    r.write("app/server.py", APP_SERVER)
    r.commit("Add minimal HTTP server")
    r.write("app/handlers.py", handlers_header())
    r.write("tests/__init__.py", "")
    r.write("tests/test_handlers.py", "")
    r.commit("Add handler registry")
    r.write("app/auth.py", AUTH_PY)
    r.write("tests/test_auth.py", TEST_AUTH)
    r.commit("Add password hashing helpers", sign=True)

    # CLOUD_KEY lands in several files (same value in multiple files)
    r.write("config/__init__.py", "")
    r.write("config/settings.py",
            "\"\"\"App settings (dummy).\"\"\"\n"
            f"CLOUD_ACCESS_KEY = \"{S['CLOUD_KEY']}\"\n"
            "REGION = \"region-1\"\n")
    marks["cloud_key_added"] = r.commit("Add settings with cloud access key")
    r.write("scripts/deploy.sh",
            "#!/bin/sh\n# dummy deploy script\n"
            f"export CLOUD_ACCESS_KEY={S['CLOUD_KEY']}\n"
            "echo deploying...\n")
    r.write("docs/setup.md",
            "# Setup\n\nSet the cloud access key:\n\n"
            f"    CLOUD_ACCESS_KEY={S['CLOUD_KEY']}\n")
    r.commit("Add deploy script and setup docs")

    # .env (whole-file removal target) with raw DB password + session secret
    r.write(".env",
            f"DB_PASSWORD={S['DB_PASSWORD']}\n"
            f"SESSION_SECRET={S['SESSION_SECRET']}\n")
    marks["env_added"] = r.commit("Add local .env")
    r.write("config/database.py",
            "\"\"\"Database settings (dummy).\"\"\"\n"
            f"DATABASE_URL = \"mysql://dummy:{db_pw_url}@db.example.invalid/app\"\n")
    r.commit("Add database DSN")

    # webhook token (later removed from code)
    r.write("app/notify.py",
            "\"\"\"Send notifications to a chat tool webhook (dummy).\"\"\"\n"
            f"WEBHOOK_URL = \"https://chat.example.invalid/hooks/{S['WEBHOOK_TOKEN']}\"\n\n\n"
            "def notify(text):\n    return {\"url\": WEBHOOK_URL, \"text\": text}\n")
    marks["webhook_added"] = r.commit("Add chat notifications", sign=True)

    # key file (whole-file removal target, stays at HEAD)
    r.write("certs/server.fakekey", key_file)
    r.commit("Add server key for local TLS testing")

    # short value collision
    r.write("config/admin.py",
            "\"\"\"Admin bootstrap settings (dummy).\"\"\"\n"
            "ADMIN_USER = \"admin\"\n"
            "ADMIN_PASSWORD = \"password\"\n")
    r.commit("Add admin bootstrap settings")

    # feature filler commits
    fi = 0

    def add_features(n, sign_every=0):
        nonlocal fi
        for _ in range(n):
            name = FEATURE_NAMES[fi % len(FEATURE_NAMES)]
            if fi >= len(FEATURE_NAMES):
                name = f"{name}_v{fi // len(FEATURE_NAMES) + 1}"
            r.append("app/handlers.py", handler_block(fi, name))
            r.append("tests/test_handlers.py", test_block(name))
            fi += 1
            r.commit(f"Add {name.replace('_', ' ')} endpoint",
                     sign=bool(sign_every) and fi % sign_every == 0)

    add_features(10, sign_every=3)

    # feature/search: branched, a few commits, abandoned (stale)
    r.checkout("feature/search", "develop")
    r.write("app/search.py", "def search(q):\n    return []\n")
    r.commit("WIP: search module")
    r.append("app/search.py", "\n\ndef rank(items):\n    return items\n")
    r.commit("WIP: ranking")
    r.checkout("develop")

    # base64 / split json / notebook / binary
    r.write("deploy/secret.yaml",
            "apiVersion: v1\nkind: Secret\nmetadata:\n  name: app-secret\ntype: Opaque\ndata:\n"
            f"  token: {b64_value}\n")
    r.commit("Add deployment secret manifest")
    r.write("config/clients.json",
            "{\n  \"clients\": [\n    {\n      \"name\": \"batch-worker\",\n      \"client_secret\":\n"
            f"        \"{S['CLIENT_SECRET']}\"\n    }}\n  ]\n}}\n")
    r.commit("Add client registry")
    r.append("config/settings.py", f"ANALYTICS_KEY = \"{S['NOTEBOOK_KEY']}\"\n")
    r.write("notebooks/explore.ipynb", notebook(S["NOTEBOOK_KEY"]))
    r.commit("Add exploration notebook")
    blob = bytearray(secrets.token_bytes(512))
    blob[200:200] = b"\x00KEY=" + S["BINARY_KEY"].encode() + b"\x00"
    r.write("assets/model.bin", bytes(blob))
    fixtures = json.dumps({"service_key": S["BINARY_KEY"], "rows": list(range(20))}).encode()
    r.write("data/fixtures.json.gz", gzip.compress(fixtures, mtime=0))
    r.commit("Add model blob and compressed fixtures")

    add_features(8, sign_every=4)
    r.write("app/version.py", "VERSION = \"0.9.0\"\n")
    r.commit("Add version module")

    # ---------------- release 1.0 ----------------
    r.checkout("version/1.0", "main")
    marks["v10_merge"] = r.merge("develop", "Merge branch 'develop' into version/1.0", sign=True)
    r.write("app/version.py", "VERSION = \"1.0.0\"\n")
    r.commit("Bump version to 1.0.0", sign=True, who=RELEASE_BOT)
    r.tag("v1.0.0", annotated=True, msg="Release 1.0.0")
    r.checkout("main")
    r.merge("version/1.0", "Merge branch 'version/1.0'", who=RELEASE_BOT)

    # hotfix/old-config: branched while WEBHOOK_TOKEN still in code; tip keeps it
    r.checkout("hotfix/old-config", "develop")
    r.append("app/notify.py", "\n# TODO: retry on failure\n")
    r.commit("Add retry TODO to notifier")

    # feature/legacy-export: stale branch whose tip alone holds LEGACY_EXPORT_KEY
    r.checkout("feature/legacy-export", "develop")
    r.write("app/export.py", "def export_all():\n    return []\n")
    r.commit("WIP: legacy export")
    r.write("config/export.py", f"EXPORT_API_KEY = \"{S['LEGACY_EXPORT_KEY']}\"\n")
    r.commit("WIP: export credentials")

    # develop continues: move webhook token & .env out of the code
    r.checkout("develop")
    r.write("app/notify.py",
            "\"\"\"Send notifications to a chat tool webhook (dummy).\"\"\"\nimport os\n\n"
            "WEBHOOK_URL = os.environ.get(\"WEBHOOK_URL\", \"\")\n\n\n"
            "def notify(text):\n    return {\"url\": WEBHOOK_URL, \"text\": text}\n")
    marks["webhook_removed"] = r.commit("Read webhook URL from environment")
    r.rm(".env")
    r.write(".env.example", "DB_PASSWORD=\nSESSION_SECRET=\n")
    r.append(".gitignore", ".env\n")
    marks["env_removed"] = r.commit("Remove .env from the repository")

    # stg: tip-only STG_TOKEN
    r.checkout("stg", "develop")
    r.write("config/stg.py", f"STG_WEBHOOK_TOKEN = \"{S['STG_TOKEN']}\"\n")
    r.commit("stg: environment overrides")
    r.checkout("develop")

    add_features(7)

    # hotfix on version/1.0 -> v1.0.1 (lightweight tag), merged to main and develop
    r.checkout("version/1.0")
    r.write("docs/known-issues.md", "# Known issues\n\n- Fixed: health endpoint content type.\n")
    r.commit("Fix: document health endpoint content type")
    r.write("app/version.py", "VERSION = \"1.0.1\"\n")
    r.commit("Bump version to 1.0.1", sign=True, who=RELEASE_BOT)
    r.tag("v1.0.1")  # lightweight
    r.checkout("main")
    r.merge("version/1.0", "Merge branch 'version/1.0'", who=RELEASE_BOT)
    r.checkout("develop")
    r.merge("version/1.0", "Merge branch 'version/1.0' into develop")

    add_features(8, sign_every=3)

    # gitleaks config + CI workflows (no secret values in them)
    gl = (Path(__file__).resolve().parent.parent / "gitleaks" / "gitleaks.toml").read_text()
    r.write(".gitleaks.toml", gl)
    wf_dir = Path(__file__).resolve().parent / "workflows"
    r.write(".github/workflows/secret-scan.yml", (wf_dir / "secret-scan.yml").read_text())
    r.write(".github/workflows/print-config.yml", (wf_dir / "print-config.yml").read_text())
    r.commit("Add CI: secret scan and config print")

    add_features(6)

    # PR branches that will be merged via PR (merged PR #1, #2)
    marks["develop_pre_pr_merge"] = r.git("rev-parse", "develop")
    r.checkout("feature/healthcheck", "develop")
    r.write("app/healthcheck.py", "def deep_health():\n    return {\"db\": \"ok\"}\n")
    r.commit("Add deep health check")
    r.append("app/healthcheck.py", "\n\ndef ready():\n    return True\n")
    r.commit("Add readiness probe")
    r.checkout("feature/logging", "develop")
    r.write("app/logging_setup.py", "import logging\n\nlogging.basicConfig(level=logging.INFO)\n")
    r.commit("Add logging setup")
    r.checkout("develop")
    r.merge("feature/healthcheck", "Merge pull request from feature/healthcheck")
    r.merge("feature/logging", "Merge pull request from feature/logging")

    add_features(6)

    # ---------------- release 1.1 ----------------
    r.checkout("version/1.1", "main")
    r.merge("develop", "Merge branch 'develop' into version/1.1", sign=True)
    r.write("app/version.py", "VERSION = \"1.1.0\"\n")
    r.commit("Bump version to 1.1.0", sign=True, who=RELEASE_BOT)
    r.tag("v1.1.0", annotated=True, sign=True, msg="Release 1.1.0")
    r.checkout("main")
    r.merge("version/1.1", "Merge branch 'version/1.1'", who=RELEASE_BOT)

    # develop after 1.1 (so version/1.1..develop is non-empty)
    r.checkout("develop")
    add_features(6, sign_every=2)
    r.write("docs/api.md", "# API\n\nSee app/handlers.py for the list of endpoints.\n")
    r.commit("Document API endpoints")

    # ---------------- open PR branches ----------------
    # PR A: normal feature on develop (its own commits contain no secret)
    r.checkout("feature/rate-limit", "develop")
    r.write("app/ratelimit.py", "LIMIT = 100\n\n\ndef allow(n):\n    return n < LIMIT\n")
    r.commit("Add rate limiter")
    r.append("app/ratelimit.py", "\n\ndef reset():\n    return 0\n")
    r.commit("Add rate limiter reset")
    # PR B: adds CLOUD_KEY to another file + its own new token
    r.checkout("feature/metrics", "develop")
    r.write("config/metrics.py",
            f"METRICS_CLOUD_KEY = \"{S['CLOUD_KEY']}\"\n"
            f"METRICS_PUSH_TOKEN = \"{S['PR_B_KEY']}\"\n")
    r.commit("Add metrics exporter config")
    r.write("app/metrics.py", "def collect():\n    return {}\n")
    r.commit("Add metrics collector")
    # PR C: branched from the root commit; nothing in it is rewritten
    r.checkout("docs/contributing", marks["root"])
    r.write("CONTRIBUTING.md", "# Contributing\n\nOpen a pull request against develop.\n")
    r.commit("Add contributing guide")

    r.checkout("main")
    r.git("gc", "-q")

    total = int(r.git("rev-list", "--all", "--count"))
    planted = {
        "_warning": "LOCAL ONLY. Never commit or push this file.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "values": S,
        "derived": {
            "DB_PASSWORD_urlencoded": db_pw_url,
            "B64_SECRET_base64": b64_value,
        },
        "items": [
            {"id": "CLOUD_KEY", "kind": "HEAD + multiple files + multiple branches",
             "where": ["config/settings.py", "scripts/deploy.sh", "docs/setup.md",
                       "config/metrics.py (open PR branch feature/metrics)",
                       "printed by Actions workflow print-config"]},
            {"id": "WEBHOOK_TOKEN", "kind": "removed from code; history only on main/develop",
             "where": ["app/notify.py (history)", "tip of hotfix/old-config"]},
            {"id": "DB_PASSWORD", "kind": "raw in deleted .env; URL-encoded at HEAD",
             "where": [".env (history, raw)", "config/database.py (HEAD, URL-encoded)"]},
            {"id": "SESSION_SECRET", "kind": "whole file removal (.env)", "where": [".env (history)"]},
            {"id": "KEY_FILE_BODY", "kind": "whole file removal (fake key file, still at HEAD)",
             "where": ["certs/server.fakekey"]},
            {"id": "LEGACY_EXPORT_KEY", "kind": "tip of stale branch only",
             "where": ["config/export.py on feature/legacy-export"]},
            {"id": "STG_TOKEN", "kind": "tip of stale branch only", "where": ["config/stg.py on stg"]},
            {"id": "B64_SECRET", "kind": "only stored base64-encoded", "where": ["deploy/secret.yaml"]},
            {"id": "CLIENT_SECRET", "kind": "JSON key and value on separate lines",
             "where": ["config/clients.json"]},
            {"id": "NOTEBOOK_KEY", "kind": ".ipynb output cell + settings",
             "where": ["notebooks/explore.ipynb", "config/settings.py"]},
            {"id": "BINARY_KEY", "kind": "inside binary files",
             "where": ["assets/model.bin (raw bytes)", "data/fixtures.json.gz (gzip)"]},
            {"id": "SHORT_PASSWORD", "kind": "short value equal to a common word",
             "where": ["config/admin.py"]},
            {"id": "PR_TEXT_KEY", "kind": "PR body and review comment only (not in git)",
             "where": ["PR body of feature/metrics", "review comment on feature/metrics"]},
            {"id": "PR_B_KEY", "kind": "open PR branch only", "where": ["config/metrics.py on feature/metrics"]},
        ],
        "marks": marks,
        "stats": {"total_commits_all_refs": total, "commits_created": r.commit_count},
    }
    (workdir / "planted.json").write_text(json.dumps(planted, indent=2) + "\n")
    os.chmod(workdir / "planted.json", 0o600)
    print(f"sandbox built at {sandbox}: {total} commits reachable from all refs")
    print(f"planted values written to {workdir / 'planted.json'} (local only)")
    return sandbox, marks


def push(workdir: Path, remote: str):
    sandbox = workdir / "sandbox"
    planted = json.loads((workdir / "planted.json").read_text())
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")

    def g(*a, check=True):
        r = subprocess.run(["git", "-C", str(sandbox)] + list(a), env=env, text=True,
                           capture_output=True)
        print(r.stdout + r.stderr, end="")
        if check and r.returncode != 0:
            sys.exit(f"git {' '.join(a)} failed")
        return r.stdout

    g("remote", "remove", "origin", check=False)
    g("remote", "add", "origin", remote)
    phase = os.environ.get("PUSH_PHASE", "B")
    if phase == "A":
        pre = planted["marks"]["develop_pre_pr_merge"]
        g("push", "--force", "origin",
          f"{pre}:refs/heads/develop",
          "refs/heads/main:refs/heads/main",
          "refs/heads/feature/healthcheck:refs/heads/feature/healthcheck",
          "refs/heads/feature/logging:refs/heads/feature/logging")
        return
    # phase B: everything; delete remote branches/tags we do not have
    g("push", "--force", "origin", "refs/heads/*:refs/heads/*", "refs/tags/*:refs/tags/*")
    local = set(g("for-each-ref", "--format=%(refname)", "refs/heads", "refs/tags").split())
    remote_refs = g("ls-remote", "--heads", "--tags", "origin").split("\n")
    stale = []
    for line in remote_refs:
        if not line.strip():
            continue
        ref = line.split("\t")[1]
        if ref.endswith("^{}"):
            continue
        if ref not in local:
            stale.append(":" + ref)
    if stale:
        print("deleting stale remote refs:", stale)
        g("push", "origin", *stale)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=str(Path.home() / "purge-verify-work"))
    ap.add_argument("--remote", default="git@github.com:euno7/git-history-deletion-verification.git")
    ap.add_argument("--push", action="store_true", help="push (PUSH_PHASE=A or B, default B)")
    ap.add_argument("--no-build", action="store_true", help="skip building (push existing sandbox)")
    a = ap.parse_args()
    workdir = Path(a.workdir).expanduser()
    workdir.mkdir(parents=True, exist_ok=True)
    if not a.no_build:
        build(workdir)
    if a.push:
        push(workdir, a.remote)


if __name__ == "__main__":
    main()
