"""
Partitions a flat file of dates or timestamps into contiguous "packets" (date
ranges) whose record counts land as close as possible to a target size N -
for use cases like SAP data-migration test-list generation.

Input: a .txt file with ONE date or timestamp value per line (no header row,
no other columns or delimiters). Supported value formats: YYYYMMDD, DDMMYYYY,
YYMMDD, DDMMYY (and '.', '/', '-' separated equivalents), each optionally
followed by a time component (glued, space-, or 'T'-separated; HHMMSS,
HH:MM:SS, or HH:MM), plus 10-digit Unix epoch seconds and 13-digit epoch
milliseconds - including SAP-style values with thousands-separator grouping
punctuation applied (e.g.
"20.260.713.195.635" for the timestamp 20260713195635). Every timestamp is
reduced to its calendar date before packetization; multiple timestamps on the
same day count toward that day, same as multiple date-only rows would.

Output: an .xlsx report (From Date / To Date / No. of Files) written next to
the input file.

Public entry point: run_packet_generation(...) - see its docstring below for
full parameter details and the packetization algorithm.
"""

import pandas as pd
import os
import bisect
import codecs
import charset_normalizer
from datetime import datetime, timedelta, date


# ---------------------------------------------------------------------------
# Date-only format candidates - still used for the plain start_date/end_date
# filter arguments, which stay simple dates regardless of whether the INPUT
# FILE holds timestamps.
# ---------------------------------------------------------------------------

_DATE_FORMAT_CANDIDATES = ['%Y%m%d', '%d%m%Y']
for _sep in ('.', '/', '-'):
    _DATE_FORMAT_CANDIDATES.append(f'%Y{_sep}%m{_sep}%d')
    _DATE_FORMAT_CANDIDATES.append(f'%d{_sep}%m{_sep}%Y')


def _parse_single_date(s):
    """Parses a single user-typed start_date/end_date string."""
    s = str(s).strip()
    formats_to_try = _DATE_FORMAT_CANDIDATES + ['%Y-%m-%d']
    for fmt in formats_to_try:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f"Could not parse '{s}' as a date. Try DD.MM.YYYY, YYYYMMDD, "
        f"YYYY-MM-DD, or one of the other supported formats."
    )


# ---------------------------------------------------------------------------
# 2-digit-year date bases (e.g. SAP's "short form of time stamp" field,
# "21.02.20" for 21 Feb 2020) - the exact same 8-candidate shape as
# _DATE_FORMAT_CANDIDATES above, just with %y instead of %Y. %y follows
# Python's normal (POSIX) convention: 00-68 -> 2000-2068, 69-99 -> 1969-1999.
# Verified that %Y does NOT ambiguously accept a 2-digit value (Python's
# strptime rejects "21.02.20" against "%d.%m.%Y" outright), so there's no
# risk of a 2-digit-year row silently being misparsed as a 4-digit one.
# Kept separate from _DATE_FORMAT_CANDIDATES/_parse_single_date (which stay
# 4-digit-year only) since this is specifically for the INPUT FILE column,
# not for a human-typed start_date/end_date argument.
# ---------------------------------------------------------------------------

_DATE_FORMAT_CANDIDATES_2DIGIT_YEAR = ['%y%m%d', '%d%m%y']
for _sep in ('.', '/', '-'):
    _DATE_FORMAT_CANDIDATES_2DIGIT_YEAR.append(f'%y{_sep}%m{_sep}%d')
    _DATE_FORMAT_CANDIDATES_2DIGIT_YEAR.append(f'%d{_sep}%m{_sep}%y')

_ALL_DATE_BASES = _DATE_FORMAT_CANDIDATES + _DATE_FORMAT_CANDIDATES_2DIGIT_YEAR


# ---------------------------------------------------------------------------
# Date+time (timestamp) format candidates for the INPUT FILE column.
#
# Starts from all date-only candidates above - both 4-digit-year and
# 2-digit-year (so a plain-date file still detects exactly as before), then
# adds each one combined with a time part - glued (SAP CPUDT+CPUTM style,
# e.g. "20230115143045"), space-separated ("15.01.2023 14:30:45"), or
# 'T'-separated (ISO 8601, "2023-01-15T14:30:45") - and with the time itself
# glued with seconds (HHMMSS), colon-separated with seconds (HH:MM:SS), or
# colon-separated with no seconds at all (HH:MM, e.g. SAP's short time
# stamp form, "02:48"). 16 date bases x 3 separators x 3 time forms = 144
# additional candidates, 160 total. A glued no-seconds time form (HHMM) is
# deliberately NOT included - combined with a glued date it would produce a
# 10-digit fully-glued value, colliding in digit count with the epoch-
# seconds candidate with no concrete format seen yet that would need it.
#
# NOT covered: ISO 8601 timezone suffixes (e.g. trailing "Z" or "+02:00").
# A row using one would simply fail to parse under every candidate here and
# get reported via the existing "skipped rows" warning, same as any other
# unparseable row - it is a documented limitation, not a silent mismatch.
# ---------------------------------------------------------------------------

_TIME_PART_CANDIDATES = ['%H%M%S', '%H:%M:%S', '%H:%M']
_DATETIME_SEPARATORS = ['', ' ', 'T']

_DATETIME_FORMAT_CANDIDATES = list(_ALL_DATE_BASES)
for _date_fmt in _ALL_DATE_BASES:
    for _dt_sep in _DATETIME_SEPARATORS:
        for _time_fmt in _TIME_PART_CANDIDATES:
            _DATETIME_FORMAT_CANDIDATES.append(f'{_date_fmt}{_dt_sep}{_time_fmt}')

# Sentinel names for the two non-strptime epoch candidates, distinguished by
# digit count (10 digits = seconds, until year 2286; 13 digits = milliseconds).
_EPOCH_SECONDS = '<epoch-seconds>'
_EPOCH_MILLISECONDS = '<epoch-milliseconds>'
_ALL_CANDIDATES = _DATETIME_FORMAT_CANDIDATES + [_EPOCH_SECONDS, _EPOCH_MILLISECONDS]

_SAMPLE_SIZE = 5000  # bounded sample for format detection - see _sniff_datetime_format

# Candidates with NO literal separator anywhere in the format string - these
# are the only ones eligible for the digit-stripping fallback below, since a
# separator-free format is the only kind where stripping punctuation from the
# input can't destroy a meaningful field boundary. Every %H:%M-based
# combination always keeps its colon, so none of them ever qualify here -
# only the seconds-based glued forms do, for both year-digit widths.
_GLUED_FORMATS = {
    '%Y%m%d', '%d%m%Y', '%Y%m%d%H%M%S', '%d%m%Y%H%M%S',
    '%y%m%d', '%d%m%y', '%y%m%d%H%M%S', '%d%m%y%H%M%S',
}

# Each glued format's exact expected digit count (sum of each directive's
# fixed width) - required to guard the digit-stripping fallback below.
# Python's strptime numeric directives accept 1 OR 2 digits FLEXIBLY (not a
# fixed width), so blindly parsing a stripped digit string against a glued
# format without checking its length first can silently SUCCEED on a
# too-short string, by having directives consume fewer digits than
# intended - e.g. "1.2.2023" strips to "122023" (6 digits) and, without a
# length check, parses against %Y%m%d into the wildly wrong date
# 1220-02-03 with no error at all, or a space-separated 2-digit-year
# timestamp like "21.02.20 02:48" strips to "2102200248" (10 digits) and
# can silently misparse against the unrelated 12-digit %y%m%d%H%M%S.
# Requiring an EXACT digit-count match before ever attempting the fallback
# closes this off entirely.
_DIRECTIVE_DIGIT_WIDTHS = {'%Y': 4, '%y': 2, '%m': 2, '%d': 2, '%H': 2, '%M': 2, '%S': 2}
_GLUED_FORMAT_LENGTHS = {
    fmt: sum(_DIRECTIVE_DIGIT_WIDTHS[fmt[i:i + 2]] for i in range(0, len(fmt), 2))
    for fmt in _GLUED_FORMATS
}


