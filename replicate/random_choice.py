"""The random-draw tool of the tree protocol, as we ran it (EXPERIMENTS.md, "Tree protocol").

The agent passes options, weights and a temperature; the tool draws one option with chance proportional to
weight ** (1 / temperature) and returns it. One session may make at most six successful draws. The schema, error
messages, checks and output below are the ones our agents saw, byte for byte (tool version 2).

    tool = RandomChoice()                       # one instance per agent session
    tool.call({"options": ["a", "b"], "weights": [0.7, 0.3], "temperature": 1})
    -> '{"choice": "a", "index": 0, "draw": "draw 1 of 6"}'

Behaviour worth knowing, all as in our runs:
- Draws use the operating system's random number generator (secrets.SystemRandom), not a seed, so draws cannot be
  replayed from a seed. Our draws are released in data/tree_draws_frontier_tree.jsonl, with the uniform number `u`.
- Weights may be off by up to 0.02 from summing to 1; they are then renormalised silently. Further off is an error.
- A weight given as a string is accepted ("0.3", or "30%" read as 0.3), and so are options or weights passed as a
  JSON-encoded list in a string. Temperature defaults to 1 when omitted.
- Argument errors are checked before the draw cap, so a malformed seventh call gets the argument error.
- Failed calls do not count toward the six draws. Errors come back as {"error": ...} in the normal tool result,
  never as a protocol error, in the loop and over MCP alike.
"""
import json
import math
import secrets

MAX_DRAWS = 6
SUM_TOL = 0.02
TOOL_SCHEMA = {
    "name": "random_choice",
    "description": ("Draw one option at random, using a real random number generator. The chance of option i is "
                    "proportional to weights[i] raised to the power 1/temperature: temperature 1 draws in proportion "
                    "to the weights, larger temperatures draw more evenly. Give 2 to 20 options. Weights must be "
                    "non-negative numbers, one per option, adding up to 1. Returns the chosen option, its 0-based "
                    f"index, and which draw this is (at most {MAX_DRAWS} per session)."),
    "parameters": {"type": "object", "properties": {
        "options": {"type": "array", "items": {"type": "string"}, "description": "The options, 2 to 20 strings."},
        "weights": {"type": "array", "items": {"type": "number"},
                    "description": "One non-negative weight per option, in the same order, adding up to 1."},
        "temperature": {"type": "number", "description": "Greater than 0. Default 1."}},
        "required": ["options", "weights"]},
}
CAP_ERROR = "Limit of six draws reached. Give your final answer."
SUM_ERROR = "weights add up to {}; they should add up to 1. Fix the weights and call random_choice again."
# Sent once if a session ends without ever calling the tool (then the usual answer-line follow-up, once, if needed).
UNCALLED_NUDGE = "You have not used the random_choice tool. Follow the steps above, then give your final answer."


def parse(raw):
    """(options, weights, temperature) or raise ValueError with the message the agent sees."""
    try:
        args = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
        if not isinstance(args, dict):
            raise ValueError
    except ValueError:
        raise ValueError("arguments must be a JSON object")
    o, w, t = args.get("options"), args.get("weights"), args.get("temperature")
    if isinstance(o, str) or isinstance(w, str):          # a JSON-encoded list passed as a string
        try:
            o = json.loads(o) if isinstance(o, str) else o
            w = json.loads(w) if isinstance(w, str) else w
        except ValueError:
            pass
    if not isinstance(o, list) or not all(isinstance(x, str) and x.strip() for x in o):
        raise ValueError("options must be a list of non-empty strings")
    if not 2 <= len(o) <= 20:
        raise ValueError("give 2 to 20 options")
    if not isinstance(w, list) or len(w) != len(o):
        raise ValueError("weights must be a list with one number per option")
    ws = []
    for x in w:
        if isinstance(x, str):
            try:
                x = float(x.strip().rstrip("%")) / (100 if x.strip().endswith("%") else 1)
            except ValueError:
                raise ValueError("weights must be numbers")
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
            raise ValueError("weights must be numbers")
        if x < 0:
            raise ValueError("weights must be non-negative")
        ws.append(float(x))
    if sum(ws) <= 0:
        raise ValueError("at least one weight must be positive")
    if t is None:
        return o, ws, 1.0
    if isinstance(t, str):
        try:
            t = float(t)
        except ValueError:
            raise ValueError("temperature must be a number greater than 0")
    if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t <= 0:
        raise ValueError("temperature must be a number greater than 0")
    return o, ws, float(t)


def probabilities(weights, temperature):
    """P(i) proportional to w_i ** (1 / temperature), in log space; zero weights stay zero."""
    lg = [math.log(w) / temperature if w > 0 else None for w in weights]
    m = max(x for x in lg if x is not None)
    p = [math.exp(x - m) if x is not None else 0.0 for x in lg]
    z = sum(p)
    return [x / z for x in p]


def pick(probs, u):
    """Index of the option drawn by a uniform number u in [0, 1): the first positive-probability option whose
    cumulative probability exceeds u (the last positive one at a floating-point edge)."""
    cum = 0.0
    for k, pk in enumerate(probs):
        cum += pk
        if pk > 0 and u < cum:
            return k
    return max(k for k, pk in enumerate(probs) if pk > 0)


class RandomChoice:
    """One agent session's random_choice tool. `log` collects every call (options, weights, u, index, error)."""
    name = "random_choice"
    schemas = [TOOL_SCHEMA]

    def __init__(self, rng=None, max_draws=MAX_DRAWS):
        self.rng = rng or secrets.SystemRandom()
        self.max_draws, self.n_ok, self.log = max_draws, 0, []

    def call(self, raw_args):
        """The tool result string for one call."""
        ev = {"args": raw_args, "u": None, "index": None, "choice": None, "error": None}
        try:
            options, weights, temperature = parse(raw_args)
            if self.n_ok >= self.max_draws:
                raise ValueError(CAP_ERROR)
            if abs(sum(weights) - 1) > SUM_TOL + 1e-9:
                raise ValueError(SUM_ERROR.format(f"{sum(weights):.4g}"))
            u = self.rng.random()
            i = pick(probabilities(weights, temperature), u)
            self.n_ok += 1
            ev.update(options=options, weights=weights, temperature=temperature, u=u, index=i, choice=options[i])
            out = {"choice": options[i], "index": i, "draw": f"draw {self.n_ok} of {self.max_draws}"}
        except ValueError as e:
            ev["error"] = str(e)
            out = {"error": str(e)}
        self.log.append(ev)
        return json.dumps(out, ensure_ascii=False)


if __name__ == "__main__":
    t = RandomChoice()
    print(t.call({"options": ["Monitoring", "Interpretability", "Evals"], "weights": [0.4, 0.35, 0.25]}))
    print(t.call({"options": ["a", "b"], "weights": [0.5, 0.2]}))
