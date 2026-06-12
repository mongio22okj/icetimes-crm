"""Commit all uncommitted/untracked changes to mongio22okj/icetimes-crm via
the GitHub Trees API in a single commit. Token read from GH_TOKEN env var.

Single-file commits via the Contents API are simple but limited; for
multi-file edits this uses the Git Data API: blob → tree → commit → update
ref. Lets us push a feature in one atomic commit without the local Git
Credential Manager.
"""
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

TOKEN = os.environ["GH_TOKEN"]
REPO = os.environ.get("GH_REPO", "mongio22okj/icetimes-crm")
BRANCH = os.environ.get("GH_BRANCH", "main")
MESSAGE = os.environ.get("GH_MESSAGE", "chore: batch update via API")


def api(method, url, body=None):
    req = urllib.request.Request(
        f"https://api.github.com{url}", method=method,
        data=json.dumps(body).encode() if body else None,
    )
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def changed_files():
    """Return list of (path, is_deleted) for all changes; skip renames."""
    out = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "-z"]
    ).decode("utf-8", errors="replace")
    files = []
    for entry in out.split("\x00"):
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        if status.startswith("R"):
            continue  # skip renames
        is_deleted = "D" in status
        files.append((path, is_deleted))
    return files


def main():
    files = changed_files()
    if not files:
        print("No changes.")
        return 0
    print(f"Committing {len(files)} files:")
    for path, deleted in files:
        prefix = "DEL" if deleted else " + "
        print(f"  {prefix} {path}")

    # 1. Current ref → commit SHA.
    _, ref = api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    parent_sha = ref["object"]["sha"]
    _, parent_commit = api("GET", f"/repos/{REPO}/git/commits/{parent_sha}")
    base_tree = parent_commit["tree"]["sha"]

    # 2. Upload each file as a blob (or mark for deletion).
    tree_items = []
    for path, deleted in files:
        if deleted:
            # Setting sha=None on a tree entry deletes it from the new tree.
            tree_items.append({
                "path": path.replace("\\", "/"),
                "mode": "100644",
                "type": "blob",
                "sha": None,
            })
            continue
        with open(path, "rb") as f:
            content = f.read()
        status, blob = api("POST", f"/repos/{REPO}/git/blobs", {
            "content": base64.b64encode(content).decode(),
            "encoding": "base64",
        })
        if status not in (200, 201):
            print(f"blob failed for {path}: {blob}")
            return 1
        tree_items.append({
            "path": path.replace("\\", "/"),
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"],
        })

    # 3. Create tree from parent + new blobs.
    status, tree = api("POST", f"/repos/{REPO}/git/trees", {
        "base_tree": base_tree,
        "tree": tree_items,
    })
    if status not in (200, 201):
        print(f"tree failed: {tree}")
        return 1

    # 4. Commit.
    status, commit = api("POST", f"/repos/{REPO}/git/commits", {
        "message": MESSAGE,
        "tree": tree["sha"],
        "parents": [parent_sha],
    })
    if status not in (200, 201):
        print(f"commit failed: {commit}")
        return 1

    # 5. Move branch ref.
    status, _ = api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {
        "sha": commit["sha"],
        "force": False,
    })
    if status not in (200, 201):
        print(f"ref update failed")
        return 1

    print(f"Commit: {commit['sha'][:10]}")
    print(f"URL: {commit['html_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
