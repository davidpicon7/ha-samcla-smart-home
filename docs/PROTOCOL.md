# SAMCLA protocol analysis

## Scope and constraints

This document is based on the reverse-engineered Java classes in the repository under .context. No Java code was copied; this is a translation of observed behavior into a clean Python-oriented design.

## Protocol summary

The official SAMCLA Android application communicates with the irrigation hub using a simple text-based protocol over TLS 1.2 on a TCP socket. The transport is not a modern REST API; it is a line-oriented protocol where commands are sent as ASCII text and the hub replies with lines such as READY, OK, ERR, or a response payload.

The protocol is currently understood at a high level only. The initial structure is documented here, and any missing details are explicitly marked as TODOs rather than guessed.

## Connection flow

1. Open a TCP connection to the hub address/port.
2. Configure an SSL/TLS 1.2 socket with client mode enabled.
3. Expect the hub to emit lines, including a READY line.
4. Send the command text to the socket.
5. Read the response lines until the hub returns OK, ERR, or a payload response.
6. Close the connection after the exchange.

### Observed transport details

- The client uses TLSv1.2.
- The socket is configured with a short timeout.
- The flow seems to accept a command string and then parse the response lines.
- The Android app appears to treat certain responses such as INVALIDPIN specially.

## Handshake and command exchange

The Android code suggests the following exchange pattern:

- Server sends one or more lines.
- When the client sees a line containing READY, it sends the command.
- The hub then replies with one or more lines.
- A final line of OK indicates success.
- ERR indicates failure.
- In some flows, the last non-OK line before the final OK is used as a payload.

### Important caution

The exact framing of every response line is not fully reconstructed from the available Java source. The implementation should therefore treat the protocol as line-based but preserve the response text for later refinement.

## Available commands observed

The Java constants expose the following command families:

- SSH100_IRRIGSEQ: sequential irrigation
- SSH100_IRRIGSIM: simultaneous irrigation
- SSH100_SBP_STOPCYCLE: stop irrigation cycle
- SSH100_STATS / STATS: status or statistics
- SYS_VERSION: firmware version
- PUTJOB / PUSH_CHECKJOB: remote/cloud relay flow
- Other configuration commands such as SETPIN, SETTIME, GETPROF, PUTPROF, etc.

## Command structure

The manual irrigation commands are built from a sequence of values encoded as hexadecimal strings. The general structure is:

- Command name: SSH100_IRRIGSEQ or SSH100_IRRIGSIM
- Hub/valve identifier (PSN)
- A payload that encodes one or more irrigation durations

### Sequential irrigation payload

The sequential mode builds a payload such as:

- 0000;0000;0000;0000
- or a different number of fields depending on the valve count

The values are expressed as hexadecimal values representing durations in tenths of seconds (10 units = 1 second). The Android code converts the user-entered duration to this value.

### Simultaneous irrigation payload

The simultaneous mode uses a payload made of:

- a first hex field for the shared duration
- a second hex field for a bitmask of selected valves
- then repeated ffff/0000 placeholders for other fields

Example pattern:

- 0000;ffff;0000;ffff;0000;ffff;0000;ffff

## Response format

Observed response handling suggests that the client expects either:

- a plain OK / ERR status, or
- a payload string returned before OK.

The Android code parses responses by splitting on semicolons and converting the parts from hexadecimal to integers when appropriate.

### Example interpretation from the Android code

The manual irrigation flow expects a response that can be split on semicolons and then parsed as:

- battery value
- firmware version
- a status byte that is masked to infer whether the program is active

This indicates that the protocol may return a compact status payload rather than a fully structured JSON object.

## Possible states

The available Java code suggests the following logical states:

- idle
- irrigating
- stopped
- programmed / not programmed
- connected / disconnected
- pin error

The exact mapping to hub-native states is still incomplete.

## Sequential vs simultaneous irrigation

### Sequential mode

- One valve at a time.
- Each valve gets its own timing field.
- The timing payload is a list of durations, one per valve.

### Simultaneous mode

- All selected valves start together.
- The first value is a shared duration.
- A bitmask encodes which valves are selected.

This distinction is significant because the Android UI exposes different controls for each mode:

- sequential mode uses per-valve time pickers
- simultaneous mode uses a shared time plus valve selection checkboxes

## Important constants and identifiers

The Java constants reveal several important protocol identifiers:

- SSH100_IRRIGSEQ
- SSH100_IRRIGSIM
- SSH100_SBP_STOPCYCLE
- SYS_VERSION
- SSH100_STATS
- INVALIDPIN

The Android code also references default ports and addresses:

- local hub IP: 10.0.0.1
- local hub port: 9000
- cloud relay IP: 138.201.247.169
- cloud port: 9001

## Possible hub models

The model mapping table in the Java code suggests a family of hubs and valve controllers, including:

- HUB222A8H / HUB222Z8H
- SBP010A8H / SBP020A8H / SBP040A8H / SBP172A8H / SBP1B2A8H
- SBI010A8H
- SBV110A8H
- SBD100A8H
- REP006A8H / REP006Z8H

These values likely define device families and capabilities such as number of valves and whether a rain sensor exists.

## Unknowns and TODOs

The following points remain uncertain and should not be guessed in implementation:

- TODO: Determine the exact line framing of successful and failed responses.
- TODO: Confirm whether each command requires a specific initial handshake sequence beyond READY.
- TODO: Confirm the exact payload schema for status and firmware responses.
- TODO: Confirm whether the PIN is always required or only for some commands.
- TODO: Determine whether the hub returns structured data or only compact semicolon-delimited strings.
- TODO: Confirm how the cloud relay flow (PUTJOB / PUSH_CHECKJOB) differs from local TCP/SSL flow.
- TODO: Confirm the precise meaning of the status byte returned in the irrigation response.
- TODO: Confirm how the number of valves and their names are discovered dynamically from the hub.
