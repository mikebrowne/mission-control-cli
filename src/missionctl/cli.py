from __future__ import annotations

import typer

from missionctl.commands.agent import app as agent_app
from missionctl.commands.commentary import app as commentary_app
from missionctl.commands.doctor import app as doctor_app
from missionctl.commands.project import app as project_app
from missionctl.commands.settings import app as settings_app
from missionctl.commands.task import app as task_app
from missionctl.commands.task_run import app as task_run_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(doctor_app, name="doctor")
app.add_typer(agent_app, name="agent")
app.add_typer(task_app, name="task")
app.add_typer(task_run_app, name="task-run")
app.add_typer(project_app, name="project")
app.add_typer(commentary_app, name="commentary")
app.add_typer(settings_app, name="settings")


if __name__ == "__main__":
    app()