def _digits_only(v):
    return ''.join(ch for ch in v if ch.isdigit())


def _parse_with_candidate(v, fmt):
    """
    Parses one raw value under one candidate ('<epoch-seconds>',
    '<epoch-milliseconds>', or a strptime format string). Returns a
    datetime.date, or raises ValueError if it doesn't fit.

    For the fully "glued" candidates (_GLUED_FORMATS: no literal separator
    anywhere) and the two epoch sentinels, an EXACT digit-count check
    (_GLUED_FORMAT_LENGTHS) always runs before any parse is attempted -
    against the raw value directly if it's already pure digits of the
    right length, or against a DIGIT-ONLY version of it (every non-digit
    character stripped) otherwise. This length gate is not optional
    politeness - Python's strptime numeric directives accept 1 OR 2 digits
    FLEXIBLY (not a fixed width), so calling strptime directly on a value
    shorter than the format's nominal length can still silently SUCCEED by
    having directives each consume fewer digits than intended (e.g. the
    8-digit "20150102" wrongly parsing as a complete %y%m%d%H%M%S, 12
    digits nominally, into 2020-01-05, or a space-separated 2-digit-year
    timestamp like "21.02.20 02:48" stripping to "2102200248", 10 digits,
    and wrongly parsing under that same 12-digit format) - checking the
    length first, before ever calling strptime, closes this off entirely,
    for both the direct value and the digit-stripped one. The
    digit-stripping itself recovers the true digit sequence when a field
    that's really just a plain glued number has had thousands-style
    grouping punctuation applied to it upstream - e.g. SAP's list viewer
    rendering the 14-digit timestamp 20260713195635 as
    "20.260.713.195.635", grouping every 3 digits from the right, which
    has nothing to do with where the actual year/month/day/hour/minute/
    second fields divide. Formats with a genuinely positioned separator
    (e.g. "%Y.%m.%d" or "%Y-%m-%d %H:%M:%S") are NOT given this treatment
    at all - `strptime` already matches their separators as literal
    characters at meaningful positions, and stripping them would destroy
    exactly what makes them parseable.
    """
    if fmt == _EPOCH_SECONDS:
        digits = _digits_only(v)
        if len(digits) != 10:
            raise ValueError(f"'{v}' is not a 10-digit epoch-seconds value")
        return datetime.fromtimestamp(int(digits)).date()
    if fmt == _EPOCH_MILLISECONDS:
        digits = _digits_only(v)
        if len(digits) != 13:
            raise ValueError(f"'{v}' is not a 13-digit epoch-milliseconds value")
        return datetime.fromtimestamp(int(digits) / 1000).date()
    if fmt in _GLUED_FORMATS:
        expected_len = _GLUED_FORMAT_LENGTHS[fmt]
        if len(v) == expected_len and v.isdigit():
            return datetime.strptime(v, fmt).date()
        digits = _digits_only(v)
        if len(digits) == expected_len:
            return datetime.strptime(digits, fmt).date()
        raise ValueError(
            f"'{v}' has {len(digits)} digit(s) after stripping punctuation, but {fmt} "
            f"requires exactly {expected_len}"
        )
    return datetime.strptime(v, fmt).date()


def _count_matches(candidates, rows):
    """Returns {candidate: success_count} for each candidate against rows."""
    counts = {}
    for fmt in candidates:
        success = 0
        for v in rows:
            try:
                _parse_with_candidate(v, fmt)
                success += 1
            except ValueError:
                continue
        counts[fmt] = success
    return counts


def _best_candidate(counts, total_rows):
    """Picks whichever candidate parses ALL rows, else whichever parses the
    MOST - returns (fmt, success_count), or (None, 0) if every count is 0."""
    best_fmt, best_success = None, -1
    for fmt, success in counts.items():
        if success == total_rows:
            return fmt, success
        if success > best_success:
            best_fmt, best_success = fmt, success
    return best_fmt, max(best_success, 0)


def _sniff_datetime_format(raw_values, sample_value=None, sample_date=None):
    """
    Detects which candidate (a strptime format, or one of the epoch
    sentinels) fits the input file's timestamp/date column.

    Detection runs against a bounded SAMPLE of the file (the first
    _SAMPLE_SIZE non-blank rows, or all of them if fewer) rather than the
    whole column - this keeps detection cost independent of file size and
    of how many candidates are tried (measured at ~9.5s for an 8-candidate
    full-column scan on a 6.5M-row file; a ~56-candidate full scan would
    take a minute or more). The full file is still parsed in one pass
    afterward with whichever candidate wins - unchanged in cost from
    today's behavior, since that pass already happens regardless.

    If sample_value and sample_date are BOTH given (one real example from
    the caller's own file: a raw value, and the date they know it
    represents - no strptime syntax required), candidates are first
    filtered to only those that parse sample_value AND land on exactly
    sample_date. If none survive, raises a clear ValueError rather than
    guessing. If exactly one survives, it's returned directly - no
    statistical scan needed. If more than one survives (rare), the
    statistical "parses all of the sample, else the most" tiebreak below
    is used, scoped to just the survivors.

    If no sample pair is given, the statistical tiebreak runs directly
    against the full candidate list (_ALL_CANDIDATES).

    Returns a candidate (a strptime format string, or one of the epoch
    sentinels above).
    """
    if not raw_values:
        raise ValueError("No date values found to detect a format from.")

    sample_rows = raw_values[:_SAMPLE_SIZE]

    candidates = _ALL_CANDIDATES
    if sample_value is not None:
        parsed_sample_date = _parse_single_date(sample_date)
        survivors = []
        for fmt in _ALL_CANDIDATES:
            try:
                if _parse_with_candidate(sample_value, fmt) == parsed_sample_date:
                    survivors.append(fmt)
            except ValueError:
                continue
        if not survivors:
            raise ValueError(
                f"The sample timestamp '{sample_value}' could not be matched to the given date "
                f"({_format_date_output(parsed_sample_date)}) under any supported pattern. Double-check "
                f"both values, or omit them to let the tool auto-detect the format instead."
            )
        if len(survivors) == 1:
            return survivors[0]
        candidates = survivors

    counts = _count_matches(candidates, sample_rows)
    best_fmt, best_success = _best_candidate(counts, len(sample_rows))

    if best_fmt is None or best_success == 0:
        raise ValueError(
            "Could not detect a consistent date/timestamp format in the input file. Supported: "
            "YYYYMMDD, DDMMYYYY, YYMMDD, DDMMYY (and '.', '/', '-' separated equivalents), each "
            "optionally followed by a time (glued, space-, or 'T'-separated; HHMMSS, HH:MM:SS, or "
            "HH:MM), plus 10-digit Unix epoch seconds and 13-digit epoch milliseconds - any of the "
            "fully glued forms (YYYYMMDD, DDMMYYYY, YYMMDD, DDMMYY, YYYYMMDDHHMMSS, DDMMYYYYHHMMSS, "
            "YYMMDDHHMMSS, DDMMYYHHMMSS) or the epoch forms may also carry extra grouping punctuation "
            "(e.g. a thousands separator inserted by an export tool, like '20.260.713.195.635'), "
            "which is stripped automatically. If none of these fit, pass sample_value and sample_date "
            "with one real example from your file."
        )

    # Detect genuine ambiguity: more than one candidate ties for the best
    # success rate AND they disagree on at least one row's resulting date.
    # This matters specifically for 2-digit-year formats - a value like
    # "21.02.20" is syntactically valid under BOTH %d.%m.%y (21 Feb 2020)
    # and %y.%m.%d (20 Feb 2021), since a day-of-month and a 2-digit year
    # occupy overlapping numeric ranges (unlike a 4-digit year, which is
    # never confusable with a day-of-month). Silently picking one via
    # arbitrary iteration order would risk a systematically wrong date
    # across the ENTIRE file with no error at all - far worse than asking
    # the caller to disambiguate with one known (sample_value, sample_date)
    # pair, which is exactly what happened when this was first found: two
    # such formats both matched 4999/5000 sample rows, and the one picked
    # arbitrarily first produced a 24-year date range for a file that only
    # actually spans about 6 weeks.
    tied = [fmt for fmt, success in counts.items() if success == best_success]
    if len(tied) > 1:
        disagreement_example = None
        for v in sample_rows:
            parsed_per_fmt = set()
            all_matched = True
            for fmt in tied:
                try:
                    parsed_per_fmt.add(_parse_with_candidate(v, fmt))
                except ValueError:
                    all_matched = False
                    break
            if all_matched and len(parsed_per_fmt) > 1:
                disagreement_example = v
                break
        if disagreement_example is not None:
            raise ValueError(
                f"The input file's format is ambiguous - {len(tied)} different patterns "
                f"({', '.join(tied)}) all fit equally well, but disagree on the resulting date for "
                f"a value like '{disagreement_example}'. This commonly happens with 2-digit years, "
                f"since a day-of-month and a 2-digit year can look identical. Pass sample_value and "
                f"sample_date with one real example from your file (and the date you know it "
                f"represents) to resolve this."
            )

    return best_fmt


