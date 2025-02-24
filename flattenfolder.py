import os
import shutil
import argparse

def get_new_name(base, extension, target_folder):
    counter = 1
    new_name = f"{base}({counter}){extension}"
    while os.path.exists(os.path.join(target_folder, new_name)):
        counter += 1
        new_name = f"{base}({counter}){extension}"
    return new_name

def flatten_folder(root_folder, rename_files, depth=None):
    if not os.path.isdir(root_folder):
        print(f"Error: The specified path '{root_folder}' is not a directory.")
        return

    current_depth = 0
    while True:
        any_folder_found = False
        for subdir in os.listdir(root_folder):
            subdir_path = os.path.join(root_folder, subdir)
            
            if os.path.isdir(subdir_path):
                any_folder_found = True
                for item in os.listdir(subdir_path):
                    item_path = os.path.join(subdir_path, item)
                    target_path = os.path.join(root_folder, item)
                    
                    if os.path.exists(target_path):
                        if rename_files:
                            base, extension = os.path.splitext(item)
                            new_name = get_new_name(base, extension, root_folder)
                            target_path = os.path.join(root_folder, new_name)
                            print(f"Renaming '{item}' to '{new_name}' to avoid conflict.")
                        else:
                            print(f"Skipping '{item}' due to naming conflict.")
                            continue
                    
                    try:
                        shutil.move(item_path, target_path)
                        print(f"Moved '{item}' to '{root_folder}'")
                    except Exception as e:
                        print(f"Error moving '{item}': {e}")
                
                if not os.listdir(subdir_path):
                    try:
                        os.rmdir(subdir_path)
                        print(f"Removed empty folder '{subdir_path}'")
                    except Exception as e:
                        print(f"Could not remove folder '{subdir_path}': {e}")
                else:
                    print(f"Skipping deletion: '{subdir_path}' is not empty.")

        current_depth += 1
        if not any_folder_found or (depth is not None and current_depth >= depth):
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flatten folder structure by moving files up a specified depth.")
    parser.add_argument("-f", "--folder", required=True, help="Path to the folder to be flattened.")
    parser.add_argument("-r", "--rename", action="store_true", help="Rename files to resolve naming conflicts instead of skipping them.")
    parser.add_argument("-d", "--depth", type=int, help="Depth to flatten. If not provided, flattens all levels.")
    
    args = parser.parse_args()
    flatten_folder(args.folder, args.rename, args.depth)
