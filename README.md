# Primum

**Bring things to life without writing code.**

Primum lets you create *sequences* (actions placed in time, like a video editor) and
*automations* (when → if → do) for lights, motors, sensors and sound, and run them on a
Raspberry Pi — fully local, no Internet required. ESP32 and Arduino boards will follow.

> 🚧 **Early development.** There is nothing to install yet. Follow the repository to see it grow.

*Primum* comes from **Primum Mobile**, the outermost sphere of medieval astronomy that set
all the others in motion.

## Documentation

- [Vision](docs/vision.md) — who it is for and what version 1 does
- [Architecture](docs/architecture.md) — layers and packages
- [Plan](docs/plan.md) — phases and current status
- [Glossary](docs/glossary.md) — the vocabulary (English ↔ Spanish)
- [Decisions](docs/decisions/) — why things are the way they are

## Development

Requirements: [uv](https://docs.astral.sh/uv/), which installs everything else (including
[just](https://just.systems/)) into the project environment, and [Node.js](https://nodejs.org/)
22 or later for the tests of the runtime's page (`just test-js`, part of `just check`).

```bash
uv sync              # install the environment (Python 3.13 and dev tools)
uv run just check    # lint, types, architecture rules, generated files and tests (what CI runs)
uv run just watch    # re-run tests on every save
uv run just pi-sync  # install this working tree on the development Pi (see image/README.md)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow.

## License

[Apache-2.0](LICENSE)
