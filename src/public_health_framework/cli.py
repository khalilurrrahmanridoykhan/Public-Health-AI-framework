"""PHFrame project and data command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import webbrowser

from . import __version__
from .application import PHFrame
from .data import DashboardConfig, load_dataset, prepare_dataset, validate_config
from .importer import import_dataset, load_mapping, save_mapping
from .project import check_project, create_project
from .report import build_dashboard
from .storage import Storage


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
    serve.add_argument("--host", help="Bind host (defaults to project configuration)")
    serve.add_argument("--port", type=int, help="Bind port (defaults to project configuration)")
    serve.add_argument("--reload", action="store_true", help="Reload when source/configuration changes")

    check = subparsers.add_parser("check", help="Validate project configuration and initialize storage.")
    check.add_argument("--config", default="phframe.yaml", help="Project configuration path")

    migrate = subparsers.add_parser("migrate", help="Apply safe dataset schema changes.")
    migrate.add_argument("--config", default="phframe.yaml", help="Project configuration path")
    migrate.add_argument("--check", action="store_true", help="Report changes without applying them")

    importer = subparsers.add_parser("import", help="Import CSV or Excel records into a dataset.")
    importer.add_argument("dataset", help="Configured dataset name")
    importer.add_argument("source", help="Path to a .csv, .xlsx, or .xlsm file")
    importer.add_argument("--config", default="phframe.yaml", help="Project configuration path")
    importer.add_argument("--sheet", default="0", help="Excel sheet name or zero-based number")
    importer.add_argument("--mapping", help="Reusable YAML column mapping")
    importer.add_argument("--map", action="append", default=[], metavar="SOURCE=FIELD", help="Map a source column")
    importer.add_argument("--save-mapping", help="Save the effective mapping to YAML")
    importer.add_argument("--dry-run", action="store_true", help="Validate without importing records")

    history = subparsers.add_parser("imports", help="Show recent dataset import runs.")
    history.add_argument("--config", default="phframe.yaml", help="Project configuration path")
    history.add_argument("--limit", type=int, default=20)

    sync = subparsers.add_parser("sync", help="Pull records from configured connectors.")
    sync.add_argument("connector", nargs="?", help="Connector name")
    sync.add_argument("--config", default="phframe.yaml", help="Project configuration path")
    sync.add_argument("--all", action="store_true", help="Run every configured connector")
    sync.add_argument("--due", action="store_true", help="Run only connectors whose schedule is due")
    sync.add_argument("--dry-run", action="store_true", help="Fetch and validate without importing")

    syncs = subparsers.add_parser("syncs", help="Show recent connector synchronization runs.")
    syncs.add_argument("--config", default="phframe.yaml", help="Project configuration path")
    syncs.add_argument("--limit", type=int, default=20)
    syncs.add_argument("--connector", help="Filter history by connector name")

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
        if args.command == "migrate":
            from .config import ProjectConfig

            config = ProjectConfig.load(args.config)
            actions = Storage(config).migrate(check_only=args.check)
            if actions:
                prefix = "Pending" if args.check else "Applied"
                print(f"{prefix} migrations:")
                for action in actions:
                    print(f"  - {action}")
                return 1 if args.check else 0
            print("Database schema is up to date.")
            return 0
        if args.command == "imports":
            from .config import ProjectConfig

            storage = Storage(ProjectConfig.load(args.config))
            storage.initialize()
            print(json.dumps(storage.import_history(args.limit), indent=2))
            return 0
        if args.command == "syncs":
            from .config import ProjectConfig

            storage = Storage(ProjectConfig.load(args.config))
            storage.initialize()
            print(json.dumps(storage.sync_history(args.limit, args.connector), indent=2))
            return 0
        if args.command == "sync":
            from .config import ProjectConfig
            from .sync import connector_due, sync_connector

            config = ProjectConfig.load(args.config)
            if args.all:
                names = list(config.connectors)
            elif args.connector:
                names = [args.connector]
            else:
                raise ValueError("Specify a connector or use --all.")
            if args.due:
                names = [name for name in names if name in config.connectors and connector_due(config, name)]
            if not names:
                print("No connector synchronizations are due.")
                return 0
            failed = False
            for name in names:
                result = sync_connector(config, name, args.dry_run)
                print(f"{name}: {result.status} ({result.imported_rows}/{result.fetched_rows} imported)")
                for error in result.errors[:20]:
                    print(f"  Error: {error['message']}")
                failed = failed or result.status == "failed"
            return 2 if failed else 0
        if args.command == "import":
            from .config import ProjectConfig

            config = ProjectConfig.load(args.config)
            mapping: dict[str, str] = {}
            if args.mapping:
                mapped_dataset, mapping = load_mapping(args.mapping)
                if mapped_dataset and mapped_dataset != args.dataset:
                    raise ValueError(
                        f"Mapping is for dataset '{mapped_dataset}', not '{args.dataset}'."
                    )
            for item in args.map:
                source, separator, target = item.partition("=")
                if not separator or not source or not target:
                    raise ValueError("--map must use SOURCE=FIELD format.")
                mapping[source] = target
            sheet: str | int = int(args.sheet) if str(args.sheet).isdigit() else args.sheet
            result = import_dataset(
                config, args.dataset, args.source, mapping or None, sheet=sheet, dry_run=args.dry_run
            )
            if args.save_mapping:
                if not mapping:
                    frame = load_dataset(args.source, sheet=sheet)
                    mapping = {column: column for column in frame.columns if column in config.datasets[args.dataset].fields}
                saved = save_mapping(args.save_mapping, args.dataset, mapping)
                print(f"Mapping saved: {saved}")
            print(f"Import run: {result.run_id}")
            print(f"Status: {result.status}")
            print(f"Rows: {result.imported_rows} imported / {result.total_rows} total")
            for error in result.errors[:20]:
                print(f"  Row {error['row']}: {error['message']}")
            return 2 if result.errors else 0
        if args.command == "serve":
            import os
            import uvicorn

            application = PHFrame.from_file(args.config)
            if args.reload and application.config.environment == "production":
                raise ValueError("--reload is not allowed in production mode.")
            host = args.host or application.config.host
            port = args.port or application.config.port
            print(
                f"Starting {application.config.name} ({application.config.environment}) "
                f"at http://{host}:{port}"
            )
            if args.reload:
                os.environ["PHFRAME_CONFIG"] = str(Path(args.config).resolve())
                uvicorn.run(
                    "public_health_framework.runtime:create_app",
                    factory=True, host=host, port=port, reload=True,
                    reload_dirs=[str(application.config.root)],
                )
            else:
                uvicorn.run(application, host=host, port=port)
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
