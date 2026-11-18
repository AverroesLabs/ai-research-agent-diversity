# Agent session transcripts

This folder holds the full session of every agent in 21 of the 23 experiments in `data/`, of 240 of the 1,045 agents of a 22nd (`simple_pilot_brief`), and of none of the 23rd (`simple_sonnet_claude_code_texts_removed`), one JSON line per session, with third-party text replaced by references. Each `transcripts_<experiment>.jsonl.zst` covers one experiment and is named like the files in [`data/`](../data/). The files are compressed with zstd at level 19. Decompress one with `zstd -d FILE`, or stream it with `zstd -dc FILE | head`.

[`sample_frontier_max.jsonl`](sample_frontier_max.jsonl) holds the first three sessions of `frontier_max`, uncompressed, so the format can be read without decompressing anything.

## Files

Sizes are in MB (10^6 bytes). In all, 8,153 sessions take 484.4 MB uncompressed and 68.0 MB compressed, and the largest file is 27.0 MB.

| File | Sessions | Agents in `data/` | Uncompressed (MB) | Compressed (MB) | sha256 |
|---|---:|---:|---:|---:|---|
| `transcripts_frontier_max.jsonl.zst` | 120 | 120 | 4.4 | 0.4 | `47972137788d9107607978e3e5bec0d86784f95afa870ca00139291cdc98999c` |
| `transcripts_frontier_no_search.jsonl.zst` | 120 | 120 | 1.7 | 0.2 | `2fa3e42a8df38c1f7f4ac899b9ffe411ebdfbc8c74c9687a527d69d6c1d4ceb1` |
| `transcripts_frontier_novelty.jsonl.zst` | 120 | 120 | 5.5 | 0.6 | `b0e72e9be7e6f424352cf644a096acd6ef932364a7f8ff1c99643a91e23cd5f4` |
| `transcripts_frontier_tree.jsonl.zst` | 120 | 120 | 3.3 | 0.4 | `526f847a27ba6893f8dc3986cf2e4d696af370dc566a1a784596564779bcea23` |
| `transcripts_frontier_tree_take_best.jsonl.zst` | 120 | 120 | 3.9 | 0.4 | `218ab25f28bfaf3c8b250dd799391cc24c9125a6be4284e93e081cdd2826d0c4` |
| `transcripts_frontier_assigned_reading.jsonl.zst` | 160 | 160 | 6.0 | 0.6 | `944ab2e921a671243465570e35236b2c505ac03979fdbfc439af7bf00e05cd71` |
| `transcripts_frontier_registry_20_placebo.jsonl.zst` | 120 | 120 | 4.2 | 0.4 | `0f8d28d90884f17e6b388d2d88f24b72fbb7b9abd4fb21c6a5de963c4091dbdc` |
| `transcripts_frontier_registry_20_projects.jsonl.zst` | 120 | 120 | 4.3 | 0.4 | `041fd5ac34538a8953a0e39f7005673a4cc48b81215aa70af05082ac249230ce` |
| `transcripts_frontier_registry_20_agenda_counts.jsonl.zst` | 120 | 120 | 4.0 | 0.4 | `4c0f9584ffdef8a23517319f0126efce8320c9de4e8e1d8ab2c423854d07ac50` |
| `transcripts_frontier_registry_100_placebo.jsonl.zst` | 300 | 300 | 14.1 | 0.9 | `65b760b148542bddfb36b6563a9bf89ccd3004cef6d097e2519c4070564da537` |
| `transcripts_frontier_registry_100_projects.jsonl.zst` | 300 | 300 | 13.9 | 1.1 | `acf02a8976c5dfe754898a6c11720ba784c723c4cadb312ae5f80fd1ec7080c8` |
| `transcripts_frontier_registry_100_agenda_counts.jsonl.zst` | 300 | 300 | 9.8 | 0.9 | `2ffa31e41bdc4a41adcac798035bd700bd962af54d8e88cc67281b38e303ca5e` |
| `transcripts_frontier_earlier_groups.jsonl.zst` | 160 | 160 | 6.3 | 0.6 | `7d753f894045938bff04652f037c7fba3d094cc8ba14c670596222a89922daf9` |
| `transcripts_simple_step_one.jsonl.zst` | 1,692 | 1,692 | 170.8 | 27.0 | `38e874e558bb072cb87ed2b2d7e22dd82cf5e034f6c47a00f971f97f64f9d4f3` |
| `transcripts_simple_reading_models.jsonl.zst` | 961 | 961 | 81.4 | 11.5 | `64e2b7fadf4aa12e2703cad5a00476e9617b9aa4d751db27039fb420d9700650` |
| `transcripts_simple_reading_gpt.jsonl.zst` | 1,040 | 1,040 | 29.0 | 2.1 | `aba50092c5a67fb392f0378ff7fc07de7e0f5090a8a5e64d2cbe228477b52651` |
| `transcripts_simple_one_change.jsonl.zst` | 320 | 320 | 10.0 | 1.9 | `373251c58e69a6038e968639fe9f7023484772f0c89ce27aa28c21755c070ee3` |
| `transcripts_simple_pilot_brief.jsonl.zst` | 240 | 1,045 | 4.3 | 0.4 | `105174431f3291eb7081a3545dc3468cf50ca2af38798d4924ac80ec5a0ec346` |
| `transcripts_simple_interp_overview_removed.jsonl.zst` | 60 | 60 | 7.6 | 1.2 | `ae5d654e6cd2768ca2f4fa948ab682d99e48a0761167bab4a9fe336b41c666bf` |
| `transcripts_simple_registry_stage1.jsonl.zst` | 1,000 | 1,000 | 70.5 | 11.6 | `935d53ec8dd98933a93e706ffb52cc2c49b7612636fbf10e331072677f4dd748` |
| `transcripts_simple_tree_glm.jsonl.zst` | 420 | 420 | 25.2 | 4.5 | `7ebcb0cc9415054638ac675d9af38771a35364a04963a6bb91f47387fcbd3ecb` |
| `transcripts_simple_tree_sonnet.jsonl.zst` | 240 | 240 | 4.3 | 0.5 | `722b9f86853b39c83050491f84aae633b013568c88cbf3c975e73e341ceb13c6` |
| `sample_frontier_max.jsonl` | 3 | | 0.1 | | `7a2f73579f81e9be96c62059372af3c6aa566f974db850c3a9981a8d61a7bd42` |

