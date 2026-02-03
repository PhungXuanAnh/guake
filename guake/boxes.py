import logging
import time

import gi

gi.require_version("Vte", "2.91")  # vte-0.42
gi.require_version("Gtk", "3.0")
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import Gtk
from gi.repository import Vte

from guake.callbacks import MenuHideCallback
from guake.callbacks import TerminalContextMenuCallbacks
from guake.dialogs import PromptResetColorsDialog
from guake.dialogs import RenameDialog
from guake.globals import PCRE2_MULTILINE
from guake.menus import mk_tab_context_menu
from guake.menus import mk_terminal_context_menu
from guake.utils import HidePrevention
from guake.utils import TabNameUtils
from guake.utils import get_server_time
from guake.utils import save_tabs_when_changed

log = logging.getLogger(__name__)

# Minimum allocation (in pixels) below which a Gtk.Paned is considered to have
# no real geometry yet. Saving a pane ratio with allocation smaller than this
# would produce garbage values when GTK is still settling hidden/shown windows.
MIN_PANE_ALLOC_PX = 10


class DegenerateAllocationError(RuntimeError):
    """Raised when a pane has no usable allocation yet."""


# TODO remove calls to guake


class TerminalHolder:
    UP = 0
    DOWN = 1
    RIGHT = 2
    LEFT = 3

    def get_terminals(self):
        raise NotImplementedError

    def iter_terminals(self):
        raise NotImplementedError

    def replace_child(self, old, new):
        raise NotImplementedError

    def get_guake(self):
        raise NotImplementedError

    def get_window(self):
        raise NotImplementedError

    def get_settings(self):
        raise NotImplementedError

    def get_root_box(self):
        raise NotImplementedError

    def get_notebook(self):
        raise NotImplementedError

    def remove_dead_child(self, child):
        raise NotImplementedError


