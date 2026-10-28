"""Owner-invoked local verification and exact-SHA fast-forward promotion.

No hosted CI, inferred approval, force pushes, rebases, or history rewriting.
Python standard library only, so the entrypoint needs no installed project deps.
"""

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import os
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET


class Refused(RuntimeError):
    pass


def git(root, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(root), *args], text=True, capture_output=True,
    )
    if check and result.returncode:
        raise Refused("Git command failed: " + " ".join(args[:2]) + "\n" + result.stderr.strip())
    return result


def clean(root):
    if git(root, "status", "--porcelain", "--untracked-files=all").stdout:
        raise Refused("Commit or set aside public working-tree changes first. Nothing was promoted.")


def check_history(root, sha):
    for commit in git(root, "rev-list", sha).stdout.splitlines():
        for name in git(root, "ls-tree", "-rz", "--name-only", commit).stdout.split("\0"):
            if not name:
                continue
            path = PurePosixPath(name)
            if (
                path.parts[0] in {"docs", ".superpowers", ".venv", ".worktrees"}
                or name in {"LEARNINGS.html", "LEARNINGS.md"}
                or path.name == ".env"
                or (path.name.startswith(".env.") and path.name != ".env.example")
            ):
                raise Refused("Private path exists in candidate history: " + name)


def remote_main(root):
    result = git(root, "ls-remote", "--exit-code", "origin", "refs/heads/main", check=False)
    if result.returncode == 2:
        return None
    if result.returncode:
        raise Refused("Cannot read origin/main; check remote access. Nothing was promoted.")
    git(root, "fetch", "--no-tags", "origin", "refs/heads/main")
    return git(root, "rev-parse", "FETCH_HEAD").stdout.strip()


def check_base(root, base, candidate):
    if base and git(root, "merge-base", "--is-ancestor", base, candidate, check=False).returncode:
        raise Refused("Candidate does not include origin/main. Integrate and verify again; no force push allowed.")


def passing_cases(report):
    try:
        cases = list(ET.parse(report).getroot().iter("testcase"))
    except (OSError, ET.ParseError) as error:
        raise Refused("Verification did not produce a readable pytest report.") from error
    if not cases or any(case.find(tag) is not None for case in cases for tag in ("failure", "error", "skipped")):
        raise Refused("Verification requires a nonempty passing suite with no skipped tests.")
    return len(cases)


def verify(root, candidate, logs):
    # Always build/import the snapshot, not an environment selected by the caller.
    environment = os.environ.copy()
    for key in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "UV_PROJECT", "PYTHONPATH"):
        environment.pop(key, None)
    report = logs / "pytest.xml"
    with tempfile.TemporaryDirectory(prefix="p01-verify-") as temporary:
        snapshot = Path(temporary) / "snapshot"
        git(root, "worktree", "add", "--detach", str(snapshot), candidate)
        try:
            with (logs / "verification.log").open("w") as output:
                for command in (
                    ["uv", "sync", "--frozen"],
                    ["uv", "run", "--frozen", "pytest", "-q", "--junitxml=" + str(report)],
                ):
                    output.write("$ " + " ".join(command) + "\n")
                    output.flush()
                    result = subprocess.run(command, cwd=snapshot, env=environment, stdout=output, stderr=subprocess.STDOUT)
                    if result.returncode:
                        raise Refused("Local verification failed; inspect " + str(logs / "verification.log"))
            count = passing_cases(report)
            clean(snapshot)
            return count
        finally:
            # Only remove the disposable worktree created by this invocation.
            git(root, "worktree", "remove", "--force", str(snapshot))


def main():
    if len(sys.argv) != 1:
        raise Refused("No automatic approval flags. Run: bash scripts/merge-local.sh")
    root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").stdout.strip())
    clean(root)
    candidate = git(root, "rev-parse", "HEAD").stdout.strip()
    check_history(root, candidate)
    if git(root, "check-ignore", "-q", ".superpowers/merges/probe", check=False).returncode:
        raise Refused("Ignore .superpowers/ before creating local verification records.")
    if not sys.stdin.isatty():
        raise Refused("Owner approval requires an interactive terminal; piped approval is refused.")
    base = remote_main(root)
    check_base(root, base, candidate)
    logs = root / ".superpowers" / "merges" / candidate / uuid.uuid4().hex
    logs.mkdir(parents=True)
    count = verify(root, candidate, logs)
    clean(root)
    if git(root, "rev-parse", "HEAD").stdout.strip() != candidate:
        raise Refused("HEAD moved during verification; rerun for the new commit.")
    action = "merge" if base else "create main"
    phrase = action + " " + candidate
    print("Verified commit:", candidate, flush=True)
    print("Passing tests:", count, "| Local records:", logs, flush=True)
    if base is None:
        print("origin/main does not exist. This explicitly creates it at the verified commit.", flush=True)
    print("Review the commit and evidence. Agents must not supply approval on the owner's behalf.", flush=True)
    try:
        approval = input("Type exactly '" + phrase + "' to push, or anything else to cancel: ")
    except EOFError as error:
        raise Refused("Approval cancelled; nothing was promoted.") from error
    if approval != phrase:
        raise Refused("Approval declined or did not name the verified SHA. Nothing was promoted.")
    clean(root)
    if git(root, "rev-parse", "HEAD").stdout.strip() != candidate:
        raise Refused("HEAD changed after verification; approval is no longer usable.")
    current = remote_main(root)
    if current != base:
        raise Refused("origin/main changed during verification/approval. Rerun; nothing was promoted.")
    check_base(root, current, candidate)
    # Normal Git fast-forward checks reject a concurrent divergent remote update.
    # There is no force/lease override, merge commit, or bypass of branch rules.
    git(root, "push", "origin", candidate + ":refs/heads/main")
    if remote_main(root) != candidate:
        raise Refused("Remote main is no longer the verified SHA; inspect concurrent remote activity.")
    (logs / "promotion.txt").write_text(
        "Verified and owner-confirmed: " + candidate + "\n"
        + "Action: " + action + "\n"
        + "Observed remote main: " + candidate + "\n"
        + "Time (UTC): " + datetime.now(timezone.utc).isoformat() + "\n"
    )
    print("origin/main now points to verified commit " + candidate)


if __name__ == "__main__":
    try:
        main()
    except (Refused, OSError, KeyboardInterrupt) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
