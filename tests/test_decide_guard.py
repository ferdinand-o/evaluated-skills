"""Tests für `decide_log.py guard` (Spec 28, Abschnitt „Hook (G3, optional)“, Tests (Repo)):
Push-Ziel und Freigabe aus der Ablage, die Befehlstabelle, eigene Fehler, Gleichlauf von
`GUARD_COMMANDS` mit `references/reversibility.md` und die Hook-Vorlage
`assets/hooks/decide-guard.json`. Echtes Git in tmp_path, `origin` ist ein lokales Bare-Repo —
kein Netz."""

import io
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from conftest import REPO_ROOT, decide_commit, decide_script, git

dl = decide_script()

SKILL_DIR = REPO_ROOT / "skills" / "decide"
REVERSIBILITY = SKILL_DIR / "references" / "reversibility.md"
SNIPPET = SKILL_DIR / "assets" / "hooks" / "decide-guard.json"
QUESTION = "Push auf origin?"


def payload(command, cwd):
    return json.dumps({"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": "Bash",
                       "tool_input": {"command": command, "description": "x"}, "cwd": str(cwd)})


def run(command, cwd):
    return dl.guard(payload(command, cwd))


def reason(out):
    """Der Grund einer `ask`-Ausgabe; prüft dabei die Form, die Claude Code erwartet."""
    assert out, "erwartet ask, bekam keine Ausgabe"
    assert "\n" not in out.strip()
    data = json.loads(out)
    assert set(data) == {"hookSpecificOutput"}, data
    hso = data["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse" and hso["permissionDecision"] == "ask", hso
    assert hso["permissionDecisionReason"].startswith("decide: "), hso
    return hso["permissionDecisionReason"]


def block(number, status, key, question=QUESTION):
    return (f"\n## D-{number} · 2026-11-04 · {status}\nFrage: {question}\nThema: Push\nSchlüssel: {key}\n"
            "Optionen:\n- A: pushen\n- B: nicht pushen\nEmpfehlung: A\nAntwort: —\nQuelle der Antwort: —\n")


def write_ledger(root, *blocks):
    path = root / "docs" / "big-decisions.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{dl.LOG_HEADER}\n\n# Große Entscheidungen\n" + "".join(blocks), encoding="utf-8")


