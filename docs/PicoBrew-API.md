# PicoBrew Zymatic HTTP API — firmware 1.1.14

This reference describes the outbound HTTP requests built by `Zymatic_1_1_14.hex`. Route names, query arguments and transport differences were checked against its AVR request builders. Response formats below describe client parsing or explicitly identified local-server behavior; they are not traffic captures. See the [firmware audit](Firmware-Audit.md) for the image hash and evidence addresses.

The firmware connects to `picobrew.com:80` and sends HTTP/1.0 GET requests with `Host: picobrew.com` and `Connection: close`. These requests contain no HTTP authentication credentials. Authorization enforced by the original service is unknown.

Request templates use uppercase placeholders for dynamic values. Each parameter table lists the arguments emitted for that operation, rather than all arguments accepted by the local Flask handler. Percent-encode query values as needed and decode them once before interpreting embedded separators. Preserve route capitalization.

## Route inventory

| Operation | WiFi path | Ethernet path | Query arguments emitted |
| --- | --- | --- | --- |
| Retrieve user or cleaning recipes | `/API/SyncUser` | `/API/SyncUSer` | `user`, `machine` |
| Check whether to resync recipes | `/API/checksync` | `/API/checksync` | `user` |
| Create a session | `/API/logSession` | `/API/logSession` | `user`, `recipe`, `code`, `machine`, `firm` |
| Log a step event | `/API/logsession` | `/API/logsession` | `session`, `code`, `data`, `state` |
| Log temperatures and recovery state | `/API/LogSession` | `/API/LogSession` | `session`, `data`, `code`, `step`, `state` |
| End a session | `/API/logSession` | `/API/logsession` | `session`, `code` |
| Recover a recipe | `/API/recoversession` | `/API/recoversession` | `session`, `code` |
| Recover machine state | `/API/recoversession` | `/API/recoversession` | `session`, `code` |
| Check application firmware version | `/API/zymaticFirmwareCheck` | `/API/zymaticFirmwareCheck` | `machine`, `ver`, `maj`, `min` |
| Retrieve associated accounts | `/API/usersetup` | `/API/usersetup` | `machine`, `admin` |
| Report first-setup identifiers | `/API/firstSetup` | `/API/firstSetup` | `machine`, `admin` |
| Report a session error or reset | `/API/sessionerror` | `/API/sessionerror` | `machine`, `session`, `errorcode` |

These operations use eight route families and eleven distinct path spellings. The three logging paths carry different operations; do not add every logging argument to every request.

## Retrieve user or cleaning recipes

```text
GET http://picobrew.com/API/SyncUser?user=USER_ID&machine=MACHINE_ID
GET http://picobrew.com/API/SyncUSer?user=USER_ID&machine=MACHINE_ID
```

The first template is WiFi; the second is Ethernet.

| Parameter | Value |
| --- | --- |
| `user` | Selected account identifier, or `00000000000000000000000000000000` for the cleaning/rinse program list. |
| `machine` | Machine identifier. |

The firmware uses the same operation for normal recipes and cleaning/rinse programs. Both arguments are present in both cases. The account identifier comes from `usersetup`; the client reserves 33 bytes for it, including its terminator.

The client parses a `#`-framed recipe list, with `/` separating recipe fields and steps, `,` separating fields within a step, and `|` separating recipes. The structural form is:

```text
#RECIPE_NAME/RECIPE_ID/STEP_NAME,TEMPERATURE,DURATION,LOCATION,DRAIN/|#
```

This is a schema, not a captured recipe. Multiple steps and recipes repeat their respective structures. The original service's exact program contents and failure responses are unknown.

## Check whether to resync recipes

```text
GET http://picobrew.com/API/checksync?user=USER_ID
```

| Parameter | Value |
| --- | --- |
| `user` | Selected account identifier. |

The client reads a payload between `#` delimiters. A first payload character of `!` returns false (no resync needed); another successfully parsed payload returns true. A failed request/parser operation also returns false. `#!#` is therefore a parser-compatible no-change response. The local server returns `\r\n#!#` for every request.

## Create a session

```text
GET http://picobrew.com/API/logSession?user=USER_ID&recipe=RECIPE_ID&code=0&machine=MACHINE_ID&firm=1.1.14
```

