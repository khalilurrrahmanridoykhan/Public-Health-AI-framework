# Contributing to PHFrame

Thank you for helping improve PHFrame. Bug reports, documentation fixes, tests, and focused feature proposals are welcome.

## Development setup

1. Fork and clone the repository.
2. Create a virtual environment with Python 3.10 or newer.
3. Install the project and development dependencies:

   ```bash
   python -m pip install -e ".[dev]"
   ```

4. Run the test suite:

   ```bash
   pytest
   ```

## Pull requests

- Create a focused branch from `main`.
- Add or update tests for behavioral changes.
- Update the README or changelog when user-facing behavior changes.
- Keep commits small and describe why the change is needed.
- Do not commit credentials, health records, or other sensitive data.

Before opening a pull request, confirm that all tests pass locally. Describe the problem, the chosen approach, and any compatibility or migration impact in the pull-request summary.

## Issues

For bugs, include the PHFrame version, Python version, operating system, a minimal reproducible example, and the full error message with secrets and sensitive data removed.

Security vulnerabilities should not be filed as public issues. Follow [SECURITY.md](SECURITY.md) instead.