Two experiments are not fully covered, because their logs were not exported before the run environment was shut down. `simple_pilot_brief` has sessions for 240 of its 1,045 agents, the GPT-6 Astra and GPT-6.1 Sol sessions with the three other instructions; the other 805 have none. `simple_sonnet_claude_code_texts_removed` has no sessions here at all. Their picks, pairs and labels are in `data/` as for every other experiment.

## Joining to the data

Every session's `agent_id` is exactly the `agent_id` of `data/agents_<experiment>.jsonl` for the same experiment name, so a session joins to its pick, its judged pairs, its agenda label and, for searching agents, its reading log. Every session has `"in_data": true`, which means its agent is in the agents file, and we checked that each one is there exactly once. Except for `simple_pilot_brief` (above), every agent in an agents file has a session here.

```python
import json, subprocess
out = subprocess.run(["zstd", "-dc", "transcripts/transcripts_frontier_max.jsonl.zst"], capture_output=True, text=True).stdout
sessions = {json.loads(l)["agent_id"]: json.loads(l) for l in out.splitlines()}
picks = {json.loads(l)["agent_id"]: json.loads(l) for l in open("data/agents_frontier_max.jsonl")}
assert sessions.keys() == picks.keys()
```

Document ids in search results, opened documents and reading lists are the ids of [`data/corpus_docs.jsonl`](../data/corpus_docs.jsonl), the list of every document in the search corpus. All 35,216 ids that appear in search or read results are in that list except one, `arxiv:2608.14611`, which agents typed into `read` and the tool resolved to the same paper filed as `web:overview_battery:c9755cab51175f2d`.

## Format

Each line is one session.

| Field | Meaning |
|---|---|
| `agent_id`, `experiment`, `condition`, `population`, `position`, `model`, `harness`, `harness_version` | As in the agents file |
| `launch_prompt_id` | The agents file's `launch_prompt`, an id from [prompts/README.md](../prompts/README.md) |
| `status` | Session status from the run (`ok` for nearly all) |
| `in_data` | Whether the agent is in `data/agents_<experiment>.jsonl` (true for every session) |
| `reading_packet` | Assigned-reading cells only: the doc ids of the list, in the order shown |
| `messages` | The session, in order (below) |
| `final_answer` | The agent's final message, from which the pick was parsed |
| `notes` | What the log could not provide, for example reasoning the provider encrypted, and how many quotes were cut |

A message has a `role` of `system`, `user`, `assistant` or `tool`. Assistant messages carry `content` (text), `reasoning` (reasoning text, where the provider returned it in clear) and `tool_calls`, a list of `{"id", "name", "arguments"}`. Tool messages carry `tool_call_id`, `name` and `tool_result`. The user message that opens a session also has `launch_prompt_id`. Later user messages are our nudges and follow-ups, marked with `followup` in the harness sessions.

Tool names are kept as each harness logged them, so the literature search appears as `search` in our loop, `mcp__survey__search` in Claude Code, `survey.search` in Codex CLI and `survey_search` in opencode. The registry and random-draw tools follow the same pattern.

### Built-in harness tools

We turned the harnesses' built-in tools off, but a few in Codex CLI and opencode could not be turned off, and some agents called them. Every call is in the sessions. None gave an agent anything but its own text back: opencode's `todowrite` stores and returns the agent's own to-do list, every `glob` and `grep` ran in an empty working directory and found nothing (two `grep` calls were refused by opencode's permission rules), Codex's `codex.list_mcp_resources` and `codex.list_mcp_resource_templates` returned empty lists, and the four `survey.read_mcp_resource` calls failed because our server offers no resources. Claude Code sessions and our loop called only our tools. Calls (sessions) per experiment, over all sessions in this folder:

