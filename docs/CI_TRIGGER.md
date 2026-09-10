# CI Trigger

This file exists to trigger a fresh CI run after the import-path fix in the workflow.

The previous CI failure was caused by the test runner not resolving the repository package. The workflow now sets `PYTHONPATH=.` and invokes `python -m pytest -q`.

No secrets are stored in this repository.