class RootTerminalBox(Gtk.Overlay, TerminalHolder):
    def __init__(self, guake, parent_notebook):
        super().__init__()
        self.guake = guake
        self.notebook = parent_notebook
        self.child = None
        self.last_terminal_focused = None

        self.searchstring = None
        self.searchre = None
        self._add_search_box()

    def _add_search_box(self):
        """--------------------------------------|
        | Revealer                            |
        | |-----------------------------------|
        | | Frame                             |
        | | |---------------------------------|
        | | | HBox                            |
        | | | |---| |-------| |----| |------| |
        | | | | x | | Entry | |Prev| | Next | |
        | | | |---| |-------| |----| |------| |
        --------------------------------------|
        """
        self.search_revealer = Gtk.Revealer()
        self.search_frame = Gtk.Frame(name="search-frame")
        self.search_box = Gtk.HBox()

        # Search
        self.search_close_btn = Gtk.Button()
        self.search_close_btn.set_can_focus(False)
        close_icon = Gio.ThemedIcon(name="window-close-symbolic")
        close_image = Gtk.Image.new_from_gicon(close_icon, Gtk.IconSize.BUTTON)
        self.search_close_btn.set_image(close_image)
        self.search_entry = Gtk.SearchEntry()
        self.search_prev_btn = Gtk.Button()
        self.search_prev_btn.set_can_focus(False)
        prev_icon = Gio.ThemedIcon(name="go-up-symbolic")
        prev_image = Gtk.Image.new_from_gicon(prev_icon, Gtk.IconSize.BUTTON)
        self.search_prev_btn.set_image(prev_image)
        self.search_next_btn = Gtk.Button()
        self.search_next_btn.set_can_focus(False)
        next_icon = Gio.ThemedIcon(name="go-down-symbolic")
        next_image = Gtk.Image.new_from_gicon(next_icon, Gtk.IconSize.BUTTON)
        self.search_next_btn.set_image(next_image)

        # Pack into box
        self.search_box.pack_start(self.search_close_btn, False, False, 0)
        self.search_box.pack_start(self.search_entry, False, False, 0)
        self.search_box.pack_start(self.search_prev_btn, False, False, 0)
        self.search_box.pack_start(self.search_next_btn, False, False, 0)

        # Add into frame
        self.search_frame.add(self.search_box)

        # Frame
        self.search_frame.set_margin_end(12)
        self.search_frame.get_style_context().add_class("background")
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            b"#search-frame border {" b"    padding: 5px 5px 5px 5px;" b"    border: none;" b"}"
        )
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        # Add to revealer
        self.search_revealer.add(self.search_frame)
        self.search_revealer.set_transition_duration(500)
        self.search_revealer.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
        self.search_revealer.set_valign(Gtk.Align.END)
        self.search_revealer.set_halign(Gtk.Align.END)

        # Welcome to the overlay
        self.add_overlay(self.search_revealer)

        # Events
        self.search_entry.connect("key-press-event", self.on_search_entry_keypress)
        self.search_entry.connect("changed", self.set_search)
        self.search_entry.connect("activate", self.do_search)
        self.search_entry.connect("focus-in-event", self.on_search_entry_focus_in)
        self.search_entry.connect("focus-out-event", self.on_search_entry_focus_out)
        self.search_next_btn.connect("clicked", self.on_search_next_clicked)
        self.search_prev_btn.connect("clicked", self.on_search_prev_clicked)
        self.search_close_btn.connect("clicked", self.close_search_box)
        self.search_prev = True

        # Search revealer visible
        def search_revealer_show_cb(widget):
            if not widget.get_child_revealed():
                widget.hide()

        self.search_revealer.hide()
        self.search_revealer_show_cb_id = self.search_revealer.connect(
            "show", search_revealer_show_cb
        )
        self.search_frame.connect("unmap", lambda x: self.search_revealer.hide())

    def get_terminals(self):
        return self.get_child().get_terminals()

    def iter_terminals(self):
        if self.get_child() is not None:
            yield from self.get_child().iter_terminals()

    def replace_child(self, old, new):
        self.remove(old)
        self.set_child(new)

    def set_child(self, terminal_holder):
        if isinstance(terminal_holder, TerminalHolder):
            self.child = terminal_holder
            self.add(self.child)
        else:
            raise RuntimeError(f"Error adding (RootTerminalBox.add({type(terminal_holder)}))")

    def get_child(self):
        return self.child

    def get_guake(self):
        return self.guake

    def get_window(self):
        return self.guake.window

    def get_settings(self):
        return self.guake.settings

    def get_root_box(self):
        return self

    def adjust_panes_for_new_size(self, width_scale, height_scale):
        """Recursively restore pane positions after the window size changes.

        Gtk.Paned positions are relative to their own allocation, not the top-level
        window. Nested panes must therefore reapply their remembered split
        percentage against their current allocation instead of using one global
        window scale.
        """
        log.debug(
            "adjust_panes_for_new_size called with scale=(%.2f, %.2f); "
            "reapplying stored split percentages",
            width_scale,
            height_scale,
        )
        self._apply_stored_pane_positions(self.get_child())

    def _apply_stored_pane_positions(self, box):
        """Recursively apply each pane's remembered split percentage."""
        if box is None:
            return

        if isinstance(box, DualTerminalBox):
            box.apply_stored_split_percentage()
            self._apply_stored_pane_positions(box.get_child1())
            self._apply_stored_pane_positions(box.get_child2())

    def save_box_layout(self, box, panes: list):
        """Save box layout with pre-order traversal, it should result `panes` with
        a full binary tree in list.
        """
        if not box:
            panes.append({"type": None, "directory": None})
            return
        if isinstance(box, DualTerminalBox):
            btype = "dual" + ("_h" if box.orient is DualTerminalBox.ORIENT_V else "_v")
            # Calculate and save the split ratio
            position = box.get_position()
            allocation = box.get_allocation()
            if box.orient is DualTerminalBox.ORIENT_V:
                total = allocation.height
            else:
                total = allocation.width
            # Guard against degenerate allocations (e.g. (1,1) before the
            # widget has been laid out). Computing position/total in that
            # state produces garbage like saved_ratio=-21000, which then
            # corrupts session.json and breaks the next restore.
            if total < MIN_PANE_ALLOC_PX:
                log.warning(
                    "[PANE-SAVE-ABORT] DualTerminalBox %s id=%s orient=%s "
                    "position=%d alloc=(w=%d,h=%d) total=%d "
                    "below MIN_PANE_ALLOC_PX=%d -> aborting save (will retry)",
                    btype,
                    id(box),
                    "V" if box.orient is DualTerminalBox.ORIENT_V else "H",
                    position,
                    allocation.width,
                    allocation.height,
                    total,
                    MIN_PANE_ALLOC_PX,
                )
                raise DegenerateAllocationError(
                    f"DualTerminalBox id={id(box)} alloc total={total} too small "
                    f"(<{MIN_PANE_ALLOC_PX}); aborting save"
                )

            # Ratio is stored in the historical split_percentage format:
            # percentage allocated to the second child. split_no_save converts
            # it back to the first-child Gtk.Paned position with 100 - ratio.
            ratio = box.calculate_current_split_percentage()
            box.set_stored_split_percentage(ratio)
            log.debug(
                "[PANE-SAVE] DualTerminalBox %s id=%s orient=%s position=%d "
                "alloc=(w=%d,h=%d) total=%d -> saved_ratio=%d",
                btype,
                id(box),
                "V" if box.orient is DualTerminalBox.ORIENT_V else "H",
                position,
                allocation.width,
                allocation.height,
                total,
                ratio,
            )
            panes.append({"type": btype, "directory": None, "ratio": ratio})
            self.save_box_layout(box.get_child1(), panes)
            self.save_box_layout(box.get_child2(), panes)
        elif isinstance(box, TerminalBox):
            btype = "term"
            directory = box.terminal.get_current_directory()
            panes.append(
                {
                    "type": btype,
                    "directory": directory,
                    "command": getattr(box.terminal, "startup_command", None),
                    "custom_colors": box.terminal.get_custom_colors_dict(),
                    "pane_name": box.get_pane_name(),
                    "font_scale": box.terminal.font_scale_index,
                }
            )

    def restore_box_layout(self, box, panes: list):
        """Restore box layout by `panes`"""
        if not panes or not isinstance(panes, list) or not box or not isinstance(box, TerminalBox):
            return

        cur = panes.pop(0)
        if cur["type"].startswith("dual"):
            while True:
                if self.guake:
                    # If Guake is not visible, we should pending the restore, then do the
                    # restore when Guake is visible again.
                    #
                    # Otherwise we will stuck in the infinite loop, since new DualTerminalBox
                    # cannot get any allocation when Guake is invisible
                    if (
                        not self.guake.window.get_property("visible")
                        or self.get_notebook()
                        is not self.guake.notebook_manager.get_current_notebook()
                    ):
                        panes.insert(0, cur)
                        self.guake._failed_restore_page_split.append((self, box, panes))
                        return

                # UI didn't update, wait for it
                alloc = box.get_allocation()
                if alloc.width == 1 and alloc.height == 1:
                    time.sleep(0.01)
                else:
                    break

                # Waiting for UI update..
                while Gtk.events_pending():
                    Gtk.main_iteration()

            # Use saved ratio if available, otherwise default to 50%.
            # Defensively clamp to [1, 99]: a session.json corrupted by an
            # earlier buggy build can hold values like -21000 or 211, which
            # would otherwise make one pane swallow the whole window after
            # restore (the "auto-increase" symptom).
            raw_ratio = cur.get("ratio", 50)
            try:
                ratio_int = int(raw_ratio)
            except (TypeError, ValueError):
                log.warning(
                    "[PANE-RESTORE-BAD-RATIO] non-numeric ratio=%r in session, "
                    "falling back to 50",
                    raw_ratio,
                )
                ratio_int = 50
            ratio = max(1, min(99, ratio_int))
            if ratio != raw_ratio:
                log.warning(
                    "[PANE-RESTORE-CLAMP] type=%s raw_ratio=%r -> clamped=%d",
                    cur.get("type"),
                    raw_ratio,
                    ratio,
                )
            alloc_dbg = box.get_allocation()
            log.debug(
                "[PANE-RESTORE] type=%s ratio=%s alloc_at_split=(w=%d,h=%d) " "window_visible=%s",
                cur.get("type"),
                ratio,
                alloc_dbg.width,
                alloc_dbg.height,
                self.guake.window.get_property("visible") if self.guake else "?",
            )
            if cur["type"].endswith("v"):
                box = box.split_v_no_save(ratio)
            else:
                box = box.split_h_no_save(ratio)
            self.restore_box_layout(box.get_child1(), panes)
            self.restore_box_layout(box.get_child2(), panes)
        else:
            if box.terminal:
                term = box.terminal
                # Remove signal handler from terminal
                for i in term.handler_ids:
                    term.disconnect(i)
                term.handler_ids = []
                box.terminal_hbox.remove(box.scroll)
                box.terminal_hbox.remove(term)
                box.unset_terminal()

            # Replace term in the TerminalBox
            term = self.get_notebook().terminal_spawn(cur["directory"])
            term.set_custom_colors_from_dict(cur.get("custom_colors", None))
            box.set_terminal(term)
            self.get_notebook().terminal_attached(term)

            # Restore pane name if saved
            if cur.get("pane_name"):
                box.set_pane_name(cur["pane_name"])

            # Restore font scale if saved
            if cur.get("font_scale") is not None:
                term.font_scale = cur["font_scale"]

            # Execute startup command if specified in session
            if cur.get("command"):
                # Store command for future session saves
                term.startup_command = cur["command"]
                # Use GLib.timeout_add to ensure shell is ready before executing command
                GLib.timeout_add(
                    100, lambda cmd=cur["command"], t=term: t.execute_command(cmd) or False
                )

    def set_last_terminal_focused(self, terminal):
        self.last_terminal_focused = terminal
        self.get_notebook().set_last_terminal_focused(terminal)

    def get_last_terminal_focused(self, terminal):
        return self.last_terminal_focused

    def get_notebook(self):
        return self.notebook

    def remove_dead_child(self, child):
        page_num = self.get_notebook().page_num(self)
        self.get_notebook().remove_page(page_num)

    def block_notebook_on_button_press_id(self):
        GObject.signal_handler_block(
            self.get_notebook(), self.get_notebook().notebook_on_button_press_id
        )

    def unblock_notebook_on_button_press_id(self):
        GObject.signal_handler_unblock(
            self.get_notebook(), self.get_notebook().notebook_on_button_press_id
        )

    def show_search_box(self):
        if not self.search_revealer.get_reveal_child():
            GObject.signal_handler_block(self.search_revealer, self.search_revealer_show_cb_id)
            self.search_revealer.set_visible(True)
            self.search_revealer.set_reveal_child(True)
            GObject.signal_handler_unblock(self.search_revealer, self.search_revealer_show_cb_id)
            # XXX: Mestery line to avoid Gtk-CRITICAL stuff
            # (guake:22694): Gtk-CRITICAL **: 18:04:57.345:
            # gtk_widget_event: assertion 'WIDGET_REALIZED_FOR_EVENT (widget, event)' failed
            self.search_entry.realize()
            self.search_entry.grab_focus()

    def hide_search_box(self):
        if self.search_revealer.get_reveal_child():
            self.search_revealer.set_reveal_child(False)
            self.last_terminal_focused.grab_focus()
            self.last_terminal_focused.unselect_all()

    def close_search_box(self, event):
        self.hide_search_box()

    def on_search_entry_focus_in(self, event, user_data):
        self.block_notebook_on_button_press_id()

    def on_search_entry_focus_out(self, event, user_data):
        self.unblock_notebook_on_button_press_id()

    def on_search_prev_clicked(self, widget):
        term = self.last_terminal_focused
        result = term.search_find_previous()
        if not result:
            term.search_find_previous()

    def on_search_next_clicked(self, widget):
        term = self.last_terminal_focused
        result = term.search_find_next()
        if not result:
            term.search_find_next()

    def on_search_entry_keypress(self, widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key == "Escape":
            self.hide_search_box()
        elif key == "Return":
            # Combine with Shift?
            if event.state & Gdk.ModifierType.SHIFT_MASK:
                self.search_prev = False
                self.do_search(None)
            else:
                self.search_prev = True

    def reset_term_search(self, term):
        term.search_set_regex(None, 0)
        term.search_find_next()

    def set_search(self, widget):
        term = self.last_terminal_focused
        text = self.search_entry.get_text()
        if not text:
            self.reset_term_search(term)
            return

        if text != self.searchstring:
            self.reset_term_search(term)

            # Set search regex on term
            self.searchstring = text
            self.searchre = Vte.Regex.new_for_search(
                text, -1, Vte.REGEX_FLAGS_DEFAULT | PCRE2_MULTILINE
            )
            term.search_set_regex(self.searchre, 0)
        self.do_search(None)

    def do_search(self, widget):
        if self.search_prev:
            self.on_search_prev_clicked(None)
        else:
            self.on_search_next_clicked(None)


class TerminalBox(Gtk.Box, TerminalHolder):
    """A box to group the terminal and a scrollbar, with optional pane name label."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.terminal = None
        self.pane_name = ""

        # Create the pane name label (hidden by default)
        self.pane_label = Gtk.Label()
        self.pane_label.set_xalign(0)  # Left align
        self.pane_label.set_margin_start(5)
        self.pane_label.set_margin_end(5)
        self.pane_label.set_margin_top(2)
        self.pane_label.set_margin_bottom(2)
        self.pane_label.get_style_context().add_class("pane-name-label")
        self.pane_label.set_no_show_all(True)  # Don't show with show_all()
        self.pack_start(self.pane_label, False, False, 0)

        # Create horizontal box to hold terminal and scrollbar
        self.terminal_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(self.terminal_hbox, True, True, 0)
        self.terminal_hbox.show()

    def set_pane_name(self, name):
        """Set the pane name and show/hide the label accordingly."""
        self.pane_name = name if name else ""
        if self.pane_name:
            self.pane_label.set_text(self.pane_name)
            self.pane_label.show()
        else:
            self.pane_label.hide()

    def get_pane_name(self):
        """Get the current pane name."""
        return self.pane_name

    def set_terminal(self, terminal):
        """Packs the terminal widget."""
        if self.terminal is not None:
            raise RuntimeError("TerminalBox: terminal already set")
        self.terminal = terminal
        self.terminal.handler_ids.append(
            self.terminal.connect("grab-focus", self.on_terminal_focus)
        )
        self.terminal.handler_ids.append(
            self.terminal.connect("button-press-event", self.on_button_press, None)
        )
        self.terminal.handler_ids.append(
            self.terminal.connect("child-exited", self.on_terminal_exited)
        )
        self.terminal_hbox.pack_start(self.terminal, True, True, 0)
        self.terminal.show()
        self.add_scroll_bar()

    def add_scroll_bar(self):
        """Packs the scrollbar."""
        adj = self.terminal.get_vadjustment()
        self.scroll = Gtk.Scrollbar.new(Gtk.Orientation.VERTICAL, adj)
        self.scroll.show()
        self.terminal_hbox.pack_start(self.scroll, False, False, 0)

        self.terminal.handler_ids.append(
            self.terminal.connect("scroll-event", self.__scroll_event_cb)
        )

    def __scroll_event_cb(self, widget, event):
        # Adjust scrolling speed when adding "shift" or "shift + ctrl"
        adj = self.scroll.get_adjustment()
        page_size = adj.get_page_size()
        if (
            event.get_state() & Gdk.ModifierType.SHIFT_MASK
            and event.get_state() & Gdk.ModifierType.CONTROL_MASK
        ):
            # Ctrl + Shift + Mouse Scroll (4 pages)
            adj.set_page_increment(page_size * 40)
        elif event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            # Shift + Mouse Scroll (1 page)
            adj.set_page_increment(page_size * 10)
        else:
            # Mouse Scroll
            adj.set_page_increment(page_size)

    def get_terminal(self):
        return self.terminal

    def get_terminals(self):
        if self.terminal is not None:
            return [self.terminal]
        return []

    def iter_terminals(self):
        if self.terminal is not None:
            yield self.terminal

    def replace_child(self, old, new):
        print("why would you call this on me?")
        pass

    def unset_terminal(self, *args):
        self.terminal = None

    def split_h(self, split_percentage: int = 50):
        return self.split(DualTerminalBox.ORIENT_V, split_percentage)

    def split_v(self, split_percentage: int = 50):
        return self.split(DualTerminalBox.ORIENT_H, split_percentage)

    def split_h_no_save(self, split_percentage: int = 50):
        return self.split_no_save(DualTerminalBox.ORIENT_V, split_percentage)

    def split_v_no_save(self, split_percentage: int = 50):
        return self.split_no_save(DualTerminalBox.ORIENT_H, split_percentage)

    @save_tabs_when_changed
    def split(self, orientation, split_percentage: int = 50):
        self.split_no_save(orientation, split_percentage)

    def split_no_save(self, orientation, split_percentage: int = 50):
        notebook = self.get_notebook()
        parent = self.get_parent()  # RootTerminalBox

        if orientation == DualTerminalBox.ORIENT_H:
            position = self.get_allocation().width * ((100 - split_percentage) / 100)
        else:
            position = self.get_allocation().height * ((100 - split_percentage) / 100)

        log.debug(
            "[PANE-SPLIT] orient=%s split_percentage=%s alloc=(w=%d,h=%d) "
            "computed_position=%.1f",
            "H" if orientation == DualTerminalBox.ORIENT_H else "V",
            split_percentage,
            self.get_allocation().width,
            self.get_allocation().height,
            position,
        )

        terminal_box = TerminalBox()
        terminal = notebook.terminal_spawn()
        terminal_box.set_terminal(terminal)
        dual_terminal_box = DualTerminalBox(orientation)
        dual_terminal_box.set_stored_split_percentage(split_percentage)
        dual_terminal_box.set_position(position)
        parent.replace_child(self, dual_terminal_box)
        dual_terminal_box.set_child_first(self)
        dual_terminal_box.set_child_second(terminal_box)
        terminal_box.show()
        dual_terminal_box.show()
        if self.terminal is not None:
            # preserve font and font_scale in the new terminal
            terminal.set_font(self.terminal.font)
            terminal.font_scale = self.terminal.font_scale
        notebook.terminal_attached(terminal)

        return dual_terminal_box

    def get_guake(self):
        return self.get_parent().get_guake()

    def get_window(self):
        return self.get_parent().get_window()

    def get_settings(self):
        return self.get_parent().get_settings()

    def get_root_box(self):
        return self.get_parent().get_root_box()

    def get_notebook(self):
        return self.get_parent().get_notebook()

    def remove_dead_child(self, child):
        print('Can\'t do, have no "child"')

    def on_terminal_focus(self, *args):
        self.get_root_box().set_last_terminal_focused(self.terminal)

    def on_terminal_exited(self, terminal, status):
        if not self.get_parent():
            return
        self.get_parent().remove_dead_child(self)

    def on_button_press(self, target, event, user_data):
        if event.button == 3:
            # First send to background process if handled, do nothing else
            if (
                not event.get_state() & Gdk.ModifierType.SHIFT_MASK
                and Vte.Terminal.do_button_press_event(self.terminal, event)
            ):
                return True

            menu = mk_terminal_context_menu(
                self.terminal,
                self.get_window(),
                self.get_settings(),
                TerminalContextMenuCallbacks(
                    self.terminal,
                    self.get_window(),
                    self.get_settings(),
                    self.get_root_box().get_notebook(),
                ),
            )
            menu.connect("hide", MenuHideCallback(self.get_window()).on_hide)
            HidePrevention(self.get_window()).prevent()
            try:
                menu.popup_at_pointer(event)
            except AttributeError:
                # Gtk 3.18 fallback ("'Menu' object has no attribute 'popup_at_pointer'")
                menu.popup(None, None, None, None, event.button, event.time)
            self.terminal.grab_focus()
            return True
        self.terminal.grab_focus()
        return False


class DualTerminalBox(Gtk.Paned, TerminalHolder):

    ORIENT_H = 0
    ORIENT_V = 1

    def __init__(self, orientation):
        super().__init__()

        self.orient = orientation
        self._save_position_timeout_id = None
        self._stored_split_percentage = 50
        if orientation is DualTerminalBox.ORIENT_H:
            self.set_orientation(orientation=Gtk.Orientation.HORIZONTAL)
        else:
            self.set_orientation(orientation=Gtk.Orientation.VERTICAL)

        # Connect to position change signal to save tabs when pane is resized
        self.connect("notify::position", self._on_position_changed)

    def _safe_get_guake(self):
        try:
            return self.get_guake()
        except (AttributeError, RuntimeError):
            return None

    def _position_save_is_suppressed(self, guake):
        return bool(
            guake
            and (
                getattr(guake, "_session_restoring", False)
                or getattr(guake, "_pending_size_reset", False)
                or getattr(guake, "_pane_ratio_adjusting", False)
                or getattr(guake, "_pane_adjust_timeout_id", None) is not None
            )
        )

    def _split_total(self):
        allocation = self.get_allocation()
        if self.orient is DualTerminalBox.ORIENT_V:
            return allocation.height, allocation
        return allocation.width, allocation

    def set_stored_split_percentage(self, split_percentage):
        try:
            ratio = int(round(float(split_percentage)))
        except (TypeError, ValueError):
            ratio = 50
        self._stored_split_percentage = max(1, min(99, ratio))

    def get_stored_split_percentage(self):
        return self._stored_split_percentage

    def calculate_current_split_percentage(self):
        total, allocation = self._split_total()
        if total < MIN_PANE_ALLOC_PX:
            raise DegenerateAllocationError(
                f"DualTerminalBox id={id(self)} alloc total={total} too small "
                f"(<{MIN_PANE_ALLOC_PX}); aborting save"
            )

        raw_ratio = 100 - (self.get_position() / total * 100)
        ratio = max(1, min(99, int(round(raw_ratio))))
        log.debug(
            "[PANE-RATIO] id=%s orient=%s position=%d alloc=(w=%d,h=%d) " "total=%d -> ratio=%d",
            id(self),
            "V" if self.orient is DualTerminalBox.ORIENT_V else "H",
            self.get_position(),
            allocation.width,
            allocation.height,
            total,
            ratio,
        )
        return ratio

    def remember_current_split_percentage(self):
        self.set_stored_split_percentage(self.calculate_current_split_percentage())

    def apply_stored_split_percentage(self):
        total, allocation = self._split_total()
        if total < MIN_PANE_ALLOC_PX:
            log.debug(
                "[PANE-RATIO-APPLY-SKIP] id=%s orient=%s alloc=(w=%d,h=%d) "
                "total=%d below MIN_PANE_ALLOC_PX=%d",
                id(self),
                "V" if self.orient is DualTerminalBox.ORIENT_V else "H",
                allocation.width,
                allocation.height,
                total,
                MIN_PANE_ALLOC_PX,
            )
            return False

        position = int(total * ((100 - self._stored_split_percentage) / 100))
        if total <= MIN_PANE_ALLOC_PX * 2:
            position = max(1, total // 2)
        else:
            position = max(MIN_PANE_ALLOC_PX, min(total - MIN_PANE_ALLOC_PX, position))

        log.debug(
            "[PANE-RATIO-APPLY] id=%s orient=%s ratio=%d alloc=(w=%d,h=%d) "
            "total=%d -> position=%d",
            id(self),
            "V" if self.orient is DualTerminalBox.ORIENT_V else "H",
            self._stored_split_percentage,
            allocation.width,
            allocation.height,
            total,
            position,
        )
        self.set_position(position)
        return True

    def _on_position_changed(self, widget, param):
        """Called when the pane divider position changes. Debounce the save to avoid
        excessive saves during continuous dragging."""
        try:
            pos = self.get_position()
            alloc = self.get_allocation()
            log.debug(
                "[PANE-NOTIFY] notify::position id=%s orient=%s pos=%d " "alloc=(w=%d,h=%d)",
                id(self),
                "V" if self.orient is DualTerminalBox.ORIENT_V else "H",
                pos,
                alloc.width,
                alloc.height,
            )
        except Exception as e:  # noqa: BLE001
            log.debug("[PANE-NOTIFY] error reading state: %s", e)

        g = self._safe_get_guake()
        if self._position_save_is_suppressed(g):
            log.debug("[PANE-NOTIFY] save suppressed for transient/programmatic position change")
            return

        try:
            self.remember_current_split_percentage()
        except DegenerateAllocationError as e:
            log.debug("[PANE-NOTIFY] ignoring position change without allocation: %s", e)
            return

        # Cancel any pending save
        if self._save_position_timeout_id is not None:
            GLib.source_remove(self._save_position_timeout_id)

        # Schedule a save after 500ms of no position changes
        self._save_position_timeout_id = GLib.timeout_add(500, self._do_save_tabs)

    def _do_save_tabs(self):
        """Actually save the tabs after debounce period."""
        self._save_position_timeout_id = None
        g = self.get_guake()
        save_enabled = bool(g and g.settings.general.get_boolean("save-tabs-when-changed"))
        session_restoring = bool(getattr(g, "_session_restoring", False)) if g else False
        save_suppressed = self._position_save_is_suppressed(g)
        log.debug(
            "[PANE-SAVE-TIMER] fired id=%s save_enabled=%s session_restoring=%s "
            "save_suppressed=%s",
            id(self),
            save_enabled,
            session_restoring,
            save_suppressed,
        )
        if g and save_enabled and not save_suppressed:
            g.save_tabs()
        return False  # Don't repeat the timeout

    def get_split_ratio(self):
        """Get the current split ratio as a percentage (0-100).

        The ratio represents the percentage of space allocated to the FIRST child.
        For example, a ratio of 60 means the first child gets 60% of the space.
        """
        position = self.get_position()
        allocation = self.get_allocation()

        if self.orient is DualTerminalBox.ORIENT_V:
            total = allocation.height
        else:
            total = allocation.width

        if total <= 0:
            return 50  # Default to 50% if we can't calculate

        # Position is the size of the first child
        ratio = (position / total) * 100
        return max(1, min(99, ratio))  # Clamp between 1% and 99%

    def set_split_ratio(self, ratio):
        """Set the split position based on a percentage ratio.

        Args:
            ratio: Percentage (0-100) of space to allocate to the first child.
        """
        allocation = self.get_allocation()

        if self.orient is DualTerminalBox.ORIENT_V:
            total = allocation.height
        else:
            total = allocation.width

        if total <= 0:
            return  # Can't set position if we don't have allocation yet

        # Calculate new position from ratio
        new_position = int((ratio / 100) * total)
        # Ensure minimum size for both children (at least 10 pixels each)
        new_position = max(10, min(total - 10, new_position))
        self.set_position(new_position)

    def set_child_first(self, terminal_holder):
        if isinstance(terminal_holder, TerminalHolder):
            self.add1(terminal_holder)
        else:
            print("wtf, what have you added to me???")

    def set_child_second(self, terminal_holder):
        if isinstance(terminal_holder, TerminalHolder):
            self.add2(terminal_holder)
        else:
            print("wtf, what have you added to me???")

    def get_terminals(self):
        return self.get_child1().get_terminals() + self.get_child2().get_terminals()

    def iter_terminals(self):
        yield from self.get_child1().iter_terminals()
        yield from self.get_child2().iter_terminals()

    def replace_child(self, old, new):
        if self.get_child1() is old:
            self.remove(old)
            self.set_child_first(new)
        elif self.get_child2() is old:
            self.remove(old)
            self.set_child_second(new)
        else:
            print("I have never seen this widget!")

    def get_guake(self):
        return self.get_parent().get_guake()

    def get_window(self):
        return self.get_parent().get_window()

    def get_settings(self):
        return self.get_parent().get_settings()

    def get_root_box(self):
        return self.get_parent().get_root_box()

    def get_notebook(self):
        return self.get_parent().get_notebook()

    def grab_box_terminal_focus(self, box):
        if isinstance(box, DualTerminalBox):
            try:
                next(box.iter_terminals()).grab_focus()
            except StopIteration:
                log.error("Both panes are empty")
        else:
            box.get_terminal().grab_focus()

    @save_tabs_when_changed
    def remove_dead_child(self, child):
        if self.get_child1() is child:
            living_child = self.get_child2()
            self.remove(living_child)
            self.get_parent().replace_child(self, living_child)
            self.grab_box_terminal_focus(living_child)
        elif self.get_child2() is child:
            living_child = self.get_child1()
            self.remove(living_child)
            self.get_parent().replace_child(self, living_child)
            self.grab_box_terminal_focus(living_child)
        else:
            print("I have never seen this widget!")


# Foreground color applied to a background tab's title when it has unseen
# activity. Chosen to stay readable on both light and dark tab bars.
TAB_ACTIVITY_COLOR = "#E8A33D"


class TabLabelEventBox(Gtk.EventBox):
    def __init__(self, notebook, text, settings):
        super().__init__()
        self.notebook = notebook
        self._text = text
        self._activity = False
        self.box = Gtk.Box(homogeneous=Gtk.Orientation.HORIZONTAL, spacing=0, visible=True)
        self.label = Gtk.Label(label=text, visible=True)
        self.close_button = Gtk.Button(
            image=Gtk.Image.new_from_icon_name("window-close", Gtk.IconSize.MENU),
            relief=Gtk.ReliefStyle.NONE,
        )
        self.close_button.connect("clicked", self.on_close)
        settings.general.bind(
            "tab-close-buttons", self.close_button, "visible", Gio.SettingsBindFlags.GET
        )
        self.box.pack_start(self.label, True, True, 0)
        self.box.pack_end(self.close_button, False, False, 0)
        self.add(self.box)
        self.connect("button-press-event", self.on_button_press, self.label)

    def set_text(self, text):
        self._text = text
        self._render()

    def get_text(self):
        return self._text

    def set_activity(self, active):
        """Highlight (or clear) this tab's title to signal unseen output.

        Returns True if the activity state actually changed, so callers can
        avoid redundant re-rendering on the frequent contents-changed signal.
        """
        active = bool(active)
        if active == self._activity:
            return False
        self._activity = active
        self._render()
        return True

    def get_activity(self):
        return self._activity

    def _render(self):
        if self._activity:
            self.label.set_markup(
                f'<span foreground="{TAB_ACTIVITY_COLOR}" weight="bold">'
                f"{GLib.markup_escape_text(self._text)}</span>"
            )
        else:
            self.label.set_text(self._text)

    def grab_focus_on_last_focused_terminal(self):
        server_time = get_server_time(self.notebook.guake.window)
        self.notebook.guake.window.get_window().focus(server_time)
        self.notebook.get_current_terminal().grab_focus()

    def on_button_press(self, target, event, user_data):
        if event.button == 3:
            menu = mk_tab_context_menu(self)
            menu.connect("hide", MenuHideCallback(self.get_toplevel()).on_hide)
            HidePrevention(self.get_toplevel()).prevent()
            try:
                menu.popup_at_pointer(event)
            except AttributeError:
                # Gtk 3.18 fallback ("'Menu' object has no attribute 'popup_at_pointer'")
                menu.popup(None, None, None, None, event.button, event.get_time())
            return True
        if event.button == 2:
            prompt_cfg = self.notebook.guake.settings.general.get_int("prompt-on-close-tab")
            self.notebook.delete_page_by_label(self, prompt=prompt_cfg)
            return True
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            self.on_rename(None)

        return False

    @save_tabs_when_changed
    def on_new_tab(self, user_data):
        self.notebook.new_page_with_focus()

    @save_tabs_when_changed
    def on_rename(self, user_data):
        HidePrevention(self.get_toplevel()).prevent()
        dialog = RenameDialog(self.notebook.guake.window, self.label.get_text())
        r = dialog.run()
        if r == Gtk.ResponseType.ACCEPT:
            new_text = TabNameUtils.shorten(dialog.get_text(), self.notebook.guake.settings)
            page_num = self.notebook.find_tab_index_by_label(self)
            self.notebook.rename_page(page_num, new_text, True)
        dialog.destroy()
        HidePrevention(self.get_toplevel()).allow()

        self.grab_focus_on_last_focused_terminal()

    @save_tabs_when_changed
    def on_reset_custom_colors(self, user_data):
        HidePrevention(self.get_toplevel()).prevent()
        if PromptResetColorsDialog(self.notebook.guake.window).reset_tab_custom_colors():
            page_num = self.notebook.find_tab_index_by_label(self)
            for t in self.notebook.get_nth_page(page_num).iter_terminals():
                t.reset_custom_colors()
            self.notebook.guake.set_colors_from_settings_on_page(page_num=page_num)
        HidePrevention(self.get_toplevel()).allow()

        self.grab_focus_on_last_focused_terminal()

    def on_close(self, user_data):
        prompt_cfg = self.notebook.guake.settings.general.get_int("prompt-on-close-tab")
        self.notebook.delete_page_by_label(self, prompt=prompt_cfg)
