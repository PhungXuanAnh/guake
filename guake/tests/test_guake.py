# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name

import json
import os
import time

from pathlib import Path
from types import SimpleNamespace

import pytest

import guake.guake_app

from guake.boxes import DualTerminalBox
from guake.boxes import RootTerminalBox
from guake.common import pixmapfile
from guake.guake_app import Guake


@pytest.fixture
def g(mocker, fs):
    mocker.patch("guake.guake_app.Guake.get_xdg_config_directory", return_value=Path("/foobar"))
    mocker.patch("guake.guake_app.shutil.copy", create=True)
    mocker.patch("guake.guake_app.notifier.showMessage", create=True)
    mocker.patch("guake.guake_app.traceback.print_exc", create=True)
    fs.pause()
    g = Guake()
    fs.add_real_file(pixmapfile("guake-notification.png"))
    fs.resume()
    return g


# Accel Test


def test_accel_search_terminal(g):
    nb = g.get_notebook()
    page = nb.get_nth_page(0)
    assert not page.search_revealer.get_reveal_child()

    g.accel_search_terminal()
    assert page.search_revealer.get_reveal_child()


def test_accel_search_terminal_debounce(g):
    nb = g.get_notebook()
    page = nb.get_nth_page(0)
    assert not page.search_revealer.get_reveal_child()

    g.prev_accel_search_terminal_time = time.time()
    g.accel_search_terminal()
    assert not page.search_revealer.get_reveal_child()


def test_accel_quit_without_prompt(mocker, g):
    # Disable quit prompt
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)
    mocker.patch("guake.guake_app.Gtk.main_quit")

    g.accel_quit()
    assert guake.guake_app.Gtk.main_quit.call_count == 1


def test_accel_quit_with_prompt(mocker, g):
    # Enable quit prompt
    mocker.patch.object(g.settings.general, "get_boolean", return_value=True)
    mocker.patch("guake.guake_app.PromptQuitDialog")
    mocker.patch("guake.guake_app.Gtk.main_quit")

    g.accel_quit()
    assert guake.guake_app.Gtk.main_quit.call_count == 1


# Save/Restore Tabs


def test_guake_restore_tabs(g, fs):
    d1 = fs.create_dir("/foobar/foo")
    d2 = fs.create_dir("/foobar/bar")
    d3 = fs.create_dir("/foobar/foo/foo")
    d4 = fs.create_dir("/foobar/foo/bar")
    session = {
        "schema_version": 1,
        "timestamp": 1556092197,
        "workspace": {
            "0": [
                [
                    {"directory": d1.path, "label": "1", "custom_label_set": True},
                    {"directory": d2.path, "label": "2", "custom_label_set": True},
                    {"directory": d3.path, "label": d3.path, "custom_label_set": False},
                ]
            ],
            "1": [[{"directory": d4.path, "label": "4", "custom_label_set": True}]],
        },
    }

    fn = fs.create_file("/foobar/session.json")
    with open(fn.path, "w", encoding="utf-8") as f:
        f.write(json.dumps(session))

    g.restore_tabs(fn.name)
    nb = g.notebook_manager.get_notebook(0)
    assert nb.get_n_pages() == 3
    assert nb.get_tab_text_index(0) == "1"
    assert nb.get_tab_text_index(1) == "2"

    nb = g.notebook_manager.get_notebook(1)
    assert nb.get_n_pages() == 1
    assert nb.get_tab_text_index(0) == "4"


def test_guake_restore_tabs_json_without_schema_version(g, fs):
    guake.guake_app.notifier.showMessage.reset_mock()

    fn = fs.create_file("/foobar/bar.json")
    with open(fn.path, "w", encoding="utf-8") as f:
        f.write("{}")

    g.restore_tabs(fn.name)
    assert guake.guake_app.notifier.showMessage.call_count == 1


def test_guake_restore_tabs_with_higher_schema_version(g, fs):
    guake.guake_app.notifier.showMessage.reset_mock()

    fn = fs.create_file("/foobar/bar.json")
    with open(fn.path, "w", encoding="utf-8") as f:
        f.write('{"schema_version": 2147483647}')

    g.restore_tabs(fn.name)
    assert guake.guake_app.notifier.showMessage.call_count == 1


