"""
ui/components/flow_canvas.py
─────────────────────────────
Clean schematic visualiser for the multi-agent flow.
Renders a simple directed diagram:
  - Nodes are plain labelled boxes, shaped/coloured by agent type
  - Arrows carry the protocol and direction
  - A compact side legend explains types and protocols
Supports zoom, pan, PNG export.
"""

from __future__ import annotations

import io
import logging
import textwrap
from typing import Any

import customtkinter as ctk
from PIL import Image, ImageTk  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    import networkx as nx
    _RENDER_AVAILABLE = True
except ImportError:
    _RENDER_AVAILABLE = False

# ── Visual constants ──────────────────────────────────────────────────────────
BG          = "#ffffff"
GRID_COL    = "#f0f2f5"
NODE_W      = 2.4      # node box width  (data units)
NODE_H      = 0.9      # node box height
FONT_NAME   = 10       # agent name font pt
FONT_ROLE   = 7.5      # role/subtitle font pt
FONT_EDGE   = 7        # edge label font pt

# Type → (fill colour, border colour)
TYPE_STYLE: dict[str, tuple[str, str]] = {
    "orchestrator": ("#1e40af", "#1e3a8a"),   # deep blue
    "worker":       ("#374151", "#1f2328"),   # dark grey
    "specialist":   ("#5b21b6", "#4c1d95"),   # purple
    "gateway":      ("#065f46", "#064e3b"),   # dark green
    "hybrid":       ("#92400e", "#78350f"),   # amber-brown
}
DEFAULT_STYLE = ("#4b5563", "#374151")

# Protocol → dash pattern
PROTOCOL_DASH: dict[str, tuple] = {
    "direct-call":   (None, 1.8),   # solid
    "message-queue": ((6, 3), 1.6),
    "rest":          ((8, 2), 1.8),
    "grpc":          ((2, 2), 1.4),
    "event-bus":     ((10, 3, 2, 3), 1.6),
}
DEFAULT_DASH = (None, 1.6)

# Protocol → line colour (subtle, not per-agent-colour)
PROTOCOL_COLOUR: dict[str, str] = {
    "direct-call":   "#1f2328",
    "message-queue": "#b45309",
    "rest":          "#1d4ed8",
    "grpc":          "#6d28d9",
    "event-bus":     "#047857",
}


