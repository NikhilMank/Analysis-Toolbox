from .languages import APP_LANGUAGES
from . import app, difference, duplicate, whitespace, packet_generator, packet_matcher

UI_TEXT = {
    "app": app.STRINGS,
    "difference": difference.STRINGS,
    "duplicate": duplicate.STRINGS,
    "whitespace": whitespace.STRINGS,
    "packet_generator": packet_generator.STRINGS,
    "packet_matcher": packet_matcher.STRINGS,
}
