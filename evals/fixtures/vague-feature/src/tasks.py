"""Aufgaben-Modell. Ein Fälligkeitsdatum ist optional; es gibt aktuell keine
geplanten Erinnerungen dafür."""

from dataclasses import dataclass
from datetime import date


@dataclass
class Task:
    title: str
    status: str  # "open" | "done"
    due_date: date | None = None


def mark_done(task: Task, event_bus) -> None:
    task.status = "done"
    event_bus.publish("task.done", {"title": task.title})
