import os
import json
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from agent.llm_client import GeminiClient
from analyzer.django_analyzer import DjangoAnalyzer
from analyzer.flask_analyzer import FlaskAnalyzer
from analyzer.node_analyzer import NodeAnalyzer
from runner.test_runner import run_test_interactive, TestResult

load_dotenv()
console = Console()

def detect_project_type(path: str) -> str:
    """Detect the project type (django, flask, node)."""
    project_path = Path(path)
    
    # Check for Django
    if (project_path / "manage.py").exists():
        return "django"
    
    # Check for Node.js
    if (project_path / "package.json").exists():
        return "node"
    
    # Check for Flask
    for py_file in project_path.rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "from flask import Flask" in content or "import flask" in content:
                    return "flask"
        except Exception:
            continue
            
    return "unknown"

@click.group()
def cli():
    """Test Authoring Agent - Generate tests from natural language"""
    pass


@cli.command()
@click.option("--path", "-p", default=".", help="Path to project")
@click.option("--repo", "-r", help="GitHub repository URL")
def analyze(path: str, repo: str | None):
    """Analyze a project and show testable components"""
    console.print("[bold blue]🔍 Test Authoring Agent[/bold blue]")

    if not os.path.exists(path):
        console.print(f"[red]Error: Path '{path}' does not exist.[/red]")
        return
    
    # --- Git clone support when --repo is provided ---
    if repo:
        from git import Repo
        import tempfile, shutil

        tmp_dir = tempfile.mkdtemp(prefix="test_agent_clone_")
        console.print(f"[yellow]Cloning {repo} into {tmp_dir}...[/yellow]")
        try:
            Repo.clone_from(repo, tmp_dir, depth=1)
            path = tmp_dir
        except Exception as clone_err:
            console.print(f"[red]Failed to clone repository: {clone_err}[/red]")
            return

    project_type = detect_project_type(path)
    
    if project_type == "unknown":
        console.print("[red]Could not determine project type.[/red]")
        return

    console.print(f"Detected [bold green]{project_type.capitalize()}[/bold green] project.")
    console.print("[dim]Analyzing project structure...[/dim]\n")

    analyzer = None
    if project_type == "django":
        analyzer = DjangoAnalyzer(path)
    elif project_type == "flask":
        analyzer = FlaskAnalyzer(path)
    elif project_type == "node":
        analyzer = NodeAnalyzer(path)

    if not analyzer:
        console.print("[red]Failed to initialize analyzer.[/red]")
        return

    # Analyze project with progress indicator
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Scanning project...", total=None)
        results = analyzer.analyze()
        progress.update(task, completed=True)

    if not results or "error" in results:
        console.print(f"[red]❌ {results.get('error', 'Analysis failed.')}[/red]")
        return

    console.print("[green]✓ Project analyzed successfully![/green]")

    # Generic stats table
    table = Table(title="Project Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Count", style="cyan")
    
    if project_type == "django":
        table.add_row("Apps", str(len(results.get("apps", []))))
        table.add_row("Model files", str(sum(len(v) for v in results.get("models", {}).values())))
        table.add_row("View files", str(sum(len(v) for v in results.get("views", {}).values())))
        table.add_row("URL files", str(sum(len(v) for v in results.get("urls", {}).values())))
    elif project_type == "flask":
        table.add_row("Routes", str(len(results.get("routes", []))))
    elif project_type == "node":
        table.add_row("Routes", str(len(results.get("routes", []))))

    console.print(table)

    # Endpoints preview
    endpoints = results.get("testable_endpoints", [])
    if project_type in ["flask", "node"]:
        endpoints = results.get("routes", [])

    if endpoints:
        console.print(f"[bold]🎯 {len(endpoints)} Testable Endpoints found[/bold]")
        ep_table = Table(show_header=True, header_style="bold blue")
        if project_type == "django":
            ep_table.add_column("URL")
            ep_table.add_column("View")
            ep_table.add_column("App")
            for ep in endpoints:
                ep_table.add_row(ep.get("url"), ep.get("view"), ep.get("app"))
        elif project_type == "flask":
            ep_table.add_column("Path")
            ep_table.add_column("Function")
            ep_table.add_column("Methods")
            for route in endpoints:
                ep_table.add_row(route.get("path"), route.get("function"), str(route.get("methods")))
        elif project_type == "node":
            ep_table.add_column("Path")
            ep_table.add_column("Handler")
            ep_table.add_column("Methods")
            for route in endpoints:
                ep_table.add_row(route.get("path"), route.get("handler"), str(route.get("methods")))

        console.print(ep_table)

    cache = {"path": path, "results": results, "type": project_type}
    console.print()
    if Confirm.ask("Would you like to generate tests?"):
        asyncio.run(_interactive_session(cache))


