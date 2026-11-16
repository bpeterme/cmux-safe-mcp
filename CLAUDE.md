# cmux-safe-mcp — instructions for Claude

An MCP server with only the safe parts of cmux, for agents that must not control
the user's terminal (e.g. agents in cbox containers). One file, `cmux-safe-mcp`,
Python stdlib only. cbox runs it on the Mac through its host MCP relay
(`~/.config/claudebox/mcp.json`); any other MCP client can run it too.

It follows the same standards as the companyon apps (claudebox, flux,
claudedot), but it is a standalone tool, not one of them: it must keep working
without cbox, and nothing in it may depend on cbox.

## Safety rules — never weaken without the user's explicit OK

1. **No tool that controls or reads terminals.** Never offer typing, pasting, keys,
   running commands, reading screens or selections, screenshots, recordings, the
   browser, ssh, hooks, raw socket calls (`rpc`), sudo or settings.
2. **The start command comes only from the settings** (`[settings] command =`),
   never from a tool argument.
3. **Every tool maps to fixed cmux argv lists**: no shell. Values from the agent
   are checked before use: workspace refs by regex, text without control
   characters, never starting with `-`, length limits.
4. **`cmux_list` passes on only `LIST_FIELDS`.** cmux also reports the latest
   messages of agents in each workspace; those never leave this server.
5. **No default targets:** drop `CMUX_WORKSPACE_ID`/`CMUX_SURFACE_ID` when calling
   cmux, and pass `--workspace` explicitly.
6. **Riskier actions are opt-in** (`allow =`, see `EXTRAS`), off by default. Close
   never closes the agent's own workspace.

## Working mode

- Before implementing, check consistency with the existing code: names, style,
  structure, approach.
- User-friendliness over technical thinking: every error says what to do next.
- After every fix or feature, decide which tests to add or change, and add them.
- English only, US spelling, in code, comments, docs, commits and errors.
- No personal data in code, tests or docs: no real usernames, paths, workspace
  titles or ids. Use placeholders (`my-user/*`, `/somewhere/a`).
- Keep it one file, stdlib only, runnable with the macOS system Python (3.9+).

## Tests

- `bash tests/run.sh`: a fake `cmux` and local git repos, so no cmux is needed.
- While iterating, run single tests:
  `python3 -B -m unittest tests.test_cmux_safe_mcp.OpenTests -v`.
  Run the full suite once, right before committing. Never commit with failures.
- CI: GitHub Actions (macOS with Python 3.9 and 3.x, Ubuntu with 3.x). Inside cbox,
  read CI through `$WARDEN_GITHUB_API` with curl and jq; `gh` stays logged out.

## Git workflow (same as the companyon apps)

- **Session start:** `git fetch origin`, make sure you are on `dev`, pull.
- **All commits go to `dev`.** Never commit on `main`, whatever the size.
- **Commit and push are one step:** never leave unpushed commits. After every
  push, check CI and fix failures before calling the task done.
- **Commit messages:** a type prefix (`feat:`, `fix:`, `test:`, `ci:`, `docs:`),
  one topic per commit.
- **Identity:** GitHub refuses pushes that expose the user's real email. Commit
  with `git -c user.email="48397193+bpeterme@users.noreply.github.com"
  -c user.name="bpeterme" commit ...`. Never edit the git config.
- **Merging into `main` only when the user asks:**
  `git merge --no-ff dev -m "Merge dev: <summary>"`, push `main`, switch back to
  `dev`. Never fast-forward. Never merge `main` back into `dev`; `main` having
  more commits (the merges) is normal.
- Never skip hooks, never force-push, never rewrite pushed history.

## Commands for the user's Mac

- The user runs them in their own terminal: no `!` prefix.
- Use `git --no-pager` for `log`, `diff` and `show`: no pager to quit.
- Commits made on the Mac also need the noreply `-c` override above.

## Releases

Every push to `main` releases automatically (`.github/workflows/release.yml`,
same as claudebox): once the Test workflow passes, it tags `YYYY.MM.DD.N`,
creates the GitHub release and updates the formula in the tap
`bpeterme/homebrew-cmux-safe-mcp`. Never ask the user to tag by hand.

- The version lives only in the tag: the source keeps `VERSION = "dev"`, and
  the formula replaces it (`HEAD-<sha>` for `brew install --HEAD`).
- `Formula/cmux-safe-mcp.rb` here is head-only; the release adds `url` and
  `sha256` before `license "MIT"` and rewrites the test. Keep those lines as
  they are (a test checks them).
- PyPI (`uvx`) only if other users show up.
