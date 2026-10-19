
"""Regression test: the TUI launcher must not spend time on plugin discovery.

`hermes --tui` just spawns a Node process; the spawned tui_gateway backend
performs its own plugin discovery. Running discover_plugins() in the
launcher added ~0.5s to every `hermes --tui` startup for work the backend
then redoes. Plain chat must still discover plugins.
"""

from __future__ import annotations

from argparse import Namespace
import sys
import types

from hermes_cli import main as main_mod


def _install_discover_spy(monkeypatch):
    calls = []

    def _discover():
        calls.append("discover")

    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.plugins",
        types.SimpleNamespace(
            discover_plugins=_discover,
        ),
    )
    return calls


def _args(**overrides):
    base = {
        "accept_hooks": False,
        "yolo": False,
        "safe_mode": False,
        "command": None,
        "query": None,
        "image": None,
    }
    base.update(overrides)
    return Namespace(**base)


def test_plugin_discovery_skipped_for_tui_launch(monkeypatch):
    calls = _install_discover_spy(monkeypatch)
    main_mod._prepare_agent_startup(_args(tui=True))
    assert calls == [], (
        "Plugin discovery must not run in the TUI launcher: the spawned "
        "tui_gateway backend discovers plugins itself."
    )


def test_plugin_discovery_runs_for_plain_chat(monkeypatch):
    calls = _install_discover_spy(monkeypatch)
    main_mod._prepare_agent_startup(_args(tui=False, command="chat"))
    assert calls == ["discover"]


def test_plain_chat_finishes_plugin_registration_before_toolset_validation(monkeypatch):
    """A plugin toolset must be visible before the CLI validates it."""
    import toolsets
    from cli import validate_toolset
    from tools.registry import registry

    state = {"discovered": False}
    validation_states = []

    def _discover():
        state["discovered"] = True

    def _registered_toolsets():
        return {"plugin_demo"} if state["discovered"] else set()

    original_validate = toolsets.validate_toolset

    def _validate(name):
        if name == "plugin_demo":
            validation_states.append(state["discovered"])
        return original_validate(name)

    monkeypatch.setattr(registry, "get_registered_toolset_names", _registered_toolsets)
    monkeypatch.setattr(toolsets, "validate_toolset", _validate)
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.plugins",
        types.SimpleNamespace(
            discover_plugins=_discover,
        ),
    )
    monkeypatch.setattr(main_mod, "_should_background_mcp_startup", lambda _args: False)

    main_mod._prepare_agent_startup(_args(tui=False, command="chat"))

    assert validate_toolset("plugin_demo") is True
    assert validation_states == [True]