def test_guake_restore_tabs_json_broken_session_file(g, fs):
    guake.guake_app.notifier.showMessage.reset_mock()
    fn = fs.create_file("/foobar/foobar.json")
    with open(fn.path, "w", encoding="utf-8") as f:
        f.write("{")

    g.restore_tabs(fn.name)
    assert guake.guake_app.shutil.copy.call_count == 1
    assert guake.guake_app.notifier.showMessage.call_count == 1


def test_guake_restore_tabs_schema_broken_session_file(g, fs):
    guake.guake_app.notifier.showMessage.reset_mock()

    fn = fs.create_file("/foobar/bar.json")
    d = fs.create_dir("/foobar/foo")
    with open(fn.path, "w", encoding="utf-8") as f:
        f.write(f'{{"schema_version": 1, "workspace": {{"0": [[{{"directory": "{d.path}"}}]]}}}}')

    g.restore_tabs(fn.name)
    assert guake.guake_app.shutil.copy.call_count == 1
    assert guake.guake_app.traceback.print_exc.call_count == 1


def test_guake_save_tabs_and_restore(mocker, g, fs):
    # Disable auto save
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)

    # Save
    assert not os.path.exists("/foobar/session.json")
    g.add_tab()
    g.rename_current_tab("foobar", True)
    g.add_tab()
    g.rename_current_tab("python", True)
    assert g.get_notebook().get_n_pages() == 3

    g.save_tabs()
    assert os.path.exists("/foobar")
    assert os.path.exists("/foobar/session.json")

    # Restore prepare
    g.close_tab()
    g.close_tab()
    assert g.get_notebook().get_n_pages() == 1

    # Restore
    g.restore_tabs()
    nb = g.get_notebook()
    assert nb.get_n_pages() == 3
    assert nb.get_tab_text_index(1) == "foobar"
    assert nb.get_tab_text_index(2) == "python"


def test_guake_hide_tab_bar_if_one_tab(mocker, g, fs):
    # Set hide-tabs-if-one-tab to True
    mocker.patch.object(g.settings.general, "get_boolean", return_value=True)

    g.settings.general.set_boolean("hide-tabs-if-one-tab", True)
    assert g.get_notebook().get_n_pages() == 1
    assert g.get_notebook().get_property("show-tabs") is False


def test_load_cwd_guake_yml_not_found_error(g):
    vte = g.get_notebook().get_current_terminal()
    assert g.fm.read_yaml("/foo/.guake.yml") is None
    assert g.load_cwd_guake_yaml(vte) == {}


def test_load_cwd_guake_yml_encoding_error(g, mocker, fs):
    vte = g.get_notebook().get_current_terminal()
    mocker.patch.object(vte, "get_current_directory", return_value="/foo/")
    fs.create_file("/foo/.guake.yml", contents=b"\xfe\xf0[\xb1\x0b\xc1\x18\xda")
    assert g.fm.read_yaml("/foo/.guake.yml") is None
    assert g.load_cwd_guake_yaml(vte) == {}


def test_load_cwd_guake_yml_format_error(g, mocker, fs):
    vte = g.get_notebook().get_current_terminal()
    mocker.patch.object(vte, "get_current_directory", return_value="/foo/")
    fs.create_file("/foo/.guake.yml", contents=b"[[as]")
    assert g.fm.read_yaml("/foo/.guake.yml") is None
    assert g.load_cwd_guake_yaml(vte) == {}


def test_load_cwd_guake_yml(mocker, g, fs):
    vte = g.get_notebook().get_current_terminal()
    mocker.patch.object(vte, "get_current_directory", return_value="/foo/")

    f = fs.create_file("/foo/.guake.yml", contents="title: bar")
    assert g.load_cwd_guake_yaml(vte) == {"title": "bar"}

    # Cache in action.
    f.set_contents("title: foo")
    assert g.load_cwd_guake_yaml(vte) == {"title": "bar"}
    g.fm.clear()
    assert g.load_cwd_guake_yaml(vte) == {"title": "foo"}


def test_guake_compute_tab_title(mocker, g, fs):
    vte = g.get_notebook().get_current_terminal()
    mocker.patch.object(vte, "get_current_directory", return_value="/foo/")

    # Original title.
    assert g.compute_tab_title(vte) == "Terminal"

    # Change title.
    fs.create_file("/foo/.guake.yml", contents="title: bar")
    assert g.compute_tab_title(vte) == "bar"

    # Avoid loading the guake.yml
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)
    assert g.compute_tab_title(vte) == "Terminal"


