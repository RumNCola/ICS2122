from __future__ import annotations

import math
import multiprocessing as mp
import os
import time
import traceback
from concurrent.futures import (
    Executor,
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .alns_adapter import ALNSScenarioSolver
from .config_dynamic import DynamicMSAConfig
from .entities import ScenarioPlan


@dataclass(slots=True)
class ScenarioSolveTask:
    """Datos autocontenidos para resolver un escenario MSA en un worker.

    La funcion ejecutada por ProcessPoolExecutor debe estar definida a nivel de
    modulo para que Windows pueda importarla con el metodo ``spawn``.
    """

    config_payload: dict[str, Any]
    scenario_df: pd.DataFrame
    known_df: pd.DataFrame
    now_sec: float
    physical_vehicle_ids: tuple[int, ...]
    scenario_id: int
    time_limit_sec: float


@dataclass(slots=True)
class ScenarioSolveResult:
    scenario_id: int
    plan: ScenarioPlan | None
    elapsed_sec: float
    error: str | None = None
    worker_pid: int | None = None


def _solve_task_impl(task: ScenarioSolveTask) -> ScenarioPlan:
    """Resuelve y proyecta un escenario. Se ejecuta dentro de cada proceso."""

    cfg = DynamicMSAConfig(**task.config_payload)
    solver = ALNSScenarioSolver(cfg)
    full_plan = solver.solve(
        task.scenario_df,
        now_sec=float(task.now_sec),
        physical_vehicle_ids=list(task.physical_vehicle_ids),
        scenario_id=int(task.scenario_id),
        time_limit_override_sec=float(task.time_limit_sec),
    )
    projected = solver.project_plan_to_known(
        full_plan,
        known_df=task.known_df,
        now_sec=float(task.now_sec),
        physical_vehicle_ids=list(task.physical_vehicle_ids),
    )

    # El objeto crudo del ALNS no se necesita para el consenso y puede ser
    # grande. Eliminarlo reduce el trafico de serializacion entre procesos.
    projected.raw_solution = None
    return projected


def solve_scenario_task(task: ScenarioSolveTask) -> ScenarioSolveResult:
    """Wrapper seguro y picklable para ProcessPoolExecutor."""

    started = time.perf_counter()
    try:
        plan = _solve_task_impl(task)
        return ScenarioSolveResult(
            scenario_id=int(task.scenario_id),
            plan=plan,
            elapsed_sec=time.perf_counter() - started,
            error=None,
            worker_pid=os.getpid(),
        )
    except Exception:
        return ScenarioSolveResult(
            scenario_id=int(task.scenario_id),
            plan=None,
            elapsed_sec=time.perf_counter() - started,
            error=traceback.format_exc(),
            worker_pid=os.getpid(),
        )


class ScenarioBatchExecutor:
    """Ejecutor persistente para escenarios MSA.

    El paralelismo se aplica en el nivel correcto para este problema: cada
    escenario MSA es independiente y contiene una corrida ALNS completa. Esto
    evita estados compartidos y mantiene exactamente la misma funcion de
    consenso posterior.
    """

    def __init__(self, config: DynamicMSAConfig):
        self.config = config
        self._executor: Executor | None = None
        self._resolved_workers: int = 1
        self.worker_errors: list[str] = []
        self.tasks_completed: int = 0
        self.tasks_fallback: int = 0

    @property
    def backend(self) -> str:
        return self.config.parallel_backend

    @property
    def resolved_workers(self) -> int:
        return self._resolved_workers

    def effective_workers(self, n_tasks: int | None = None) -> int:
        if self.config.parallel_backend == "sequential":
            return 1

        detected = max(1, int(os.cpu_count() or 1))
        if self.config.parallel_max_workers is None:
            workers = max(1, detected - int(self.config.parallel_cpu_reserve))
        else:
            workers = max(1, int(self.config.parallel_max_workers))

        if n_tasks is not None:
            workers = min(workers, max(1, int(n_tasks)))
        return max(1, workers)

    def per_scenario_time_limit(self, n_tasks: int) -> float:
        """Calcula el limite por escenario respetando un presupuesto wall-clock.

        Con W workers y N escenarios existen ceil(N/W) olas. Si se exige un
        presupuesto total B para el evento MSA, cada escenario puede usar a lo
        mas B/ceil(N/W), acotado por scenario_time_limit_sec.
        """

        base = float(self.config.scenario_time_limit_sec)
        if not self.config.respect_msa_event_budget:
            return base

        workers = self.effective_workers(n_tasks)
        waves = max(1, math.ceil(max(1, n_tasks) / workers))
        budget_limit = float(self.config.msa_event_budget_sec) / waves
        return max(0.05, min(base, budget_limit))

    def _limit_native_threads(self) -> None:
        if not self.config.parallel_limit_native_threads:
            return
        # Evita que cada proceso lance a su vez muchos threads internos de
        # BLAS/NumPy y sobre-sature el PC. Los hijos heredan estas variables.
        for key in (
            "OMP_NUM_THREADS",
            "MKL_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
        ):
            os.environ[key] = "1"

    def start(self, n_tasks_hint: int | None = None) -> None:
        if self._executor is not None or self.config.parallel_backend == "sequential":
            self._resolved_workers = self.effective_workers(n_tasks_hint)
            return

        self._limit_native_threads()
        self._resolved_workers = self.effective_workers(n_tasks_hint)

        if self.config.parallel_backend == "thread":
            self._executor = ThreadPoolExecutor(
                max_workers=self._resolved_workers,
                thread_name_prefix="msa-alns",
            )
            return

        # Windows requiere spawn. Tambien funciona en Linux y es mas seguro que
        # fork cuando ya se importaron NumPy/Pandas.
        context = mp.get_context(self.config.parallel_start_method)
        self._executor = ProcessPoolExecutor(
            max_workers=self._resolved_workers,
            mp_context=context,
        )

    def close(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=False)
            self._executor = None

    def _run_sequential(self, tasks: list[ScenarioSolveTask]) -> list[ScenarioSolveResult]:
        return [solve_scenario_task(task) for task in tasks]

    def solve(self, tasks: list[ScenarioSolveTask]) -> list[ScenarioSolveResult]:
        if not tasks:
            return []

        if self.config.parallel_backend == "sequential":
            results = self._run_sequential(tasks)
            self.tasks_completed += len(results)
            return sorted(results, key=lambda x: x.scenario_id)

        self.start(len(tasks))
        assert self._executor is not None

        futures: dict[Future[ScenarioSolveResult], ScenarioSolveTask] = {
            self._executor.submit(solve_scenario_task, task): task for task in tasks
        }
        results: list[ScenarioSolveResult] = []

        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
            except Exception:
                result = ScenarioSolveResult(
                    scenario_id=task.scenario_id,
                    plan=None,
                    elapsed_sec=0.0,
                    error=traceback.format_exc(),
                    worker_pid=None,
                )

            if result.error is not None:
                self.worker_errors.append(
                    f"Escenario {task.scenario_id}:\n{result.error}"
                )
                if self.config.parallel_fallback_to_sequential:
                    fallback_started = time.perf_counter()
                    try:
                        plan = _solve_task_impl(task)
                        result = ScenarioSolveResult(
                            scenario_id=task.scenario_id,
                            plan=plan,
                            elapsed_sec=time.perf_counter() - fallback_started,
                            error=None,
                            worker_pid=os.getpid(),
                        )
                        self.tasks_fallback += 1
                    except Exception:
                        self.worker_errors.append(
                            f"Fallback escenario {task.scenario_id}:\n{traceback.format_exc()}"
                        )

            if self.config.parallel_log_progress:
                status = "OK" if result.plan is not None and result.error is None else "ERROR"
                print(
                    f"[MSA-ALNS] escenario={result.scenario_id} "
                    f"status={status} worker={result.worker_pid} "
                    f"elapsed={result.elapsed_sec:.2f}s"
                )
            results.append(result)

        self.tasks_completed += len(results)
        return sorted(results, key=lambda x: x.scenario_id)


def build_scenario_tasks(
    *,
    config: DynamicMSAConfig,
    known_df: pd.DataFrame,
    future_scenarios: list[pd.DataFrame],
    now_sec: float,
    physical_vehicle_ids: list[int],
    per_scenario_time_limit_sec: float,
) -> list[ScenarioSolveTask]:
    """Construye tareas compactas para enviar al pool."""

    payload = asdict(config)
    tasks: list[ScenarioSolveTask] = []
    for sid, future in enumerate(future_scenarios):
        scenario_df = pd.concat([known_df, future], ignore_index=True)
        if scenario_df.empty:
            continue
        tasks.append(
            ScenarioSolveTask(
                config_payload=payload,
                scenario_df=scenario_df,
                known_df=known_df,
                now_sec=float(now_sec),
                physical_vehicle_ids=tuple(int(v) for v in physical_vehicle_ids),
                scenario_id=int(sid),
                time_limit_sec=float(per_scenario_time_limit_sec),
            )
        )
    return tasks
