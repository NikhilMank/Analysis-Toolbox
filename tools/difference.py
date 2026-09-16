import pandas as pd
import os
import csv


def run_difference_analysis(file_a_path, file_b_path, has_header=False):
    """
    Core engine comparing File A and File B by COMPLETE ROW (all columns).
    Two rows are considered "the same" only if every column matches exactly
    (after stripping whitespace - case is preserved and treated as
    significant).

    Output format mirrors the INPUT format: rows unique to File A are saved
    using File A's file type and delimiter, rows unique to File B are saved
    using File B's file type and delimiter. Both outputs are written next to
    File A.

    Returns (saved_a_path, count_a, saved_b_path, count_b) - each path is
    None if that side had no reportable differences (in which case its
    count is 0), and each count is the number of entries in that output
    file, since a .txt file's row count isn't visible at a glance the way
    it is when opening the .xlsx/.csv output in Excel.

    Parameters
    ----------
    has_header : bool
        Set True if your CSV/XLSX/TXT files have a header row. Default is
        False to match the original script's behavior. If your files DO
        have headers and this stays False, the header row itself gets
        treated as a data row and may incorrectly show up as a "difference".
    """
    output_dir = os.path.dirname(file_a_path)

    print("Reading files...")

    # Sniff the delimiter instead of assuming a comma - SAP exports are
    # frequently semicolon-delimited. Reused later so the OUTPUT uses the
    # same delimiter as the corresponding INPUT file.
    def sniff_delimiter(filepath, encoding):
        with open(filepath, encoding=encoding) as f:
            sample = f.read(4096)
        try:
            return csv.Sniffer().sniff(sample, delimiters=[',', ';', '\t', '|']).delimiter
        except csv.Error:
            return ','  # sensible fallback

    def load_full_rows(filepath):
        """Returns (dataframe, delimiter_or_None). Delimiter is only
        meaningful for .csv - None for .xlsx/.txt."""
        ext = filepath.lower()
        header_arg = 0 if has_header else None

        try:
            if ext.endswith('.csv'):
                for encoding in ('utf-8-sig', 'latin1'):
                    try:
                        sep = sniff_delimiter(filepath, encoding)
                        df = pd.read_csv(filepath, header=header_arg, dtype=str,
                                          encoding=encoding, sep=sep)
                        return df, sep
                    except UnicodeDecodeError:
                        continue
                raise UnicodeDecodeError('csv', b'', 0, 1, 'Could not decode with utf-8-sig or latin1')

            elif ext.endswith('.xlsx'):
                df = pd.read_excel(filepath, engine='openpyxl', header=header_arg, dtype=str)
                return df, None

            elif ext.endswith('.txt'):
                try:
                    encoding = 'utf-8-sig'
                    with open(filepath, encoding=encoding) as f:
                        lines = f.read().splitlines()
                except UnicodeDecodeError:
                    encoding = 'latin1'
                    with open(filepath, encoding=encoding) as f:
                        lines = f.read().splitlines()
                if has_header and lines:
                    lines = lines[1:]
                return pd.DataFrame(lines), None

            else:
                raise ValueError(f"Unsupported file type for {filepath}")

        except Exception as e:
            print(f"\nError reading {filepath}. Ensure the file is not corrupted or open in another program.")
            raise e

    def get_unique_filename(filepath):
        if not os.path.exists(filepath):
            return filepath
        base_name, extension = os.path.splitext(filepath)
        counter = 1
        new_filepath = f"{base_name}_{counter}{extension}"
        while os.path.exists(new_filepath):
            counter += 1
            new_filepath = f"{base_name}_{counter}{extension}"
        return new_filepath

    def save_report(df_rows, list_name, filepath, delimiter):
        # Same whitespace-stripped-is-insignificant standard the comparison
        # already applies in build_comparison_key() - a diff that survives
        # only as blank/whitespace content (e.g. a stray trailing blank line
        # present in one .txt file but not the other) isn't a real
        # difference worth a file, and for .txt in particular a single blank
        # line is visually indistinguishable from a truly empty file.
        is_blank_only = df_rows.fillna('').astype(str).apply(
            lambda col: col.str.strip()).eq('').all(axis=None)
        if len(df_rows) == 0 or is_blank_only:
            print(f"-> No differences found for '{list_name}'. Skipping file creation.")
            return None, 0

        ext = filepath.lower()
        sep = delimiter or ','

        if len(df_rows) > 1048500 and ext.endswith('.xlsx'):
            print("\n⚠️ WARNING: The differences exceed Excel's 1,048,576 row limit!")
            filepath = filepath.replace('.xlsx', '.csv')
            ext = '.csv'
            print("Forcing format to CSV to prevent data loss.")

        safe_filepath = get_unique_filename(filepath)
        print(f"-> Saving {len(df_rows):,} rows to '{safe_filepath}'...")

        if ext.endswith('.xlsx'):
            df_rows.to_excel(safe_filepath, index=False, header=has_header)
        elif ext.endswith('.csv'):
            df_rows.to_csv(safe_filepath, index=False, header=has_header, sep=sep)
        elif ext.endswith('.txt'):
            # TXT was read as raw, unparsed lines (no delimiter splitting),
            # so it must be written back the same way - plain text, no CSV
            # quoting/escaping. to_csv would wrap lines containing a comma
            # or quote character in quotes, altering content that was never
            # actually delimited data to begin with.
            with open(safe_filepath, 'w', encoding='utf-8') as f:
                for line in df_rows.iloc[:, 0]:
                    f.write(f"{line}\n")

        return safe_filepath, len(df_rows)

    # Build a normalized comparison key per row - used ONLY for matching,
    # never written to the output. The output keeps the original values.
    def build_comparison_key(df):
        df_norm = df.fillna('').astype(str).apply(lambda col: col.str.strip())
        return df_norm.agg('\x1f'.join, axis=1)

    df_a, sep_a = load_full_rows(file_a_path)
    df_b, sep_b = load_full_rows(file_b_path)

    if df_a.shape[1] != df_b.shape[1]:
        print(f"\n⚠️ WARNING: File A has {df_a.shape[1]} column(s) but File B has "
              f"{df_b.shape[1]} column(s). Full-row comparison assumes matching "
              f"column structure - results may not be meaningful.")

    key_a = build_comparison_key(df_a)
    key_b = build_comparison_key(df_b)

    only_in_a = df_a[~key_a.isin(key_b)]
    only_in_b = df_b[~key_b.isin(key_a)]

    # Rows unique to A came FROM File A, so they're saved in File A's format.
    # Rows unique to B came FROM File B, so they're saved in File B's format.
    ext_a = os.path.splitext(file_a_path)[1].lower() or '.xlsx'
    ext_b = os.path.splitext(file_b_path)[1].lower() or '.xlsx'
    output_a_target = os.path.join(output_dir, f'Missing_From_B{ext_a}')
    output_b_target = os.path.join(output_dir, f'Missing_From_A{ext_b}')

    saved_a_path, count_a = save_report(only_in_a, "File A", output_a_target, sep_a)
    saved_b_path, count_b = save_report(only_in_b, "File B", output_b_target, sep_b)

    return saved_a_path, count_a, saved_b_path, count_b


if __name__ == '__main__':
    loc_a = '/Users/an0045/Desktop/PythonPrograms/data/BASF_PM01_DOCS.XLSX'
    loc_b = '/Users/an0045/Desktop/PythonPrograms/data/BASF_PM01_MIG.XLSX'
    run_difference_analysis(loc_a, loc_b)