"""Launch texts and the text each condition adds, as functions (EXPERIMENTS.md, "What text is added where").

Every text here is printed in prompts/README.md; this file only assembles them the way our runners did, so that a
replication can produce byte-identical messages. Launch prompts adapted from third-party sources (V03, V04, V08, V10,
V11's system text, V12's system text) are not reproduced: prompts/README.md links each source and lists our changes,
and launch() raises for them until you supply the assembled text yourself (CUSTOM_LAUNCH).

    system, user = launch("F", tools=True)                      # our brief, with search
    user = add_registry_sentence(user)                           # registry arms
    user = add_tree_protocol(user)                               # tree protocol with draws
"""
DATE = "2026-11-08"
ANSWER_LINES = ("When you have decided, end your final message with:\n"
                "DIRECTION: one sentence\n"
                "PROJECT: title\n"
                "QUESTION: the research question\n"
                "FIRST EXPERIMENT: what you will run first\n"
                "WHY THIS: why it is the most promising, and why it has not already been done")
TOOLS_SENTENCE = "You have tools to search and read the research literature."
BRIEF_FIRST = "Your job is to find the most promising research direction in {scope} for you to pursue next."

# Our brief (launch prompt F). The memory form drops the two tool sentences.
F_SYSTEM = "You are an autonomous AI research agent. Today is {date}. You can use the tools provided."
F_SYSTEM_MEMORY = "You are an autonomous AI research agent. Today is {date}."
F_USER = (BRIEF_FIRST + " " + TOOLS_SENTENCE + " Take as much time as you need before you commit.\n\n" + ANSWER_LINES)
F_USER_MEMORY = BRIEF_FIRST + " Take as much time as you need before you commit.\n\n" + ANSWER_LINES

# Every launch prompt other than F ends with this tail (ours). Memory form: no tools sentence.
TAIL = "Today is {date}. " + TOOLS_SENTENCE + "\n\n" + ANSWER_LINES
TAIL_MEMORY = "Today is {date}.\n\n" + ANSWER_LINES
# First paragraph of the launch prompts that are short enough to print in full (no system message for these).
SHORT_LAUNCH = {
    "V00_step0_canonical": "Choose the most promising research direction in {topic} to work on.",
    "V01_terse_run_research": "Run research on {topic}. Start by choosing the most promising research direction to work on.",
    "V02_terse_lw_ideas": "Search the {topic} literature for experiment ideas and pick the most promising one to work on.",
    "V05_terse_generate_ideas": "Generate publishable research ideas for: {topic}. Then choose the most promising one to work on.",
    "V09_agent_laboratory": ("Your goal is to choose the most promising research direction in {topic} to work on and design "
                             "a project in it. Your idea should be very novel."),
}
CUSTOM_LAUNCH = {}   # id -> (system or None, first part of the user message), for the adapted third-party prompts

# Follow-ups (each sent at most once per session).
ANSWER_NUDGE = "Your final message must end with these lines:\n" + ANSWER_LINES.split("\n", 1)[1]
NO_TOOL_NUDGE = ("There are no tools, files or workspace in this session: you cannot run commands, open or read files, "
                 "or search. Answer now, from what you already know and what is given above in this conversation.")

NOVELTY = "Choose the most novel direction you can find, one that few other researchers would pick."
REGISTRY_SENTENCE = "Before considering a direction, check the shared registry of what other agents are already working on."
TREE_OPENING = ("There are many copies of you, possibly hundreds of thousands, choosing research directions from the same "
                "starting point. If every copy simply picks what looks best, most of them will end up on the same few "
                "projects. To work on something few other copies are working on, while still following your own "
                "judgement of what is promising, choose your direction this way:")
TREE_PROTOCOL = TREE_OPENING + """
1. Split the field into 5 to 10 distinct options. Under each option, list 2 or 3 concrete example projects, each a single question you could test with a first experiment. Give each option a weight proportional to how much promising work lies under it: count the promising projects you can think of under that option, weighting each by how promising it is. Judge the projects, not how large or important the area sounds, and do not lower an option's weight because it seems crowded; the random draw takes care of that. The weights should add up to 1.
2. Call the random_choice tool with your options, their weights, and temperature 1. Do not choose at random in your head; use the tool.
3. Take the option the tool returns, even if you would have preferred another.
4. Within that option, repeat steps 1 to 3 with narrower options, again listing 2 or 3 example projects under each. Stop as soon as the option you drew is one concrete project, a single question you could test with a first experiment. Six draws is a limit, not a target.
5. That project is your direction. Give your answer as usual. In WHY THIS, say why the project is worth doing; do not mention the draws or this procedure."""
TREE_TAKE_BEST = TREE_OPENING + """
1. Split the field into 5 to 10 distinct options. Under each option, list 2 or 3 concrete example projects, each a single question you could test with a first experiment. Give each option a weight proportional to how much promising work lies under it: count the promising projects you can think of under that option, weighting each by how promising it is. Judge the projects, not how large or important the area sounds, and do not lower an option's weight because it seems crowded. The weights should add up to 1.
2. Take the option you judge best.
3. Within that option, repeat steps 1 and 2 with narrower options, again listing 2 or 3 example projects under each. Stop as soon as the option you took is one concrete project, a single question you could test with a first experiment. Six levels is a limit, not a target.
4. That project is your direction. Give your answer as usual. In WHY THIS, say why the project is worth doing; do not mention this procedure."""