class TriggerRecorder:
    def __init__(self):
        self.calls = []

    def triggerOnChangedValue(self, settings, key, user_data=None):
        self.calls.append((key, user_data))


def test_finish_show_size_reset_reapplies_configured_window_rect(mocker):
    """Show settling should reapply geometry without enabling pane scaling yet."""
    app = object.__new__(Guake)
    app.settings = SimpleNamespace()
    app.window = SimpleNamespace(
        get_allocation=lambda: SimpleNamespace(width=1804, height=928),
        get_state=lambda: 0,
    )
    app.fullscreen_manager = SimpleNamespace(is_fullscreen=lambda: False)
    app._pending_size_reset = True
    app._last_window_width = 1920
    app._last_window_height = 1080
    set_rect = mocker.patch("guake.guake_app.RectCalculator.set_final_window_rect")
    timeout_add = mocker.patch("guake.guake_app.GLib.timeout_add")

    assert app._finish_show_size_reset() is False

    set_rect.assert_called_once_with(app.settings, app.window)
    timeout_add.assert_called_once_with(150, app._complete_show_size_reset)
    assert app._last_window_width == 1920
    assert app._last_window_height == 1080
    assert app._pending_size_reset is True


def test_complete_show_size_reset_schedules_ratio_reapply_before_clearing(mocker):
    """Window tracking clears only after pane ratios have settled."""
    app = object.__new__(Guake)
    app.window = SimpleNamespace(
        get_allocation=lambda: SimpleNamespace(width=1804, height=928),
    )
    app._pending_size_reset = True
    app._last_window_width = 1920
    app._last_window_height = 1080
    schedule = mocker.patch.object(app, "_schedule_pane_ratio_reapply")

    assert app._complete_show_size_reset() is False

    schedule.assert_called_once_with(
        1.0,
        1.0,
        "show size reset",
        on_complete=app._complete_show_size_reset_after_panes,
    )
    assert app._last_window_width == 1920
    assert app._last_window_height == 1080
    assert app._pending_size_reset is True


def test_complete_show_size_reset_after_panes_clears_pending_flag():
    app = object.__new__(Guake)
    app.window = SimpleNamespace(
        get_allocation=lambda: SimpleNamespace(width=1804, height=928),
        get_property=lambda key: True if key == "visible" else None,
    )
    app._pending_size_reset = True
    app._last_window_width = 1920
    app._last_window_height = 1080

    app._complete_show_size_reset_after_panes()

    assert app._last_window_width == 1804
    assert app._last_window_height == 928
    assert app._pending_size_reset is False


def test_complete_show_size_reset_after_panes_skips_hidden_degenerate_allocation():
    app = object.__new__(Guake)
    app.window = SimpleNamespace(
        get_allocation=lambda: SimpleNamespace(width=1, height=1),
        get_property=lambda key: False if key == "visible" else None,
    )
    app._pending_size_reset = True
    app._last_window_width = 1920
    app._last_window_height = 1080

    assert app._complete_show_size_reset_after_panes() is False

    assert app._last_window_width == 1920
    assert app._last_window_height == 1080
    assert app._pending_size_reset is True


def test_cancel_pending_pane_ratio_reapply_clears_timer(mocker):
    app = object.__new__(Guake)
    app._pane_ratio_reapply_timeout_id = 123
    app._pane_ratio_adjusting = True
    source_remove = mocker.patch("guake.guake_app.GLib.source_remove")

    app._cancel_pending_pane_ratio_reapply("test")

    source_remove.assert_called_once_with(123)
    assert app._pane_ratio_reapply_timeout_id is None
    assert app._pane_ratio_adjusting is False


def _make_load_config_app(fullscreen=False):
    app = object.__new__(Guake)
    app.settings = SimpleNamespace(
        general=TriggerRecorder(),
        style=TriggerRecorder(),
        styleFont=TriggerRecorder(),
        styleBackground=TriggerRecorder(),
    )
    app.fullscreen_manager = SimpleNamespace(is_fullscreen=lambda: fullscreen)
    return app


def test_load_config_global_reloads_window_geometry():
    app = _make_load_config_app()

    app.load_config()

    general_keys = [key for key, _ in app.settings.general.calls]
    assert "window-height" in general_keys
    assert "window-width" in general_keys


