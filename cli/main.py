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
from analyzer.enhanced_django_analyzer import DjangoAnalyzer

# Import runner components
try:
    from runner import TestRunner, run_test_interactive, TestResult, ErrorAnalysis
except ImportError:
    console.print("[yellow]Warning: Test runner not available. Some features may be limited.[/yellow]")

load_dotenv()
console = Console()

@click.group()
def cli():
    """Test Authoring Agent - Generate tests from natural language"""
    pass


@cli.command()
@click.option("--path", "-p", default=".", help="Path to Django project")
@click.option("--repo", "-r", help="GitHub repository URL")
def analyze(path: str, repo: str | None):
    """Analyze a Django project and show testable components"""
    console.print("[bold blue]🔍 Django Test Authoring Agent[/bold blue]")
    console.print("[dim]Analyzing project structure...[/dim]\n")

    # --- Git clone support when --repo is provided ---
    if repo:
        from git import Repo  # GitPython
        import tempfile, shutil

        tmp_dir = tempfile.mkdtemp(prefix="test_agent_clone_")
        console.print(f"[yellow]Cloning {repo} into {tmp_dir}...[/yellow]")
        try:
            Repo.clone_from(repo, tmp_dir, depth=1)
            path = tmp_dir
        except Exception as clone_err:
            console.print(f"[red]Failed to clone repository: {clone_err}[/red]")
            return

    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.tree import Tree
    from rich.syntax import Syntax

    # Analyze project with progress indicator
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Scanning project...", total=None)
        analyzer = DjangoAnalyzer(path)
        results = analyzer.analyze()
        progress.update(task, completed=True)

    if "error" in results:
        console.print(f"[red]❌ {results['error']}[/red]")
        return

    console.print("[green]✓ Django project detected![/green]")

    # Stats table
    table = Table(title="Project Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Count", style="cyan")
    table.add_row("Apps", str(len(results["apps"])))
    table.add_row("Model files", str(sum(len(v) for v in results["models"].values())))
    table.add_row("View files", str(sum(len(v) for v in results["views"].values())))
    table.add_row("URL files", str(sum(len(v) for v in results["urls"].values())))
    console.print(table)

    # Endpoints preview
    if results["testable_endpoints"]:
        console.print(f"[bold]🎯 {len(results['testable_endpoints'])} Testable Endpoints found[/bold]")
        ep_table = Table(show_header=True, header_style="bold blue")
        ep_table.add_column("URL")
        ep_table.add_column("View")
        ep_table.add_column("App")
        for ep in results["testable_endpoints"]:
            ep_table.add_row(ep["url"], ep["view"], ep["app"])
        console.print(ep_table)

    cache = {"path": path, "results": results}
    console.print()
    if Confirm.ask("Would you like to generate tests?"):
        _interactive_session(cache)


