import argparse
import struct


def main():
    parser = argparse.ArgumentParser(description="Read a .DAT recording")
    parser.add_argument('path', help="Path to the recording")
    config = parser.parse_args()

    with open(config.path, 'rb') as handle:
        data = list(struct.iter_unpack('<llll', handle.read()))
    print(f"{len(data)} rows")
    for i, r in enumerate(data):
        print(i, r)
    avg_pos = [
        sum(r[i] for r in data[1:]) / (len(data) - 1)
        for i in (1, 2, 3)
    ]
    print(f"Average position (ignoring first): {avg_pos}")


if __name__ == "__main__":
    main()