async def _interactive_session(cache):
    console.print("\n[bold green]🧪 Interactive Test Generation Session[/bold green]")
    analysis_results = cache["results"]
    project_path = cache["path"]
    project_type = cache["type"]

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[red]Error: GEMINI_API_KEY not found in environment[/red]")
        return

    client = GeminiClient(api_key)
    generated_tests: List[Dict[str, str]] = []

    from rich.syntax import Syntax
    from agent.prompts import PromptTemplates

    while True:
        spec = Prompt.ask("\n[cyan]Enter test specification[/cyan] ([dim]'help' for commands, 'exit' to quit)[/dim]")
        cmd = spec.lower().strip()
        if cmd in {"quit", "exit", "q"}:
            break

        console.print("[yellow]🤖 Generating test...[/yellow]")
        
        prompt = ""
        if project_type == "django":
            prompt = PromptTemplates.GENERATE_API_TEST_DJANGO.format(
                specification=spec, url_pattern="/api/items/", view_name="ItemListView",
                methods="['GET', 'POST']", parameters="{}", view_code="class ItemListView(APIView): ...",
                model_info='{"name": "Item", "fields": ["name", "value"]}',
                codebase_context=json.dumps(analysis_results, indent=2, default=str)
            )
        elif project_type == "flask":
            route_info = analysis_results.get("routes", [{}])[0] if analysis_results.get("routes") else {}
            prompt = PromptTemplates.GENERATE_API_TEST_FLASK.format(
                specification=spec, path=route_info.get("path", "/"),
                function=route_info.get("function", "unknown"), methods=str(route_info.get("methods", ["GET"])),
                app_context=json.dumps(analysis_results, indent=2, default=str)
            )
        elif project_type == "node":
            route_info = analysis_results.get("routes", [{}])[0] if analysis_results.get("routes") else {}
            app_file = analysis_results.get("app_file", "app.js")
            prompt = PromptTemplates.GENERATE_API_TEST_NODE.format(
                specification=spec, path=route_info.get("path", "/"),
                handler=route_info.get("handler", "unknown"), methods=str(route_info.get("methods", ["GET"])),
                app_context=json.dumps(analysis_results, indent=2, default=str), app_file=app_file
            )

        if not prompt:
            console.print("[red]Could not generate prompt for this project type.[/red]")
            continue

        test_code = await client.generate(prompt, {{}})
        generated_tests.append({"code": test_code, "spec": spec})

        console.print("\n[bold green]✅ Generated Test:[/bold green]")
        lang = "python" if project_type != "node" else "javascript"
        console.print(Syntax(test_code, lang))

        if Confirm.ask("\nRun this test?", default=True):
            test_name = "_".join(spec.lower().split()[:3])
            await run_test_interactive(
                project_path=project_path,
                test_code=test_code,
                project_type=project_type,
                test_name=test_name
            )

@cli.command()
def version():
    """Show version information"""
    console.print("[bold]Test Authoring Agent v0.1.0[/bold]")


if __name__ == "__main__":
    cli()