"""Serve the registry, random-draw or search tool to a real harness over MCP (stdio JSON-RPC 2.0)
(EXPERIMENTS.md, "Harnesses" and "Tools").

This is how our harness agents (Claude Code, Codex CLI, opencode) got the same tools as the minimal loop: one server
process per agent session, named `registry`, `random_choice` or `survey`, so agents saw names such as
mcp__registry__read_registry (Claude Code), registry_read_registry (opencode) or tool read_registry of server
registry (Codex CLI). Tool names, descriptions and input schemas are the loop's. Registry and random_choice results
are the same text in every harness; a search error comes back as "Error: ..." with isError true.

    python3 mcp_server.py registry --mode projects --state pop00.json --position 3 --population-seed 2026111700
    python3 mcp_server.py random_choice
    python3 mcp_server.py survey --index INDEX_DIR --seed 2026111600 --tau 0.02

Example Claude Code flags (our survey-mode command; built-in tools off, only these MCP tools allowed):
    claude -p "<user message>" --append-system-prompt "<system line>" --output-format stream-json --verbose
      --tools "" --allowedTools mcp__survey__search,mcp__survey__read,mcp__registry__read_registry
      --mcp-config '{"mcpServers": {...}}' --strict-mcp-config --disable-slash-commands --permission-mode acceptEdits

A resumed harness session (for a follow-up turn) starts a new server; for random_choice pass --prior-draws so the
six-draw cap spans the whole session, as ours did. --log FILE appends one JSON line per tool call ({"tool", "args",
"result", "is_error"}), which run_frontier.py reads to see whether the agent used its tool and how many draws it made.
"""
import argparse
import json
import sys

PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]


def handle(name, tool, msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return None                                              # notifications
    ok = lambda r: {"jsonrpc": "2.0", "id": mid, "result": r}
    if method == "initialize":
        v = params.get("protocolVersion")
        return ok({"protocolVersion": v if v in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                   "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": name, "version": "1"}})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": [{"name": s["name"], "description": s["description"], "inputSchema": s["parameters"]}
                             for s in tool.schemas]})
    if method == "tools/call":
        tname, args = params.get("name"), params.get("arguments")
        if name == "survey":
            text = tool.call(tname, args or {})
            err = text.startswith('{"error"')
            if err:
                text = "Error: " + json.loads(text)["error"]
            return ok({"content": [{"type": "text", "text": text}], "isError": err})
        if tname != tool.schemas[0]["name"]:
            return ok({"content": [{"type": "text", "text": f"Error: unknown tool: {tname}"}], "isError": True})
        return ok({"content": [{"type": "text", "text": tool.call(args)}], "isError": False})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}


def serve(name, tool, fin=sys.stdin, fout=sys.stdout, log=None):
    for line in fin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            resp = handle(name, tool, msg)
            if log and msg.get("method") == "tools/call" and resp and "result" in resp:
                with open(log, "a") as f:
                    f.write(json.dumps({"tool": (msg.get("params") or {}).get("name"),
                                        "args": (msg.get("params") or {}).get("arguments"),
                                        "result": resp["result"]["content"][0]["text"],
                                        "is_error": resp["result"]["isError"]}, ensure_ascii=False) + "\n")
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        except Exception as e:                                   # never crash the agent's session
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": f"internal error: {e}"}}
        if resp is not None:
            fout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            fout.flush()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tool", choices=["registry", "random_choice", "survey"])
    ap.add_argument("--mode", choices=["projects", "agenda_counts", "placebo"])
    ap.add_argument("--state"); ap.add_argument("--position", type=int); ap.add_argument("--population-seed", type=int)
    ap.add_argument("--prior-draws", type=int, default=0)
    ap.add_argument("--index"); ap.add_argument("--seed", type=int); ap.add_argument("--tau", type=float, default=0.0)
    ap.add_argument("--log", help="append each tool call and its result to this JSONL file")
    a = ap.parse_args(argv)
    if a.tool == "registry":
        import registry
        tool = registry.RegistryTool(a.mode, registry.Population(a.state, a.population_seed), a.position)
    elif a.tool == "random_choice":
        import random_choice
        tool = random_choice.RandomChoice()
        tool.n_ok = a.prior_draws
    else:
        import search_tool
        tool = search_tool.SearchTool(a.index, tau=a.tau, rank_seed=a.seed)
    serve(a.tool, tool, log=a.log)


if __name__ == "__main__":
    main()
