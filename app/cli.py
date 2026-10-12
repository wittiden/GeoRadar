import argparse
import sys

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import setup_logging
from app.services.ingest import collect
from app.sources.registry import REGISTRY


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sources", help="список зарегистрированных адаптеров")
    c = sub.add_parser("collect", help="собрать данные источника и записать в БД")
    c.add_argument("code")
    args = parser.parse_args(argv)

    setup_logging(settings.log_level, settings.log_json)
    if args.cmd == "sources":
        print("\n".join(sorted(REGISTRY)))
        return 0
    if args.code not in REGISTRY:
        print(f"неизвестный источник {args.code!r}; доступны: {', '.join(sorted(REGISTRY))}", file=sys.stderr)
        return 2
    with SessionLocal() as db:
        result = collect(db, args.code)
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
