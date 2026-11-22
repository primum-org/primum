"""HTTP and WebSocket routes.

Every handler is ``async``: they run on the event loop's thread, one at a time, so the
controller and the broadcaster are never used from two threads (FastAPI runs plain ``def``
handlers in a thread pool).
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from primum_runtime.api.broadcast import StateBroadcaster, Subscription
from primum_runtime.api.models import OutputCommand, StateBody, VariableValue
from primum_runtime.control import Controller, State

router = APIRouter(prefix="/api")


def _controller(request: Request) -> Controller:
    controller: Controller = request.app.state.controller
    return controller


type ControllerDep = Annotated[Controller, Depends(_controller)]


@router.get("/status")
async def status(controller: ControllerDep) -> StateBody:
    return StateBody.of(controller.state())


@router.put("/outputs/{output_id}")
async def command_output(
    output_id: str, command: OutputCommand, controller: ControllerDep
) -> StateBody:
    """``output_id`` is the ``id`` the state gives the output."""
    controller.command(output_id, command.action, command.arguments, command.durationMs)
    return StateBody.of(controller.state())


@router.delete("/outputs/{output_id}")
async def release_output(output_id: str, controller: ControllerDep) -> StateBody:
    """Let go of an output a person commanded: it goes back to what the sequences say."""
    controller.release(output_id)
    return StateBody.of(controller.state())


@router.post("/sequences/{sequence_id}/start")
async def start_sequence(sequence_id: str, controller: ControllerDep) -> StateBody:
    controller.start_sequence(sequence_id)
    return StateBody.of(controller.state())


@router.post("/sequences/{sequence_id}/stop")
async def stop_sequence(sequence_id: str, controller: ControllerDep) -> StateBody:
    controller.stop_sequence(sequence_id)
    return StateBody.of(controller.state())


@router.put("/variables/{variable_id}")
async def set_variable(
    variable_id: str, body: VariableValue, controller: ControllerDep
) -> StateBody:
    """Give a variable of the package a value. Commands that start from now on read it."""
    controller.set_variable(variable_id, body.value)
    return StateBody.of(controller.state())


@router.post("/events/{event_id}/fire")
async def fire_event(event_id: str, controller: ControllerDep) -> StateBody:
    """Make an event of the package happen: one whose source is ``ui`` or ``api``. An event
    that listens to an element only happens when the element says so."""
    controller.fire_event(event_id)
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
