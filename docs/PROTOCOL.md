# SAMCLA protocol analysis

## Scope and constraints

This document is based on the reverse-engineered Java classes in the repository under .context. No Java code was copied; this is a translation of observed behavior into a clean Python-oriented design.

## Protocol summary

The official SAMCLA Android application communicates with the irrigation hub using a simple text-based protocol over TLS 1.2 on a TCP socket. The transport is not a modern REST API; it is a line-oriented protocol where commands are sent as ASCII text and the hub replies with lines such as READY, OK, ERR, or a response payload.

The details below are derived from the decompiled Android classes in `.context` (`SamclaNetworkTask`, `SbpManualActivity`, `Constants`, `SamclaTable`).

## Connection flow

1. Open a TCP connection to the hub address/port.
2. Configure an SSL/TLS 1.2 socket with client mode enabled.
3. Expect the hub to emit lines, including a READY line.
4. Send the command text to the socket.
5. Read the response lines until the hub returns OK, ERR, or a payload response.
6. Close the connection after the exchange.

### Observed transport details

- TLS 1.2 only; the Android app installs a trust-all `X509TrustManager`.
- Socket timeout: `60000 ms` (`Constants.WIFI_TIMEOUT`).
- `SoLinger(true, 10)` enabled.
- When connecting to the hub AP at `10.0.0.1`, the client sleeps 2 seconds before opening the socket.
- Responses such as `INVALIDPIN` are handled as terminal error lines.

## Handshake and command exchange

The Android code suggests the following exchange pattern:

- Server sends one or more lines.
- When the client sees a line containing READY, it sends the command.
- The hub then replies with one or more lines.
- A final line of OK indicates success.
- ERR indicates failure.
- In some flows, the last non-OK line before the final OK is used as a payload.

### Line framing (confirmed)

Each message is a single ASCII line terminated by `\n`. The client reads with `BufferedReader.readLine()` and writes with `PrintWriter.println()`.

Observed server lines:

| Line | Meaning |
| ---- | ------- |
| `READY` (or a line containing `READY`) | Hub is ready to accept a command |
| `OK` | Command completed successfully; ends the exchange |
| `ERR` | Command failed; client treats this as failure (`null` return) |
| `INVALIDPIN` | PIN rejected (cloud/remote flow) |
| Any other line | Payload fragment; usually semicolon-delimited hex fields |

Payload extraction on success:

1. Collect all lines until `OK` or `ERR`.
2. On `OK`, scan backwards from the end and take the last line that is neither `OK` nor `ERR` as the payload.
3. On `ERR`, treat the command as failed.

Special cases from `SamclaNetworkTask`:

- If `INVALIDPIN` appears at any point, return it immediately and close the socket.
- When connecting to the local AP address `10.0.0.1`, a successful payload is prefixed with `0000000000000000;` before being returned to the caller.
- In the cloud two-phase flow (see below), the final return value is `{intermediate_result};{payload}`.

## Available commands observed

The Java constants expose the following command families:

- SSH100_IRRIGSEQ: sequential irrigation
- SSH100_IRRIGSIM: simultaneous irrigation
- SSH100_SBP_STOPCYCLE: stop irrigation cycle
- SSH100_STATS / STATS: status or statistics
- SYS_VERSION: firmware version
- PUTJOB / PUSH_CHECKJOB: remote/cloud relay flow
- Other configuration commands such as `SYS_SETPIN`, `SYS_SETTIME`, `GETPROF`, `PUTPROF`, etc.

### Wire command examples (from `SbpManualActivity`)

```text
SSH100_IRRIGSEQ {device_psn} 0060;0120;0000;0000
SSH100_IRRIGSIM {device_psn} 0060;0003;0000;ffff;0000;ffff;0000;ffff
SSH100_IRRIGSEQ {device_psn} 0000;0000;0000;0000          # stop sequential (4-valve box)
```

Cloud wrapper for the same irrigation command:

