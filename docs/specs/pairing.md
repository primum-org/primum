# Pairing

Who may use the API of a board. Decision 0034.

A board has a **pairing code**: six digits, made at random the first time the service or
`primum-pairing` asks for it. A device that gives the code is **paired**: it gets a token and
sends it with every request from then on. A device that is not paired is shown nothing and
commands nothing, panic included.

It is called a pairing code, not a PIN, in the API, the code and the texts: a pin is where
an element is wired.

## What is asked of whom

| Request | Without pairing |
|---|---|
| The page and its files (`/`) | Served: it is where the code is typed |
| `GET /api/pairing`, `POST /api/pairing` | Answered |
| Every other route under `/api`, whatever it does | `pairing.required` (401) |
| The WebSockets (`/api/ws`, `/api/trace/ws`) | Not opened: closed with 1008 before anything is sent |

A device says who it is in one of two ways, and the service takes either:

- the cookie `primum_session`, which a browser keeps: `HttpOnly` (the page's code never
  reads it), `SameSite=Strict` (a page of another site cannot make the browser send it, in a
  request or in a WebSocket), kept 400 days and given again each time the page asks
  `GET /api/pairing`, so a device in use never runs out;
- `Authorization: Bearer <token>`, for a program. It wins over the cookie.

A token does not expire: a device stays paired until it is forgotten or the code is renewed.
A board has no clock to trust for an expiry (the Pi 4 has no RTC), and an installation
touched once a year should not ask for the code again.

## The API

| Request | Does | Refused |
|---|---|---|
| `GET /api/pairing` | `{required, device}`: whether the service asks for pairing, and the device that asks (`{id, name, current}`) or `null` | |
| `POST /api/pairing` with `{"code": "123456", "name": "…"}` | Pairs: `{token, device}`, and the cookie. The token is told this once. `name` (optional, 64 characters) is what the device calls itself | `pairing.code_wrong` (403, `left`); `pairing.locked` (429, `seconds`); `pairing.unwritable` (500) |
| `DELETE /api/pairing` | Forgets the device that asks | |
| `GET /api/pairing/devices` | The paired devices | |
| `DELETE /api/pairing/devices/{id}` | Forgets one: its token is worth nothing from now on. Answers with those left | `pairing.device_unknown` (404, `id`) |

## Wrong codes

After 5 wrong codes in a row no code is taken for 5 minutes, the right one neither
(`pairing.locked`, with the seconds left). A right code sets the count back. Trying every
code takes most of a year. The count is the service's, in memory, for everyone at once:

- whoever reaches the port can keep new devices from pairing by sending wrong codes. Paired
  devices are not affected;
- restarting the service sets the count back, which takes being on the board.

## On the board

Everything is one file in the data directory, `pairing.json`, that only its owner reads:
the code (the board has to show it) and, of each device, its id, its name and the SHA-256
of its token. Whoever reads the file learns the code, but cannot pass for a paired device.
It is written whole and renamed into place.

`primum-pairing` shows the code; `primum-pairing --renew` makes a new one and forgets every
device (a board that changes hands, a device lost with nobody left to forget it from). Run
as root, it hands the file to the owner of the data directory, so the service still reads
it. The service reads the file at every question: a renewed code unpairs a running service
at once.

A file that cannot be read, or that does not say what it should, pairs nobody, and the board
gets a new code.

## Without pairing

`--no-pairing` (`PRIMUM_NO_PAIRING=1`) starts a service that asks for nothing: for a laptop
with a simulated HAL, and for tests. It says so when it starts, `GET /api/pairing` answers
`required: false`, and pairing with it is refused (`pairing.off`, 409). A board is never
run like that: `provision.sh` does not write it.

## Not yet

- A WebSocket that is open stays open when its device is forgotten: it goes on receiving
  states until it closes. Commands are refused at once.
- The traffic is plain HTTP on the local network: whoever listens to it reads the code as it
  is typed and the token after. HTTPS on a board with no name of its own is not solved here.
- Showing the code without a shell on the board (a screen, a label, the first-boot wizard):
  phase 7.
- Roles: every paired device may do everything.
