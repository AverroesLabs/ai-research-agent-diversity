"""The shared registry tool of Result 2, as plain functions (EXPERIMENTS.md, "Registry").

Agents of one population choose one at a time. Agent k calls read_registry and sees what the agents at positions
0..k-1 of its own population chose, in one of three forms that share every fixed text (tool name, description,
header and closing line), so the arm is not announced:

    projects       one line per earlier agent: "PROJECT: QUESTION", whitespace collapsed, cut at 300 characters
    agenda_counts  one line per agenda that has at least one earlier agent: "<agenda name>: <n> agent(s)"
    placebo        k lines from a fixed list of 267 off-topic machine-learning projects (placebo_offscope_v1.jsonl);
                   independent of every other agent, so placebo agents can run in parallel

    reg = Population("pop00.json", population_seed=2026111700)
    text = render("projects", reg.visible(position=3), position=3, population_seed=reg.seed)
    reg.register(position=3, agent_id="a03", parsed={"direction": ..., "project": ..., "question": ...})

Exactly as ours: the display order is a seeded shuffle per (population seed, position); self-references such as
"As a Claude agent" are masked as "[...]" before display; the agenda-counts arm needs a label per pick from the
agenda labeller (labeller.py) before the pick is registered. Two oddities are kept on purpose:
- The header counts the lines' source agents, so with agenda counts it says "(5 earlier agents)" above fewer lines.
- In the frontier setup only picks with all five answer lines were registered; in the simple setup any pick with a
  parsed DIRECTION line was (Population.register takes the rule as an argument).
"""
import hashlib
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_ENTRY_CHARS = 300
HEADER = "Shared registry of active work ({n} earlier agents):\n"
CLOSING = "End of registry.\n"
TOOL_SCHEMA = {"name": "read_registry",
               "description": "Read the shared registry of active work in this scope. Takes no arguments.",
               "parameters": {"type": "object", "properties": {}}}
# The sentence added to the launch prompt (EXPERIMENTS.md says where), and the follow-up for an agent that never read.
INSTRUCTION = "Before considering a direction, check the shared registry of what other agents are already working on."
NUDGE_SENTENCE = ("You have not checked the shared registry. Check the shared registry of what other agents are already "
                  "working on, then give your final answer.")
PLACEBO_POOL = HERE / "placebo_offscope_v1.jsonl"
PLACEBO_POOL_SHA256 = "56d1e9106da0745feb91d0c2c9504d463138f89b4b36f58708fa7803a4c11eb1"

# Identity screen: an agent's own words could reveal its model ("As a Claude agent, I ..."). Self-references are masked;
# model or company names used as research content are left in place.
_NAMES = (r"claude(?:[ -]code)?|anthropic|glm(?:-[\w.-]+)?|zhipu|z\.ai|deepseek(?:[ -]v?\d[\w.]*)?|qwen[\w.-]*|"
          r"chatgpt|gpt-?[\w.]*|openai|codex(?: cli)?|gemini(?: cli)?|opencode|kimi|llama[\w.-]*|mistral")
_SELF = (r"\b(?:as an? (?:ai(?: language model| assistant| agent| model)?|(?:" + _NAMES + r")"
         r"(?: (?:agent|model|assistant|instance))?)|i am (?:an? )?(?:" + _NAMES + r")|i'm (?:an? )?(?:" + _NAMES + r"))\b")


