# Replicating or extending the experiments

This folder holds small reference implementations of the pieces we used to run the experiments, so that you can run them again with your own models and harnesses. [EXPERIMENTS.md](../EXPERIMENTS.md) describes every experiment; each file here links to the section it implements. The code needs Python 3.10 or later and numpy. The judge's screening step and the search tool's dense retrieval also need `sentence-transformers`. Model calls go to any OpenAI-compatible endpoint set by `OPENAI_BASE_URL` and `OPENAI_API_KEY`; nothing here holds a key.

| File | What it is |
|---|---|
| `random_choice.py` | the random-draw tool of the tree protocol: schema, checks, draw, error texts |
| `registry.py` | the registry tool: earlier projects, agenda counts and placebo list, with a file-backed population |
| `placebo_offscope_v1.jsonl` | the 267 off-topic projects of the placebo list (ours, written by a language model) |
| `labeller.py`, `agendas.json` | the agenda labeller (used live by the agenda-counts registry) and our 45 agendas |
| `judge.py` | the duplicate judge: both orders, the 0.75 rule, every-pair or screened judging |
| `minimal_loop.py` | our agent loop, with its follow-up turns, caps and compaction |
| `prompts.py` | our launch texts and the text each condition adds, assembled as we did |
| `search_tool.py`, `corpus_from_ids.py` | the search tool's ranking and output, and a script to start a corpus from the ids we release |
| `mcp_server.py` | serves the registry, random-draw or search tool to Claude Code, Codex CLI or opencode over MCP |
| `slots.py` | the seeded draw of each frontier agent's model, harness and launch prompt; checks it against `../data` |
| `run_population.py` | runs one population of one condition in the minimal loop and writes picks in our data format |
| `run_frontier.py` | runs one frontier condition over all its slots (in the minimal loop, or in a harness through a runner you supply), then judges it |
| `selftest.py` | an offline check of all of the above with a scripted fake model ($0) |

Start with `python3 selftest.py`. It needs no key and no network.

The implementations match ours where it can be checked: the registry returns the same bytes as our runner's tool, `random_choice` gives the released index for all 434 recorded frontier draws from their uniform numbers, `prompts.py` reproduces the hash of every frontier launch text it covers, and `slots.py` reproduces every frontier slot and run order in `../data`. The search tool reproduces our ranking rules and noise but not our corpus (see EXPERIMENTS.md, "What a rerun can and cannot reproduce").

## Worked example: 20 agents with a registry, judged, and their effective number

This runs the simple setup's registry of earlier projects for one population of 20 GLM-5.3-flash agents, judges every pair, and computes the effective number of projects with `../analysis`. It costs well under a dollar on OpenRouter.

```bash
export OPENAI_BASE_URL=https://openrouter.ai/api/v1 OPENAI_API_KEY=...   # your key
cd replicate

# 1. Twenty agents in sequence; agent k reads the projects of agents 0..k-1.
python3 run_population.py --condition registry_projects --model z-ai/glm-5.3-flash \
    --provider '{"order": ["Z.AI"], "allow_fallbacks": false, "require_parameters": true}' \
    --n 20 --population-seed 25261112 --out runs/registry.jsonl

# 2. The same 20 slots without a registry, for comparison (agents are independent here).
python3 run_population.py --condition max --model z-ai/glm-5.3-flash \
    --provider '{"order": ["Z.AI"], "allow_fallbacks": false, "require_parameters": true}' \
    --n 20 --population-seed 25261112 --out runs/max.jsonl

# 3. Judge every pair, pinned as in our every-pair judging.
for c in registry max; do
  python3 judge.py runs/$c.jsonl --out runs/$c.twins.jsonl --pin DeepInfra
done
```

Then compute the effective number and its interval with the same code as our reported numbers:

```python
import json, sys
sys.path.insert(0, "..")
from analysis import effnum

for c in ("registry", "max"):
    agents = [json.loads(l) for l in open(f"runs/{c}.jsonl")]
    ids = [a["agent_id"] for a in agents if a["usable"]]
    pairs = [(t["a"], t["b"]) for t in map(json.loads, open(f"runs/{c}.twins.jsonl"))]
    print(c, effnum.summarise(ids, pairs, seed=0))
```

