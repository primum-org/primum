"""Who may use the board's API: the pairing code and the devices paired with it.

A board has a code of six digits, made at random the first time it is asked for. A device
that gives it is paired: it gets a token, also random, that it sends with every request from
then on. The board keeps the code (it has to show it) and, of each token, only its hash:
whoever reads the file cannot pass for a device. A device stays paired until it is forgotten
or the code is renewed, which forgets them all.

Everything is one file in the data directory, ``pairing.json``, that only its owner reads,
written whole and renamed into place. It is read at every question, so what ``primum-pairing``
changes from outside reaches a running service at once.

Guessing is slow on purpose: after ``MAX_ATTEMPTS`` wrong codes in a row nothing is taken
for ``LOCK_S``, the right code neither. That count is in memory: it is the service's.
"""

import hashlib
import hmac
import json
import logging
import math
import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from primum_runtime.errors import ErrorCode, PrimumError

log = logging.getLogger(__name__)

NAME = "pairing.json"
CODE_DIGITS = 6
MAX_ATTEMPTS = 5
LOCK_S = 300.0
MAX_NAME = 64
_OWNER_ONLY = 0o600


@dataclass(frozen=True)
class Device:
    """A device that was paired. ``id`` names it to forget it; ``name`` is what it called
    itself, for a person to tell them apart."""

    id: str
    name: str


@dataclass(frozen=True)
class _Kept:
    code: str
    devices: tuple[Device, ...] = ()
    hashes: tuple[str, ...] = field(default=(), repr=False)  # of each device's token


class Pairing:
    """The code and the paired devices kept in ``data_dir``. ``clock`` measures the wait
    after too many wrong codes: monotonic seconds."""

    def __init__(self, data_dir: Path, clock: Callable[[], float]) -> None:
        self._file = data_dir / NAME
        self._clock = clock
        self._wrong = 0
        self._locked_until: float | None = None

    def code(self) -> str:
        """The code of this board, made now if it has none. ``pairing.unwritable``
        (``path``, ``detail``) if it cannot be kept."""
        return self._kept().code

    def renew(self) -> str:
        """A new code. Every device is forgotten: it is what to do when one is lost."""
        kept = _Kept(_new_code())
        self._write(kept)
        return kept.code

    def pair(self, code: str, name: str) -> tuple[Device, str]:
        """Pair a device that gives the code: the device and its token, which is told this
        once and never kept. ``pairing.code_wrong`` (``left``: the tries left before the
        wait), ``pairing.locked`` (``seconds``) while nothing is taken."""
        self._not_locked()
        kept = self._kept()
        if not hmac.compare_digest(code.encode(), kept.code.encode()):
            raise self._wrong_code()
        self._wrong = 0
        token = secrets.token_urlsafe(32)
        device = Device(secrets.token_hex(4), name[:MAX_NAME])
        added = replace(kept, devices=(*kept.devices, device), hashes=(*kept.hashes, _hash(token)))
        self._write(added)
        return device, token

    def device(self, token: str) -> Device | None:
        """The device ``token`` was given to, if it is still paired."""
        kept = self._read()
        if kept is None:
            return None
        given = _hash(token)
        for device, known in zip(kept.devices, kept.hashes, strict=True):
            if hmac.compare_digest(given, known):
                return device
        return None

    def devices(self) -> tuple[Device, ...]:
        kept = self._read()
        return () if kept is None else kept.devices

    def forget(self, device_id: str) -> None:
        """Unpair a device: its token is worth nothing from now on.
        ``pairing.device_unknown`` (``id``)."""
        kept = self._kept()
        left = [
            (device, known)
            for device, known in zip(kept.devices, kept.hashes, strict=True)
            if device.id != device_id
        ]
        if len(left) == len(kept.devices):
            raise PrimumError(ErrorCode.PAIRING_DEVICE_UNKNOWN, {"id": device_id})
        devices = tuple(device for device, _ in left)
        self._write(replace(kept, devices=devices, hashes=tuple(known for _, known in left)))

    def _not_locked(self) -> None:
        if self._locked_until is None:
            return
        left = self._locked_until - self._clock()
        if left > 0:
            raise PrimumError(ErrorCode.PAIRING_LOCKED, {"seconds": math.ceil(left)})
        self._locked_until = None

    def _wrong_code(self) -> PrimumError:
        self._wrong += 1
        if self._wrong < MAX_ATTEMPTS:
            return PrimumError(ErrorCode.PAIRING_CODE_WRONG, {"left": MAX_ATTEMPTS - self._wrong})
        self._wrong = 0
        self._locked_until = self._clock() + LOCK_S
        log.warning("%d wrong pairing codes in a row: none is taken for %d s", MAX_ATTEMPTS, LOCK_S)
        return PrimumError(ErrorCode.PAIRING_LOCKED, {"seconds": int(LOCK_S)})

    def _kept(self) -> _Kept:
        kept = self._read()
        if kept is None:
            kept = _Kept(_new_code())
            self._write(kept)
            log.info("this board has a new pairing code: `primum-pairing` shows it")
        return kept

    def _read(self) -> _Kept | None:
        """What is kept; nothing when there is no file or it does not say what it should
        (then no device is paired, and the board gets a new code)."""
        try:
            document = json.loads(self._file.read_text(encoding="utf-8"))
            code = document["code"]
            listed = document["devices"]
            devices = tuple(Device(str(item["id"]), str(item["name"])) for item in listed)
            hashes = tuple(str(item["token"]) for item in listed)
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError):
            log.exception("%s cannot be read: no device is paired", self._file)
            return None
        if not isinstance(code, str) or len(code) != CODE_DIGITS or not code.isdecimal():
            log.error("%s has no pairing code: no device is paired", self._file)
            return None
        return _Kept(code, devices, hashes)

    def _write(self, kept: _Kept) -> None:
        devices = [
            {"id": device.id, "name": device.name, "token": known}
            for device, known in zip(kept.devices, kept.hashes, strict=True)
        ]
        content = json.dumps({"code": kept.code, "devices": devices}).encode()
        temporary = self._file.with_suffix(".tmp")
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            temporary.unlink(missing_ok=True)  # one a power cut left may be anyone's to read
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _OWNER_ONLY)
            with os.fdopen(descriptor, "wb") as written:
                written.write(content)
                written.flush()
                os.fsync(written.fileno())
            _give_to_the_owner_of(self._file.parent, temporary)
            temporary.replace(self._file)
        except OSError as error:
            params = {"path": str(self._file), "detail": error.strerror or str(error)}
            raise PrimumError(ErrorCode.PAIRING_UNWRITABLE, params) from error


def _give_to_the_owner_of(directory: Path, file: Path) -> None:
    """The file is the service's to read: written by another user (root running
    ``primum-pairing``), it is handed to whoever owns the data directory."""
    owner = directory.stat()
    if owner.st_uid != os.geteuid():
        os.chown(file, owner.st_uid, owner.st_gid)


def _new_code() -> str:
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