class FlowCanvas(ctk.CTkFrame):
    """Schematic agent-flow canvas embedded in a CTk frame."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._graph_data: Any = None
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._drag_start: tuple[int, int] | None = None
        self._img_ref: ImageTk.PhotoImage | None = None
        self._show_labels = True

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        if _RENDER_AVAILABLE:
            self._build_canvas()
        else:
            ctk.CTkLabel(
                self,
                text="Install matplotlib and networkx to enable the flow visualiser.",
                wraplength=300,
            ).grid(row=0, column=0, padx=20, pady=20)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_canvas(self) -> None:
        toolbar = ctk.CTkFrame(self, height=34, corner_radius=0, fg_color="#f7f8fa")
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_columnconfigure(5, weight=1)

        for col, (label, cmd) in enumerate([
            ("＋", self._zoom_in),
            ("－", self._zoom_out),
            ("⟳", self._reset),
            ("⊞", self._toggle_labels),
            ("💾", self._export_png),
        ]):
            ctk.CTkButton(
                toolbar, text=label, width=30, height=26,
                fg_color="transparent", hover_color="#e5e7eb",
                text_color="#1f2328", font=ctk.CTkFont(size=13),
                command=cmd,
            ).grid(row=0, column=col, padx=2, pady=4)

        self._status_var = ctk.StringVar(value="No project loaded")
        ctk.CTkLabel(
            toolbar, textvariable=self._status_var,
            font=ctk.CTkFont(size=11), text_color="#57606a",
        ).grid(row=0, column=6, padx=8, sticky="e")

        self._canvas = ctk.CTkCanvas(
            self, bg=BG, highlightthickness=0, cursor="fleur"
        )
        self._canvas.grid(row=1, column=0, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)

        self._canvas.bind("<ButtonPress-1>", self._drag_start_handler)
        self._canvas.bind("<B1-Motion>", self._drag_handler)
        self._canvas.bind("<ButtonRelease-1>", self._drag_end_handler)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Configure>", lambda _e: self._redraw())

    # ── Public API ────────────────────────────────────────────────────────────

    def render(self, graph_data: Any) -> None:
        self._graph_data = graph_data
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._redraw()

    def clear(self) -> None:
        self._graph_data = None
        if _RENDER_AVAILABLE:
            self._canvas.delete("all")
            self._status_var.set("No project loaded")

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _redraw(self) -> None:
        if not _RENDER_AVAILABLE or self._graph_data is None:
            return
        graph = self._graph_data
        if not graph.nodes:
            self._status_var.set("No agents found in project")
            return
        try:
            img = self._render_to_image(graph)
            self._display_image(img)
            self._status_var.set(
                f"{len(graph.nodes)} agent(s)  ·  {len(graph.edges)} connection(s)"
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Flow render error: %s", exc)
            self._status_var.set(f"Render error: {exc}")

    def _render_to_image(self, graph) -> Image.Image:  # type: ignore[no-untyped-def]
        """Render a clean schematic diagram of the agent network."""
        import networkx as nx

        G = graph.raw_graph
        if G is None:
            G = nx.DiGraph()
            for n in graph.nodes:
                G.add_node(n.name)
            for e in graph.edges:
                G.add_edge(e.source, e.target)

        if len(G.nodes) == 0:
            G.add_node("(empty)")

        # ── Layout ────────────────────────────────────────────────────────────
        # Use a layered layout if graphviz is available; spring otherwise.
        try:
            pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
            # Rescale to generous spacing so boxes don't crowd
            xs = [v[0] for v in pos.values()]
            ys = [v[1] for v in pos.values()]
            xr = max(xs) - min(xs) or 1
            yr = max(ys) - min(ys) or 1
            n = len(G.nodes)
            sx = NODE_W * 2.6 * max(1, n ** 0.5)
            sy = NODE_H * 5.0 * max(1, n ** 0.5)
            pos = {
                k: (
                    (v[0] - min(xs)) / xr * sx,
                    (v[1] - min(ys)) / yr * sy,
                )
                for k, v in pos.items()
            }
        except Exception:  # noqa: BLE001
            pos = nx.spring_layout(G, seed=42, k=NODE_W * 3.0)

        # ── Figure ────────────────────────────────────────────────────────────
        cw = max(self._canvas.winfo_width(), 900)
        ch = max(self._canvas.winfo_height(), 650)
        dpi = 96
        fig, ax = plt.subplots(
            figsize=(cw / dpi * self._zoom, ch / dpi * self._zoom), dpi=dpi
        )
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(BG)
        ax.set_aspect("equal")
        ax.axis("off")

        node_lookup = {n.name: n for n in graph.nodes}
        edge_lookup = {(e.source, e.target): e for e in graph.edges}

        # ── Edges ─────────────────────────────────────────────────────────────
        for u, v in G.edges:
            ed = edge_lookup.get((u, v))
            protocol = (ed.protocol if ed else "direct-call") or "direct-call"
            p_key = protocol.lower().replace(" ", "-")
            dash, lw = PROTOCOL_DASH.get(p_key, DEFAULT_DASH)
            colour = PROTOCOL_COLOUR.get(p_key, "#4b5563")

            x0, y0 = pos[u]
            x1, y1 = pos[v]

            # Slight lateral offset for parallel edges
            dx, dy = x1 - x0, y1 - y0
            length = (dx ** 2 + dy ** 2) ** 0.5 or 1
            ox = -dy / length * 0.08
            oy =  dx / length * 0.08

            arrow = FancyArrowPatch(
                (x0 + ox, y0 + oy),
                (x1 + ox, y1 + oy),
                arrowstyle="-|>",
                color=colour,
                linewidth=lw,
                linestyle=(0, dash) if dash else "solid",
                mutation_scale=14,
                connectionstyle="arc3,rad=0.15",
                shrinkA=NODE_W * 50,   # pull back from source box
                shrinkB=NODE_W * 50,   # pull back from target box
                zorder=1,
            )
            ax.add_patch(arrow)

            # Protocol label mid-edge
            if self._show_labels:
                mx = (x0 + x1) / 2 + ox * 3
                my = (y0 + y1) / 2 + oy * 3
                ax.text(
                    mx, my, protocol,
                    ha="center", va="center",
                    fontsize=FONT_EDGE, color=colour,
                    bbox=dict(
                        boxstyle="round,pad=0.18",
                        fc=BG, ec=colour, lw=0.8, alpha=0.95,
                    ),
                    zorder=3,
                )

        # ── Nodes ─────────────────────────────────────────────────────────────
        for node_name in G.nodes:
            nd = node_lookup.get(node_name)
            cx, cy = pos[node_name]
            lx = cx - NODE_W / 2
            by = cy - NODE_H / 2

            atype = (nd.agent_type if nd else "worker").lower()
            fill, border = TYPE_STYLE.get(atype, DEFAULT_STYLE)
            role  = (nd.role if nd else "").strip()
            pct   = nd.completion_pct if nd else 0

            # Box
            ax.add_patch(FancyBboxPatch(
                (lx, by), NODE_W, NODE_H,
                boxstyle="round,pad=0.07",
                facecolor=fill,
                edgecolor=border,
                linewidth=1.6,
                zorder=2,
            ))

            # Agent name
            name_str = node_name.replace("_", " ")
            ax.text(
                cx, cy + 0.10,
                name_str,
                ha="center", va="center",
                fontsize=FONT_NAME, color="#ffffff",
                fontweight="bold", zorder=4,
            )

            # Role sub-label (one wrapped line below name)
            if self._show_labels and role and "TODO" not in role:
                role_short = textwrap.shorten(role, width=32, placeholder="…")
                ax.text(
                    cx, cy - 0.18,
                    role_short,
                    ha="center", va="center",
                    fontsize=FONT_ROLE, color="#d1d5db",
                    zorder=4,
                )

            # Completion dot (bottom-right corner of box)
            dot_colour = (
                "#ef4444" if pct < 30
                else "#fbbf24" if pct < 70
                else "#34d399"
            )
            ax.plot(
                lx + NODE_W - 0.09, by + 0.09,
                "o", markersize=5, color=dot_colour, zorder=5,
            )

        # ── Legend (top-right, compact) ───────────────────────────────────────
        type_entries = [
            mpatches.Patch(facecolor=f, edgecolor=b, label=t.capitalize())
            for t, (f, b) in TYPE_STYLE.items()
        ]
        protocol_entries = [
            plt.Line2D(
                [0], [0], color=PROTOCOL_COLOUR.get(p, "#4b5563"),
                lw=1.8,
                linestyle=(0, dash) if dash else "solid",
                label=p.replace("-", " ").title(),
            )
            for p, (dash, _lw) in PROTOCOL_DASH.items()
        ]
        completion_entries = [
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c,
                       markersize=7, label=lbl)
            for c, lbl in [("#ef4444","< 30%"),("#fbbf24","30–70%"),("#34d399","> 70%")]
        ]

        leg = ax.legend(
            handles=type_entries + [
                plt.Line2D([0],[0], color="none", label=""),   # spacer
            ] + protocol_entries + [
                plt.Line2D([0],[0], color="none", label=""),   # spacer
            ] + completion_entries,
            loc="upper right",
            fontsize=7,
            framealpha=0.95,
            edgecolor="#e5e7eb",
            title="Legend",
            title_fontsize=7.5,
            handlelength=2.2,
        )
        leg.get_frame().set_linewidth(0.8)

        plt.tight_layout(pad=0.4)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                    facecolor=BG)
        plt.close(fig)
        buf.seek(0)
        return Image.open(buf)

    def _display_image(self, img: Image.Image) -> None:
        photo = ImageTk.PhotoImage(img)
        self._img_ref = photo
        self._canvas.delete("all")
        cx = self._canvas.winfo_width() // 2 + self._pan_x
        cy = self._canvas.winfo_height() // 2 + self._pan_y
        self._canvas.create_image(cx, cy, anchor="center", image=photo)

    # ── Controls ──────────────────────────────────────────────────────────────

    def _zoom_in(self) -> None:
        self._zoom = min(self._zoom * 1.25, 4.0)
        self._redraw()

    def _zoom_out(self) -> None:
        self._zoom = max(self._zoom / 1.25, 0.25)
        self._redraw()

    def _reset(self) -> None:
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._redraw()

    def _toggle_labels(self) -> None:
        self._show_labels = not self._show_labels
        self._redraw()

    def _export_png(self) -> None:
        if not _RENDER_AVAILABLE or self._graph_data is None:
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
            title="Export flow diagram",
        )
        if path:
            img = self._render_to_image(self._graph_data)
            img.save(path)

    def _drag_start_handler(self, event) -> None:  # type: ignore[no-untyped-def]
        self._drag_start = (event.x, event.y)

    def _drag_handler(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._drag_start:
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            self._pan_x += dx
            self._pan_y += dy
            self._drag_start = (event.x, event.y)
            if self._img_ref:
                self._canvas.delete("all")
                cx = self._canvas.winfo_width() // 2 + self._pan_x
                cy = self._canvas.winfo_height() // 2 + self._pan_y
                self._canvas.create_image(cx, cy, anchor="center", image=self._img_ref)

    def _drag_end_handler(self, event) -> None:  # type: ignore[no-untyped-def]
        self._drag_start = None

    def _on_mousewheel(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()
