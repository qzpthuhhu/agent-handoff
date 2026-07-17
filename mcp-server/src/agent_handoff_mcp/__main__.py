"""python -m agent_handoff_mcp 入口,方便直接跑。"""
from .server import mcp

if __name__ == "__main__":
    mcp.run()
