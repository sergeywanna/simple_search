import sys
import csv
import numpy as np

def main(input_csv, urls_output, embeddings_output):
    with open(input_csv) as f:
        reader = csv.reader(f)
        urls = []
        embeddings_list = []
        for row in reader:
            urls.append(row[0])
            embeddings_list.append(np.array(eval(row[1])))

    embeddings_array = np.stack(embeddings_list, dtype=np.float32)

    with open(urls_output, 'w') as f:
        for url in urls:
            f.write(url + '\n')

    np.save(embeddings_output, embeddings_array)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python convert_embeddings.py <input_csv> <urls_output> <embeddings_output>")
        sys.exit(1)

    input_csv = sys.argv[1]
    urls_output = sys.argv[2]
    embeddings_output = sys.argv[3]

    main(input_csv, urls_output, embeddings_output)
