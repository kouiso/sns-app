"""Bounded stdio MCP adapter for chapter-only D4 workspace editing.

The model CLI remains outside the network namespace to reach its backend.
Only these capabilities are exported; provider, account and UI controls are not.
This adapter is not a formal knowledge-isolation or device receipt.
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
from pathlib import Path
from typing import Any

MAX_MESSAGE_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_EVENT_BYTES = 4096
VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
TOOLS = [
    {"name": "read_file", "description": "Read chapter.md or a declared app source; no host paths.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}},
                     "required": ["path"], "additionalProperties": False}},
    {"name": "edit_file", "description": "CAS edit app/App.tsx or create/edit app/components/RlsTrial.tsx. Choose your own code.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string", "enum": ["app/App.tsx", "app/components/RlsTrial.tsx"]},
         "expected_sha256": {"type": ["string", "null"]}, "content": {"type": "string"}},
         "required": ["path", "expected_sha256", "content"], "additionalProperties": False}},
    {"name": "typecheck", "description": "Run the controller-owned offline TypeScript profile on your app.",
     "inputSchema": {"type": "object", "properties": {
         "profile_id": {"type": "string", "enum": ["d4-sdk57"]}},
         "required": ["profile_id"], "additionalProperties": False}},
]


class ProtocolError(ValueError):
    pass


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate field")
        result[key] = value
    return result


def reject_constant(value):
    raise ProtocolError("non-JSON constant")


def decode_message(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message too large")
    try:
        value = json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("invalid JSON") from exc
    if not isinstance(value, dict):
        raise ProtocolError("request must be an object")
    return value


def closed(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise ProtocolError("invalid fields")
    return value


class D4MCPServer:
    def __init__(self, workspace, checker, record=lambda value: None):
        self.workspace, self.checker, self.record = workspace, checker, record
        self.initialized = False
        self.ready = False
        self.audit_failed = False

    def _audit(self, value):
        try:
            if len(json.dumps(value).encode("utf-8")) > MAX_EVENT_BYTES:
                raise ValueError("event too large")
            self.record(value)
            return True
        except Exception:
            self.audit_failed = True
            return False

    def handle(self, message):
        rid = message.get("id") if isinstance(message, dict) else None
        if rid is not None and (type(rid) not in (str, int)
                or (type(rid) is int and not -(2**53 - 1) <= rid <= 2**53 - 1)
                or (isinstance(rid, str) and (len(rid) > 128 or any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in rid)))):
            rid = None
        try:
            closed(message, {"jsonrpc", "method"}, {"id", "params"})
            if message["jsonrpc"] != "2.0" or not isinstance(message["method"], str):
                raise ProtocolError("invalid request")
            if "id" in message and (message["id"] is None or rid is None):
                raise ProtocolError("invalid request id")
            method, params = message["method"], message.get("params", {})
            if not isinstance(params, dict):
                raise ProtocolError("invalid parameters")
            if "_meta" in params:
                meta = params["_meta"]
                if not isinstance(meta, dict) or len(json.dumps(meta).encode("utf-8")) > 4096:
                    raise ProtocolError("invalid request metadata")
                params = {key: value for key, value in params.items() if key != "_meta"}
            if rid is None:
                if method == "notifications/initialized" and params == {} and self.initialized:
                    self.ready = True
                return None
            if method == "initialize":
                closed(params, {"protocolVersion", "capabilities", "clientInfo"})
                requested_version = params["protocolVersion"]
                if self.initialized or not isinstance(requested_version, str) or not requested_version or len(requested_version) > 128 or any(ord(c) < 32 or ord(c) > 126 for c in requested_version) or not isinstance(params["capabilities"], dict) or not isinstance(params["clientInfo"], dict):
                    raise ProtocolError("initialization rejected")
                self.initialized = True
                result = {"protocolVersion": requested_version if requested_version in VERSIONS else max(VERSIONS), "capabilities": {"tools": {}},
                          "serverInfo": {"name": "d4-workspace", "version": "1"}}
            elif method == "ping" and params == {}:
                result = {}
            elif not self.ready:
                raise ProtocolError("not initialized")
            elif method == "tools/list" and params == {}:
                result = {"tools": TOOLS}
            elif method in {"resources/list", "prompts/list"} and params == {}:
                result = {"resources" if method == "resources/list" else "prompts": []}
            elif method == "tools/call":
                closed(params, {"name", "arguments"})
                name, args = params["name"], params["arguments"]
                if name not in {"read_file", "edit_file", "typecheck"}:
                    raise ProtocolError("unknown tool")
                if self.audit_failed:
                    return {"jsonrpc": "2.0", "id": rid, "result": {"isError": True,
                            "content": [{"type": "text", "text": "audit_failed_session_closed"}]}}
                try:
                    self.workspace.verify_inventory()
                    if name == "typecheck":
                        closed(args, {"profile_id"})
                        if args["profile_id"] != "d4-sdk57":
                            raise ProtocolError("unknown profile")
                        receipt = self.checker.run(args["profile_id"])
                        value = dataclasses.asdict(receipt) if dataclasses.is_dataclass(receipt) else dict(receipt)
                    else:
                        value = getattr(self.workspace, name)(args)
                    self.workspace.verify_inventory()
                    result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}
                    encoded = json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}, ensure_ascii=False).encode("utf-8")
                    if len(encoded) > MAX_RESPONSE_BYTES - 1:
                        raise ProtocolError("response too large")
                    event = {"tool": name, "ok": True, "snapshot": self.workspace.snapshot()}
                    if name == "typecheck":
                        event.update(typecheck_passed=value.get("passed"), exit_code=value.get("exit_code"))
                    if not self._audit(event):
                        result = {"isError": True, "content": [{"type": "text", "text": "tool_completed_audit_failed_stop"}]}
                except Exception:
                    self._audit({"tool": name, "ok": False})
                    result = {"isError": True, "content": [{"type": "text", "text": "tool_outcome_unknown"}]}
            else:
                raise ProtocolError("unsupported request")
            return {"jsonrpc": "2.0", "id": rid, "result": result}
        except (ProtocolError, TypeError, ValueError):
            if isinstance(message, dict) and "id" not in message and message.get("jsonrpc") == "2.0" and isinstance(message.get("method"), str):
                return None
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "request_rejected"}}


def serve(server, incoming, outgoing):
    while True:
        raw = incoming.readline(MAX_MESSAGE_BYTES + 1)
        if not raw:
            break
        try:
            if len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\n"):
                # A partial/oversized frame ends the session instead of resyncing
                # on an attacker-selected suffix of an oversized request.
                raise ProtocolError("invalid frame")
            response = server.handle(decode_message(raw))
        except ProtocolError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "invalid_frame"}}
            outgoing.write((json.dumps(response) + "\n").encode())
            outgoing.flush()
            break
        if response is not None:
            encoded = (json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8")
            if len(encoded) > MAX_RESPONSE_BYTES:
                encoded = b'{"jsonrpc":"2.0","id":null,"error":{"code":-32603,"message":"response_rejected"}}\n'
            outgoing.write(encoded)
            outgoing.flush()


def main():
    from d4_workspace import D4Workspace
    from d4_typecheck import FixedD4Typecheck
    workspace = D4Workspace.create(Path(os.environ["D4_CANDIDATE"]), Path(os.environ["D4_WORKSPACE"]))
    checker = FixedD4Typecheck(Path(os.environ["D4_WORKSPACE"]) / "app",
                             Path(os.environ["D4_DEPENDENCIES"]),
                             node_executable=Path(os.environ["D4_NODE"]),
                             dependency_targets=tuple(Path(value) for value in json.loads(os.environ["D4_DEPENDENCY_TARGETS"])))
    events = Path(os.environ["D4_EVENTS"])
    def record(value):
        with events.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")
    serve(D4MCPServer(workspace, checker, record), sys.stdin.buffer, sys.stdout.buffer)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("d4_mcp_bootstrap_failed\n")
        raise SystemExit(2)
