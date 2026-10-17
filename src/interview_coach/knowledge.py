import os

from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

PRACTICES = """
Behavioral answers: use STAR. Situation and Task in 1 to 2 sentences, Action in 3 to 5 sentences
using I rather than we, Result with a number or a clear outcome. Aim for 60 to 120 seconds.
Technical answers: state the approach first, then design, then tradeoffs, then a concrete example.
Name tools and explain why they were chosen over alternatives.
Situational answers: clarify the situation, prioritize, act, then follow up. Mention risks and who you
would communicate with.
Common weak points: vague claims without evidence, no measurable result, listing tools without
decisions, no conclusion, long setup and a short action.
Filler words such as um and uh are reduced by pausing briefly between points.
Coaching must refer to what the candidate actually said and must not assume experience that was
not stated.
"""


def coach_knowledge() -> list:
    """Agent-level knowledge for the evaluation coach. Set USE_KNOWLEDGE=0 to disable."""
    if os.getenv("USE_KNOWLEDGE", "1") != "1":
        return []
    return [StringKnowledgeSource(content=PRACTICES)]