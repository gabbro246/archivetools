import os
import shutil
import argparse

def flatten_folder(root_folder):
    if not os.path.isdir(root_folder):
        print(f"Error: The specified path '{root_folder}' is not a directory.")
        return

    for subdir in os.listdir(root_folder):
        subdir_path = os.path.join(root_folder, subdir)
        
        if os.path.isdir(subdir_path):  # Ensure it's a directory
            for item in os.listdir(subdir_path):
                item_path = os.path.join(subdir_path, item)
                target_path = os.path.join(root_folder, item)
                
                if os.path.exists(target_path):
                    print(f"Skipping '{item}' due to naming conflict.")
                    continue
                
                try:
                    shutil.move(item_path, root_folder)
                    print(f"Moved '{item}' to '{root_folder}'")
                except Exception as e:
                    print(f"Error moving '{item}': {e}")
            
            # Check if the directory is really empty before trying to delete
            if not os.listdir(subdir_path):
                try:
                    os.rmdir(subdir_path)
                    print(f"Removed empty folder '{subdir_path}'")
                except Exception as e:
                    print(f"Could not remove folder '{subdir_path}': {e}")
            else:
                print(f"Skipping deletion: '{subdir_path}' is not empty.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flatten folder structure by moving files one level up.")
    parser.add_argument("-f", "--folder", required=True, help="Path to the folder to be flattened.")
    
    args = parser.parse_args()
    flatten_folder(args.folder)
