import os

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from interview_coach.guardrails import quiz_guards
from interview_coach.schemas import MCQSet

MODEL = os.getenv("MODEL", "gpt-4o-mini")


@CrewBase
class MCQCrew:
    agents_config = "config/quiz_agents.yaml"
    tasks_config = "config/quiz_tasks.yaml"

    @agent
    def quiz_writer(self) -> Agent:
        return Agent(config=self.agents_config["quiz_writer"], llm=MODEL)

    @task
    def generate_mcqs(self) -> Task:
        return Task(
            config=self.tasks_config["generate_mcqs"],
            output_pydantic=MCQSet,
            guardrail=quiz_guards.valid_mcqs,
            guardrail_max_retries=2,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential)