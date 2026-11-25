"""Pairing over HTTP: who may use the API, and the routes a device pairs through.

Every route of the API but these asks for a paired device (``paired``): its token, in the
cookie a browser keeps or in ``Authorization: Bearer`` for a program. Nothing is seen and
nothing is commanded without it, panic included. A service started with ``--no-pairing``
asks for nothing: that is for a laptop, never for a board.

The cookie is ``HttpOnly`` (the page's code never reads it) and ``SameSite=Strict`` (another
site's page cannot make the browser send it, in a request or in a WebSocket). ``SameSite``
tells sites apart, not ports: a page served from another port of the board is the same
site. So a request that says where it comes from (``Origin``, which a browser always sends
across origins and with a WebSocket) must come from the service's own page.
"""

from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Response, WebSocketException
from starlette.requests import HTTPConnection

from primum_runtime.api.models import DeviceBody, PairedBody, PairingBody, PairingRequest
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.pairing import Device, Pairing

router = APIRouter(prefix="/api/pairing")
COOKIE = "primum_session"
# As long as a browser keeps a cookie (they cap it near 400 days); it is given again each
# time the page asks whether it is paired, so a device in use never runs out.
COOKIE_MAX_AGE_S = 400 * 24 * 60 * 60
_BEARER = "bearer "
# The close code of a WebSocket for a request that is refused (RFC 6455, 1008).
WS_POLICY_VIOLATION = 1008


def _pairing(connection: HTTPConnection) -> Pairing | None:
    pairing: Pairing | None = connection.app.state.pairing
    return pairing


def _token(connection: HTTPConnection) -> str | None:
    authorization = connection.headers.get("authorization", "")
    if authorization.lower().startswith(_BEARER):
        return authorization[len(_BEARER) :].strip()
    return connection.cookies.get(COOKIE)


def _device(connection: HTTPConnection) -> Device | None:
    pairing = _pairing(connection)
    token = _token(connection)
    return None if pairing is None or token is None else pairing.device(token)


def paired(connection: HTTPConnection) -> None:
    """Refuse whoever is not a paired device: ``pairing.required`` (401), or a WebSocket
    that is not opened."""
    if _pairing(connection) is None:
        return
    refused = None
    if _device(connection) is None:
        refused = PrimumError(ErrorCode.PAIRING_REQUIRED)
    elif not _from_its_own_page(connection):
        refused = PrimumError(ErrorCode.REQUEST_ORIGIN_REFUSED)
    if refused is None:
        return
    if connection.scope["type"] == "websocket":
        raise WebSocketException(code=WS_POLICY_VIOLATION)
    raise refused


def _from_its_own_page(connection: HTTPConnection) -> bool:
    """Whether a request that says where it comes from comes from this service's page. A
    program says nothing, and has the token because it paired."""
    origin = connection.headers.get("origin")
    return origin is None or urlsplit(origin).netloc == connection.headers.get("host")


def _on(connection: HTTPConnection) -> Pairing:
    pairing = _pairing(connection)
    if pairing is None:
        raise PrimumError(ErrorCode.PAIRING_OFF)
    return pairing


type PairingDep = Annotated[Pairing, Depends(_on)]
type DeviceDep = Annotated[Device | None, Depends(_device)]


@router.get("")
async def status(connection: HTTPConnection, response: Response, device: DeviceDep) -> PairingBody:
    """Whether this service asks for pairing, and whether whoever asks is paired."""
    token = connection.cookies.get(COOKIE)
    if device is not None and token is not None:
        _keep(response, token)
    return PairingBody(
        required=_pairing(connection) is not None,
        device=None if device is None else DeviceBody.of(device, device),
    )


@router.post("")
async def pair(body: PairingRequest, response: Response, pairing: PairingDep) -> PairedBody:
    """Pair with the board's code. The token comes once, here: in the cookie for a browser,
    in the body for a program."""
    device, token = pairing.pair(body.code, body.name)
    _keep(response, token)
    return PairedBody(token=token, device=DeviceBody.of(device, device))


@router.delete("", dependencies=[Depends(paired)])
async def unpair(response: Response, pairing: PairingDep, device: DeviceDep) -> PairingBody:
    """Forget the device that asks."""
    if device is not None:
        pairing.forget(device.id)
    response.delete_cookie(COOKIE)
    return PairingBody(required=True, device=None)


@router.get("/devices", dependencies=[Depends(paired)])
async def devices(pairing: PairingDep, device: DeviceDep) -> list[DeviceBody]:
    return [DeviceBody.of(each, device) for each in pairing.devices()]


@router.delete("/devices/{device_id}", dependencies=[Depends(paired)])
async def forget(device_id: str, pairing: PairingDep, device: DeviceDep) -> list[DeviceBody]:
    """Forget a device, lost or no longer wanted: its token is worth nothing from now on."""
    pairing.forget(device_id)
    return [DeviceBody.of(each, device) for each in pairing.devices()]


def _keep(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE, token, max_age=COOKIE_MAX_AGE_S, httponly=True, samesite="strict", path="/"
    )
