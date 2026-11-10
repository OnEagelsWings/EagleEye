# Build 482 – Dork-, Bild- und Graph-Wiederherstellung

- Vorhandene `eagleeye_pro.providers.dork_engine.DorkEngine` wird per fallautorisierter Oberfläche `/workbench/dorks482` nutzbar. Nur öffentliche Suchlinks; **keine** automatischen Suchtreffer, Browserklick führt zu Drittanbieter.
- Vorhandene lokale Bildanalyse `ctx.build354.ingest_image` mit MAGiC-/Metadaten-/Ähnlichkeitsprüfung wird über `/workbench/images482` erreichbar. Maximal 20 MB, CSRF/Origin, `research.run`, fallgetrennte Anzeige/Originaldaten, Quarantäne nicht als Vorschau.
- Bestehender interaktiver Graph `/graph464` und Build-447/449-Dossier bleiben verfügbar; keine neue Dossier-DB.
- `Geführte Recherche` und Hauptnavigation: Dork-Recherche, Bildakte und Graph sichtbar; vorhandene Kategorien und Fachwerkzeuge bleiben erhalten.
- Ein regulärer Fall statt Qualifikationsfall; Build-482-Windows-Installer, Startup/Runtime und Servicekennung integriert.
- Pflicht: Windows/Linux CI, echte Chromium-Navigation, Security/ACL, Preview-/Uploadprüfung, lokaler Startup und SHA-geprüfter Dossier-Restore; bei roten Tests bleibt PR Draft.
- Weiterhin kein freier Live-Crawler/Such-API-Adapter und **keine Freigabe** für vertrauliche Personen-/Kundenaufträge.
