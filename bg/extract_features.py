import argparse
import csv
import os
import lxml.html
import yaml
import re

def get_text_representation(element):
    if element is None:
        return ''
    if isinstance(element, str):
        return element
    return ''.join(element.itertext())

def extract_features(html_file, feature_config):
    tree = lxml.html.parse(html_file)
    root = tree.getroot()
    features = {}

    for feature_name, extraction_info in feature_config.items():
        xpath = extraction_info['xpath']
        regex = extraction_info.get('regex', None)

        elements = root.xpath(xpath)
        if elements:
            text = get_text_representation(elements[0])
            if regex:
                match = re.search(regex, text)
                if match:
                    features[feature_name] = match.group(1)
                else:
                    features[feature_name] = None
            else:
                features[feature_name] = text
        else:
            features[feature_name] = None

    return features

def main():
    parser = argparse.ArgumentParser(description="Extract features from HTML files and write to CSV")
    parser.add_argument("--input-dir", required=True, help="The directory containing the downloaded HTML files")
    parser.add_argument("--config-file", required=True, help="The YAML configuration file with feature names, XPaths and optional Regexes")
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
            if not file.endswith(".html"):
                continue
            file_path = os.path.join(args.input_dir, file)
            if os.path.isfile(file_path):
                features = extract_features(file_path, feature_config)
                writer.writerow(features)
                print(f"Processed {file}")


if __name__ == "__main__":
    main()
