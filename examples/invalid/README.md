# Invalid projects

One small project per conflict a board can have, named after the code it gives: run
`uv run primum validate examples/invalid/<name> --lang es` to see the message. A test checks that
each one gives exactly its code (`packages/cli/tests/test_validate.py`).
