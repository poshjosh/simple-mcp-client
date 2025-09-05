import dataclasses
import json
from dataclasses import dataclass
from typing import List, Dict, Optional, Union, Any


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
