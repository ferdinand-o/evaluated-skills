"""Tests für `decide_log.py guard` (Spec 28, Abschnitt „Hook (G3, optional)“, „Erkennen statt
zerlegen“, und Tests (Repo)): schlichter Push mit Freigabe aus der Ablage, die Mustertabelle, eigene
Fehler, Gleichlauf von `GUARD_PATTERNS` mit `references/reversibility.md` und die Hook-Vorlage
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
ALWAYS = "immer Rückfrage"
PLAIN = "Befehl nicht schlicht"
NO_APPROVAL = "keine Freigabe mit Schlüssel push:origin/x in docs/big-decisions.md"


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


@pytest.fixture
def work(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    return repo


# --- Push ------------------------------------------------------------------------------

def template(word="'EOF'", head="<<"):
    """Die Commit-Vorlage von Claude Code; der Rumpf enthält Muster, die nicht zählen dürfen."""
    end = word.strip("'\"")
    return (f'git commit -m "$(cat {head}{word}\nFix (#12): `foo` und $(bar) "zitat"\n\nrm -rf data\n'
            f'git push --force\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n{end}\n)"')


PLAIN_PUSHES = [
    "git push", "git push origin", "git push -u origin HEAD", "git push origin HEAD:refs/heads/x",
    "git push -q --no-verify origin x", "git push origin refs/heads/x",
    "git add a && git commit -m 'Fix (#12) und `foo`' && git push origin x",
    template() + " && git push origin x", template("'EOF'", "<< ") + " && git push origin x",
    template("'EOF'", "<<-") + "\ngit push origin x", template('"EOF"') + "; git push origin x",
    "git push origin x 2>&1", "git push origin x >/dev/null 2>&1",
]


def test_guard_push(pushed, tmp_path, monkeypatch):
    repo = pushed
    # ohne Block: Rückfrage mit dem Ziel
    for command in PLAIN_PUSHES:
        why = reason(run(command, repo))
        assert why.startswith("decide: push — ") and why.endswith(": " + NO_APPROVAL), (command, why)
    assert reason(run("git push", repo)) == f"decide: push — git push: {NO_APPROVAL}"
    assert dl.guard_decision("git push -u origin HEAD", repo) == ("push", NO_APPROVAL)

    # Freigabe per Auftrag, wie die Doktrin sie ablegt
    monkeypatch.chdir(repo)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sitzung-1")
    assert dl.main(["add", "--class", "gross", "--topic", "Push", "--question", QUESTION,
                    "--key", "push:origin/**", "--approved-by-request", "push auf origin"]) == 0
    for command in PLAIN_PUSHES:
        assert run(command, repo) == "", command
        assert dl.guard_decision(command, repo) is None, command
    assert run(f"git -C {repo} push origin x", tmp_path) == ""
    assert run("git -C repo push origin x", tmp_path) == ""                # -C relativ zu cwd
    assert dl.guard_decision("git -C repo push origin x", repo, tmp_path) is None

    # trotz Block: Rückfrage
    git(repo, "tag", "v1")
    for command in ("git push --force", "git push -f origin x", "git push --force-with-lease", "git push origin +x",
                    "git push origin :x", "git push origin --delete x", "git push --tags", "git push origin v1",
                    "git push origin x y", "git push origin HEAD:refs/tags/v1", "git push origin refs/tags/v1",
                    "git -c k=v push origin x", "git --git-dir=.git push origin x", "git push -o ci.skip",
                    "git push upstream"):
        assert reason(run(command, repo)) == f"decide: push — {command}: {ALWAYS}", command
    for key, value in (("push.default", "matching"), ("remote.origin.mirror", "true"),
                       ("remote.origin.push", "refs/heads/*:refs/heads/*")):
        git(repo, "config", key, value)
        assert reason(run("git push", repo)).endswith(ALWAYS), key
        assert reason(run("git push origin x", repo)).endswith(ALWAYS), key
        git(repo, "config", "--unset", key)
    assert run("git push", repo) == ""
    git(repo, "checkout", "-q", "--detach")
    assert reason(run("git push origin HEAD", repo)).endswith(ALWAYS)
    assert reason(run("git push", repo)).endswith(ALWAYS)
    git(repo, "checkout", "-q", "x")

    # nicht schlicht
    for command in ("cd ../o && git push origin x", "timeout 9 git push origin x",
                    "git push origin $(git branch --show-current)", "git push origin `git branch --show-current`",
                    'git commit -m "Fix `foo`" && git push origin x', 'git commit -m "Fix $(foo)" && git push origin x',
                    "git push origin x && git push origin y", "git push origin x | tail -3", "git push origin x &",
                    "(git push origin x)", "pushd .. && git push origin x", "git push origin x > log",
                    "FOO=1 git push origin x", "git push origin x || true",
                    "bash <<EOF\ngit push origin x\nEOF"):
        why = reason(run(command, repo))
        assert why.startswith("decide: push — ") and why.endswith(": " + PLAIN), (command, why)

    # --dry-run: nichts erkannt, auch ohne Block
    write_ledger(repo)
    for command in ("git push --dry-run", "git push -n origin x", "git push --dry-run --force"):
        assert run(command, repo) == "", command


def test_guard_push_latest_block_counts(pushed):
    repo = pushed
    write_ledger(repo, block(1, "freigegeben", "push:origin/**"))
    assert run("git push", repo) == ""
    # ein jüngerer offener Block mit gleicher Frage und gleichem Schlüssel überholt die Freigabe
    write_ledger(repo, block(1, "freigegeben", "push:origin/**"), block(2, "offen", "push:origin/**"))
    assert reason(run("git push", repo)).endswith(NO_APPROVAL)
    # anderes Muster, Text nach #, abgelehnt, andere Kategorie: keine Freigabe
    for key, status in (("push:origin/main", "freigegeben"), ("push:origin/x#foo", "freigegeben"),
                        ("push:origin/x", "abgelehnt"), ("dependency:origin/x", "freigegeben")):
        write_ledger(repo, block(1, status, key))
        assert reason(run("git push", repo)).endswith(NO_APPROVAL), key
    write_ledger(repo, block(1, "freigegeben", "push:origin/x"))
    assert run("git push", repo) == ""
    assert "keine Freigabe mit Schlüssel push:origin/main" in reason(run("git push origin main", repo))
    # eine unlesbare Ablage steht im Grund
    (repo / "docs" / "big-decisions.md").write_text("ohne Kopfzeile\n", encoding="utf-8")
    assert "übersprungen" in reason(run("git push", repo))


# --- Mustertabelle ---------------------------------------------------------------------

# Je Befehl der Mustertabelle Treffer (ask) und ähnliche Nicht-Treffer (nichts).
HITS = {
    "git push": ["git push --force", "git -C . push origin +x"],
    "gh pr merge": ["gh pr merge 12 --squash"],
    "gh release create": ["gh release create v1"],
    "gh pr create": ["gh pr create --fill"], "gh pr comment": ["gh pr comment 3 -b x"],
    "gh pr close": ["gh pr close 3"], "gh pr review": ["gh pr review --approve"], "gh pr edit": ["gh pr edit 3"],
    "gh issue create": ["gh issue create -t x"], "gh issue close": ["gh issue close 4"],
    "gh issue comment": ["gh issue comment 4 -b x"], "gh repo delete": ["gh repo delete o/r"],
    "gh release delete": ["gh release delete v1"],
    "gh api": ["gh api -X POST repos/o/r/issues", "gh api --method=PATCH repos/o/r", "gh api -XDELETE x",
               "gh api repos/o/r/issues -f title=x", "gh api x -F a=1", "gh api x --raw-field a=b",
               "gh api x --input f.json", "gh api x --field=a=b"],
    "npm publish": ["npm publish", "npm --tag beta publish"], "yarn publish": ["yarn publish"],
    "pnpm publish": ["pnpm publish --no-git-checks"], "cargo publish": ["cargo publish"],
    "uv publish": ["uv publish"], "poetry publish": ["poetry publish --build"],
    "twine upload": ["twine upload dist/*"], "docker push": ["docker push img", "docker image push img"],
    "terraform apply": ["terraform apply", "terraform -chdir=x apply"], "terraform destroy": ["terraform destroy"],
    "kubectl apply": ["kubectl -n x apply -f a.yaml"], "kubectl delete": ["kubectl delete pod x"],
    "curl": ["curl -X POST https://x", "curl -XPOST https://x", "curl -sX PUT https://x", "curl -d a https://x",
             "curl -sSd a https://x", "curl --data-binary @f https://x", "curl --data=a https://x",
             "curl -F f=@a https://x", "curl --form-string a=b https://x", "curl --json {} https://x",
             "curl -T a https://x", "curl --upload-file a https://x", "curl --request=PUT https://x",
             "curl --request PATCH https://x"],
    "wget": ["wget --post-data a https://x", "wget --post-file=a https://x", "wget --method=PUT https://x"],
    "rm": ["rm -rf data", "rm -fr data", "rm -R data", "rm --recursive data", "rm -rf build data", "rm -r",
           "rm -rf /tmp", "rm -rf /tmp/", "rm -rf node_modules/../src", "rm -rf ~/build", "rm -rf /home/u/dist",
           "rm -rf $HOME/build", "rm -rf build/*", 'rm -rf "build', "/bin/rm -rf data",
           "sudo -iu root rm -rf src", "timeout 5 rm -rf src", "cat <(rm -rf src)", "case x in a) rm -rf src;; esac",
           "bash <<EOF\nrm -rf src\nEOF", "rm -rf build && rm -rf src", 'echo "rm -rf data"',
           "rm -rf .skills/cache", "rm -rf build/`echo ..`"],
    "find": ["find . -delete", "find . \\( -name a \\) -delete", "find . -exec rm {} +",
             "find . -execdir /bin/rm -f {} \\;", "find . -ok rm {} \\;", "find . -okdir rm {} +"],
    "git clean": ["git clean -fdx", "git clean -df", "git clean --force"],
    "git branch": ["git branch -D x", "git branch --delete --force x", "git branch -df x"],
    "psql": ["psql <<EOF\nDROP TABLE x;\nEOF", 'psql -c "truncate orders"', 'echo "drop schema s" | psql',
             'psql -c "DROP DATABASE app"'],
    "sqlite3": ['sqlite3 app.db "DROP TABLE users;"', 'sqlite3 app.db "DELETE FROM t WHERE id=1; DELETE FROM u;"'],
    "mysql": ['mysql -e "delete from orders"', "mysql -e 'TRUNCATE TABLE t'"],
    "git reset": ["git reset --hard", "git reset $(git merge-base a b) --hard", "git reset --merge",
                  "git reset --keep HEAD~1", "git -C sub reset --hard", "echo hallo && git reset --hard"],
    "git checkout": ["git checkout -- a.txt", "git checkout .", "git checkout -f x", "git checkout --force x"],
    "git restore": ["git restore a", "git restore --staged --worktree a", "git restore -SW a", "git restore ."],
    "git switch": ["git switch -f x", "git switch --discard-changes x", "git switch --force x"],
    "git stash drop": ["git stash drop", "git stash drop stash@{1}"], "git stash clear": ["git stash clear"],
}
MISSES = {
    "git push": ["git pull", "git status"],
    "gh pr merge": ["gh pr view 12"], "gh release create": ["gh release list"], "gh pr create": ["gh pr list"],
    "gh pr comment": ["gh pr view 3 --comments"], "gh pr close": ["gh pr checks 3"], "gh pr review": ["gh pr diff"],
    "gh pr edit": ["gh pr status"], "gh issue create": ["gh issue list"], "gh issue close": ["gh issue view 4"],
    "gh issue comment": ["gh issue view 4 --comments"], "gh repo delete": ["gh repo view o/r"],
    "gh release delete": ["gh release view v1"],
    "gh api": ["gh api repos/o/r/pulls", "gh api -X GET repos/o/r", "gh api --method get x"],
    "npm publish": ["npm install"], "yarn publish": ["yarn add x"], "pnpm publish": ["pnpm install"],
    "cargo publish": ["cargo build"], "uv publish": ["uv sync"], "poetry publish": ["poetry install"],
    "twine upload": ["twine check dist/*"], "docker push": ["docker pull img"], "terraform apply": ["terraform plan"],
    "terraform destroy": ["terraform plan -destroy"], "kubectl apply": ["kubectl get pods"],
    "kubectl delete": ["kubectl describe pod x"],
    "curl": ["curl https://x", "curl -X GET https://x", "curl -XHEAD https://x", "curl -I https://x",
             "curl -sSfL -o out https://x", "curl -H 'X-Data: 1' https://x"],
    "wget": ["wget https://x", "wget -O f https://x"],
    "rm": ["rm -rf build dist .venv", "rm -rf .skills/cache/x", "rm a.txt", "rm -f a.txt", "rm -rf /tmp/x",
           "rm -rf ./a/__pycache__ .pytest_cache sub/node_modules", "rm -rf -- build", "format x",
           "git commit -m \"$(cat <<'EOF'\nrm -rf data\nEOF\n)\""],
    "find": ["find . -exec grep x {} +", "find . -name '*.py'", "find . -exec echo rmdir {} +"],
    "git clean": ["git clean -n", "git clean -dn"], "git branch": ["git branch -d x", "git branch neu"],
    "psql": ['psql -c "SELECT 1"', 'echo "DROP TABLE x"', 'psql -c "DROP VIEW v"'],
    "sqlite3": ['sqlite3 app.db "DELETE FROM t WHERE id=1;"'],
    "mysql": ['mysql -e "delete from orders where id = 1"'],
    "git reset": ["git reset HEAD~1", "git reset --soft HEAD~1"],
    "git checkout": ["git checkout -b feature", "git checkout main", "git checkout fix-foo"],
    "git restore": ["git restore --staged a", "git restore -S a"],
    "git switch": ["git switch x", "git switch -c neu"],
    "git stash drop": ["git stash list", "git stash"], "git stash clear": ["git stash pop"],
}
NO_PROGRAM = ["ls", "ls -la", "pytest -q", "echo hallo && python -m pytest -q", "cat a.txt | head", "",
              "make clean", "echo DROP TABLE x"]


def test_guard_commands(work, monkeypatch):
    table = {command: category for category, command, _ in dl.GUARD_PATTERNS}
    assert set(HITS) == set(MISSES) == set(table)
    # außer im Push-Fall startet guard keinen Subprozess
    calls = []

    def spy(*args, **kwargs):
        calls.append(args)
        raise AssertionError("subprocess")
    with monkeypatch.context() as patch:
        patch.setattr(dl.subprocess, "run", spy)
        patch.setattr(dl, "repo_root", spy)
        for command in NO_PROGRAM:
            assert run(command, work) == "", command
        for name, category in table.items():
            if name == "git push":
                continue
            for command in HITS[name]:
                why = reason(run(command, work))
                assert why.startswith(f"decide: {category} — ") and why.endswith(": " + ALWAYS), (command, why)
                assert dl.guard_decision(command, work) == (category, ALWAYS), command
            for command in MISSES[name]:
                assert run(command, work) == "", command
                assert dl.guard_decision(command, work) is None, command
    assert calls == []
    for command in HITS["git push"]:
        assert dl.guard_decision(command, work) == ("push", ALWAYS), command
    for command in MISSES["git push"]:
        assert dl.guard_decision(command, work) is None, command

    # ein anderes Muster geht dem Push vor
    assert dl.guard_decision("git push origin x && rm -rf src", work) == ("data-delete", ALWAYS)
    # der Grund nennt den getroffenen Befehl, höchstens 80 Zeichen
    assert reason(run("echo hallo && git reset --hard", work)) == "decide: unsaved-work — git reset --hard: " + ALWAYS
    why = reason(run("rm -rf data " + " ".join(f"datei{n}" for n in range(40)), work))
    shown = why[len("decide: data-delete — "):-len(": " + ALWAYS)]
    assert len(shown) == 80 and shown.endswith("…") and shown.startswith("rm -rf data datei0"), shown


def test_guard_precheck_is_one_regex():
    """Vorprüfung: ein Regex an einer Stelle, aus den Programmnamen der Tabelle."""
    source = (SKILL_DIR / "scripts" / "decide_log.py").read_text(encoding="utf-8")
    assert source.count("_PROGRAM_RE.search(") == 1
    programs = {command.split()[0] for _, command, _ in dl.GUARD_PATTERNS}
    assert {name for name in programs if dl._PROGRAM_RE.search(name)} == programs
    assert not dl._PROGRAM_RE.search("format gitlab finder rmdir")


# --- eigene Fehler ---------------------------------------------------------------------

def test_guard_errors(work, monkeypatch, capsys):
    for text in ("", "   ", "kein json", "[1, 2]", json.dumps({"tool_name": "Bash"}),
                 json.dumps({"tool_input": {"command": 3}}), json.dumps({"tool_input": "rm -rf data"})):
        data = json.loads(dl.guard(text))
        assert set(data) == {"systemMessage"}, text
        assert data["systemMessage"].startswith("[decide] Hook ungeprüft — "), data
    # über main: Exit 0, Antwort auf stdout
    for text, expect in (("kein json", "system"), ("", "system"), (json.dumps({"cwd": str(work)}), "system"),
                         (payload("rm -rf data", work), "ask"), (payload("ls", work), "")):
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8"))
        assert dl.main(["guard"]) == 0
        out = capsys.readouterr().out
        if expect == "ask":
            assert reason(out.strip()).startswith("decide: data-delete")
        elif expect == "system":
            assert "Hook ungeprüft" in json.loads(out)["systemMessage"], text
        else:
            assert out == ""

    # ein Fehler von shlex im Push-Teil: Rückfrage „Befehl nicht schlicht“
    assert reason(run('git push origin "x', work)).endswith(": " + PLAIN)

    def broken(text, *args, **kwargs):
        raise ValueError("No closing quotation")
    with monkeypatch.context() as patch:
        patch.setattr(dl.shlex, "split", broken)
        assert dl.guard_decision("git push origin x", work) == ("push", PLAIN)

    # eine unerwartete Ausnahme hält nichts an
    def boom(*args, **kwargs):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(dl, "_guard_hit", boom)
    data = json.loads(run("rm -rf data", work))
    assert data == {"systemMessage": "[decide] Hook ungeprüft — RuntimeError: kaputt"}, data


# --- Gleichlauf mit der Reference ------------------------------------------------------

def reference_commands():
    section = REVERSIBILITY.read_text(encoding="utf-8").split("## Befehle, die guard erkennt", 1)[1]
    section = section.split("\n## ", 1)[0]
    found = {}
    for line in (line for line in section.splitlines() if line.startswith("| `")):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        category, command = (re.fullmatch(r"`([^`]+)`", cell).group(1) for cell in cells[:2])
        assert command not in found, command
        found[command] = category
    return found, section


def test_guard_table_matches_reference():
    table, section = reference_commands()
    assert table == {command: category for category, command, _ in dl.GUARD_PATTERNS}
    assert len(table) == len(dl.GUARD_PATTERNS) >= 40
    assert set(table.values()) == {"push", "external", "data-delete", "unsaved-work"}
    assert {c.split()[0] for c in table} == {
        "git", "gh", "rm", "curl", "wget", "psql", "sqlite3", "mysql", "npm", "twine", "docker", "terraform", "kubectl",
        "find", "yarn", "pnpm", "cargo", "uv", "poetry"}
    # der Text um die Tabelle beschreibt die neue Fassung, nicht den alten Parser
    flat = " ".join(section.split())
    for stale in ("Befehl nicht zerlegbar", "Wrapper", "einmal je Verzeichnis", "ausgeglichene Anführungszeichen"):
        assert stale not in flat, stale
    for current in ("Befehl nicht schlicht", "Commit-Vorlage", "`eval`", "kein Python"):
        assert current in flat, current
    head = (SKILL_DIR / "scripts" / "decide_log.py").read_text(encoding="utf-8").split('"""')[1]
    assert "GUARD_PATTERNS" in head and "GUARD_COMMANDS" not in head
    assert "GUARD_COMMANDS" not in REVERSIBILITY.read_text(encoding="utf-8")


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
def test_hook_snippet(work, tmp_path):
    command = snippet_command()
    assert '"$CLAUDE_PROJECT_DIR/.claude/hooks/decide_log.py" guard' in command
    assert "skills/decide/scripts/" not in command and "version_info" not in command

    def hook(text, path=None):
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(work), "COUNT": str(tmp_path / "count")}
        if path is not None:
            env["PATH"] = str(path)
        return subprocess.run([shutil.which("bash"), "-c", command], cwd=work, input=payload(text, work),
                              capture_output=True, text=True, env=env, timeout=60)

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
    assert done.returncode == 0 and reason(done.stdout.strip()).endswith(ALWAYS), done

    # genau ein Python-Start: python3, sonst python; fehlen beide, die Meldung „kein Python“
    counted, only_python, empty = tmp_path / "counted", tmp_path / "only-python", tmp_path / "empty"
    for folder in (counted, only_python, empty):
        folder.mkdir()
    (counted / "python3").write_text(f'#!/bin/sh\necho start >> "$COUNT"\nexec "{sys.executable}" "$@"\n',
                                     encoding="utf-8")
    (counted / "python3").chmod(0o755)
    (counted / "python").symlink_to(counted / "python3")
    (only_python / "python").symlink_to(sys.executable)
    done = hook("rm -rf data", counted)
    assert done.returncode == 0 and reason(done.stdout.strip()).startswith("decide: data-delete"), done
    assert (tmp_path / "count").read_text(encoding="utf-8") == "start\n"
    done = hook("rm -rf data", only_python)
    assert done.returncode == 0 and reason(done.stdout.strip()).startswith("decide: data-delete"), done
    done = hook("rm -rf data", empty)
    assert done.returncode == 0, done
    assert json.loads(done.stdout) == {"systemMessage": "[decide] Hook ungeprüft — kein Python"}


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