def _interactive_session(cache):
    console.print("\n[bold green]🧪 Interactive Test Generation Session[/bold green]")
    analysis_results = cache["results"]
    project_path = cache["path"]

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[red]Error: GEMINI_API_KEY not found in environment[/red]")
        return

    client = GeminiClient(api_key)
    generated_tests: List[str] = []

    from rich.syntax import Syntax

    while True:
        spec = Prompt.ask("\n[cyan]Enter test specification[/cyan] ([dim]'help' for commands)[/dim]")
        cmd = spec.lower().strip()
        if cmd in {"quit", "exit", "q"}:
            break

        if cmd == "help":
            console.print("Available commands: [bold]list, save, quit[/bold]")
            continue
        if cmd == "list":
            if not generated_tests:
                console.print("[dim]No tests generated yet.[/dim]")
            else:
                for idx, t in enumerate(generated_tests, 1):
                    console.print(f"\n[bold]Test #{idx}[/bold]")
                    console.print(Syntax(t, "python"))
            continue

        # Treat as spec for generating new test
        console.print("[yellow]🤖 Generating test...[/yellow]")
        from agent.prompts import PromptTemplates, TestContext
        ctx = TestContext(
                specification=spec,
                target_type="unspecified",
                target_info={},
                codebase_context=analysis_results,
            )
        # Extract relevant information from analysis results
        models = analysis_results.get('models', {})
        views = analysis_results.get('views', {})
        urls = analysis_results.get('urls', {})
        
        # Find the target view and related model
        target_view = next((v for v in views.get('crud', []) if v['name'] == 'create'), None)
        model_info = models.get('crud', [{}])[0] if models.get('crud') else {}
        
        # Prepare detailed context
        context = {
            "specification": spec,
            "models": models,
            "views": views,
            "urls": urls,
            "target_view": target_view,
            "model_info": model_info,
            "endpoints": [e for e in analysis_results.get("testable_endpoints", []) 
                         if e.get('view') == 'views.create']
        }
        
        # Get the actual view code if available
        view_code = ""
        if target_view and os.path.exists(target_view['file']):
            with open(target_view['file'], 'r') as f:
                view_code = f.read()
        
        # Get URL pattern for the view
        url_pattern = "/"
        try:
            # Try to find the URL pattern for the create view
            for app_name, url_list in urls.items():
                for url_info in url_list:
                    if isinstance(url_info, dict) and url_info.get('view') == 'views.create':
                        url_pattern = url_info.get('pattern', '/')
                        break
                if url_pattern != "/":
                    break
        except Exception as e:
            logger.warning(f"Error getting URL pattern: {e}")

        # Get template and format prompt
        prompt_template = PromptTemplates.GENERATE_API_TEST
        prompt = prompt_template.format(
            specification=spec,
            url_pattern=url_pattern,
            view_name="views.create",
            methods="['GET', 'POST']",
            parameters=json.dumps({"id": "int"} if "<int:" in json.dumps(urls) else {}),
            view_code=view_code,
            model_info=json.dumps(model_info, indent=2) if model_info else "{}",
            codebase_context=json.dumps(context, indent=2, default=str)
        )
        # console.print(prompt)
        # Generate test code with full context
        test_code = asyncio.run(client.generate(prompt, context))

        # Display the generated test
        console.print("\n[bold green]✅ Generated Test:[/bold green]")
        console.print(Syntax(test_code, "python"))
        
        # Save the test to a file
        test_dir = os.path.join(project_path, "tests", "generated")
        os.makedirs(test_dir, exist_ok=True)
        
        # Create a sanitized filename based on the test specification
        test_name = "test_" + "_".join(spec.lower().split()[:5]).replace(" ", "_")
        test_file = os.path.join(test_dir, f"{test_name}.py")
        
        try:
            with open(test_file, "w") as f:
                f.write(test_code)
            console.print(f"\n[green]✓ Test saved to: {test_file}[/green]")
        except Exception as e:
            console.print(f"[red]Error saving test file: {e}[/red]")
        
        # Add to generated tests list
        generated_tests.append({"code": test_code, "file": test_file})

        # Post-generation actions
        while True:
            console.print("\n[bold]Actions:[/bold]")
            console.print("  [1] Run locally")
            console.print("  [2] Run in Docker sandbox [recommended]")
            console.print("  [3] Run with coverage")
            console.print("  [4] Save test to file")
            console.print("  [5] Generate another test")
            console.print("  [6] Add edge cases")
            console.print("  [7] Exit to main menu")
            
            try:
                choice = Prompt.ask("\nChoose action [1-7]", default="2").strip()
                
                if choice == "1":
                    # Run locally
                    asyncio.run(_run_test(project_path, test_code, use_sandbox=False, with_coverage=False))
                elif choice == "2":
                    # Run in Docker sandbox
                    asyncio.run(_run_test(project_path, test_code, use_sandbox=True, with_coverage=False))
                elif choice == "3":
                    # Run with coverage
                    asyncio.run(_run_test(project_path, test_code, use_sandbox=True, with_coverage=True))
                elif choice == "4":
                    # Save test to file
                    _save_test(project_path, test_code)
                    console.print("\n[green]✓ Test saved successfully![/green]")
                elif choice == "5":
                    # Generate another test
                    break
                elif choice == "6":
                    # Add edge cases (placeholder for future implementation)
                    console.print("\n[blue]Edge case generation coming soon![/blue]")
                else:
                    # Exit to main menu
                    return
                    
                # After running tests, ask if user wants to save
                if choice in ["1", "2", "3"] and Confirm.ask("\nSave this test?", default=True):
                    _save_test(project_path, test_code)
                    
            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")
                if Confirm.ask("Show traceback?", default=False):
                    import traceback
                    console.print(traceback.format_exc())



