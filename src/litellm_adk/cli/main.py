"""Command Line Interface for LiteLLM ADK Platform."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from ..server.serve import serve
from ..workflow.schema import WorkflowDefinition
from ..workflow.graph import WorkflowGraph
from ..workflow.engine import WorkflowEngine
from ..persistence.sqlite_workflow import workflow_repository


def cli():
    """Main entrypoint for litellm-adk command line tool."""
    parser = argparse.ArgumentParser(
        prog="litellm-adk",
        description="LiteLLM ADK: Visual Workflow Platform & Multi-Agent Orchestration CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Start the native visual workflow server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host address to bind to (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for local development")
    serve_parser.add_argument("--db", default=None, help="Custom SQLite database file path")

    # Command: workflow
    wf_parser = subparsers.add_parser("workflow", help="Workflow management commands")
    wf_subparsers = wf_parser.add_subparsers(dest="wf_command", help="Workflow action")

    # workflow list
    wf_subparsers.add_parser("list", help="List all saved workflows")

    # workflow validate
    val_parser = wf_subparsers.add_parser("validate", help="Validate a workflow definition file")
    val_parser.add_argument("file", help="Path to workflow JSON file")

    # workflow run
    run_parser = wf_subparsers.add_parser("run", help="Run a workflow definition")
    run_parser.add_argument("target", help="Workflow ID or path to workflow JSON file")
    run_parser.add_argument("--input", "-i", default="{}", help="Input payload as JSON string")

    # workflow export
    exp_parser = wf_subparsers.add_parser("export", help="Export a workflow to JSON")
    exp_parser.add_argument("workflow_id", help="Workflow ID to export")
    exp_parser.add_argument("output", help="Output file path")

    # workflow import
    imp_parser = wf_subparsers.add_parser("import", help="Import a workflow from JSON file")
    imp_parser.add_argument("file", help="Input file path")

    args = parser.parse_args()

    if args.command == "serve":
        serve(host=args.host, port=args.port, reload=args.reload, database_url=args.db)
    elif args.command == "workflow":
        asyncio.run(_handle_workflow_command(args))
    else:
        parser.print_help()


async def _handle_workflow_command(args):
    if args.wf_command == "list":
        wfs = await workflow_repository.list_all()
        if not wfs:
            print("No workflows found in database.")
            return
        print(f"\n{'ID':<20} {'NAME':<30} {'ACTIVE':<8} {'VERSION':<8}")
        print("-" * 70)
        for w in wfs:
            print(f"{w.id:<20} {w.name:<30} {str(w.active):<8} {w.version:<8}")
        print()

    elif args.wf_command == "validate":
        path = Path(args.file)
        if not path.exists():
            print(f"Error: File '{args.file}' does not exist.")
            sys.exit(1)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            wf = WorkflowDefinition.model_validate(data)
            graph = WorkflowGraph(wf)
            graph.validate()
            print(f"Workflow '{wf.name}' ({len(wf.nodes)} nodes, {len(wf.edges)} edges) is valid!")
        except Exception as e:
            print(f"Workflow validation failed: {e}")
            sys.exit(1)

    elif args.wf_command == "run":
        target = args.target
        input_data = json.loads(args.input)

        path = Path(target)
        if path.exists() and path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            wf = WorkflowDefinition.model_validate(data)
        else:
            wf = await workflow_repository.get(target)
            if not wf:
                print(f"Error: Workflow '{target}' not found.")
                sys.exit(1)

        print(f"Executing workflow: {wf.name} ({wf.id})...")
        engine = WorkflowEngine()

        def _print_event(e_type, payload):
            if e_type == "node.started":
                print(f"  ▶ Node started: {payload.get('node_id')} ({payload.get('node_name')})")
            elif e_type == "node.completed":
                print(f"  ✓ Node completed: {payload.get('node_id')} ({payload.get('duration', 0):.2f}s)")
            elif e_type == "node.failed":
                print(f"  ✗ Node failed: {payload.get('node_id')} - {payload.get('error')}")
            elif e_type == "human.required":
                print(f"  ⏸ PAUSED for human approval: {payload.get('approval', {}).get('message')}")

        engine.subscribe(_print_event)
        state = await engine.execute(wf, trigger_data=input_data)
        print(f"\nExecution finished with status: {state.status.value.upper()} in {state.total_duration:.2f}s")
        print("Outputs:")
        print(json.dumps(state.node_outputs, indent=2))

    elif args.wf_command == "export":
        wf = await workflow_repository.get(args.workflow_id)
        if not wf:
            print(f"Error: Workflow '{args.workflow_id}' not found.")
            sys.exit(1)
        out_path = Path(args.output)
        out_path.write_text(wf.model_dump_json(indent=2), encoding="utf-8")
        print(f"Workflow exported to {args.output}")

    elif args.wf_command == "import":
        path = Path(args.file)
        if not path.exists():
            print(f"Error: File '{args.file}' does not exist.")
            sys.exit(1)
        data = json.loads(path.read_text(encoding="utf-8"))
        wf = WorkflowDefinition.model_validate(data)
        await workflow_repository.save(wf)
        print(f"Successfully imported workflow: {wf.name} ({wf.id})")


if __name__ == "__main__":
    cli()
