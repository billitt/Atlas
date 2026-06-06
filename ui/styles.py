"""Atlas dashboard design tokens and global CSS."""

from __future__ import annotations

PALETTE = {
    "bg": "#0b0f14",
    "surface": "#141a22",
    "surface_alt": "#1c2430",
    "border": "#2a3544",
    "accent": "#3b82f6",
    "accent_muted": "#2563eb33",
    "text": "#e8edf4",
    "text_muted": "#94a3b8",
    "success": "#22c55e",
    "warning": "#eab308",
    "danger": "#ef4444",
}

CONFIDENCE_COLORS = {
    "HIGH": PALETTE["success"],
    "MEDIUM": PALETTE["warning"],
    "LOW": PALETTE["danger"],
}

SEVERITY_COLORS = {
    "HIGH": PALETTE["danger"],
    "MEDIUM": PALETTE["warning"],
    "LOW": PALETTE["success"],
}


def global_css() -> str:
    """Return dashboard-wide CSS injected once per rerun."""
    p = PALETTE
    return f"""
    <style>
      .stApp {{
        background: linear-gradient(180deg, {p["bg"]} 0%, #0e141c 100%);
        color: {p["text"]};
      }}
      [data-testid="stSidebar"] {{
        background-color: {p["surface"]};
        border-right: 1px solid {p["border"]};
      }}
      .atlas-card {{
        background: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 12px;
        padding: 1rem 1.1rem;
        margin-bottom: 0.75rem;
      }}
      .atlas-card-title {{
        font-size: 0.95rem;
        font-weight: 600;
        margin-bottom: 0.35rem;
        color: {p["text"]};
      }}
      .atlas-pill {{
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }}
      .atlas-tag {{
        display: inline-block;
        background: {p["surface_alt"]};
        border: 1px solid {p["border"]};
        color: {p["text_muted"]};
        border-radius: 6px;
        padding: 0.15rem 0.45rem;
        font-size: 0.72rem;
        margin: 0.15rem 0.25rem 0 0;
      }}
      .atlas-metric-label {{
        font-size: 0.75rem;
        color: {p["text_muted"]};
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }}
      .atlas-metric-value {{
        font-size: 1.35rem;
        font-weight: 700;
        color: {p["text"]};
      }}
      .atlas-callout {{
        border-left: 4px solid {p["accent"]};
        background: {p["accent_muted"]};
        padding: 0.85rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.75rem 0;
      }}
      .atlas-alert-card {{
        border-left: 4px solid {p["border"]};
        background: {p["surface"]};
        border-radius: 0 10px 10px 0;
        padding: 0.9rem 1rem;
        margin-bottom: 0.75rem;
      }}
      .atlas-status-dot {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
      }}
    </style>
    """
