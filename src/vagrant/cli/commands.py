"""CLI command definitions using Click."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from vagrant import __version__
from vagrant.core.config import load_config, get_config_value, set_config_value
from vagrant.core.errors import VagrantError
from vagrant.http.client import HttpClient, HttpRequest
from vagrant.http.auth import AuthConfig
from vagrant.parser.openapi import parse_spec
from vagrant.storage.history import HistoryStorage, HistoryEntry
from vagrant.storage.environments import EnvironmentManager, Environment

console = Console()


import functools

def handle_errors(func):
    """Decorator to handle VagrantError exceptions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except VagrantError as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled.[/dim]")
            sys.exit(130)
    return wrapper


@click.group()
@click.version_option(version=__version__, prog_name="vagrant")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Vagrant - API Explorer.
    
    Explore any API without writing code. Point at an OpenAPI spec or URL,
    browse endpoints interactively, make requests, and understand the API.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.argument("spec_or_url")
@click.option("--env", "-e", help="Environment name to use")
@click.option("--base-url", "-b", help="Override base URL")
@click.pass_context
@handle_errors
def explore(ctx: click.Context, spec_or_url: str, env: str | None, base_url: str | None) -> None:
    """Launch TUI explorer for an API.
    
    SPEC_OR_URL can be a path to an OpenAPI spec file or a URL.
    """
    # Parse the spec
    spec = parse_spec(spec_or_url)
    
    console.print(f"[bold]{spec.title}[/bold] v{spec.version}")
    if spec.description:
        console.print(f"[dim]{spec.description}[/dim]")
    console.print()
    
    # Show server info
    if spec.servers:
        console.print("[bold]Servers:[/bold]")
        for server in spec.servers:
            desc = f" - {server.description}" if server.description else ""
            console.print(f"  {server.url}{desc}")
        console.print()
    
    # Show operations summary
    console.print(f"[bold]Operations:[/bold] {len(spec.operations)} endpoints")
    console.print()
    
    # Group by tags
    tags: dict[str, list] = {}
    for op in spec.operations:
        tag = op.tags[0] if op.tags else "default"
        if tag not in tags:
            tags[tag] = []
        tags[tag].append(op)
    
    for tag, ops in sorted(tags.items()):
        console.print(f"[bold cyan]{tag}[/bold cyan]")
        for op in ops:
            method_colors = {
                "GET": "green",
                "POST": "blue",
                "PUT": "yellow",
                "PATCH": "yellow",
                "DELETE": "red",
            }
            color = method_colors.get(op.method, "white")
            console.print(f"  [{color}]{op.method:7}[/{color}] {op.path}")
    
    console.print()
    console.print("[dim]TUI explorer coming soon. Use 'vagrant request' for now.[/dim]")