def test_load_config_for_terminal_skips_global_window_geometry():
    app = _make_load_config_app()

    app.load_config(terminal_uuid="term-1")

    general_keys = [key for key, _ in app.settings.general.calls]
    assert "window-height" not in general_keys
    assert "window-width" not in general_keys
    assert ("use-scrollbar", {"terminal_uuid": "term-1"}) in app.settings.general.calls


# Pane Zoom Tests


def test_accel_pane_zoom_in(mocker, g):
    """Test that pane zoom in increases the font scale of the current terminal only."""
    # Disable auto save to avoid side effects
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)

    term = g.get_notebook().get_current_terminal()
    initial_scale = term.font_scale_index

    result = g.accel_pane_zoom_in()

    assert result is True
    assert term.font_scale_index == initial_scale + 1


def test_accel_pane_zoom_out(mocker, g):
    """Test that pane zoom out decreases the font scale of the current terminal only."""
    # Disable auto save to avoid side effects
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)

    term = g.get_notebook().get_current_terminal()
    initial_scale = term.font_scale_index

    result = g.accel_pane_zoom_out()

    assert result is True
    assert term.font_scale_index == initial_scale - 1


def test_accel_pane_zoom_saves_tabs_when_enabled(mocker, g):
    """Test that pane zoom triggers save_tabs when save-tabs-when-changed is enabled."""
    # Enable auto save
    mocker.patch.object(g.settings.general, "get_boolean", return_value=True)
    mock_save = mocker.patch.object(g, "save_tabs")

    g.accel_pane_zoom_in()
    assert mock_save.call_count == 1

    g.accel_pane_zoom_out()
    assert mock_save.call_count == 2


def test_accel_pane_zoom_no_save_when_disabled(mocker, g):
    """Test that pane zoom does not trigger save_tabs when save-tabs-when-changed is disabled."""
    # Disable auto save
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)
    mock_save = mocker.patch.object(g, "save_tabs")

    g.accel_pane_zoom_in()
    g.accel_pane_zoom_out()

    assert mock_save.call_count == 0


def test_pane_zoom_independent_of_other_terminals(mocker, g):
    """Test that pane zoom only affects the current terminal, not others."""
    # Disable auto save to avoid side effects
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)

    # Get the first terminal
    term1 = g.get_notebook().get_current_terminal()
    initial_scale1 = term1.font_scale_index

    # Add a new tab with a second terminal
    g.add_tab()
    term2 = g.get_notebook().get_current_terminal()
    initial_scale2 = term2.font_scale_index

    # Zoom in on the second terminal (current one)
    g.accel_pane_zoom_in()
    g.accel_pane_zoom_in()

    # Verify that only the second terminal's scale changed
    assert term2.font_scale_index == initial_scale2 + 2
    assert term1.font_scale_index == initial_scale1  # First terminal unchanged


# Session Restoration Pane Adjustment Protection Tests


def test_session_restoring_flag_initialized(g):
    """Test that _session_restoring flag is initialized to False."""
    assert hasattr(g, "_session_restoring")
    assert g._session_restoring is False


def test_pending_size_reset_flag_initialized(g):
    """Test that _pending_size_reset flag is initialized to False."""
    assert hasattr(g, "_pending_size_reset")
    assert g._pending_size_reset is False


def test_window_size_tracking_initialized(g):
    """Test that window size tracking attributes are initialized."""
    assert hasattr(g, "_last_window_width")
    assert hasattr(g, "_last_window_height")
    assert g._last_window_width == 0
    assert g._last_window_height == 0


def test_pane_adjust_timeout_id_initialized(g):
    """Test that pane adjustment timeout ID is initialized to None."""
    assert hasattr(g, "_pane_adjust_timeout_id")
    assert g._pane_adjust_timeout_id is None


def test_on_window_configure_skips_during_session_restoring(mocker, g):
    """Test that _on_window_configure skips pane adjustments when _session_restoring is True."""
    # Create a mock event
    mock_event = mocker.MagicMock()
    mock_event.width = 1920
    mock_event.height = 1080

    # Set initial size to trigger a potential change detection
    g._last_window_width = 800
    g._last_window_height = 600

    # Set session restoring flag
    g._session_restoring = True

    # Mock the timeout to prevent scheduling pane adjustments
    mock_timeout = mocker.patch("guake.guake_app.GLib.timeout_add")

    # Call the configure handler
    result = g._on_window_configure(g.window, mock_event)

    # Should return False (event handled)
    assert result is False

    # Should NOT schedule pane adjustments
    assert mock_timeout.call_count == 0

    # Should update the tracked size even during restoration
    assert g._last_window_width == 1920
    assert g._last_window_height == 1080


