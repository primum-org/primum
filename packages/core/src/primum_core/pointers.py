"""Where something is inside a file: as a JSON Pointer, and as a person reads it.

A place is a path of steps from the top of the document: object keys and array indices.
"""

type Step = str | int


def pointer(steps: tuple[Step, ...]) -> str:
    """A JSON Pointer (RFC 6901): ``/outputs/2/name``. The whole document is ``""``."""
    return "".join(f"/{str(step).replace('~', '~0').replace('/', '~1')}" for step in steps)


def field_name(steps: tuple[Step, ...]) -> str:
    """How a person reads a field: ``outputs[2].name``."""
    text = ""
    for step in steps:
        text += f"[{step}]" if isinstance(step, int) else f".{step}" if text else step
    return text
