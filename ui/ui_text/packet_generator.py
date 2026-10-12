STRINGS = {
    "title": {"en": "Packet Generator", "de": "Paketgenerator"},
    "how_to_use_button": {"en": "❓ How to Use", "de": "❓ Anleitung"},
    "description": {
        "en": "Split a list of dates or timestamps into calendar-aligned packets sized close to a target record count.",
        "de": "Teilt eine Liste von Daten oder Zeitstempeln in kalenderausgerichtete Pakete auf, die möglichst nah an einer Ziel-Datensatzanzahl liegen.",
    },
    "select_file": {"en": "Select Date File", "de": "Datumsdatei auswählen"},
    "no_file_selected": {"en": "No file selected...", "de": "Keine Datei ausgewählt..."},
    "packet_size_label": {"en": "Packet Size (N):", "de": "Paketgröße (N):"},
    "packet_size_placeholder": {"en": "e.g. 70000", "de": "z. B. 70000"},
    "tolerance_label": {"en": "Tolerance %:", "de": "Toleranz %:"},
    "tolerance_placeholder": {"en": "e.g. 20", "de": "z. B. 20"},
    "granularity_label": {"en": "Start Granularity:", "de": "Start-Granularität:"},
    "granularity_values": {
        "year": {"en": "year", "de": "Jahr"},
        "half-year": {"en": "half-year", "de": "Halbjahr"},
        "quarter": {"en": "quarter", "de": "Quartal"},
        "month": {"en": "month", "de": "Monat"},
        "day": {"en": "day", "de": "Tag"},
    },
    "finest_granularity_label": {"en": "Finest Granularity:", "de": "Feinste Granularität:"},
    "finest_granularity_values": {
        "half-year": {"en": "half-year", "de": "Halbjahr"},
        "quarter": {"en": "quarter", "de": "Quartal"},
        "month": {"en": "month", "de": "Monat"},
        "day": {"en": "day", "de": "Tag"},
    },
    "finest_granularity_note": {
        "en": (
            "The finest calendar unit a packet boundary may use. Default: day. If a single day alone "
            "holds at least N records, day level is still used there, even with a coarser setting."
        ),
        "de": (
            "Die feinste Kalendereinheit, die eine Paketgrenze verwenden darf. Standard: Tag. Enthält ein "
            "einzelner Tag allein mindestens N Datensätze, wird dort trotzdem auf Tagesebene gearbeitet, "
            "auch bei einer gröberen Einstellung."
        ),
    },
    "start_date_label": {"en": "Start Date:", "de": "Startdatum:"},
    "end_date_label": {"en": "End Date:", "de": "Enddatum:"},
    "date_placeholder_optional": {"en": "DD.MM.YYYY (optional)", "de": "TT.MM.JJJJ (optional)"},
    "direction_checkbox": {
        "en": "Build backward",
        "de": "Rückwärts aufbauen",
    },
    "direction_note": {
        "en": (
            "Unchecked (default): builds oldest-to-newest, and the leftover packet that doesn't fit "
            "evenly is the most recent data. Checked: builds newest-to-oldest instead, so the "
            "leftover packet becomes the oldest data."
        ),
        "de": (
            "Nicht aktiviert (Standard): baut vom ältesten zum neuesten Datum auf, und das nicht "
            "passend aufgehende Restpaket enthält die aktuellsten Daten. Aktiviert: baut stattdessen "
            "vom neuesten zum ältesten auf, sodass das Restpaket die ältesten Daten enthält."
        ),
    },
    "sample_note": {
        "en": "If the file's format is unusual or ambiguous, give one real example instead of guessing:",
        "de": "Ist das Format der Datei ungewöhnlich oder mehrdeutig, gib ein echtes Beispiel an, statt zu raten:",
    },
    "sample_value_label": {"en": "Sample Value:", "de": "Beispielwert:"},
    "sample_value_placeholder": {"en": "e.g. 20230115143045 (optional)", "de": "z. B. 20230115143045 (optional)"},
    "sample_date_label": {"en": "Its Date:", "de": "Zugehöriges Datum:"},
    "run_button": {"en": "Generate Packets", "de": "Pakete erzeugen"},
    "processing": {"en": "Processing...", "de": "Wird verarbeitet..."},
}