def test_on_window_configure_skips_during_pending_size_reset(mocker, g):
    """Test that _on_window_configure skips pane adjustments when _pending_size_reset is True."""
    # Create a mock event
    mock_event = mocker.MagicMock()
    mock_event.width = 1920
    mock_event.height = 1080

    # Set initial size to trigger a potential change detection
    g._last_window_width = 800
    g._last_window_height = 600

    # Ensure session restoring is False but pending reset is True
    g._session_restoring = False
    g._pending_size_reset = True

    # Mock the timeout to prevent scheduling pane adjustments
    mock_timeout = mocker.patch("guake.guake_app.GLib.timeout_add")

    # Call the configure handler
    result = g._on_window_configure(g.window, mock_event)

    # Should return False (event handled)
    assert result is False

    # Should NOT schedule pane adjustments
    assert mock_timeout.call_count == 0

    # Should update the tracked size even while pending reset
    assert g._last_window_width == 1920
    assert g._last_window_height == 1080


def test_on_window_configure_skips_show_transition_resize_sequence(mocker):
    """Hidden->shown configure events should not grow pane font sizes."""
    mock_timeout = mocker.patch("guake.guake_app.GLib.timeout_add")
    app = object.__new__(Guake)
    app._session_restoring = False
    app._pending_size_reset = True
    app._last_window_width = 1920
    app._last_window_height = 1080

    first_event = mocker.MagicMock()
    first_event.width = 1804
    first_event.height = 928
    second_event = mocker.MagicMock()
    second_event.width = 1920
    second_event.height = 1080

    assert app._on_window_configure(None, first_event) is False
    assert app._on_window_configure(None, second_event) is False

    assert mock_timeout.call_count == 0
    assert app._last_window_width == 1920
    assert app._last_window_height == 1080


def test_on_window_configure_skips_when_no_previous_size(mocker, g):
    """Test that _on_window_configure skips adjustments on first configure event."""
    # Create a mock event
    mock_event = mocker.MagicMock()
    mock_event.width = 1920
    mock_event.height = 1080

    # Reset size tracking to 0 (initial state)
    g._last_window_width = 0
    g._last_window_height = 0
    g._session_restoring = False
    g._pending_size_reset = False

    # Mock the timeout to prevent scheduling pane adjustments
    mock_timeout = mocker.patch("guake.guake_app.GLib.timeout_add")

    # Call the configure handler
    result = g._on_window_configure(g.window, mock_event)

    # Should return False (event handled)
    assert result is False

    # Should NOT schedule pane adjustments for first event
    assert mock_timeout.call_count == 0

    # Should store the initial size
    assert g._last_window_width == 1920
    assert g._last_window_height == 1080


def test_on_window_configure_skips_small_size_changes(mocker, g):
    """Test that _on_window_configure skips adjustments for small size changes (below 5%)."""
    # Create a mock event with small change (3% change)
    mock_event = mocker.MagicMock()
    mock_event.width = 1030  # 3% larger than 1000
    mock_event.height = 600

    # Set initial size
    g._last_window_width = 1000
    g._last_window_height = 600
    g._session_restoring = False
    g._pending_size_reset = False

    # Mock the timeout to prevent scheduling pane adjustments
    mock_timeout = mocker.patch("guake.guake_app.GLib.timeout_add")

    # Call the configure handler
    result = g._on_window_configure(g.window, mock_event)

    # Should return False (event handled)
    assert result is False

    # Should NOT schedule pane adjustments for small changes
    assert mock_timeout.call_count == 0


