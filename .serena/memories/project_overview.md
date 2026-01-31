# Guake Project Overview

## Purpose
Guake is a Python-based dropdown terminal application made for the GNOME desktop environment. Its style is inspired by FPS game terminals (like Quake), providing easy access via a single key press (F12 by default).

## Tech Stack

### Core Technologies
- **Language**: Python 3.8+
- **GUI Framework**: GTK 3.0 (via PyGObject/gi)
- **Terminal Widget**: VTE (Virtual Terminal Emulator)
- **IPC**: D-Bus (for remote control and toggle functionality)
- **Configuration**: GSettings with custom GLib schema

### Key Dependencies
- `PyGObject` - GTK bindings for Python
- `pycairo` - Cairo graphics library bindings
- `dbus-python` - D-Bus bindings
- `pyyaml` - YAML parsing for configuration
- `pbr` - Python Build Reasonableness (versioning)

## Project Structure

```
guake/
├── main.py          # Entry point, exec_main()
├── guake_app.py     # Main Guake class - core application logic
├── terminal.py      # Terminal widget handling
├── notebook.py      # Tab/notebook management
├── prefs.py         # Preferences dialog
├── settings.py      # GSettings wrapper
├── keybindings.py   # Keyboard shortcut handling
├── dbusiface.py     # D-Bus interface
├── guake_toggle.py  # Toggle guake via D-Bus
├── utils.py         # Utility functions
├── boxes.py         # Terminal split containers
├── theme.py         # GTK theme handling
├── palettes.py      # Color palette definitions
├── paths.py         # Path configuration (generated)
├── data/            # Glade files, schemas, icons
│   ├── *.glade      # GTK UI definitions
│   ├── org.guake.gschema.xml  # GSettings schema
│   └── pixmaps/     # Icons and images
├── tests/           # pytest test files
└── po/              # Localization files
```

## Entry Points

Defined in `setup.cfg`:
- `guake = guake.main:exec_main` - Main application
- `guake-toggle = guake.guake_toggle:toggle_guake_by_dbus` - Toggle visibility

## Key Classes

- `Guake` (guake_app.py) - Main application class, handles window, tabs, accelerators
- `NotebookManager` (notebook.py) - Manages terminal tabs
- `Settings` (settings.py) - Wrapper for GSettings configuration
- `SimpleGladeApp` (simplegladeapp.py) - Base class for Glade-based GTK apps
