# engine/agents/__init__.py
"""
Multi-Agent AI Framework for Intellect RAG Assistant.
Contains Supervisor Agent and specialized sub-agents.
"""
from engine.agents.supervisor import supervisor_agent

__all__ = ["supervisor_agent"]
