#!/usr/bin/env python3
"""
Simple MCP (Model Context Protocol) Client

A client that can:
1. Connect to an MCP server using command, args, and env parameters
2. Call tools on the MCP server with tool_name and args
"""

import json
import asyncio
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Base exception for MCP Client errors."""
    def __init__(self, *args):
        super().__init__(*args)
        self.message = args[0] if args and len(args) > 0 else None

    def __str__(self):
        class_name = type(self).__name__
        return f"{class_name}: {self.message}" if self.message else class_name

class NotConnectedError(MCPClientError):
    def __init__(self, *args):
        super().__init__(*args)

class ConnectionFailedError(MCPClientError):
    def __init__(self, *args):
        super().__init__(*args)

class MCPServerError(MCPClientError):
    def __init__(self, *args):
        super().__init__(*args)
        self.raw = args[1] if args and len(args) > 1 else None

class MCPServerDidNotRespondError(MCPClientError):
    def __init__(self, *args):
        super().__init__(*args)
        self.raw = args[1] if args and len(args) > 1 else None


@dataclass
class MCPMessage:
    """Represents an MCP protocol message"""
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class ErrorResolver:
    def resolve_str(self, text: str) -> Optional[MCPServerError]:
        if not text:
            return None
        if re.search(r'\berror\b', text, re.IGNORECASE):
            return MCPServerError(text, text)
        return None

    def resolve_dict(self, response: Dict[str, Any]) -> Optional[MCPServerError]:
        if "error" in response:
            error = response["error"]
            return MCPServerError(error.get('message', 'Unexpected error'), error)
        return None

@dataclass(frozen=True)
class MCPServerResponse:
    lines: list[str]
    errors: list[MCPServerError]
    success: Optional[Dict[str, Any]] = None
    error: Optional[MCPServerError] = None

class MCPServerResponseParser:
    def __init__(self, error_resolver: ErrorResolver = ErrorResolver()):
        self.__error_resolver = error_resolver

    async def parse(self, source: asyncio.StreamReader, encoding: str) -> MCPServerResponse:
        # Wait for response
        # The response comprises all the output lines from the MCP server.
        # Only the last line of the multi-line output is the actual JSON response.
        response_lines: list[str] = []
        response_errors: list[MCPServerError] = []
        success_response: Optional[Dict[str, Any]] = None
        error_response: Optional[MCPServerError] = None

        async for response_line in source:
            response_line = response_line.decode(encoding).strip()
            response_dict = MCPServerResponseParser._parse_response(response_line)
            is_response = False if response_dict is None else response_dict.get("result", None) or response_dict.get("error", None)
            error = self.__error_resolver.resolve_str(response_line) \
                if response_dict is None else self.__error_resolver.resolve_dict(response_dict)
            if error:
                response_errors.append(error)
            response_lines.append(response_line)

            # self.process.stdout.at_eof() did not work as expected here,
            # so we break when we see a JSON line with the expected result format.
            if is_response:
                if error:
                    error_response = error
                else:
                    success_response = response_dict
                break

        return MCPServerResponse(
            lines=response_lines,
            errors=response_errors,
            success=success_response,
            error=error_response
        )

    @staticmethod
    def _parse_response(text: str) -> Union[Dict[str, Any], None]:
        try :
            json_dict = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not json_dict or not isinstance(json_dict, dict):
            return None
        return json_dict


class RetryBelowLimit:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.attempts = 0

    def should_retry(self, _) -> bool:
        if self.attempts < self.max_retries:
            self.attempts += 1
            return True
        return False


class MCPClient:
    """Simple MCP Client implementation"""

    def __init__(self, server_response_parser: Optional[MCPServerResponseParser] = MCPServerResponseParser()):
        # Model Context Protocol uses utf-8 encoding
        self.encoding = 'utf-8'
        self.process = None
        self.request_id = 0
        self.capabilities = {}
        self.connected = False
        self.server_response_parser = server_response_parser

    def is_connected(self) -> bool:
        """Check if connected to MCP server"""
        return self.connected

    async def connect(self, command: str, args: List[str], env: Dict[str, Any]):
        """
        Connect to MCP server by spawning a process

        Args:
            command: The command to run the MCP server (e.g., 'python', 'node')
            args: List of arguments for the command (e.g., ['server.py'] or ['server.js'])
            env: Environment variables for the server process
        """
        try:
            logger.info(f"Connecting to MCP server: {command} {' '.join(args)}")

            # Start the MCP server process
            self.process = await asyncio.create_subprocess_exec(
                command, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**env} if env else None
            )

            # Initialize the MCP connection
            await self._initialize()
            self.connected = True

            logger.info("Successfully connected to MCP server")

        except Exception as exc:
            await self._terminate_process_and_set_to_none()
            raise ConnectionFailedError from exc

    async def disconnect(self):
        """Disconnect from MCP server"""
        logger.info("Disconnecting from MCP server")
        await self._terminate_process_and_set_to_none()
        self.connected = False
        logger.info("Disconnected from MCP server")

    async def call_tool(self,
                        tool_name: str,
                        args=None,
                        retry: Union[int, Callable[[Dict[str, Any]], bool]] = 2) -> Dict[str, Any]:
        """
        Call a tool on the MCP server

        Args:
            tool_name: Name of the tool to call
            args: Arguments to pass to the tool
            retry: A callable that takes the response and returns True if the call should be retried

        Returns:
            The result from the tool call
        """

        if args is None:
            args = {}

        logger.info(f"Calling tool '{tool_name}' with args: {args}")

        message = MCPMessage(
            id=self._next_id(),
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": args
            }
        )

        response = await self.send_message(message, retry)
        return response.get("result", {})

    async def list_tools(self) -> Dict[str, Any]:
        """List available tools (helper method)"""

        logger.info("Listing tools")
        message = MCPMessage(
            id=self._next_id(),
            method="tools/list"
        )

        response = await self.send_message(message)
        return response.get("result", {})

    async def send_message(self, message: MCPMessage, retry: Union[int, Callable[[Dict[str, Any]], bool]] = 0) -> Dict[str, Any]:
        """Send a message to the server and wait for response"""
        if not self.process or not self.connected:
            raise NotConnectedError()

        if isinstance(retry, int):
            retry = RetryBelowLimit(retry).should_retry

        while True:
            response = await self._send_message(message)
            if not retry(response):
                break
            logger.debug("Retrying message send due to retry condition")
        return response

    async def _initialize(self):
        """Initialize the MCP connection"""
        # Send initialize request
        init_message = MCPMessage(
            id=self._next_id(),
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {}
                },
                "clientInfo": {
                    "name": "simple-mcp-client",
                    "version": "1.0.0"
                }
            }
        )

        response = await self._send_message(init_message)
        self.capabilities = response.get("result", {}).get("capabilities", {})
        logger.debug(f"Server capabilities: {self.capabilities}")

        # Send initialized notification
        initialized_message = MCPMessage(
            method="notifications/initialized"
        )
        await self._send_message(initialized_message)

    async def _send_message(self, message: MCPMessage) -> Dict[str, Any]:
        """Send a message to the server and wait for response"""
        logger.debug("Sending message... ")
        self.process.stdin.write(self._parse_message(message, self.encoding))
        logger.debug("Draining stdin... ")
        await self.process.stdin.drain()

        # For notifications (no id), don't wait for response
        if message.id is None:
            logger.debug(
                "Will not wait for response because an id was not specified for the sent message")
            return { 'result': None }

        logger.debug("Parsing response... ")

        response = await self.server_response_parser.parse(self.process.stdout, self.encoding)

        response_text = '\n'.join(response.lines)

        if response.error:
            logger.error(f"Raw response:\n{response_text}")
            raise response.error
        elif response.errors:
            logger.error(f"Raw response:\n{response_text}")
            raise MCPServerError(f"Response contained {len(response.errors)} errors, see logs for details.")
        elif not response.lines or not response.success:
            logger.error(f"Raw response:\n{response_text}")
            raise MCPServerDidNotRespondError()
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Raw response:\n{response_text}")
            # else:
            #     logger.info(f"Response: {json.dumps(response.success, indent=2)}")

        return response.success

    @staticmethod
    def _parse_message(message: MCPMessage, encoding: str) -> bytes:
        """Converts an MCPMessage to its JSON string representation in bytes"""
        message_dict = {
            "jsonrpc": message.jsonrpc
        }

        if message.id is not None:
            message_dict["id"] = message.id
        if message.method is not None:
            message_dict["method"] = message.method
        if message.params is not None:
            message_dict["params"] = message.params

        logger.debug(f"Message: {json.dumps(message_dict, indent=2)}")

        # Send message
        message_json = json.dumps(message_dict) + "\n"

        return message_json.encode(encoding)

    async def _terminate_process_and_set_to_none(self):
        if self.process:
            try :
                self.process.terminate()
                await self.process.wait()
            except Exception as exc:
                logger.debug("Failed to terminate MCPClient process", exc_info=exc)
            finally:
                self.process = None

    def _next_id(self) -> str:
        """Generate next request ID"""
        self.request_id += 1
        return str(self.request_id)

async def _example_usage():
    logging.basicConfig(level=logging.INFO)

    """Example usage of the MCP client"""
    client = MCPClient()

    try:
        # Example 1: Connect to a Python MCP server
        await client.connect(
            command = 'docker',
            args = [
                "run", "-u", "0", "-i", #"--rm",
                "-v", "/var/run/docker.sock:/var/run/docker.sock",
                "-e", "APP_PROFILES=docker",
                "-e", f"USER_HOME={Path.home()}",
                "poshjosh/aideas-mcp:0.0.1"
            ],
            env={}
        )

        # List available tools
        list_tools_result = await client.list_tools()
        tools: List[Dict[str, Any]] = list_tools_result.get('tools', [])
        logger.debug('\n'.join([f"\t- {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}" for tool in tools]))
        for tool in tools:
            logger.info(f"\t- {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")

        if not tools:
            logger.warning("No tools found")
            return

        # Example tool call | in this case, specific to the aideas-mcp server
        tool_name = tools[0].get('name')

        def parse_aideas_response_text(mcp_server_result: Dict[str, Any]) -> Dict[str, Any]:
            result_text = mcp_server_result.get('content', [{}])[0].get('text', '{}')
            return json.loads(result_text)

        tool_call_result = await client.call_tool(tool_name)
        agents: list[str] = parse_aideas_response_text(tool_call_result).get('agents', [])
        logger.info(f"Agents:\n{agents}")

        if not agents:
            logger.warning("No agents found")
            return

        tool_call_result = await client.call_tool("get_agent_config", args={"agent_name": agents[0]})
        logger.debug(f"{agents[0]} agent config result:\n{tool_call_result}")

        tool_call_result = await client.call_tool("create_automation_task", args={
            "agents": ["test-agent", "test-log"]
        })
        logger.debug(f"create_automation_task result:\n{tool_call_result}")
        task_id = parse_aideas_response_text(tool_call_result).get('task_id', None)
        logger.info(f"Task ID: {task_id}")

        tool_call_result = await client.call_tool("list_tasks", args={
            "filter_by_status": "RUNNING"
        })
        logger.debug(f"list_tasks result:\n{tool_call_result}")

        if not task_id:
            logger.warning("No task_id was returned")
            return

        def retry_if_status_is_running(response: Dict[str, Any]) -> bool:
            status = parse_aideas_response_text(response.get('result', {})).get('status', None)
            return status == 'RUNNING'

        tool_call_result = await client.call_tool("get_task_status", args={
            "task_id": task_id
        }, retry=retry_if_status_is_running)
        task_status = parse_aideas_response_text(tool_call_result).get('status', None)
        logger.info(f"Status: {task_status}, task ID: {task_id}")

    except Exception as exc:
        logger.error(f"{exc}", exc_info=exc)

    finally:
        await client.disconnect()

if __name__ == "__main__":
    # Run the example
    asyncio.run(_example_usage())