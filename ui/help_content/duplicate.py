CONTENT = {
    "en": {
        "title": "How to Use: Duplicate Finder",
        "content": (
            "DUPLICATE FINDER\n"
            "Scans a single file for rows that are repeated, and produces a "
            "cleaned copy plus a log of what was removed.\n\n"
            "WHAT TO UPLOAD\n"
            "- One file. Supported formats: .xlsx, .csv, .txt\n\n"
            "HEADER ROW\n"
            "- Check \"File includes a header row\" if the first row is "
            "column titles, not data.\n"
            "- Leave it unchecked if the file starts straight with data.\n"
            "- If this is set wrong on a headerless file, the first real "
            "row of data gets silently treated as a header and disappears "
            "from the results.\n\n"
            "WHAT COUNTS AS A DUPLICATE\n"
            "- A row must match COMPLETELY (every column) to be treated as "
            "a repeat.\n"
            "- Leading/trailing spaces are ignored. Capitalization matters.\n\n"
            "WHAT YOU GET\n"
            "- _CLEANED: the file with duplicates removed (the first "
            "occurrence of each entry is kept).\n"
            "- _DUPLICATES_LOG: shows each duplicated entry and how many "
            "times it was repeated. Only created if duplicates were "
            "actually found.\n"
            "- Both are saved next to the original, in the same format."
        ),
    },
    "de": {
        "title": "Anleitung: Duplikatfinder",
        "content": (
            "DUPLIKATFINDER\n"
            "Durchsucht eine einzelne Datei nach wiederholten Zeilen und "
            "erzeugt eine bereinigte Kopie sowie ein Protokoll der "
            "entfernten Einträge.\n\n"
            "WAS HOCHGELADEN WERDEN SOLL\n"
            "- Eine Datei. Unterstützte Formate: .xlsx, .csv, .txt\n\n"
            "KOPFZEILE\n"
            "- Aktiviere \"File includes a header row\", wenn die erste "
            "Zeile Spaltentitel statt Daten enthält.\n"
            "- Lasse die Option deaktiviert, wenn die Datei direkt mit "
            "Daten beginnt.\n"
            "- Ist dies bei einer Datei ohne Kopfzeile falsch eingestellt, "
            "wird die erste echte Datenzeile stillschweigend als Kopfzeile "
            "behandelt und verschwindet aus den Ergebnissen.\n\n"
            "WAS ALS DUPLIKAT ZÄHLT\n"
            "- Eine Zeile muss VOLLSTÄNDIG (in jeder Spalte) übereinstimmen, "
            "um als Wiederholung zu gelten.\n"
            "- Führende und abschließende Leerzeichen werden ignoriert. "
            "Groß- und Kleinschreibung ist relevant.\n\n"
            "WAS DU BEKOMMST\n"
            "- _CLEANED: die Datei mit entfernten Duplikaten (das erste "
            "Vorkommen jedes Eintrags bleibt erhalten).\n"
            "- _DUPLICATES_LOG: zeigt jeden doppelten Eintrag und wie oft "
            "er wiederholt wurde. Wird nur erstellt, wenn tatsächlich "
            "Duplikate gefunden wurden.\n"
            "- Beide werden neben dem Original gespeichert, im gleichen "
            "Format."
        ),
    },
}
