"""The agenda labeller: puts a pick into one of 45 AI-safety agendas (EXPERIMENTS.md, "Agenda labeller").

Two uses, with the same prompt:
- the agenda-counts registry labels each pick live, before the next agent starts: one call per pick,
  qwen/qwen3.8-flash pinned to Alibaba on OpenRouter, temperature 0 (live_label below);
- the agenda figures label all picks afterwards: GLM-5.3-flash pinned to Z.AI, temperature 0, batches of 5 in three
  seeded shuffles (seeds 1, 2, 3), majority label, else the first valid label (majority_of_three below).

The text of a pick is its DIRECTION line, " Why: ", and its WHY THIS line. The prompt lists every agenda with our id,
name, group and boundary rule. The prompt we sent also carried, after each name, the first ~120 characters of each
merged Shallow Review agenda's description; that text is not ours, so agendas.json leaves it out. Pass your own
`descriptions` ({shallow_review_leaf_name: text}) to rebuild the exact prompt; without it the prompt has no
descriptions, a small change to what the labeller sees.
"""
import json
import random
import re
from pathlib import Path

import llm

HERE = Path(__file__).resolve().parent
LIVE_MODEL, LIVE_PIN = "qwen/qwen3.8-flash", {"order": ["Alibaba"], "allow_fallbacks": False, "require_parameters": True}
BATCH_MODEL, BATCH_PIN = "z-ai/glm-5.3-flash", {"order": ["Z.AI"], "allow_fallbacks": False}

RULES = """PROBLEM VS METHOD. Many picks name both a target problem and a method. Apply in order:
1. Read the direction sentence for the target problem and the method. Motivation in "Why" (detect misalignment, ensure alignment, oversight will not scale) never decides the category.
2. Narrow problem wins. If the pick is about one of these problems, label by the problem whatever method it uses (probes, circuits, SAEs, causal tests, formal methods), and put the method's category as secondary:
   - stated reasoning or chain of thought not matching the computation that drives the output (CoT faithfulness, legibility) -> cot_monitor
   - a model recognising it is being tested, evaluation vs deployment awareness, situational awareness -> sa_evals
   - hidden or encoded reasoning, steganography -> stego_evals
   - systems that recognise their own unreliability and escalate, defer, or accept correction or interruption -> corrigibility
3. Deception, scheming, hidden goals, deceptive alignment, sandbagging: the taxonomy splits these by means, so the means decides:
   - read from internals (probes, latent knowledge, or "interpretability" with no specific method) -> probing
   - circuits, patching or causal reverse-engineering named as the method -> circuits; SAEs or sparse features named -> sae
   - behavioural tests, audits or evals of the model -> scheming_evals
   - runtime monitors or protocols on deployed agents -> control (cot_monitor if the monitor reads the chain of thought)
   - no means stated -> scheming_evals, or probing if internals or interpretability are mentioned
   - behavioural and internal means both named -> the one the direction names first; the other as secondary.
4. Otherwise (no narrow problem, only a broad aim), label by the method or agenda the pick proposes. Mitigating a behaviour with a named method (e.g. SAE steering against sycophancy) is labelled by the method; the eval categories are for measuring or detecting a behaviour.
5. Secondary: the other side of the pick (the method when the problem won, the problem when the method won), only if it is named in the direction and maps to a different category; else null. Do not use secondary for the motivation.
6. Tie-breaks: the direction sentence beats the Why; the main object beats "such as" / "e.g." examples; between two of equal weight, the first named. Never choose a category because it is broader or more common.
EXAMPLES:
- "Interpretability probes to detect when a model's stated reasoning diverges from the computation driving its outputs" -> cot_monitor, secondary probing.
- "Find and causally test circuits that make a model behave differently when it detects an evaluation" -> sa_evals, secondary circuits.
- "Evals that detect whether models recognise evaluation contexts and alter behaviour to conceal unsafe objectives" -> sa_evals, secondary scheming_evals.
- "Detect deceptive alignment through mechanistic interpretability of latent goals" -> probing, secondary null.
- "Detect deceptive alignment through adversarial pressure testing and latent state analysis" -> scheming_evals, secondary probing.
- "Behavioural monitoring pipelines that detect scheming in LLM agent outputs on long-horizon tasks" -> control, secondary scheming_evals.
- "Use SAEs to identify and causally intervene on the features driving sycophancy" -> sae, secondary act_steer.
- "Oversight methods that let systems flag unreliable answers and defer under distribution shift" -> corrigibility, secondary null."""


