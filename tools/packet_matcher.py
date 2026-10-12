"""
Builds a B packet list from an existing A packet list (the .xlsx report written
by packet_generator.py) and a raw file of B dates or timestamps.

The date ranges are taken verbatim from the A list; only the record counts are
recomputed, from the B data. No sizing or tolerance logic is involved.

Input A: the *_PACKETS.xlsx report (columns "From Date" / "To Date", dates as
DD.MM.YYYY text). The "No. of Files" column is ignored.
Input B: a .txt file with ONE date or timestamp per line, in any format the
Packet Generator supports (auto-detected independently of A's format).

Output: an .xlsx report (From Date / To Date / No. of Files) written next to
the B file, in the same layout as the Packet Generator's report.

Public entry point: run_packet_matching(...)
"""

import os
import bisect
import pandas as pd
from datetime import timedelta

from tools.packet_generator import (
    _read_raw_date_column,
    _sniff_datetime_format,
    _parse_with_candidate,
    _parse_single_date,
    _get_unique_filename,
    _format_date_output,
    _format_count_output,
)


def _parse_a_date(value):
    """Parses one A-list cell. Excel may have turned the text dates into real
    date cells (read back as 'YYYY-MM-DD 00:00:00'), so a trailing time is dropped."""
    s = str(value).strip()
    if len(s) > 10 and s[4] == '-' and s[7] == '-' and s[10] in (' ', 'T'):
        s = s[:10]
    return _parse_single_date(s)


