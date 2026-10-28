"""Reads one field from the hook's JSON input (stdin). Avoids depending on jq."""

import json
import sys

data = json.load(sys.stdin)
value: object = data
for key in sys.argv[1].split("."):
    value = value.get(key, "") if isinstance(value, dict) else ""
sys.stdout.write(str(value))