def test_on_window_configure_schedules_for_large_size_changes(mocker, g):
    """Test that _on_window_configure schedules adjustments for large size changes (above 5%)."""
    # Create a mock event with large change (33% change - like moving between monitors)
    mock_event = mocker.MagicMock()
    mock_event.width = 2560
    mock_event.height = 1080

    # Set initial size
    g._last_window_width = 1920
    g._last_window_height = 1080
    g._session_restoring = False
    g._pending_size_reset = False

    # Ensure no existing timeout
    g._pane_adjust_timeout_id = None

    # Mock the timeout to capture the scheduling
    mock_timeout = mocker.patch("guake.guake_app.GLib.timeout_add", return_value=12345)

    # Call the configure handler
    result = g._on_window_configure(g.window, mock_event)

    # Should return False (event handled)
    assert result is False

    # Should schedule pane adjustments for large changes
    assert mock_timeout.call_count == 1

    # Should store the timeout ID
    assert g._pane_adjust_timeout_id == 12345


def make_fake_dual_box(orientation, width, height, position, ratio=50):
    box = DualTerminalBox.__new__(DualTerminalBox)
    box.orient = orientation
    box._stored_split_percentage = ratio
    box._save_position_timeout_id = None
    box._allocation = SimpleNamespace(width=width, height=height)
    box._position = position
    box.get_allocation = lambda: box._allocation
    box.get_position = lambda: box._position
    box.set_position = lambda value: setattr(box, "_position", value)
    box.get_child1 = lambda: None
    box.get_child2 = lambda: None
    return box


def test_dual_terminal_box_remembers_second_child_split_percentage():
    box = make_fake_dual_box(DualTerminalBox.ORIENT_H, width=1000, height=500, position=250)

    box.remember_current_split_percentage()

    assert box.get_stored_split_percentage() == 75


def test_dual_terminal_box_applies_stored_split_percentage_to_current_allocation():
    box = make_fake_dual_box(
        DualTerminalBox.ORIENT_H, width=1200, height=500, position=100, ratio=25
    )

    assert box.apply_stored_split_percentage()

    assert box.get_position() == 900


def test_root_terminal_box_reapplies_nested_pane_ratios():
    root_split = make_fake_dual_box(
        DualTerminalBox.ORIENT_H, width=2000, height=1000, position=1500, ratio=50
    )
    nested_split = make_fake_dual_box(
        DualTerminalBox.ORIENT_H, width=1000, height=1000, position=100, ratio=25
    )
    root_split.get_child1 = lambda: nested_split

    root = RootTerminalBox.__new__(RootTerminalBox)
    root.get_child = lambda: root_split

    root.adjust_panes_for_new_size(2.0, 1.0)

    assert root_split.get_position() == 1000
    assert nested_split.get_position() == 750


def test_position_notify_is_ignored_during_show_size_reset(mocker):
    box = make_fake_dual_box(
        DualTerminalBox.ORIENT_H, width=1000, height=500, position=250, ratio=50
    )
    box.get_guake = lambda: SimpleNamespace(
        _session_restoring=False,
        _pending_size_reset=True,
        _pane_ratio_adjusting=False,
        _pane_adjust_timeout_id=None,
    )
    timeout_add = mocker.patch("guake.boxes.GLib.timeout_add")

    box._on_position_changed(None, None)

    assert box.get_stored_split_percentage() == 50
    assert timeout_add.call_count == 0


def test_reapply_all_pane_ratios_suppresses_position_saves(mocker):
    page = mocker.MagicMock()
    notebook = SimpleNamespace(iter_pages=lambda: iter([page]))
    app = object.__new__(Guake)
    app.notebook_manager = SimpleNamespace(iter_notebooks=lambda: iter([notebook]))
    app._pane_ratio_adjusting = False

    app._reapply_all_pane_ratios(1.5, 0.75, "test")

    page.adjust_panes_for_new_size.assert_called_once_with(1.5, 0.75)
    assert app._pane_ratio_adjusting is False


def test_schedule_pane_ratio_reapply_runs_multiple_settle_passes(mocker):
    callbacks = []

    def timeout_add(delay, callback):
        callbacks.append((delay, callback))
        return len(callbacks)

    mocker.patch("guake.guake_app.GLib.timeout_add", side_effect=timeout_add)
    app = object.__new__(Guake)
    app._pane_ratio_adjusting = False
    app._pane_ratio_reapply_timeout_id = None
    app._reapply_all_pane_ratios = mocker.Mock()
    on_complete = mocker.Mock()

    app._schedule_pane_ratio_reapply(
        1.25,
        0.75,
        "test",
        passes=3,
        interval_ms=25,
        on_complete=on_complete,
    )

    assert app._pane_ratio_adjusting is True
    assert app._reapply_all_pane_ratios.call_count == 1
    assert callbacks[0][0] == 25

    callbacks.pop(0)[1]()
    assert app._pane_ratio_adjusting is True
    assert app._reapply_all_pane_ratios.call_count == 2

    callbacks.pop(0)[1]()
    assert app._pane_ratio_adjusting is False
    assert app._pane_ratio_reapply_timeout_id is None
    assert app._reapply_all_pane_ratios.call_count == 3
    on_complete.assert_called_once_with()


