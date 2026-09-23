from .languages import LANGUAGES, UI_STRINGS
from . import difference, duplicate, whitespace, packet_generator

HELP_CONTENT = {
    "difference": difference.CONTENT,
    "duplicate": duplicate.CONTENT,
    "whitespace": whitespace.CONTENT,
    "packet_generator": packet_generator.CONTENT,
}
