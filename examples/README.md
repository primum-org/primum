# Example projects

Each folder is a Primum project (decision 0004): `project.json` and the files of the project.
Check one with `uv run primum validate examples/<name>`; a test keeps every example valid.

- `minimal/`: an LED on GPIO 17 that blinks when the phone's *Start* button is pressed.
- `shop-window/`: a complete project, the size of a real small one, valid without warnings:
  - `hardware.hw`: a Raspberry Pi 4 with the sign's relay (GPIO 27, active low), the window LED
    (GPIO 18, PWM) and a presence sensor (GPIO 22);
  - `shop.vars`: `max_visits` (constant), `visits` (persistent, exported) and `brightness` (a
    setting shown on the phone);
  - `scenes/fade.sec`: a component with an element parameter, used by `scenes/welcome.sec` on
    the LED while the relay is on; `scenes/close.sec` turns the relay off. Both are in the
    exclusive group `shop`, so they never run at once;
  - `presence.evt` + `welcome.auto`: a visitor starts *Welcome* and counts, while
    `visits < max_visits`;
  - `schedule/evening.sched` + `schedule/close.auto`: at 20:30 *Close* runs and the count
    resets; `schedule/schedule.vars` imports `visits` from the root, which exports it.

  Four things in it are previews of later phases and do nothing yet: the `if` condition of
  `welcome.auto` (the expression language, phase 4), the `times` parameter of *Fade* and the
  `brightness` setting (clip parameters and the phone UI, phases 4 and 5), and the time window
  of `evening.sched` (conditions on schedules, phase 4). They show the shape; validation
  accepts them and checks their types.
- `invalid/<code>/`: one project per pin conflict, each giving exactly that code (see its README).

A project folder holds only project files: a README inside one would be reported as a file of
no project type.
