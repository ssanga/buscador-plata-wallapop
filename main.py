"""Punto de entrada del buscador de plata en Wallapop.

    python main.py batch                  descarga y analiza los anuncios (lo que se ejecuta cada noche)
    python main.py batch --max-pages 3    prueba rápida
    python main.py batch --reanalyze      recalcula el análisis sin descargar (tras tocar analyzer.py)
    python main.py export                 genera site/data.json para la web estática (GitHub Pages)
    python main.py web                    web en http://127.0.0.1:5000
    python main.py web --port 8080 --host 0.0.0.0
"""
import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("batch", help="descarga y analiza los anuncios", add_help=False)
    exp = sub.add_parser("export", help="genera el JSON de la web estática")
    exp.add_argument("--out", default="site/data.json")
    web = sub.add_parser("web", help="arranca la web de consulta")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=5000)

    args, rest = parser.parse_known_args()

    if args.command == "batch":
        from plata import batch

        return batch.main(rest)

    if rest:
        parser.error(f"argumentos no reconocidos: {' '.join(rest)}")
    if args.command == "export":
        from pathlib import Path

        from plata import export

        data = export.export(Path(args.out))
        print(f"{args.out}: {len(data['items'])} anuncios")
        return 0

    from plata.web import app

    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
