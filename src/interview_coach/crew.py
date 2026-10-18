import os

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from interview_coach.knowledge import coach_knowledge
from interview_coach.guardrails import output_guards
from interview_coach.guardrails.tool_guards import mcp_for
from interview_coach.schemas import (
    AnswerEvaluation,
    CodeEvaluation,
    FinalReport,
    InterviewPlan,
    JobProfile,
    ResumeProfile,
)

MODEL = os.getenv("MODEL", "gpt-4o-mini")


@CrewBase
class PlanningCrew:
    """Runs once: job analysis, resume analysis, interview plan via MCP."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def job_analyst(self) -> Agent:
        return Agent(config=self.agents_config["job_analyst"], llm=MODEL)

    @agent
    def resume_analyst(self) -> Agent:
        return Agent(config=self.agents_config["resume_analyst"], llm=MODEL)

    @agent
    def interview_planner(self) -> Agent:
        return Agent(
            config=self.agents_config["interview_planner"],
            llm=MODEL,
            mcps=[mcp_for("interview_planner")],
        )

    @agent
    def interviewer(self) -> Agent:
        return Agent(config=self.agents_config["interviewer"], llm=MODEL)

    @agent
    def evaluation_coach(self) -> Agent:
        return Agent(config=self.agents_config["evaluation_coach"], llm=MODEL)

    @task
    def analyze_job(self) -> Task:
        return Task(config=self.tasks_config["analyze_job"], output_pydantic=JobProfile)

    @task
    def analyze_resume(self) -> Task:
        return Task(config=self.tasks_config["analyze_resume"], output_pydantic=ResumeProfile)

    @task
    def plan_interview(self) -> Task:
        return Task(
            config=self.tasks_config["plan_interview"],
            output_pydantic=InterviewPlan,
            guardrail=output_guards.valid_plan,
            guardrail_max_retries=2,
        )

    @task
    def generate_followup(self) -> Task:
        return Task(config=self.tasks_config["generate_followup"])

    @task
    def evaluate_answer(self) -> Task:
        return Task(config=self.tasks_config["evaluate_answer"])

    @task
    def write_final_report(self) -> Task:
        return Task(config=self.tasks_config["write_final_report"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.job_analyst(), self.resume_analyst(), self.interview_planner()],
            tasks=[self.analyze_job(), self.analyze_resume(), self.plan_interview()],
            process=Process.sequential,
        )


@CrewBase
class EvaluationCrew:
    """Runs per confirmed answer: rubric scoring and coaching via MCP."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def job_analyst(self) -> Agent:
        return Agent(config=self.agents_config["job_analyst"], llm=MODEL)

    @agent
    def resume_analyst(self) -> Agent:
        return Agent(config=self.agents_config["resume_analyst"], llm=MODEL)

    @agent
    def interview_planner(self) -> Agent:
        return Agent(config=self.agents_config["interview_planner"], llm=MODEL)

    @agent
    def interviewer(self) -> Agent:
        return Agent(config=self.agents_config["interviewer"], llm=MODEL)

    @agent
    def evaluation_coach(self) -> Agent:
        return Agent(
            config=self.agents_config["evaluation_coach"],
            llm=MODEL,
            mcps=[mcp_for("evaluation_coach")],
            knowledge_sources=coach_knowledge(),
        )

    @task
    def analyze_job(self) -> Task:
        return Task(config=self.tasks_config["analyze_job"])

    @task
    def analyze_resume(self) -> Task:
        return Task(config=self.tasks_config["analyze_resume"])

    @task
    def plan_interview(self) -> Task:
        return Task(config=self.tasks_config["plan_interview"])

    @task
    def generate_followup(self) -> Task:
        return Task(config=self.tasks_config["generate_followup"])

    @task
    def evaluate_answer(self) -> Task:
        return Task(
            config=self.tasks_config["evaluate_answer"],
            output_pydantic=AnswerEvaluation,
            guardrail=output_guards.valid_evaluation,
            guardrail_max_retries=2,
        )

    @task
    def write_final_report(self) -> Task:
        return Task(config=self.tasks_config["write_final_report"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.evaluation_coach()],
            tasks=[self.evaluate_answer()],
            process=Process.sequential,
        )


@CrewBase
class ReportCrew:
    """Runs once at the end: narrative for the final report. No MCP access needed."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def job_analyst(self) -> Agent:
        return Agent(config=self.agents_config["job_analyst"], llm=MODEL)

    @agent
    def resume_analyst(self) -> Agent:
        return Agent(config=self.agents_config["resume_analyst"], llm=MODEL)

    @agent
    def interview_planner(self) -> Agent:
        return Agent(config=self.agents_config["interview_planner"], llm=MODEL)

    @agent
    def interviewer(self) -> Agent:
        return Agent(config=self.agents_config["interviewer"], llm=MODEL)

    @agent
    def evaluation_coach(self) -> Agent:
        return Agent(config=self.agents_config["evaluation_coach"], llm=MODEL)

    @task
    def analyze_job(self) -> Task:
        return Task(config=self.tasks_config["analyze_job"])

    @task
    def analyze_resume(self) -> Task:
        return Task(config=self.tasks_config["analyze_resume"])

    @task
    def plan_interview(self) -> Task:
        return Task(config=self.tasks_config["plan_interview"])

    @task
    def generate_followup(self) -> Task:
        return Task(config=self.tasks_config["generate_followup"])

    @task
    def evaluate_answer(self) -> Task:
        return Task(config=self.tasks_config["evaluate_answer"])

    @task
    def write_final_report(self) -> Task:
        return Task(
            config=self.tasks_config["write_final_report"],
            output_pydantic=FinalReport,
            guardrail=output_guards.valid_report,
            guardrail_max_retries=2,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.evaluation_coach()],
            tasks=[self.write_final_report()],
            process=Process.sequential,
        )


@CrewBase
class CodeReviewCrew:
    """Reviews a coding solution after deterministic sandbox execution."""

    agents_config = "config/coding_agents.yaml"
    tasks_config = "config/coding_tasks.yaml"

    @agent
    def code_reviewer(self) -> Agent:
        return Agent(config=self.agents_config["code_reviewer"], llm=MODEL)

    @task
    def review_code(self) -> Task:
        return Task(
            config=self.tasks_config["review_code"],
            output_pydantic=CodeEvaluation,
            guardrail=output_guards.valid_code_evaluation,
            guardrail_max_retries=2,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.code_reviewer()],
            tasks=[self.review_code()],
            process=Process.sequential,
        )