def _read_a_ranges(a_list_path):
    """
    Reads the A list. Returns (ranges, descending): the (from_date, to_date)
    pairs sorted chronologically, and whether the sheet itself lists them
    newest-first (which is how the Packet Generator writes a backward-built
    report), so the output can follow the same row order.
    """
    if not a_list_path.lower().endswith('.xlsx'):
        raise ValueError("The A list must be an .xlsx packet report.")

    df = pd.read_excel(a_list_path, engine="openpyxl", dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    for col in ("From Date", "To Date"):
        if col not in df.columns:
            raise ValueError(
                f"The A list has no '{col}' column. Expected a packet report with the "
                f"columns 'From Date', 'To Date' and 'No. of Files'."
            )

    ranges = []
    for i, (f, t) in enumerate(zip(df["From Date"], df["To Date"]), start=2):
        if pd.isna(f) or pd.isna(t):
            continue
        try:
            fd, td = _parse_a_date(f), _parse_a_date(t)
        except ValueError as e:
            raise ValueError(f"A list, spreadsheet row {i}: {e}")
        if td < fd:
            raise ValueError(
                f"A list, spreadsheet row {i}: 'To Date' ({_format_date_output(td)}) is "
                f"before 'From Date' ({_format_date_output(fd)})."
            )
        ranges.append((fd, td))

    if not ranges:
        raise ValueError("The A list contains no packets.")

    descending = len(ranges) > 1 and all(a[0] > b[0] for a, b in zip(ranges, ranges[1:]))
    ranges.sort()

    for (pf, pt), (nf, nt) in zip(ranges, ranges[1:]):
        if nf <= pt:
            raise ValueError(
                f"The A list has overlapping packets "
                f"({_format_date_output(pf)} - {_format_date_output(pt)} and "
                f"{_format_date_output(nf)} - {_format_date_output(nt)})."
            )
    return ranges, descending


def run_packet_matching(a_list_path, b_raw_path, out_of_range='extend',
                        sample_timestamp=None, sample_timestamp_date=None):
    """
    Counts the B records falling into each date range of the A list. The A
    list may be in either order (oldest-first, or newest-first as written by
    a backward Packet Generator run); the output uses the same row order.

    Parameters
    ----------
    a_list_path : str
        Packet Generator .xlsx report (the A list).
    b_raw_path : str
        .txt file, one date or timestamp per line (B_Raw).
    out_of_range : 'extend' (default) or 'extra_packets'
        What to do with B dates before the first A range or after the last one.
        'extend'        - count early dates in the first packet and late dates in
                          the last packet; the A dates are printed unchanged.
        'extra_packets' - add a leading and/or trailing packet covering the
                          uncovered B dates, so every A packet stays exact.
    sample_timestamp, sample_timestamp_date : str, optional
        One real raw value from B_Raw plus the date it represents, to resolve an
        unrecognised or ambiguous format. Must be given together or not at all.

    Returns
    -------
    (saved_path, warnings) : tuple
        saved_path : str - path to the generated .xlsx report.
        warnings : list[str]
    """
    warnings = []

    if out_of_range not in ('extend', 'extra_packets'):
        raise ValueError(f"out_of_range must be 'extend' or 'extra_packets', got {out_of_range!r}")
    if (sample_timestamp is None) != (sample_timestamp_date is None):
        raise ValueError("sample_timestamp and sample_timestamp_date must be given together, or neither.")

    ranges, descending = _read_a_ranges(a_list_path)

    raw_values = _read_raw_date_column(b_raw_path)
    if not raw_values:
        raise ValueError("The selected B file is empty.")

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
            f"Skipped {skipped:,} row(s) of the B file that could not be parsed under the "
            f"detected format ({date_fmt}) - likely a header label."
        )
    if not parsed:
        raise ValueError("No valid dates could be parsed from the B file.")

    parsed.sort()
    first_from, last_to = ranges[0][0], ranges[-1][1]

    # Count per A range (both ends inclusive).
    rows = []
    for fd, td in ranges:
        n = bisect.bisect_right(parsed, td) - bisect.bisect_left(parsed, fd)
        rows.append([fd, td, n])

    before = bisect.bisect_left(parsed, first_from)
    after = len(parsed) - bisect.bisect_right(parsed, last_to)

    if before:
        if out_of_range == 'extend':
            rows[0][2] += before
            warnings.append(
                f"{before:,} B record(s) are dated before the A list's first From Date "
                f"({_format_date_output(first_from)}); they were counted in the first packet."
            )
        else:
            rows.insert(0, [parsed[0], first_from - timedelta(days=1), before])
            warnings.append(
                f"{before:,} B record(s) are dated before the A list's first From Date "
                f"({_format_date_output(first_from)}); an extra packet was added at the start."
            )
    if after:
        if out_of_range == 'extend':
            rows[-1][2] += after
            warnings.append(
                f"{after:,} B record(s) are dated after the A list's last To Date "
                f"({_format_date_output(last_to)}); they were counted in the last packet."
            )
        else:
            rows.append([last_to + timedelta(days=1), parsed[-1], after])
            warnings.append(
                f"{after:,} B record(s) are dated after the A list's last To Date "
                f"({_format_date_output(last_to)}); an extra packet was added at the end."
            )

    # B records sitting in gaps between two A packets belong to no packet.
    covered = sum(bisect.bisect_right(parsed, td) - bisect.bisect_left(parsed, fd) for fd, td in ranges)
    in_gaps = len(parsed) - before - after - covered
    if in_gaps:
        warnings.append(
            f"{in_gaps:,} B record(s) fall into gaps between A packets and are not counted in any packet."
        )

    # Follow A's own row order: a newest-first A list gives a newest-first B list.
    if descending:
        rows.reverse()

    out_rows = [
        {
            "From Date": _format_date_output(fd),
            "To Date": _format_date_output(td),
            "No. of Files": _format_count_output(n),
        }
        for fd, td, n in rows
    ]

    base = os.path.splitext(os.path.basename(b_raw_path))[0]
    out_path = _get_unique_filename(
        os.path.join(os.path.dirname(b_raw_path), f"{base}_PACKETS.xlsx")
    )
    pd.DataFrame(out_rows).to_excel(out_path, index=False, header=True)
    return out_path, warnings
