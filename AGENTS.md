Notes for running tests in varied environments

- To avoid interference and run just this project's tests, disable auto-loading of external plugins when invoking pytest:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`
- This does not change test behavior; it simply prevents unrelated third-party plugins from being imported.
