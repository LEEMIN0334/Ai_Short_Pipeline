from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    agent_id: str
    display_name: str
    kind: str = "worker"
    capabilities: list[str] = Field(default_factory=list)
    description: str


AGENT_DEFINITIONS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        agent_id="pm_supervisor",
        display_name="PM Supervisor",
        kind="supervisor",
        capabilities=[
            "natural_language_routing",
            "pipeline_planning",
            "mvp_preview",
        ],
        description="Routes user intent and coordinates the shorts production pipeline.",
    ),
    AgentDefinition(
        agent_id="trend_scout",
        display_name="Trend Scout",
        capabilities=[
            "topic_discovery",
            "candidate_scoring",
            "source_deduplication",
        ],
        description="Finds and ranks trend candidates from available sources.",
    ),
    AgentDefinition(
        agent_id="research_agent",
        display_name="Research Agent",
        capabilities=[
            "web_research",
            "source_comparison",
            "evidence_handoff",
        ],
        description="Searches the public web and turns evidence into a PM-ready research brief.",
    ),
    AgentDefinition(
        agent_id="script_writer",
        display_name="Script Writer",
        capabilities=[
            "script_draft",
            "scene_breakdown",
            "subtitle_split",
        ],
        description="Drafts a shorts script and splits it into timed production segments.",
    ),
    AgentDefinition(
        agent_id="developer_agent",
        display_name="Developer Agent",
        capabilities=[
            "research_to_implementation",
            "scoped_code_changes",
            "approved_codex_execution",
            "verification_planning",
            "self_review_gate",
        ],
        description=(
            "Implements approved software changes after Research Agent and PM "
            "Supervisor produce a direction and plan, then reviews its own output "
            "before handoff."
        ),
    ),
    AgentDefinition(
        agent_id="grok_planner",
        display_name="Grok Clip Planner",
        capabilities=[
            "loop_clip_prompts",
            "first_last_frame_matching",
            "manual_generation_tracking",
        ],
        description="Prepares 10-15 second loop clip prompts for manual Grok generation.",
    ),
    AgentDefinition(
        agent_id="composer",
        display_name="Composer",
        capabilities=[
            "subtitle_plan",
            "ffmpeg_plan",
            "vertical_assembly",
        ],
        description="Builds a vertical composition plan for approved clip assets.",
    ),
    AgentDefinition(
        agent_id="qc_agent",
        display_name="QC Agent",
        capabilities=[
            "final_qc",
            "retry_decision",
            "approval_gate",
        ],
        description="Checks duration, subtitles, voiceover, and final approval readiness.",
    ),
)


def get_agent_definition(agent_id: str) -> AgentDefinition | None:
    return next(
        (definition for definition in AGENT_DEFINITIONS if definition.agent_id == agent_id),
        None,
    )


def render_agent_catalog() -> str:
    lines = ["Agents ready for always-on runtime:"]
    for definition in AGENT_DEFINITIONS:
        capabilities = ", ".join(definition.capabilities)
        lines.append(f"- {definition.agent_id}: {definition.display_name} ({capabilities})")
    lines.extend(
        [
            "",
            "Commands:",
            "- /research <topic> queues pure web research with source links",
            "- /trend <topic> queues platform trend scouting",
            "- /script <topic> queues Script Writer preview",
            "- /dev <feature> queues Research -> PM -> Developer implementation plan",
            "- /dev 실행 승인: <feature> lets Developer Agent execute approved code changes",
            "- /grok <topic> queues Grok loop clip planning",
            "- /mvp <topic> queues full local MVP preview",
            "- /tasks shows recent work",
            "- /task <task_id> shows one task result",
        ]
    )
    return "\n".join(lines)
