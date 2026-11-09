# Erstveröffentlichung in GitHub und HACS

## Vor dem Push

1. Ein **öffentliches** GitHub-Repository anlegen, z. B. `asterisk-line-monitor`. Bei der Erstellung keine README, kein `.gitignore` und keine Lizenz automatisch hinzufügen, weil diese Dateien bereits im Paket liegen.
2. In `README.md` und `custom_components/asterisk_line_monitor/manifest.json` den Platzhalter `YOUR_GITHUB_USER` durch den tatsächlichen GitHub-Benutzernamen ersetzen.
3. Optional `codeowners` in `manifest.json` eintragen, z. B. `["@DEIN_GITHUB_NAME"]`.
4. Prüfen, dass keine Zugangsdaten oder produktiven `manager.conf`-Dateien im Repository liegen. Das enthaltene `manager.conf-SNIPPET.txt` enthält nur ein Passwort-Platzhalter.

## Repository initialisieren und veröffentlichen

Im entpackten Verzeichnis dieses Pakets ausführen:

```bash
git init -b main
git add .
git commit -m "Initial release 1.2.0"
git remote add origin https://github.com/YOUR_GITHUB_USER/asterisk-line-monitor.git
git push -u origin main

git tag -a v1.2.0 -m "Asterisk Line Monitor 1.2.0"
git push origin v1.2.0
```

Alternativ kann das Repository zuerst geklont und der Paketinhalt in den Klon kopiert werden.

## HACS hinzufügen

In HACS → ⋮ → Custom repositories die Repository-URL eintragen und als Kategorie **Integration** auswählen. Anschließend die Integration installieren bzw. mit HACS verwalten lassen.

## Künftige Updates

Beispiel für Version 1.3.0:

```bash
# manifest.json: version auf 1.3.0 setzen
# CHANGELOG.md: Abschnitt 1.3.0 ergänzen

git add .
git commit -m "Release 1.3.0"
git push

git tag -a v1.3.0 -m "Asterisk Line Monitor 1.3.0"
git push origin v1.3.0
```

Danach auf GitHub unter Releases aus dem Tag `v1.3.0` eine veröffentlichte Release erstellen (nicht nur einen Entwurf). HACS verwendet die GitHub-Releases, um verfügbare Versionen zu erkennen.

## HACS-Validierung

HACS-Integrations-Repositories benötigen unter anderem:

- `hacs.json` im Repository-Stammverzeichnis
- genau eine Integration unter `custom_components/<domain>/`
- `manifest.json` mit `domain`, `name`, `version`, `documentation`, `issue_tracker` und `codeowners`
- eine README im Stammverzeichnis

Siehe: https://hacs.dev/docs/publish/integration/ und https://hacs.dev/docs/publish/start/