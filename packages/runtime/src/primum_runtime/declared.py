"""What the runtime has claimed, declared where it survives the process (decision 0020).

A process killed at once (``SIGKILL``, a watchdog) cannot put its outputs in their safe state,
and the kernel keeps them as they were. So before claiming anything the runtime writes down
what it is about to claim, in its data directory; ``primum-safe`` reads it after the service
stops, whatever stopped it, and drives those outputs to their safe state. Inputs are not
declared: there is nothing to make safe in a line that is only read.

The file is written whole and then renamed into place, so it is never half written. It is
removed once the outputs it names are known to be safe and released.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from primum_core.json_values import as_bool, as_int, as_list, as_object, as_str
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.hal import Claim, OutputSpec, PwmSpec

FILE_NAME = "claimed.json"
VERSION = 1


@dataclass(frozen=True)
class Declaration:
    """The outputs a runtime claimed on a board, by its model."""

    board: str
    outputs: tuple[OutputSpec, ...] = ()
    pwms: tuple[PwmSpec, ...] = ()

    @classmethod
    def of(cls, board: str, claim: Claim) -> "Declaration":
        return cls(board, tuple(claim.outputs), tuple(claim.pwms))

    def claim(self) -> Claim:
        return Claim(outputs=self.outputs, pwms=self.pwms)


def write(directory: Path, declaration: Declaration) -> None:
    """Declare ``declaration`` in ``directory``, replacing what was declared before.

    Fails with ``safe.declaration_unwritable`` (``path``, ``detail``): a runtime that cannot
    declare its outputs must not claim them.
    """
    path = directory / FILE_NAME
    document = {
        "version": VERSION,
        "board": declaration.board,
        "outputs": [
            {"pin": spec.pin, "activeLow": spec.active_low} for spec in declaration.outputs
        ],
        "pwms": [{"pin": spec.pin, "frequencyHz": spec.frequency_hz} for spec in declaration.pwms],
    }
    temporary = path.with_suffix(".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(document, file)
            file.flush()
            os.fsync(file.fileno())  # on the card before the outputs it names can go on
        temporary.replace(path)
    except OSError as error:
        params = {"path": str(path), "detail": error.strerror or str(error)}
        raise PrimumError(ErrorCode.SAFE_DECLARATION_UNWRITABLE, params) from error


def read(directory: Path) -> Declaration | None:
    """What is declared in ``directory``; ``None`` when nothing is.

    Fails with ``safe.declaration_invalid`` (``path``, ``detail``) for a file that cannot be
    read or does not say what it should: nothing is guessed from it.
    """
    path = directory / FILE_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        raise _invalid(path, error.strerror or str(error)) from error
    try:
        return _declaration(json.loads(text))
    except (ValueError, KeyError, TypeError) as error:
        raise _invalid(path, str(error)) from error


def remove(directory: Path) -> None:
    """Forget what was declared: its outputs are safe and released. Nothing declared is fine."""
    (directory / FILE_NAME).unlink(missing_ok=True)


def _declaration(document: object) -> Declaration:
    fields = as_object(document)
    if fields["version"] != VERSION:
        raise ValueError(f"not a declaration of version {VERSION}")
    outputs = tuple(
        OutputSpec(pin=as_int(item["pin"]), active_low=as_bool(item["activeLow"]))
        for item in map(as_object, as_list(fields["outputs"]))
    )
    pwms = tuple(
        PwmSpec(pin=as_int(item["pin"]), frequency_hz=as_int(item["frequencyHz"]))
        for item in map(as_object, as_list(fields["pwms"]))
    )
    return Declaration(as_str(fields["board"]), outputs, pwms)


def _invalid(path: Path, detail: str) -> PrimumError:
    return PrimumError(ErrorCode.SAFE_DECLARATION_INVALID, {"path": str(path), "detail": detail})
