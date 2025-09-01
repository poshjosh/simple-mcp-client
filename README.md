# simple-mcp-client

A simple Model Context Protocol (MCP) client for working with MCP servers.

## Usage

### Setup

- Install by running [this script](./shell/install.sh).
- Activate by running `source .venv/bin/activate || exit 1` in the project root directory.
- Get help by running `mcx --help` from the same shell where you activated the project.

### mcx use (select an mcp server)

```shell
mcx use <SERVER_ALIAS> --cmd=<MCP_SERVER_COMMAND> --arg=<MCP_SERVER_ARGUMENT> --env='<KEY>=<VALUE>'
```

Provide a value for:

- `<SERVER_ALIAS>`: the alias you want to identify this server by.
- `<MCP_SERVER_COMMAND>`: the mcp server command.
- `<MCP_SERVER_ARGUMENT>`: the mcp server command argument (may be multiple).
- `<KEY>=<VALUE>`: mcp server environment (may be multiple)

### mcx call (call a tool on the selected mcp server)

```shell
mcx call "<TOOL_NAME>" --arg='<KEY=VALUE>'
```

- Provide a value for `<TOOL_NAME>`: the name of the tool you want to call.
- Provide a value for `<KEY=VALUE>`: the tool argument (may be multiple).

## Examples

### mcx use (select an mcp server)

```shell
mcx use automate-ideas-to-social --cmd=docker \
  --arg="run" --arg="-u" --arg="0" --arg="-i" --arg="--rm" \
  --arg="-v" --arg="/var/run/docker.sock:/var/run/docker.sock" \
  --arg="-e" --arg="APP_PROFILES=docker" \
  --arg="-e" --arg="USER_HOME=<YOUR HOME DIRECTORY>" \
  --arg="poshjosh/aideas-mcp:0.0.1"
```

- Provide a value for `<YOUR HOME DIRECTORY>`: the path to your home directory.

### mcx call (call a tool on the selected mcp server)

```shell
mcx call list_agents --fmt='content[0].text'
```

### mcx list (list all tools on the selected mcp server)

```shell
mcx list --fmt='tools[*].name'
```

## Development

- Run [this script](./shell/install.dev.sh).