`effective_number` is None when no pair is a duplicate, which is the expected outcome for the registry. With 20 agents the intervals are wide; our runs used four populations of 100 for this comparison (EXPERIMENTS.md, "Registry, first stage"). Pass `groups=effnum.groups_of([a["population"] for a in agents])` to count only pairs within populations when you run several. The judge must read only usable picks for the counts to match ours, so filter `runs/*.jsonl` to `usable` rows before step 3 if any session failed. In the simple setup's tree experiments we also dropped sentences about the draws from the judge text: pass `--mask-draw-sentences` to `judge.py` to do the same.

Other conditions run the same way: `--condition tree` adds the protocol paragraph and the `random_choice` tool and records every draw; `novelty`, `tree_take_best`, `registry_agenda_counts` (which calls the live labeller) and `registry_placebo` are the other arms. `--setup frontier --index DIR --launch F` runs a frontier-style agent with search in our loop.

## Running a frontier condition

`run_frontier.py` runs one frontier arm the way our runner did: the 120 slots of `slots.slots_120()` (or, with `--size 100`, the three populations of 100), each with its model, harness and launch prompt; the agent seed base + 1000p + i (bases 2026111600, 2026111300 for registries of 20, 2026111700 for populations of 100); the launch text from `prompts.launch` plus the condition's text; search and read with the agent's seed and noise 0.02; the registry, in position order within each population, registering only complete answers; the random-draw tool; both follow-ups; and one retry of a failed session. It writes `agents_<experiment>.jsonl` in the schema of `../data`, and with `--judge` every pair judged in both orders (within populations for registries) as `pairs_<experiment>.jsonl`, followed by the effective number and its interval.

```bash
python3 search_tool.py build corpus.jsonl index/ --dense          # corpus from corpus_from_ids.py
python3 run_frontier.py --condition tree --index index/ --out-dir runs/ --judge
python3 run_frontier.py --condition max  --index index/ --out-dir runs/ --judge   # its comparison arm, same day
python3 run_frontier.py --condition registry_projects --size 100 --index index/ --out-dir runs/ --judge
```

Conditions: `max`, `no_search`, `novelty`, `tree`, `tree_take_best`, `registry_projects`, `registry_agenda_counts`, `registry_placebo`. A run can be stopped and started again; agents already in the output are skipped. `--populations 0,1` and `--limit N` run part of an arm.

Two gaps to know about. The launch prompts adapted from other people's prompts (V03, V04, V08, V10, V11, V12) are not in this repository, so their 48 of the 120 slots are skipped and listed unless you supply their text with `--custom-launch FILE` (assembled from prompts section 7). In a registry population a skipped slot registers nothing, so later agents see one entry fewer than ours did; supply the texts before running registries. And by default every slot runs in our minimal loop over chat completions, whatever harness the slot names (`slot_harness` keeps it). Our GPT models went to OpenAI's API, so map them to an endpoint you can reach with `--model-map '{"openai/gpt-6-astra": "..."}'`.

