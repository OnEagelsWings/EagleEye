#!/bin/sh
set -eu
sudo apt-get update
sudo apt-get install -y python3 recoll python3-recoll poppler-utils ocrmypdf tesseract-ocr-deu tesseract-ocr-eng ffmpeg libimage-exiftool-perl sherlock sleuthkit tshark zaproxy gitleaks python3-yara lynis
cd "$(dirname "$0")"
exec python3 bridge.py
