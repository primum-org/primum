"""GENERATED from schemas/ by tools/gen_schemas.py: do not edit."""

import json
from collections.abc import Mapping
from typing import Final

# Each schema by file name, which is also its $id.
SCHEMAS: Final[Mapping[str, Mapping[str, object]]] = {
    "automation.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "automation.schema.json",
  "title": "Automation",
  "description": "An .auto file: when an event or a schedule fires, if the condition holds, do the actions.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "kind",
    "schemaVersion",
    "name",
    "when",
    "do"
  ],
  "properties": {
    "id": {
      "$ref": "common.schema.json#/$defs/id"
    },
    "kind": {
      "const": "automation"
    },
    "schemaVersion": {
      "const": 1
    },
    "name": {
      "$ref": "common.schema.json#/$defs/name"
    },
    "enabled": {
      "type": "boolean",
      "default": true
    },
    "when": {
      "description": "Events (.evt) and schedules (.sched) that start it.",
      "type": "array",
      "items": {
        "$ref": "common.schema.json#/$defs/reference"
      },
      "minItems": 1,
      "uniqueItems": true
    },
    "during": {
      "description": "Schedules whose windows must be open for it to act: all of them. Without it, the time does not matter.",
      "type": "array",
      "items": {
        "$ref": "common.schema.json#/$defs/reference"
      },
      "minItems": 1,
      "uniqueItems": true
    },
    "if": {
      "description": "The condition that must hold, in the expression language (docs/specs/expressions.md): visits < limit and not paused. Without it, the actions always run.",
      "type": "string",
      "maxLength": 500
    },
    "do": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/automationAction"
      },
      "minItems": 1
    }
  },
  "$defs": {
    "automationAction": {
      "type": "object",
      "additionalProperties": false,
      "description": "Start or stop a sequence, or set or increment a variable.",
      "required": [
        "action"
      ],
      "properties": {
        "action": {
          "enum": [
            "start_sequence",
            "stop_sequence",
            "set_variable",
            "increment_variable"
          ]
        },
        "sequence": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "variable": {
          "$ref": "common.schema.json#/$defs/variableName"
        },
        "value": {
          "$ref": "common.schema.json#/$defs/value"
        }
      }
    }
  }
}
"""
    ),
    "board-profile.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "board-profile.schema.json",
  "title": "Board profile",
  "description": "What a board model offers: its header pins, buses, PWM channels and reserved pins, how its GPIOs map to the lines of its GPIO chip, and the limits it puts on the options of its elements. One file per model in boards/.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "kind",
    "schemaVersion",
    "model",
    "name",
    "gpioChip",
    "pwmChip",
    "pins",
    "buses",
    "pwmChannels",
    "reserved",
    "limits"
  ],
  "properties": {
    "id": {
      "$ref": "common.schema.json#/$defs/id"
    },
    "kind": {
      "const": "board_profile"
    },
    "schemaVersion": {
      "const": 1
    },
    "model": {
      "description": "Short, stable identifier of the model, used by project files and the runtime (rpi4b). It is the profile's file name.",
      "type": "string",
      "pattern": "^[a-z0-9][a-z0-9-]*$",
      "maxLength": 40
    },
    "name": {
      "$ref": "common.schema.json#/$defs/name"
    },
    "gpioChip": {
      "$ref": "#/$defs/gpioChip"
    },
    "pwmChip": {
      "$ref": "#/$defs/pwmChip"
    },
    "pins": {
      "description": "Every pin of the header, by physical number.",
      "type": "array",
      "items": {
        "$ref": "#/$defs/headerPin"
      },
      "minItems": 1
    },
    "buses": {
      "description": "Buses on the header and the GPIOs each signal uses when it is enabled.",
      "type": "array",
      "items": {
        "$ref": "#/$defs/bus"
      }
    },
    "pwmChannels": {
      "description": "Hardware PWM channels: the GPIOs listed for a channel share it, so only one of them can use it at a time.",
      "type": "array",
      "items": {
        "$ref": "#/$defs/pwmChannel"
      }
    },
    "reserved": {
      "description": "GPIOs Primum never assigns to an element.",
      "type": "array",
      "items": {
        "$ref": "#/$defs/reservedGpio"
      }
    },
    "limits": {
      "description": "The limits this board puts on options of the elements wired to it, each taken from the documentation it cites.",
      "type": "array",
      "items": {
        "$ref": "#/$defs/optionLimit"
      }
    }
  },
  "$defs": {
    "gpioChip": {
      "description": "The GPIO chip that drives the header, found by its label: the device number (/dev/gpiochipN) can change with the kernel.",
      "type": "object",
      "additionalProperties": false,
      "required": [
        "label"
      ],
      "properties": {
        "label": {
          "type": "string",
          "minLength": 1,
          "maxLength": 80
        }
      }
    },
    "headerPin": {
      "description": "A pin of the header. A gpio pin has its GPIO number, its line on the GPIO chip and its pull at power on; other pins have none of them.",
      "type": "object",
      "additionalProperties": false,
      "required": [
        "physical",
        "kind"
      ],
      "properties": {
        "physical": {
          "type": "integer",
          "minimum": 1
        },
        "kind": {
          "enum": [
            "gpio",
            "power_3v3",
            "power_5v",
            "ground"
          ]
        },
        "gpio": {
          "type": "integer",
          "minimum": 0
        },
        "line": {
          "type": "integer",
          "minimum": 0
        },
        "defaultPull": {
          "enum": [
            "up",
            "down"
          ]
        }
      }
    },
    "bus": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "id",
        "kind",
        "signals"
      ],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9]*$"
        },
        "kind": {
          "enum": [
            "i2c",
            "spi",
            "uart"
          ]
        },
        "signals": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/busSignal"
          },
          "minItems": 1
        }
      }
    },
    "busSignal": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "name",
        "gpio"
      ],
      "properties": {
        "name": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9]*$"
        },
        "gpio": {
          "type": "integer",
          "minimum": 0
        }
      }
    },
    "pwmChannel": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "id",
        "channel",
        "gpios"
      ],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9]*$"
        },
        "channel": {
          "description": "The channel's index on the PWM controller.",
          "type": "integer",
          "minimum": 0
        },
        "gpios": {
          "type": "array",
          "items": {
            "type": "integer",
            "minimum": 0
          },
          "minItems": 1,
          "uniqueItems": true
        }
      }
    },
    "reservedGpio": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "gpio",
        "reason"
      ],
      "properties": {
        "gpio": {
          "type": "integer",
          "minimum": 0
        },
        "reason": {
          "enum": [
            "hat_eeprom"
          ]
        }
      }
    },
    "pwmChip": {
      "description": "The hardware PWM controller, found by its device name in the kernel (the directory /sys/class/pwm/pwmchipN/device points at): the chip number can change with the kernel.",
      "type": "object",
      "additionalProperties": false,
      "required": [
        "device"
      ],
      "properties": {
        "device": {
          "type": "string",
          "minLength": 1,
          "maxLength": 80
        }
      }
    },
    "optionLimit": {
      "description": "The values this board takes for one option of the elements of one type (the frequency of a PWM output), and where that is documented.",
      "type": "object",
      "additionalProperties": false,
      "required": [
        "elementType",
        "option",
        "min",
        "max",
        "sources"
      ],
      "properties": {
        "elementType": {
          "description": "The type of the elements it applies to, as .hw files write it (pwm_output).",
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$",
          "maxLength": 40
        },
        "option": {
          "$ref": "common.schema.json#/$defs/parameterName"
        },
        "min": {
          "description": "The lowest value the board takes.",
          "type": "number"
        },
        "max": {
          "description": "The highest value the board takes.",
          "type": "number"
        },
        "sources": {
          "description": "Where the limit comes from: the manufacturer's documentation or the source of the system Primum ships, as links.",
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^https://",
            "maxLength": 300
          },
          "minItems": 1,
          "uniqueItems": true
        },
        "note": {
          "description": "How the limit follows from the sources, for whoever maintains the profile.",
          "type": "string",
          "minLength": 1,
          "maxLength": 600
        }
      }
    }
  }
}
"""
    ),
    "common.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "common.schema.json",
  "title": "Common definitions",
  "description": "Definitions shared by every Primum format.",
  "$defs": {
    "id": {
      "description": "A UUID that identifies an entity for good. Files reference each other by id, never by path.",
      "type": "string",
      "format": "uuid"
    },
    "name": {
      "description": "A name a person reads: shown in the UI, never used as a reference.",
      "type": "string",
      "minLength": 1,
      "maxLength": 80
    },
    "description": {
      "description": "Free text that explains what something is for.",
      "type": "string",
      "maxLength": 2000
    },
    "reference": {
      "description": "The id of another file of the project, or of something defined in one (an element, a parameter). Never a path.",
      "type": "string",
      "format": "uuid"
    },
    "variableName": {
      "description": "The name of a constant or a variable, as conditions will write it: a letter or _ first, then letters, digits or _.",
      "type": "string",
      "pattern": "^[A-Za-z_][A-Za-z0-9_]*$",
      "maxLength": 40
    },
    "valueType": {
      "description": "The type of a value: number (with decimals), integer, boolean (true or false) or text.",
      "enum": [
        "number",
        "integer",
        "boolean",
        "text"
      ]
    },
    "value": {
      "description": "A number, a boolean or a text.",
      "type": [
        "number",
        "boolean",
        "string"
      ]
    },
    "parameterName": {
      "description": "The name of a parameter of an action or of an option of an element's configuration, as its driver declares it (level, frequencyHz).",
      "type": "string",
      "pattern": "^[a-z][A-Za-z0-9]*$",
      "maxLength": 40
    },
    "namedValue": {
      "type": "object",
      "additionalProperties": false,
      "description": "A value given by name: an argument of a clip's action, an option of an element's configuration.",
      "required": [
        "name",
        "value"
      ],
      "properties": {
        "name": {
          "$ref": "#/$defs/parameterName"
        },
        "value": {
          "$ref": "#/$defs/value"
        }
      }
    },
    "durationMs": {
      "description": "A length of time in milliseconds.",
      "type": "integer",
      "minimum": 0
    },
    "weekday": {
      "enum": [
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
        "sat",
        "sun"
      ]
    },
    "timeOfDay": {
      "description": "A time of day, 24-hour HH:MM, local time.",
      "type": "string",
      "pattern": "^([01][0-9]|2[0-3]):[0-5][0-9]$"
    }
  }
}
"""
    ),
    "driver.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "driver.schema.json",
  "title": "Driver",
  "description": "What a driver offers, as data: the element type it serves, what a clip may ask of it and how the element is set up. One file per element type in drivers/. Its implementation lives in the runtimes.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "kind",
    "schemaVersion",
    "elementType",
    "config",
    "actions"
  ],
  "properties": {
    "id": {
      "$ref": "common.schema.json#/$defs/id"
    },
    "kind": {
      "const": "driver"
    },
    "schemaVersion": {
      "const": 1
    },
    "elementType": {
      "description": "The type of the elements it serves, as .hw files write it (pwm_output); the file is named after it.",
      "type": "string",
      "pattern": "^[a-z][a-z0-9_]*$",
      "maxLength": 40
    },
    "conflictPolicy": {
      "description": "What happens when two sequences on one priority command the element: the latest command wins (lights, relays), or one sequence owns it while it runs (motors, servos). Needed by a driver with actions.",
      "enum": [
        "latest_wins",
        "exclusive"
      ]
    },
    "safeState": {
      "description": "The action the element rests in: when nothing commands it, on stop, on panic. One of its actions that needs no arguments. Needed by a driver with actions.",
      "type": "string",
      "pattern": "^[a-z][a-z0-9_]*$",
      "maxLength": 40
    },
    "config": {
      "description": "The options an element of this type takes in a .hw file, beyond its wiring.",
      "type": "array",
      "items": {
        "$ref": "#/$defs/driverParameter"
      }
    },
    "actions": {
      "description": "What a clip may ask of the element. None for an element that only reads.",
      "type": "array",
      "items": {
        "$ref": "#/$defs/driverAction"
      }
    },
    "triggers": {
      "description": "What an event may listen to on the element: it turning on (pressed, detected) or off. Absent for an element that tells nothing.",
      "type": "array",
      "items": {
        "enum": [
          "on",
          "off"
        ]
      },
      "minItems": 1,
      "uniqueItems": true
    }
  },
  "$defs": {
    "driverAction": {
      "type": "object",
      "additionalProperties": false,
      "description": "An action of the element, with the parameters a clip gives it and the state it leaves the element in.",
      "required": [
        "name",
        "parameters",
        "endState"
      ],
      "properties": {
        "name": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$",
          "maxLength": 40
        },
        "parameters": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/driverParameter"
          }
        },
        "endState": {
          "description": "The state the action leaves the element in: what an instant command sets, and where a clip with a length ends.",
          "$ref": "#/$defs/actionState"
        },
        "startState": {
          "description": "The state a clip with a length starts from, for an action that moves the element from one state to another over its clip (a fade). Without it the action holds its end state for the whole clip.",
          "$ref": "#/$defs/actionState"
        }
      }
    },
    "driverParameter": {
      "type": "object",
      "additionalProperties": false,
      "description": "A parameter of an action or an option of an element's configuration: its type, its limits and the value it takes when not given. Without a default it must be given, unless it is optional.",
      "required": [
        "name",
        "type"
      ],
      "properties": {
        "name": {
          "$ref": "common.schema.json#/$defs/parameterName"
        },
        "type": {
          "$ref": "common.schema.json#/$defs/valueType"
        },
        "min": {
          "description": "The lowest value allowed on every board (numbers only, with max). What only a board limits is in its profile.",
          "type": "number"
        },
        "max": {
          "description": "The highest value allowed (numbers only, with min).",
          "type": "number"
        },
        "choices": {
          "description": "The values allowed (texts only).",
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 40
          },
          "minItems": 1,
          "uniqueItems": true
        },
        "default": {
          "$ref": "common.schema.json#/$defs/value"
        },
        "optional": {
          "description": "May be left out with nothing in its place: the driver then decides (a fade without a from starts where the element is). Never with a default.",
          "type": "boolean",
          "default": false
        }
      }
    },
    "actionState": {
      "description": "A state of the element as a level, from 0 (off) to 100 (fully on): the level itself, or the name of the parameter of the action that gives it.",
      "type": [
        "number",
        "string"
      ],
      "minimum": 0,
      "maximum": 100,
      "pattern": "^[a-z][A-Za-z0-9]*$",
      "maxLength": 40
    }
  }
}
"""
    ),
    "event.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "event.schema.json",
  "title": "Event",
  "description": "An .evt file: something that happens outside and can start automations. The source says where it comes from: an input element, a button of the phone UI, or a request to the local API.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "kind",
    "schemaVersion",
    "name",
    "source"
  ],
  "properties": {
    "id": {
      "$ref": "common.schema.json#/$defs/id"
    },
    "kind": {
      "const": "event"
    },
    "schemaVersion": {
      "const": 1
    },
    "name": {
      "$ref": "common.schema.json#/$defs/name"
    },
    "source": {
      "enum": [
        "element",
        "ui",
        "api"
      ]
    },
    "element": {
      "description": "Source element: the input element (a .hw element).",
      "$ref": "common.schema.json#/$defs/reference"
    },
    "trigger": {
      "description": "Source element: when it turns on (pressed, detected) or off.",
      "enum": [
        "on",
        "off"
      ]
    }
  }
}
"""
    ),
    "hardware.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "hardware.schema.json",
  "title": "Hardware",
  "description": "A .hw file: boards and the elements wired to them. Which resources an element uses depends on its type: a pin for GPIO elements, a bus and an address for I2C devices.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "kind",
    "schemaVersion",
    "boards",
    "elements"
  ],
  "properties": {
    "id": {
      "$ref": "common.schema.json#/$defs/id"
    },
    "kind": {
      "const": "hardware"
    },
    "schemaVersion": {
      "const": 1
    },
    "name": {
      "$ref": "common.schema.json#/$defs/name"
    },
    "boards": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/hardwareBoard"
      }
    },
    "elements": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/element"
      }
    }
  },
  "$defs": {
    "hardwareBoard": {
      "type": "object",
      "additionalProperties": false,
      "description": "A board of the project, of a model that has a board profile (boards/).",
      "required": [
        "id",
        "name",
        "model"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/name"
        },
        "model": {
          "type": "string",
          "pattern": "^[a-z0-9][a-z0-9-]*$",
          "maxLength": 40
        }
      }
    },
    "element": {
      "type": "object",
      "additionalProperties": false,
      "description": "Something wired to a board: an LED, a relay, a button, a sensor.",
      "required": [
        "id",
        "name",
        "board",
        "type"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/name"
        },
        "board": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "type": {
          "enum": [
            "digital_output",
            "digital_input",
            "pwm_output",
            "i2c_device"
          ]
        },
        "pin": {
          "description": "GPIO number (BCM) for digital and PWM elements.",
          "type": "integer",
          "minimum": 0
        },
        "activeLow": {
          "description": "Digital elements: on means the line is low.",
          "type": "boolean",
          "default": false
        },
        "bus": {
          "description": "I2C devices: the bus of the board profile (i2c1).",
          "type": "string",
          "pattern": "^[a-z][a-z0-9]*$"
        },
        "address": {
          "description": "I2C devices: the 7-bit address.",
          "type": "integer",
          "minimum": 8,
          "maximum": 119
        },
        "config": {
          "description": "The options of the element's driver, by name (frequencyHz, pull, debounceMs); the ones not given take the driver's default.",
          "type": "array",
          "items": {
            "$ref": "common.schema.json#/$defs/namedValue"
          }
        }
      }
    }
  }
}
"""
    ),
    "package.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "package.schema.json",
  "title": "Package",
  "description": "A deployment package: a project compiled for one board, flat, built from a project that passed every check (decision 0024). Whoever reads one checks it again: its shape, its hash and that it holds together. It is all the runtime sees: no folders, no scopes, no components, no constants. Built by primum-core, never written by hand.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "kind",
    "schemaVersion",
    "hash",
    "project",
    "board",
    "elements",
    "variables",
    "sequences",
    "events",
    "schedules",
    "automations"
  ],
  "properties": {
    "kind": {
      "const": "package"
    },
    "schemaVersion": {
      "const": 1
    },
    "hash": {
      "description": "sha256 of the package without this field, in its canonical form: keys sorted, no spaces, UTF-8.",
      "type": "string",
      "pattern": "^sha256:[0-9a-f]{64}$"
    },
    "project": {
      "$ref": "#/$defs/packageProject"
    },
    "timeZone": {
      "description": "The time zone of the project's schedules, by its IANA name. Present when it has schedules.",
      "type": "string",
      "pattern": "^[A-Za-z][A-Za-z0-9_+-]*(/[A-Za-z0-9_+-]+)*$",
      "maxLength": 64
    },
    "board": {
      "$ref": "#/$defs/packageBoard"
    },
    "elements": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/packageElement"
      }
    },
    "variables": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/packageVariable"
      }
    },
    "sequences": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/packageSequence"
      }
    },
    "events": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/packageEvent"
      }
    },
    "schedules": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/packageSchedule"
      }
    },
    "automations": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/packageAutomation"
      }
    }
  },
  "$defs": {
    "packageProject": {
      "type": "object",
      "additionalProperties": false,
      "description": "The project the package was compiled from.",
      "required": [
        "id",
        "name"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/name"
        }
      }
    },
    "packageBoard": {
      "type": "object",
      "additionalProperties": false,
      "description": "The board the package is for.",
      "required": [
        "id",
        "name",
        "model"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/name"
        },
        "model": {
          "type": "string",
          "pattern": "^[a-z0-9][a-z0-9-]*$",
          "maxLength": 40
        }
      }
    },
    "packageElement": {
      "type": "object",
      "additionalProperties": false,
      "description": "An element of the board, with every option of its driver: the ones its .hw file gives and the defaults of the others.",
      "required": [
        "id",
        "name",
        "type",
        "config"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/name"
        },
        "type": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$",
          "maxLength": 40
        },
        "pin": {
          "type": "integer",
          "minimum": 0
        },
        "activeLow": {
          "type": "boolean",
          "default": false
        },
        "bus": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9]*$"
        },
        "address": {
          "type": "integer",
          "minimum": 8,
          "maximum": 119
        },
        "config": {
          "type": "array",
          "items": {
            "$ref": "common.schema.json#/$defs/namedValue"
          }
        }
      }
    },
    "packageVariable": {
      "type": "object",
      "additionalProperties": false,
      "description": "A variable: a value that changes while running.",
      "required": [
        "id",
        "name",
        "type",
        "initial",
        "persistent",
        "setting"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/variableName"
        },
        "type": {
          "$ref": "common.schema.json#/$defs/valueType"
        },
        "initial": {
          "$ref": "common.schema.json#/$defs/value"
        },
        "min": {
          "type": "number"
        },
        "max": {
          "type": "number"
        },
        "persistent": {
          "type": "boolean"
        },
        "setting": {
          "type": "boolean"
        }
      }
    },
    "packageSequence": {
      "type": "object",
      "additionalProperties": false,
      "description": "A sequence that can be started: its components expanded, its clips turned into commands by the rule of decision 0017.",
      "required": [
        "id",
        "name",
        "priority",
        "whenDone",
        "whenStartedAgain",
        "durationMs",
        "commands"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/name"
        },
        "priority": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100
        },
        "exclusiveGroup": {
          "type": "string",
          "pattern": "^[A-Za-z_][A-Za-z0-9_]*$",
          "maxLength": 40
        },
        "whenDone": {
          "enum": [
            "end",
            "hold"
          ]
        },
        "whenStartedAgain": {
          "enum": [
            "restart",
            "ignore"
          ]
        },
        "durationMs": {
          "description": "When its last clip ends.",
          "$ref": "common.schema.json#/$defs/durationMs"
        },
        "commands": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/command"
          }
        }
      }
    },
    "command": {
      "type": "object",
      "additionalProperties": false,
      "description": "What an element is asked from atMs, in the time of its sequence. In force until untilMs; without it, until the sequence is stopped (what a sequence that holds keeps). The action lasts durationMs, 0 for an instant command; after that the element stays in the state the action ends in.",
      "required": [
        "clip",
        "element",
        "atMs",
        "durationMs",
        "action",
        "arguments"
      ],
      "properties": {
        "clip": {
          "description": "The clip of the project it comes from, for the trace.",
          "$ref": "common.schema.json#/$defs/id"
        },
        "element": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "atMs": {
          "$ref": "common.schema.json#/$defs/durationMs"
        },
        "durationMs": {
          "$ref": "common.schema.json#/$defs/durationMs"
        },
        "untilMs": {
          "$ref": "common.schema.json#/$defs/durationMs"
        },
        "action": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$",
          "maxLength": 40
        },
        "arguments": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/commandArgument"
          }
        }
      }
    },
    "commandArgument": {
      "type": "object",
      "additionalProperties": false,
      "description": "The value of one parameter of the action: the value itself, or the variable to read it from while running (when exactly is the engine's). One of the two. Every parameter is here, the driver's default included, except an optional one that was left out.",
      "required": [
        "name"
      ],
      "properties": {
        "name": {
          "$ref": "common.schema.json#/$defs/parameterName"
        },
        "value": {
          "$ref": "common.schema.json#/$defs/value"
        },
        "variable": {
          "$ref": "common.schema.json#/$defs/reference"
        }
      }
    },
    "packageEvent": {
      "type": "object",
      "additionalProperties": false,
      "description": "Something that happens outside and starts automations.",
      "required": [
        "id",
        "name",
        "source"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/name"
        },
        "source": {
          "enum": [
            "element",
            "ui",
            "api"
          ]
        },
        "element": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "trigger": {
          "enum": [
            "on",
            "off"
          ]
        }
      }
    },
    "packageSchedule": {
      "type": "object",
      "additionalProperties": false,
      "description": "Times of day and windows of time that start automations.",
      "required": [
        "id",
        "name",
        "times",
        "windows"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/name"
        },
        "times": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/packageTime"
          }
        },
        "windows": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/packageWindow"
          }
        }
      }
    },
    "packageTime": {
      "type": "object",
      "additionalProperties": false,
      "description": "Every listed day at a time.",
      "required": [
        "days",
        "at"
      ],
      "properties": {
        "days": {
          "type": "array",
          "items": {
            "$ref": "common.schema.json#/$defs/weekday"
          },
          "minItems": 1,
          "uniqueItems": true
        },
        "at": {
          "$ref": "common.schema.json#/$defs/timeOfDay"
        }
      }
    },
    "packageWindow": {
      "type": "object",
      "additionalProperties": false,
      "description": "Every listed day from one time to another.",
      "required": [
        "days",
        "from",
        "to"
      ],
      "properties": {
        "days": {
          "type": "array",
          "items": {
            "$ref": "common.schema.json#/$defs/weekday"
          },
          "minItems": 1,
          "uniqueItems": true
        },
        "from": {
          "$ref": "common.schema.json#/$defs/timeOfDay"
        },
        "to": {
          "$ref": "common.schema.json#/$defs/timeOfDay"
        }
      }
    },
    "packageAutomation": {
      "type": "object",
      "additionalProperties": false,
      "description": "When an event or a schedule fires, if the condition holds, do the actions.",
      "required": [
        "id",
        "name",
        "enabled",
        "when",
        "do"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/name"
        },
        "enabled": {
          "type": "boolean"
        },
        "when": {
          "type": "array",
          "items": {
            "$ref": "common.schema.json#/$defs/reference"
          },
          "minItems": 1,
          "uniqueItems": true
        },
        "during": {
          "description": "Schedules whose windows must all be open for it to act, each by its id.",
          "type": "array",
          "items": {
            "$ref": "common.schema.json#/$defs/reference"
          },
          "minItems": 1,
          "uniqueItems": true
        },
        "if": {
          "description": "The condition, compiled (docs/specs/expressions.md): its steps in postfix order, for a stack. Constants are already values; variables go by id.",
          "type": "array",
          "items": {
            "$ref": "#/$defs/conditionStep"
          },
          "minItems": 1,
          "maxItems": 500
        },
        "do": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/packageAction"
          },
          "minItems": 1
        }
      }
    },
    "conditionStep": {
      "type": "object",
      "additionalProperties": false,
      "description": "One step of a condition: push a value, push the value a variable has, or apply an operator to what is on the stack. Exactly one of the three.",
      "properties": {
        "value": {
          "$ref": "common.schema.json#/$defs/value"
        },
        "variable": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "op": {
          "description": "neg is the minus of one operand (-x).",
          "enum": [
            "or",
            "and",
            "not",
            "==",
            "!=",
            "<",
            "<=",
            ">",
            ">=",
            "+",
            "-",
            "*",
            "/",
            "%",
            "neg"
          ]
        }
      }
    },
    "packageAction": {
      "type": "object",
      "additionalProperties": false,
      "description": "Start or stop a sequence, or set or increment a variable, each by its id.",
      "required": [
        "action"
      ],
      "properties": {
        "action": {
          "enum": [
            "start_sequence",
            "stop_sequence",
            "set_variable",
            "increment_variable"
          ]
        },
        "sequence": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "variable": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "value": {
          "$ref": "common.schema.json#/$defs/value"
        }
      }
    }
  }
}
"""
    ),
    "project.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "project.schema.json",
  "title": "Project",
  "description": "The manifest of a project: project.json, at the root of the project's folder.",
  "type": "object",
  "additionalProperties": false,
  "required": ["id", "kind", "schemaVersion", "name"],
  "properties": {
    "id": { "$ref": "common.schema.json#/$defs/id" },
    "kind": { "const": "project" },
    "schemaVersion": { "const": 1 },
    "name": { "$ref": "common.schema.json#/$defs/name" },
    "description": { "$ref": "common.schema.json#/$defs/description" },
    "timeZone": {
      "description": "The time zone the times of its schedules are in, by its IANA name (Europe/Madrid). Needed by a project with schedules.",
      "type": "string",
      "pattern": "^[A-Za-z][A-Za-z0-9_+-]*(/[A-Za-z0-9_+-]+)*$",
      "maxLength": 64
    }
  }
}
"""
    ),
    "schedule.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "schedule.schema.json",
  "title": "Schedule",
  "description": "A .sched file: times of day and windows of time that start automations. A time fires at its instant, and is lost if the board was off then; a window fires when it opens, or when the engine starts inside it (decision 0023). Windows are also conditions of automations.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "kind",
    "schemaVersion",
    "name"
  ],
  "properties": {
    "id": {
      "$ref": "common.schema.json#/$defs/id"
    },
    "kind": {
      "const": "schedule"
    },
    "schemaVersion": {
      "const": 1
    },
    "name": {
      "$ref": "common.schema.json#/$defs/name"
    },
    "times": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/scheduleTime"
      }
    },
    "windows": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/scheduleWindow"
      }
    }
  },
  "$defs": {
    "scheduleTime": {
      "type": "object",
      "additionalProperties": false,
      "description": "Every listed day at a time.",
      "required": [
        "days",
        "at"
      ],
      "properties": {
        "days": {
          "type": "array",
          "items": {
            "$ref": "common.schema.json#/$defs/weekday"
          },
          "minItems": 1,
          "uniqueItems": true
        },
        "at": {
          "$ref": "common.schema.json#/$defs/timeOfDay"
        }
      }
    },
    "scheduleWindow": {
      "type": "object",
      "additionalProperties": false,
      "description": "Every listed day from one time to another.",
      "required": [
        "days",
        "from",
        "to"
      ],
      "properties": {
        "days": {
          "type": "array",
          "items": {
            "$ref": "common.schema.json#/$defs/weekday"
          },
          "minItems": 1,
          "uniqueItems": true
        },
        "from": {
          "$ref": "common.schema.json#/$defs/timeOfDay"
        },
        "to": {
          "$ref": "common.schema.json#/$defs/timeOfDay"
        }
      }
    }
  }
}
"""
    ),
    "sequence.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "sequence.schema.json",
  "title": "Sequence",
  "description": "A .sec file: actions placed in time on tracks, one track per element, and blocks that include other sequences. With parameters it is a component, reused by other sequences. Sequences never emit events.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "kind",
    "schemaVersion",
    "name",
    "tracks"
  ],
  "properties": {
    "id": {
      "$ref": "common.schema.json#/$defs/id"
    },
    "kind": {
      "const": "sequence"
    },
    "schemaVersion": {
      "const": 1
    },
    "name": {
      "$ref": "common.schema.json#/$defs/name"
    },
    "description": {
      "$ref": "common.schema.json#/$defs/description"
    },
    "priority": {
      "description": "The layer the sequence commands its elements on (decision 0006): a higher priority overrides a lower one while it runs; within one priority the latest command wins.",
      "type": "integer",
      "minimum": 0,
      "maximum": 100,
      "default": 0
    },
    "exclusiveGroup": {
      "description": "Sequences in the same exclusive group cancel each other: starting one stops the others, so they never run at once (decision 0023).",
      "type": "string",
      "pattern": "^[A-Za-z_][A-Za-z0-9_]*$",
      "maxLength": 40
    },
    "whenDone": {
      "description": "What the sequence does when its last clip ends: end, and its elements go back to what was under it; or hold as it is in that instant until it is stopped (decision 0017). Ignored when the sequence is included in another.",
      "enum": [
        "end",
        "hold"
      ],
      "default": "end"
    },
    "whenStartedAgain": {
      "description": "What starting the sequence does while it is already running (decision 0023): restart, it begins again and counts as started last; or ignore, the start does nothing.",
      "enum": [
        "restart",
        "ignore"
      ],
      "default": "restart"
    },
    "parameters": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/parameter"
      }
    },
    "tracks": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/track"
      }
    },
    "blocks": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/block"
      }
    }
  },
  "$defs": {
    "parameter": {
      "type": "object",
      "additionalProperties": false,
      "description": "An input of a component, given by each sequence that uses it.",
      "required": [
        "id",
        "name",
        "type"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/variableName"
        },
        "type": {
          "enum": [
            "element",
            "number",
            "integer",
            "boolean",
            "text"
          ]
        }
      }
    },
    "track": {
      "type": "object",
      "additionalProperties": false,
      "description": "The clips of one element: an element of a .hw file, or an element parameter of this sequence.",
      "required": [
        "element",
        "clips"
      ],
      "properties": {
        "element": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "clips": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/clip"
          }
        }
      }
    },
    "clip": {
      "type": "object",
      "additionalProperties": false,
      "description": "An action of the element from atMs: held for durationMs, or, with durationMs 0, an instant command, in force until the next instant command of the element in this sequence or the end of this sequence, of its block when it is included (decision 0017).",
      "required": [
        "id",
        "atMs",
        "durationMs",
        "action"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "atMs": {
          "$ref": "common.schema.json#/$defs/durationMs"
        },
        "durationMs": {
          "$ref": "common.schema.json#/$defs/durationMs"
        },
        "action": {
          "description": "What the element does: one of the actions of its driver (drivers/).",
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$"
        },
        "arguments": {
          "description": "The values of the action's parameters, by name.",
          "type": "array",
          "items": {
            "$ref": "#/$defs/clipArgument"
          }
        }
      }
    },
    "clipArgument": {
      "type": "object",
      "additionalProperties": false,
      "description": "The value of one parameter of the clip's action: written here, or taken from a name (valueOf). One of the two.",
      "required": [
        "name"
      ],
      "properties": {
        "name": {
          "$ref": "common.schema.json#/$defs/parameterName"
        },
        "value": {
          "$ref": "common.schema.json#/$defs/value"
        },
        "valueOf": {
          "$ref": "#/$defs/valueOf"
        }
      }
    },
    "valueOf": {
      "description": "A value taken from a name instead of written: a parameter of this sequence (not an element one), or a constant or a variable its folder sees. A constant and a parameter are put in place when the project is compiled; a variable is read while running (decision 0024).",
      "$ref": "common.schema.json#/$defs/variableName"
    },
    "block": {
      "type": "object",
      "additionalProperties": false,
      "description": "Another sequence, started at atMs.",
      "required": [
        "id",
        "sequence",
        "atMs"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "sequence": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "atMs": {
          "$ref": "common.schema.json#/$defs/durationMs"
        },
        "arguments": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/argument"
          }
        }
      }
    },
    "argument": {
      "type": "object",
      "additionalProperties": false,
      "description": "The value of one parameter of the included sequence: an element for an element parameter; for the others a value, written (value) or taken from a name (valueOf).",
      "required": [
        "parameter"
      ],
      "properties": {
        "parameter": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "element": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "value": {
          "$ref": "common.schema.json#/$defs/value"
        },
        "valueOf": {
          "$ref": "#/$defs/valueOf"
        }
      }
    }
  }
}
"""
    ),
    "variables.schema.json": json.loads(
        """
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "variables.schema.json",
  "title": "Variables",
  "description": "A .vars file: the constants and variables of the folder it is in, and the names that folder shares with others (decision 0005).",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "kind",
    "schemaVersion",
    "constants",
    "variables"
  ],
  "properties": {
    "id": {
      "$ref": "common.schema.json#/$defs/id"
    },
    "kind": {
      "const": "variables"
    },
    "schemaVersion": {
      "const": 1
    },
    "constants": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/constant"
      }
    },
    "variables": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/variable"
      }
    },
    "exports": {
      "description": "Names of this file that other folders may import.",
      "type": "array",
      "items": {
        "$ref": "common.schema.json#/$defs/variableName"
      },
      "uniqueItems": true
    },
    "imports": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/variableImport"
      }
    }
  },
  "$defs": {
    "constant": {
      "type": "object",
      "additionalProperties": false,
      "description": "A value fixed while the show runs, resolved when the project is compiled.",
      "required": [
        "id",
        "name",
        "type",
        "value"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/variableName"
        },
        "type": {
          "$ref": "common.schema.json#/$defs/valueType"
        },
        "value": {
          "$ref": "common.schema.json#/$defs/value"
        }
      }
    },
    "variable": {
      "type": "object",
      "additionalProperties": false,
      "description": "A value that changes while running, owned by one board.",
      "required": [
        "id",
        "name",
        "type",
        "initial"
      ],
      "properties": {
        "id": {
          "$ref": "common.schema.json#/$defs/id"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/variableName"
        },
        "type": {
          "$ref": "common.schema.json#/$defs/valueType"
        },
        "initial": {
          "$ref": "common.schema.json#/$defs/value"
        },
        "min": {
          "type": "number"
        },
        "max": {
          "type": "number"
        },
        "persistent": {
          "description": "Kept across restarts.",
          "type": "boolean",
          "default": false
        },
        "setting": {
          "description": "Shown in the phone UI as a setting.",
          "type": "boolean",
          "default": false
        }
      }
    },
    "variableImport": {
      "type": "object",
      "additionalProperties": false,
      "description": "A name exported by the .vars file of another folder.",
      "required": [
        "from",
        "name"
      ],
      "properties": {
        "from": {
          "$ref": "common.schema.json#/$defs/reference"
        },
        "name": {
          "$ref": "common.schema.json#/$defs/variableName"
        }
      }
    }
  }
}
"""
    ),
}
