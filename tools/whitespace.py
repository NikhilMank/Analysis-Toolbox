import pandas as pd
import os
import csv


def run_whitespace_cleanup(input_file_path, has_header=False):
    """
    Strips leading/trailing whitespace from every cell entry in a CSV or
    XLSX file. Internal whitespace is left untouched; only whitespace at
    the very start/end of each entry is removed.

    Saves a new file next to the original, in the SAME format and
    delimiter as the input - the original file is never modified. If
    nothing needed trimming, no output file is created.

    Returns (saved_path_or_None, cells_trimmed_count)

    Parameters
    ----------
    has_header : bool
        Set True if your file has a header row. Default is False. Header
        labels get trimmed (and counted) too if True, since trailing
        whitespace in a header can cause silent mismatches in the
        Difference/Duplicate tools that key off it.
    """
    output_dir = os.path.dirname(input_file_path)
    base_name = os.path.basename(input_file_path)
    file_no_ext, ext = os.path.splitext(base_name)
    ext_lower = ext.lower()

    output_target = os.path.join(output_dir, f"{file_no_ext}_TRIMMED{ext_lower}")

    print("Reading file...")

    # Sniff the delimiter instead of assuming a comma - SAP exports are
    # frequently semicolon-delimited. Reused so the OUTPUT uses the same
    # delimiter as the INPUT.
    def sniff_delimiter(filepath, encoding):
        with open(filepath, encoding=encoding) as f:
            sample = f.read(4096)
        try:
            return csv.Sniffer().sniff(sample, delimiters=[',', ';', '\t', '|']).delimiter
        except csv.Error:
            return ','  # sensible fallback

    def load_data(filepath):
        """Returns (dataframe, delimiter_or_None). Delimiter is only
        meaningful for .csv - None for .xlsx."""
        ext_lower_check = filepath.lower()
        header_arg = 0 if has_header else None

        try:
            if ext_lower_check.endswith(".csv"):
                for encoding in ("utf-8-sig", "latin1"):
                    try:
                        sep = sniff_delimiter(filepath, encoding)
                        df = pd.read_csv(filepath, header=header_arg, dtype=str,
                                          encoding=encoding, sep=sep)
                        return df, sep
                    except UnicodeDecodeError:
                        continue
                raise UnicodeDecodeError('csv', b'', 0, 1, 'Could not decode with utf-8-sig or latin1')

            elif ext_lower_check.endswith(".xlsx"):
                df = pd.read_excel(filepath, engine="openpyxl", header=header_arg, dtype=str)
                return df, None

            else:
                raise ValueError(f"Unsupported file type for {filepath}. This tool supports .csv and .xlsx only.")

        except Exception as e:
            print(f"\nError reading {filepath}. Ensure the file is not corrupted or open in another program.")
            raise

    def get_unique_filename(filepath):
        if not os.path.exists(filepath):
            return filepath
        b_name, extension = os.path.splitext(filepath)
        counter = 1
        new_filepath = f"{b_name}_{counter}{extension}"
        while os.path.exists(new_filepath):
            counter += 1
            new_filepath = f"{b_name}_{counter}{extension}"
        return new_filepath

    # Load the source data
    df, delimiter = load_data(input_file_path)

    if len(df) == 0:
        raise ValueError("The selected input file is empty.")

    print("Scanning cells for leading/trailing whitespace...")

    cells_trimmed = 0

    def strip_cell(value):
        nonlocal cells_trimmed
        if isinstance(value, str):
            stripped = value.strip()
            if stripped != value:
                cells_trimmed += 1
            return stripped
        return value  # leave real NaN / missing values untouched

    # Trim every cell (for TXT this is every line, since it's a single column)
    for col in df.columns:
        df[col] = df[col].apply(strip_cell)

    # Also trim header labels themselves - trailing whitespace there is a
    # common source of silent mismatches downstream.
    if has_header:
        new_columns = []
        for c in df.columns:
            if isinstance(c, str):
                stripped_c = c.strip()
                if stripped_c != c:
                    cells_trimmed += 1
                new_columns.append(stripped_c)
            else:
                new_columns.append(c)
        df.columns = new_columns

    if cells_trimmed == 0:
        print("-> No leading/trailing whitespace found. Nothing to clean.")
        return None, 0

    sep = delimiter or ','
    safe_filepath = get_unique_filename(output_target)
    entry_word = "entry" if cells_trimmed == 1 else "entries"
    print(f"-> Trimmed {cells_trimmed:,} {entry_word}. Saving to '{safe_filepath}'...")

    ext_check = safe_filepath.lower()
    if ext_check.endswith('.xlsx'):
        df.to_excel(safe_filepath, index=False, header=has_header)
    elif ext_check.endswith('.csv'):
        df.to_csv(safe_filepath, index=False, sep=sep, header=has_header)

    return safe_filepath, cells_trimmed


if __name__ == '__main__':
    loc = '/Users/an0045/Desktop/PythonPrograms/data/BASF_PM01_DOCS.XLSX'
    run_whitespace_cleanup(loc)