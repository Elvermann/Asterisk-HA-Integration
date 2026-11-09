# Changelog

## 1.2.1

- Fixed remote-party sensor being overwritten by Asterisk dialplan strings such as `*810...` in `NewConnectedLine.ConnectedLineNum`.
- Retains the valid destination number extracted from `DialBegin.DialString` when later connected-line events contain unknown or feature-code values.
- Leaves provider line occupancy sensors and read-only AMI permissions unchanged.

## 1.2.0

- Added an options-flow toggle to show or hide conversation-partner and call-duration sensors.
- When the option is disabled, previously created optional conversation entities are removed from the Home Assistant entity registry.
- Added per-PJSIP-client conversation partner and answered-call duration sensors.
- Correlates source and destination channels from AMI `DialBegin`, with follow-up updates from `NewConnectedLine`, `Newstate`, `DialEnd`, and `Hangup`.
- Shows peer number/name, call direction, epcan line and channel metadata in sensor attributes.
- Added the MOBOTIX M26 endpoint 1003 to the known device labels.
- Kept the existing three epcan line sensors named only `1820`, `9092255` and `9092256`.
- Retains read-only AMI operation; no AMI write permissions are required.

## 1.1.0

- The three provider line binary sensors are named only `1820`, `9092255` and `9092256`.
- Dynamically discovers PJSIP client status sensors from AMI events.
- Monitors active provider call legs and PJSIP client channel state.