@cli.command("request")
@click.argument("method")
@click.argument("url")
@click.option("--data", "-d", help="Request body (JSON)")
@click.option("--header", "-H", "headers", multiple=True, help="Add header (key:value)")
@click.option("--env", "-e", "env_name", help="Environment name")
@click.option("--no-history", is_flag=True, help="Don't save to history")
@click.pass_context
@handle_errors
def request_cmd(
    ctx: click.Context,
    method: str,
    url: str,
    data: str | None,
    headers: tuple[str, ...],
    env_name: str | None,
    no_history: bool,
) -> None:
    """Make a single HTTP request.
    
    METHOD is the HTTP method (GET, POST, PUT, DELETE, etc.).
    URL is the full URL or path (if base_url is set in environment).
    """
    config = load_config()
    
    # Load environment if specified
    env = None
    env_mgr = EnvironmentManager()
    if env_name:
        env = env_mgr.get(env_name)
    elif config.default_environment and env_mgr.exists(config.default_environment):
        env = env_mgr.get(config.default_environment)
    
    # Build client
    client = HttpClient(
        timeout=config.timeout,
        verify_ssl=config.verify_ssl,
    )
    
    # Apply environment settings
    if env:
        if env.base_url:
            client.set_base_url(env.base_url)
        if env.auth:
            client.set_auth(env.auth)
        url = env_mgr.substitute(url, env)
    
    # Parse headers
    parsed_headers: dict[str, str] = {}
    for h in headers:
        if ":" in h:
            key, value = h.split(":", 1)
            parsed_headers[key.strip()] = value.strip()
    
    # Parse body
    body = None
    if data:
        try:
            body = json.loads(data)
        except json.JSONDecodeError:
            body = data  # Use as raw string
    
    # Build request
    req = HttpRequest(
        method=method.upper(),  # type: ignore
        url=url,
        headers=parsed_headers,
        body=body,
    )
    
    # Execute
    async def do_request():
        return await client.send(req)
    
    response = asyncio.run(do_request())
    
    # Display response
    status_color = "green" if response.is_success else "red"
    console.print(
        f"[{status_color}]{response.status_code} {response.status_text}[/{status_color}] "
        f"[dim]({response.elapsed_ms:.0f}ms, {response.size_bytes} bytes)[/dim]"
    )
    console.print()
    
    # Display headers if verbose
    if ctx.obj.get("verbose"):
        console.print("[bold]Response Headers:[/bold]")
        for key, value in response.headers.items():
            console.print(f"  {key}: {value}")
        console.print()
    
    # Display body
    if response.body:
        if isinstance(response.body, (dict, list)):
            json_str = json.dumps(response.body, indent=2)
            syntax = Syntax(json_str, "json", theme="monokai")
            console.print(syntax)
        else:
            console.print(response.body)
    
    # Save to history
    if not no_history:
        from datetime import datetime
        storage = HistoryStorage()
        entry = HistoryEntry(
            id=None,
            timestamp=datetime.now(),
            method=method.upper(),
            url=url,
            headers=parsed_headers,
            params={},
            body=data,
            status_code=response.status_code,
            response_body=json.dumps(response.body) if isinstance(response.body, (dict, list)) else str(response.body),
            elapsed_ms=response.elapsed_ms,
            environment=env_name,
        )
        storage.add(entry)


@cli.command()
@click.option("--limit", "-n", default=20, help="Number of entries to show")
@click.option("--search", "-s", help="Search by URL or method")
@handle_errors
def history(limit: int, search: str | None) -> None:
    """Show request history."""
    storage = HistoryStorage()
    
    if search:
        entries = storage.search(search)[:limit]
    else:
        entries = storage.list(limit=limit)
    
    if not entries:
        console.print("[dim]No history entries found.[/dim]")
        return
    
    table = Table(title=f"Request History (last {len(entries)})")
    table.add_column("ID", style="dim")
    table.add_column("Time", style="dim")
    table.add_column("Method")
    table.add_column("URL")
    table.add_column("Status")
    table.add_column("Time")
    
    method_colors = {
        "GET": "green",
        "POST": "blue",
        "PUT": "yellow",
        "PATCH": "yellow",
        "DELETE": "red",
    }
    
    for entry in entries:
        color = method_colors.get(entry.method, "white")
        status_color = "green" if 200 <= entry.status_code < 300 else "red"
        
        # Truncate URL if too long
        url = entry.url
        if len(url) > 50:
            url = url[:47] + "..."
        
        table.add_row(
            str(entry.id),
            entry.timestamp.strftime("%H:%M:%S"),
            f"[{color}]{entry.method}[/{color}]",
            url,
            f"[{status_color}]{entry.status_code}[/{status_color}]",
            f"{entry.elapsed_ms:.0f}ms",
        )
    
    console.print(table)


@cli.group()
def env() -> None:
    """Environment management commands."""