async def _run_test(project_path: str, test_code: str, use_sandbox: bool = True, with_coverage: bool = False) -> Optional[TestResult]:
    """Run a test with the specified execution method"""
    console.print("\n[blue]Setting up test environment...[/blue]")
    
    try:
        if use_sandbox:
            console.print("🚀 Initializing Docker sandbox...")
        else:
            console.print("🏃 Starting local test execution...")
            
        if with_coverage:
            console.print("📊 Coverage analysis enabled")
            
        # Create a unique test name
        test_name = f"test_{int(time.time())}"
        
        # Run the test
        result = await run_test_interactive(project_path, test_code, test_name)
        
        # Display results
        if result.success:
            console.print("\n[green]✓ Test passed![/green]")
        else:
            console.print("\n[red]✗ Test failed![/red]")
            
        if result.error_analysis:
            console.print("\n[bold]Error Analysis:[/bold]")
            console.print(f"Type: {result.error_analysis.error_type}")
            console.print(f"Message: {result.error_analysis.error_message}")
            
            if result.error_analysis.suggested_fix:
                console.print("\n[bold]Suggested Fix:[/bold]")
                console.print(result.error_analysis.suggested_fix)
        
        if result.output:
            console.print("\n[bold]Test Output:[/bold]")
            console.print(Syntax(result.output, "text", theme="monokai", line_numbers=False))
            
        console.print(f"\n[dim]Duration: {result.duration:.2f}s[/dim]")
        
        return result
        
    except Exception as e:
        console.print(f"[red]Error running test: {str(e)}[/red]")
        if "Docker" in str(e) and "not running" in str(e).lower():
            console.print("\n[bold]Docker is not running.[/bold]")
            console.print("Please start Docker Desktop and try again, or use local execution.")
        return None


def _save_test(project_path: str, test_code: str) -> str:
    """Save test code to a file with improved error handling"""
    test_dir = os.path.join(project_path, "tests", "generated")
    os.makedirs(test_dir, exist_ok=True)
    
    # Create a sanitized filename based on the test code
    first_line = test_code.split("\n")[0].strip()
    test_name = "test_" + "".join(
        c if c.isalnum() else "_" 
        for c in first_line[:50]
    )
    
    # Ensure filename is valid
    test_name = "".join(c for c in test_name if c.isalnum() or c in "_-")
    if not test_name.endswith(".py"):
        test_name += ".py"
        
    # Handle duplicate filenames
    counter = 1
    base_name = test_name[:-3]  # Remove .py
    while os.path.exists(os.path.join(test_dir, test_name)):
        test_name = f"{base_name}_{counter}.py"
        counter += 1
        
    test_file = os.path.join(test_dir, test_name)
    
    try:
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_code)
        console.print(f"\n[green]✓ Test saved to: {test_file}[/green]")
        return test_file
    except Exception as e:
        error_msg = f"Error saving test file: {str(e)}"
        console.print(f"[red]{error_msg}[/red]")
        raise RuntimeError(error_msg) from e


@cli.command()
def version():
    """Show version information"""
    console.print("[bold]Test Authoring Agent v0.1.0[/bold]")


if __name__ == "__main__":
    cli()
