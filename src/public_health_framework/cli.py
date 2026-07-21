"""PHFrame project and data command-line interface."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import webbrowser

from . import __version__
from .application import PHFrame
from .data import DashboardConfig, load_dataset, prepare_dataset, validate_config
from .project import check_project, create_project
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
    parser = argparse.ArgumentParser(prog="phframe", description="Build public-health data applications.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new = subparsers.add_parser("new", help="Create a new PHFrame project.")
    new.add_argument("name", help="Human-readable project name")
    new.add_argument("--directory", "-d", help="Destination directory (defaults to a project-name slug)")

    serve = subparsers.add_parser("serve", help="Run a PHFrame project development server.")
    serve.add_argument("--config", default="phframe.yaml", help="Project configuration path")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)

    check = subparsers.add_parser("check", help="Validate project configuration and initialize storage.")
    check.add_argument("--config", default="phframe.yaml", help="Project configuration path")

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
        if args.command == "new":
            project = create_project(args.name, args.directory)
            print(f"PHFrame project created: {project}")
            print(f"Next: cd {project.name} && phframe serve")
            return 0
        if args.command == "check":
            _, messages = check_project(args.config)
            print("\n".join(messages))
            return 0
        if args.command == "serve":
            import uvicorn

            application = PHFrame.from_file(args.config)
            print(f"Starting {application.config.name} at http://{args.host}:{args.port}")
            uvicorn.run(application, host=args.host, port=args.port)
            return 0

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
    except (FileExistsError, FileNotFoundError, ImportError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
