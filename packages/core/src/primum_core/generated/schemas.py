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
    "if": {
      "description": "Condition, in the expression language of phase 4: stored, not interpreted yet.",
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
  "description": "What a board model offers: its header pins, buses, PWM channels and reserved pins, and how its GPIOs map to the lines of its GPIO chip. One file per model in boards/.",
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
    "reserved"
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
    "capabilities",
    "platforms",
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
    "capabilities": {
      "description": "What the element can do in general terms.",
      "type": "array",
      "items": {
        "enum": [
          "switch",
          "level",
          "color",
          "position",
          "measure"
        ]
      },
      "minItems": 1,
      "uniqueItems": true
    },
    "platforms": {
      "description": "The runtimes that implement it.",
      "type": "array",
      "items": {
        "enum": [
          "linux",
          "esp32",
          "rp2040",
          "avr"
        ]
      },
      "minItems": 1,
      "uniqueItems": true
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
    }
  },
  "$defs": {
    "driverAction": {
      "type": "object",
      "additionalProperties": false,
      "description": "An action of the element, with the parameters a clip gives it.",
      "required": [
        "name",
        "parameters"
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
        }
      }
    },
    "driverParameter": {
      "type": "object",
      "additionalProperties": false,
      "description": "A parameter of an action or an option of an element's configuration: its type, its limits and the value it takes when not given. Without a default it must be given.",
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
          "description": "The lowest value allowed (numbers only, with max).",
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
        }
      }
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
    "description": { "$ref": "common.schema.json#/$defs/description" }
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
  "description": "A .sched file: times of day that start automations, and windows of time that automations use as conditions.",
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
      "description": "Sequences in the same exclusive group cancel each other: starting one stops the others, so they never run at once.",
      "type": "string",
      "pattern": "^[A-Za-z_][A-Za-z0-9_]*$",
      "maxLength": 40
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
      "description": "An action of the element from atMs: held for durationMs, or, with durationMs 0, an instant command that stands, under the clips with a length, until the next instant command of the element or the end of the sequence (decision 0016).",
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
            "$ref": "common.schema.json#/$defs/namedValue"
          }
        }
      }
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
      "description": "The value of one parameter of the included sequence: an element, or a value.",
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
