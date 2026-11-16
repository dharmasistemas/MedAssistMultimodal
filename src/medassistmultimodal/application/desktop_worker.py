"""Single-operation worker. No Tkinter references or shared SQLite connections."""
from dataclasses import dataclass
from queue import Queue, Empty
from threading import Thread
from uuid import uuid4

from .desktop_history import HistoryError


@dataclass(frozen=True, slots=True)
class WorkerMessage:
    job_id: str
    kind: str
    value: object


class DesktopWorker:
    def __init__(self):
        self.messages = Queue()
        self.active = None
        self.thread = None

    @property
    def busy(self):
        return self.active is not None

    def start(self, operation):
        if self.busy:
            raise ValueError('An operation is already active')
        job = str(uuid4()); self.active = job
        def run():
            def progress(stage):
                self.messages.put(WorkerMessage(job, 'progress', stage))
            try:
                result = operation(progress)
            except Exception as exc:
                code = exc.code if isinstance(exc, HistoryError) else 'operation_failed'
                self.messages.put(WorkerMessage(job, 'error', code))
            else:
                self.messages.put(WorkerMessage(job, 'done', result))
        self.thread = Thread(target=run, name='MedAssistMultimodal-worker', daemon=False)
        self.thread.start()
        return job

    def drain(self):
        result = []
        while True:
            try: message = self.messages.get_nowait()
            except Empty: break
            if message.job_id != self.active:
                continue
            result.append(message)
            if message.kind in ('done', 'error'):
                self.active = None
        return result
