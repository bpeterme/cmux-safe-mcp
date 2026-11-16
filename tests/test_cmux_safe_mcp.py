"""Tests for cmux-safe-mcp, with a fake cmux CLI and local git "remotes".

Run: python3 -m unittest discover -s tests   (or: bash tests/run.sh)
"""
import importlib.machinery, importlib.util, io, json, os, shutil, subprocess, sys, tempfile, textwrap, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "cmux-safe-mcp")


def load():
    loader = importlib.machinery.SourceFileLoader("cmux_safe_mcp", SCRIPT)
    spec = importlib.util.spec_from_loader("cmux_safe_mcp", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


m = load()

# The fake cmux logs each call (argv and the env cmux-safe-mcp passes) and answers
# like the real one: "OK workspace:<n>" for new-workspace, JSON for the list.
FAKE_CMUX = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "cmux.log"), "a") as f:
        f.write(json.dumps({"argv": sys.argv[1:], "ws": os.environ.get("CMUX_WORKSPACE_ID"),
                            "quiet": os.environ.get("CMUX_QUIET")}) + "\\n")
    if os.path.exists(os.path.join(here, "cmux.fail")):
        sys.stderr.write("Error: ERROR: Access denied - only processes started inside cmux can connect\\n")
        sys.exit(1)
    if sys.argv[1] == "new-workspace":
        print("OK workspace:42")
    elif sys.argv[1] == "list-workspaces":
        print(open(os.path.join(here, "list.json")).read())
    else:
        print("OK")
    """)

OWN_ID = "6B5B72BF-9DFC-4933-8885-E311B461ABD8"


def workspace(ref, title, folder, wid="00000000-0000-0000-0000-000000000000", **kw):
    w = {"ref": ref, "id": wid, "title": title, "custom_color": None, "description": None,
         "current_directory": folder, "pinned": False, "selected": False,
         "latest_conversation_message": "SECRET agent text", "latest_submitted_message": "SECRET prompt",
         "remote": {"state": "disconnected"}}
    w.update(kw)
    return w


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.t, True)
        self.ws = os.path.join(self.t, "ws")
        self.remotes = os.path.join(self.t, "remotes")
        os.makedirs(self.ws)
        self.cmux = os.path.join(self.t, "cmux")
        with open(self.cmux, "w") as f:
            f.write(FAKE_CMUX)
        os.chmod(self.cmux, 0o755)
        self.set_list([workspace("workspace:1", "Project A", "/somewhere/a", wid=OWN_ID),
                       workspace("workspace:2", "Project B", "/somewhere/b")])
        self.env = dict(os.environ)
        self.addCleanup(self.restore_env)
        os.environ.pop("CMUX_WORKSPACE_ID", None)
        os.environ["PWD"] = "/nowhere"
        os.environ["CMUX_SAFE_MCP_CONFIG"] = os.path.join(self.t, "config")
        self.write_config()

    def restore_env(self):
        os.environ.clear()
        os.environ.update(self.env)

    def set_list(self, items):
        with open(os.path.join(self.t, "list.json"), "w") as f:
            json.dump({"window_ref": "window:1", "workspaces": items}, f)

    def write_config(self, settings="", sources=None, folder=None):
        sources = sources if sources is not None else f"""
            [github]
            repos = my-org/*, someone/notes
            clone = {self.remotes}/{{repo}}.git
            """
        with open(os.environ["CMUX_SAFE_MCP_CONFIG"], "w") as f:
            f.write(textwrap.dedent(f"""\
                [settings]
                folder = {folder or self.ws}
                cmux   = {self.cmux}
                {settings}
                """) + textwrap.dedent(sources))

    def remote(self, repo):
        path = os.path.join(self.remotes, repo + ".git")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        subprocess.run(["git", "init", "-q", "--bare", path], check=True)
        return path

    def calls(self):
        try:
            with open(os.path.join(self.t, "cmux.log")) as f:
                return [json.loads(l) for l in f]
        except FileNotFoundError:
            return []

    def call(self, name, args=None):
        return m.call(m.load_config(), name, args or {})

    def refused(self, name, args=None):
        with self.assertRaises(m.Refused) as cm:
            self.call(name, args)
        return str(cm.exception)


class ListTests(Base):
    def test_only_safe_fields_and_no_agent_messages(self):
        out = self.call("cmux_list")
        self.assertEqual([w["workspace"] for w in out["workspaces"]], ["workspace:1", "workspace:2"])
        self.assertEqual(set(out["workspaces"][0]),
                         {"workspace", "title", "color", "description", "folder", "pinned", "selected"})
        self.assertNotIn("SECRET", json.dumps(out))

    def test_marks_this_session_by_cmux_workspace_id(self):
        os.environ["CMUX_WORKSPACE_ID"] = OWN_ID
        out = self.call("cmux_list")
        self.assertTrue(out["workspaces"][0].get("this_session"))
        self.assertNotIn("this_session", out["workspaces"][1])

    def test_marks_this_session_by_folder_when_unique(self):
        os.environ["PWD"] = "/somewhere/b"
        self.assertTrue(self.call("cmux_list")["workspaces"][1].get("this_session"))

    def test_cmux_gets_no_caller_workspace_and_is_quiet(self):
        os.environ["CMUX_WORKSPACE_ID"] = OWN_ID
        self.call("cmux_list")
        self.assertEqual(self.calls()[0], {"argv": ["list-workspaces", "--json"], "ws": None, "quiet": "1"})

    def test_refused_socket_access_says_what_to_do(self):
        open(os.path.join(self.t, "cmux.fail"), "w").close()
        msg = self.refused("cmux_list")
        self.assertIn("Access denied", msg)
        self.assertIn("choose password mode", msg)


class OpenTests(Base):
    def test_clones_and_opens_named_colored_workspace_without_a_command_by_default(self):
        self.remote("my-org/demo")
        out = self.call("cmux_open", {"repo": "my-org/demo"})
        self.assertEqual((out["repo"], out["workspace"], out["cloned"], out["source"]),
                         ("my-org/demo", "workspace:42", True, "github"))
        self.assertIn(out["color"], m.COLORS)
        path = os.path.join(self.ws, "demo")
        self.assertTrue(os.path.isdir(os.path.join(path, ".git")))
        argv = [c["argv"] for c in self.calls()]
        self.assertEqual(argv[0], ["new-workspace", "--name", "demo", "--cwd", os.path.realpath(path)])
        self.assertEqual(argv[1], ["workspace-action", "--action", "set-color", "--color", out["color"],
                                   "--workspace", "workspace:42"])

    def test_command_comes_from_settings_and_existing_clone_is_reused(self):
        self.write_config(settings="command = cbox")
        self.remote("my-org/demo")
        self.call("cmux_open", {"repo": "my-org/demo"})
        out = self.call("cmux_open", {"repo": "demo", "color": "teal"})
        self.assertEqual((out["cloned"], out["color"]), (False, "Teal"))
        self.assertEqual(self.calls()[-2]["argv"][-2:], ["--command", "cbox"])

    def test_agent_cannot_pass_a_command(self):
        self.assertIn("does not take command", self.refused("cmux_open", {"repo": "my-org/demo", "command": "x"}))

    def test_color_is_stable_and_validated(self):
        self.assertEqual(m.color_value("my-org/demo", None), m.color_value("My-Org/Demo", None))
        self.assertEqual(m.color_value(None, "#c0392b"), "#C0392B")
        with self.assertRaises(m.Refused):
            m.color_value(None, "red; rm -rf ~")

    def test_refuses_repos_outside_the_patterns_and_odd_names(self):
        for repo in ["evil/demo", "my-org/../x", "my-org/-x", "my-org/demo.git", "my-org/a b", "my-org//x",
                     "/my-org/x", "my-org/x/", "-x", ".x", "", 7]:
            self.refused("cmux_open", {"repo": repo})
        self.assertEqual(self.calls(), [])
        self.assertEqual(os.listdir(self.ws), [])

    def test_existing_folder_of_another_repo_is_left_alone(self):
        other = self.remote("my-org/other")
        subprocess.run(["git", "clone", "-q", other, os.path.join(self.ws, "demo")], check=True,
                       stderr=subprocess.DEVNULL)
        os.makedirs(os.path.join(self.ws, "plain"))
        self.assertIn("exists and is not a clone of", self.refused("cmux_open", {"repo": "my-org/demo"}))
        self.refused("cmux_open", {"repo": "my-org/plain"})
        self.assertEqual(self.calls(), [])

    def test_bare_name_with_two_owners_in_one_source_asks_unless_cloned(self):
        self.remote("my-org/notes")
        theirs = self.remote("someone/notes")
        self.assertIn("could be my-org/notes or someone/notes", self.refused("cmux_open", {"repo": "notes"}))
        subprocess.run(["git", "clone", "-q", theirs, os.path.join(self.ws, "notes")], check=True,
                       stderr=subprocess.DEVNULL)
        self.assertEqual(self.call("cmux_open", {"repo": "notes"})["repo"], "someone/notes")

    def test_bare_name_without_a_fixed_owner_asks_for_one(self):
        self.write_config(sources=f"""
            [any]
            repos = */app
            clone = {self.remotes}/{{repo}}.git
            """)
        self.assertIn("no repos setting fixes the owner", self.refused("cmux_open", {"repo": "app"}))

    def test_same_repo_on_two_hosts_takes_the_first_that_has_it(self):
        gl = os.path.join(self.t, "gitlab")
        self.write_config(sources=f"""
            [github]
            repos = my-org/*
            clone = {self.remotes}/{{repo}}.git
            [gitlab]
            repos = my-org/*
            clone = {gl}/{{repo}}.git
            """)
        os.makedirs(os.path.join(gl, "my-org"))
        subprocess.run(["git", "init", "-q", "--bare", os.path.join(gl, "my-org", "tool.git")], check=True)
        out = self.call("cmux_open", {"repo": "tool"})
        self.assertEqual((out["source"], out["repo"]), ("gitlab", "my-org/tool"))
        self.assertIn("could not clone — github:", self.refused("cmux_open", {"repo": "missing"}))
        self.assertIn("source must be one of", self.refused("cmux_open", {"repo": "tool", "source": "x"}))

    def test_gitlab_subgroups_open_into_their_last_part(self):
        self.write_config(sources=f"""
            [gitlab]
            repos = my-group/*
            clone = {self.remotes}/{{repo}}.git
            """)
        self.remote("my-group/sub/app")
        out = self.call("cmux_open", {"repo": "my-group/sub/app"})
        self.assertEqual(out["folder"], m.tilde(os.path.join(self.ws, "app")))
        self.assertTrue(os.path.isdir(os.path.join(self.ws, "app", ".git")))


class WorkspaceToolTests(Base):
    def test_actions_map_to_fixed_cmux_commands(self):
        self.call("cmux_select", {"workspace": "workspace:2"})
        self.call("cmux_rename", {"workspace": "workspace:2", "title": "New name"})
        self.call("cmux_color", {"workspace": "workspace:2", "color": "navy"})
        self.call("cmux_color", {"workspace": "workspace:2", "color": None})
        self.call("cmux_describe", {"workspace": "workspace:2", "description": "Ship it"})
        self.call("cmux_describe", {"workspace": "workspace:2", "description": None})
        self.call("cmux_pin", {"workspace": "workspace:2", "pinned": True})
        w = ["--workspace", "workspace:2"]
        self.assertEqual([c["argv"] for c in self.calls()], [
            ["select-workspace"] + w,
            ["workspace-action", "--action", "rename", "--title", "New name"] + w,
            ["workspace-action", "--action", "set-color", "--color", "Navy"] + w,
            ["workspace-action", "--action", "clear-color"] + w,
            ["workspace-action", "--action", "set-description", "--description", "Ship it"] + w,
            ["workspace-action", "--action", "clear-description"] + w,
            ["workspace-action", "--action", "pin"] + w])

    def test_arguments_are_checked(self):
        for args in [{"workspace": "2"}, {"workspace": "workspace:2; ls"}, {"workspace": "--window"},
                     {"workspace": "workspace:2", "title": "-x"}, {"workspace": "workspace:2", "title": "a\nb"},
                     {"workspace": "workspace:2", "title": "x" * 101}, {"workspace": "workspace:2"}]:
            self.refused("cmux_rename", args)
        self.refused("cmux_pin", {"workspace": "workspace:2", "pinned": "yes"})
        self.assertIn("does not take", self.refused("cmux_select", {"workspace": "workspace:2", "x": 1}))
        self.assertEqual(self.calls(), [])

    def test_unsafe_cmux_commands_are_no_tools(self):
        names = {t["name"] for t in m.tool_specs(m.load_config())}
        for bad in ["cmux_send", "cmux_send_key", "cmux_read_screen", "cmux_close", "cmux_browser"]:
            self.assertNotIn(bad, names)
        self.assertIn("unknown tool", self.refused("cmux_send", {"text": "rm -rf ~"}))


class OwnWorkspaceTests(Base):
    def test_notify_status_progress_target_this_session(self):
        os.environ["CMUX_WORKSPACE_ID"] = OWN_ID
        self.call("cmux_notify", {"title": "Done", "body": "Tests pass"})
        self.call("cmux_status", {"value": "tests running"})
        self.call("cmux_status", {"value": None})
        self.call("cmux_progress", {"value": 0.5, "label": "build"})
        self.call("cmux_progress", {"value": None})
        own = ["--workspace", "workspace:1"]
        self.assertEqual([c["argv"] for c in self.calls() if c["argv"][0] != "list-workspaces"], [
            ["notify", "--title", "Done", "--body", "Tests pass"] + own,
            ["set-status", "agent", "tests running"] + own,
            ["clear-status", "agent"] + own,
            ["set-progress", "0.500", "--label", "build"] + own,
            ["clear-progress"] + own])

    def test_unknown_own_workspace_is_refused(self):
        self.assertIn("workspace is unknown", self.refused("cmux_notify", {"title": "x"}))
        os.environ["CMUX_WORKSPACE_ID"] = OWN_ID
        self.refused("cmux_progress", {"value": 2})
        self.refused("cmux_status", {"key": "a b", "value": "x"})

    def test_close_is_opt_in_and_never_the_own_workspace(self):
        self.assertIn("unknown tool", self.refused("cmux_close", {"workspace": "workspace:2"}))
        self.write_config(settings="allow = close")
        os.environ["CMUX_WORKSPACE_ID"] = OWN_ID
        self.assertIn("own workspace", self.refused("cmux_close", {"workspace": "workspace:1"}))
        self.assertIn("own workspace", self.refused("cmux_close", {"workspace": OWN_ID}))
        self.assertEqual(self.call("cmux_close", {"workspace": "workspace:2"}), {"closed": "workspace:2"})
        self.assertEqual(self.calls()[-1]["argv"], ["close-workspace", "--workspace", "workspace:2"])


class ConfigTests(Base):
    def test_problems_name_the_line_to_fix(self):
        cases = [("bogus = 1", "", "[settings] bogus is unknown"),
                 ("allow = send", "", "allow = send is unknown"),
                 ("", "[gh]\nrepos = my-org", "is not an owner/name pattern"),
                 ("", "[gh]\nrepos = a/*\nclone = git@x:fixed.git", "clone must contain {repo}"),
                 ("", "[gh]\nrepos = a/*\ncommand = rm", "[gh] command is unknown"),
                 ("", "[gh]\n", "repos is missing"),
                 ("", "[GH]\nrepos = a/*", "a name may only contain")]
        for settings, sources, want in cases:
            self.write_config(settings=settings, sources=sources)
            with self.assertRaises(m.Refused) as cm:
                m.load_config()
            self.assertIn(want, str(cm.exception), (settings, sources))

    def test_folder_must_be_absolute(self):
        self.write_config(folder="relative/path")
        with self.assertRaises(m.Refused) as cm:
            m.load_config()
        self.assertIn("folder must be an absolute path", str(cm.exception))

    def test_missing_settings_file(self):
        os.environ["CMUX_SAFE_MCP_CONFIG"] = os.path.join(self.t, "nope")
        with self.assertRaises(m.Refused) as cm:
            m.load_config()
        self.assertIn("no settings file", str(cm.exception))


class ProtocolTests(Base):
    def rpc(self, *msgs):
        p = subprocess.run([sys.executable, SCRIPT], input="".join(json.dumps(x) + "\n" for x in msgs),
                           capture_output=True, text=True, timeout=30, env=os.environ)
        return [json.loads(l) for l in p.stdout.splitlines()]

    def test_initialize_list_call_and_errors(self):
        out = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                       {"jsonrpc": "2.0", "method": "notifications/initialized"},
                       {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                       {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "cmux_list"}},
                       {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                        "params": {"name": "cmux_send", "arguments": {"text": "x"}}},
                       {"jsonrpc": "2.0", "id": 5, "method": "bogus"})
        self.assertEqual([r["id"] for r in out], [1, 2, 3, 4, 5])
        self.assertEqual(out[0]["result"]["serverInfo"]["name"], "cmux-safe-mcp")
        self.assertIn("cmux_open", [t["name"] for t in out[1]["result"]["tools"]])
        self.assertFalse(out[2]["result"]["isError"])
        self.assertIn("workspace:2", out[2]["result"]["content"][0]["text"])
        self.assertTrue(out[3]["result"]["isError"])
        self.assertEqual(out[4]["error"]["code"], -32601)

    def test_bad_settings_show_up_as_tool_errors(self):
        self.write_config(settings="bogus = 1")
        out = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "cmux_list"}})
        self.assertTrue(out[0]["result"]["isError"])
        self.assertIn("bogus is unknown", out[0]["result"]["content"][0]["text"])

    def test_check_command(self):
        p = subprocess.run([sys.executable, SCRIPT, "check"], capture_output=True, text=True, timeout=30,
                           env=os.environ)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("cmux answers: 2 workspaces", p.stdout)


if __name__ == "__main__":
    unittest.main()
