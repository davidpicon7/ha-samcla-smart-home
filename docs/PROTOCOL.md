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

## Current implementation decisions

The reverse-engineered Android code gives enough signal to implement the transport conservatively without guessing every payload schema:

- The transport is line-based over TLS 1.2. The client connects to the hub, waits for a READY line, sends the command as ASCII text, and reads until OK, ERR, or INVALIDPIN.
- The raw payload text before the final OK is preserved as the response payload. This is the safest interpretation of the Java flow and keeps the implementation future-proof.
- The PIN is treated as an optional suffix to the command line, matching the observed behavior where the Android client appends a PIN when available.
- Manual irrigation commands use hexadecimal values for durations expressed in tenths of seconds. Sequential irrigation uses one duration field per valve, while simultaneous irrigation uses a shared duration plus a valve-selection mask.
- The current integration uses the generic status fields needed for the coordinator: connection state, firmware version, irrigation state, and default duration. The exact semantics of every status byte and model-specific payload remain device dependent and are therefore parsed conservatively.
- The local hub defaults remain the values observed in the Java constants: 10.0.0.1:9000. The cloud relay flow uses the observed relay endpoint 138.201.247.169:9001 but is not fully implemented in this repository yet.

### Remaining uncertainties

Some details are still intentionally left as protocol assumptions rather than hard facts:

- The exact payload schema for every command family is device-specific and may vary by firmware revision.
- The precise meaning of every status byte returned by the hub should be validated against a real device or a captured session.
- The exact valve discovery flow and the full cloud-relay sequence require a real-world trace before they can be implemented as strict parsers.
