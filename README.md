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

Requirements: [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

```bash
just sync     # install the Python environment
just check    # lint, types, architecture rules and tests (same as CI)
just watch    # re-run tests on every save
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow.

## License

[Apache-2.0](LICENSE)
