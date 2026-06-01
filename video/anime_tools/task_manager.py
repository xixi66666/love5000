from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


TaskStatus = str
TaskWorker = Callable[[Callable[[str], None]], Any]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class TaskBusyError(RuntimeError):
    pass


@dataclass
class TaskRecord:
    id: str
    type: str
    project_name: str
    status: TaskStatus
    logs: list[str] = field(default_factory=list)
    result: Any = None
    error: str = ""
    created_at: str = field(default_factory=_now_iso)
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "project_name": self.project_name,
            "status": self.status,
            "logs": list(self.logs),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class TaskManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._tasks: dict[str, TaskRecord] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._active_task_id: str | None = None

    def submit(self, task_type: str, project_name: str, worker: TaskWorker) -> TaskRecord:
        with self._lock:
            if self._active_task_id is not None:
                active = self._tasks[self._active_task_id]
                if active.status in {"queued", "running"}:
                    raise TaskBusyError("已有任务正在运行，请等待完成后再试")

            task = TaskRecord(
                id=f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
                type=task_type,
                project_name=project_name,
                status="queued",
            )
            self._tasks[task.id] = task
            self._active_task_id = task.id

            thread = threading.Thread(target=self._run, args=(task.id, worker), daemon=True)
            self._threads[task.id] = thread
            thread.start()
            return task

    def get(self, task_id: str) -> TaskRecord:
        with self._lock:
            if task_id not in self._tasks:
                raise KeyError(task_id)
            task = self._tasks[task_id]
            return TaskRecord(
                id=task.id,
                type=task.type,
                project_name=task.project_name,
                status=task.status,
                logs=list(task.logs),
                result=task.result,
                error=task.error,
                created_at=task.created_at,
                finished_at=task.finished_at,
            )

    def wait(self, task_id: str, timeout: float | None = None) -> None:
        thread = self._threads[task_id]
        thread.join(timeout)
        if thread.is_alive():
            raise TimeoutError(f"任务未在 {timeout} 秒内完成: {task_id}")

    def _run(self, task_id: str, worker: TaskWorker) -> None:
        def log(message: str) -> None:
            with self._lock:
                self._tasks[task_id].logs.append(message)

        with self._lock:
            self._tasks[task_id].status = "running"

        try:
            result = worker(log)
        except Exception as exc:
            with self._lock:
                task = self._tasks[task_id]
                task.status = "failed"
                task.error = str(exc)
                task.finished_at = _now_iso()
                self._active_task_id = None
            return

        with self._lock:
            task = self._tasks[task_id]
            task.status = "success"
            task.result = result
            task.finished_at = _now_iso()
            self._active_task_id = None
