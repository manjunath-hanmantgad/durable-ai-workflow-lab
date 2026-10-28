"""Exercise real Git promotion only against disposable local bare remotes.

The package manager is the external boundary: its test double emits controlled
pytest reports. No test supplies approval to GitHub or to the actual repository.
"""

import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import time

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "merge-local.sh"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()


@pytest.fixture
def sandbox(tmp_path):
    repo, remote = tmp_path / "project", tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "feature", str(repo)], check=True, capture_output=True)
    for key, value in (("user.name", "Local Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false")):
        git(repo, "config", key, value)
    (repo / ".gitignore").write_text(".superpowers/\n.venv/\n__pycache__/\n.pytest_cache/\n")
    (repo / "example.txt").write_text("base\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "origin", "HEAD:refs/heads/main")
    (repo / "example.txt").write_text("candidate\n")
    git(repo, "add", "example.txt")
    git(repo, "commit", "-m", "candidate")
    head = git(repo, "rev-parse", "HEAD")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(f"#!{sys.executable}\n" + '''import os, pathlib, subprocess, sys
args = sys.argv[1:]
if os.environ.get("TEST_CHECK_ENV") and any(key in os.environ for key in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "UV_PROJECT", "PYTHONPATH")):
    sys.exit(7)
mode = os.environ.get("TEST_VERIFY_MODE", "pass")
if "pytest" in args:
    if mode == "fail": sys.exit(1)
    report = next(a.split("=", 1)[1] for a in args if a.startswith("--junitxml="))
    cases = "" if mode == "empty" else '<testcase name="example">' + ('<skipped />' if mode == "skip" else '') + '</testcase>'
    pathlib.Path(report).write_text('<testsuites><testsuite>' + cases + '</testsuite></testsuites>')
    if mode == "dirty_snapshot": pathlib.Path("example.txt").write_text("modified by tests")
    if mode == "advance":
        subprocess.run(["git", "--git-dir=" + os.environ["TEST_REMOTE"], "update-ref", "refs/heads/main", os.environ["TEST_NEW_MAIN"]], check=True)
print("controlled verifier result")
''')
    uv.chmod(0o755)
    env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "TEST_REMOTE": str(remote)}
    return repo, remote, base, head, env


def run_interactive(repo, env, approval):
    assert SCRIPT.exists(), "Local merge command is not implemented"
    master, slave = pty.openpty()
    process = subprocess.Popen(["bash", str(SCRIPT)], cwd=repo, env=env, stdin=slave, stdout=slave, stderr=slave)
    os.close(slave)
    chunks, sent = [], False
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], .1)
            if ready:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                chunks.append(data)
                if not sent and b"Type exactly" in b"".join(chunks):
                    os.write(master, (approval + "\n").encode())
                    sent = True
            elif process.poll() is not None:
                break
        else:
            pytest.fail("Local merge command did not finish")
        return process.wait(timeout=5), b"".join(chunks).decode(errors="replace"), sent
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)


def remote_main(remote):
    return git(remote, "rev-parse", "refs/heads/main")


def test_exact_approval_pushes_only_the_verified_commit(sandbox):
    repo, remote, _, head, env = sandbox
    code, output, prompted = run_interactive(repo, env, f"merge {head}")
    assert code == 0, output
    assert prompted
    assert remote_main(remote) == head
    assert (repo / ".superpowers" / "merges" / head).is_dir()
    assert len(git(repo, "worktree", "list", "--porcelain").split("worktree ")) == 2


def test_new_main_requires_explicit_bootstrap_approval(sandbox):
    repo, remote, _, head, env = sandbox
    git(remote, "update-ref", "-d", "refs/heads/main")
    code, output, _ = run_interactive(repo, env, f"create main {head}")
    assert code == 0, output
    assert remote_main(remote) == head


