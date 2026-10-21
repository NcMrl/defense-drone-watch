"""Commandes d'exploitation.

  python -m app.cli seed-demo          charge les données synthétiques de démonstration
  python -m app.cli purge-demo         supprime toutes les données synthétiques
  python -m app.cli import-catalog     importe le catalogue initial de sources (non vérifiées)
  python -m app.cli add-source URL NOM [--type media_specialise] [--country FR] [--language fr]
  python -m app.cli run-source ID      collecte immédiate d'une source
  python -m app.cli list-sources       état des sources
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app.config import BASE_DIR
from app.db import session_scope
from app.logging_config import configure_logging
from app.models import Source
from app.services.demo import purge_demo, seed_demo
from app.services.ingest import run_source
from app.services.net import assert_public_url

CATALOG = BASE_DIR / "data" / "catalogue_sources.json"


def import_catalog(path: Path = CATALOG) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    added = skipped = 0
    with session_scope() as session:
        for entry in data["sources"]:
            if session.scalar(select(Source).where(Source.url == entry["url"])):
                skipped += 1
                continue
            session.add(Source(
                **entry,
                connector_type="rss",
                verification_status="non_verifiee",
                verification_note=f"URL candidate proposée le {data['proposees_le']}, non vérifiée.",
            ))
            added += 1
    return {"ajoutees": added, "deja_presentes": skipped}


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-demo")
    sub.add_parser("purge-demo")
    sub.add_parser("import-catalog")
    sub.add_parser("list-sources")
    add = sub.add_parser("add-source")
    add.add_argument("url")
    add.add_argument("name")
    add.add_argument("--type", default="non_verifiee")
    add.add_argument("--country")
    add.add_argument("--language")
    run = sub.add_parser("run-source")
    run.add_argument("id", type=int)
    args = parser.parse_args()

    if args.cmd == "seed-demo":
        with session_scope() as s:
            print(json.dumps(seed_demo(s), ensure_ascii=False))
    elif args.cmd == "purge-demo":
        with session_scope() as s:
            print(f"{purge_demo(s)} document(s) synthétique(s) supprimé(s)")
    elif args.cmd == "import-catalog":
        print(json.dumps(import_catalog(), ensure_ascii=False))
    elif args.cmd == "add-source":
        assert_public_url(args.url)
        with session_scope() as s:
            src = Source(name=args.name, url=args.url, source_type=args.type, country=args.country, language=args.language)
            s.add(src)
            s.flush()
            print(f"Source {src.id} ajoutée")
    elif args.cmd == "run-source":
        with session_scope() as s:
            r = run_source(s, args.id)
            print(json.dumps({
                "statut": r.status, "elements": r.items_fetched, "nouveaux": r.docs_created,
                "mis_a_jour": r.docs_updated, "doublons": r.duplicates, "non_modifie": r.not_modified,
                "erreur": r.error_message, "duree_ms": r.duration_ms,
            }, ensure_ascii=False))
    elif args.cmd == "list-sources":
        with session_scope() as s:
            for src in s.scalars(select(Source).order_by(Source.id)):
                print(f"{src.id:>4}  {'ON ' if src.enabled else 'OFF'}  {src.verification_status:<13} {src.name}  "
                      f"{'⚠ ' + src.last_error if src.last_error else ''}")


if __name__ == "__main__":
    main()
