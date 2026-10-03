# Yu-Gi-Oh! Edison

Unser Archiv für Decklisten, Strategien und gemeinsame Duelle im Edison-Format.
Startpaarung: **Schwarzflügel gegen Lichtverpflichtete**.

## Struktur

- `decks/edison/`: Decklisten mit Herkunft, Version und Main-, Extra- und Side-Deck.
- `strategies/edison/`: Spielpläne und Hinweise zur Startpaarung.
- `games/`: Gespielte Partien, Zugprotokolle und gespeicherte Spielstände.
- `templates/`: Vorlagen für neue Decks und Partien.
- `rules/edison.md`: Regeln für unsere Duelle.

## Decklisten

Für beide Startdecks müssen noch veröffentlichte Listen aus dem Netz abgerufen
und mit ihrer Quelle gespeichert werden. Bis dahin sind sie nicht spielbereit.
Keine unbestätigte Liste wird als Original einer Online-Quelle ausgegeben.

Deckversionen erhalten eindeutige IDs, zum Beispiel `blackwings-v1`.
Vor dem ersten Zug wird die konkrete Liste in die Partie kopiert; spätere
Deckänderungen verändern damit keine alten Spielprotokolle.

## Partien speichern

Für jede Partie einen Ordner `games/JJJJ-MM-TT-001/` anlegen und die Vorlagen
kopieren. Dort `game.json` für Metadaten, `log.md` für Züge und `state.json`
für einen pausierten Spielstand ablegen. Verwendete Decklisten liegen als
Kopien im Unterordner `decks/` der Partie.

Vollständige Spielstände können verdeckte Karten enthalten. Während eines
laufenden Duells werden im Chat nur Informationen gezeigt, die der jeweilige
Spieler sehen darf. Ein öffentliches Protokoll enthält keine verdeckten Karten.

Noch keine Partie gespielt.
