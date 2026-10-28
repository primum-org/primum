# 0001. Python for core and the Linux runtime; TypeScript for the UI

- Status: Accepted
- Date: 2026-10-28

## Context
The runtime runs on a Raspberry Pi and talks to GPIO, I2C, PWM, LED strips and audio. The
core must be shared by the runtime, a desktop app and a backend. Development leans heavily on
AI assistants, and the author must be able to review what they write.

## Decision
- `primum-core` and `primum-runtime` in **Python 3.13** (the version of current Raspberry Pi OS),
  with strict typing (pyright strict), pydantic at the edges and uv for environments.
- The UI in **TypeScript with Vue 3**.
- Microcontroller firmware (later) in **C++ with PlatformIO**.
- Rust is reserved for well-bounded modules later (PyO3 extensions, WASM build of `core`,
  Primum Studio's native side with Tauri).

## Alternatives considered
- **C** for the runtime: memory-unsafe in a networked service running as root, and slow to
  build HTTP/JSON/SQLite on. AI-written C hides memory bugs that are hard to review.
- **Rust or Go** for the runtime: good fits, but unknown to the author; learning them would
  slow version 1. Rust stays as a later, bounded addition.

## Consequences
- The richest ecosystem for Raspberry Pi hardware (libgpiod, smbus2, Adafruit drivers) is available.
- Timing-critical work goes to hardware (hardware PWM, DMA) or to microcontrollers, not to Python loops.
- Strict types, tests and CI are mandatory to keep AI-written code reviewable.
- `core` must stay pure and small so it can be reimplemented in Rust without changing callers.
