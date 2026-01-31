# Task Completion Checklist

When completing a task in the Guake project, follow this checklist:

## Before Committing Code

### 1. Code Quality Checks

```bash
# Run all style checks (pre-commit hooks)
make style

# OR run checks individually:
make black       # Format code
make flake8      # Lint with flake8
make pylint      # Lint with pylint
```

### 2. Run Tests

```bash
# Run all tests
make test

# For test coverage report
make test-coverage
```

### 3. Verify Application Runs

```bash
# Run the application locally
make run-local

# Test with verbose logging if needed
make run-local V=1
```

### 4. If Schema Changed

```bash
# Recompile GSettings schema
make compile-glib-schemas-dev
```

### 5. If Translations Changed

```bash
# Update translation files
make update-po
make generate-mo
make install-dev-locale
```

## Commit Message Guidelines

- Use clear, descriptive commit messages
- Reference issue numbers if applicable

## For New Features

1. Add appropriate tests in `guake/tests/`
2. Update documentation if needed
3. Create release note:
   ```bash
   make reno SLUG=brief_description_of_change
   ```

## For Bug Fixes

1. Add regression test if possible
2. Verify fix with manual testing
3. Create release note if significant:
   ```bash
   make reno SLUG=fix_brief_description
   ```

## Common Issues

### Schema Errors
If you see GLib schema errors, recompile:
```bash
make compile-glib-schemas-dev
```

### Import Errors
Ensure GTK system packages are accessible:
```bash
pew toggleglobalsitepackages  # If using pew
```

### Test Failures
Run tests with more verbosity:
```bash
pipenv run pytest -v guake/tests/
```