| Experiment | `todowrite` | `glob` | `grep` | Codex MCP-resource tools |
|---|---:|---:|---:|---:|
| `frontier_max` | 23 (11) | 1 (1) | 0 | 2 (2) |
| `frontier_no_search` | 0 | 0 | 0 | 24 (12) |
| `frontier_novelty` | 16 (9) | 2 (2) | 0 | 1 (1) |
| `frontier_tree` | 19 (6) | 0 | 0 | 0 |
| `frontier_tree_take_best` | 11 (4) | 1 (1) | 0 | 2 (1) |
| `frontier_assigned_reading` | 29 (14) | 2 (2) | 1 (1) | 1 (1) |
| `frontier_registry_20_placebo` | 10 (3) | 1 (1) | 1 (1) | 0 |
| `frontier_registry_20_projects` | 11 (3) | 4 (4) | 0 | 1 (1) |
| `frontier_registry_20_agenda_counts` | 4 (1) | 1 (1) | 0 | 1 (1) |
| `frontier_registry_100_placebo` | 34 (9) | 6 (6) | 0 | 0 |
| `frontier_registry_100_projects` | 10 (3) | 5 (5) | 1 (1) | 1 (1) |
| `frontier_registry_100_agenda_counts` | 36 (10) | 5 (5) | 0 | 0 |
| `frontier_earlier_groups` | 32 (13) | 2 (2) | 0 | 14 (8) |
| `simple_one_change` | 0 | 0 | 0 | 12 (6) |
| All | 235 (86) | 30 (30) | 3 (3) | 59 (34) |

The 805 `simple_pilot_brief` sessions without transcripts include 164 in Codex CLI and 117 in opencode, and the 80 sessions of `simple_sonnet_claude_code_texts_removed` ran in Claude Code; their built-in tool use is not counted here.

## What the logs lack

The four harnesses log different amounts. Our loop keeps the full message list, including the model's reasoning when the provider returned it in clear. OpenAI's and Anthropic's APIs return reasoning encrypted or as a signature only, so it is missing for those models. Claude Code's stream log has every text, thinking and tool block. Codex CLI's JSON event log has messages and tool calls but no reasoning. opencode's event log has text and tool parts but no reasoning. For harness sessions the opening system and user messages were rebuilt from our run record, since the harness logs do not repeat them. Where a session was retried, the final attempt is given. In 17 Claude Code sessions with no tools, the harness wrote only its final JSON result, so they hold the final text alone. One session, `mech_interp/uniform_list/r2_a15` in `simple_step_one`, ended without a final answer, and its agents row marks it as a failed session left out of the analysis.

## What was removed

All agent-written text stays. That covers the agents' messages, reasoning, search queries, tool arguments and final answers, and the registry entries that earlier agents wrote, which agents later in a population read. Everything below was removed or replaced.

- **Search results** became a list of `{"doc_id", "url", "title"}` per result. The snippets were dropped.
- **Opened documents** became the same reference plus the page number read. The document text was dropped.
- **Assigned reading lists** became a marker in the launch message, `[reading packet of N items omitted; doc ids in reading_packet]`, plus the `reading_packet` list of doc ids. Titles and summaries were dropped.
- **Launch prompts adapted from public sources** (the `V01` to `V12` ids, including their pilot forms) became a marker naming the prompt id, and so did the system text that came with them. [prompts/README.md](../prompts/README.md) links each source and lists our changes. Our own briefs, nudges and protocol text are kept, and every one is printed in the prompts file.
- **Harness default system prompts** became a marker naming the harness and its version. They are not in the harness logs in any case.
- **Long verbatim quotes.** Some agents, mostly GLM models reading search results, copied passages from documents into their reasoning or answers. Any run of 25 or more words that matches a document the agent retrieved, or its assigned list, was replaced with `[N words quoted verbatim from a retrieved document omitted]`. This touched 2,430 passages in 998 sessions, all in `simple_step_one` (1,796 passages in 724 sessions), `simple_reading_models` (569 in 241) and `simple_interp_overview_removed` (65 in 33). Each session's `notes` say how many were cut. Shorter quotes, titles and paraphrases in the agents' own words stay.
- **Run metadata.** File paths, host names, local URLs, API and session ids, costs, token counts, usage blocks, provider routing and anything shaped like a key were dropped or replaced by `<path>`, `<local-url>` or `<redacted>`.

## Checks

For every file, the session ids equal the agent ids of the experiment's agents file, each exactly once (for `simple_pilot_brief`, a subset of them). Every session has at least one assistant message. A scan of the decompressed files found no local addresses, no paths on our machines, no `sk-` keys or bearer tokens, no `abstract` or `snippet` fields and no read-page bodies. The string `api_key` appears in three sessions, each time inside an agent's own text: a shell command that the agent wrote into a message as text, which never ran and which masks any value it would print.
