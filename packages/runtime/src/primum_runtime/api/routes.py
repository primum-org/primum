"""HTTP and WebSocket routes.

Every handler is ``async``: they run on the event loop's thread, one at a time, so the
controller and the broadcaster are never used from two threads (FastAPI runs plain ``def``
handlers in a thread pool).
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from primum_runtime.api.broadcast import StateBroadcaster, Subscription
from primum_runtime.api.models import OutputCommand, StateBody
from primum_runtime.control import Controller, State

router = APIRouter(prefix="/api")


def _controller(request: Request) -> Controller:
    controller: Controller = request.app.state.controller
    return controller


type ControllerDep = Annotated[Controller, Depends(_controller)]


@router.get("/status")
async def status(controller: ControllerDep) -> StateBody:
    return StateBody.of(controller.state())


@router.put("/outputs/{name}")
async def set_output(name: str, command: OutputCommand, controller: ControllerDep) -> StateBody:
    controller.set_output(name, command.on)
    return StateBody.of(controller.state())


@router.post("/panic")
async def panic(controller: ControllerDep) -> StateBody:
    controller.panic()
    return StateBody.of(controller.state())


@router.delete("/panic")
async def release_panic(controller: ControllerDep) -> StateBody:
    controller.release_panic()
    return StateBody.of(controller.state())


@router.websocket("/ws")
async def state_updates(websocket: WebSocket) -> None:
    """Send the current state on connect, then every new state, until either side closes."""
    controller: Controller = websocket.app.state.controller
    broadcaster: StateBroadcaster = websocket.app.state.broadcaster
    await websocket.accept()
    # Subscribed before the current state is read, so no change falls in between.
    subscription = broadcaster.subscribe()
    tasks = {
        asyncio.create_task(_send_states(websocket, controller.state(), subscription)),
        asyncio.create_task(_wait_for_disconnect(websocket)),
    }
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            task.result()  # re-raise what went wrong, if anything
    finally:
        subscription.close()


async def _send_states(websocket: WebSocket, current: State, subscription: Subscription) -> None:
    state: State | None = current
    try:
        while state is not None:
            await websocket.send_json(StateBody.of(state).model_dump())
            state = await subscription.next()
    except WebSocketDisconnect:
        return  # the client left while a state was being sent
    await websocket.close()  # the service is stopping


async def _wait_for_disconnect(websocket: WebSocket) -> None:
    # The client sends nothing; reading is how a closed connection is noticed.
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