@pytest.mark.parametrize("approval", ["no", "merge " + "0" * 40])
def test_declined_or_mismatched_approval_never_pushes(sandbox, approval):
    repo, remote, base, _, env = sandbox
    code, output, prompted = run_interactive(repo, env, approval)
    assert code != 0, output
    assert prompted
    assert remote_main(remote) == base


@pytest.mark.parametrize("mode", ["fail", "empty", "skip", "dirty_snapshot"])
def test_bad_verification_stops_before_approval(sandbox, mode):
    repo, remote, base, head, env = sandbox
    code, output, prompted = run_interactive(repo, {**env, "TEST_VERIFY_MODE": mode}, f"merge {head}")
    assert code != 0, output
    assert not prompted
    assert remote_main(remote) == base


@pytest.mark.parametrize("path", ["docs/private.md", "LEARNINGS.html", "LEARNINGS.md", ".env", "nested/.env.production"])
def test_private_paths_in_history_cannot_be_promoted(sandbox, path):
    repo, remote, base, head, env = sandbox
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("private test material")
    git(repo, "add", path)
    git(repo, "commit", "-m", "private path")
    git(repo, "rm", path)
    git(repo, "commit", "-m", "delete private path")
    code, output, prompted = run_interactive(repo, env, f"merge {head}")
    assert code != 0, output
    assert not prompted
    assert remote_main(remote) == base


def test_dirty_public_tree_is_refused(sandbox):
    repo, remote, base, head, env = sandbox
    (repo / "uncommitted.txt").write_text("not verified")
    code, output, prompted = run_interactive(repo, env, f"merge {head}")
    assert code != 0, output
    assert not prompted
    assert remote_main(remote) == base


def test_remote_movement_does_not_get_overwritten(sandbox):
    repo, remote, base, head, env = sandbox
    tree = git(repo, "rev-parse", f"{base}^{{tree}}")
    other = git(repo, "commit-tree", tree, "-p", base, "-m", "concurrent main")
    git(repo, "push", "origin", f"{other}:refs/heads/concurrent")
    env = {**env, "TEST_VERIFY_MODE": "advance", "TEST_NEW_MAIN": other}
    code, output, _ = run_interactive(repo, env, f"merge {head}")
    assert code != 0, output
    assert remote_main(remote) == other


def test_verifier_does_not_use_parent_project_environment(sandbox):
    repo, remote, _, head, env = sandbox
    env = {**env, "TEST_CHECK_ENV": "1", "UV_PROJECT_ENVIRONMENT": "/not-the-snapshot", "PYTHONPATH": "/not-the-snapshot"}
    code, output, _ = run_interactive(repo, env, f"merge {head}")
    assert code == 0, output
    assert remote_main(remote) == head


def test_real_uv_verifies_a_fresh_snapshot_offline(sandbox):
    repo, remote, _, _, env = sandbox
    source = SCRIPT.parent.parent
    for name in ("pyproject.toml", "uv.lock", ".python-version", "src/p01/__init__.py"):
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_smoke.py").write_text("def test_snapshot_imports_package():\n    import p01\n    assert p01.__name__ == 'p01'\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "runnable disposable snapshot")
    head = git(repo, "rev-parse", "HEAD")
    env = {**env, "PATH": os.environ["PATH"], "UV_OFFLINE": "1"}
    code, output, _ = run_interactive(repo, env, f"merge {head}")
    assert code == 0, output
    assert remote_main(remote) == head
    reports = list((repo / ".superpowers" / "merges" / head).glob("*/pytest.xml"))
    assert len(reports) == 1


def test_noninteractive_call_cannot_supply_owner_approval(sandbox):
    repo, remote, base, head, env = sandbox
    assert SCRIPT.exists(), "Local merge command is not implemented"
    result = subprocess.run(["bash", str(SCRIPT)], cwd=repo, env=env, input=f"merge {head}\n", text=True, capture_output=True)
    assert result.returncode != 0
    assert remote_main(remote) == base
