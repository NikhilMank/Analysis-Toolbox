import pandas as pd
import os

def run_difference_analysis(file_a_path, file_b_path):
    """
    Core engine comparing File A and File B.
    Dynamically outputs files next to File A.
    Returns a tuple of the actual generated output paths (or None if empty).
    """
    # Dynamically set output paths to live right next to File A
    output_dir = os.path.dirname(file_a_path)
    output_a_target = os.path.join(output_dir, 'Missing_From_B.xlsx')
    output_b_target = os.path.join(output_dir, 'Missing_From_A.xlsx')

    print("Reading files...")

    # 1. Helper function to load the first column regardless of its name
    def load_first_column(filepath):
        ext = filepath.lower()
        try:
            if ext.endswith('.csv'):
                try:
                    return pd.read_csv(filepath, header=None, usecols=[0], dtype=str, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    return pd.read_csv(filepath, header=None, usecols=[0], dtype=str, encoding='latin1')
            elif ext.endswith('.xlsx'):
                return pd.read_excel(filepath, engine='openpyxl', header=None, usecols=[0], dtype=str)
            elif ext.endswith('.txt'):
                try:
                    encoding = 'utf-8-sig'
                    with open(filepath, encoding=encoding) as f:
                        return pd.DataFrame(f.read().splitlines())
                except UnicodeDecodeError:
                    encoding = 'latin1'
                    with open(filepath, encoding=encoding) as f:
                        return pd.DataFrame(f.read().splitlines())
            else:
                raise ValueError(f"Unsupported file type for {filepath}")
        except Exception as e:
            print(f"\nError reading {filepath}. Ensure the file is not corrupted or open in another program.")
            raise e

    # 2. Helper function to generate a unique filename so we never overwrite
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

    # 3. Helper function to save a single report (skips if empty)
    def save_report(data, list_name, filepath):
        if len(data) == 0:
            print(f"-> No differences found for '{list_name}'. Skipping file creation.")
            return None
        
        df = pd.DataFrame({"Document ID": data})
        ext = filepath.lower()

        # Excel Safety Check (forces to CSV if it exceeds 1.04M rows)
        if len(df) > 1048500 and ext.endswith('.xlsx'):
            print("\n⚠️ WARNING: The differences exceed Excel's 1,048,576 row limit!")
            filepath = filepath.replace('.xlsx', '.csv')
            ext = '.csv'
            print("Forcing format to CSV to prevent data loss.")

        # Get a safe, unique filename right before saving
        safe_filepath = get_unique_filename(filepath)
        print(f"-> Saving {len(data):,} rows to '{safe_filepath}'...")

        # Save the file using the safe name
        if ext.endswith('.xlsx'):
            df.to_excel(safe_filepath, index=False)
        elif ext.endswith('.csv'):
            df.to_csv(safe_filepath, index=False)
        elif ext.endswith('.txt'):
            df.to_csv(safe_filepath, index=False, header=False)
            
        return safe_filepath

    # Load the first column from each file
    df_a = load_first_column(file_a_path)
    df_b = load_first_column(file_b_path)

    # Clean data (pandas assigns the number 0 as the column name when header=None)
    ids_a = df_a[0].dropna().astype(str).str.strip().str.upper()
    ids_b = df_b[0].dropna().astype(str).str.strip().str.upper()

    # File comparison
    only_in_a = ids_a[~ids_a.isin(ids_b)]
    only_in_b = ids_b[~ids_b.isin(ids_a)]

    # Process and save the reports independently, keeping track of actual saved filenames
    saved_a_path = save_report(only_in_a, "File A", output_a_target)
    saved_b_path = save_report(only_in_b, "File B", output_b_target)

    # Return the file names to the UI so we can display them in the popup
    return saved_a_path, saved_b_path

if __name__ == '__main__':
    loc_a = '/Users/an0045/Desktop/PythonPrograms/data/BASF_PM01_DOCS.XLSX'
    loc_b = '/Users/an0045/Desktop/PythonPrograms/data/BASF_PM01_MIG.XLSX'
    run_difference_analysis(loc_a, loc_b)