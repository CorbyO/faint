"""Tool metadata shared by toolbar, status text, shortcuts and width state.

Tuple order is the visible toolbar order. A missing default_width disables the
width control; keeping these values here prevents UI and command drift.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDefinition:
    key: str
    label: str
    shortcut: str | None
    hint: str
    default_width: int | None


TOOLS = (
    ToolDefinition("pixel", "TOOLBAR.PIXEL", "P", "TOOL_HINT.PIXEL", 1),
    ToolDefinition("brush", "TOOLBAR.BRUSH", "B", "TOOL_HINT.BRUSH", 4),
    ToolDefinition("eraser", "TOOLBAR.ERASER", "E", "TOOL_HINT.ERASER", 4),
    ToolDefinition(
        "select",
        "TOOLBAR.SELECT",
        "S",
        "TOOL_HINT.SELECT",
        None,
    ),
    ToolDefinition("line", "TOOLBAR.LINE", "L", "TOOL_HINT.LINE", 4),
    ToolDefinition("rect", "TOOLBAR.RECTANGLE", "R", "TOOL_HINT.RECTANGLE", 4),
    ToolDefinition("ellipse", "TOOLBAR.ELLIPSE", "C", "TOOL_HINT.ELLIPSE", 4),
    ToolDefinition(
        "roundrect",
        "TOOLBAR.ROUNDED_RECTANGLE",
        "Ctrl+R",
        "TOOL_HINT.ROUNDED_RECTANGLE",
        4,
    ),
    ToolDefinition("picker", "TOOLBAR.COLOR_PICKER", None, "TOOL_HINT.COLOR_PICKER", None),
    ToolDefinition("fill", "TOOLBAR.FILL", "F", "TOOL_HINT.FILL", None),
)

TOOL_BY_KEY = {tool.key: tool for tool in TOOLS}

# Preserve the original width-state key order as well as the default values.
DEFAULT_TOOL_WIDTHS = {
    "brush": 4,
    "eraser": 4,
    "pixel": 1,
    "line": 4,
    "rect": 4,
    "ellipse": 4,
    "roundrect": 4,
}