To run slots in their own harness, pass `--runner MODULE:FUNCTION`. The function runs one turn of one harness session: it gets the model, the slot's harness, the system line to append, the prompt, the MCP servers to start and, for a follow-up, the previous turn's session to resume, and returns the final text and a session handle (the contract is in `run_external`'s docstring). `run_frontier.claude_code_runner` is a worked example for Claude Code in print mode. For Codex CLI and opencode, write the same function around `codex exec` / `codex exec resume` and `opencode run` / `opencode run --session`, declaring each server of `servers` as a local MCP server in the harness's config, with the system line as `developer_instructions` (Codex) or an instructions file (opencode). Each server logs its calls, from which the script decides whether to send the uncalled-tool follow-up and starts a resumed tree session's `random_choice` with `--prior-draws`.

## Using your own harness

Any harness works if it gives the agent the same text and tools and you record the five answer lines. `run_frontier.py --runner` does steps 1 to 5 for you once you supply a function that runs one harness turn; the steps below are what it does.

1. Build the launch text with `prompts.launch(...)` and the condition's `add_*` function. Put the user message in as the prompt and append the system line to the harness's own system prompt, as we did.
2. Serve the tools over MCP with `mcp_server.py`, one server process per agent session: `registry` with the agent's mode, population state file, position and population seed; `random_choice`; or `survey` with a search index, the agent's seed and the noise. Turn off every built-in tool you can; Codex and opencode keep a few, which our agents sometimes called (EXPERIMENTS.md, "Harnesses").
3. Run registry agents one at a time within a population. After each session, parse the final message with `minimal_loop.parse_final` and add the pick with `registry.Population(...).register(...)` before the next agent starts. For agenda counts, label the pick first with `labeller.live_label`.
4. Send the follow-up turns of EXPERIMENTS.md, "Exclusions, retries and follow-ups", in the same session if the agent skips the tool or the answer lines.
5. Write one JSON line per agent with at least `agent_id`, `population`, `position`, `project` and `question`, and continue from step 3 of the worked example.

## Adding a condition

To test a new intervention against ours, add it as one more arm and compare it only with arms run the same way.

1. **Write the text and the tool.** Put the added text in `prompts.py` as a constant with an `add_*` function that places it with `insert_after`, as the novelty sentence and the tree protocol are placed (after the tools sentence in the frontier setup, after the brief's first sentence in the simple setup). A new tool is a class with `schemas` and `call` like `random_choice.RandomChoice`; serve it over MCP by adding a branch to `mcp_server.py`. If agents must use it, give it a follow-up sentence and name it in `must_call` in `run_frontier.py`.
2. **Register the arm.** Add an entry to `CONDITIONS` in `run_frontier.py` (an id prefix not used in `../data`, a condition name, an experiment name), a branch in `launch_text`, and its tools in `run_loop` and `mcp_servers`. Keep the slots and seeds: a new arm on `slots_120()` with the seed base of the arm you compare against makes slot (p, i) the same model, harness, launch prompt and seed in both.
3. **Run the new arm and its comparison arms on the same slots and the same day.** Models and providers drift from day to day; several of our comparisons ran a day apart, and the same-day comparison is the cleaner one. Rerun `max` (and the placebo registry, if your arm is a registry) next to your arm rather than comparing with our released numbers, and run `python3 selftest.py` first.
4. **Judge the same way in every arm.** Every pair, both orders, the same judge, prompt, provider pin and text (`judge.pick_text` of PROJECT and QUESTION, masked in every arm or in none).
5. **Compare like with like.** An arm whose agents see each other (a registry) is measured within populations, because agents in different populations never saw each other's picks. Compare its within-population number with a within-population number of the comparison arm, computed on the same populations, never with the comparison arm's number over all pairs: a population of 20 has 190 pairs and the whole arm 7,140, so the two numbers answer different questions. Arms without a registry are compared over all pairs.
6. **Compute the effective numbers and their ratio with `../analysis`.**

```python
import json, sys
sys.path.insert(0, "..")
from analysis import effnum

def load(exp):
    agents = [r for r in map(json.loads, open(f"runs/agents_{exp}.jsonl")) if r["analysed"]]
    dup = [(p["a"], p["b"]) for p in map(json.loads, open(f"runs/pairs_{exp}.jsonl")) if p["duplicate"]]
    return agents, dup

for exp in ("frontier_registry_20_mine", "frontier_registry_20_placebo"):
    agents, dup = load(exp)
    ids = [a["agent_id"] for a in agents]
    within = effnum.groups_of([a["population"] for a in agents])        # within populations, for both arms
    print(exp, effnum.summarise(ids, dup, groups=within, seed=20261116))
```

For arms without a registry drop `groups=` in both. For a ratio between two arms on the same slots, resample slots jointly, as our tree-against-placebo test did, with `effnum.joint_ratio`: key each arm's duplicate pairs by slot, `(population, position)`, pass the slots usable in both arms, and add `groups=` for within-population arms. It draws one set of slot weights per bootstrap draw and applies it to both arms, so the interval of the ratio is narrower than two independent intervals suggest.

```python
slot = lambda agents: {a["agent_id"]: (a["population"], a["position"]) for a in agents}
(new, dn), (old, do) = load("frontier_tree_mine"), load("frontier_max")
sn, so = slot(new), slot(old)
keys = sorted(set(sn.values()) & set(so.values()))
print(effnum.joint_ratio(keys, [(sn[a], sn[b]) for a, b in dn], [(so[a], so[b]) for a, b in do], seed=20261116))
```

`ratio` is the first arm's effective number divided by the second's. The judge pairs file of the comparison arm must hold only pairs judged by the same rule, so judge the comparison arm yourself rather than mixing in our released pairs.
