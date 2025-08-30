# simple-mcp-client

A simple Model Context Protocol (MCP) client for working with MCP servers.

## Usage

- Install by running [this script](./shell/install.sh).

### mcx use (select an mcp server)

```shell
mcx use <SERVER_ALIAS> --cmd=node --arg=/build/index.js
```

- Provide a value for `<SERVER_ALIAS>`: the alias you want to identify this server by.


### mcx call (call a tool on the selected mcp server)

```shell
mcx call "<TOOL_NAME>" --arg='key==val' --arg='key1==val1'
```

- Provide a value for `<TOOL_NAME>`: the name of the tool you want to call.

## Development

- Run [this script](./shell/install.dev.sh).