| Parameter | Value |
| --- | --- |
| `user` | Selected account identifier, or the all-zero identifier for a cleaning/rinse program. |
| `recipe` | Selected recipe/program identifier. |
| `code` | `0` for session creation. |
| `machine` | Machine identifier. |
| `firm` | Literal application version `1.1.14`, formatted as three decimal components separated by dots. |

Both transports use `/API/logSession`. This request does not contain `session`, `data`, `step` or `state`. The client reads a `#SESSION_ID#` response and checks that the returned identifier has 32 characters.

## Log a step event

```text
GET http://picobrew.com/API/logsession?session=SESSION_ID&code=1&data=ENCODED_STEP_NAME&state=STATE
```

| Parameter | Value |
| --- | --- |
| `session` | Identifier returned during session creation. |
| `code` | `1` for the step event. |
| `data` | Current step-name/event text, encoded for the query string. |
| `state` | Decimal machine/brew state supplied by the caller; its full enumeration is unverified. |

Both transports use lowercase `/API/logsession`. The builder always appends `data` and `state`; it does not append `step`. It does not parse an application-level acknowledgment. The local server returns an empty body.

## Log temperatures and recovery state

```text
GET http://picobrew.com/API/LogSession?session=SESSION_ID&data=ENCODED_READINGS&code=2&step=RECOVERY_SNAPSHOT&state=STATE
```

| Parameter | Value |
| --- | --- |
| `session` | Identifier returned during session creation. |
| `data` | Temperature-reading text, encoded for the query string. Each reading contains a sensor identifier and temperature; `/` separates the pair and `|` separates readings. |
| `code` | `2` for temperature/recovery-state logging. |
| `step` | Eight-field, slash-separated recovery snapshot. Preserve it exactly for subsequent recovery. |
| `state` | Decimal machine/brew state supplied by the caller; distinct from the recovery snapshot. |

Both transports use `/API/LogSession`. This request does not contain `user`, `recipe`, `machine` or `firm`.

The `step` builders differ in their final field:

```text
WiFi:     FIELD_1/FIELD_2/FIELD_3/FIELD_4/FIELD_5/FIELD_6/FIELD_7/1
Ethernet: FIELD_1/FIELD_2/FIELD_3/FIELD_4/FIELD_5/FIELD_6/FIELD_7/0
```

The full field meanings are unverified. `step` is separate from the step-name text sent by the step-event operation. These senders do not parse an application-level acknowledgment. The local server returns an empty body.

## End a session

```text
GET http://picobrew.com/API/logSession?session=SESSION_ID&code=3
GET http://picobrew.com/API/logsession?session=SESSION_ID&code=3
```

The first template is WiFi; the second is Ethernet.

| Parameter | Value |
| --- | --- |
| `session` | Identifier of the session being ended. |
| `code` | `3` for session termination. |

Neither termination builder appends `data`, `step` or `state`. Neither parses an application-level acknowledgment. The local server returns an empty body.

## Recover a recipe

```text
GET http://picobrew.com/API/recoversession?session=SESSION_ID&code=0
```

| Parameter | Value |
| --- | --- |
| `session` | Identifier of the session to recover. |
| `code` | `0` to retrieve its recipe/program. |

Both transports use this request shape. The client invokes the recipe-list parser on the response. The local server returns the matching uploaded recipe in the form `#RECIPE_NAME/RECIPE_ID/STEPS/|!#`; its handler does not resolve built-in cleaning/rinse recipes. The exact original-service failure response is unknown.

## Recover machine state

```text
GET http://picobrew.com/API/recoversession?session=SESSION_ID&code=1
```

| Parameter | Value |
| --- | --- |
| `session` | Identifier of the session to recover. |
| `code` | `1` to retrieve its saved recovery snapshot. |

Both transports use this request shape. The client reads a `#`-framed, slash-separated snapshot. A replacement server should return the complete previously saved `step` value as `#RECOVERY_SNAPSHOT#`, including the transport-dependent final field. The local server reads that value from the session's `machine_state` entry.

## Check application firmware version

```text
GET http://picobrew.com/API/zymaticFirmwareCheck?machine=MACHINE_ID&ver=1&maj=1&min=14
```

| Parameter | Value |
| --- | --- |
| `machine` | Machine identifier. |
| `ver` | Literal `1`, the first application-version component. |
| `maj` | Literal `1`, the second component. |
| `min` | Literal `14`, the third component. |

