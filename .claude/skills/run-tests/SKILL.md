---
name: run-tests
description: Run OneKey's full check - Lua 5.1 compile, macro and data tests, the simulated WoW client for all nine classes, the fuzz run, coverage, the mutation check and the security scan - and read the results. Use after any change to the addon.
---

# Run the OneKey tests

1. Make sure Lua 5.1 is available through lupa:
   `python3 -c "from lupa.lua51 import LuaRuntime"`; if not,
   `pip install --require-hashes -r tests/requirements.txt`
   (in a sandbox add `--break-system-packages` if pip asks).
2. Run, from the repository root, in this order:
   ```
   python3 -I tests/run_tests.py --json test-results.json
   python3 -I tests/fuzz_test.py --runs 40
   OKD_COVERAGE=1 python3 -I tests/run_tests.py --min-coverage 65
   python3 -I tests/mutation_check.py
   python3 -I security/scan.py
   ```
   Before a release, run the fuzz with `--runs 500`. The gates and the
   requirement table are in `docs/TEST_STRATEGY.md`; a new requirement
   needs a row there and a test, or the traceability test fails.
   `-k WORD` on run_tests.py runs only the tests whose name has WORD
   (`-k macro`, `-k smoke`, `-k questdata`).
3. Reading failures:
   - `taint: SetAttribute(...) in combat` — a secure button or binding
     changed during combat; move the change to an out-of-combat path.
   - `attempt to compare table with number` / `compared a secret value` —
     health or power was compared; use the game's curves instead.
   - `level N cat fight lost Faerie Fire`, `... chars` — a macro went over
     255 characters and `fit()` dropped a line; shorten or merge lines.
   - `attempt to call global 'X' (a nil value)` in a smoke test — the
     addon uses an API the fake client lacks; add it to
     `tests/wowstub.lua` with the real client's behaviour (check the API in
     the Warcraft Wiki), do not just make it return nil.
   - `MISSED` in the mutation check — a guard stopped catching its fault;
     the guard is broken, not the mutant. `BASELINE FAILED` means the
     unchanged suite fails: fix that first, or every mutant looks caught.
   - `FAIL seed N` in the fuzz run — replay it with
     `python3 -I tests/fuzz_test.py --seed N`.
4. Only call the work done when all five commands exit 0.
