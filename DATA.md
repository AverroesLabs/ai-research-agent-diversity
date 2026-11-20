# Data

This file describes the data behind [Many Agents, Few Projects](README.md). Every file in `data/` is JSON Lines (one JSON object per line) except `data/experiments.json`. The prompts are in [prompts/README.md](prompts/README.md), and `analysis/reproduce.py` recomputes every effective number in `experiments.json` from these files.

## Experiments

Each experiment is one set of agents run under one setup. Names start with `frontier_` for the frontier setup (four frontier models in their harnesses, eleven launch prompts, searching a frozen copy of the AI safety literature) and `simple_` for the simple setup (open and frontier models answering our brief in our own minimal agent loop, unless the conditions say otherwise). The release holds every experiment whose numbers appear in the post and its appendix, and nothing else.

| Experiment | What varies | Agents | Figures | Preregistered |
|---|---|---|---|---|
| `frontier_max` | nothing added: each agent takes the project it judges best | 120 | 2, 4, 6, 8, 9, 12, A2-A6, A8 | no |
| `frontier_no_search` | the same 120 combinations of model, launch prompt and harness, without search | 120 | 6, A4 | no, extension preregistered before running |
| `frontier_novelty` | adds one sentence asking for the most novel direction | 120 | 12 | no, as above |
| `frontier_tree_take_best` | tree protocol, but the agent takes its best option at each level | 120 | 12 | no, as above |
| `frontier_tree` | tree protocol with the random-draw tool | 120 | 4, 10, 12, A8, A10 | yes |
| `frontier_registry_20_placebo` | registry tool listing unrelated projects, 6 populations of 20 | 120 | Results 2 and 3 text, A8, A9 | yes |
| `frontier_registry_20_projects` | registry of earlier agents' projects, 6 populations of 20 | 120 | Result 2 text, A8, A9 | yes |
| `frontier_registry_20_agenda_counts` | registry of agenda counts, 6 populations of 20 | 120 | Result 2 text, A8, A9 | no |
| `frontier_registry_100_placebo` | placebo list, 3 populations of 100 | 300 | 8, 9, A6 | no, extension preregistered before running |
| `frontier_registry_100_projects` | registry of earlier projects, 3 populations of 100 | 300 | 4, 8, 9, A6 | no, as above |
| `frontier_registry_100_agenda_counts` | agenda counts, 3 populations of 100 | 300 | 8, 9, A6 | no, as above |
| `frontier_assigned_reading` | one assigned paper returned first by the agent's first search, 4 papers × 40 agents | 160 | A5 text | no, as above |
| `frontier_earlier_groups` | the frontier setup's earlier groups of 80, with our brief and with the interpretability brief | 160 | A14 | no |
| `simple_step_one` | step one: GLM-5.3-flash under six reading conditions, with our brief and the interpretability brief | 1,692 | A12, A14, A16 | yes (design); the every-pair counting reported is exploratory |
| `simple_reading_models` | step one's reading conditions for GLM-5.3, DeepSeek V4.1 Flash, Claude Sonnet 5.5 and Claude Opus 5.5 | 961 | A3 text, A12, A14 | no |
| `simple_reading_gpt` | step one's reading conditions for GPT-6 Astra and GPT-6.1 Sol, both briefs | 1,040 | 2, A12, A14 | no |
| `simple_one_change` | one change at a time to the instructions or harness, and every change at once | 320 | A7, A12 | no |
| `simple_pilot_brief` | the pilot brief, with its extra paragraph on resources: seven models, three other instructions, two other harnesses, every change at once | 1,045 | A7 (pilot-brief chart), A12 text, A17, judge appendix | no |
| `simple_interp_overview_removed` | step one's interpretability search cell re-run after removing the overview post most searchers opened first | 60 | A14 text | no, follow-up preregistered before running |
| `simple_sonnet_claude_code_texts_removed` | Claude Sonnet 5.5 in Claude Code, with the two most-read chain-of-thought texts removed or in place | 80 | A14 text | no, as above |
| `simple_registry_stage1` | the registry's first stage: earlier projects and agenda counts (4 populations of 100 each), placebo (200) | 1,000 | A16 | yes |
| `simple_tree_glm` | GLM-5.3-flash with and without the tree protocol | 420 | A10, A16 | yes (first 120 tree agents) |
| `simple_tree_sonnet` | Claude Sonnet 5.5 with and without the tree protocol | 240 | A10, A16 | yes |

