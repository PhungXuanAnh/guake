# Multi-Monitor Pane Position Fix

## Problem

When moving Guake between monitors with different resolutions, panes could disappear because:

1. `Gtk.Paned` (which `DualTerminalBox` extends) stores divider positions as **absolute pixels**, not percentages
2. When the window becomes smaller (e.g., moving from 2560x1440 to 1920x1080), the absolute pixel position might exceed the new window size
3. This causes child widgets to receive 0 or negative allocation, making them **disappear**

### Example Scenario

```
1. Configure panes on a 2560px wide monitor
   - Split position: 1600px (62% split)
   
2. Move Guake to a 1366px monitor
   - Split position stays: 1600px (unchanged)
   - First child gets: 1600px (but window is only 1366px!)
   - GTK clips first child to 1366px (fills entire space)
   - Second child gets: 1366 - 1600 = -234px → clipped to 0 → DISAPPEARS!
```

## Solution

This fix implements **automatic proportional adjustment** of pane positions when the window size changes significantly (indicating a monitor switch).

### How It Works

1. **Window Configure Event Handler** (`_on_window_configure` in `guake_app.py`)
   - Monitors window resize events
   - Detects significant size changes (>5% in width or height)
   - Triggers pane adjustment with debouncing (100ms delay to let resize settle)

2. **Ratio Collection** (`_collect_pane_ratios` in `RootTerminalBox`)
   - Recursively traverses all `DualTerminalBox` instances
   - Captures current split ratios as percentages before adjustment

3. **Ratio Application** (`_apply_pane_ratios` in `RootTerminalBox`)
   - After GTK processes the resize, applies the saved ratios
   - Calculates new absolute positions based on new container sizes
   - Ensures minimum 10px for each child to prevent disappearance

### New Methods

#### In `DualTerminalBox` (boxes.py)

- `get_split_ratio()` - Returns current split ratio as percentage (0-100)
- `set_split_ratio(ratio)` - Sets split position based on percentage ratio

#### In `RootTerminalBox` (boxes.py)

- `adjust_panes_for_new_size()` - Entry point for pane adjustment
- `_collect_pane_ratios(box, ratios)` - Recursively collects all ratios
- `_apply_pane_ratios(box, ratios)` - Recursively applies ratios

#### In `Guake` (guake_app.py)

- `_on_window_configure(window, event)` - Handles window configure events
- `_do_adjust_all_pane_positions()` - Adjusts panes across all notebooks/pages

### Features

- **Automatic**: No user intervention needed
- **Debounced**: Avoids excessive recalculations during resize
- **Proportional**: Maintains relative pane sizes
- **Safe**: Ensures minimum 10px allocation for each pane
- **Multi-workspace aware**: Adjusts panes in all notebooks

## Testing

To test the fix:

1. Open Guake with split panes on your primary monitor
2. Use the setting or command to move Guake to a different monitor with different resolution
3. Panes should automatically adjust their positions to maintain proportions
4. No panes should disappear

## Files Modified

- `guake/boxes.py` - Added ratio get/set methods and adjustment logic
- `guake/guake_app.py` - Added window configure event handling
