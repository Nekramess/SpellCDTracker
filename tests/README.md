# SpellCDTracker tests (simulated Forever client)

Python + lupa (Lua 5.1). Run from the repo root:

    pip install --break-system-packages lupa
    python3 tests/run_all.py            # every *_test.py, per-file counts, non-zero exit on any FAIL
    python3 tests/<name>_test.py        # one file
    python3 tests/mutation_check.py     # breaks a temp COPY of SpellCDTracker.lua, expects a failure each time

- `mock_env.py` shared client: Forever-like globals, a secret-value stub that throws on arithmetic/comparison/concat/index, `issecretvalue`.
  `SCDT_LUA=/path/to/copy.lua` points the suite at another copy of the addon.
- `forever_api_check_test.py` re-verifies the mocks against the Forever UI source (`FOREVER_UI`, default `/tmp/claude-0/forever-ui/wow-ui-source`; SKIPs without it).
- `XFAIL` lines are tests of desired behaviour that currently fail because of a known addon bug; they do not fail the suite and print `XPASS` once fixed.

Simulated client only; not tested in the live Forever client.
