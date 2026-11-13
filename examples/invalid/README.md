# Invalid projects

One small project per problem, named after the code it gives: the conflicts a board can have
(`pin-*`, `pwm-*`, `bus-*`, `i2c-*`, `board-*`), and what an element cannot do or be given
(`action-*`, `track-*`, `config-*`). Run
`uv run primum validate examples/invalid/<name> --lang es` to see the message. A test checks that
each one gives exactly its code (`packages/cli/tests/test_validate.py`).