@env.command("list")
@handle_errors
def env_list() -> None:
    """List all environments."""
    manager = EnvironmentManager()
    envs = manager.list()
    
    if not envs:
        console.print("[dim]No environments configured.[/dim]")
        console.print("[dim]Create one with: vagrant env create <name>[/dim]")
        return
    
    config = load_config()
    
    console.print("[bold]Environments:[/bold]")
    for name in envs:
        env = manager.get(name)
        default = " [dim](default)[/dim]" if name == config.default_environment else ""
        console.print(f"  [cyan]{name}[/cyan]{default}")
        if env.base_url:
            console.print(f"    [dim]URL: {env.base_url}[/dim]")


@env.command("create")
@click.argument("name")
@click.option("--base-url", "-u", help="Base URL for API")
@click.option("--auth-type", "-a", type=click.Choice(["bearer", "basic", "apikey"]), help="Auth type")
@click.option("--token", "-t", help="Auth token or API key")
@handle_errors
def env_create(name: str, base_url: str | None, auth_type: str | None, token: str | None) -> None:
    """Create a new environment."""
    manager = EnvironmentManager()
    
    if manager.exists(name):
        console.print(f"[red]Environment '{name}' already exists.[/red]")
        sys.exit(1)
    
    auth = None
    if auth_type and token:
        if auth_type == "bearer":
            auth = AuthConfig(type="bearer", credentials={"token": token})
        elif auth_type == "apikey":
            auth = AuthConfig(type="apikey", credentials={"key": token})
        elif auth_type == "basic":
            # Expect token as user:pass
            auth = AuthConfig(type="basic", credentials={"username": token.split(":")[0], "password": token.split(":")[-1]})
    
    env = Environment(
        name=name,
        base_url=base_url or "",
        auth=auth,
    )
    manager.save(env)
    console.print(f"[green]Created environment '{name}'[/green]")


@env.command("delete")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this environment?")
@handle_errors
def env_delete(name: str) -> None:
    """Delete an environment."""
    manager = EnvironmentManager()
    manager.delete(name)
    console.print(f"[green]Deleted environment '{name}'[/green]")


@env.command("show")
@click.argument("name")
@handle_errors
def env_show(name: str) -> None:
    """Show environment details."""
    manager = EnvironmentManager()
    env = manager.get(name)
    
    console.print(f"[bold]Environment: {env.name}[/bold]")
    console.print()
    
    if env.base_url:
        console.print(f"[bold]Base URL:[/bold] {env.base_url}")
    
    if env.auth:
        console.print(f"[bold]Auth Type:[/bold] {env.auth.type}")
    
    if env.variables:
        console.print("[bold]Variables:[/bold]")
        for key, value in env.variables.items():
            display_value = value if not key.startswith("secret") else "****"
            console.print(f"  {key}: {display_value}")


@env.command("set-var")
@click.argument("env_name")
@click.argument("key")
@click.argument("value")
@handle_errors
def env_set_var(env_name: str, key: str, value: str) -> None:
    """Set a variable in an environment."""
    manager = EnvironmentManager()
    env = manager.get(env_name)
    env.variables[key] = value
    manager.save(env)
    console.print(f"[green]Set {key} in '{env_name}'[/green]")


@cli.group()
def config() -> None:
    """Configuration management commands."""


@config.command("get")
@click.argument("key")
@handle_errors
def config_get(key: str) -> None:
    """Get a config value."""
    value = get_config_value(key)
    console.print(f"{key}: {value}")


@config.command("set")
@click.argument("key")
@click.argument("value")
@handle_errors
def config_set(key: str, value: str) -> None:
    """Set a config value."""
    set_config_value(key, value)
    console.print(f"[green]Set {key} = {value}[/green]")


@config.command("list")
@handle_errors
def config_list() -> None:
    """List all config values."""
    cfg = load_config()
    console.print("[bold]Configuration:[/bold]")
    for key, value in cfg.to_dict().items():
        console.print(f"  {key}: {value}")


if __name__ == "__main__":
    cli()