# Font Scaling with Resolution Changes Tests


def test_do_adjust_scales_font_for_larger_monitor(mocker, g):
    """Test that font scale increases when moving to a larger monitor."""
    # Disable auto save to avoid side effects
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)

    # Get initial font scale
    term = g.get_notebook().get_current_terminal()
    initial_scale = term.font_scale_index

    # Simulate moving from 1920 to 3840 (double width, 2x scaling)
    # log2(2) * 6 = 6, so font_scale_index should increase by 6
    g._do_adjust_all_pane_positions(1920, 1080, 3840, 2160)

    assert term.font_scale_index == initial_scale + 6


def test_do_adjust_scales_font_for_smaller_monitor(mocker, g):
    """Test that font scale decreases when moving to a smaller monitor."""
    # Disable auto save to avoid side effects
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)

    # Get initial font scale and set it high enough so decrease doesn't clamp
    term = g.get_notebook().get_current_terminal()
    term.set_font_scale_index(6)
    initial_scale = term.font_scale_index

    # Simulate moving from 3840 to 1920 (half width, 0.5x scaling)
    # log2(0.5) * 6 = -6, so font_scale_index should decrease by 6
    g._do_adjust_all_pane_positions(3840, 2160, 1920, 1080)

    assert term.font_scale_index == initial_scale - 6


def test_do_adjust_no_font_scale_for_same_size(mocker, g):
    """Test that font scale doesn't change when window size stays the same."""
    # Disable auto save to avoid side effects
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)

    # Get initial font scale
    term = g.get_notebook().get_current_terminal()
    initial_scale = term.font_scale_index

    # Simulate no size change
    g._do_adjust_all_pane_positions(1920, 1080, 1920, 1080)

    assert term.font_scale_index == initial_scale


def test_do_adjust_no_font_scale_for_small_change(mocker, g):
    """Test that font scale doesn't change for small resolution differences."""
    # Disable auto save to avoid side effects
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)

    # Get initial font scale
    term = g.get_notebook().get_current_terminal()
    initial_scale = term.font_scale_index

    # Simulate small width change (1920 -> 2048, ~1.07x, log2(1.07)*6 ≈ 0.58, rounds to 1)
    # But let's use a smaller change that rounds to 0
    # 1920 -> 1980 (~1.03x, log2(1.03)*6 ≈ 0.26, rounds to 0)
    g._do_adjust_all_pane_positions(1920, 1080, 1980, 1080)

    assert term.font_scale_index == initial_scale


def test_do_adjust_font_scale_respects_clamp_limits(mocker, g):
    """Test that font scale stays within clamped range (-6 to 12)."""
    # Disable auto save to avoid side effects
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)

    # Get terminal and set to max scale
    term = g.get_notebook().get_current_terminal()
    term.set_font_scale_index(12)

    # Simulate moving to larger monitor (would try to go above 12)
    g._do_adjust_all_pane_positions(1920, 1080, 3840, 2160)

    # Should be clamped at 12 (max)
    assert term.font_scale_index == 12


def test_do_adjust_font_scale_all_terminals(mocker, g):
    """Test that font scale is adjusted for all terminals."""
    # Disable auto save to avoid side effects
    mocker.patch.object(g.settings.general, "get_boolean", return_value=False)

    # Get first terminal
    term1 = g.get_notebook().get_current_terminal()
    initial_scale1 = term1.font_scale_index

    # Add a new tab
    g.add_tab()
    term2 = g.get_notebook().get_current_terminal()
    initial_scale2 = term2.font_scale_index

    # Simulate moving to larger monitor (2x width, +6 to font_scale_index)
    g._do_adjust_all_pane_positions(1920, 1080, 3840, 2160)

    # Both terminals should have their font scale adjusted
    assert term1.font_scale_index == initial_scale1 + 6
    assert term2.font_scale_index == initial_scale2 + 6
