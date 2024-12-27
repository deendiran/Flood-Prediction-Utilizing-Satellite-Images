import os
import json
import shutil
import glob
import pandas as pd
from pathlib import Path
import random


def divide_train_validation_dataset(source_images_dir, source_labels_dir, train_dir, validation_dir, num_validation_samples=100):
    """
    Organize dataset into training and validation subsets, ensuring no overlap.
    
    Args:
        source_images_dir: Path to original images directory
        source_labels_dir: Path to original labels directory
        train_dir: Path where training subset will be created
        validation_dir: Path where validation subset will be created
        num_validation_samples: Minimum number of validation samples to select
    """
    # Create directories for the training and validation sets
    train_images_dir = os.path.join(train_dir, 'images')
    train_labels_dir = os.path.join(train_dir, 'labels')
    validation_images_dir = os.path.join(validation_dir, 'images')
    validation_labels_dir = os.path.join(validation_dir, 'labels')
    
    os.makedirs(train_images_dir, exist_ok=True)
    os.makedirs(train_labels_dir, exist_ok=True)
    os.makedirs(validation_images_dir, exist_ok=True)
    os.makedirs(validation_labels_dir, exist_ok=True)
    
    # Dictionary to store matching files and their flood status
    matching_files = {
        's1': [],  # Sentinel-1 matches
        's2': []   # Sentinel-2 matches
    }
    
    # Get all geojson files
    geojson_files = glob.glob(os.path.join(source_labels_dir, '*.geojson'))
    print(f"Found {len(geojson_files)} label files")
    
    # Analyze each label file and find matching images
    for label_file in geojson_files:
        basename = os.path.basename(label_file)
        parts = basename.split('_')
        
        if len(parts) < 6:
            continue
            
        sensor = parts[0]  # s1 or s2
        digit = parts[2]
        date = f"{parts[3]}_{parts[4]}_{parts[5]}"
        
        # Find corresponding image folder
        image_pattern = f"{sensor}_source_{digit}_{date}_*"
        image_search_path = os.path.join(source_images_dir, digit, image_pattern)
        matching_images = glob.glob(image_search_path)
        
        if matching_images:
            # Read geojson to check flood status
            with open(label_file, 'r') as f:
                try:
                    geojson_data = json.load(f)
                    has_flooding = geojson_data.get("properties", {}).get("FLOODING", None)
                    
                    # Normalize flooding property to a boolean
                    if isinstance(has_flooding, str):
                        has_flooding = has_flooding.lower() == "true"
                    elif isinstance(has_flooding, int):
                        has_flooding = bool(has_flooding)
                    
                    # Append matching images and labels
                    matching_files[sensor].append({
                        'label_file': label_file,
                        'image_files': matching_images,
                        'has_flooding': has_flooding
                    })
                except json.JSONDecodeError:
                    print(f"Error reading {label_file}")
                    continue
    
    # Print analysis results
    for sensor in ['s1', 's2']:
        total = len(matching_files[sensor])
        print(f"\n{sensor.upper()} Images:")
        print(f"Total matching pairs: {total}")
    
    # Shuffle and split data into train and validation sets
    train_samples = []
    validation_samples = []
    for sensor in ['s1', 's2']:
        # Shuffle data
        random.shuffle(matching_files[sensor])
        
        # Split validation and training samples
        validation_samples.extend(matching_files[sensor][:num_validation_samples // 2])
        train_samples.extend(matching_files[sensor][num_validation_samples // 2:])
    
    # Copy data to respective directories
    def copy_samples(samples, images_dir, labels_dir):
        for sample in samples:
            # Copy label file
            label_basename = os.path.basename(sample['label_file'])
            shutil.copy2(sample['label_file'], os.path.join(labels_dir, label_basename))
            
            # Copy image files
            for img_file in sample['image_files']:
                img_basename = os.path.basename(img_file)
                img_subdir = os.path.basename(os.path.dirname(img_file))
                
                # Create subdirectory if needed
                img_target_dir = os.path.join(images_dir, img_subdir)
                os.makedirs(img_target_dir, exist_ok=True)
                
                shutil.copy2(img_file, os.path.join(img_target_dir, img_basename))
    
    # Copy training and validation samples
    copy_samples(train_samples, train_images_dir, train_labels_dir)
    copy_samples(validation_samples, validation_images_dir, validation_labels_dir)
    
    print("\nData split completed:")
    print(f"Training samples: {len(train_samples)}")
    print(f"Validation samples: {len(validation_samples)}")

    # Create summary CSV for validation set
    summary_data = []
    for sample in validation_samples:
        summary_data.append({
            'sensor': 's1' if 's1' in sample['label_file'] else 's2',
            'label_file': os.path.basename(sample['label_file']),
            'has_flooding': sample['has_flooding'],
            'num_image_files': len(sample['image_files'])
        })
    
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(os.path.join(validation_dir, 'validation_summary.csv'), index=False)
    print("\nValidation summary saved to validation_summary.csv")


# Example usage
if __name__ == "__main__":
    # Update these paths to match your directory structure
    SOURCE_IMAGES_DIR = r"C:\Users\san\OneDrive\Desktop\Personal\School\sen12flood\images"
    SOURCE_LABELS_DIR = r"C:\Users\san\OneDrive\Desktop\Personal\School\sen12flood\labels"
    TRAIN_DIR = r"C:\Users\san\OneDrive\Desktop\Personal\School\train2"
    VALIDATION_DIR = r"C:\Users\san\OneDrive\Desktop\Personal\School\validation"
    
    divide_train_validation_dataset(
        source_images_dir=SOURCE_IMAGES_DIR,
        source_labels_dir=SOURCE_LABELS_DIR,
        train_dir=TRAIN_DIR,
        validation_dir=VALIDATION_DIR,
        num_validation_samples=100  # Select at least 100 validation samples (50 flood, 50 non-flood) per sensor
    )
