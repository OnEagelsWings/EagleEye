#!/usr/bin/env sh
# Erzeugt Datenbankpasswort und Anwendungsschlüssel (einmalig). Beide Dateien sicher zusätzlich verwahren:
# Ohne app.key lassen sich verschlüsselte Fotos, 2FA-Geheimnisse und schlüsselbasierte Sicherungen nicht lesen.
set -e
cd "$(dirname "$0")"
mkdir -p secrets backups
umask 077
[ -f secrets/db_password ] || python3 -c "import secrets; print(secrets.token_urlsafe(32), end='')" > secrets/db_password
[ -f secrets/app.key ] || python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode(), end='')" > secrets/app.key
# Container laufen als UID 10001 und müssen die Dateien lesen können
chmod 644 secrets/db_password secrets/app.key 2>/dev/null || true
chmod 700 secrets
# Der App-Container läuft als UID 10001 und schreibt die Sicherungen
if [ "$(id -u)" = "0" ]; then chown 10001:10001 backups; else echo "Hinweis: Ordner deploy/backups muss für UID 10001 beschreibbar sein (sudo chown 10001:10001 backups)."; fi
echo "Geheimnisse liegen in deploy/secrets/ – bitte zusätzlich offline sichern."
