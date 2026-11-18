# Asterisk Line Monitor 1.2.2

Home Assistant custom integration for monitoring Asterisk PJSIP provider registrations and PJSIP clients over the Asterisk Manager Interface (AMI).

## Features

- Discovers provider phone numbers dynamically from the AMI `PJSIPShowRegistrationsOutbound` response. No fixed phone numbers or maximum number of lines are configured.
- Creates one Home Assistant device for each distinct provider number found in the outbound registration snapshot.
- Each provider-line device contains exactly two entities:
  - **Gespräch** — exists as soon as the registration is discovered; initially reports `Frei`, and during a call reports the remote party when available.
  - **Registrierung** — reports whether at least one matching outbound registration is registered.
- Keeps integration overview sensors for AMI connectivity, active provider calls and the total number of PJSIP registrations.
- Dynamically discovers PJSIP client devices and their status sensors. Optional conversation-partner and answered-call-duration sensors can be enabled in the integration options.
- The provider endpoint `epcan` is not created as a separate PJSIP client device; provider call information is shown on the matching phone-number device.
- Uses AMI events for call tracking and the read-only registration-list action for dynamic line discovery.

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

The AMI account needs:
- Read permissions for the AMI events used by the integration.
- The `reporting` write permission for the `PJSIPShowRegistrationsOutbound` AMI action on Asterisk versions that authorize this action through its reporting privilege class.

Restrict the AMI account to the Home Assistant source address. Do not expose TCP 5038 to the internet and do not grant broad `all` permissions.

Example `manager.conf` user section (adapt the address and password):

```ini
[ha_line_monitor]
secret = YOUR_LONG_RANDOM_PASSWORD
deny = 0.0.0.0/0.0.0.0
permit = HOME_ASSISTANT_LAN_IP/255.255.255.255
read = system,call,dialplan,reporting
write = reporting
```

After changing `manager.conf`, reload the AMI configuration in Asterisk:

```asterisk
manager reload
```

## Provider line devices and entities

The number of provider-line devices is determined dynamically by the outbound PJSIP registrations returned by Asterisk. For every distinct `ContactUser` found in the registration snapshot, Home Assistant creates one device with exactly two entities. No phone numbers or provider-line counts are predefined or hard-coded; newly discovered registrations are added automatically.

The entity set is not limited to these example numbers. Additional registrations are discovered automatically.

| Entity | Initial / normal state | During a call |
|---|---|---|
| **Gespräch** | `Frei` | Remote party number when available; otherwise `Belegt` |
| **Registrierung** | Connected or disconnected according to the registration snapshot | Continues to reflect registration state |

The former standalone occupancy sensor named only after the phone number is no longer created. Obsolete legacy occupancy entities and the old `PJSIP epcan` client device are cleaned up during integration setup.

## PJSIP client entities

Other PJSIP client devices are discovered dynamically. Each client has a status sensor. When call details are enabled in the integration options, additional conversation-partner and answered-call-duration sensors are created.

Use **Settings → Devices & services → Asterisk Line Monitor → Configure** to enable or disable those optional client call-detail sensors.

- Enabled: conversation-partner and answered-call-duration sensors are created for PJSIP clients.
- Disabled: those optional entities are removed from Home Assistant's entity registry.
- Provider-line **Gespräch** and **Registrierung** entities remain available.

Conversation duration starts when the call is answered, not while it is ringing.

## Notes and limitations

The integration is event-driven for calls and periodically reconciles the outbound PJSIP registration list. Calls already in progress before an AMI connection or reconnection may not be fully reconstructed until new AMI events arrive. After an AMI reconnect, stale channel state is discarded.

Conversation-partner association is based on AMI events such as `DialBegin`, `NewConnectedLine`, `Newstate`, `DialEnd` and `Hangup`. Transfers, queues and complex forwarding can affect remote-party identification depending on the Asterisk call flow.

## Development and releases

The integration source is under `custom_components/asterisk_line_monitor/`.

For each release:

1. Update the `version` in `custom_components/asterisk_line_monitor/manifest.json`.
2. Add release notes to `CHANGELOG.md`.
3. Commit and push the changes to the default branch.
4. Create and publish a GitHub Release with a matching tag, for example `v1.2.2`.

HACS can then offer the published release as an update.