`data/experiments.json` gives, for each experiment, a description, the figures it fills, whether it was preregistered, run dates, numbers of agents, pair rows and duplicates, the list of its files, and one or more **measures**. A measure is one effective number as reported, with what is needed to recompute it: the agents file and the filters that pick its agents (`condition`, `model`, `populations`, `batch`, and `only_analysed`), the pairs file and judging rule, whether pairs are counted among all agents (`all_pairs`) or only within each population (`within_population`), the interval method, the bootstrap seed and the agent order. `reported_ratios`, `reported_cells`, `reported_counts` and `reported_extra` hold other numbers quoted in the post; a ratio with a `check` (the tree against the placebo registry) is recomputed by `reproduce.py` with `effnum.joint_ratio`. `people` describes the people's groups.

## Agent ids and their codes

Agent ids carry short codes for the arm they ran in. They are labels only; the `experiment` and `condition` fields say the same thing in words.

| Id pattern | Experiment | Condition |
|---|---|---|
| `N_pop<p>_a<i>` | `frontier_max` | each agent takes the project it judges best, with search (Max) |
| `N0_pop<p>_a<i>` | `frontier_no_search` | Max without search |
| `NV_pop<p>_a<i>` | `frontier_novelty` | the novelty sentence |
| `TT_pop<p>_a<i>` | `frontier_tree` | the tree protocol with random draws |
| `TW_pop<p>_a<i>` | `frontier_tree_take_best` | the tree protocol, taking the best option |
| `D_pop<p>_a<i>` | `frontier_registry_20_projects`, `frontier_registry_100_projects` | registry of earlier projects |
| `P_pop<p>_a<i>` | `frontier_registry_20_placebo`, `frontier_registry_100_placebo` | placebo list |
| `C_pop<p>_a<i>` | `frontier_registry_20_agenda_counts`, `frontier_registry_100_agenda_counts` | agenda counts |
| `NA_pop<p>_a<i>`, `NA_pop<p>_a<i>_x` | `frontier_assigned_reading` | assigned first document; `_x` marks the 40 slots drawn a second time |
| `ai_safety/field_a<k>`, `mech_interp/subfield_a<k>` | `frontier_earlier_groups` | our brief, and the brief narrowed to interpretability |
| `<brief>/<reading>/r<group>_a<k>` | `simple_step_one` | brief and reading condition; `r<group>_fill<n>_a<k>` is a replacement agent |
| `<model>/<brief>/<reading>/r<group>_a<k>` | `simple_reading_models`, `simple_reading_gpt` | the same cells for one model |
| `<change>/r<group>_a<k>`, `<harness>/none_<k>`, `every_change_at_once/a<k>` | `simple_one_change` | the one change made (instruction or harness), or every change at once |
| `<instruction>:<model>:<harness>/none_<k>`, `every_change_at_once_pilot/a<k>` | `simple_pilot_brief` | the pilot-brief cell |
| `mech_interp/search_no_randomness/overview_pages_removed/r<group>_a<k>` | `simple_interp_overview_removed` | the interpretability search cell, overview post removed |
| `texts_removed/varied_<k>`, `texts_in_place/varied_<k>` | `simple_sonnet_claude_code_texts_removed` | the two chain-of-thought texts removed or in place |
| `S1_D_pop<p>_a<i>`, `S1_C_pop<p>_a<i>`, `S1_P_pop<p>_a<i>` | `simple_registry_stage1` | the registry's first stage: earlier projects, agenda counts, placebo |
| `tree_a<k>`, `max_a<k>` | `simple_tree_glm`, `simple_tree_sonnet` | with the tree protocol, and the comparison arm without it |