# ---------------------------------------------------------------------------
# Calendar boundary math - one "_end_of_nth_X" helper per granularity, all
# following the same index-arithmetic pattern: convert start_date's position
# within a grid of X-sized blocks to a flat "block index", add n, convert
# back to a year/month, then take the last day of that month. Each is paired
# with a bounded candidate generator ("_X_candidates(start_date, end_date)")
# that yields boundaries one at a time and stops once a boundary would
# exceed end_date - unbounded (only the usual safety valve) when end_date is
# None, which only ever happens at the very first (coarsest) tier of a
# search; every recursive refinement always supplies a real bound (the
# busting span it's confined to).
# ---------------------------------------------------------------------------

def _end_of_nth_year(start_date, n):
    return date(start_date.year + n, 12, 31)


def _end_of_nth_half_year(start_date, n):
    half_start_month_index = 0 if start_date.month <= 6 else 6  # 0-indexed: Jan=0, Jul=6
    total_month_index = half_start_month_index + n * 6 + 5  # +5 lands on the LAST month of the nth half-year
    year = start_date.year + total_month_index // 12
    month = total_month_index % 12 + 1
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _end_of_nth_quarter(start_date, n):
    quarter_start_month_index = ((start_date.month - 1) // 3) * 3  # 0-indexed: Jan=0, Apr=3, Jul=6, Oct=9
    total_month_index = quarter_start_month_index + n * 3 + 2  # +2 lands on the LAST month of the nth quarter
    year = start_date.year + total_month_index // 12
    month = total_month_index % 12 + 1
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _end_of_nth_month(start_date, n):
    """
    Last calendar day of the month that is `n` months after the month
    containing start_date. n=0 -> end of start_date's own month.
    """
    total_month_index = (start_date.month - 1) + n
    year = start_date.year + total_month_index // 12
    month = total_month_index % 12 + 1
    if month == 12:
        return date(year, 12, 31)
    next_month_first = date(year, month + 1, 1)
    return next_month_first - timedelta(days=1)


def _year_candidates(start_date, end_date=None):
    n = 0
    while n <= 200:  # safety valve for pathologically sparse data
        b = _end_of_nth_year(start_date, n)
        if end_date is not None and b > end_date:
            return
        yield b
        n += 1


def _half_year_candidates(start_date, end_date=None):
    n = 0
    while n <= 400:
        b = _end_of_nth_half_year(start_date, n)
        if end_date is not None and b > end_date:
            return
        yield b
        n += 1


def _quarter_candidates(start_date, end_date=None):
    n = 0
    while n <= 800:
        b = _end_of_nth_quarter(start_date, n)
        if end_date is not None and b > end_date:
            return
        yield b
        n += 1


def _month_candidates(start_date, end_date=None):
    n = 0
    while n <= 2400:
        b = _end_of_nth_month(start_date, n)
        if end_date is not None and b > end_date:
            return
        yield b
        n += 1


def _day_candidates(start_date, end_date=None):
    """
    Yields every day from start_date onward. Always called with a real
    end_date in practice (day is always the finest tier, only ever reached
    via a recursive refinement that's already bounded to some busting
    span) - the unbounded/safety-valved branch exists only so this
    generator's signature matches every other tier's for a uniform tier
    list, not because it's ever exercised.
    """
    d = start_date
    n = 0
    while True:
        if end_date is not None and d > end_date:
            return
        yield d
        d += timedelta(days=1)
        n += 1
        if end_date is None and n > 73000:  # safety valve - only relevant if truly unbounded
            return


# ---------------------------------------------------------------------------
# Backward calendar boundary math - mirrors the forward block above exactly,
# but computes the FIRST day of the block that is `n` blocks BEFORE an
# anchor date, instead of the last day of the block `n` blocks after one.
# Used by the 'backward' build direction (present -> past): the same
# index-arithmetic pattern, just counting down instead of up. Python's
# floor-dividing `//`/`%` on a negative total_month_index naturally handles
# crossing a year boundary backward correctly (verified by hand for several
# cases, e.g. half-year index 0 minus 6 months lands on July 1 of the
# PREVIOUS year, not some malformed date).
# ---------------------------------------------------------------------------

def _start_of_nth_year_before(anchor, n):
    return date(anchor.year - n, 1, 1)


def _start_of_nth_half_year_before(anchor, n):
    half_start_month_index = 0 if anchor.month <= 6 else 6  # 0-indexed: Jan=0, Jul=6
    total_month_index = half_start_month_index - n * 6
    year = anchor.year + total_month_index // 12
    month = total_month_index % 12 + 1
    return date(year, month, 1)


def _start_of_nth_quarter_before(anchor, n):
    quarter_start_month_index = ((anchor.month - 1) // 3) * 3  # 0-indexed: Jan=0, Apr=3, Jul=6, Oct=9
    total_month_index = quarter_start_month_index - n * 3
    year = anchor.year + total_month_index // 12
    month = total_month_index % 12 + 1
    return date(year, month, 1)


def _start_of_nth_month_before(anchor, n):
    """
    First calendar day of the month that is `n` months before the month
    containing anchor. n=0 -> start of anchor's own month.
    """
    total_month_index = (anchor.month - 1) - n
    year = anchor.year + total_month_index // 12
    month = total_month_index % 12 + 1
    return date(year, month, 1)


def _year_candidates_backward(anchor, bound=None):
    n = 0
    while n <= 200:  # safety valve for pathologically sparse data
        b = _start_of_nth_year_before(anchor, n)
        if bound is not None and b < bound:
            return
        yield b
        n += 1


def _half_year_candidates_backward(anchor, bound=None):
    n = 0
    while n <= 400:
        b = _start_of_nth_half_year_before(anchor, n)
        if bound is not None and b < bound:
            return
        yield b
        n += 1


def _quarter_candidates_backward(anchor, bound=None):
    n = 0
    while n <= 800:
        b = _start_of_nth_quarter_before(anchor, n)
        if bound is not None and b < bound:
            return
        yield b
        n += 1


def _month_candidates_backward(anchor, bound=None):
    n = 0
    while n <= 2400:
        b = _start_of_nth_month_before(anchor, n)
        if bound is not None and b < bound:
            return
        yield b
        n += 1


def _day_candidates_backward(anchor, bound=None):
    """Mirrors _day_candidates: yields every day from anchor BACKWARD."""
    d = anchor
    n = 0
    while True:
        if bound is not None and d < bound:
            return
        yield d
        d -= timedelta(days=1)
        n += 1
        if bound is None and n > 73000:  # safety valve - only relevant if truly unbounded
            return


_FULL_TIER_GENERATORS = [_year_candidates, _half_year_candidates, _quarter_candidates,
                          _month_candidates, _day_candidates]
_FULL_TIER_GENERATORS_BACKWARD = [_year_candidates_backward, _half_year_candidates_backward,
                                   _quarter_candidates_backward, _month_candidates_backward,
                                   _day_candidates_backward]
_FULL_TIER_NAMES = ['year', 'half-year', 'quarter', 'month', 'day']

# Every tier except the finest (day) is a valid starting point - day itself
# isn't offered since starting there would mean no cascade at all.
_START_GRANULARITY_INDEX = {name: i for i, name in enumerate(_FULL_TIER_NAMES[:-1])}


def _tier_lists_for(start_granularity, direction='forward'):
    """
    Returns (tier_generators, tier_names) - a slice of the full
    year/half-year/quarter/month/day cascade starting from whichever tier
    `start_granularity` names, running through day (the finest) regardless
    of where it starts. `direction='backward'` selects the backward
    (present -> past) candidate generators instead of the forward ones -
    the tier NAMES are direction-agnostic labels, shared by both.
    """
    if start_granularity not in _START_GRANULARITY_INDEX:
        raise ValueError(
            f"start_granularity must be one of {sorted(_START_GRANULARITY_INDEX, key=list(_FULL_TIER_NAMES).index)}, "
            f"got {start_granularity!r}"
        )
    idx = _START_GRANULARITY_INDEX[start_granularity]
    generators = _FULL_TIER_GENERATORS if direction == 'forward' else _FULL_TIER_GENERATORS_BACKWARD
    return generators[idx:], _FULL_TIER_NAMES[idx:]


# ---------------------------------------------------------------------------
# File reading (.txt only, one date or timestamp per line)
# ---------------------------------------------------------------------------

_ENCODING_SAMPLE_BYTES = 1_048_576  # 1 MiB - bounded sample for statistical detection, see below


def _detect_text_encoding(filepath):
    """
    Picks a text encoding to open `filepath` with.

    First, sniffs its byte order mark (BOM) - the standard, reliable way
    to identify UTF-16/UTF-32 text (a real export was found to be UTF-16
    with a BOM, which the previous utf-8-sig-then-latin1 fallback had no
    way to read correctly - it silently decoded every 2-byte character as
    if it were 1-byte latin1, doubling the apparent character count with a
    stray null byte between each real one). Checks the UTF-32 BOMs before
    the UTF-16 ones deliberately - the UTF-16 LE BOM (FF FE) is a
    byte-for-byte PREFIX of the UTF-32 LE BOM (FF FE 00 00), so checking in
    the other order would misidentify a UTF-32 LE file as UTF-16 LE. A BOM
    is unambiguous when present, so this path never needs anything more.

    If no BOM is present, falls through to real statistical detection via
    charset_normalizer - covering everything a BOM can't (UTF-16/32 text
    with no BOM at all, single-byte code pages like Windows-1252, etc.)
    instead of just assuming 'utf-8-sig' as before. Detection runs against
    a bounded sample of the file's raw bytes (_ENCODING_SAMPLE_BYTES),
    not the whole file, so this stays fast on a large export - mirroring
    the same bounded-sampling approach _sniff_datetime_format already uses
    for timestamp-format detection. Falls back to 'utf-8-sig' (today's
    prior default) only if charset_normalizer can't find a confident match
    at all - rare, and no worse than the behavior this replaces.
    """
    with open(filepath, 'rb') as f:
        head = f.read(4)

    if head.startswith(codecs.BOM_UTF32_LE) or head.startswith(codecs.BOM_UTF32_BE):
        return 'utf-32'
    if head.startswith(codecs.BOM_UTF16_LE) or head.startswith(codecs.BOM_UTF16_BE):
        return 'utf-16'

    with open(filepath, 'rb') as f:
        sample = f.read(_ENCODING_SAMPLE_BYTES)
    match = charset_normalizer.from_bytes(sample).best()
    if match is not None and match.encoding:
        return match.encoding
    return 'utf-8-sig'


def _read_raw_date_column(filepath):
    """
    Reads a single-column .txt file of dates/timestamps and returns a list
    of raw, whitespace-stripped string values (blanks dropped). No parsing
    happens here - the format is detected separately.
    """
    ext = filepath.lower()
    if not ext.endswith('.txt'):
        raise ValueError(f"Unsupported file type for {filepath}. This tool only supports .txt files.")

    encoding = _detect_text_encoding(filepath)
    try:
        with open(filepath, encoding=encoding) as f:
            lines = f.read().splitlines()
    except UnicodeDecodeError:
        with open(filepath, encoding='latin1') as f:
            lines = f.read().splitlines()

    cleaned = []
    for v in lines:
        if v is None:
            continue
        s = str(v).strip()
        if s and s.lower() != 'nan':
            cleaned.append(s)
    return cleaned


def _get_unique_filename(filepath):
    if not os.path.exists(filepath):
        return filepath
    base_name, extension = os.path.splitext(filepath)
    counter = 1
    new_filepath = f"{base_name}_{counter}{extension}"
    while os.path.exists(new_filepath):
        counter += 1
        new_filepath = f"{base_name}_{counter}{extension}"
    return new_filepath


# ---------------------------------------------------------------------------
# Formatting helpers for the output report
# ---------------------------------------------------------------------------

def _format_date_output(d):
    return d.strftime('%d.%m.%Y')


def _format_count_output(n):
    return f"{n:,}".replace(',', '.')


# ---------------------------------------------------------------------------
# PHASE 1 - tiered cascade.
#
# For each packet: find the closest-crossing pair at the current tier's
# granularity (the last candidate whose cumulative count is still under
# packet_size, and the first one that reaches or crosses it), and pick
# whichever is numerically closer to packet_size (ties favor the larger
# candidate - fewer/larger packets are preferred). The earlier candidate
# can never itself bust the tolerance ceiling (it's below packet_size by
# construction, and packet_size <= cap), so it's always accepted outright
# when it's the closer one.
#
# If the later candidate is picked and its count busts the ceiling, the
# next finer tier is resolved (bounded to that same busting span), and
# "keep the whole busting span as one packet" is compared against "switch
# to the finer result" - whichever leaves the smaller worst-case miss from
# [floor, cap] wins (a tie keeps the coarser, single packet). This is
# DELIBERATE: always refining unconditionally, with no such comparison, was
# tested against real data and produces MORE total packets overall than
# this check does, which runs against the standing preference for fewer,
# larger packets. If "switch" wins, the finer tier's own result may itself
# already have cascaded down through even finer tiers still (each tier
# resolves its own switch-vs-keep question independently before handing a
# result back up) - this is what lets a caller configure a coarse starting
# tier (e.g. year) and have the cascade land on whatever granularity the
# data actually supports, all the way down to day if needed.
#
# Before a packet's cascade starts, _find_certain_skip_tier checks whether
# some of the configured coarser tiers can be skipped outright - not as a
# guess, but because they're PROVABLY pointless: a coarser tier's span
# always contains a finer one's, so if the finer tier's own first candidate
# already busts the cap, every coarser tier's first candidate is guaranteed
# to bust it too (its count can only be equal or higher). This only removes
# redundant "obviously going to fail" warnings on data that's uniformly
# denser than packet_size at a given tier (e.g. a file spanning just a few
# months, where trying whole-year candidates every time is pointless) - it
# never changes which boundary is ultimately chosen.
# ---------------------------------------------------------------------------

def _closest_match_raw(packet_size, candidates, count_fn, exhausted_fn):
    """
    Walks `candidates` (a sequence of boundary dates with non-decreasing
    cumulative count) accumulating count via count_fn, and stops at the
    first candidate whose cumulative count is >= packet_size, or where
    exhausted_fn signals the data has run out. Returns the raw crossing
    pair BEFORE picking a winner:
    (prev_boundary, prev_count, cur_boundary, cur_count, exhausted).
    prev_boundary/prev_count is None/0 if the very first candidate already
    reaches packet_size or is exhausted (no earlier candidate exists).

    count_fn/exhausted_fn are closures that encapsulate which end of the
    packet is FIXED (the counting/exhaustion reference point) - this is
    what lets this one function serve both build directions: forward
    (the packet's start is fixed, candidates are increasing "to"
    boundaries) and backward (the packet's end is fixed, candidates are
    decreasing "from" boundaries). Either way "candidates" is simply a
    sequence with non-decreasing cumulative count as it's walked, and
    count_fn/exhausted_fn are the only place that knows which physical
    direction is in play.
    """
    prev_boundary, prev_count = None, 0
    boundary = count = None
    exhausted = False
    for candidate in candidates:
        boundary = candidate
        count = count_fn(boundary)
        exhausted = exhausted_fn(boundary)

        if count >= packet_size or exhausted:
            return prev_boundary, prev_count, boundary, count, exhausted

        prev_boundary, prev_count = boundary, count

    return prev_boundary, prev_count, boundary, count, exhausted


def _violation(count, floor, cap):
    """0 if count is within [floor, cap]; how far under floor it is if
    undershooting; how far over cap it is if overshooting."""
    if count < floor:
        return floor - count
    if count > cap:
        return count - cap
    return 0


def _find_packet_boundary(packet_size, floor, cap, tier_generators, tier_names, tier_index, bound,
                           anchor, count_fn, exhausted_fn, narrow_fn, direction_label, warnings):
    """
    Recursively resolves the next packet's boundary at `tier_index`'s
    granularity (candidates generated from `anchor`, bounded to `bound` -
    None only at the very first, outermost call). See the PHASE 1 comment
    block above for the overall mechanic. Returns (boundary, count,
    exhausted, tier_name_used) - the caller (either the outer
    packet-building loop, or a coarser recursive call) is responsible for
    any "still outside [floor, cap]" warning, since an inner result may end
    up unused if the coarser tier's "keep" branch wins instead.

    count_fn/exhausted_fn are FIXED for the whole recursion of one packet
    (built once by the caller from that packet's true fixed edge - forward
    mode fixes the start, backward mode fixes the end). Only `anchor` (via
    narrow_fn) and `bound` narrow per recursion level, to confine a finer
    tier's search to the specific busting span that triggered it - the
    counting/exhaustion reference point never moves mid-recursion.
    direction_label ('starting'/'ending') only affects warning wording.
    """
    prev_boundary, prev_count, cur_boundary, cur_count, exhausted = _closest_match_raw(
        packet_size, tier_generators[tier_index](anchor, bound), count_fn, exhausted_fn
    )

    if prev_boundary is not None and abs(prev_count - packet_size) < abs(cur_count - packet_size):
        # prev can never bust the cap (it's always < packet_size <= cap by
        # construction, since it's the last candidate BEFORE crossing
        # target) - always accept it outright.
        return prev_boundary, prev_count, exhausted, tier_names[tier_index]

    this_boundary, this_count = cur_boundary, cur_count
    is_finest = tier_index == len(tier_generators) - 1

    if this_count <= cap or is_finest:
        return this_boundary, this_count, exhausted, tier_names[tier_index]

    # Busts cap, and a finer tier exists - resolve it, bounded to this
    # busting span (from wherever prev left off, or this level's own
    # anchor if the very first candidate here already overshoots, up to
    # this_boundary). count_fn/exhausted_fn are passed through UNCHANGED -
    # every tier's count must always be measured against the packet's true
    # fixed edge. Only the CANDIDATE search range narrows via narrow_fn;
    # the counting reference point never does.
    next_anchor = narrow_fn(prev_boundary, anchor)
    finer_boundary, finer_count, finer_exhausted, finer_tier_name = _find_packet_boundary(
        packet_size, floor, cap, tier_generators, tier_names, tier_index + 1, this_boundary,
        next_anchor, count_fn, exhausted_fn, narrow_fn, direction_label, warnings
    )

    if finer_exhausted:
        return finer_boundary, finer_count, finer_exhausted, finer_tier_name

    remainder_count = this_count - finer_count
    switch_violation = max(_violation(finer_count, floor, cap), _violation(remainder_count, floor, cap))
    keep_violation = this_count - cap

    if switch_violation < keep_violation:
        if finer_count > cap:
            # only reachable when finer_tier_name is the absolute finest
            # tier (day) and even IT still busts cap - nothing left to try
            warnings.append(
                f"Packet {direction_label} {_format_date_output(anchor)}: {tier_names[tier_index]}-level "
                f"granularity required {_format_count_output(this_count)} records, exceeding the tolerance "
                f"ceiling of {_format_count_output(int(cap))} - switched to {finer_tier_name}-level "
                f"granularity, but even that still gives {_format_count_output(finer_count)} records. "
                f"{finer_tier_name.capitalize()} is the finest granularity supported, so it was kept as "
                f"one packet."
            )
        else:
            warnings.append(
                f"Packet {direction_label} {_format_date_output(anchor)}: {tier_names[tier_index]}-level "
                f"granularity required {_format_count_output(this_count)} records, exceeding the tolerance "
                f"ceiling of {_format_count_output(int(cap))} - switched to {finer_tier_name}-level "
                f"granularity instead, landing on {_format_count_output(finer_count)} records."
            )
        return finer_boundary, finer_count, finer_exhausted, finer_tier_name

    warnings.append(
        f"Packet {direction_label} {_format_date_output(anchor)}: {tier_names[tier_index]}-level granularity "
        f"required {_format_count_output(this_count)} records, exceeding the tolerance ceiling of "
        f"{_format_count_output(int(cap))}. Switching to {finer_tier_name}-level granularity would leave a "
        f"remainder of {_format_count_output(remainder_count)} records - a bigger miss than leaving it "
        f"unsplit, so it was kept as one oversized {tier_names[tier_index]}-level packet instead."
    )
    return this_boundary, this_count, exhausted, tier_names[tier_index]


def _find_certain_skip_tier(cap, tier_generators, tier_names, anchor, count_fn):
    """
    Finds the finest tier that can be PROVEN to make every coarser tier in
    the list pointless for this packet, so the cascade can start there
    directly instead of wasting a warning on each coarser tier along the
    way.

    This is not a density estimate or a heuristic - it's an exact
    consequence of two facts: cumulative record counts only ever grow
    moving away from the packet's fixed edge, and every coarser tier's span
    (from the same anchor) fully CONTAINS every finer tier's span. So if a
    tier's own first candidate (its "n=0" boundary - the earliest point
    _closest_match_raw would ever look at) already has a count >= cap,
    every coarser tier's own first candidate spans at least that same
    range plus more, so its count can only be equal or higher - it is
    GUARANTEED to also land at/above cap. Trying it is not "unlikely to
    help", it provably cannot produce a different outcome.

    Checks tiers from finest (excluding the last one, `day`, which is
    always the non-skippable fallback) to coarsest, and returns the index
    of the FIRST (finest) one found to already bust the cap this way - all
    tiers coarser than it (lower indices) are skipped. Returns 0 (the
    configured coarsest tier - no skip) if none of them do, since then a
    coarser tier might still genuinely fit and deserves a real try.
    """
    for i in range(len(tier_names) - 2, -1, -1):
        first_candidate = next(tier_generators[i](anchor, None))
        count = count_fn(first_candidate)
        if count >= cap:
            return i
    return 0


def _build_packets_phase1(sorted_dates, packet_size, range_start, range_end, tolerance_percent,
                           start_granularity, direction='forward'):
    """
    direction='forward' (default): builds from range_start toward range_end,
    packet by packet, oldest to newest - byte-for-byte the original
    behavior of this function. range_end is the true last date, used as
    the exhaustion boundary.

    direction='backward': builds from range_end toward range_start,
    packet by packet, newest to oldest - the returned list comes out in
    that same newest-to-oldest (build) order, NOT chronological order; the
    caller is responsible for reversing it afterward. range_start is the
    true first date, used as the exhaustion boundary.

    Either way, the "doesn't fit evenly" leftover packet ends up LAST in
    the returned list - the end furthest from where building started -
    which is exactly the property Phase 2's severely-off regrouping (and
    the caller's final-edge display override) already rely on.
    """
    packets = []
    warnings = []
    floor = packet_size * (1 - tolerance_percent / 100)
    cap = packet_size * (1 + tolerance_percent / 100)
    tier_generators, tier_names = _tier_lists_for(start_granularity, direction)

    if direction == 'forward':
        current_start = range_start
        while True:
            start_idx = bisect.bisect_left(sorted_dates, current_start)
            if start_idx >= len(sorted_dates):
                break

            count_fn = lambda b, _si=start_idx: bisect.bisect_right(sorted_dates, b) - _si
            exhausted_fn = lambda b: b >= range_end
            narrow_fn = lambda prev, anchor: prev + timedelta(days=1) if prev is not None else anchor

            start_tier_index = _find_certain_skip_tier(cap, tier_generators, tier_names, current_start, count_fn)
            chosen_boundary, chosen_count, _, tier_used = _find_packet_boundary(
                packet_size, floor, cap, tier_generators, tier_names, start_tier_index, None,
                current_start, count_fn, exhausted_fn, narrow_fn, 'starting', warnings
            )

            if chosen_count < floor:
                warnings.append(
                    f"Packet starting {_format_date_output(current_start)}: the closest available {tier_used}-level "
                    f"boundary gives {_format_count_output(chosen_count)} records, which falls below the tolerance "
                    f"floor, outside the {tolerance_percent}% band around the target of "
                    f"{_format_count_output(packet_size)} ({_format_count_output(int(floor))}-"
                    f"{_format_count_output(int(cap))}). {tier_used.capitalize()} is the finest granularity "
                    f"reached for this packet, so it was kept as one packet."
                )

            packets.append({'from': current_start, 'to': chosen_boundary, 'count': chosen_count})
            current_start = chosen_boundary + timedelta(days=1)
    else:
        current_end = range_end
        while True:
            end_idx = bisect.bisect_right(sorted_dates, current_end)
            if end_idx <= 0:
                break

            count_fn = lambda b, _ei=end_idx: _ei - bisect.bisect_left(sorted_dates, b)
            exhausted_fn = lambda b: b <= range_start
            narrow_fn = lambda prev, anchor: prev - timedelta(days=1) if prev is not None else anchor

            start_tier_index = _find_certain_skip_tier(cap, tier_generators, tier_names, current_end, count_fn)
            chosen_boundary, chosen_count, _, tier_used = _find_packet_boundary(
                packet_size, floor, cap, tier_generators, tier_names, start_tier_index, None,
                current_end, count_fn, exhausted_fn, narrow_fn, 'ending', warnings
            )

            if chosen_count < floor:
                warnings.append(
                    f"Packet ending {_format_date_output(current_end)}: the closest available {tier_used}-level "
                    f"boundary gives {_format_count_output(chosen_count)} records, which falls below the tolerance "
                    f"floor, outside the {tolerance_percent}% band around the target of "
                    f"{_format_count_output(packet_size)} ({_format_count_output(int(floor))}-"
                    f"{_format_count_output(int(cap))}). {tier_used.capitalize()} is the finest granularity "
                    f"reached for this packet, so it was kept as one packet."
                )

            packets.append({'from': chosen_boundary, 'to': current_end, 'count': chosen_count})
            current_end = chosen_boundary - timedelta(days=1)

    return packets, warnings


# ---------------------------------------------------------------------------
# PHASE 2 - regroup severely-off packets.
#
# Phase 1 makes each packet decision locally (only looking one step ahead),
# which is usually fine but can occasionally leave a genuinely bad pair
# sitting side by side - e.g. one severely undersized packet immediately
# followed by one severely oversized packet (a whole crossing span that
# didn't individually bust the cap enough to trigger Phase 1's own
# finer-tier fallback, but was still a bad split relative to its neighbor).
#
# This pass looks at the WHOLE Phase 1 list and fixes only the packets that
# are severely off - far outside the normal [floor, cap] band, using a
# wider "severity" band that begins one sixth of the way from the tolerance
# edge toward total nonsense (100% off target), so that merely imperfect
# (but still reasonable) packets are left untouched. Most of the list keeps
# its original Phase 1 boundaries; only the pathological entries get
# touched.
#
# For each run of adjacent severely-off packets, the fix is to treat their
# combined date range as raw material to redistribute: estimate how many
# packets it SHOULD become (round(total / packet_size)), and evenly
# redistribute the range into that many day-level pieces. If the result is
# still severely off (the window didn't have enough - or had too much -
# material to divide evenly, e.g. because its immediate neighbors were
# already well-sized and there was nothing "spare" to borrow), the window
# widens to absorb one more neighboring packet (preferring the next packet,
# then the previous one) and tries again, until it succeeds or there is
# nothing left to absorb.
# ---------------------------------------------------------------------------

def _closest_day_to_target(sorted_dates, start_idx, search_start, search_end, target_count):
    """
    Scans every day from search_start up to (but not including) search_end
    and returns whichever day's cumulative count (from start_idx) is
    closest to target_count - ties favor the larger count, since
    fewer/larger packets are preferred for this tool.

    Returns (boundary, count).
    """
    best_boundary, best_count, best_diff = None, None, None
    d = search_start
    while d < search_end:
        count = bisect.bisect_right(sorted_dates, d) - start_idx
        diff = abs(count - target_count)
        if best_diff is None or diff < best_diff or (diff == best_diff and count > best_count):
            best_boundary, best_count, best_diff = d, count, diff
        d += timedelta(days=1)
    return best_boundary, best_count


def _partition_evenly(sorted_dates, range_start, range_end, num_pieces):
    """
    Splits [range_start, range_end] into exactly `num_pieces` day-level
    packets, aiming for each to be an even share of whatever's left at
    each step (so uneven day-to-day density doesn't compound into a lopsided
    final piece). Returns a list of packet dicts: {'from','to','count'}.
    """
    start_idx = bisect.bisect_left(sorted_dates, range_start)
    total = bisect.bisect_right(sorted_dates, range_end) - start_idx
    if num_pieces <= 1:
        return [{'from': range_start, 'to': range_end, 'count': total}]

    pieces = []
    piece_start = range_start
    remaining_total = total
    remaining_pieces = num_pieces
    for _ in range(num_pieces - 1):
        piece_start_idx = bisect.bisect_left(sorted_dates, piece_start)
        target_share = remaining_total / remaining_pieces
        boundary, count = _closest_day_to_target(
            sorted_dates, piece_start_idx, piece_start, range_end, target_share
        )
        pieces.append({'from': piece_start, 'to': boundary, 'count': count})
        piece_start = boundary + timedelta(days=1)
        remaining_total -= count
        remaining_pieces -= 1

    last_start_idx = bisect.bisect_left(sorted_dates, piece_start)
    last_count = bisect.bisect_right(sorted_dates, range_end) - last_start_idx
    pieces.append({'from': piece_start, 'to': range_end, 'count': last_count})
    return pieces


def _regroup_severely_off(packets, sorted_dates, packet_size, tolerance_percent, warnings,
                           leftover_at_start=False):
    """
    packets MUST be in chronological (ascending) order - the combined-span
    math below (bisect against sorted_dates using packets[window_start]
    ['from'] .. packets[window_end]['to']) only makes sense if list index
    order matches date order. In 'backward' build mode the caller reverses
    the newest-to-oldest build-order list into chronological order BEFORE
    calling this.

    leftover_at_start distinguishes which end of the (now-chronological)
    list holds the legitimate "doesn't fit evenly" packet that's exempt
    from regrouping when undersized - False (default, forward build) means
    it's the LAST (most recent) packet; True (backward build) means it's
    the FIRST (oldest) packet instead.
    """
    # "Severe" begins one sixth of the way from the tolerance edge toward
    # total nonsense (100% off target). This is always strictly wider than
    # the tolerance band (so an in-tolerance packet is never called severe),
    # asymptotic toward 100% (so it never needs clamping and never produces
    # a negative floor or an unbounded ceiling), and scales in the right
    # direction - a caller who asks for 5% gets a stricter severity
    # threshold than one who asks for 20%.
    severe_percent = tolerance_percent + (100 - tolerance_percent) / 6
    severe_floor = packet_size * (1 - severe_percent / 100)
    severe_cap = packet_size * (1 + severe_percent / 100)

    def is_severely_off(p):
        return p['count'] < severe_floor or p['count'] > severe_cap

    def needs_regrouping(idx):
        """
        A severely-off packet needs regrouping UNLESS it's the legitimate
        leftover edge of the list (see leftover_at_start) and undersized -
        that's the legitimate "end of data" case, not something to fix.
        """
        p = packets[idx]
        if not is_severely_off(p):
            return False
        leftover_idx = 0 if leftover_at_start else len(packets) - 1
        if idx == leftover_idx and p['count'] < severe_floor:
            return False
        return True

    i = 0
    while i < len(packets):
        if not needs_regrouping(i):
            i += 1
            continue

        # Found the start of a run of severely-off packets - extend to
        # include any immediately adjacent ones too.
        window_start, window_end = i, i
        while window_end + 1 < len(packets) and needs_regrouping(window_end + 1):
            window_end += 1

        while True:
            combined_from = packets[window_start]['from']
            combined_to = packets[window_end]['to']
            start_idx = bisect.bisect_left(sorted_dates, combined_from)
            total = bisect.bisect_right(sorted_dates, combined_to) - start_idx
            num_pieces = max(1, round(total / packet_size))

            new_pieces = _partition_evenly(sorted_dates, combined_from, combined_to, num_pieces)

            if all(not is_severely_off(p) for p in new_pieces):
                break

            can_expand_right = window_end + 1 < len(packets)
            can_expand_left = window_start > 0
            if can_expand_right:
                window_end += 1
            elif can_expand_left:
                window_start -= 1
            else:
                break  # nothing left to absorb - accept the best attempt

        warnings.append(
            f"Regrouped {window_end - window_start + 1} severely off packet(s) covering "
            f"{_format_date_output(combined_from)}-{_format_date_output(combined_to)} "
            f"({_format_count_output(total)} records total) into {len(new_pieces)} packet(s) instead."
        )
        packets[window_start:window_end + 1] = new_pieces
        i = window_start + len(new_pieces)

    return packets


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_packet_generation(input_file_path, packet_size, tolerance_percent,
                                             start_date=None, end_date=None,
                                             sample_timestamp=None, sample_timestamp_date=None,
                                             start_granularity='year', direction='forward'):
    """
    Reads a single-column file of dates or timestamps and partitions them
    into contiguous, calendar-aligned "packets" (date ranges) whose record
    counts land as close as possible to packet_size (N), within a
    symmetric (+/-) tolerance band.

    Phase 1 tries the coarsest tier of `start_granularity` first, and only
    cascades down to progressively finer tiers as far as the data actually
    requires - the cascade always runs through to day (the finest tier)
    regardless of where it starts:
      - start_granularity='year' (default): year -> half-year -> quarter
        -> month -> day.
      - start_granularity='half-year': half-year -> quarter -> month -> day.
      - start_granularity='quarter': quarter -> month -> day.
      - start_granularity='month': month -> day.
    At each tier transition, if a tier's closest-crossing-pair candidate
    busts the tolerance ceiling, the next finer tier is resolved (bounded
    to that same busting span), and "keep the whole busting span as one
    packet" is compared against "switch to the finer result" using a
    violation-based estimate of which leaves the smaller miss from
    [floor, cap] - whichever wins, wins (a tie keeps the coarser packet,
    since fewer/larger packets are preferred for this tool). This is NOT a
    "prefer the closest granularity" search - it's deliberately biased
    toward keeping the coarsest tier that's actually workable, since
    verified testing shows unconditionally always refining produces MORE
    total packets than this check does.

    For dense data, 'year' cascades all the way down to month/day anyway -
    and before each packet's cascade starts, any coarser tiers that are
    PROVABLY going to fail are skipped outright (not guessed at): if a
    finer tier's own first candidate already busts the cap, every coarser
    tier's first candidate is guaranteed to bust it too, since its span
    only ever contains more data, never less. This keeps a uniformly dense
    file (e.g. a few months' worth of SAP export where every packet
    genuinely needs day-level granularity) from generating a redundant
    warning for every coarser tier it was always going to fail - without
    changing which boundary ends up chosen for any packet.

    Phase 2 then looks at the WHOLE list and regroups any packets that are
    SEVERELY off - outside a band that begins one sixth of the way from the
    tolerance edge toward total nonsense (100% off target) - since Phase 1
    only ever looks one step ahead and can occasionally leave a genuinely
    bad pair sitting side by side (e.g. one severely undersized packet
    immediately followed by one severely oversized one). See the
    _regroup_severely_off docstring above for the full mechanism.

    Supported input patterns: YYYYMMDD, DDMMYYYY, YYMMDD, DDMMYY (and
    '.', '/', '-' separated equivalents), each optionally followed by a
    time (glued, space-, or 'T'-separated; HHMMSS, HH:MM:SS, or HH:MM),
    plus 10-digit Unix epoch seconds and 13-digit epoch milliseconds.
    Format detection runs
    against a bounded sample of the file, not the whole column, so cost
    stays independent of file size. By default the format is
    auto-detected; optionally pass sample_timestamp and
    sample_timestamp_date together - ONE real example from your own file
    (a raw value exactly as it appears, and the date you know it
    represents) - to skip guessing, with no strptime syntax required.

    Rows that cannot be parsed under the detected format (e.g. a stray
    header label) are skipped and reported as a warning.

    Parameters
    ----------
    input_file_path : str
        Path to a .txt file containing ONE date or timestamp value per
        line.
    packet_size : int
        Target record count (N) for each packet.
    tolerance_percent : float
        Required. How far above and below packet_size a packet is allowed
        to land before a warning is raised, e.g. 20 means the accepted band
        is [0.8x, 1.2x] the target.
    start_date : str or None
        Optional (any supported date format, e.g. DD.MM.YYYY - always a
        plain date, never a timestamp). Records before this date are
        excluded, and this becomes the first packet's from_date. If
        omitted, the earliest date found in the data is used.
    end_date : str or None
        Optional. Records after this date are excluded, and the FINAL
        packet's to_date is forced to this date exactly. If omitted, the
        final packet's to_date is written as the actual last date found
        in the data, regardless of its size.
    sample_timestamp : str or None
        Optional. One raw value copied exactly from the input file, used
        together with sample_timestamp_date to identify the format
        without needing to know strptime syntax. Must be given together
        with sample_timestamp_date, or not at all.
    sample_timestamp_date : str or None
        Optional. The date (any supported date format) that
        sample_timestamp is known to represent.
    start_granularity : str
        'year' (default), 'half-year', 'quarter', or 'month'. Which tier
        Phase 1 starts each packet search from - the cascade always runs
        through to day (the finest tier) regardless of where it starts,
        it just skips checking any tier coarser than the one named here.
    direction : str
        'forward' (default) or 'backward'. Which end of the data
        packetization starts from:
        - 'forward': starts at the earliest date and builds toward the
          most recent - the "doesn't fit evenly" leftover packet ends up
          being the MOST RECENT data (today's/every prior version's
          behavior).
        - 'backward': starts at the most recent date (or end_date, if
          given) and builds backward toward the earliest - the leftover
          packet ends up being the OLDEST data instead.
        Either way, the output report always lists packets chronologically
        (oldest From Date first) - only which end absorbs the leftover
        packet differs.

    Returns
    -------
    (saved_path, warnings) : tuple
        saved_path : str or None - path to the generated .xlsx report, or
            None if no data remained after filtering.
        warnings : list[str]
    """
    warnings = []

    if tolerance_percent is None:
        raise ValueError("tolerance_percent is required.")
    if tolerance_percent < 0:
        raise ValueError("tolerance_percent cannot be negative.")
    if (sample_timestamp is None) != (sample_timestamp_date is None):
        raise ValueError("sample_timestamp and sample_timestamp_date must be given together, or neither.")
    if start_granularity not in _START_GRANULARITY_INDEX:
        raise ValueError(
            f"start_granularity must be one of {sorted(_START_GRANULARITY_INDEX, key=list(_FULL_TIER_NAMES).index)}, "
            f"got {start_granularity!r}"
        )
    if direction not in ('forward', 'backward'):
        raise ValueError(f"direction must be 'forward' or 'backward', got {direction!r}")

    raw_values = _read_raw_date_column(input_file_path)
    if not raw_values:
        raise ValueError("The selected input file is empty.")

    date_fmt = _sniff_datetime_format(raw_values, sample_timestamp, sample_timestamp_date)

    parsed = []
    skipped = 0
    for v in raw_values:
        try:
            parsed.append(_parse_with_candidate(v, date_fmt))
        except ValueError:
            skipped += 1
    if skipped:
        warnings.append(
            f"Skipped {skipped:,} row(s) that could not be parsed under the detected format "
            f"({date_fmt}) - likely a header label."
        )

    if not parsed:
        raise ValueError("No valid dates could be parsed from the input file.")

    parsed_start_date = _parse_single_date(start_date) if start_date else None
    parsed_end_date = _parse_single_date(end_date) if end_date else None

    if parsed_start_date:
        before_count = sum(1 for d in parsed if d < parsed_start_date)
        if before_count:
            warnings.append(
                f"Excluded {before_count:,} record(s) dated before the given start date "
                f"({_format_date_output(parsed_start_date)})."
            )
        parsed = [d for d in parsed if d >= parsed_start_date]

    if parsed_end_date:
        after_count = sum(1 for d in parsed if d > parsed_end_date)
        if after_count:
            warnings.append(
                f"Excluded {after_count:,} record(s) dated after the given end date "
                f"({_format_date_output(parsed_end_date)})."
            )
        parsed = [d for d in parsed if d <= parsed_end_date]

    if not parsed:
        warnings.append("No records remain after applying the start/end date filters.")
        return None, warnings

    parsed.sort()
    first_start = parsed_start_date or parsed[0]
    last_date = parsed[-1]
    first_date = parsed[0]

    if direction == 'forward':
        packets, phase1_warnings = _build_packets_phase1(
            parsed, packet_size, first_start, last_date, tolerance_percent, start_granularity, direction
        )
    else:
        last_start = parsed_end_date or last_date
        packets, phase1_warnings = _build_packets_phase1(
            parsed, packet_size, first_date, last_start, tolerance_percent, start_granularity, direction
        )
    warnings.extend(phase1_warnings)

    # _build_packets_phase1 returns packets in BUILD order - chronological
    # already for 'forward', but newest-to-oldest for 'backward'. Reverse to
    # chronological order NOW, before Phase 2, since _regroup_severely_off's
    # combined-span math (bisecting sorted_dates using packets[window_start]
    # ['from']..packets[window_end]['to']) requires ascending date order to
    # make sense - it isn't just about which end of the list is "last".
    if direction == 'backward':
        packets.reverse()

    packets = _regroup_severely_off(
        packets, parsed, packet_size, tolerance_percent, warnings,
        leftover_at_start=(direction == 'backward')
    )

    # The edge of the packet list furthest from where building started is
    # forced to the true edge of the data (or the given start_date/end_date,
    # if one was given) - not left as whatever calendar boundary the
    # packetization tier happened to land on, which can extend past the
    # true last record (forward mode) or before the true first record
    # (backward mode) - e.g. a month-end boundary chosen for a packet whose
    # real data actually stops mid-month, as in a 2026-07-31 boundary vs. a
    # true last record of 2026-07-13. The list is chronological by now, so
    # 'forward' overrides the LAST (most recent) packet's 'to', and
    # 'backward' overrides the FIRST (oldest) packet's 'from'.
    if packets:
        if direction == 'forward':
            packets[-1]['to'] = parsed_end_date if parsed_end_date else last_date
        else:
            packets[0]['from'] = parsed_start_date if parsed_start_date else first_date

    # The list has been chronological since before Phase 2 (a correctness
    # requirement for its span math, and for the edge override just above -
    # neither of those cares about the OUTPUT row order). Now that both are
    # done, flip backward mode's report to read newest-to-oldest, matching
    # the order packets were actually built in - forward mode's output was
    # already chronological in build order, so it needs no equivalent flip.
    if direction == 'backward':
        packets.reverse()

    rows = []
    for p in packets:
        rows.append({
            "From Date": _format_date_output(p['from']),
            "To Date": _format_date_output(p['to']),
            "No. of Files": _format_count_output(p['count']),
        })
    df_out = pd.DataFrame(rows)

    output_dir = os.path.dirname(input_file_path)
    base_name = os.path.splitext(os.path.basename(input_file_path))[0]
    output_target = os.path.join(output_dir, f"{base_name}_PACKETS.xlsx")
    safe_filepath = _get_unique_filename(output_target)

    df_out.to_excel(safe_filepath, index=False, header=True)

    return safe_filepath, warnings


if __name__ == '__main__':
    loc = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'TestDatesFile.txt')
    path, warns = run_packet_generation(loc, 70000, 20)
    print(path)
    for w in warns:
        print("WARNING:", w)