def rng_for(*parts):
    """The seeded generator behind every shuffle: Random(first 16 hex digits of sha256(json(parts)))."""
    h = hashlib.sha256(json.dumps(list(parts), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def cut(text, n=MAX_ENTRY_CHARS):
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def entry_line(project, question, direction=None, n=MAX_ENTRY_CHARS):
    """'PROJECT: QUESTION' (the direction stands in for a missing question), whitespace collapsed, cut at n chars."""
    head, body = (project or "").strip(), (question or direction or "").strip()
    t = f"{head}: {body}" if head and body else (head or body)
    return cut(" ".join(t.split()), n)


def identity_screen(text):
    return re.sub(_SELF, "[...]", text, flags=re.I) if text else text


def load_placebo_pool(path=PLACEBO_POOL, sha256=PLACEBO_POOL_SHA256):
    raw = Path(path).read_bytes()
    if sha256 and hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError(f"{path}: sha256 differs from the pool we used")
    return [json.loads(l)["text"].strip() for l in raw.decode().splitlines() if l.strip()]


def agenda_names(path=HERE / "agendas.json"):
    d = json.loads(Path(path).read_text())
    names = {a["id"]: a["name"] for a in d["agendas"]}
    names["governance_policy"] = "Governance, policy or strategy work"   # the only non-agenda label shown by name
    return names


def render(mode, entries, position, population_seed, pool=None, names=None):
    """The read_registry result for the agent at `position`.
    entries: the earlier agents' registered picks, dicts with position, project, question, direction and (for
    agenda_counts) label; ignored for placebo. pool: placebo lines (default: our pool). names: agenda id -> name."""
    order = rng_for("order", population_seed, position, 0)        # the 0 is a display seed that we never changed
    if mode == "placebo":
        pool = pool if pool is not None else load_placebo_pool()
        idx = list(range(len(pool)))
        rng_for("placebo_list", population_seed, position).shuffle(idx)
        idx = [i for i in idx if len(pool[i]) > MAX_ENTRY_CHARS] + [i for i in idx if len(pool[i]) <= MAX_ENTRY_CHARS]
        body = "".join("- " + cut(" ".join(pool[i].split())) + "\n" for i in idx[:position])
        return HEADER.format(n=position) + body + CLOSING
    es = sorted(entries, key=lambda e: e["position"])
    if mode == "projects":
        es = es[:]
        order.shuffle(es)
        body = "".join("- " + identity_screen(entry_line(e.get("project"), e.get("question"), e.get("direction")))
                       + "\n" for e in es)
    elif mode == "agenda_counts":
        names = names or agenda_names()
        counts = {}
        for e in es:                                   # labels outside the agendas all show as "unclassified"
            k = e.get("label") if e.get("label") in names else None
            counts[k] = counts.get(k, 0) + 1
        keys = sorted(counts, key=lambda k: (k is None, k or ""))
        order.shuffle(keys)
        body = "".join(f"- {names[k] if k else 'unclassified'}: {counts[k]} agent{'s' * (counts[k] != 1)}\n"
                       for k in keys)
    else:
        raise ValueError(f"mode {mode!r}: projects, agenda_counts or placebo")
    return HEADER.format(n=len(es)) + body + CLOSING


class Population:
    """A file-backed registry for one population (JSON list of registered picks)."""

    def __init__(self, path, population_seed):
        self.path, self.seed = Path(path), population_seed

    def entries(self):
        return json.loads(self.path.read_text()) if self.path.exists() else []

    def visible(self, position):
        return [e for e in self.entries() if e["position"] < position]

    def register(self, position, agent_id, parsed, label=None, status="ok", rule="frontier"):
        """Add a finished agent's pick. rule "frontier": only status ok; "simple": any parsed DIRECTION line.
        Returns False when nothing was registered (later agents then see one fewer line)."""
        parsed = parsed or {}
        if (rule == "frontier" and status != "ok") or not parsed.get("direction"):
            return False
        es = [e for e in self.entries() if e["agent_id"] != agent_id]
        es.append({"agent_id": agent_id, "position": position, "label": label, "direction": parsed.get("direction"),
                   "project": parsed.get("project"), "question": parsed.get("question")})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sorted(es, key=lambda e: e["position"]), ensure_ascii=False, indent=1))
        return True


class RegistryTool:
    """read_registry for one agent: the object a loop or an MCP server calls."""
    name = "read_registry"
    schemas = [TOOL_SCHEMA]

    def __init__(self, mode, population, position):
        self.mode, self.pop, self.position, self.n_reads = mode, population, position, 0

    def call(self, raw_args=None):
        self.n_reads += 1
        es = [] if self.mode == "placebo" else self.pop.visible(self.position)
        return render(self.mode, es, self.position, self.pop.seed)


if __name__ == "__main__":
    demo = [{"position": 0, "project": "SAND-Bench", "question": "Can sandbagging be detected blind?",
             "label": "scheming_evals"},
            {"position": 1, "project": "Monitor Decay", "question": "As a Claude agent I ask how monitors degrade.",
             "label": "control"}]
    for m in ("projects", "agenda_counts", "placebo"):
        print(render(m, demo, 2, 2026111700))