`<p>` is the population and `<i>` the position in it, both zero-padded. The experiment names follow one rule: `frontier_` for the frontier setup, `simple_` for the simple setup, including `simple_sonnet_claude_code_texts_removed`, which runs Claude Sonnet 5.5 in Claude Code on the simple setup's pilot brief.

The seed strings in EXPERIMENTS.md and [replicate/slots.py](replicate/slots.py), such as `"20261111:p13:field"`, `"20261112:act2s2:<p>"`, `"20261116:w118:tree-order"` or `"20261118:w147:NA-redraw"`, contain our internal work-item tags (`p13`, `act2s2`, `w118`, `w147`). We kept them verbatim because they are seeds: a generator seeded with any other string draws different slots, run orders and assignments, so they must be used exactly as written.

## How a duplicate is defined

A judge model, DeepSeek V4.1 Flash on OpenRouter (temperature 0, seed 0, up to 16,000 output tokens, one retry of an unparsable reply), reads two projects and labels the pair *same project* (one team's result would largely answer the other's question), *same direction* (same agenda, different question or method) or *different*. Its prompt is in [prompts/README.md](prompts/README.md#10-duplicate-judge). An agent's project is its PROJECT line and its QUESTION line joined by ". ". A person's item is its title and the first 55 words of its abstract or description.

Each pair is judged in both orders. The labels score 1, 0.5 and 0, and a pair is a **duplicate** when the mean of the two orders is at least 0.75: both orders say same project, or one says same project and the other same direction.

There are two judging rules.

- **Every pair** (`every_pair`): the judge reads every pair of agents. The judge's provider was pinned to DeepInfra with no fallbacks, in every experiment that used this rule. All main-post frontier numbers use this rule.
- **Screened** (`screened`): pairs whose texts have cosine similarity below 0.55 under the `sentence-transformers/all-MiniLM-L6-v2` embedding are counted as not duplicates without asking the judge. The provider was left to OpenRouter, except in the two text-removal checks, where it was pinned to DeepInfra. This was the preregistered rule for the frontier registry's populations of 20 and the registry's first stage, and it is used for people's groups and all the simple-setup grids. It misses some of agents' duplicates (and none of people's that judging every pair found), so it can only make agents look more spread.

## Effective number of projects

The effective number is 1 / p, where p is the share of pairs that are duplicates, counted among all agents or only within populations as the measure says. Three interval methods appear in `ci_method`.

- `agent_bootstrap`, used for every frontier number and the simple-setup interventions of Figure A16: 2,000 draws that resample the agents with replacement (within each population for within-population measures), weight each pair by w_i w_j, drop the pairs of an agent with its own copies, floor a draw with no duplicate at half a pair, and take the 2.5th and 97.5th percentiles of 1 / p* as order statistics. `effnum.summarise` implements it.
- `stratified_agent_bootstrap`, used for the simple-setup grids of Figures A12 and A14: the same resampling done within each group of 20, with pairs counted across groups, the percentiles taken with linear interpolation and no floor. `effnum.stratified_bootstrap` implements it.
- A delete-one-agent jackknife on the logit of the duplicate share, which several appendix figures drew, and a few preregistered methods (a t interval over populations, a jackknife over agents, a mean over populations). For these, `reproduce.py` checks the point estimate and prints its own bootstrap beside the reported interval. Where a cell also recorded an agent bootstrap with its seed (`reported_bootstrap_ci95`), that one is recomputed and compared.

With the seed in `experiments.json` and the agent order the measure names, the script reproduces every reported point estimate and every bootstrap interval. People's numbers pool 16 random groups of 40 items from one source: 1 / mean duplicate share over the groups, with the middle 95% of the groups' own values as its range. The four broad-theme hackathons weight each event equally and take the range over all 64 groups.

## Files

`agent_id` is unique within an experiment, but the same id can appear in two experiments (for example `D_pop00_a24` in both registry populations), so key agents by experiment and id.

### `agents_<experiment>.jsonl`

One line per agent, every session that ended with a parsed answer, including the few that the analysis left out. Every agents file has `analysed` and `excluded_because`; in the frontier experiments and `simple_registry_stage1` every agent was analysed, so they are `true` and null throughout.

| Field | Meaning |
|---|---|
| `agent_id` | id within the experiment; [Agent ids and their codes](#agent-ids-and-their-codes) explains the codes |
| `experiment`, `condition` | experiment name and condition, e.g. `max`, `tree_random_draw`, `placebo_list`, `registry_of_earlier_projects`, `agenda_counts`, `ai_safety/search_no_randomness`, or `pilot_brief:gpt-6-astra:codex_cli` (instruction, model and harness) |
| `population`, `position` | population and place in its order. In registries agents choose one at a time, each pick joining the registry before the next agent starts. In the simple setup the population is the group of 20 that shared a reading list or search seed. In frontier arms without registries the same 6 × 20 slots are reused, so slot (p, k) has the same model, launch prompt and harness in every frontier experiment with 120 agents |
| `model` | model id (`anthropic/...`, `z-ai/...` and `deepseek/...` through OpenRouter, `openai/...` through OpenAI's API) |
| `harness`, `harness_version` | `claude_code`, `codex_cli`, `opencode` or `minimal_loop` (our own short tool-calling loop) |
| `launch_prompt` | an id from [prompts/README.md](prompts/README.md): `F` (our brief, section 1, or in the frontier setup section 7) or one of the `V..` ids of section 7; `F_novelty` (section 4a); `F_pilot` (the pilot brief, section 2); and `F_pilot_novelty`, `V01_terse_run_research_pilot` and `V08_ai_scientist_v1_pilot`, the pilot-brief forms of section 13d. The texts themselves are not in the data files |
| `brief` | the scope and form of the brief |
| `reading` | simple setup and earlier groups: `from_memory`, `skewed_list` or `uniform_list` (an assigned list of 88 papers and posts, [section 6a](prompts/README.md#6a-assigned-reading)), or search with no, moderate or high randomness in the results |
| `run_date` | UTC date of the session |
| `batch` | `replacement` for sessions run later to replace ones the analysis left out; `first_120` and `extension` for the GLM tree agents (the preregistered test used the first 120) |
| `analysed`, `excluded_because` | whether the published analysis used the agent, and why not: a failed session, an answer that copies the format template, or a catch-all label meaning no direction in the field |
| `direction`, `project`, `question`, `first_experiment`, `why` | the five answer lines the agent ended with |
| `run_order` | frontier only: the slot's place in the run order shared by the 120-agent frontier experiments |
| `assigned_document` | `frontier_assigned_reading` only: the paper returned first |
| `reading_list_sha256` | `simple_step_one` only: the hash of the assigned list the agent read |

### `pairs_<experiment>.jsonl`

Every pair the judge read, one row per pair and rule: `{"experiment", "a", "b", "score_ab", "score_ba", "score", "duplicate", "rule", "both_orders_cached"}`, plus `counted_in_published_analysis` in the simple-setup files. `score_ab` is the verdict with `a` shown first and `score_ba` with `b` first (1, 0.5 or 0, null if not parsed), `score` is their mean, and `duplicate` is `score >= 0.75`. Under every-pair judging the file lists every pair of the experiment's agents that was judged. Under screened judging, a pair below the screen has no row and counts as not a duplicate, except in `frontier_registry_20_*` and `simple_registry_stage1`, whose screened rows list every pair the analysis counted, with score 0.0 for a pair below the screen and null per-order scores where the per-order verdicts were not kept.

Some judged rows come from other analyses than the published one. The judge's cache also holds pairs it read later, below the screen, for other checks. Where such a pair is a duplicate in a published simple-setup cell, `counted_in_published_analysis` is `false` and the screened rule counts it as not a duplicate, as the published analysis did. For other rows the field is `true` or null. In `simple_reading_gpt`, 724 rows with null scores are the duplicate pairs between the first 40 GPT-6 Astra agents from memory and the 80 that brought the cell to 120 (Figure 2). Their verdicts were judged in the published analysis, but only the list of duplicate pairs survives.

### `twin_pairs_<experiment>.jsonl`

Duplicate pairs only, where the other verdicts were not recovered: `{"experiment", "a", "b", "rule"}`. Three experiments have them:

- `frontier_registry_20_agenda_counts`: all its duplicate pairs (every pair within populations, and screened within and across populations). This arm's per-pair verdicts were not recovered from the judge's cache.
- `frontier_registry_20_placebo` and `frontier_registry_20_projects`: the duplicate pairs of the screened judging across populations (`screened_all_pairs`). Their other judgings are in their pairs files.

A judged pair that is not listed was judged not a duplicate.

### `labels_<experiment>.jsonl`

`{"agent_id", "labeller", "agenda"}`: each agent's agenda among the 45 of the [2025 Shallow Review of technical AI safety](https://www.greaterwrong.com/posts/Wti4Wr7Cf5ma3FGWa/shallow-review-of-technical-ai-safety-2025-2), with ids as in the labeller prompt ([prompts/README.md](prompts/README.md#11-agenda-labeller-figures-a6-and-a7-and-the-agenda-counts-registry)). The main labeller is GLM-5.3-flash, majority of three batchings. Some experiments also carry a second labeller from another family (GPT-6.1 Terra), and the agenda-counts registries carry the live labels (Qwen3.8-flash) that the registry showed to later agents.

### `tree_draws_<experiment>.jsonl`

Each tree agent's calls to the random-draw tool. In `tree_draws_frontier_tree.jsonl`: `{"agent_id", "n_draws", "nudged", "draws"}`, where each draw has the `options`, `weights` and `temperature` the agent passed, the uniform number `u` used, the drawn `index` and `choice`, and any `error` the tool returned. The two `simple_tree_*` files have the same draws with the agent's turn instead of `u`.

### `reading_frontier_max.jsonl` and `corpus_docs.jsonl`

What each agent of `frontier_max` did with the search tool: `{"agent_id", "experiment", "n_searches", "queries", "opened"}`. `opened` lists each document opened, by its id in our frozen copy of the literature, with its kind and year.

`corpus_docs.jsonl` lists every document in that frozen copy, the corpus the search tool searched: 99,464 rows, the same count as the index the tool used. The two text-removal experiments searched it with a few documents taken out, as EXPERIMENTS.md describes. Each row is `{"doc_id", "url", "kind", "year", "title", "layer", "pop"}`. `kind` is `paper` (74,852), `post` (22,341, LessWrong, Alignment Forum and EA Forum), `blog` (1,924) or `overview` (347). `title` is given for papers and posts and is null for blog and overview pages. `layer` is `core` (51,549 AI-safety documents) or `neighbour` (47,915 papers one citation away from the core, which the tool searched by keyword only). `pop` is the popularity the ranking added at weight 0.25: for papers, the mid-rank percentile of the paper's citation count among papers of the same field and year (falling back to year, then to all papers, for groups under 30), for posts the percentile of its karma among posts of the same forum (EA Forum, or LessWrong and the Alignment Forum) and year, as a number from 0 to 1. It is null for 3,295 documents with no count, which the tool gave the median of their kind (all blog and overview pages, 1,023 papers and one post). We recomputed `pop` from the corpus build's frozen citation and karma inputs with its rule; the document order and kinds match the tool's index exactly, but the scores are not byte-identical to the index's own popularity array, so treat them as a close reconstruction. No abstracts, texts, citation counts or karma are included. The corpus's own build file was lost with the machine it was built on, so we rebuilt this list by re-running the corpus build's merge and scope-drop steps on the same frozen inputs, which gives exactly the document count and the count in each layer and kind that the tool reported. Every document id that appears in a released session's search or read results is in the list, apart from one alias that the tool resolved to a listed paper (see [transcripts/README.md](transcripts/README.md)). [replicate/corpus_from_ids.py](replicate/corpus_from_ids.py) turns the list into a corpus for the reference search tool.

### `judge_checks/`

The blind labels behind the judge appendix: pairs of picks that a Claude model, and for some sets a GPT or Qwen model, labelled without seeing the judge's verdict, joined to that verdict by pair. Agent pairs use the `agent_id`s of `data/agents_<experiment>.jsonl`. No pick texts or third-party texts are included. [data/judge_checks/README.md](data/judge_checks/README.md) describes each file and recomputes the agreement figures the post quotes.

### `transcripts/`

The full sessions of 8,153 agents in 22 experiments, compressed with zstd, one file per experiment, joined to `data/` by `agent_id`. Search results, opened documents and reading lists are reduced to document ids, links and titles, adapted launch prompts to their ids, and any run of 25 or more words copied verbatim from a retrieved document is cut. [transcripts/README.md](transcripts/README.md) gives the format, what was removed, what each harness's logs lack and a checksum for each file. Two experiments are not fully covered: `simple_pilot_brief` has sessions for 240 of its 1,045 agents and `simple_sonnet_claude_code_texts_removed` has none.

### `people/`

For each source of people's work (`papers`, `posts`, `spar_proposals`, `hackathon_one_theme`, `hackathon_same_models` and four broad-theme hackathons):

- `items_<source>.jsonl`: `{"item_id", "url"}` for every item in any group;
- `groups_<source>.jsonl`: `{"group", "item_ids"}`, the 16 random groups of 40;
- `pairs_<source>.jsonl`, for the first five sources: every pair the judge read, with its verdicts as in the agents' pairs files and `groups`, the groups that contain the pair (screened judging);
- `duplicates_<source>.jsonl`, for the four broad-theme hackathons: `{"group", "a", "b"}`, the duplicate pairs found in each group.

The per-pair verdicts of the four broad-theme Apart hackathons (Global South AI Safety 2026, def/acc 2025, AI Manipulation 2026 and Digital Minds 2026) are lost: they were judged after our last archive of the judge's cache, and that cache was not kept. Only their duplicate pairs and their pooled results are released, and `reproduce.py` recomputes the pooled numbers from them.

## Numbers that cannot be recomputed from these files

- The pooled rows of Figure A12 (seven models, four instructions, three harnesses, and the one-change groups without the GPT models) mix agents from several experiments. Pairs between agents of different experiments were not kept, so `simple_one_change` gives these pools as `reported_cells` only. The same holds for the mixed row of Figure A14.
- The control arm of `simple_interp_overview_removed` (step one's first 60 agents of that cell, re-judged with the judge pinned to DeepInfra) is reported in `reported_extra`; its re-judged verdicts were not kept.
- `frontier_assigned_reading` reports a ratio of duplicate rates in the text. Its pairs are released, but not as an effective number. They cover the 120 agents handed the most-read, sabotage or on-topic theory paper, same-model pairs only; the 40 agents handed the off-topic paper were not judged for duplicates.

## What is released as ids only, and why

People's texts (SPAR mentor proposals, Apart hackathon project pages, paper abstracts and LessWrong posts) belong to their authors, so we release ids and links, not the texts. To rebuild the judge's input, open each URL and take the title and the first 55 words of the abstract or description (for SPAR, the summary followed by the "about" text). Paper ids map to `https://arxiv.org/abs/<id>` or `https://doi.org/<id>`, and post ids to `https://www.lesswrong.com/posts/<id>`. Pages can change after our retrieval in November 2026.

Also not included: the full text of the launch prompts that adapt someone else's public prompt (the data refers to each by its id, and the prompts file links each source and lists our changes), the reading lists given to agents (third-party titles and summaries), the harnesses' own default system prompts (they belong to their developers; versions are given), and the texts of the frozen literature corpus and its search index (`corpus_docs.jsonl` lists the documents). The session transcripts are in [transcripts/](transcripts/README.md), with the third-party text in them replaced by references.

## Quality ratings (not used in the post)

`quality_<experiment>.jsonl` holds one row per pick and rater: `{"agent_id", "rater", "importance", "tractability", "specificity"}`, each criterion scored 1 to 10 by three language models (`qwen/qwen3.8-flash`, `deepseek/deepseek-v4.1-flash`, `google/gemma-4-31b-it`) that never saw the arm. Ratings exist for the simple setup's tree and no-tree picks, the simple setup's registry stage and the frontier registry test in populations of 20. The prompts and the blinding steps are in `prompts/README.md`, section 12. The post does not report these ratings, because today's models judge promise too weakly and inconsistently for them to say much; we release them for anyone who wants to examine them.

