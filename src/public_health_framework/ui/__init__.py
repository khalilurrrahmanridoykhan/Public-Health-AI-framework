"""Browser assets for the PHFrame Web Component frontend."""

from importlib.resources import files


def asset_text(name: str) -> str:
    return files(__package__).joinpath(name).read_text(encoding="utf-8")


def asset_bytes(name: str) -> bytes:
    return files(__package__).joinpath(name).read_bytes()
