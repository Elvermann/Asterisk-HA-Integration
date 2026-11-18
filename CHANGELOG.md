# Changelog

## 1.2.2-beta.2

- Adds a central sensor for all outgoing PJSIP registrations and their status details.
- Detects epcan provider call legs even when the registration snapshot has not yet arrived; epcan-in remains separate.
- Adds a per-line conversation sensor after the first detected call; it shows the remote number during a call and Frei after hangup.
- Tracks remote-party information on the provider-side channel and restores previously registered line sensors after Home Assistant restarts.
- Keeps AMI operations read-only.
- Not yet validated against the live Asterisk/Home Assistant installation.

## 1.2.2-beta.1

- Beta: dynamically discovers outgoing PJSIP provider registrations through the read-only AMI action `PJSIPShowRegistrationsOutbound`.
- Maps registration objects named `epcan-reg-N` to their corresponding `epcan-N` endpoints and uses the AMI `ContactUser` value to identify provider line numbers.
- Keeps the inbound-only `epcan-in` endpoint separate from the three outgoing provider lines.
- Adds dynamic registration status entities and reconciles provider line entities as registration data changes.
- Preserves the existing provider line sensor behavior and read-only AMI operation.
- This beta has not yet been validated against the user's live Asterisk/Home Assistant setup.

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