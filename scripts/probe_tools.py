#!/usr/bin/env python3
"""MCP server with safe_tap: a tap that first checks the control is on top.

MobileBuildMCP's touch taps the middle of an element without checking what is
there, so a control under a fixed bar (a Next button, the keyboard) gets a tap
meant for it delivered to the bar. safe_tap hit-tests the point with AXe
(`describe-ui --point`), scrolls the content if something covers it, and taps
only a point where the control itself is on top.

Speaks MCP over stdio (newline-delimited JSON-RPC), standard library only. The
simulator comes from .mobilebuildmcp/config.yaml, which explore.py writes for
every run; AXe is the copy bundled with MobileBuildMCP (or $AXE_PATH).
"""

import glob
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAP_DELAY = 0.15
MAX_SCROLLS = 3
# Edge strips where iOS keeps touches for its own gestures (status bar, home indicator):
# a tap there may never reach the app even when the hit-test names a control.
TOP_INSET, BOTTOM_INSET = 50, 34
# Containers that share a label with the control inside them.
CONTAINER_TYPES = {"Group", "Other", "Application", "Window"}


def axe_path():
    if os.environ.get("AXE_PATH"):
        return os.environ["AXE_PATH"]
    # The copy bundled with the MobileBuildMCP version that .mcp.json pins.
    args = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["mobilebuildmcp"]["args"]
    version = next((a.split("@", 1)[1] for a in args if a.startswith("mobilebuildmcp@")), None)
    for package in glob.glob(os.path.expanduser("~/.npm/_npx/*/node_modules/mobilebuildmcp/package.json")):
        if version is None or json.loads(Path(package).read_text()).get("version") == version:
            return str(Path(package).parent / "bundled" / "axe")
    raise RuntimeError("AXe not found: run MobileBuildMCP once or set AXE_PATH")


def simulator_id():
    text = (ROOT / ".mobilebuildmcp" / "config.yaml").read_text()
    match = re.search(r"^\s*simulatorId:\s*(\S+)", text, re.M)
    if not match:
        raise RuntimeError("No simulatorId in .mobilebuildmcp/config.yaml")
    return match.group(1)


