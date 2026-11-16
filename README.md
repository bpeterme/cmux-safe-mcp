# cmux-safe-mcp

An MCP server with only the safe parts of [cmux](https://cmux.com): your agent
can list, open, arrange and label workspaces and tell you when it's done, but
it can never type into a terminal, run a command or read a screen.

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

**Never offered:** typing or pasting into terminals, keys, running commands
(the only command a new workspace runs is the one in *your* settings), reading
screens or selections, screenshots, recordings, the browser, ssh, hooks, raw
socket calls, or settings.

**Not passed on:** cmux's workspace list also holds the latest messages of
agents in each workspace. `cmux_list` leaves them out.

## Install

Needs macOS with cmux, `python3` and `git`. There are no other dependencies;
the server is one file.

```sh
curl -fsSL -o ~/.local/bin/cmux-safe-mcp \
  https://raw.githubusercontent.com/bpeterme/cmux-safe-mcp/main/cmux-safe-mcp
chmod +x ~/.local/bin/cmux-safe-mcp
```

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

`repos` is the list of what the agent may open. A bare name like `app` is
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

- **Claude Code:** `claude mcp add cmux -- ~/.local/bin/cmux-safe-mcp`
- **cbox:** in `~/.config/claudebox/mcp.json`:
  ```json
  { "mcpServers": { "cmux": { "command": "/Users/<you>/.local/bin/cmux-safe-mcp" } } }
  ```
  cbox starts it on the Mac when the agent connects; the container only gets
  the tools.

## Which workspace is "its own"?

cmux sets `CMUX_WORKSPACE_ID` in its terminals. An agent started from a cmux
terminal (or cbox, whose relay inherits that terminal's environment) passes it
on. Without it, cmux-safe-mcp takes the one workspace whose folder is the
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
