import argparse
import csv
import os
import lxml.html
import yaml

def extract_features(html_file, feature_config):
    tree = lxml.html.parse(html_file)
    root = tree.getroot()
    features = {}

    for feature_name, xpath in feature_config.items():
        elements = root.xpath(xpath)
        if elements:
            features[feature_name] = elements[0]
        else:
            features[feature_name] = None

    return features

def main():
    parser = argparse.ArgumentParser(description="Extract features from HTML files and write to CSV")
    parser.add_argument("--input-dir", required=True, help="The directory containing the downloaded HTML files")
    parser.add_argument("--config-file", required=True, help="The YAML configuration file with feature names and XPaths")
    parser.add_argument("--output-file", required=True, help="The CSV file to write the extracted features to")
    args = parser.parse_args()

    with open(args.config_file, "r") as f:
        feature_config = yaml.safe_load(f)

    # Create the CSV file and write the header row
    with open(args.output_file, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = list(feature_config.keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for file in os.listdir(args.input_dir):
            file_path = os.path.join(args.input_dir, file)
            if os.path.isfile(file_path):
                features = extract_features(file_path, feature_config)
                writer.writerow(features)
                print(f"Processed {file}")

if __name__ == "__main__":
    main()