@pytest.fixture
def pushed(tmp_path, monkeypatch):
    """Repo auf Zweig `x` mit einem Commit, `origin` ein Bare-Repo, Upstream `origin/x` gesetzt."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "x")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    decide_commit(repo)
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "-u", "origin", "x")
    return repo


# --- Push ------------------------------------------------------------------------------

def test_guard_push(pushed, tmp_path, monkeypatch):
    repo = pushed
    # ohne Block: Rückfrage mit dem Ziel aus dem Upstream
    why = reason(run("git push", repo))
    assert why.startswith("decide: push — git push: ")
    assert "keine Freigabe mit Schlüssel push:origin/x in docs/big-decisions.md" in why, why
    assert "keine Freigabe mit Schlüssel push:origin/x" in reason(run("git push -u origin HEAD", repo))
    assert dl.guard_decision("git push -u origin HEAD", repo)[0] == "push"
    assert "push:origin/x " in dl.guard_decision("git push -u origin HEAD", repo)[1]

    # Freigabe per Auftrag, wie die Doktrin sie ablegt
    monkeypatch.chdir(repo)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sitzung-1")
    assert dl.main(["add", "--class", "gross", "--topic", "Push", "--question", QUESTION,
                    "--key", "push:origin/**", "--approved-by-request", "push auf origin"]) == 0
    for command in ("git push", "git push origin", "git push -u origin HEAD", "git push origin HEAD:refs/heads/x",
                    "git push -q --no-verify origin x", "git push origin refs/heads/x"):
        assert run(command, repo) == "", command
        assert dl.guard_decision(command, repo) is None, command
    assert run(f"git -C {repo} push origin x", tmp_path) == ""
    assert run(f"git -C repo push origin x", tmp_path) == ""            # -C relativ zu cwd

    # trotz Block: Rückfrage
    for command in ("git push --force", "git push -f origin x", "git push --force-with-lease",
                    "git push origin +x", "git push origin :x", "git push origin --delete x", "git push --tags",
                    "git push -o ci.skip", "git push origin x y", "git push origin HEAD:refs/tags/v1",
                    "git push --repo=origin", "git push -uf origin x"):
        why = reason(run(command, repo))
        assert why.startswith("decide: push — ") and why.endswith("immer Rückfrage"), (command, why)
    assert run("git push --dry-run --force", repo) == ""
    assert run("git push -n origin x", repo) == ""

    # abgelöster HEAD
    git(repo, "checkout", "-q", "--detach")
    assert "immer Rückfrage" in reason(run("git push origin HEAD", repo))
    assert "immer Rückfrage" in reason(run("git push origin", repo))
    git(repo, "checkout", "-q", "x")

    # ohne Upstream und ohne Argumente
    git(repo, "checkout", "-q", "-b", "y")
    assert "immer Rückfrage" in reason(run("git push", repo))
    assert run("git push origin y", repo) == ""                          # Ziel bestimmbar, Muster trifft
    git(repo, "checkout", "-q", "x")


def test_guard_push_latest_block_counts(pushed):
    repo = pushed
    write_ledger(repo, block(1, "freigegeben", "push:origin/**"))
    assert run("git push", repo) == ""
    # ein jüngerer offener Block mit gleicher Frage und gleichem Schlüssel überholt die Freigabe
    write_ledger(repo, block(1, "freigegeben", "push:origin/**"), block(2, "offen", "push:origin/**"))
    assert "keine Freigabe mit Schlüssel push:origin/x" in reason(run("git push", repo))
    # anderes Muster, Text nach #, abgelehnt: keine Freigabe
    for key, status in (("push:origin/main", "freigegeben"), ("push:origin/x#foo", "freigegeben"),
                        ("push:origin/x", "abgelehnt"), ("dependency:origin/x", "freigegeben")):
        write_ledger(repo, block(1, status, key))
        assert "keine Freigabe" in reason(run("git push", repo)), key
    write_ledger(repo, block(1, "freigegeben", "push:origin/x"))
    assert run("git push", repo) == ""
    assert "keine Freigabe mit Schlüssel push:origin/main" in reason(run("git push origin main", repo))


def test_guard_push_line_continuation_and_redirects(pushed):
    repo = pushed
    write_ledger(repo, block(1, "freigegeben", "push:origin/x"))
    assert run("git push origin x 2>&1 | tail -3", repo) == ""
    assert run("git push origin x > /dev/null 2>&1", repo) == ""
    assert "immer Rückfrage" in reason(run("git push \\\n  --force origin x", repo))
    assert "immer Rückfrage" in reason(run("git push origin x && git push --force", repo))


# --- Befehlstabelle --------------------------------------------------------------------

ASK = [
    ("data-delete", "rm -rf data"), ("data-delete", "rm -fr data"), ("data-delete", "rm -R data"),
    ("data-delete", "rm --recursive data"), ("data-delete", "rm -rf build data"), ("data-delete", "rm -rf /tmp"),
    ("data-delete", "rm -rf node_modules/../src"), ("data-delete", "/bin/rm -rf data"),
    ("external", "curl -d a https://x"), ("external", "curl -sSd a https://x"), ("external", "curl -XPOST https://x"),
    ("external", "curl -X DELETE https://x"), ("external", "curl --request=PUT https://x"),
    ("external", "curl --request PATCH https://x"), ("external", "curl --data-binary @f https://x"),
    ("external", "curl -F f=@a https://x"), ("external", "curl --json {} https://x"),
    ("external", "curl -T a https://x"), ("external", "curl --upload-file a https://x"),
    ("external", "curl --form-string a=b https://x"),
    ("external", "wget --post-data a https://x"), ("external", "wget --post-file=a https://x"),
    ("external", "wget --method=PUT https://x"),
    ("data-delete", 'sqlite3 app.db "DROP TABLE users;"'), ("data-delete", 'psql -c "truncate orders"'),
    ("data-delete", 'mysql -e "delete from orders"'),
    ("data-delete", 'sqlite3 app.db "DELETE FROM t WHERE id=1; DELETE FROM u;"'),
    ("unsaved-work", "git restore --staged --worktree a"), ("unsaved-work", "git restore a"),
    ("unsaved-work", "git restore -SW a"),
    ("unsaved-work", "git checkout a.txt"), ("unsaved-work", "git checkout -- a"), ("unsaved-work", "git checkout ."),
    ("unsaved-work", "git checkout -f main"), ("unsaved-work", "git reset --hard"),
    ("unsaved-work", "git reset --hard HEAD~1"), ("unsaved-work", "git stash drop"), ("unsaved-work", "git stash clear"),
    ("data-delete", "git clean -fdx"), ("data-delete", "git clean --force"), ("data-delete", "git clean -f"),
    ("data-delete", "git branch -D old"), ("data-delete", "git branch --delete --force old"),
    ("data-delete", "git branch -df old"),
    ("push", "gh pr merge 12"), ("push", "gh release create v1"),
    ("external", "gh pr create --fill"), ("external", "gh issue create -t x"), ("external", "gh issue close 3"),
    ("external", "gh issue comment 3 -b x"), ("external", "npm publish"), ("external", "twine upload dist/*"),
    ("external", "docker push img"), ("external", "terraform apply"), ("external", "terraform -chdir=x destroy"),
    ("external", "kubectl apply -f a.yaml"), ("external", "kubectl -n prod delete pod a"),
    ("unsaved-work", "cd x && git reset --hard"), ("data-delete", "FOO=1 sudo rm -rf data"),
    ("data-delete", "sudo -u root rm -rf data"), ("data-delete", "echo a; rm -rf data"),
    ("data-delete", "ls | rm -rf data"), ("data-delete", "true || rm -rf data"), ("data-delete", "sleep 1 & rm -rf data"),
    ("data-delete", "ls\nrm -rf data"), ("data-delete", "for d in a b; do rm -rf $d; done"),
    ("data-delete", "if true; then rm -rf data; fi"), ("data-delete", "curl https://x/#a; rm -rf data"),
    ("unsaved-work", "git -C sub --no-pager -c a=b reset --hard"),
]

NOTHING = [
    "rm -rf .skills/cache/x", "rm -rf build dist .venv", "rm -rf a/node_modules", "rm a.txt", "rm -f a.txt",
    "rm -rf /tmp/x", "rm -rf __pycache__ src/__pycache__ .pytest_cache .mypy_cache .ruff_cache",
    "curl https://x", "curl -sS https://x", "curl -X GET https://x", "curl -XHEAD https://x", "curl -I https://x",
    "curl -o out -H 'X-d: 1' https://x", "wget https://x",
    'sqlite3 app.db "DELETE FROM t WHERE id=1;"', 'sqlite3 drop.db "SELECT 1"', "psql -c 'select 1'",
    "git restore --staged a", "git restore -S a", "git checkout main", "git checkout -b neu", "git clean -n",
    "git branch -d old", "git stash", "git stash list", "git reset --soft HEAD~1", "git reset a",
    "gh pr view 12", "gh release list", "gh issue list", "npm install", "twine check dist/*", "docker pull img",
    "terraform plan", "kubectl get pods", "ls -la", "echo rm -rf data", "git status", "",
    'git commit -m "$(cat <<\'EOF\'\nfix\n\ngit reset --hard\nEOF\n)"',
    'echo "a && rm -rf data"',
]


@pytest.fixture
def work(tmp_path):
    repo = tmp_path / "repo"
    (repo / "x").mkdir(parents=True)
    (repo / "sub").mkdir()
    git(repo, "init", "-q")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    return repo


def test_guard_commands(work):
    for category, command in ASK:
        out = run(command, work)
        why = reason(out)
        assert why.startswith(f"decide: {category} — "), (command, why)
        assert why.endswith(": immer Rückfrage"), (command, why)
        assert dl.guard_decision(command, work) == (category, "immer Rückfrage"), command
    for command in NOTHING:
        assert run(command, work) == "", command
        assert dl.guard_decision(command, work) is None, command


def test_guard_reason_shortens_command(work):
    command = "rm -rf data " + " ".join(f"datei{n}" for n in range(40))
    why = reason(run(command, work))
    shown = why[len("decide: data-delete — "):-len(": immer Rückfrage")]
    assert len(shown) == 80 and shown.endswith("…") and shown.startswith("rm -rf data datei0"), shown
    # der erkannte Teil, nicht der ganze Befehl
    why = reason(run("echo hallo && git reset --hard", work))
    assert why == "decide: unsaved-work — git reset --hard: immer Rückfrage", why


# --- eigene Fehler ---------------------------------------------------------------------

def test_guard_errors(work, monkeypatch, capsys):
    for text in ("", "   ", "kein json", "[1, 2]", json.dumps({"tool_name": "Bash"}),
                 json.dumps({"tool_input": {"command": 3}}), json.dumps({"tool_input": "rm -rf data"})):
        data = json.loads(dl.guard(text))
        assert set(data) == {"systemMessage"}, text
        assert data["systemMessage"].startswith("[decide] Hook ungeprüft — "), data

    # unbalancierte Anführungszeichen
    why = reason(run('rm -rf "data', work))
    assert why.startswith("decide: data-delete — ") and why.endswith(": Befehl nicht zerlegbar"), why
    assert "Befehl nicht zerlegbar" in reason(run("git commit -m 'x && git push", work))
    assert run('echo "hallo', work) == ""
    assert run("format 'x", work) == ""                                   # rm nur als ganzes Wort

    # eine unerwartete Ausnahme hält nichts an
    def boom(*args, **kwargs):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(dl, "_guard_hit", boom)
    data = json.loads(run("rm -rf data", work))
    assert data["systemMessage"] == "[decide] Hook ungeprüft — RuntimeError: kaputt", data


def test_guard_main_reads_stdin_and_exits_zero(work, monkeypatch, capsys):
    for text, expect in ((payload("rm -rf data", work), "ask"), (payload("ls", work), ""), ("kein json", "system")):
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8"))
        assert dl.main(["guard"]) == 0
        out = capsys.readouterr().out
        if expect == "ask":
            assert reason(out.strip()).startswith("decide: data-delete")
        elif expect == "system":
            assert "Hook ungeprüft" in json.loads(out)["systemMessage"]
        else:
            assert out == ""


# --- Prüfpunkt nach Task 3 (F1–F12) ----------------------------------------------------

def test_guard_push_target_from_push_not_upstream(pushed, tmp_path):
    """F1: Ziel aus @{push}; nur <remote> gilt nur, wenn es das Remote von @{push} ist;
    push.default=matching und remote.<r>.push fragen nach."""
    repo = pushed
    write_ledger(repo, block(1, "freigegeben", "push:origin/**"))
    fork = tmp_path / "fork.git"
    subprocess.run(["git", "init", "-q", "--bare", str(fork)], check=True)
    git(repo, "remote", "add", "fork", str(fork))
    git(repo, "push", "-q", "fork", "x")
    assert reason(run("git push fork", repo)).endswith("immer Rückfrage (Remote ist nicht das von @{push})")
    git(repo, "config", "push.default", "current")
    git(repo, "config", "branch.x.pushRemote", "fork")
    assert "keine Freigabe mit Schlüssel push:fork/x" in reason(run("git push", repo))
    assert "immer Rückfrage" in reason(run("git push origin", repo))
    git(repo, "config", "--unset", "branch.x.pushRemote")
    assert run("git push", repo) == "" and run("git push origin", repo) == ""
    git(repo, "config", "push.default", "matching")
    assert "immer Rückfrage" in reason(run("git push", repo))
    assert "immer Rückfrage" in reason(run("git push origin", repo))
    assert run("git push origin x", repo) == ""                            # Refspec: Konfiguration egal
    git(repo, "config", "push.default", "simple")
    git(repo, "config", "remote.origin.push", "refs/heads/*:refs/heads/*")
    assert "immer Rückfrage" in reason(run("git push", repo))
    assert "immer Rückfrage" in reason(run("git push origin", repo))


def test_guard_push_tag_source_asks(pushed):
    """F2: Ein Tag als Quelle ist nie ein Zweig-Push."""
    repo = pushed
    write_ledger(repo, block(1, "freigegeben", "push:origin/**"))
    git(repo, "tag", "v1.0")
    assert "immer Rückfrage" in reason(run("git push origin v1.0", repo))
    assert "immer Rückfrage" in reason(run("git push origin v1.0:v1.0", repo))
    assert run("git push origin x", repo) == ""


def test_guard_git_global_options_with_value(pushed, work):
    """F3: Globale git-Optionen nehmen ihren Wert mit; `git -c … push` fragt nach."""
    write_ledger(pushed, block(1, "freigegeben", "push:origin/**"))
    assert "immer Rückfrage" in reason(run("git --git-dir .git push --force", pushed))
    assert "immer Rückfrage" in reason(run("git -c remote.origin.url=/x push origin x", pushed))
    assert "immer Rückfrage" in reason(run("git --config-env=remote.origin.url=U push origin x", pushed))
    assert run("git --no-pager push origin x", pushed) == ""
    for command in ("git --work-tree . reset --hard", "git --git-dir=.git reset --hard",
                    "git --namespace n reset --hard", "git --config-env a=B reset --hard"):
        assert dl.guard_decision(command, work) == ("unsaved-work", "immer Rückfrage"), command


def test_guard_wrappers(work):
    """F4: Wrapper vor dem Programm samt Optionen und Werten."""
    for category, command in (
            ("push", "timeout 60 git push --force"), ("push", "timeout -s KILL -k 5 60 git push --force"),
            ("data-delete", "nice rm -rf src"), ("data-delete", "nice -n 10 rm -rf src"),
            ("data-delete", "env -i rm -rf src"), ("data-delete", "env -u X A=1 rm -rf src"),
            ("data-delete", "sudo --user root rm -rf src"), ("data-delete", "sudo -g wheel rm -rf src"),
            ("data-delete", "doas -u root rm -rf src"), ("data-delete", "ionice -c 3 rm -rf src"),
            ("data-delete", "stdbuf -oL rm -rf src"), ("data-delete", "nohup rm -rf src"),
            ("data-delete", "time rm -rf src"), ("data-delete", "command rm -rf src"),
            ("data-delete", "exec rm -rf src"), ("data-delete", "sudo -- rm -rf src")):
        assert dl.guard_decision(command, work) == (category, "immer Rückfrage"), command
    assert dl.guard_decision("timeout 60 ls", work) is None


def test_guard_cd_sets_directory(pushed, tmp_path):
    """F5: `cd` setzt das Verzeichnis für folgende Teile; unbekanntes Ziel → Push fragt; nach `(`/`)` ist es unbekannt (R2-F6)."""
    repo = pushed
    write_ledger(repo, block(1, "freigegeben", "push:origin/**"))
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "-q", "-b", "main")
    git(other, "remote", "add", "origin", str(tmp_path / "origin.git"))
    assert run("git push origin main", repo) == ""
    why = reason(run("cd ../other && git push origin main", repo))
    assert "keine Freigabe mit Schlüssel push:origin/main" in why, why
    for command in ("cd && git push origin x", "cd - && git push origin x", "cd $D && git push origin x",
                    "cd ~/repo && git push origin x"):
        assert "immer Rückfrage" in reason(run(command, repo)), command
    assert run("cd . && git push origin x", repo) == ""
    assert "Verzeichnis unbekannt" in reason(run("(cd ../other) && git push origin x", repo))
    assert dl.guard_decision("(cd sub && git reset --hard)", repo) == ("unsaved-work", "immer Rückfrage")
    assert dl.guard_decision("(git reset --hard)", repo) == ("unsaved-work", "immer Rückfrage")


def test_guard_rm_without_target_asks(work):
    """F6: Bleibt nach dem Zerlegen kein Ziel übrig, fragt guard."""
    for command in ('rm -rf "<x>"', "rm -rf '>out'", "rm -rf"):
        assert dl.guard_decision(command, work) == ("data-delete", "immer Rückfrage"), command


def test_guard_rm_exemptions_only_relative(work):
    """F7: Ausnahmen nur für relative Pfade ohne `..`, `~`, `$`; absolut nur /tmp/."""
    for command in ("rm -rf ~/build", "rm -rf /home/u/dist", 'rm -rf "$HOME/build"', "rm -rf $X/node_modules",
                    "rm -rf ../build", "rm -rf /tmp/../build"):
        assert dl.guard_decision(command, work) == ("data-delete", "immer Rückfrage"), command
    for command in ("rm -rf build", "rm -rf a/dist", "rm -rf /tmp/x", "rm -rf .skills/cache/x"):
        assert dl.guard_decision(command, work) is None, command


FURTHER = [
    ("unsaved-work", "git switch -f main"), ("unsaved-work", "git switch --discard-changes main"),
    ("unsaved-work", "git switch --force main"), ("unsaved-work", "git reset --merge"),
    ("unsaved-work", "git reset --keep HEAD~1"),
    ("data-delete", "find . -name '*.pyc' -delete"), ("data-delete", "find . -type d -exec rm -rf {} +"),
    ("data-delete", "find . -execdir /bin/rm {} ;"),
    ("external", "gh api -X POST repos/o/r/issues"), ("external", "gh api --method=DELETE repos/o/r"),
    ("external", "gh api -XPATCH repos/o/r"), ("external", "gh api --method PUT repos/o/r"),
    ("external", "gh api repos/o/r/issues -f title=x"), ("external", "gh api repos/o/r -F a=1"),
    ("external", "gh api repos/o/r --field a=1"), ("external", "gh api repos/o/r --raw-field=a=1"),
    ("external", "gh api repos/o/r --input body.json"),
    ("external", "gh pr comment 3 -b x"), ("external", "gh pr close 3"), ("external", "gh pr review 3 --approve"),
    ("external", "gh pr edit 3 -t x"), ("external", "gh repo delete o/r"), ("external", "gh release delete v1"),
    ("external", "yarn publish"), ("external", "pnpm publish"), ("external", "cargo publish"),
    ("external", "uv publish"), ("external", "poetry publish"),
]


def test_guard_further_commands(work):
    """F8: die Liste „Weitere Befehle“ aus Spec 28."""
    for category, command in FURTHER:
        assert dl.guard_decision(command, work) == (category, "immer Rückfrage"), command
    for command in ("git switch main", "git switch -c neu", "git reset --soft HEAD~1", "find . -name x",
                    "find . -exec grep a {} +", "gh api repos/o/r", "gh api -X GET repos/o/r", "gh pr view 3",
                    "yarn install", "cargo build", "uv run pytest", "poetry install"):
        assert dl.guard_decision(command, work) is None, command


def test_guard_heredocs(work):
    """F9: Heredoc-Rümpfe sind keine Befehle; an psql/sqlite3/mysql wird der Rumpf wie ein Argument geprüft."""
    for command in ("cat <<'EOF' > notes.txt\ndon't rm -rf data\nEOF", "cat <<EOF > f\nrm -rf data\nEOF",
                    "cat <<-\"END\"\n\tgit reset --hard\n\tEND", "psql app <<-SQL\n\tDELETE FROM t WHERE id=1;\n\tSQL",
                    "cat <<<'rm -rf data'"):
        assert dl.guard_decision(command, work) is None, command
    for command in ("psql app <<EOF\nDROP TABLE users;\nEOF", "sqlite3 app.db <<'SQL'\ndelete from t;\nSQL",
                    "mysql <<X\nselect 1;\ntruncate t;\nX"):
        assert dl.guard_decision(command, work) == ("data-delete", "immer Rückfrage"), command
    assert dl.guard_decision("cat <<EOF\nx\nEOF\nrm -rf data", work) == ("data-delete", "immer Rückfrage")
    # ohne Endzeile: kein Schnitt, der Rest bleibt Befehl
    assert dl.guard_decision("cat <<EOF\nrm -rf data", work) == ("data-delete", "immer Rückfrage")


def test_guard_without_program_starts_no_subprocess(work, monkeypatch):
    """F10: Ohne Programmnamen der Tabelle kein Git-Aufruf, keine Ausgabe."""
    calls = []

    def spy(*args, **kwargs):
        calls.append(args)
        raise AssertionError("subprocess")
    monkeypatch.setattr(dl.subprocess, "run", spy)
    for command in ("ls -la", "echo hallo && python -m pytest -q", "cat a.txt | head"):
        assert run(command, work) == "", command
    assert calls == []


@pytest.mark.skipif(shutil.which("bash") is None, reason="Hooks laufen über bash")
def test_hook_snippet_python_fallback(work, tmp_path):
    """F11: python3, sonst python, sonst Meldung „kein Python 3“ (R2-F8)."""
    command = snippet_command()
    (work / ".claude" / "hooks").mkdir(parents=True)
    shutil.copy(SKILL_DIR / "scripts" / "decide_log.py", work / ".claude" / "hooks" / "decide_log.py")
    only_python, empty = tmp_path / "only-python", tmp_path / "empty"
    only_python.mkdir()
    empty.mkdir()
    (only_python / "python").symlink_to(sys.executable)

    def hook(path):
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(work), "PATH": str(path)}
        return subprocess.run([shutil.which("bash"), "-c", command], cwd=work, input=payload("rm -rf data", work),
                              capture_output=True, text=True, env=env, timeout=60)

    done = hook(only_python)
    assert done.returncode == 0, done
    assert reason(done.stdout.strip()).startswith("decide: data-delete")
    done = hook(empty)
    assert done.returncode == 0, done
    assert json.loads(done.stdout) == {"systemMessage": "[decide] Hook ungeprüft — kein Python 3"}


def test_guard_noclobber_redirect(work):
    """F12: `>|` ist eine Umleitung, kein Trenner — das Wort danach ist ihr Ziel."""
    assert dl.guard_decision("rm -rf build >| log src", work) == ("data-delete", "immer Rückfrage")
    assert dl.guard_decision("rm -rf build >| log", work) is None
    assert ">\\|" not in dl._REDIRECT_OP_RE.pattern and ">\\|" not in dl._REDIRECT_RE.pattern


# --- Prüfpunkt nach Task 3, Runde 2 (F1–F11) -------------------------------------------

UNPARSED = "Befehl nicht zerlegbar"


def test_guard_command_substitution_asks(work):
    """R2-F1: `$(` oder Backtick außerhalb einfacher Anführungszeichen plus Programmname → ask."""
    for command in ("git reset $(git merge-base a b) --hard", "rm $(echo x) -rf src", "rm `echo x` -rf src",
                    'echo "$(rm -rf src)"', "cat <<EOF\ndon't $(rm -rf src) won't\nEOF",
                    "git commit -m \"$(cat <<EOF\nx\nEOF\n)\" && rm $(echo x) -rf src"):
        assert reason(run(command, work)).endswith(": " + UNPARSED), command
        assert dl.guard_decision(command, work)[1] == UNPARSED, command
    for command in ("echo '$(rm -rf src)'", "ls $(pwd)", "cat <<'EOF' > f.sh\ngit log $(x)\nEOF",
                    "git commit -m \"$(cat <<'EOF'\nfix (x)\n\ngit reset --hard\nEOF\n)\""):
        assert dl.guard_decision(command, work) is None, command
    # die Nachricht aus der Commit-Vorlage ist ein Wort: was danach steht, wird weiter geprüft
    assert dl.guard_decision("git commit -m \"$(cat <<'EOF'\nx\nEOF\n)\" && git reset --hard", work) == (
        "unsaved-work", "immer Rückfrage")
    assert dl.guard_decision("rm \"$(cat <<'EOF'\n-rf\nEOF\n)\" src", work) == ("data-delete", "immer Rückfrage")


def test_guard_parentheses_are_no_separators(work):
    """R2-F2: `\\(` und `\\)` bei find zerschneiden den Befehl nicht."""
    for command in ("find . \\( -name '*.pyc' -o -name '*.pyo' \\) -delete", "(git reset --hard)",
                    "( rm -rf src )"):
        assert dl.guard_decision(command, work) in (("data-delete", "immer Rückfrage"),
                                                    ("unsaved-work", "immer Rückfrage")), command


def test_guard_heredoc_at_shell_is_checked(work):
    """R2-F3: An einer Shell bleibt der Heredoc-Rumpf Befehlstext."""
    for category, command in (("data-delete", "bash <<EOF\nrm -rf src\nEOF"),
                              ("unsaved-work", "ssh host <<'EOF'\ngit reset --hard\nEOF"),
                              ("data-delete", "sh <<-X\n\trm -rf src\n\tX"),
                              ("data-delete", "cat <<EOF | bash\nrm -rf src\nEOF")):
        assert dl.guard_decision(command, work) == (category, "immer Rückfrage"), command
    assert dl.guard_decision("cat <<EOF > run.sh\nrm -rf src\nEOF", work) is None


def test_guard_heredoc_marker_in_quotes_is_no_heredoc(work):
    """R2-F4: `<<WORT` in Anführungszeichen ist kein Heredoc."""
    for command in ('echo "<<X"\nrm -rf src\nX', "echo '<<X'\nrm -rf src\nX"):
        assert dl.guard_decision(command, work)[0] == "data-delete", command
    assert dl.guard_decision('echo "a <<X" <<Y\nrm -rf src\nY', work) is None      # der zweite ist ein Heredoc


def test_guard_push_mirror_asks(pushed):
    """R2-F5: `remote.<r>.mirror=true` fragt ohne Refspec nach."""
    repo = pushed
    write_ledger(repo, block(1, "freigegeben", "push:origin/**"))
    git(repo, "config", "remote.origin.mirror", "true")
    assert "immer Rückfrage" in reason(run("git push", repo))
    assert "immer Rückfrage" in reason(run("git push origin", repo))
    git(repo, "config", "remote.origin.mirror", "false")
    assert run("git push", repo) == ""


def test_guard_directory_after_pushd_pipe_and_parentheses(pushed, tmp_path):
    """R2-F6: pushd/popd und Wörter mit `(`/`)` machen das Verzeichnis unbekannt; cd wirkt nicht über | und &."""
    approved = tmp_path / "approved"
    approved.mkdir()
    git(approved, "init", "-q", "-b", "x")
    write_ledger(approved, block(1, "freigegeben", "push:origin/**"))
    assert run("cd ../approved && git push origin x", pushed) == ""
    assert run("cd ../approved\ngit push origin x", pushed) == ""
    for command in ("cd ../approved & git push origin x", "cd ../approved | git push origin x",
                    "ls | cd ../approved && git push origin x"):
        assert "keine Freigabe mit Schlüssel push:origin/x" in reason(run(command, pushed)), command
    for command in ("pushd ../approved && git push origin x", "popd && git push origin x",
                    "(cd ../approved) && git push origin x", "(cd ../approved && git push origin x)"):
        assert reason(run(command, pushed)).endswith("immer Rückfrage (Verzeichnis unbekannt)"), command


def test_guard_find_exec_checks_inner_command(work):
    """R2-F7: Die Wörter nach -exec/-execdir/-ok/-okdir bis `;` oder `+` sind ein eigener Befehl."""
    for category, command in (("data-delete", "find . -exec sudo rm -rf {} +"), ("data-delete", "find . -ok rm {} ;"),
                              ("data-delete", "find . -okdir rm {} \\;"),
                              ("unsaved-work", "find . -exec git checkout -- {} ;"),
                              ("unsaved-work", "find . -name x -exec echo {} \\; -exec git reset --hard \\;")):
        assert dl.guard_decision(command, work) == (category, "immer Rückfrage"), command
    assert dl.guard_decision("find . -exec git status {} ; -print", work) is None


@pytest.mark.skipif(shutil.which("bash") is None, reason="Hooks laufen über bash")
def test_hook_snippet_requires_python3(work, tmp_path):
    """R2-F8: python3 oder python nur ab Python 3.8; sonst die Meldung „kein Python 3“."""
    command = snippet_command()
    (work / ".claude" / "hooks").mkdir(parents=True)
    shutil.copy(SKILL_DIR / "scripts" / "decide_log.py", work / ".claude" / "hooks" / "decide_log.py")
    old, mixed = tmp_path / "old", tmp_path / "mixed"
    for folder in (old, mixed):
        folder.mkdir()
        (folder / "python3").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (folder / "python3").chmod(0o755)
    (old / "python").symlink_to(old / "python3")
    (mixed / "python").symlink_to(sys.executable)

    def hook(path):
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(work), "PATH": str(path)}
        return subprocess.run([shutil.which("bash"), "-c", command], cwd=work, input=payload("rm -rf data", work),
                              capture_output=True, text=True, env=env, timeout=60)

    done = hook(old)
    assert done.returncode == 0, done
    assert json.loads(done.stdout) == {"systemMessage": "[decide] Hook ungeprüft — kein Python 3"}
    done = hook(mixed)
    assert done.returncode == 0, done
    assert reason(done.stdout.strip()).startswith("decide: data-delete")


def test_guard_wrappers_with_path_and_values(work):
    """R2-F9: Wrapper mit Pfad, `sudo -r/-t/--role/--type` mit Wert, `env -S` → nicht zerlegbar."""
    for command in ("sudo -r role rm -rf src", "sudo -t type rm -rf src", "sudo --role r --type t rm -rf src",
                    "/usr/bin/env rm -rf src", "/usr/bin/sudo -u root rm -rf src"):
        assert dl.guard_decision(command, work) == ("data-delete", "immer Rückfrage"), command
    for command in ("env -S 'rm -rf src'", "/usr/bin/env --split-string='rm -rf src'"):
        assert dl.guard_decision(command, work)[1] == UNPARSED, command


def test_reference_describes_what_guard_does_not_parse():
    """R2-F10: reversibility.md beschreibt `$(…)`, Klammern und Heredocs wie der Code."""
    section = REVERSIBILITY.read_text(encoding="utf-8").split("## Befehle, die guard erkennt", 1)[1]
    section = " ".join(section.split("\n## ", 1)[0].split())
    assert "trennen auch" not in section and "nach einer Subshell" not in section
    assert "`bash`, `sh`, `zsh`, `dash`, `ksh`, `ssh`" in section
    assert "ausgeglichene Anführungszeichen" in section
    assert "„Befehl nicht zerlegbar“ (unbalancierte Anführungszeichen, `$(` oder ein Backtick" in section
    assert "`-ok`" in section and "`pushd`" in section and "`env -S`" in section and "mirror" in section


def test_guard_root_lazy_and_one_precheck(pushed, work, monkeypatch):
    """R2-F11: eine Vorprüfung; Wurzel erst bei Bedarf und einmal je Verzeichnis; SQL-Programme aus _GUARD_CHECKS."""
    source = (SKILL_DIR / "scripts" / "decide_log.py").read_text(encoding="utf-8")
    assert source.count("_PROGRAM_RE.search(") == 1
    assert "_SQL_PROGRAM_RE" not in source and "psql|sqlite3|mysql" not in source
    write_ledger(pushed, block(1, "freigegeben", "push:origin/**"))
    calls, real = [], dl.repo_root

    def spy(directory):
        calls.append(str(directory))
        return real(directory)
    monkeypatch.setattr(dl, "repo_root", spy)
    assert run("rm a.txt && git status", work) == "" and calls == []
    assert run("git push origin x && git push origin y && git push", pushed) == ""
    assert calls == [str(pushed)]


# --- Gleichlauf mit der Reference ------------------------------------------------------

def reference_commands():
    text = REVERSIBILITY.read_text(encoding="utf-8")
    section = text.split("## Befehle, die guard erkennt", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| `")]
    found = {}
    for line in rows:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        category, command = (re.fullmatch(r"`([^`]+)`", cell).group(1) for cell in cells[:2])
        assert command not in found, command
        found[command] = category
    return found


def test_guard_table_matches_reference():
    assert reference_commands() == dict(dl.GUARD_COMMANDS)
    assert len(dl.GUARD_COMMANDS) >= 25
    # die Programmnamen aus Spec 28 („Befehl nicht zerlegbar“, dazu „Weitere Befehle“)
    assert {c.split()[0] for c in dl.GUARD_COMMANDS} == {
        "git", "gh", "rm", "curl", "wget", "psql", "sqlite3", "mysql", "npm", "twine", "docker", "terraform", "kubectl",
        "find", "yarn", "pnpm", "cargo", "uv", "poetry"}
    assert {category for category, _ in FURTHER} <= set(dl.GUARD_COMMANDS.values())
    assert set(dl.GUARD_COMMANDS.values()) == {"push", "external", "data-delete", "unsaved-work"}
    text = REVERSIBILITY.read_text(encoding="utf-8")
    assert "eine zweite Liste im Skript gibt es nicht" not in text
    head = (SKILL_DIR / "scripts" / "decide_log.py").read_text(encoding="utf-8").split('"""')[1]
    assert "guard" in head and "GUARD_COMMANDS" in head


