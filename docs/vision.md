# Vision

## In one sentence

Flash an SD card, plug in the board, open it from your phone, say what is connected to
each pin, and create sequences and automations without writing code.

## Who it is for

People who want to bring physical things to life but do not program: makers and hobbyists,
associations (nativity scenes, amateur theatre), small shops (window displays), escape rooms,
small museums, teachers, model railway builders, Halloween and Christmas decorators.

Primum was born to automate a mechanical nativity scene, but nothing in it is specific to one.

## What makes it different

- **Sequences and automations together.** Show tools have timelines but no rules; home
  automation tools have rules but no timelines. Primum has both, and an automation can
  start a sequence.
- **Mixed hardware.** A Raspberry Pi coordinates other boards (ESP32 over Wi-Fi, Arduino over
  a cable) and a single sequence can span all of them.
- **Local first.** Everything works without Internet. The cloud is optional.
- **Safety by design.** Every output has a safe state, motors have hard limits, there is
  always a panic button, and the AI never moves hardware without the user's confirmation.
- **AI that proposes, a validator that decides, a human that accepts.** Through an MCP
  server (the user's own Claude or similar) and, later, a built-in chat with the user's own key.

## Version 1 (Raspberry Pi 4B only)

- Primum OS image: flash, boot, connect to its own Wi-Fi, configure from the phone.
- Hardware: digital outputs (LEDs, relays), digital inputs (buttons, presence sensors),
  hardware PWM (dimming, servos), I2C devices, LED strips, audio.
- Projects as a workspace of files: sequences, automations, events, schedules, variables
  with scopes, reusable components.
- Local web UI: elements, sequences, automations, daily control, alerts.
- Deployment packages validated on the board, atomic activation and rollback.
- Local MCP server.

## Not in version 1

ESP32 and Arduino boards, the desktop app (Primum Studio), the cloud, accounts and tiers,
the built-in AI chat, Zigbee/Matter, native mobile apps, external radio modules.
They are planned (see `plan.md`) and the architecture leaves room for them.

## Principles

1. The device executes validated data, never new code.
2. One source for each concept; everything else is generated from it.
3. Safety above features.
4. Works offline; the cloud only adds.
5. Simple for a non-programmer, honest about what the hardware can do.
