# Suggested Commands for Guake Development

## Development Environment Setup

```bash
# Install system dependencies (Debian/Ubuntu)
./scripts/bootstrap-dev-debian.sh run make

# OR use local install (from Makefile)
make local-install-system-dependencies

# Setup development environment with pipenv
make dev

# Alternative: Setup without pipenv
make dev-no-pipenv
```

## Running the Application

```bash
# Run locally in development mode
make run-local
# With verbose logging:
make run-local V=1

# Run preferences dialog
make run-local-prefs

# Local run without pipenv (using .venv)
.venv/bin/python guake/main.py --no-startup-script

# With DEBUG logging
.venv/bin/python guake/main.py --no-startup-script --verbose

# With debugpy for remote debugging
.venv/bin/python -m debugpy --listen 5678 guake/main.py --no-startup-script --verbose
```

## Code Quality & Linting

```bash
# Run all style checks (pre-commit hooks)
make style

# Run black formatter only
make black

# Run all checks (black-check, flake8, pylint)
make checks

# Individual checks
make black-check
make flake8
make pylint
```

## Testing

```bash
# Run all tests
make test

# Run tests with coverage
make test-coverage

# Run pytest directly
pipenv run pytest guake

# Run specific test file
pipenv run pytest guake/tests/test_guake.py

# Run specific test
pipenv run pytest guake/tests/test_guake.py::test_accel_search_terminal
```

## Building & Distribution

```bash
# Build all distributions
make build

# Build wheel only
make wheel

# Build source distribution
make sdist

# Clean build artifacts
make clean
```

## GSettings Schema

```bash
# Compile GSettings schema for development
make compile-glib-schemas-dev

# Reset all GSettings to defaults
make reset
```

## Localization

```bash
# Update .pot and .po files
make update-po

# Generate .mo files
make generate-mo

# Install locales for development
make install-dev-locale
```

## Installation

```bash
# System-wide installation (requires sudo)
sudo make install

# Uninstall
sudo make uninstall

# Reinstall (uninstall + install)
make reinstall
```

## Git Operations

```bash
# Standard git commands
git status
git diff
git add .
git commit -m "message"

# Amend and push (from Makefile)
make git-amend-push
```

## Release Notes

```bash
# Create new release note
make reno SLUG=my_change_description

# Lint release notes
make reno-lint

# Generate release notes for GitHub
make release-note-github
```

## Useful Aliases (in Makefile)

- `make check` = `make checks`
- `make devel` = `make dev`
- `make doc` = `make docs`
- `make run` = `make run-local`
- `make run-prefs` = `make run-local-prefs`