def categories(path=HERE / "agendas.json", descriptions=None):
    d = json.loads(Path(path).read_text())
    lines = []
    for a in d["agendas"] + d["special"]:
        s = f"{a['id']}: {a['name']} [{a['group']}]"
        subs = [descriptions[n].split(". ")[0][:120] for n in a["shallow_review_leaves"] if descriptions and n in descriptions]
        if subs:
            s += " - " + "; ".join(subs)
        if a.get("label_rule"):
            s += f" RULE: {a['label_rule']}"
        lines.append(s)
    ids = {a["id"] for a in d["agendas"] + d["special"]}
    return "\n".join(lines), ids


def prompt(texts, descriptions=None):
    cats, _ = categories(descriptions=descriptions)
    items = "\n".join(f"[{j}] {t}" for j, t in enumerate(texts))
    return ("Classify each AI safety research pick into the taxonomy below. Judge by the core technical "
            "direction, not wording. Give a primary category id and, only if the pick clearly combines two "
            "categories, a secondary id (else null).\n\nCATEGORIES:\n" + cats + "\n\n" + RULES +
            "\n\nPICKS:\n" + items +
            '\n\nReply with only a JSON list, one object per pick in order, e.g. '
            '[{"primary": "id1", "secondary": null}, {"primary": "id2", "secondary": "id3"}].')


def pick_text(parsed):
    return f"{parsed.get('direction', '')} Why: {parsed.get('why_this', parsed.get('why', ''))}".strip()


def label_batch(texts, model, provider=None, descriptions=None):
    """[primary label or None] per text. Three attempts; a retry appends "\\n(attempt k)" to the prompt."""
    extra = {"provider": provider} if provider else {}
    for attempt in range(3):
        p = prompt(texts, descriptions) + (f"\n(attempt {attempt})" if attempt else "")
        r = llm.chat(model, [{"role": "user", "content": p}], temperature=0, **extra)
        try:
            labs = json.loads(re.search(r"\[.*\]", r["message"].get("content") or "", re.S).group(0))
            if len(labs) == len(texts):
                return [d.get("primary") if isinstance(d, dict) else d for d in labs]
        except (AttributeError, ValueError):
            pass
    return [None] * len(texts)


def live_label(parsed, descriptions=None):
    """The agenda-counts registry's label for one pick; a label outside the 45 agendas is shown as 'unclassified'."""
    if not (parsed or {}).get("direction"):
        return None
    return label_batch([pick_text(parsed)], LIVE_MODEL, LIVE_PIN, descriptions)[0]


def majority_of_three(texts, descriptions=None):
    """Batch labelling for the agenda figures: three shuffles (seeds 1, 2, 3) into batches of 5; majority label,
    else the first valid one."""
    _, ids = categories()
    reps = [[None] * len(texts) for _ in range(3)]
    for rep, seed in enumerate((1, 2, 3)):
        order = list(range(len(texts)))
        random.Random(seed).shuffle(order)
        for s in range(0, len(order), 5):
            idx = order[s:s + 5]
            for i, lab in zip(idx, label_batch([texts[i] for i in idx], BATCH_MODEL, BATCH_PIN, descriptions)):
                reps[rep][i] = lab if lab in ids else None
    out = []
    for i in range(len(texts)):
        valid = [reps[k][i] for k in range(3) if reps[k][i]]
        best = max(set(valid), key=valid.count) if valid else None
        out.append(best if best and valid.count(best) >= 2 else (valid[0] if valid else None))
    return out