```text
PUTJOB {hub_psn}{pin} {hub_mac_rf} SSH100_IRRIGSEQ {device_psn} {payload}
PUSH_CHECKJOB {hub_psn}{pin} {hub_mac_rf} {intermediate_result}
```

Duration encoding: user minutes/hours are converted to tenths of a second (`value = (hours*3600 + minutes*60) / 10`), then formatted as 4-digit lowercase hex (`%04x`). Simultaneous valve selection uses a bitmask (`BIT_MANUAL_EV1=1`, `EV2=2`, …, `EV10=512`).

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

The hub does **not** return JSON. All structured data is sent as compact semicolon-delimited strings with hexadecimal fields.

The client expects either:

- a plain `OK` / `ERR` status, or
- one or more payload lines followed by a final `OK`.

The Android code parses payloads with `response.split(";")` and `Integer.parseInt(field, 16)`.

### Irrigation response schema (confirmed)

After `SSH100_IRRIGSEQ` or `SSH100_IRRIGSIM`, the payload line uses (at least) four semicolon-separated fields:

| Index | Field | Interpretation |
| ----- | ----- | -------------- |
| `[0]` | hex | Present in the payload; not used by `SbpManualActivity` for manual irrigation |
| `[1]` | hex | Battery level (integer after hex decode) |
| `[2]` | hex | IO status byte (see IO byte flags below) |
| `[3]` | hex | Firmware version (integer after hex decode) |

Example parsing logic from the Android app:

```text
battery   = int(parts[1], 16)
io_byte   = int(parts[2], 16)
firmware  = int(parts[3], 16)
programmed_on_box = (io_byte & 0x10) == 0   # BIT_IO_NOPROG clear => programmed
```

### Status and firmware commands

`Constants.java` defines dedicated commands that likely return similar hex payloads:

| Command constant | Wire name | Purpose |
| ---------------- | --------- | ------- |
| `CMD_BATTERY` | `SSH100_STATS` | Device statistics / battery |
| `CMD_STATS` | `STATS` | General statistics |
| `CMD_SYSVERSION` | `SYS_VERSION` | Hub or device firmware version |

The decompiled sources in `.context` do not include the callers that parse `SSH100_STATS` or `SYS_VERSION` responses, but the irrigation response already exposes battery (`[1]`) and firmware (`[3]`) in the same format. Treat status queries as semicolon-delimited hex payloads until validated against a live hub.

## Possible states

The available Java code suggests the following logical states:

- idle
- irrigating
- stopped
- programmed / not programmed
- connected / disconnected
- pin error

### IO status byte flags (from `Constants.java`)

The IO byte at payload index `[2]` is a bitmask. Constants used by the Android app:

| Constant | Value | Meaning |
| -------- | ----- | ------- |
| `BIT_IO_NOPROG` | `0x10` (16) | No program stored on the physical controller |
| `BIT_IO_NOPROG_SBV` | `0x08` (8) | No program (SBV valve model variant) |
| `BIT_IO_LIMIT_EXCEED` | `0x20` (32) | Daily/limit threshold exceeded |
| `BIT_IO_EVEON` | `0x40` (64) | Event/valve active (irrigation running) |

Manual irrigation only checks `BIT_IO_NOPROG`: if `(io_byte & 16) == 16`, the box is considered **not programmed**; otherwise it is **programmed on box**.

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

These values define device families and capabilities such as number of valves and whether a rain sensor exists.

### Valve count by model (from `SamclaTable.getEV()`)

| Model code | Model name | Valves (`ev_num`) |
| ---------- | ---------- | ----------------- |
| 29000420 / 29000600 / 29001010 | SBP010* | 1 |
| 29000410 / 29000610 / 29001020 | SBP020* | 2 |
| 29000100 / 29000580 / 29001030 / 29099006 | SBP040* | 4 |
| 29000620 / 29001040 | SBP172* | 6 |
| 29000630 / 29001050 | SBP1B2* | 10 |

Rain sensor support is inferred with `SamclaTable.hasRainSensor(type)` when `type >= 5`.

## Handshake sequence (confirmed)

No multi-step application handshake exists beyond waiting for `READY`:

