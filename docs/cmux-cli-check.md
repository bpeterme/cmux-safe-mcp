# cmux CLI check for the pane tools

The pane tools (`allow = panes`) call the cmux CLI with the exact arguments
below. The tests pin them with a fake cmux (`PaneTests` in
`tests/test_cmux_safe_mcp.py`); this page checks them against a real cmux.

## What each tool runs

`<ws>` is the session's workspace ref (`workspace:N`), `<own>` its own pane
(`CMUX_SURFACE_ID`), `<p>` a pane the session opened (`surface:N`).

| Tool | cmux call |
|------|-----------|
| `cmux_pane_open` | `new-split right\|down --workspace <ws> --surface <own> --command "exec <command> \|\| exit"` |
| `cmux_pane_open` (with `label`) | then `rename-tab --workspace <ws> --surface <p> <label>` |
| `cmux_pane_send` | `send --workspace <ws> --surface <p> <text>`, then `send-key ... enter` (unless `enter` is false) |
| `cmux_pane_key` | `send-key --workspace <ws> --surface <p> enter\|escape\|tab\|up\|down\|ctrl-c` |
| `cmux_pane_read` | `read-screen --workspace <ws> --surface <p> --lines <1-200>` |
| `cmux_pane_close` | `close-surface --workspace <ws> --surface <p> --force` |
| (every pane tool) | `read-screen --workspace <ws> --surface <p> --lines 1` to see if a pane still exists |

## Checked against the cmux source (2026-11-17)

Checked in `CLI/cmux.swift`, `CLI/CMUXCLI+Paste.swift` and
`Packages/macOS/CmuxTerminal/.../TerminalSurface+Input.swift` of
`manaflow-ai/cmux` (main). The docs page (cmux.com/docs/api) lists only
`send`, `send-key` and `new-split`.

- All six commands take `--workspace` and `--surface`.
- `close-surface --force` exists (sent as `force` to `surface.close`).
- Key names: `enter`, `escape`, `tab`, `up`, `down` and `ctrl-c` are all in
  cmux's key table (it also accepts `esc`, `ctrl+c` and others).
- `new-split` prints `OK surface:N workspace:N`; `--command` runs the
  command in a shell that stays open, hence `exec ... || exit`.
- `rename-tab` takes the title as the last argument (or `--title`).
- `read-screen --lines N` returns the last N lines, scrollback included.
- `send` and `send-key` without `--force` refuse to type into an agent
  prompt that holds a draft or an open question. The pane tools never pass
  `--force`, so this check applies to them.
- `send` turns the two characters `\n` and `\r` into Enter and `\t` into
  Tab, and offers no way to escape them. `cmux_pane_send` therefore refuses
  text that contains them.

## Checklist on the Mac

Run these in a cmux terminal, one at a time, and compare with the expected
result in the comment. In the `WS=` and `P=` lines, replace `workspace:3` and
`surface:7` with the refs the command just above prints.

```sh
cmux list-workspaces                                                            # the selected line has this workspace's ref
WS=workspace:3
cmux new-split right --workspace "$WS" --surface "$CMUX_SURFACE_ID" --command "exec zsh || exit"   # a pane opens; prints OK surface:N workspace:N
P=surface:7
cmux rename-tab --workspace "$WS" --surface "$P" cli-check                      # the new pane's tab reads cli-check
cmux send --workspace "$WS" --surface "$P" "echo hello"                         # echo hello typed, not run
cmux send-key --workspace "$WS" --surface "$P" enter                            # it runs: hello
cmux send-key --workspace "$WS" --surface "$P" up                               # echo hello is back on the prompt
cmux send-key --workspace "$WS" --surface "$P" escape                           # no error
cmux send-key --workspace "$WS" --surface "$P" ctrl-c                           # the prompt line is dropped (^C)
cmux send --workspace "$WS" --surface "$P" "ech"                                # ech typed
cmux send-key --workspace "$WS" --surface "$P" tab                              # completes to echo (or lists matches)
cmux send-key --workspace "$WS" --surface "$P" down                             # no error
cmux send-key --workspace "$WS" --surface "$P" ctrl-c                           # the prompt is empty again
cmux send --workspace "$WS" --surface "$P" 'echo a\nb'                          # runs "echo a" at once: why pane_send refuses \n
cmux read-screen --workspace "$WS" --surface "$P" --lines 5                     # the last 5 lines of the pane
cmux close-surface --workspace "$WS" --surface "$P" --force                     # the pane closes
cmux read-screen --workspace "$WS" --surface "$P" --lines 1                     # fails: surface not found
```

If a line does not do what its comment says, note the line and cmux's output:
the pane tool that uses that call needs a fix.