# --- Hook-Vorlage ----------------------------------------------------------------------

def snippet_command():
    data = json.loads(SNIPPET.read_text(encoding="utf-8"))
    assert "_comment" in data and ".claude/hooks/" in data["_comment"] and "NIE" in data["_comment"]
    entries = data["hooks"]["PreToolUse"]
    assert len(entries) == 1 and entries[0]["matcher"] == "Bash"
    hooks = entries[0]["hooks"]
    assert len(hooks) == 1 and hooks[0]["type"] == "command"
    return hooks[0]["command"]


@pytest.mark.skipif(shutil.which("bash") is None, reason="Hooks laufen über bash")
def test_hook_snippet(work):
    command = snippet_command()
    assert '"$CLAUDE_PROJECT_DIR/.claude/hooks/decide_log.py" guard' in command
    assert "skills/decide/scripts/" not in command

    def hook(text):
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(work)}
        return subprocess.run(["bash", "-c", command], cwd=work, input=payload(text, work), capture_output=True,
                              text=True, env=env, timeout=60)

    done = hook("rm -rf data")                                            # ohne Kopie
    assert done.returncode == 0, done
    assert json.loads(done.stdout) == {"systemMessage": "[decide] Hook ungeprüft — .claude/hooks/decide_log.py fehlt"}

    # nur die eine Datei kopiert, ohne references/ und assets/
    (work / ".claude" / "hooks").mkdir(parents=True)
    shutil.copy(SKILL_DIR / "scripts" / "decide_log.py", work / ".claude" / "hooks" / "decide_log.py")
    done = hook("rm -rf data")
    assert done.returncode == 0, done
    assert reason(done.stdout.strip()).startswith("decide: data-delete — rm -rf data")
    done = hook("ls -la")
    assert done.returncode == 0 and done.stdout == "", done
    done = hook("git push --force")
    assert done.returncode == 0 and "immer Rückfrage" in reason(done.stdout.strip()), done


# --- Nacharbeit aus dem Review: _read_untracked ----------------------------------------
# Gehört inhaltlich zu check; steht hier, weil tests/test_decide_log.py nicht in der Allowlist
# dieser Task liegt.

def test_read_untracked_closes_descriptor_when_fdopen_fails(tmp_path, monkeypatch):
    path = tmp_path / "a.txt"
    path.write_text("a\n", encoding="utf-8")
    opened, closed = [], []
    real_open, real_close = os.open, os.close

    def fake_open(*args, **kwargs):
        fd = real_open(*args, **kwargs)
        opened.append(fd)
        return fd

    def fake_close(fd):
        closed.append(fd)
        return real_close(fd)

    def fail(*args, **kwargs):
        raise OSError("fdopen kaputt")
    monkeypatch.setattr(dl.os, "open", fake_open)
    monkeypatch.setattr(dl.os, "close", fake_close)
    monkeypatch.setattr(dl.os, "fdopen", fail)
    assert dl._read_untracked(path) is None
    assert opened and closed == opened
