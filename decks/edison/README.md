# Decklisten

| Deck | Status | Deck-ID |
| --- | --- | --- |
| Schwarzflügel / Blackwings | Online-Liste noch abzurufen | noch offen |
| Lichtverpflichtete / Lightsworn | Online-Liste noch abzurufen | noch offen |

Pro Liste eine JSON-Datei nach `templates/deck.json` speichern. Karten haben
englische Namen als eindeutige Referenz; deutsche Anzeigenamen können ergänzt
werden. `source.url`, Abrufdatum und Änderungen gegenüber der Quelle festhalten.
`.ydk`-Exporte können ergänzend gespeichert werden, sobald Karten-IDs vorliegen.

## Verbindliche Quelle

Alle Decklisten stammen von https://cardcluster.com/. Andere Deckarchive werden
nicht als Quelle verwendet. Die konkrete Deck-URL und das Abrufdatum gehören
zu jeder importierten Liste. Änderungen an importierten Listen werden als eigene
Version mit dokumentierten Abweichungen gespeichert.
