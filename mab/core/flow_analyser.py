"""
core/flow_analyser.py
─────────────────────
Reads all agent.md files in a project and builds a NetworkX directed graph
suitable for rendering in the flow visualiser panel.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import networkx as nx  # type: ignore[import-untyped]
    NX_AVAILABLE = True
except ImportError:
    NX_AVAILABLE = False
    nx = None  # type: ignore[assignment]

# Colour scheme by agent type
NODE_COLOURS: dict[str, str] = {
    "orchestrator": "#3b82d4",
    "worker": "#6b7280",
    "specialist": "#7c5cd8",
    "gateway": "#22c55e",
    "hybrid": "#f59e0b",
}

NODE_SHAPES: dict[str, str] = {
    "orchestrator": "round_rect",
    "worker": "rect",
    "specialist": "diamond",
    "gateway": "hexagon",
    "hybrid": "ellipse",
}

# Edge colours by communication protocol
EDGE_COLOURS: dict[str, str] = {
    "direct-call": "#1f2328",
    "message-queue": "#f59e0b",
    "rest": "#3b82d4",
    "grpc": "#7c5cd8",
    "event-bus": "#22c55e",
}


@dataclass
class NodeData:
    name: str
    role: str
    agent_type: str
    trigger: str
    completion_pct: int
    colour: str = "#6b7280"
    shape: str = "rect"
    # Extra fields for rich card rendering
    memory_type: str = ""
    deployment_target: str = ""
    reasoning_strategy: str = ""
    tools: str = ""
    authentication: str = ""


@dataclass
class EdgeData:
    source: str
    target: str
    protocol: str = "direct-call"
    handoff_conditions: str = ""
    colour: str = "#1f2328"


@dataclass
class FlowGraph:
    nodes: list[NodeData] = field(default_factory=list)
    edges: list[EdgeData] = field(default_factory=list)
    raw_graph: Any = None  # networkx.DiGraph when available


def build_graph(project_root: Path) -> FlowGraph:
    """
    Load all agent.md files from <project_root>/agents/** and build a FlowGraph.
    """
    from core.agent_parser import load as parse_agent  # local import avoids circulars

    agents_dir = project_root / "agents"
    if not agents_dir.exists():
        return FlowGraph()

    agent_data_list = []
    for agent_md in sorted(agents_dir.rglob("agent.md")):
        try:
            agent_data_list.append(parse_agent(agent_md))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping %s — parse error: %s", agent_md, exc)

    return _build_from_agent_data(agent_data_list)


def _build_from_agent_data(agent_data_list) -> FlowGraph:  # type: ignore[no-untyped-def]
    graph = FlowGraph()

    # Build nodes
    for ad in agent_data_list:
        atype = ad.agent_type.lower()
        node = NodeData(
            name=ad.name or "unnamed",
            role=ad.role,
            agent_type=atype,
            trigger=ad.trigger,
            completion_pct=ad.completion_pct,
            colour=NODE_COLOURS.get(atype, "#6b7280"),
            shape=NODE_SHAPES.get(atype, "rect"),
            memory_type=ad.fields.get("memory_type", ""),
            deployment_target=ad.fields.get("deployment_target", ""),
            reasoning_strategy=ad.fields.get("reasoning_strategy", ""),
            tools=ad.fields.get("tools", ""),
            authentication=ad.fields.get("authentication", ""),
        )
        graph.nodes.append(node)

    # Build name → agent_data lookup
    name_map = {ad.name: ad for ad in agent_data_list}

    # Build edges
    for ad in agent_data_list:
        protocol = ad.communication_protocol.lower().replace(" ", "-")
        edge_colour = EDGE_COLOURS.get(protocol, "#1f2328")
        for target_name in ad.communicates_with:
            target_name = target_name.strip()
            if not target_name:
                continue
            # Auto-register unknown target as a stub node
            if target_name not in {n.name for n in graph.nodes}:
                graph.nodes.append(
                    NodeData(
                        name=target_name,
                        role="(external / undefined)",
                        agent_type="worker",
                        trigger="",
                        completion_pct=0,
                        colour="#d1d5db",
                        shape="rect",
                    )
                )
            edge = EdgeData(
                source=ad.name,
                target=target_name,
                protocol=protocol or "direct-call",
                handoff_conditions=ad.handoff_conditions,
                colour=edge_colour,
            )
            graph.edges.append(edge)

    # Optionally build networkx graph
    if NX_AVAILABLE:
        G = nx.DiGraph()
        for n in graph.nodes:
            G.add_node(
                n.name,
                role=n.role,
                agent_type=n.agent_type,
                colour=n.colour,
                shape=n.shape,
                completion_pct=n.completion_pct,
                memory_type=n.memory_type,
                deployment_target=n.deployment_target,
                reasoning_strategy=n.reasoning_strategy,
                authentication=n.authentication,
            )
        for e in graph.edges:
            G.add_edge(
                e.source,
                e.target,
                protocol=e.protocol,
                colour=e.colour,
                handoff_conditions=e.handoff_conditions,
            )
        graph.raw_graph = G

    return graph
