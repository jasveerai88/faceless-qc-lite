# Contributing

Thanks for helping keep Lite free and useful.

- **Bug reports:** open an issue with your OS, Python and FFmpeg versions, the command you ran, and the full output.
- **Test runs:** Windows and macOS runs are especially wanted — see issue #2.
- **New checks:** propose the check in an issue first, with a real example file result. Checks are accepted only with a measurable gate (a number and a threshold), never vibes.
- **Code:** Python stdlib + FFmpeg only — no new dependencies. Keep it local-only: no network calls, no telemetry, ever.
- Run `python3 tests/test_lite.py` before sending a pull request.
