# How the experiments were run

This file is for anyone who wants to run the experiments of [Many Agents, Few Projects](README.md) again, with our setup or their own. It describes each experiment the post reports in enough detail to reproduce it: which agents ran, what text and tools they got, in what order, how their picks were judged, and how each number was computed. The prompts are printed in [prompts/README.md](prompts/README.md), the released data is described in [DATA.md](DATA.md), and [replicate/](replicate/README.md) holds small reference implementations of our tools, judge and agent loop, a driver that runs any frontier condition over its slots ([replicate/run_frontier.py](replicate/run_frontier.py)), and a worked example.

All runs took place between 8 and 18 November 2026. The models we used will be updated or retired, and the harnesses change from version to version, so a rerun should not expect our exact numbers. What a rerun can test is whether the pattern holds within our intervals: agents choosing alone crowd onto a few projects, a registry of earlier projects stops repeats, and random draws down a tree spread agents many times wider.

## Contents

- [Shared design](#shared-design): agents, harnesses, tools, populations and slots, follow-up turns, exclusions, judging, the effective number
- [The frontier setup](#the-frontier-setup): Max with search; no search; the three registries in populations of 20 and of 100, with the placebo; the tree protocol; the tree taking the best option; the novelty sentence; the assigned first document; the earlier groups of 80
- [The simple setup](#the-simple-setup): step one; model, instructions and harness; reading conditions; the registry's first stage; the tree with GLM-5.3-flash and with Claude Sonnet 5.5
- [People](#people)
- [What a rerun can and cannot reproduce](#what-a-rerun-can-and-cannot-reproduce)

## Shared design

### Agents

An agent is a model, a launch prompt and a harness. Every agent got one session and ended it by naming one project in five answer lines (DIRECTION, PROJECT, QUESTION, FIRST EXPERIMENT, WHY THIS). The date in every prompt is 2026-11-08, the cutoff of our copy of the literature.

| Model | Id we called | Route | Settings |
|---|---|---|---|
| Claude Opus 5.5 | `anthropic/claude-opus-5.5` | OpenRouter, provider pinned to Anthropic, no fallbacks | `max_tokens` 32,000 in our loop; harness defaults otherwise |
| Claude Sonnet 5.5 | `anthropic/claude-sonnet-5.5` | as Opus | as Opus |
| GPT-6 Astra | `gpt-6-astra` | OpenAI's API directly | reasoning effort low everywhere; in our loop the Responses API with `max_output_tokens` 32,000, `store` false and the encrypted reasoning passed back each turn |
| GPT-6.1 Sol | `gpt-6.1-sol` | as Astra | as Astra |
| GLM-5.3-flash | `z-ai/glm-5.3-flash` | OpenRouter, pinned to Z.AI, no fallbacks | `max_tokens` 32,000 |
| GLM-5.3 | `z-ai/glm-5.3` | OpenRouter, pinned to Novita | `max_tokens` 32,000 |
| DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | OpenRouter, pinned to DeepInfra | `max_tokens` 32,000 |

Temperature was left at each provider's default for every agent. Our loop sends the agent's seed as the `seed` parameter, which these providers ignore, so it only labels the request. OpenRouter calls carried `require_parameters` and failed rather than fall back to an unpinned provider; a session in which any call was served outside the pin was excluded (see [Exclusions](#exclusions-retries-and-follow-ups)).

### Harnesses

| Harness | Version | Models | How our text entered it |
|---|---|---|---|
| Minimal loop (ours) | [replicate/minimal_loop.py](replicate/minimal_loop.py) | all | the launch prompt's system and user messages, nothing else |
| Claude Code, print mode | 2.1.319 | Claude models only | user message as the prompt, system line via `--append-system-prompt` |
| Codex CLI (`codex exec`) | 0.167.0 | all four frontier models | user message as the prompt, system line as `developer_instructions` |
| opencode (`opencode run`) | 1.19.5 | all four frontier models | user message as the prompt, system line as an instructions file |

The harnesses kept their own default system prompts, which we do not reproduce. Each ran in a fresh home directory with no user settings, memory or plugins. We turned their built-in tools off: no shell, no file edits, no web search or fetch, and in Codex the shell, apps, plugins, browser, image generation, sub-agents and memories features disabled. Our tools were served as local MCP servers (named `survey` for search, `registry`, `random_choice`), in the same JSON schemas and with the same output text as in our loop ([replicate/mcp_server.py](replicate/mcp_server.py) gives a Claude Code command line). A few built-in tools stayed available in Codex and opencode, and some agents used them. In the released transcripts, opencode agents called `todowrite` 235 times in 86 sessions, `glob` 30 times in 30 sessions and `grep` 3 times, and Codex agents called its MCP-resource tools 59 times in 34 sessions (`list_mcp_resources` 30, `list_mcp_resource_templates` 25, and `read_mcp_resource` on our search server 4). None of these gave an agent anything but its own text back: `todowrite` stores the agent's own to-do list, every `glob` and `grep` ran in an empty working directory and found nothing or was refused, the resource lists came back empty, and every resource read failed. Claude Code and our loop called only our tools. [transcripts/README.md](transcripts/README.md#built-in-harness-tools) gives the counts per experiment. Claude Code was billed through OpenRouter's Anthropic-compatible endpoint with the Anthropic pin, and every model alias it uses for side calls was set to the session's model. In Codex and opencode the Claude models went through OpenRouter with the same pin, and the GPT models used each harness's built-in OpenAI provider with reasoning effort low (opencode's title call also went to the agent's model). Every session had a $2 spending limit (enforced during the session in our loop, in Claude Code and for the GPT models, and checked afterwards for Codex and opencode on OpenRouter), and caps on turns and tool calls high enough that they never bound.

Three harness behaviours affect what agents saw or what we parsed. Codex CLI running a Claude model through OpenRouter cut any tool result longer than about 12,000 bytes, because it falls back to generic model metadata for those models. Long registry lists and some first searches reached those agents truncated; three of the four repeats left in the registry of earlier projects (populations of 100) came from such agents, and for the assigned-first-document arm only we raised Codex's `tool_output_token_limit` so the injected paper arrived whole. Codex returns several messages and we parsed the last; opencode returns text parts that we joined, so its parsed answer is the last occurrence of each answer line in the whole session. The minimal loop compacts the conversation at 0.8 of the context window, which rarely if ever happened.

### Tools

Agents could have up to three tools, each described in full in the prompts file and implemented in [replicate/](replicate/README.md).

- **Search** ([prompts section 6b](prompts/README.md#6b-search), [replicate/search_tool.py](replicate/search_tool.py)). `search(query)` returns a JSON list of up to 10 results with id, title, source, date and a 200-character snippet; `read(id, page)` returns a short header and 8,000 characters of the document per page. It searched a frozen copy of the AI-safety literature, 99,464 papers, forum posts, research blog posts and overview pages, snapshot of 8 November 2026: 51,549 core documents (26,937 papers, 22,341 posts, 1,924 blog posts, 347 overview pages) and 47,915 papers one citation away from them. `data/corpus_docs.jsonl` lists every one of them. Ranking fuses BM25 and a small embedding model by reciprocal rank, adds a popularity term (0.25 times the document's citation or karma percentile, the `pop` field of `data/corpus_docs.jsonl`) and, per agent, Gumbel noise seeded by the agent's seed and redrawn on every repeat of a query. The frontier setup used moderate noise (scale 0.02); step one also used none (0) and high noise (0.0945). The noise levels were set so that a repeated query keeps about 89% (moderate) or 50% (high) of its top 10, against 85 to 93% for real search engines.
- **Registry** (`read_registry`, [prompts section 8](prompts/README.md#8-registry-result-2), [replicate/registry.py](replicate/registry.py)). Takes no arguments and returns the earlier agents' projects, agenda counts or the placebo list, in the format below.
- **Random draw** (`random_choice`, [prompts section 9](prompts/README.md#9-tree-protocol-result-3), [replicate/random_choice.py](replicate/random_choice.py)). Takes options, weights and a temperature, draws one option with chance proportional to weight^(1/temperature) from the operating system's random number generator, and allows six successful draws per session.

The reference implementations reproduce our registry output and our draws exactly: on 25 synthetic earlier picks, `registry.render` returns the same bytes as our runner's tool for all three arms at several positions, and `random_choice.pick` gives the released index for all 434 recorded draws of the frontier tree arm from their recorded uniform numbers.

### What text is added where

Each condition adds at most one piece of text to the launch prompt. [replicate/prompts.py](replicate/prompts.py) assembles them; its output matches the SHA-256 of every recorded frontier launch text it covers (the 72 sessions per arm with our brief or the short launch prompts, in Max, novelty, tree and tree-take-best).

| Condition | Text | Where, frontier setup | Where, simple setup |
|---|---|---|---|
| Registry (all three lists) | "Before considering a direction, check the shared registry of what other agents are already working on." | after "You have tools to search and read the research literature.", one space | after the brief's first sentence, one space |
| Novelty | "Choose the most novel direction you can find, one that few other researchers would pick." | after the tools sentence, one space | its own paragraph at the end of the user message |
| Tree protocol, with draws or taking the best | the protocol paragraph of [prompts section 9](prompts/README.md#9-tree-protocol-result-3) | its own paragraph after the tools sentence | its own paragraph after the brief's first sentence |
| No search | the tools sentences are removed (memory form of each launch prompt) | | |
| Assigned first document | none: the paper is injected into the first search result | | |

In the launch prompts other than our brief, the tools sentence ends a paragraph, so the protocol paragraph is followed by three blank lines instead of one. We kept that.

### Populations and slots

In the frontier setup each agent fills a slot, a (population, position) pair with a model, harness and launch prompt. Slots are drawn factor by factor with one Python `random.Random` seeded by a string: model uniformly from the four, harness uniformly from those the model runs in (Claude Code only for the Claude models), then launch prompt uniformly from the twelve texts (our brief F and its short form V00 count as one prompt in the post). The 120 slots, six populations of 20, are the first 80 slots of the draw seeded `"20261111:p13:field"` (populations 0 to 3, drawn for the earlier groups of 80) and one draw of 20 seeded `"20261112:act2s2:<p>"` for populations 4 and 5. The populations of 100 use `"20261117:p100:<p>"`. These strings are literal seeds and contain our internal work-item tags, kept verbatim because changing them changes every draw. [replicate/slots.py](replicate/slots.py) reproduces every slot of every released frontier agent file, and the `run_order` field, from these seeds.

Every 120-agent frontier arm uses the same 120 slots, so the arms differ only in their condition and their run date. Agent (p, i) gets seed base + 1000p + i, with base 2026111300 for the registry arms in populations of 20, 2026111600 for Max, no search, novelty, the tree and the tree taking the best, and 2026111700 for the populations of 100. A population's registry seed is base + 1000p. The seed sets the search noise and the registry's display order; the random draws are not seeded.

### Exclusions, retries and follow-ups

A session could get at most two follow-up turns, each at most once, in the same session (harnesses resumed it with `claude -p --resume`, `codex exec resume` or `opencode run --session`):

1. if the condition has a tool the agent must use and the agent ended without calling it: for the registry, "You have not checked the shared registry. Check the shared registry of what other agents are already working on, then give your final answer." followed by the answer-line reminder; for the tree, "You have not used the random_choice tool. Follow the steps above, then give your final answer.";
2. then, if the final message lacks any of the five answer lines, the answer-line reminder ([prompts section 1](prompts/README.md#1-our-brief-as-used-in-step-one-of-the-simple-setup)). Sessions with no tool at all get the no-tools paragraph in front of it.

A harness session that failed (non-zero exit or empty answer) was retried once. A pick is usable when the session finished with all five answer lines parsed, every model call was served by the pinned provider, the answer does not copy the template (a DIRECTION of "one sentence" or a QUESTION starting "as stated"), and it has a DIRECTION and a PROJECT. Only usable picks are judged and counted. Rules specific to one experiment are given in its section.

### Judging pairs

The judge reads two projects and labels the pair same project, same direction or different ([prompts section 10](prompts/README.md#10-duplicate-judge), [replicate/judge.py](replicate/judge.py)). It is `deepseek/deepseek-v4.1-flash` through OpenRouter, one user message, temperature 0, seed 0, `max_tokens` 16,000, and one retry of an order whose reply does not parse. An agent's text is its PROJECT and QUESTION lines, each stripped of spaces and a trailing period, joined by ". ". Each pair is judged in both orders, the labels score 1, 0.5 and 0, and a pair is a duplicate when the mean over the orders that parsed is at least 0.75. Because only parsed orders are averaged, a pair whose other order never parsed is a duplicate on a single same-project verdict. This was rare and we kept it.

There are two judging rules. **Every pair** judges all pairs in scope with the provider pinned to DeepInfra. **Screened** first embeds both texts with `sentence-transformers/all-MiniLM-L6-v2` and counts pairs with cosine similarity below 0.55 as different without asking the judge, and leaves the provider to OpenRouter's routing. Screening misses some of agents' duplicates and none of people's that every-pair judging found, so it can only make agents look more spread. Scope is either all pairs among an arm's agents, or only pairs within each population for registry arms, since agents in different populations never saw each other's picks.

DeepSeek V4.1 Flash is also one of the simple setup's agent models, so its agents were judged by the same model.

### The effective number of projects and its interval

The effective number is 1/p, where p is the share of pairs in scope that are duplicates. The interval is an agent bootstrap with 2,000 draws: resample agents with replacement (within each population for within-population measures), weight pairs by the product of the agents' counts, drop an agent's pairs with its own copies, floor a draw with no duplicate at half a pair, and take the 2.5th and 97.5th percentiles of 1/p. [analysis/effnum.py](analysis/effnum.py) implements it, and `python3 analysis/reproduce.py` recomputes every reported number from the released files with the seeds in [data/experiments.json](data/experiments.json). A few preregistered measures used other intervals, listed in the sections below and in `experiments.json`.

## The frontier setup

Four frontier models in the harnesses they run in, twelve launch texts ([prompts section 7](prompts/README.md#7-the-frontier-setup-the-launch-prompts-figures-1-4-and-6-and-results-2-and-3)), and our search tool at moderate noise, on the slots above. Agents that do not read a registry are independent, so their sessions ran in parallel, in the seeded run order, a few per provider at a time.

### Max: agents choosing on their own, with search (Figures 4, 6, 10, 13, A2 to A6)

- **Question.** How spread out is a field of frontier agents that each take the project they judge best?
- **Agents.** The 120 slots, seeds 2026111600 + 1000p + i, launch prompts with the tools sentence, search and read only. Answer-line follow-up only. Run on 16 November. Data: `frontier_max`.
- **Judging.** Every pair of the 120 agents (7,140 pairs), DeepInfra pin.
- **Number.** 1/p over all pairs, agent bootstrap seed 20261116. The per-model cells of Figure A2 count only pairs within one model. Figure 7 divides the duplicate share of pairs that share a model, launch prompt or harness by that of pairs that do not, with an agent bootstrap. Figure A4 counts documents opened in the search tool's logs (`reading_frontier_max.jsonl`).

### No search (Figure 6)

- **Question.** What does searching change?
- **Agents.** The same 120 slots and seeds as Max, with no tools at all: the memory form of each launch prompt (our brief without its two tool sentences; the others with "Today is 2026-11-08." alone before the answer lines). Claude Code ran in chat mode (`--tools ""`), Codex and opencode with every tool we could turn off turned off, our loop with no tools declared. Codex still offered its MCP-resource tools: 12 of these sessions called them and got empty lists. The answer-line follow-up carries the no-tools paragraph. Run on 17 November, a day after Max. Data: `frontier_no_search`.
- **Judging and number.** As Max.

### Registry in populations of 20: earlier projects, placebo and agenda counts (Result 2 text, Figures A7, A8)

- **Question.** Does a shared registry of what earlier agents chose stop them repeating each other? This was the preregistered test of Result 2.
- **Agents.** The 120 slots per arm, seeds 2026111300 + 1000p + i, registry seed 2026111300 + 1000p, with search and the registry tool, and the registry sentence after the tools sentence. The arms share slots and seeds, so slot (p, i) has the same model, harness, launch prompt and seed in every arm. Earlier projects and placebo ran on 14 November; agenda counts, added later as an exploratory arm, on 16 November.
- **Run order.** In the earlier-projects and agenda-counts arms, agents of one population ran strictly in position order, populations in parallel. After agent i finished with status ok, its parsed pick was added to its population's registry before agent i+1 started. Placebo agents depend on no one and ran in parallel.
- **What the tool returned.** A header "Shared registry of active work (n earlier agents):", one line per item starting "- ", and "End of registry.". Earlier projects: one line per registered earlier pick, "PROJECT: QUESTION", whitespace collapsed, cut at 300 characters with "…", self-references such as "As a Claude agent" masked as "[...]", in a random order seeded by (population seed, position). Agenda counts: one line per agenda with at least one earlier pick, "agenda name: n agent(s)", in the same seeded order, with labels outside the 45 agendas merged into "unclassified"; each pick was labelled when it finished by `qwen/qwen3.8-flash` pinned to Alibaba, temperature 0 ([Agenda labeller](#agenda-labeller)). Note that n in the header counts earlier agents, not lines. Placebo: k lines at position k, drawn without replacement from our list of 267 off-topic machine-learning projects ([replicate/placebo_offscope_v1.jsonl](replicate/placebo_offscope_v1.jsonl), written by a language model and screened by our labeller and by hand), shuffled by (population seed, position), lines longer than 300 characters first, cut like the project lines. [prompts section 8](prompts/README.md#8-registry-result-2) prints real examples.
- **Judging.** The preregistered rule was screened judging within populations (1,140 pairs per arm). We also judged every pair within populations (DeepInfra), and every pair across populations with both rules.
- **Number.** Within populations, 1/p pooled over the six populations. The preregistered interval was a t interval over the six population means, and the preregistered test an exact permutation test over the 6 + 6 populations of earlier projects against placebo (p = 0.002 is the smallest it can give). The agent bootstrap within populations is given beside it. The placebo arm is also the comparison arm of the preregistered tree test.
- **Rewording check.** For each earlier-projects pick at position 5 or later, the most similar earlier pick in its population was rated for overlap by Claude Opus 5.5 subagents and `openai/gpt-6.1-terra` (temperature 0, seed 0, low reasoning effort), blind to arm ([prompts section 13a](prompts/README.md#13a-registry-rewording-check)).
- **Quality.** Picks were rewritten to a neutral form by `openai/gpt-oss-120b` and rated blind by `qwen/qwen3.8-flash`, `deepseek/deepseek-v4.1-flash` and `google/gemma-4-31b-it` on importance, tractability and specificity ([prompts section 12](prompts/README.md#12-quality-raters)).

### Registry in populations of 100 (Figures 4, 9, 10)

- **Question.** Does the registry keep working as the list grows?
- **Agents.** Three populations of 100 per arm, slots drawn with `"20261117:p100:<p>"`, seeds 2026111700 + 1000p + i, registry seed 2026111700 + 1000p. Everything else as in populations of 20, for all three arms. All three ran on 17 November, a day after Max. Placebo agents ran in parallel, ordered by position then population; earlier-projects and agenda-counts agents ran in position order within each population, populations in parallel. A failed agent was retried once, and an agent failing twice would have stopped its population; none did.
- **Judging.** Every pair within each population (4,950 per population), DeepInfra pin.
- **Number.** 1/p within populations, agent bootstrap within populations (seed 20261130). Figure 9 counts distinct projects among the first k agents of each population, grouping by the judge's duplicate pairs, averaged over the three populations, with a population bootstrap; the no-registry line resamples Max's agents into populations of 100.

### Tree protocol with random draws (Result 3, Figures 4, 11, 13, A8)

- **Question.** Does drawing the project at random, down a tree of the agent's own weighted options, spread the field?
- **Agents.** The 120 slots, seeds 2026111600 + 1000p + i (the same seeds as Max), with search, the protocol paragraph after the tools sentence and the `random_choice` tool next to search and read. Uncalled-tool follow-up, then the answer-line follow-up. Run on 16 November, in the same seeded run order as Max. Data: `frontier_tree`; every draw in `tree_draws_frontier_tree.jsonl`.
- **Tool behaviour.** Weights more than 0.02 from summing to 1 return an error asking the agent to fix them; within 0.02 they are renormalised silently. Weights written as strings ("0.3" or "30%") and lists passed as JSON strings are accepted. Temperature defaults to 1. A seventh successful draw returns "Limit of six draws reached. Give your final answer." Failed calls do not count. A resumed harness session started a new tool server that carried the draw count over.
- **Judging.** Every pair of the 120 agents, DeepInfra pin, raw PROJECT and QUESTION text.
- **Number.** 1/p over all pairs, agent bootstrap seed 20261116. The preregistered test compared the tree with the placebo arm of the 20-agent registry test, on slots usable in both arms: the ratio of effective numbers counted over all pairs in each arm, with a joint slot bootstrap (2,000 draws, seed 20261116) applying one draw of slot weights to both arms. "Spreads" meant the whole interval above 1. The comparison with Max uses the same estimator.

### Tree protocol, taking the best option (Figure 13)

The same as the tree arm, with the protocol rewritten so the agent takes the option it judges best at each level ([prompts section 9b](prompts/README.md#9b-in-the-frontier-setup-figures-4-10-and-12)) and no `random_choice` tool, so only the answer-line follow-up applies. Same slots, seeds and run order. Run on 17 November. Every pair judged; number as Max. Data: `frontier_tree_take_best`.

### Novelty sentence (Figure 13)

The novelty sentence after the tools sentence, otherwise as Max. Run on 17 November. Every pair judged; number as Max. Data: `frontier_novelty`.

### Assigned first document (appendix, "What do searching agents read?")

- **Question.** Does the first paper an agent reads steer its pick?
- **Agents.** 160 sessions: the 120 slots plus 40 slots drawn again from them, a third of each (model, harness) cell with the remainder spread by the seeded draw `"20261118:w147:NA-redraw"`. Four papers were assigned 40 slots each, in seeded permuted blocks of four within each cell (`"20261118:w147:NA-assign"`): `arxiv:2610.29734` (the most-read chain-of-thought monitorability paper), `arxiv:2607.19321` (sabotage in automated research), `arxiv:2609.15803` (an on-topic theory paper) and `arxiv:2607.11070` (an off-topic paper). Seeds 2026114800 + k in slot order; run order shuffled by `"20261118:w147:NA-order"`. Run on 18 November.
- **What changed.** No prompt text. On the agent's first successful search, the assigned paper was put at rank 1 of the result list (the list stays at 10) and its first page, exactly as `read` returns it, was appended after a blank line. Later calls were unchanged. Codex with a Claude model got a larger tool-output limit so the injected result was not cut.
- **Judging.** Every pair of agents on the same model among the 120 handed the most-read, sabotage or on-topic theory paper (1,753 pairs), DeepInfra pin. Pairs across models, and the 40 agents handed the off-topic paper, were not judged for duplicates. Whether each of the 160 picks built on its assigned paper was judged separately by DeepSeek V4.1 Flash and GLM-5.3-flash.
- **Number.** The ratio of the duplicate share among same-model pairs handed the same paper to pairs handed different papers, combined across models (Mantel-Haenszel); the value and interval are in `experiments.json`.

### Earlier groups of 80 (Figure A13's bottom rows)

Two groups of 80 frontier agents run on 11 November, one with our brief and one with the brief narrowed to mechanistic interpretability ([prompts section 3](prompts/README.md#3-the-brief-narrowed-to-mechanistic-interpretability)), with search. Slots drawn with `"20261111:p13:field"` and `"20261111:p13:subfield"`, seeds 2026111100 + 1000s + k (s = 0 for the field, 1 for interpretability). Harness sessions got no follow-up turns and loop sessions the answer-line follow-up. Screened judging over all pairs. Data: `frontier_earlier_groups`.

## The simple setup

GLM-5.3-flash pinned to Z.AI, in our minimal loop, with our brief ([prompts section 1](prompts/README.md#1-our-brief-as-used-in-step-one-of-the-simple-setup)), answering from memory unless the condition says otherwise. Agents in different cells share seeds by position, so cells are paired agent by agent.

### Step one (Figures A11, A13, A15)

- **Question.** The preregistered first experiment: how spread are agents from memory, after an assigned reading list, and after searching with more or less randomness?
- **Agents.** Groups of 20. Agent a of group r has seed 20261109 + 10000r + a (plus 500,000 for the interpretability brief), also the search tool's noise seed. Cells: from memory (6 groups, 120 agents); an assigned reading list of 88 papers and posts, skewed (each agenda in proportion to its share of the literature) or uniform across agendas, one fresh list per group with its order shuffled per agent ([prompts section 6a](prompts/README.md#6a-assigned-reading)); search with no, moderate or high noise ([prompts section 6b](prompts/README.md#6b-search)). Reading-list agents made one call with no tools. The two search cells without and with high noise ran 12 groups (240 agents) for a preregistered test. Run 9 to 11 November. Data: `simple_step_one`.
- **Judging.** Screened, every valid pair counted. The preregistered analysis counted pairs within groups and gives the same picture with wider intervals.

### Model, instructions and harness, one change at a time (Figure A11)

- Models: the first 40 agents (groups 0 and 1, same seeds) of the from-memory cell for each of the seven models, with the routes in the [model table](#agents).
- Instructions: GLM-5.3-flash with the novelty sentence, the Claude Code launch prompt (V01) or AI Scientist's (V08) ([prompts section 4](prompts/README.md#4-other-instructions-in-the-simple-setup-figure-a11)), 40 agents each, same seeds.
- Harnesses: GLM-5.3-flash in Codex CLI and in opencode, 40 each, pure chat with every tool we could turn off turned off (6 Codex sessions still listed MCP resources and got empty lists), the harness's default system prompt, and our memory-form user message as the prompt (our system line was not sent). opencode sessions without answer lines got the no-tools follow-up once; Codex sessions got none.
- Every change at once: 120 agents, each drawing one cell uniformly from the feasible products of 7 models, 4 instructions and 3 harnesses with `random.Random("20261110:p12")`, seeds 2026111000 + k. In Codex and opencode the instruction's system line was not sent.
- Judging: screened, every pair. Data: `simple_one_change` and the from-memory cells of the reading experiments.

### Reading conditions for every model (Figure A13)

Step one's cells (from memory, skewed list, uniform list, search at three noise levels) re-run for GLM-5.3, DeepSeek V4.1 Flash, Claude Sonnet 5.5, Claude Opus 5.5, GPT-6 Astra and GPT-6.1 Sol in our loop, on groups 0 and 1 of step one with the same seeds, reading lists and noise, 40 agents per cell. The GPT models also ran the interpretability brief. Screened judging; in assigned-reading cells only pairs that read the same list count. Data: `simple_reading_models`, `simple_reading_gpt`. Two follow-ups reported in the text re-ran cells after removing documents from the corpus: 60 GLM-5.3-flash interpretability searchers with the same seeds (`simple_interp_overview_removed`) and 40 Claude Sonnet 5.5 agents in Claude Code on the pilot brief with 40 same-day controls (`simple_sonnet_claude_code_texts_removed`), both screened with the judge pinned to DeepInfra.

### Registry, first stage (Figure A15)

- **Question.** The preregistered first test of the three registries, from memory.
- **Agents.** GLM-5.3-flash from memory with the registry tool as its only tool and the registry sentence after the brief's first sentence ([prompts section 8a](prompts/README.md#8a-the-registrys-first-stage-in-the-simple-setup)). Earlier projects and agenda counts: four populations of 100 each, population p seeded 25261112 + 100p, agent k seed population seed + k, agents in position order. Placebo: 200 independent agents, positions 0 to 99 twice, seeded like populations 0 and 1. Tool output as in the frontier setup. In this stage a pick was registered whenever a DIRECTION line was parsed, even if other answer lines were missing; the frontier setup registered only complete answers. The follow-up texts are the tools form, since the registry counts as a tool. All 1,000 agents called the tool on their first turn. Run 12 and 13 November. Data: `simple_registry_stage1`.
- **Judging.** Screened, within populations (preregistered); the earlier-projects arm also every pair within populations.
- **Number.** Preregistered: 1/p from the mean over populations of the duplicate share, with a jackknife interval for placebo. The agent bootstrap is given beside them.

### Tree protocol with GLM-5.3-flash and with Claude Sonnet 5.5 (Figure A15)

- **Question.** The preregistered test of random draws, from memory, and its repeat on a frontier model.
- **Agents.** The protocol as its own paragraph after the brief's first sentence and `random_choice` as the only tool ([prompts section 9a](prompts/README.md#9a-in-the-simple-setup-figure-a15)); the comparison arm is the unchanged memory-form brief with no tool. GLM-5.3-flash: 300 tree agents, seeds 33261114 + 5000 + k, of which the first 120 usable by index are the reported group (all 299 usable ones in the text); 120 comparison agents, seeds 31261113 + 4000 + k, with one replacement per unusable agent at seed + 10,000. Claude Sonnet 5.5, pinned to Anthropic: seeds 35261114 + 5000 + k (tree) and 35261114 + 4000 + k (comparison); an unusable agent was followed by agent 120, 121 and so on. Tree agents got the tools-form follow-ups. GLM tree run 14 November (comparison 13 November); Sonnet 14 November.
- **Judging.** Every pair within each arm of 120, DeepInfra pin (both arms, both models). Unlike the frontier arms, the judge text of both arms here had sentences that mention the draws, the tool, copies or the procedure removed first. The PROJECT and QUESTION lines were each split into sentences after ".", "!" or "?" followed by white space, every sentence matching the regular expression below (case-insensitive) was dropped, and the rest joined as usual. `replicate/judge.py --mask-draw-sentences` applies it.

```text
random[_ ]choice|\brandom(ly)? (draw|drew|drawn|choice|walk|number)|\bdraws?\b(?! (on|from|upon|attention|conclusions?|inspiration|a line|lessons?))|\bdrew\b|\bdrawn (path|branch|option|project)|\bthe dice\b|\bcopies of (me|you|myself)\b|\bother copies\b|\bmany copies\b|\b(this|the) (procedure|protocol)\b|\b(random |metropolis[- ]?(hastings)? )walk\b|\bmetropolis\b|\bswitch(ed)? or stay\b|\b(switch|stay)\" ?\b|\bthe tool (returned|chose|picked|landed)|\blanded (on|there)\b|\bmy (weights|probabilities)\b|\bless crowded\b
```
- **Number.** 1/p per arm, agent bootstrap; the ratio uses independent agent bootstraps of the two arms. Quality: the normaliser and three raters of [prompts section 12](prompts/README.md#12-quality-raters), with a preregistered non-inferiority margin of 0.13 points on the 10-point scale.

### Agenda labeller

Figures A6, A7 and A8 put each pick into one of 45 agendas merged from the [2025 Shallow Review](https://www.greaterwrong.com/posts/Wti4Wr7Cf5ma3FGWa/shallow-review-of-technical-ai-safety-2025-2) ([prompts section 11](prompts/README.md#11-agenda-labeller-figures-a6-and-a7-and-the-agenda-counts-registry), [replicate/labeller.py](replicate/labeller.py)). The labeller sees the DIRECTION line, " Why: " and the WHY THIS line. For the figures, GLM-5.3-flash pinned to Z.AI at temperature 0 labels batches of five, in three shuffles seeded 1, 2 and 3, and takes the majority label, else the first valid one. The agenda-counts registry labelled each pick alone with `qwen/qwen3.8-flash` pinned to Alibaba. The prompt carried a short excerpt of the Shallow Review's description of each agenda; that text is not ours, so [replicate/agendas.json](replicate/agendas.json) has our ids, names, groups and rules and leaves the descriptions for you to add.

## People

Figure A1 and the people columns of Figure 4 compare agents with people's own choices: AI-safety papers and LessWrong posts from 2025 and 2026, SPAR mentor project proposals, and team projects from six Apart hackathons. Each source is 16 random groups of 40, released as item ids and links in `data/people/`. The judge reads the title, ". ", and the first 55 words of the abstract or proposal (followed by " ..." when cut), with screened judging over every pair within a group. A source's number is 1 over the mean duplicate share of its 16 groups, with the middle 95% of the groups' own values as its range; the four broad-theme hackathons weight each event equally. [analysis/effnum.py](analysis/effnum.py) (`people_summary`) computes it. People's texts are not ours to release; DATA.md explains how to rebuild the judge's input from the links.

## What a rerun can and cannot reproduce

Exactly reproducible from this repository: every slot, seed and run order of the frontier setup; every launch text that is ours; the registry's output for any sequence of picks; the random-draw tool's behaviour given its uniform numbers; the judge's prompt and settings; and every reported effective number and interval, from the released duplicate pairs.

Reproducible only in pattern: the agents' picks. The models sample at provider-default temperature, providers ignore the seed, and the random draws come from the operating system. The model versions of November 2026 may be retired, providers change the weights behind a model id, and harness versions change their system prompts and tools. A rerun with the same models should land inside our intervals, and one with newer models tests whether the pattern carries over.

Not reproducible from this repository alone: the inputs below are not ours to release, or were not kept. Each line says what we release instead and how to approximate the missing part.

- [ ] **The search corpus's texts.** We release the list of all 99,464 documents the tool searched (`data/corpus_docs.jsonl`: id, link, kind, year, layer, the title of each paper and post, and the popularity percentile `pop` the ranking used) and what each searching agent opened (`data/reading_frontier_max.jsonl` and the [transcripts](transcripts/README.md)). To approximate: `python3 replicate/corpus_from_ids.py --out corpus.jsonl --fetch-arxiv` adds arXiv titles and abstracts; add LessWrong, Alignment Forum and EA Forum post texts and the blog and overview pages from their links; then `python3 replicate/search_tool.py build corpus.jsonl index/ --dense`. Our corpus served full text for most core arXiv papers and abstracts or page text for the rest, so a rebuilt corpus ranks somewhat differently, and the search conditions are the least exactly reproducible part of the study.
- [ ] **The popularity scores, exactly.** `pop` was recomputed from the same frozen citation and karma inputs with the corpus build's rule (mid-rank percentile of citations within field and year for papers, of karma within forum and year for posts). The document order and kinds match the tool's index exactly, but the recomputed scores are not byte-identical to the index's own popularity array, which was lost with the machine it was built on, so treat them as a close reconstruction.
- [ ] **The full text of the launch prompts adapted from other people's prompts** (V03, V04, V08 and V10, and the system text of V11 and V12, with their pilot-brief forms). [prompts section 7](prompts/README.md#7-the-frontier-setup-the-launch-prompts-figures-1-4-and-6-and-results-2-and-3) links each source and lists every change we made. To approximate: assemble each text from its source and our changes, and pass it to `replicate/run_frontier.py --custom-launch` (or put it in `prompts.CUSTOM_LAUNCH`). Without them, a rerun covers the 72 of 120 slots whose launch prompt is ours or short enough to print.
- [ ] **The harnesses' default system prompts.** They belong to their developers and ship with each version. To approximate: install Claude Code 2.1.319, Codex CLI 0.167.0 and opencode 1.19.5, which carry them; a newer version changes them and should be recorded as a difference.
- [ ] **The assigned reading lists' titles and summaries** (step one and the reading conditions). Each session's list is in its transcript as document ids (`reading_packet`), in the order shown. To approximate: rebuild each item from `corpus_docs.jsonl` and the paper's abstract.
- [ ] **The Shallow Review's agenda descriptions in the labeller prompt.** [replicate/agendas.json](replicate/agendas.json) has our ids, names, groups and rules. To approximate: add each agenda's description from the [2025 Shallow Review](https://www.greaterwrong.com/posts/Wti4Wr7Cf5ma3FGWa/shallow-review-of-technical-ai-safety-2025-2).
- [ ] **People's texts.** Released as ids and links; DATA.md explains how to rebuild the judge's input from them.
- [ ] **Our GPT loop's Responses API client.** The reference loop speaks chat completions. To approximate: run the GPT models through an OpenAI-compatible chat endpoint with reasoning effort low, or port `minimal_loop.run_session` to the Responses API with `store` false and the encrypted reasoning passed back each turn.
- [ ] **The model weights and provider behaviour of November 2026.** Model ids, routes and pins are in the [model table](#agents); providers may change what an id serves, so record the date and the provider that served each call.
