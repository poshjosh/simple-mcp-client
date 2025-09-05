"""
Command-line interface for the MCP Client.
"""

import asyncio
import json
import logging
import sys
from typing import List, Dict, Optional, Any, Callable, Coroutine

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .mcp_config import MCPServerConfig, write_config_to_file, read_config_from_file
from .mcp_client import MCPClient

console = Console()
logger = logging.getLogger(__name__)

def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

@click.group()
@click.option("-v", "--verbose", help="Enable verbose logging", is_flag=True)
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """A Python MCP client for working with MCP servers"""
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

@cli.command()
@click.argument("mcp_server_id")
@click.option("-c", "--cmd", type=str, help="The command to pass to the MCP server")
@click.option("-a", "--arg", type=str, help="An argument to pass to the MCP server command", multiple=True)
@click.option("-e", "--env", type=str, help="An environment to pass to the MCP server command", multiple=True)
async def use(mcp_server_id: str, cmd: str, arg: List[str], env: List[str]) -> None:
    """Use a server"""
    mcp_server_config = MCPServerConfig(
        id=mcp_server_id if mcp_server_id else "mcp-server",
        cmd=cmd,
        arg=arg,
        env=_to_dict(env)
    )
    await asyncio.to_thread(write_config_to_file, mcp_server_config)
    console.print(Panel(f"✅ Using <{mcp_server_config.id}> MCP Server!", style="green"))
    
@cli.command()
@click.option("-f", "--fmt", type=str, help="The format to apply to the output from the list command")
@click.option("--quit", help="Quit the mcp server after this operation", is_flag=True)
async def list(fmt: str = None, quit: bool = False) -> None:
    """List the available tools for the current MCP server"""
    client = MCPClient()
    try:
        name = "list"
        async def _list_tool(mcp_server_config: MCPServerConfig):
            tool_call_result = await client.list_tools()
            if tool_call_result and fmt:
                from .output_formatter import format_dict_safe
                tool_call_result = format_dict_safe(fmt, tool_call_result, json.dumps(tool_call_result, indent=2))
            console.print(f"<{mcp_server_config.id}> {tool_call_result}")

        await _execute(name, client, _list_tool)

    finally:
        try :
            if quit and client.is_connected():
                await client.disconnect()
        finally:
            sys.exit(1)

@cli.command()
@click.argument("tool_name")
@click.option("-a", "--arg", type=str, help="An argument to pass to the MCP server tool call", multiple=True)
@click.option("-r", "--retries", default=0, help="Number of retries")
@click.option("-f", "--fmt", type=str, help="The format to apply to the output from the tool call")
@click.option("--quit", help="Quit the mcp server after this operation", is_flag=True)
async def call(
        tool_name: str,
        arg: List[str],
        retries: int = 0,
        fmt: str = None,
        quit: bool = False
) -> None:
    """Call a tool on the current MCP server"""
    client = MCPClient()
    try:
        name = f"call {tool_name}"
        async def _call_tool(mcp_server_config: MCPServerConfig):
            arguments = _to_dict(arg) if arg else {}
            console.print(f"[cyan]<{mcp_server_config.id}> {name}, args: {arguments}[/cyan]")
            tool_call_result = await client.call_tool(tool_name, arguments, retry=retries)
            if tool_call_result and fmt:
                from .output_formatter import format_dict_safe
                tool_call_result = format_dict_safe(fmt, tool_call_result, json.dumps(tool_call_result, indent=2))
            console.print(f"<{mcp_server_config.id}> {tool_call_result}")

        await _execute(name, client, _call_tool)

    finally:
        try :
            if quit and client.is_connected():
                await client.disconnect()
        finally:    
            sys.exit(1)

@cli.command()
async def quit() -> None:
    """Quit the current MCP server"""
    try:
        client = MCPClient()
        def _quit(_):
            return client.disconnect()
        await _execute("Quit", client, _quit)
    finally:
        sys.exit(1)

def _to_dict(items: List[str]) ->  Dict[str, str]:
    result = {}
    for item in items:
        if '=' not in item:
            raise ValueError(f"Invalid format for: '{item}'. Expected 'key=value'.")
        key, value = item.split('=', 1)
        if key in result:
            existing = result[key]
            arr = existing if isinstance(existing, List) else [existing]
            arr.append(value)
            value = arr
        result[key] = value
    return result

async def _execute(name: str, client: MCPClient, action: Callable[[MCPServerConfig], Coroutine[Any, Any, Any]]):
    mcp_server_config: Optional[MCPServerConfig] = None
    try:
        mcp_server_config = await _require_mcp_server_config()

        console.print(f"[dim]<{mcp_server_config.id}> Connecting... [/dim]")

        await client.connect(mcp_server_config.cmd, mcp_server_config.arg, mcp_server_config.env)

        console.print(f"[cyan]<{mcp_server_config.id}> {name}[/cyan]")

        await _with_progress(f"<{mcp_server_config.id}> ... please wait ", action, mcp_server_config)

        console.print(Panel(f"✅ <{mcp_server_config.id}> {name} succeeded!", style="green"))

    except Exception as exc:
        logger.debug("", exc_info=exc)
        mcp_server_id = mcp_server_config.id if mcp_server_config else ""
        console.print(Panel(f"❌ <{mcp_server_id}> {name} failed: {exc}", style="red"))

async def _with_progress(description: str,
                         action: Callable[[MCPServerConfig], Coroutine[Any, Any, Any]],
                         config: MCPServerConfig) -> Any:
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
    ) as progress:
        task = progress.add_task(description, total=None)
        try:
            return await action(config)
        finally:
            progress.remove_task(task)

async def _require_mcp_server_config() -> MCPServerConfig:
    mcp_server_config: Optional[MCPServerConfig] = await asyncio.to_thread(read_config_from_file)
    if not mcp_server_config:
        console.print(Panel("❌ No MCP server selected. Please first use the 'use' command to select an MCP server.", style="red"))
        sys.exit(1)
    return mcp_server_config


def main() -> None:
    """Main entry point for the CLI."""
    # Convert async commands to sync
    def async_command(f):
        def wrapper(*args, **kwargs):
            return asyncio.run(f(*args, **kwargs))
        return wrapper

    # Apply async wrapper to commands
    for command in [use, list, call, quit]:
        command.callback = async_command(command.callback)

    cli()


if __name__ == "__main__":
    main()