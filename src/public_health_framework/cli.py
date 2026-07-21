"""Command-line interface for Public Health Framework."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import webbrowser

from . import __version__
from .data import DashboardConfig, load_dataset, prepare_dataset, validate_config
from .report import build_dashboard


def _choose(prompt: str, columns: list[str], required: bool = False) -> str | None:
    print(f"\n{prompt}")
    if not required:
        print("  0. Skip")
    for index, column in enumerate(columns, 1):
        print(f"  {index}. {column}")
    while True:
        answer = input("Select a number: ").strip()
        if not required and answer in {"", "0"}:
            return None
        try:
            selected = int(answer)
            if 1 <= selected <= len(columns):
                return columns[selected - 1]
        except ValueError:
            pass
        print("Please enter one of the listed numbers.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="phdash", description="Generate dashboards from public-health data.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="Create an HTML dashboard from CSV or Excel data.")
    analyze.add_argument("input", help="Path to a .csv, .xlsx, or .xlsm file")
    analyze.add_argument("-o", "--output", default="dashboard.html", help="Output HTML path")
    analyze.add_argument("--sheet", default="0", help="Excel sheet name or zero-based number")
    analyze.add_argument("--location", help="Location/geography column")
    analyze.add_argument("--date", help="Date column")
    analyze.add_argument("--value", help="Cases, events, or other value column")
    analyze.add_argument("--population", help="Population/denominator column")
    analyze.add_argument("--category", help="Disease, sex, age group, or other category column")
    analyze.add_argument("--title", default="Public Health Dashboard")
    analyze.add_argument("--interactive", action="store_true", help="Choose columns through prompts")
    analyze.add_argument("--open", action="store_true", help="Open the generated dashboard in a browser")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        sheet: str | int = int(args.sheet) if str(args.sheet).isdigit() else args.sheet
        frame = load_dataset(args.input, sheet=sheet)
        columns = frame.columns.tolist()
        if args.interactive:
            args.location = _choose("Which column contains the location?", columns)
            args.date = _choose("Which column contains the date?", columns)
            args.value = _choose("Which column contains cases or another measured value?", columns, required=True)
            args.population = _choose("Which column contains the population/denominator?", columns)
            args.category = _choose("Which column contains a category?", columns)
        config = DashboardConfig(args.location, args.date, args.value, args.population, args.category)
        validate_config(frame, config)
        prepared = prepare_dataset(frame, config)
        output = build_dashboard(prepared, config, args.output, args.title)
        print(f"Dashboard created: {output}")
        if args.open:
            webbrowser.open(output.as_uri())
        return 0
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