Both transports use this request shape. These version parameters belong to this route; the session-error builders do not send them. The client reads `#PAYLOAD#` and reports a newer firmware only if the first payload character is uppercase `T`. `#T#` and `#F#` are parser-compatible examples, not captured service responses. This operation displays an update notice; it does not download the firmware image.

## Retrieve associated accounts

```text
GET http://picobrew.com/API/usersetup?machine=MACHINE_ID&admin=0
```

| Parameter | Value |
| --- | --- |
| `machine` | Machine identifier used to find associated accounts. |
| `admin` | Literal `0` in both normal setup paths. Behavior for other values is unknown. |

The client skips bytes until the opening `#`, commits each account record on `|`, and ends on the closing `#`. The first record field is stored as the account identifier; the second is the displayed account name. The splitter recognizes `/`, `,` and `|`. A parser-compatible example using `/` is:

```text
#0123456789abcdef0123456789abcdef/Brewer|#
```

Include the trailing `|` to commit the last record. The original service's preferred field separator and failure responses are unverified.

## Report first-setup identifiers

```text
GET http://picobrew.com/API/firstSetup?machine=MACHINE_ID|SENSOR_ID_1,1/SENSOR_ID_2,2/SENSOR_ID_3,3/SENSOR_ID_4,4&admin=0
```

| Parameter | Value |
| --- | --- |
| `machine` | One compound value: the machine ID followed by `|` and four sensor-ID/index pairs separated by `/`; a comma separates each sensor ID from its decimal index. |
| `admin` | Literal `0`. |

The sensor indexes are `1` through `4`. There are no separate sensor query arguments. Their index-to-physical-sensor mapping is unverified.

The Ethernet builder emits the template above. The WiFi builder constructs the same list, then calls `strcat` with a null source; its exact effect on the transmitted value is unverified. Both paths attempt the same two query arguments. Neither parses an application-level acknowledgment; the original service's response and registration side effects are unknown.

## Report a session error or reset

```text
GET http://picobrew.com/API/sessionerror?machine=MACHINE_ID&session=SESSION_ID&errorcode=ERROR_CODE
```

| Parameter | Value |
| --- | --- |
| `machine` | Machine identifier. |
| `session` | Affected session identifier. |
| `errorcode` | Decimal numeric error/reset code, distinct from the logging operation's `code` parameter. |

Both transports use this request shape. The builders do not append `code`, `ver`, `maj` or `min`.

The reset-reporting caller selects the following values:

| Error code | Branch label/meaning |
| --- | --- |
| `300` | JTAG reset |
| `301` | External reset |
| `302` | Power-off reset |
| `303` | Brownout reset |
| `304` | Generic reset branch |
| `305` | “Jump to 0 reset” branch |

A watchdog reset uses the stored error code. This is not a complete error catalog. Neither sender parses an application-level acknowledgment, so the response body is unknown.

## Local server compatibility

The current [Flask blueprint](../picobrew_server/blueprints/picobrew_api.py) accepts all documented arguments for the implemented firmware operations:

| Handler / accepted paths | Argument handling |
| --- | --- |
| Recipes: `/API/SyncUser`, `/API/SyncUSer` | Requires `user` and `machine`. |
| Resync check: `/API/checksync` | Requires `user`; always reports no change. |
| Logging: `/API/logSession`, `/API/logsession`, `/API/LogSession` | Requires `code`; accepts `user`, `recipe`, `machine`, `firm`, `session`, `data`, `step`, `state`. Creation requests supply `recipe`; subsequent operations supply `session`. |
| Recovery: `/API/recoversession` | Requires `session` and integer `code` (`0` or `1`). |

The shared logging handler accepts all three spellings, but the firmware's operation-specific argument sets are those listed above. It creates a session whenever `recipe` is present, stores step names for `code=1`, stores temperatures and the `step` snapshot for `code=2`, and records termination for `code=3`. It accepts but does not persist `state`, `user`, `machine` or `firm`.

`zymaticFirmwareCheck`, `usersetup`, `firstSetup` and `sessionerror` are documented firmware routes without local handlers; requests to them currently return 404. This reference documents the firmware and current compatibility, without adding server implementations.
