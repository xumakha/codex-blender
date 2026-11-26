import argparse
import json
import sys

from .models import SceneSpec


def main():
    parser = argparse.ArgumentParser(description="Codex ↔ Blender video tools")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("serve", help="Run the MCP stdio server")
    subs.add_parser("doctor", help="Check Blender and paths")
    subs.add_parser("schema", help="Print the scene JSON schema")
    render = subs.add_parser("render", help="Render a scene JSON file")
    render.add_argument("scene")
    render.add_argument("--mode", choices=["preview", "video"], default="preview")
    status_parser = subs.add_parser("status", help="Check an existing render job")
    status_parser.add_argument("job_id")
    args = parser.parse_args()
    try:
        if args.command == "serve":
            from .server import main as serve
            serve()
            return
        if args.command == "schema":
            result = SceneSpec.model_json_schema()
        elif args.command == "doctor":
            from .server import blender_info
            result = blender_info()
        elif args.command == "render":
            from pathlib import Path
            from .jobs import submit
            result = submit(SceneSpec.model_validate_json(Path(args.scene).read_text(encoding="utf-8")), args.mode)
        else:
            from .jobs import status
            result = status(args.job_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "doctor" and not result["ready"]:
            sys.exit(1)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
