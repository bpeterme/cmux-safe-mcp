# cmux-safe-mcp

An MCP server with only the safe parts of [cmux](https://cmux.com): your agent
can list, open, arrange and label workspaces and tell you when it's done, but
it can never type into your terminals, run a command of its choice or read
their screens. If you allow it, it can run a team: open panes with commands
you named, and drive only those.

Made for agents you don't want at your keyboard, like an agent in a container
([cbox](https://github.com/bpeterme/claudebox)) or any agent with its
permission prompts turned off.

## Why

cmux can be scripted through its CLI, and existing cmux MCP servers expose all
of it: `send`, `send-key`, `read-screen`, the browser, `respawn-pane`. Any one
of these lets an agent run commands on your Mac, or read what other projects
show in their terminals. None of those servers can switch tools off.

cmux-safe-mcp offers a short, fixed list of actions instead. Every action maps
to one fixed cmux command, and the agent only fills in checked values: a
workspace ref, a title, a color.

## Tools

| Tool | What it does |
|------|--------------|
| `cmux_list` | All workspaces: ref, title, color, description, folder, pinned, selected; `this_session` marks the agent's own |
| `cmux_open` | Opens a repo in a new workspace named after it, colored, in `~/Workspace/<name>`. Clones it first when missing |
| `cmux_select` | Switches to a workspace |
| `cmux_rename`, `cmux_color`, `cmux_describe`, `cmux_pin` | Labels and arranges workspaces |
| `cmux_notify` | Shows you a notification ("tests pass", "needs your input") |
| `cmux_status`, `cmux_progress` | A short status or a progress bar in the agent's own sidebar entry |
| `cmux_close` | Closes a workspace. **Off** unless your settings say `allow = close`; never the agent's own |
| `cmux_pane_open`, `cmux_pane_list` | Opens a pane next to the agent's own that runs a command you named in `[commands]`; lists the panes it opened. **Off** unless `allow = panes` |
| `cmux_pane_send`, `cmux_pane_key`, `cmux_pane_read`, `cmux_pane_close` | Types a line, presses a key (Enter, Escape, Tab, Up, Down, Ctrl-C), reads the screen, closes — only in panes this session opened |

**Never offered:** typing, keys or reading in any terminal the agent did not
open itself (its own included), pasting, running a command of its choice (new
workspaces and panes run only commands from *your* settings), reading
selections, screenshots, recordings, the browser, ssh, hooks, raw socket calls,
or settings.

**Not passed on:** cmux's workspace list also holds the latest messages of
agents in each workspace. `cmux_list` leaves them out.

## Install

Needs macOS with cmux, `python3` and `git` (both come with the Command Line
Tools). There are no other dependencies; the server is one file.

### Homebrew (recommended)

```sh
brew tap bpeterme/cmux-safe-mcp
brew install bpeterme/cmux-safe-mcp/cmux-safe-mcp
cmux-safe-mcp version
```

### Manual

```sh
curl -fsSL -o ~/.local/bin/cmux-safe-mcp \
  https://raw.githubusercontent.com/bpeterme/cmux-safe-mcp/main/cmux-safe-mcp
chmod +x ~/.local/bin/cmux-safe-mcp
```

With a manual install, use the full path (`/Users/<you>/.local/bin/cmux-safe-mcp`)
as the command in the MCP entries below.

**Switching to Homebrew?** Remove the old file or symlink first, so it doesn't
shadow the Homebrew one: `rm ~/.local/bin/cmux-safe-mcp`. Then set the command
in your MCP entries to plain `cmux-safe-mcp`.

### 1. Settings

Create `~/.config/cmux-safe-mcp/config` (see [`config.example`](config.example)):

```ini
[settings]
folder  = ~/Workspace          # where repos go
command = cbox                 # optional: what each opened workspace runs (cbox, claude, …)

[github]                       # a git host; the first one is tried first
repos   = my-user/*, my-org/app

[gitlab]
repos   = my-group/*           # * also covers subgroups
clone   = git@gitlab.com:{repo}.git
```

`repos` is the list of what the agent may open.

**A team of agents** (opt-in): let the agent open panes beside its own, for
example one worker agent per task.

```ini
[settings]
allow     = panes
max_panes = 4                  # panes open at once on this Mac (default 4)

[commands]                     # what a pane may run; the agent picks a name
worker    = cbox
```

A pane runs its command with `exec`: it closes when the command ends. Only the
session that opened a pane can type into it, read it or close it; a session
restarted in the same terminal gets its panes back.

**Choose the commands with care:** the agent types into these panes. A command
like `cbox` gives it another agent in a container. A shell (`zsh`) or a host
`claude` without permission prompts gives it your Mac. A bare name like `app` is
enough when a pattern fixes the owner (`my-user/*` → `my-user/app`). When a
repo is on several hosts, the first host that has it wins. Clones use your own
git and ssh setup.

Keep this file where your agent cannot write it. For cbox, `~/.config` is not
visible in containers.

### 2. Let it reach cmux

By default, cmux only accepts processes started in its own terminals. An MCP
server that runs in the background (cbox's relay, for example) is refused. In
cmux's settings, choose **password mode** and set a password: the cmux CLI
then uses the saved password by itself.

Check from a terminal that is *not* cmux (e.g. Terminal.app):

```sh
cmux-safe-mcp check
```

### 3. Add it to your MCP client

- **Claude Code:** `claude mcp add cmux -- cmux-safe-mcp`
- **cbox:** in `~/.config/claudebox/mcp.json`:
  ```json
  { "mcpServers": { "cmux": { "command": "cmux-safe-mcp" } } }
  ```
  cbox starts it on the Mac when the agent connects; the container only gets
  the tools.

## Which workspace is "its own"?

cmux sets `CMUX_WORKSPACE_ID` and `CMUX_SURFACE_ID` in its terminals. An agent
started from a cmux terminal passes them on; so does cbox, per session, even
when several sessions share a container. Without it, cmux-safe-mcp takes the one workspace whose folder is the
folder the client started in. If neither works, the agent can still list and
arrange workspaces, but not notify you or set its status.

## Tests

```sh
bash tests/run.sh
```

The tests use a fake `cmux` and local git repos, so they run anywhere (also on
Linux CI).

## License

MIT
