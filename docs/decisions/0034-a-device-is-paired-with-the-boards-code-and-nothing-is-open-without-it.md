# 0034. A device is paired with the board's code, and nothing is open without it

- Status: Accepted
- Date: 2026-11-25

## Context
Since phase 1 whoever reached the port commanded the board (decision 0011), which was
acceptable with one LED and is not with packages that are activated through the API
(decision 0033) and motors behind them. Phase 5 builds the web UI, and its first block is
this: who may use the API. A board has no screen, no keyboard and no clock to trust, sits on
a local network without a name a certificate could be issued for, and may be touched once a
year.

## Decision
- **A code made on the board.** Six digits, random, made the first time it is asked for and
  kept in the data directory. `primum-pairing` shows it and renews it. No code is set at
  installation: it would sit in a configuration file and be the same on every board.
- **A paired device has a token**, random, of which the board keeps only the hash. A browser
  keeps it in an `HttpOnly`, `SameSite=Strict` cookie, which also covers the WebSocket; a
  program sends it as `Authorization: Bearer`. The service takes both.
- **A token does not expire.** A device is unpaired by forgetting it, or by renewing the
  code, which forgets them all.
- **Nothing without pairing, panic included.** The page is served and the code can be
  given; every other route answers `pairing.required`, and a WebSocket is not opened.
- **Guessing is slow, and slower each time**: 5 wrong codes in a row and none is taken for
  5 minutes, then 10, then 20, up to a day. The code never changes by itself and tokens
  never expire, so a wait that did not grow would be a matter of patience.
- **A file that cannot be read is not a file that is missing**: it is left alone and the
  request fails. Only a missing or broken one gives the board a new code.
- **A browser's request must come from the service's own page** (`Origin`): `SameSite`
  does not tell ports of one host apart.
- **Off only when told**: `--no-pairing`, for a laptop and for tests.
- **It is a pairing code, not a PIN**, everywhere: a pin is where an element is wired.

## Alternatives considered
- Panic open to anyone: whoever stands before a motor could stop it from any phone. Lost
  because then anyone on the network can stop a show, and the person before the motor has
  the power switch; a paired phone is what stops it from the page.
- Reading open, commanding paired: handy for a wall display, but it tells anyone on the
  network what is wired and what it does.
- Tokens that expire: a board without a trusted clock cannot say when, and asking for the
  code again in the middle of a season is worse than a token that lasts.
- Only a cookie: programs (Primum Studio, the MCP server) would have to pass for a browser.
- No pairing when simulated: the simulator would stop behaving as the board, and the UI
  could not be tried whole on a laptop.

## Consequences
- Every new route is behind pairing because the router is; a test lists the routes and
  fails for one that is not.
- Nobody stops a board from the page without having paired first. Pair the phones that
  must be able to before a show.
- Whoever reaches the port can keep new devices from pairing by sending wrong codes, for
  up to a day at a time; restarting the service ends it.
- The traffic is plain HTTP: on a network that is listened to, the code and the tokens can
  be read. Pairing keeps out whoever is on the network; it is not encryption.
- A device that loses its token pairs again. A board whose every device was lost is renewed
  from a shell on it.
- Decision 0011's "no authentication until phase 5" ends here.