1. Open TLS 1.2 socket (trust-all certificate validator in the Android app).
2. If the target is the local AP at `10.0.0.1`, sleep 2 seconds before connecting.
3. Read lines until one contains `READY`.
4. Send the command as a single line (`PrintWriter.println`).
5. Read lines until `OK`, `ERR`, or `INVALIDPIN`.

Socket settings observed: `SoTimeout = 60000 ms`, `SoLinger(true, 10)`, client mode, TLS 1.2 only.

There is no separate login or PIN exchange on the local Wi-Fi path; the command itself is sent immediately after `READY`.

## PIN usage (confirmed)

| Connection mode | PIN in command? | Example |
| --------------- | --------------- | ------- |
| Local hub Wi-Fi (`10.0.0.1:9000`) | No | `SSH100_IRRIGSEQ {psn} {payload}` |
| Cloud relay (`138.201.247.169:9001`) | Yes, appended to hub PSN | `PUTJOB {hub_psn}{pin} {mac_rf} {command}` |

PIN management commands exist but are separate operations: `SYS_SETPIN`, `SYS_UNSETPIN`.

When the PIN is wrong in cloud mode, the hub returns the line `INVALIDPIN` instead of a payload.

## Cloud relay vs local TCP/SSL (confirmed)

### Local flow

- **Host/port:** `10.0.0.1:9000` (or the hub LAN address when not in AP mode).
- **Connections:** one TLS session per command.
- **Call:** `SamclaNetworkTask.connect(context, command, null, host, port, dialog)`.
- **Send:** the irrigation or control command directly after `READY`.
- **Return:** payload line (with `0000000000000000;` prefix when host is `10.0.0.1`).

### Cloud relay flow

- **Host/port:** `138.201.247.169:9001`.
- **Connections:** two sequential TLS sessions.
- **Phase 1 — submit job:**
  - Command: `PUTJOB {hub_psn}{pin} {mac_rf} {actual_command}`
  - Example: `PUTJOB 1234567890123456789012345678901234567890 AA:BB:CC:DD:EE:FF SSH100_IRRIGSEQ ...`
  - Waits for `OK`; captures the penultimate line as `intermediate_result`.
- **Phase 2 — poll result:**
  - Command: `PUSH_CHECKJOB {hub_psn}{pin} {mac_rf} {intermediate_result}`
  - Waits for `OK`; extracts payload as in the local flow.
  - **Return:** `{intermediate_result};{payload}`.

Note: PSN and PIN are concatenated without a separator in cloud commands.

## Valve discovery (confirmed)

Valve metadata is **not** returned inline in irrigation responses. The Android app loads it from persisted hub configuration (`Utils.loadConfSbp`):

| Property | Storage key (Constants) | Source |
| -------- | ----------------------- | ------ |
| Valve count | `sbp_ev_num_` (`SBP_EV`) | Derived from device model via `SamclaTable.getEV(model_code)` |
| Valve names | `sbp_ev1_name_` … `sbp_ev10_name_` | Populated during hub sync (not in manual-irrigation code path) |

Relevant sync commands defined in `Constants.java`:

- `SSH100_GETHUB` — hub topology
- `SSH100_GETMAP` — device map
- `SSH100_GETVOL` — valve names / volume configuration

`SbpManualActivity.loadEVs()` uses `ev_num` to show 1, 2, 4, 6, or 10 valve rows and reads `ev1_name` … `ev10_name` for labels. For a Home Assistant integration, expect to run a hub discovery/sync command once, cache model → valve count via `SamclaTable`, and store custom valve names from `SSH100_GETVOL` or equivalent sync data.

## Remaining gaps

The following are **not** covered by the current `.context` decompilation and should be validated against a live hub:

- Exact field layout of `SSH100_STATS`, `STATS`, and `SYS_VERSION` responses (likely same hex/semicolon format).
- Full hub sync sequence that populates `sbp_ev*_name_*` fields.
- Behavior of long-running commands such as `SSH100_LISTEN` (push/async updates).
