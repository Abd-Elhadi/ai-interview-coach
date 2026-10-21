import os

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from interview_coach.schemas import CodingProblemDraft

MODEL = os.getenv("MODEL", "gpt-4o-mini")


@CrewBase
class CodingProblemCrew:
    agents_config = "config/coding_problem_agents.yaml"
    tasks_config = "config/coding_problem_tasks.yaml"

    @agent
    def problem_writer(self) -> Agent:
        return Agent(config=self.agents_config["problem_writer"], llm=MODEL)

    @task
    def generate_problem(self) -> Task:
        return Task(config=self.tasks_config["generate_problem"], output_pydantic=CodingProblemDraft)

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.problem_writer()],
            tasks=[self.generate_problem()],
            process=Process.sequential,
        )
