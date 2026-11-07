# Example projects

Each folder is a Primum project (decision 0004): `project.json` and the files of the project.
Check one with `uv run primum validate examples/<name>`; a test keeps every example valid.

- `minimal/`: an LED on GPIO 17 that blinks when the phone's *Start* button is pressed.
- `invalid/<code>/`: one project per pin conflict, each giving exactly that code (see its README).
