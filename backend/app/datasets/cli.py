"""Run `python -m app.datasets.cli register` from backend/."""

import argparse

from app.datasets.registry import register_all
from app.storage.database import repository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["register"])
    args = parser.parse_args()
    if args.command == "register":
        repository.initialize()
        datasets = register_all(repository)
        print(f"Registered {len(datasets)} benchmark datasets (metadata only).")


if __name__ == "__main__":
    main()
