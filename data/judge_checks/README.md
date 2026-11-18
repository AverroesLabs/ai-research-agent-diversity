# Checks of the duplicate judge

These files hold the blind labels behind the appendix "the judge and how far to trust it". In each check, one or two language models from other families labelled pairs of picks without seeing the judge's verdict, the experiment or the model behind each pick, and the labels are joined here to the judge's verdict on the same pair. The labellers followed the judge's own definition of a duplicate (one team's result would largely answer the other's question) with three labels. The judge is DeepSeek V4.1 Flash with the prompt in [prompts/README.md](../../prompts/README.md#10-duplicate-judge), and a pair is a duplicate when the mean of its two orders is at least 0.75.

Each row is one pair, identified by `pair_id`. Agent pairs give the two agents as `a` and `b`, using the `agent_id`s of `data/agents_<experiment>.jsonl`, and `in_data` says that both are there (true in every row). The pick texts are in the agents files, so no text is repeated here, and none of these files holds third-party text.

## Files

| File | Pairs | What was checked | Labellers |
|---|---:|---|---|
| `judge_gate_150.jsonl` | 150 | The judge's validation gate before the main runs: pairs from two early pilot runs of agents and from AI safety papers, drawn across bands of embedding similarity | Claude Opus 5.5 |
| `pilot_brief_memory_pairs.jsonl` | 360 | Pairs of agents answering the pilot brief from memory (`simple_pilot_brief`), in three samples: 120 drawn half from judge duplicates and half from other pairs the judge read, then two samples of 120 matched on the judge's score | Claude Opus 5.5 on all three, GPT-6.1 Terra on the first |
| `frontier_registry_20_pairs.jsonl` | 84 | Pairs of the frontier registry test in populations of 20, placebo and earlier-projects arms, including pairs the embedding screen kept from the judge | Claude Opus 5.5 and Qwen3.8-flash |
| `frontier_blind_90.jsonl` | 90 | Pairs within populations of all eleven frontier arms: 31 judge duplicates, 30 near misses and 29 other pairs | Claude Sonnet 5.5 and GPT-6.1 Terra |

## Fields

- `judge_score_ab`, `judge_score_ba`: the judge's verdict with `a` shown first and with `b` shown first (1 = same project, 0.5 = same direction, 0 = different, null = not parsed). `judge_score` is their mean, and `judge_duplicate` is `judge_score >= 0.75`. The frontier files give the mean only.
- `minilm_cosine`: cosine similarity of the two texts under the all-MiniLM-L6-v2 embedding model, the measure the screened judging uses.
- `label_claude`, `label_gpt`, `label_qwen`: `same_project`, `same_direction` or `different`. In `frontier_blind_90.jsonl` the labels are `yes` (same project), `borderline` or `no`. `borderline_*` is the labeller's own flag that a label was a close call.
- `stratum` and `draw` (where present): how the pair was sampled. In `frontier_blind_90.jsonl`, `judge_duplicate` pairs had a judge score of at least 0.75, `near_miss` pairs a score of 0.5 to 0.75 and a cosine of at least 0.65, and `other` is every other pair. `judged: false` in `frontier_registry_20_pairs.jsonl` marks pairs the embedding screen kept from the judge, which count as not duplicates.
- `judge_gate_150.jsonl` gives `source` instead of agent ids. Its pilot agents were run before the experiments in `data/` and are not released, and its paper pairs come from an earlier paper list.

## The numbers in the post

```python
import json
def rows(f): return [json.loads(l) for l in open(f"data/judge_checks/{f}")]
def kappa(x, y):
    n = len(x); po = sum(a == b for a, b in zip(x, y)) / n
    pe = sum((x.count(c) / n) * (y.count(c) / n) for c in set(x) | set(y))
    return (po - pe) / (1 - pe)

g = rows("judge_gate_150.jsonl")
print(kappa([r["judge_duplicate"] for r in g], [r["label_claude"] == "same_project" for r in g]))   # 0.76
p = [r for r in rows("pilot_brief_memory_pairs.jsonl") if r["sample"] == "random_and_judge_stratified"]
print(kappa([r["judge_duplicate"] for r in p], [r["label_claude"] == "same_project" for r in p]))   # 0.60
f = rows("frontier_blind_90.jsonl")
print(kappa([r["label_claude"] == "yes" for r in f], [r["label_gpt"] == "yes" for r in f]))          # 0.79
d = [r for r in f if r["judge_duplicate"]]
print(len(d), sum(r["label_claude"] != "no" and r["label_gpt"] != "no" for r in d))                # 31 30
```

The judge's agreement with the Claude labels runs from a kappa of 0.60 (the pilot brief's first sample) to 0.76 (the gate's 150 pairs). On the gate pairs it found 11 of the 16 pairs Claude called the same project, so it missed about 30%. In the frontier check the two labellers agree at a kappa of 0.79 on whether a pair is the same project, and 30 of the 31 judge duplicates are the same project or borderline for both. The per-model miss rates and corrections in the appendix pool the Claude labels of `pilot_brief_memory_pairs.jsonl` and `frontier_registry_20_pairs.jsonl`, weighting each pair by how many pairs of its judge score it stands for.
