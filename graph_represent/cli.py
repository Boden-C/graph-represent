from __future__ import annotations

from graph_represent.runner import build_parser, run_task


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_task(args.task, runname=args.runname, limit=args.limit)


if __name__ == "__main__":
    main()