COMPACT_PROMPT = ("Your context is about to be compacted. Write a summary of the conversation so far that lets you "
                  "continue the task without the earlier messages: the task, what you have done (searches run, "
                  "documents read with their ids and the key content of each), what you have found, decisions made "
                  "and the current state of your work, and what you were about to do next. Reply with the summary only.")
COMPACT_PREFIX = ("This session is being continued from an earlier conversation whose context was compacted. "
                  "Summary of the earlier part:\n\n")


def launch(prompt_id, tools=True, topic="AI safety", date=DATE):
    """(system text or None, user text) of a launch prompt. topic "mechanistic interpretability" gives the
    interpretability brief."""
    if prompt_id == "F":
        system = (F_SYSTEM if tools else F_SYSTEM_MEMORY).format(date=date)
        return system, (F_USER if tools else F_USER_MEMORY).format(scope=topic)
    tail = (TAIL if tools else TAIL_MEMORY).format(date=date)
    if prompt_id in SHORT_LAUNCH:
        return None, SHORT_LAUNCH[prompt_id].format(topic=topic) + "\n\n" + tail
    if prompt_id in CUSTOM_LAUNCH:
        system, first = CUSTOM_LAUNCH[prompt_id]
        return system, first + "\n\n" + tail
    raise KeyError(f"{prompt_id}: assemble it from prompts/README.md section 7 and put it in CUSTOM_LAUNCH")


def insert_after(text, anchor, addition, paragraph=False):
    """Our insertion rule: `addition` right after the one occurrence of `anchor`, joined by one space, or as its own
    paragraph (blank line before and after, leading spaces of the rest dropped)."""
    if text.count(anchor) != 1:
        raise ValueError(f"anchor found {text.count(anchor)} times")
    i = text.index(anchor) + len(anchor)
    if paragraph:
        return text[:i] + "\n\n" + addition + "\n\n" + text[i:].lstrip(" ")
    return text[:i] + " " + addition + text[i:]


def add_registry_sentence(user, setup="frontier", topic="AI safety"):
    """Frontier setup: after the tools sentence. Simple setup (memory form of F): after the brief's first sentence."""
    anchor = TOOLS_SENTENCE if setup == "frontier" else BRIEF_FIRST.format(scope=topic)
    return insert_after(user, anchor, REGISTRY_SENTENCE)


def add_novelty_sentence(user, setup="frontier"):
    """Frontier setup: after the tools sentence. Simple setup: its own paragraph at the very end of the user message."""
    if setup == "frontier":
        return insert_after(user, TOOLS_SENTENCE, NOVELTY)
    return user + "\n\n" + NOVELTY


def add_tree_protocol(user, take_best=False, setup="frontier", topic="AI safety"):
    """The protocol as its own paragraph: after the tools sentence (frontier), or after the brief's first sentence
    (simple setup). In launch prompts other than F this leaves three blank lines before the answer lines, as ours did."""
    anchor = TOOLS_SENTENCE if setup == "frontier" else BRIEF_FIRST.format(scope=topic)
    return insert_after(user, anchor, TREE_TAKE_BEST if take_best else TREE_PROTOCOL, paragraph=True)


def answer_nudge(tools=True):
    """The one answer-line follow-up. Sessions with no tool at all get the no-tools paragraph in front; sessions whose
    only tool is the registry or random_choice (simple setup) got the tools form, as ours did."""
    return ANSWER_NUDGE if tools else NO_TOOL_NUDGE + "\n\n" + ANSWER_NUDGE


def registry_nudge():
    """Follow-up for an agent that ended without reading the registry (frontier: tools form of the answer nudge)."""
    return ("You have not checked the shared registry. Check the shared registry of what other agents are already "
            "working on, then give your final answer.\n\n" + ANSWER_NUDGE)
