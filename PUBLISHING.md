# Repository und HACS-Veröffentlichung

Repository: https://github.com/Elvermann/Asterisk-HA-Integration

## Installation über HACS

1. In HACS **Custom repositories** öffnen.
2. Repository-URL eintragen und als Kategorie **Integration** auswählen.
3. **Asterisk Line Monitor** installieren.
4. Home Assistant neu starten.
5. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** die Integration **Asterisk Line Monitor** auswählen.

## Neue Version veröffentlichen

1. Die Versionsnummer in `custom_components/asterisk_line_monitor/manifest.json` erhöhen.
2. Die Änderungen in `CHANGELOG.md` dokumentieren.
3. Änderungen in den Branch `main` committen und pushen.
4. Ein GitHub Release mit passendem Versions-Tag veröffentlichen, zum Beispiel `v1.2.2`.

## AMI-Sicherheit

Die Integration verwendet AMI ausschließlich lesend. Keine AMI-Schreibrechte vergeben und TCP-Port 5038 nicht aus dem Internet erreichbar machen. Zugangsdaten gehören ausschließlich in die Home-Assistant-Konfiguration und nicht ins Repository.
