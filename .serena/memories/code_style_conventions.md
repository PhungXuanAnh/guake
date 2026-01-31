# Guake Code Style and Conventions

## Python Version
- Minimum Python 3.8
- Uses type hints sparingly (typing module imported for Python < 3.5 compatibility)

## Code Formatting

### Black
- **Line length**: 100 characters
- **Target version**: Python 3.6+
- Configuration in `pyproject.toml`

### Indentation
- Python files: 4 spaces
- YAML/HTML/CSS: 2 spaces
- Makefile: tabs
- Configuration in `.editorconfig`

## Linting

### Flake8 (`.flake8`)
```ini
max-line-length = 100
max-complexity = 25
exclude = env,.direnv,docs
builtins = _
```

Ignored errors:
- E226, E302, E41, E402 - various formatting
- C901 - complexity
- E722 - bare except
- W503 - line break before binary operator
- E231 - missing whitespace after ','

### Pylint (`.pylintrc`)
- Jobs: 4 parallel processes
- Many rules configured for GTK/GLib compatibility

## Pre-commit Hooks (`.pre-commit-config.yaml`)

Runs on every commit:
1. `end-of-file-fixer` - ensures files end with newline
2. `trailing-whitespace` - removes trailing whitespace
3. `flake8` - linting
4. `pylint` - linting
5. `black` - formatting
6. `fiximports` - import sorting

## File Headers

All Python files include:
```python
# -*- coding: utf-8; -*-
"""
Copyright (C) 2007-2012 Lincoln de Sousa <lincoln@minaslivre.org>
...
This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License...
"""
```

## Import Style

Imports ordered by:
1. Standard library
2. Third-party (gi, cairo, etc.)
3. Local imports (guake.*)

GTK/GLib imports require version specification:
```python
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk
```

## Logging

Uses Python `logging` module:
```python
import logging
log = logging.getLogger(__name__)

log.info("Message")
log.debug("Debug message")
log.exception("Error with traceback")
```

## Naming Conventions

- **Classes**: PascalCase (`Guake`, `NotebookManager`)
- **Functions/Methods**: snake_case (`get_notebook`, `show_hide`)
- **Constants**: UPPER_SNAKE_CASE (`RESPONSE_FORWARD`, `GDK_WINDOW_STATE_WITHDRAWN`)
- **Module-level variables**: lowercase (`log`, `instance`)

## Testing Conventions

- Use `pytest` with fixtures
- Use `mocker` for mocking (pytest-mock)
- Use `fs` fixture for filesystem mocking (pyfakefs)
- Test files: `test_*.py` in `guake/tests/`
- Test functions: `test_*`

Example:
```python
@pytest.fixture
def g(mocker, fs):
    mocker.patch("guake.guake_app.Guake.get_xdg_config_directory", return_value=Path("/foobar"))
    # ...
    return Guake()

def test_accel_search_terminal(g):
    nb = g.get_notebook()
    # assertions...
```

## GTK/Glade Patterns

- UI defined in `.glade` files (XML)
- `SimpleGladeApp` base class for loading Glade files
- Widgets accessed via `get_widget("widget-name")`
- Callbacks connected via `add_callbacks(self)`

## Decorators

Custom decorators used:
```python
@save_tabs_when_changed  # Auto-save tabs after method execution
def some_tab_modifying_method(self):
    pass
```
