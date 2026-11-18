# Asterisk Line Monitor 1.2.2-beta.4

Home Assistant custom integration for monitoring dynamically discovered Asterisk PJSIP provider lines and PJSIP clients over the Asterisk Manager Interface (AMI).

## Features

- Discovers the provider phone numbers dynamically from the AMI `PJSIPShowRegistrationsOutbound` response; no fixed number or line count is configured.
- Creates one Home Assistant device per discovered provider number.
- Each provider-line device has exactly two entities: **Gespräch** and **Registrierung**.
- The conversation sensor is created immediately when the registration is discovered and initially reports `Frei`; during calls it reports the remote party when available.
- The registration binary sensor reports whether at least one matching outbound registration is registered.
- Retains the integration overview sensors for AMI connectivity, active provider calls and total PJSIP registrations.
- Dynamically discovers PJSIP client status sensors and optional client conversation-detail sensors, excluding the provider endpoint `epcan`.
- Read-only AMI event monitoring plus the registration-list action required for dynamic discovery.

## HACS installation

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/Elvermann/Asterisk-HA-Integration` and select **Integration**.
3. Install **Asterisk Line Monitor**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and select **Asterisk Line Monitor**.

## Configuration

Enter the Asterisk host, AMI port, AMI username and AMI password in the integration setup flow.

The AMI user needs permission to receive the required events and to execute the read-only `PJSIPShowRegistrationsOutbound` action. Restrict the AMI account with an ACL to the Home Assistant host and do not expose TCP 5038 to the internet. The action's permission class may require `reporting` in the AMI user's write permissions; do not grant broad `all` permissions.

## Provider line entities

The number of line devices is not fixed. Each distinct `ContactUser` found in the outbound registration snapshot is used as a provider-line device name. For each number, the integration creates:

- **Gespräch** — initially `Frei`; during a call it shows the remote number when available. Additional call metadata is available as attributes.
- **Registrierung** — connected when at least one registration for that number reports `Registered`.

The old standalone occupancy entity named only after the phone number is no longer created. Legacy occupancy entities are removed from the entity registry during setup.

## PJSIP client entities

PJSIP client devices can expose a status sensor and, when enabled in the integration options, conversation-partner and answered-call-duration sensors. The provider endpoint `epcan` is not treated as a client device; its call information is shown on the corresponding provider-line device instead.

## Notes and limitations

The integration is event-driven for calls and periodically reconciles the outbound registration list. Calls already in progress before an AMI connection or reconnection may not be fully reconstructed until new AMI events arrive. Complex transfers, queues and forwarding can affect remote-party identification depending on Asterisk's call flow.

## Development and releases

The integration source is under `custom_components/asterisk_line_monitor/`. Beta releases are published for validation before the stable version is tagged.
