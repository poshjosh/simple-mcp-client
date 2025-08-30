"""
Command-line interface for the MCP Client.
"""

import asyncio
import dataclasses
import json
import logging
import sys
from dataclasses import dataclass
from typing import List, Dict, Optional, Union, Any, Callable, Coroutine

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

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

def to_dict(items: List[str]) ->  Dict[str, str]:
    result = {}
    for item in items:
        if '=' not in item:
            raise ValueError(f"Invalid format for env, with value: '{item}'. Expected env='key=value'.")
    return result

@dataclass(frozen=True)
class MCPServerConfig:
    id: str
    cmd: str
    arg: List[str]
    env: Optional[Dict[str, str]] = None

    @staticmethod
    def of_dict(data: dict[str, Any]) -> 'MCPServerConfig':
        return MCPServerConfig(id=data["id"], cmd=data["cmd"], arg=data["arg"], env=data.get("env"))

    def to_dict(self):
        return dataclasses.asdict(self)

def write_config_to_file(data: MCPServerConfig):
    with open('mcp_server_config.json', 'w', encoding='utf-8') as f:
        json.dump(data.to_dict(), f, ensure_ascii=False)

def read_config_from_file() -> Union[MCPServerConfig, None]:
    with open('mcp_server_config.json', "r", encoding='utf-8') as f:
        data = json.load(f)
        return None if not data else MCPServerConfig.of_dict(data)


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
        env=to_dict(env)
    )
    await asyncio.to_thread(write_config_to_file, mcp_server_config)
    
@cli.command()
async def list() -> None:
    """List the available tools for the current MCP server"""
    mcp_server_config: Union[MCPServerConfig, None] = None
    client = MCPClient()
    try:

        mcp_server_config: Union[MCPServerConfig, None] = await asyncio.to_thread(read_config_from_file)
        if not mcp_server_config:
            console.print(Panel("❌ No MCP server selected. Please use the 'use' command first.", style="red"))
            sys.exit(1)

        console.print(f"[dim]<{mcp_server_config.id}> Connecting... [/dim]")

        await client.connect(mcp_server_config.cmd, mcp_server_config.arg, mcp_server_config.env)

        console.print(f"[cyan]<{mcp_server_config.id}> Listing tools:[/cyan]")

        tool_call_result = await client.list_tools()
        console.print(f"<{mcp_server_config.id}> {tool_call_result}")

        console.print(Panel(f"✅ <{mcp_server_config.id}> Listing tools succeeded!", style="green"))
    except Exception as exc:
        logger.debug("", exc_info=exc)
        mcp_server_id = mcp_server_config.id if mcp_server_config else ""
        console.print(Panel(f"❌ <{mcp_server_id}> Listing tools failed: {exc}", style="red"))
    finally:
        try :
            if client.is_connected():
                await client.disconnect()
        finally:
            sys.exit(1)

@cli.command()
@click.argument("tool_name")
@click.option("--retries", "-r", default=0, help="Number of retries")
async def call(
        tool_name: str,
        retries: int = 0,
) -> None:
    """Call a tool on the current MCP server"""
    mcp_server_config: Union[MCPServerConfig, None] = None
    client = MCPClient()
    try:
        
        mcp_server_config: Union[MCPServerConfig, None] = await asyncio.to_thread(read_config_from_file)
        if not mcp_server_config:
            console.print(Panel("❌ No MCP server selected. Please use the 'use' command first.", style="red"))
            sys.exit(1)

        console.print(f"[dim]<{mcp_server_config.id}> Connecting... [/dim]")

        await client.connect(mcp_server_config.cmd, mcp_server_config.arg, mcp_server_config.env)

        console.print(f"[cyan]<{mcp_server_config.id}> Calling tool:[/cyan] {tool_name}")

        with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
        ) as progress:
            task = progress.add_task(f"<{mcp_server_config.id}> Calling tool... ", total=None)

            tool_call_result = await client.call_tool(tool_name, retry=retries)
            console.print(f"<{mcp_server_config.id}> {tool_call_result}")

            progress.remove_task(task)

        console.print(Panel(f"✅ <{mcp_server_config.id}> Tool call succeeded!", style="green"))
    except Exception as exc:
        logger.debug("", exc_info=exc)
        mcp_server_id = mcp_server_config.id if mcp_server_config else ""
        console.print(Panel(f"❌ <{mcp_server_id}> Tool call failed: {exc}", style="red"))
    finally:
        try :
            if client.is_connected():
                await client.disconnect()
        finally:    
            sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    # Convert async commands to sync
    def async_command(f):
        def wrapper(*args, **kwargs):
            return asyncio.run(f(*args, **kwargs))
        return wrapper

    # Apply async wrapper to commands
    for command in [use, list, call]:
        command.callback = async_command(command.callback)

    cli()


if __name__ == "__main__":
    main()