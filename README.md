# Asterisk Line Monitor 1.2.2-beta.2

Home Assistant custom integration for monitoring Asterisk 23 / PJSIP over the read-only Asterisk Manager Interface (AMI).

It monitors the epcan lines identified by the numbers **1820**, **9092255** and **9092256**, and discovers PJSIP client status from AMI events. Optional per-client conversation partner and call-duration sensors can be enabled in the integration options.

## Features

- Three line-occupancy binary sensors named only `1820`, `9092255` and `9092256`.
- AMI connection status and active epcan call count.
- Dynamic PJSIP client status sensors (`online`, `offline`, `ringing`, `in call`, `dialing`, `unknown`).
- Optional conversation partner and answered-call duration sensors per PJSIP client.
- Read-only AMI operation; no AMI write permissions are required.
- Keeps the external destination from `DialBegin.DialString` when Asterisk temporarily reports a dialplan feature string as `NewConnectedLine.ConnectedLineNum`.

## HACS installation

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/Elvermann/Asterisk-HA-Integration` and select **Integration**.
3. Install **Asterisk Line Monitor**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and select **Asterisk Line Monitor**.

## Configuration

Enter the Asterisk host, AMI port, AMI username and AMI password in the integration setup flow.

Typical local setup:

| Setting | Value |
|---|---|
| Asterisk host | `ASTERISK_LAN_IP` |
| AMI port | `5038` |
| AMI username | `ha_line_monitor` |
| Home Assistant host allowed in `manager.conf` | `HOME_ASSISTANT_LAN_IP` |

The AMI user should be restricted to the Home Assistant source address and should have only the required read permissions. Do not expose TCP 5038 to the internet.

Example `manager.conf` user section:

```ini
[ha_line_monitor]
secret = YOUR_LONG_RANDOM_PASSWORD
deny = 0.0.0.0/0.0.0.0
permit = HOME_ASSISTANT_LAN_IP/255.255.255.255
read = system,call,dialplan
write =
```

## Line sensors

The three line sensors retain the display names:

- `1820`
- `9092255`
- `9092256`

For these binary sensors, `on` means occupied and `off` means free.

## Optional call details

Use **Settings → Devices & services → Asterisk Line Monitor → Configure** to enable or disable conversation partner and call-duration sensors.

- Enabled: additional per-PJSIP-client sensors are created.
- Disabled: those optional entities are removed from Home Assistant's entity registry.
- Line sensors and basic client-status sensors remain available.

Conversation duration starts when the call is answered, not while it is ringing.

## Notes and limitations

The integration is event-driven and does not issue AMI write actions or request a snapshot of active channels at startup. A call that was already in progress before Home Assistant connects or reconnects may not be discovered until new AMI events arrive. After an AMI reconnect, stale channel state is discarded.

Conversation-partner association is based on AMI `DialBegin`, `NewConnectedLine`, `Newstate`, `DialEnd` and `Hangup` events. Transfers, queues and complex forwarding can result in changing peer information depending on the call flow.

## Development and releases

The integration source is under `custom_components/asterisk_line_monitor/`.

For each new release:

1. Update the `version` in `custom_components/asterisk_line_monitor/manifest.json`.
2. Add release notes to `CHANGELOG.md`.
3. Commit and push the changes to the default branch.
4. Create and publish a GitHub Release with a matching tag, for example `v1.3.0`.

HACS can then offer the published release as an update.