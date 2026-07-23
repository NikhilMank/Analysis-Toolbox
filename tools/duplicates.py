import pandas as pd
import os

# def run_duplicate_analysis(input_file_path):
#     """
#     Finds duplicate rows in a file.
#     Saves a cleaned version and a duplicates log next to the original file.
#     Returns (cleaned_file_path, duplicates_file_path_or_None)
#     """
#     # 1. Dynamically build output paths to live next to the input file
#     output_dir = os.path.dirname(input_file_path)
#     base_name = os.path.basename(input_file_path)
#     file_no_ext, ext = os.path.splitext(base_name)
    
    # # FORCE the extension to lowercase to bypass the Pandas case-sensitivity bug
    # ext_lower = ext.lower()
    # output_clean_target = os.path.join(output_dir, f"{file_no_ext}_CLEANED{ext_lower}")
    # output_duplicates_target = os.path.join(output_dir, f"{file_no_ext}_DUPLICATES_LOG{ext_lower}")


#     print("Initializing file reader...")
    
#     # Helper function to load CSV or Excel files safely
#     def load_data(filepath):
#         ext_lower = filepath.lower()
#         try:
#             if ext_lower.endswith('.csv'):
#                 return pd.read_csv(filepath)
#             elif ext_lower.endswith('.xlsx'):
#                 return pd.read_excel(filepath, engine='openpyxl')
#             elif ext_lower.endswith('.txt'):
#                 return pd.read_csv(filepath, sep=None, engine='python')
#             else:
#                 raise ValueError(f"Unsupported file type for {filepath}")
#         except Exception as e:
#             print(f"\nError reading {filepath}. Ensure the file is not corrupted or open in another program.")
#             raise e

#     # Helper function to generate a unique filename so we never overwrite
#     def get_unique_filename(filepath):
#         if not os.path.exists(filepath):
#             return filepath
        
#         b_name, extension = os.path.splitext(filepath)
#         counter = 1
#         new_filepath = f"{b_name}_{counter}{extension}"
#         while os.path.exists(new_filepath):
#             counter += 1
#             new_filepath = f"{b_name}_{counter}{extension}"
#         return new_filepath

#     # Helper function to save files safely
#     def save_file(df, filepath):
#         safe_filepath = get_unique_filename(filepath)
#         ext_lower = safe_filepath.lower()
        
#         print(f"-> Saving {len(df):,} rows to '{safe_filepath}'...")
#         if ext_lower.endswith('.xlsx'):
#             df.to_excel(safe_filepath, index=False)
#         elif ext_lower.endswith('.csv'):
#             df.to_csv(safe_filepath, index=False)
#         elif ext_lower.endswith('.txt'):
#             df.to_csv(safe_filepath, index=False, sep='\t')
#         return safe_filepath

#     # Load the source data
#     df_all = load_data(input_file_path)
#     total_rows = len(df_all)

#     if total_rows == 0:
#         raise ValueError("The selected input file is empty.")

#     # Flag duplicate rows
#     duplicate_mask = df_all.duplicated(keep='first')
    
#     # Separate datasets
#     df_clean = df_all[~duplicate_mask]
#     df_duplicates = df_all[duplicate_mask]

#     # Save the clean file
#     saved_clean_path = save_file(df_clean, output_clean_target)
    
#     # Save duplicates file ONLY if duplicate rows exist
#     saved_duplicates_path = None
#     if len(df_duplicates) > 0:
#         saved_duplicates_path = save_file(df_duplicates, output_duplicates_target)

#     return saved_clean_path, saved_duplicates_path


def run_duplicate_analysis(input_file_path):
    """
    Finds duplicate rows in a file.
    Saves a cleaned version next to the original.
    Saves an aggregated "offenders list" showing duplicate counts.
    Returns (cleaned_file_path, duplicates_file_path_or_None)
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
    
    # Helper function to load CSV or Excel safely
    def load_data(filepath):
        ext_lower_check = filepath.lower()
        try:
            if ext_lower_check.endswith('.csv'):
                return pd.read_csv(filepath)
            elif ext_lower_check.endswith('.xlsx'):
                return pd.read_excel(filepath, engine='openpyxl')
            elif ext_lower_check.endswith('.txt'):
                #return pd.read_csv(filepath, sep='\n', header=None, dtype=str engine='python')
                try:
                    return pd.read_csv(filepath, sep='\n', header=None, dtype=str, skip_blank_lines=False, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    return pd.read_csv(filepath, sep='\n', header=None, dtype=str, skip_blank_lines=False, encoding='latin1')
            else:
                raise ValueError(f"Unsupported file type for {filepath}")
        except Exception as e:
            print(f"\nError reading {filepath}. Ensure the file is not corrupted or open in another program.")
            raise e

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
    def save_file(df, filepath):
        # Force incoming target paths to be lowercase
        b_name, extension = os.path.splitext(filepath)
        filepath_lower = f"{b_name}{extension.lower()}"
        
        safe_filepath = get_unique_filename(filepath_lower)
        ext_lower_check = safe_filepath.lower()
        
        print(f"-> Saving {len(df):,} rows to '{safe_filepath}'...")
        if ext_lower_check.endswith('.xlsx'):
            df.to_excel(safe_filepath, index=False, engine='openpyxl')
        elif ext_lower_check.endswith('.csv'):
            df.to_csv(safe_filepath, index=False)
        elif ext_lower_check.endswith('.txt'):
            # df.to_csv(safe_filepath, index=False, sep='\t')
            if "DUPLICATES_LOG" in safe_filepath:
                df.columns = ['Raw Line Entry', 'Total Occurrences', 'Duplicate Count (Repeated Times)']
                df.to_csv(safe_filepath, index=False, sep=';', header=True, encoding='utf-8-sig')
            else:
                df.to_csv(safe_filepath, index=False, header=False, encoding='utf-8-sig')
                
        return safe_filepath

    # Load the source data
    df_all = load_data(input_file_path)
    total_rows = len(df_all)

    if total_rows == 0:
        raise ValueError("The selected input file is empty.")

    print("Analyzing dataset and calculating occurrence counts...")
    
    # Get all original column names
    all_cols = list(df_all.columns)
    
    # Group by all columns to find exact row matches and count them
    df_grouped = df_all.groupby(all_cols, dropna=False).size().reset_index(name='Total Occurrences')
    
    # 1. Cleaned Data: Keep only unique rows
    df_clean = df_grouped[all_cols]
    
    # 2. Duplicate Log: Keep only rows that appeared more than once
    df_duplicates = df_grouped[df_grouped['Total Occurrences'] > 1].copy()
    
    # Calculate exactly how many extra "repeated" copies were removed
    df_duplicates['Duplicate Count (Repeated Times)'] = df_duplicates['Total Occurrences'] - 1
    
    # Sort so the heaviest duplicates appear at the top
    df_duplicates = df_duplicates.sort_values(by='Total Occurrences', ascending=False)

    # Save the cleaned file
    saved_clean_path = save_file(df_clean, output_clean_target)
    
    # Save duplicate log only if duplicates were found
    saved_duplicates_path = None
    if len(df_duplicates) > 0:
        saved_duplicates_path = save_file(df_duplicates, output_duplicates_target)

    return saved_clean_path, saved_duplicates_path