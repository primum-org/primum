# Glossary

The words users see and the words in the code are the same concepts. English is used in code
and docs; the Spanish term is the one shown by the Spanish UI.

## Project and files

| Term | Spanish | Meaning |
|---|---|---|
| Project | Proyecto | The whole work: boards, elements, sequences, automations, events, schedules, variables. A folder of files. Saved or shared as a single `.primum` file |
| Folder | Carpeta | A group of files inside a project. Defines a scope for variables |
| Sequence (`.sec`) | Secuencia | Actions placed in time on tracks, one track per element. Can include other sequences as blocks |
| Component | Componente | A sequence with parameters, reused from other sequences |
| Parameter | Parámetro | An input of a component; exists only inside that use (instance) |
| Automation (`.auto`) | Automatización | When an event happens → if conditions hold → do something (start/stop a sequence, change a variable) |
| Event (`.evt`) | Evento | A named thing that happened in the outside world: a sensor, a button, a phone button, an external message. Sequences never emit events |
| Schedule (`.prog`) | Programación | Time events ("every day at 20:30") and time windows used as conditions ("Mon–Sat 10:00–20:30"). Runs as an automation underneath |
| Variables file (`.vars`) | Variables | Constants and variables of the folder it is in |
| Hardware file (`.hw`) | Hardware | Boards and elements of the project |
| Constant | Constante | A value fixed while the show runs; resolved at compile time |
| Variable | Variable | A value that changes while running (by automations or by the user); has a type, an initial value, limits and persistence |
| Scope | Ámbito | Where a name is visible: the folder it is defined in and the folders inside it |
| Export / Import | Exportar / Importar | Explicitly sharing a variable with another folder |
| Setting | Ajuste | A variable exposed in the phone UI (slider, switch) |

## Hardware

| Term | Spanish | Meaning |
|---|---|---|
| Board | Placa | A physical device: Raspberry Pi, ESP32, Arduino |
| Hub | Hub | A board running the full runtime that coordinates the others (Raspberry Pi) |
| Autonomous node | Nodo autónomo | A board that stores and runs its part of a project (ESP32) |
| Satellite | Satélite | A board without logic that obeys a hub (Arduino Uno) |
| Board profile | Perfil de placa | Data describing a board model: pins, functions, buses, resources |
| Element | Elemento | Something the user connects and controls: LED strip, relay, motor, sensor, speaker |
| Capability | Capacidad | What an element can do in general terms: switch, level, color, position, measure |
| Action | Acción | What an element does in a sequence: *Fade*, *Wave*, *Play* |
| Driver | Driver | Code that implements an element type on a platform |
| HAL | HAL | Hardware abstraction layer; has a real and a simulated implementation |
| Transport | Transporte | How messages travel between boards: Wi-Fi, USB serial, RS-485, LoRa |

## Running

| Term | Spanish | Meaning |
|---|---|---|
| Deploy | Desplegar | Send a validated project to the boards |
| Deployment package | Paquete de despliegue | The flat, validated, hashed result of compiling a project for one board |
| Priority | Prioridad | Which sequence controls an element when several want it |
| Layer | Capa | A priority level; when a higher layer ends, the element returns to what the layer below says |
| Exclusive group | Grupo exclusivo | Sequences that cancel each other: starting one stops the others |
| Exclusive element | Elemento exclusivo | An element (motor, servo) that one sequence owns while it runs |
| Safe state | Estado seguro | The state every output goes to on start, stop, crash or panic |
| Panic | Pánico | Immediately put everything in its safe state |
| Test mode | Modo prueba | Manual commands for checking wiring; they expire on their own |
| Trace | Traza | The log of what happened and why ("the sensor fired → automation X → sequence Y") |

## Products

| Term | Meaning |
|---|---|
| Primum | The project and the platform. From *Primum Mobile*, the outermost sphere of medieval astronomy that set all the others in motion |
| Primum OS | The Raspberry Pi image with Primum preinstalled |
| Primum Studio | The future desktop app |
