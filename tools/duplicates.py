import pandas as pd
import os
import csv

def run_duplicate_analysis(input_file_path, has_header=False):
    """
    Finds duplicate rows in a file (matching is whitespace-insensitive,
    case-sensitive, and considers the ENTIRE row - same rules as
    run_difference_analysis).
    Saves a cleaned version next to the original, keeping the FIRST
    occurrence's original (unstripped) values.
    Saves an aggregated "offenders list" showing duplicate counts.
    CSV output reuses the delimiter detected on the input CSV, instead of
    always defaulting to a comma.
    Returns (cleaned_file_path, duplicates_file_path_or_None)

    Parameters
    ----------
    has_header : bool
        Set True if your CSV/XLSX/TXT file has a header row. Default is
        False. If your file DOES have a header and this stays False, the
        header row gets treated as data. If your file does NOT have a
        header and this is left True (or omitted with the old pandas
        default), the first row of real data gets silently treated as
        column labels and is dropped from the results.
    """
    # 1. Dynamically build output paths to live next to the input file
    output_dir = os.path.dirname(input_file_path)
    base_name = os.path.basename(input_file_path)
    file_no_ext, ext = os.path.splitext(base_name)
    
    # FORCE the extension to lowercase to bypass the Pandas case-sensitivity bug
    ext_lower = ext.lower()
    
    output_clean_target = os.path.join(output_dir, f"{file_no_ext}_CLEANED{ext_lower}")
    output_duplicates_target = os.path.join(output_dir, f"{file_no_ext}_DUPLICATES_LOG{ext_lower}")

    print("Initializing file reader...")

    # Sniff the delimiter instead of assuming a comma - SAP exports are
    # frequently semicolon-delimited. Reused later so the OUTPUT uses the
    # same delimiter as the INPUT.
    def sniff_delimiter(filepath, encoding):
        with open(filepath, encoding=encoding) as f:
            sample = f.read(4096)
        try:
            return csv.Sniffer().sniff(sample, delimiters=[',', ';', '\t', '|']).delimiter
        except csv.Error:
            return ','  # sensible fallback

    # Helper function to load CSV or Excel safely
    def load_data(filepath):
        """Returns (dataframe, delimiter_or_None). Delimiter is only
        meaningful for .csv - None for .xlsx/.txt."""
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

            elif ext_lower_check.endswith(".txt"):
                try:
                    encoding = "utf-8-sig"
                    with open(filepath, encoding=encoding) as f:
                        lines = [line.rstrip("\r\n") for line in f]
                except UnicodeDecodeError:
                    with open(filepath, encoding="latin1") as f:
                        lines = [line.rstrip("\r\n") for line in f]

                if has_header and lines:
                    lines = lines[1:]
                return pd.DataFrame(lines, columns=["Raw Line Entry"]), None

            else:
                raise ValueError(f"Unsupported file type for {filepath}")

        except Exception as e:
            print(f"\nError reading {filepath}. Ensure the file is not corrupted or open in another program.")
            raise

    # Helper function to generate a unique filename so we never overwrite
    def get_unique_filename(filepath):
        if not os.path.exists(filepath):
            return filepath
        
        b_name, extension = os.path.splitext(filepath)
        extension_lower = extension.lower() # Double-safety
        counter = 1
        new_filepath = f"{b_name}_{counter}{extension_lower}"
        while os.path.exists(new_filepath):
            counter += 1
            new_filepath = f"{b_name}_{counter}{extension_lower}"
        return new_filepath

    # Helper function to save files safely
    def save_file(df, filepath, delimiter=None):
        # Force incoming target paths to be lowercase
        b_name, extension = os.path.splitext(filepath)
        filepath_lower = f"{b_name}{extension.lower()}"
        
        safe_filepath = get_unique_filename(filepath_lower)
        ext_lower_check = safe_filepath.lower()
        sep = delimiter or ','
        # The duplicates log always needs its column labels (Total
        # Occurrences etc.) to be readable, regardless of has_header.
        is_log = "DUPLICATES_LOG" in safe_filepath
        
        print(f"-> Saving {len(df):,} rows to '{safe_filepath}'...")
        if ext_lower_check.endswith('.xlsx'):
            df.to_excel(safe_filepath, index=False, engine='openpyxl',
                        header=True if is_log else has_header)
        elif ext_lower_check.endswith('.csv'):
            df.to_csv(safe_filepath, index=False, sep=sep,
                       header=True if is_log else has_header)
        elif ext_lower_check.endswith('.txt'):
            if is_log:
                # This is a derived, structured report (adds count columns)
                # not a reproduction of the original file - a real
                # delimited/quoted CSV-style write is correct here.
                df.columns = ['Raw Line Entry', 'Total Occurrences', 'Duplicate Count (Repeated Times)']
                df.to_csv(safe_filepath, index=False, sep=';', header=True, encoding='utf-8-sig')
            else:
                # This is meant to be a faithful reproduction of the
                # original raw text lines, which were read WITHOUT any
                # delimiter parsing. Writing it via to_csv would apply CSV
                # quoting/escaping (e.g. wrapping a line containing a comma
                # in quotes) and silently corrupt content that was never
                # actually delimited data.
                with open(safe_filepath, 'w', encoding='utf-8') as f:
                    for line in df.iloc[:, 0]:
                        f.write(f"{line}\n")
                
        return safe_filepath

    # Build a normalized comparison key per row - whitespace-stripped,
    # case preserved - used ONLY for matching. The output keeps the
    # original, unstripped values of the first occurrence in each group.
    def build_comparison_key(df):
        df_norm = df.fillna('').astype(str).apply(lambda col: col.str.strip())
        return df_norm.agg('\x1f'.join, axis=1)

    # Load the source data
    df_all, detected_sep = load_data(input_file_path)
    total_rows = len(df_all)

    if total_rows == 0:
        raise ValueError("The selected input file is empty.")

    print("Analyzing dataset and calculating occurrence counts...")
    
    # Get all original column names
    all_cols = list(df_all.columns)

    df_all = df_all.reset_index(drop=True)
    df_all['_key'] = build_comparison_key(df_all)

    # Occurrence counts per normalized key
    counts = df_all['_key'].value_counts(dropna=False).reset_index()
    counts.columns = ['_key', 'Total Occurrences']

    # Keep the literal FIRST full row per key (not a per-column first
    # non-null, which could mix fields from different actual rows).
    df_first = df_all.drop_duplicates(subset='_key', keep='first')

    df_grouped = df_first.merge(counts, on='_key', how='left').drop(columns='_key')

    # 1. Cleaned Data: Keep only unique rows (original, unstripped values)
    df_clean = df_grouped[all_cols]
    
    # 2. Duplicate Log: Keep only rows that appeared more than once
    df_duplicates = df_grouped[df_grouped['Total Occurrences'] > 1].copy()
    
    # Calculate exactly how many extra "repeated" copies were removed
    df_duplicates['Duplicate Count (Repeated Times)'] = df_duplicates['Total Occurrences'] - 1
    
    # Sort so the heaviest duplicates appear at the top
    df_duplicates = df_duplicates.sort_values(by='Total Occurrences', ascending=False)
    df_duplicates = df_duplicates[all_cols + ['Total Occurrences', 'Duplicate Count (Repeated Times)']]

    # Save the cleaned file (CSV output reuses the detected input delimiter)
    saved_clean_path = save_file(df_clean, output_clean_target, detected_sep)
    
    # Save duplicate log only if duplicates were found
    saved_duplicates_path = None
    if len(df_duplicates) > 0:
        saved_duplicates_path = save_file(df_duplicates, output_duplicates_target, detected_sep)

    return saved_clean_path, saved_duplicates_path

if __name__ == '__main__':
    loc = '/Users/an0045/Desktop/PythonPrograms/data/BUS0010_BUS0010_2CFL_P1.txt'
    run_duplicate_analysis(loc)