class Screen:
    """AXe calls for one simulator."""

    def __init__(self):
        self.axe, self.udid = axe_path(), simulator_id()

    def run(self, *args):
        result = subprocess.run([self.axe, *args, "--udid", self.udid], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"axe {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
        return result.stdout

    def tree(self, point=None):
        data = json.loads(self.run("describe-ui", *(["--point", f"{point[0]:.0f},{point[1]:.0f}"] if point else [])))
        return data if isinstance(data, list) else [data]

    def touch(self, point, delay):
        self.run("touch", "-x", f"{point[0]:.0f}", "-y", f"{point[1]:.0f}", "--down", "--up", "--delay", str(delay))

    def drag(self, start, end):
        # A slow drag scrolls by about its length, without the fling a fast swipe adds.
        self.run("drag", "--start-x", f"{start[0]:.0f}", "--start-y", f"{start[1]:.0f}",
                 "--end-x", f"{end[0]:.0f}", "--end-y", f"{end[1]:.0f}", "--duration", "0.6")


def flatten(nodes):
    for node in nodes:
        yield node
        yield from flatten(node.get("children") or [])


def rect(node):
    f = node.get("frame") or {}
    return (f.get("x", 0), f.get("y", 0), f.get("width", 0), f.get("height", 0))


def same(a, b, tolerance=1.0):
    return all(abs(x - y) <= tolerance for x, y in zip(a, b))


def contains(outer, inner):
    return (outer[0] - 1 <= inner[0] and outer[1] - 1 <= inner[1]
            and inner[0] + inner[2] <= outer[0] + outer[2] + 1 and inner[1] + inner[3] <= outer[1] + outer[3] + 1)


def describe(node):
    label = node.get("AXLabel") or node.get("AXValue") or ""
    return f"{node.get('type', 'element')} '{label}'" if label else node.get("type", "element")


def find(nodes, label, element_type, index):
    """The index-th visible element with this label, preferring a control over the group around it."""
    matches = [n for n in flatten(nodes)
               if (n.get("AXLabel") or "") == label and n.get("enabled", True) is not False
               and (not element_type or n.get("type") == element_type)]
    if not matches:
        matches = [n for n in flatten(nodes)
                   if (n.get("AXLabel") or "").lower() == label.lower()
                   and (not element_type or n.get("type") == element_type)]
    if not matches:
        # A text field without a label is known by its value, such as its placeholder.
        matches = [n for n in flatten(nodes)
                   if not n.get("AXLabel") and (n.get("AXValue") or "") == label
                   and (not element_type or n.get("type") == element_type)]
    controls = [n for n in matches if n.get("type") not in CONTAINER_TYPES]
    matches = controls or matches
    return matches[index] if index < len(matches) else None, len(matches)


def is_target(hit_nodes, target):
    """True when the hit-tested element is the target, a part of it, or a container holding it."""
    frame, label = rect(target), target.get("AXLabel")
    top = hit_nodes[0] if hit_nodes else None
    if top is None:
        return False
    if contains(frame, rect(top)) and top.get("type") not in CONTAINER_TYPES | {"Application"}:
        return True
    # An unlabeled container around the whole control is a hit-test that missed the control,
    # not a cover: some controls (a floating glass button) are not hit-testable at all.
    if top.get("type") in CONTAINER_TYPES and not top.get("AXLabel") and contains(rect(top), frame):
        return True
    return any(same(rect(n), frame) and n.get("AXLabel") == label for n in flatten(hit_nodes))


def probe_points(frame, viewport):
    """Points inside the element, middle first, that lie outside the system edge strips."""
    x, y, w, h = frame
    top, bottom = viewport[1] + TOP_INSET, viewport[1] + viewport[3] - BOTTOM_INSET
    points = []
    for fy in (0.5, 0.3, 0.7):
        for fx in (0.5, 0.25, 0.75):
            px, py = x + w * fx, y + h * fy
            if top <= py <= bottom and viewport[0] <= px <= viewport[0] + viewport[2]:
                points.append((px, py))
    return points


def safe_tap(label, index=0, element_type=None, delay=TAP_DELAY):
    screen = Screen()
    scrolls = []
    for attempt in range(MAX_SCROLLS + 1):
        nodes = screen.tree()
        viewport = rect(nodes[0])
        target, count = find(nodes, label, element_type, index)
        if target is None:
            where = f" after scrolling {', '.join(scrolls)}" if scrolls else ""
            return False, f"No element labeled '{label}'{f' of type {element_type}' if element_type else ''} " \
                          f"at index {index} on screen{where} ({count} found)."
        frame = rect(target)
        cover = None
        for point in probe_points(frame, viewport):
            hit = screen.tree(point)
            if is_target(hit, target):
                screen.touch(point, delay)
                moved = f" after scrolling {', '.join(scrolls)}" if scrolls else ""
                return True, f"Tapped {describe(target)} at ({point[0]:.0f}, {point[1]:.0f}){moved}."
            cover = cover or (hit[0] if hit else None)
        if attempt == MAX_SCROLLS:
            break
        # Move the content so the control clears whatever is on top of it, or the edge strips.
        mid_y = frame[1] + frame[3] / 2
        cover_frame = rect(cover) if cover else None
        top, bottom = viewport[1] + TOP_INSET, viewport[1] + viewport[3] - BOTTOM_INSET
        if cover_frame and cover_frame[1] + cover_frame[3] / 2 < mid_y:
            distance = (cover_frame[1] + cover_frame[3]) - frame[1] + 40      # cover above: content down
        elif cover_frame:
            distance = -((frame[1] + frame[3]) - cover_frame[1] + 40)        # cover below: content up
        elif mid_y > bottom:
            distance = -((frame[1] + frame[3]) - bottom + 40)
        else:
            distance = top - frame[1] + 40
        distance = max(-viewport[3] * 0.5, min(viewport[3] * 0.5, distance))
        # Drag through the middle of the screen, away from bars at the edges.
        cx, cy = viewport[0] + viewport[2] / 2, viewport[1] + viewport[3] / 2
        screen.drag((cx, cy - distance / 2), (cx, cy + distance / 2))
        scrolls.append(("down" if distance > 0 else "up") + f" {abs(distance):.0f} pt")
        time.sleep(0.6)
    covered = f"covered by {describe(cover)}" if cover else "not reachable (at the screen edge)"
    return False, f"Did not tap {describe(target)}: {covered} after {len(scrolls)} scrolls. " \
                  "It may sit under a sheet, an alert, or a bar that scrolling cannot clear."


TOOLS = [{
    "name": "safe_tap",
    "description": (
        "Tap a control by its accessibility label, only where the control is really on top. "
        "Before tapping it hit-tests the point; if something covers the control (a fixed bottom "
        "button, the keyboard, a banner) it scrolls the content and checks again, up to 3 times. "
        "Use the label exactly as the snapshot shows it. Returns where it tapped, or what covers "
        "the control if it did not tap."),
    "inputSchema": {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "The control's label from the snapshot, e.g. 'Decrement'; for a field without a label, its value or placeholder"},
            "index": {"type": "integer", "minimum": 0, "default": 0,
                      "description": "Which match, from the top, when several controls share the label"},
            "elementType": {"type": "string",
                            "description": "Optional accessibility type to narrow matches, e.g. Button, CheckBox, TextField"},
            "delay": {"type": "number", "minimum": 0.05, "maximum": 2, "default": TAP_DELAY,
                      "description": "Seconds between touch down and up"},
        },
        "required": ["label"],
        "additionalProperties": False,
    },
}]


def handle(message):
    method, params = message.get("method"), message.get("params") or {}
    if method == "initialize":
        return {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "probe-tools", "version": "1.0.0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        args = params.get("arguments") or {}
        if params.get("name") != "safe_tap":
            return {"content": [{"type": "text", "text": f"Unknown tool {params.get('name')}"}], "isError": True}
        try:
            ok, text = safe_tap(str(args["label"]), int(args.get("index", 0)),
                                args.get("elementType"), float(args.get("delay", TAP_DELAY)))
        except Exception as error:  # Reported to the bot as a failed call, not a crash of the server.
            ok, text = False, f"safe_tap failed: {error}"
        return {"content": [{"type": "text", "text": text}], "isError": not ok}
    raise KeyError(method)


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        message = json.loads(line)
        if "id" not in message:
            continue  # A notification, such as notifications/initialized.
        try:
            reply = {"jsonrpc": "2.0", "id": message["id"], "result": handle(message)}
        except KeyError:
            reply = {"jsonrpc": "2.0", "id": message["id"],
                     "error": {"code": -32601, "message": f"Method not found: {message.get('method')}"}}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--tap":
        # Manual check from a terminal: python3 scripts/probe_tools.py --tap "Decrement"
        print(safe_tap(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0))
    else:
        main()
