from __future__ import annotations

from graph_represent.runner import build_parser, run_tasks


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_tasks(args.tasks, runname=args.runname, limit=args.limit)


if __name__ == "__main__":
    main()
