"""实验控制器：编排「生成 -> 评价 -> 修改/回退」循环。

职责：
- 每次运行前重置状态，防止上一轮工作状态泄漏；
- 循环受「迭代上限、停止条件、回退规则」约束；
- 瞬时后端错误按配置安全重试；重试耗尽则显式标记失败，绝不静默跳过；
- 每轮保存断点（best/current 图像 + 元数据），支持断点恢复；
- 成功与失败均写入 manifest；失败运行不计为成功。
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PIL import Image

from . import audit
from .comparison import sha256_file
from .config import config_snapshot, resolve_seed
from .errors import ReproError, RunFailedError
from .generators.base import GeneratedImage
from .manifest import (
    collect_comfyui_version,
    collect_model_hashes,
    collect_software_versions,
    read_json,
    utcnow_iso,
    write_json,
    write_run_manifest,
)
from .seeds import (
    generate_seed_book,
    load_seed_book,
    load_seed_sequence,
    resolve_config_path,
    save_seed_book,
)
from .state import RoundRecord, RunState, StateManager

FINAL_IMAGE_NAME = "final.png"
BEST_IMAGE_NAME = "best.png"
CURRENT_IMAGE_NAME = "current.png"
CHECKPOINT_NAME = "checkpoint.json"


@dataclass
class EvalFeedback:
    """传递给修改步骤的上轮评价反馈。"""

    score: Optional[float] = None
    note: str = ""


class ExperimentResult:
    def __init__(self, experiment_dir: Path, manifests: List[Dict[str, Any]]):
        self.experiment_dir = Path(experiment_dir)
        self.manifests = manifests

    @property
    def success_count(self) -> int:
        return sum(1 for m in self.manifests if m.get("status") == "success")

    @property
    def failed_count(self) -> int:
        return sum(1 for m in self.manifests if m.get("status") == "failed")


class ExperimentController:
    def __init__(
        self,
        config: Dict[str, Any],
        experiment_dir: Path | str,
        generator_factory: Optional[Callable[[], Any]] = None,
        evaluator_factory: Optional[Callable[[], Any]] = None,
    ):
        self.config = config
        self.experiment_dir = Path(experiment_dir)
        self.generator_factory = generator_factory
        self.evaluator_factory = evaluator_factory
        self.state_manager = StateManager(self.experiment_dir, config)
        logs_dir = self.experiment_dir / config["paths"]["logs_dir"]
        self.logger = audit.setup_experiment_logger(logs_dir, console=True)
        self._last_generator: Any = None
        self._last_evaluator: Any = None
        self.run_logger: Any = None
        self.seed_book = self._load_seed_book()

    # ------------------------------------------------------------------ #
    # 工厂
    # ------------------------------------------------------------------ #
    def _build_generator(self) -> Any:
        if self.generator_factory is not None:
            return self.generator_factory()
        from .build import build_generator

        return build_generator(self.config)

    def _build_evaluator(self) -> Any:
        if self.evaluator_factory is not None:
            return self.evaluator_factory()
        from .build import build_evaluator

        return build_evaluator(self.config)

    # ------------------------------------------------------------------ #
    # 配对与种子
    # ------------------------------------------------------------------ #
    def _num_runs(self) -> int:
        """总创作次数：num_pairs 优先（= num_pairs * replicates_per_pair）。"""
        n_pairs = self.config.get("num_pairs")
        if n_pairs is not None and int(n_pairs) >= 1:
            return int(n_pairs) * int(self.config["replicates_per_pair"])
        return int(self.config["num_runs"])

    @staticmethod
    def _pair_replicate(run_index: int, replicates_per_pair: int):
        """run_index(1 基) -> (pair_id, replicate_id)（replicate_id 从 1 起）。"""
        pair_id = (run_index - 1) // replicates_per_pair + 1
        replicate_id = (run_index - 1) % replicates_per_pair + 1
        return pair_id, replicate_id

    def _load_seed_book(self):
        """加载种子簿；缺失时按 master_seed 确定性生成并保存（可审计，绝不事后挑选）。"""
        g = self.config["generator"]
        if g.get("type") != "comfyui":
            return None
        book_file = g.get("seed_book_file")
        if book_file:
            p = resolve_config_path(book_file)
            if p is not None and Path(p).exists():
                book = load_seed_book(p)
                self.logger.info("已加载种子簿: %s（%d 条）", p, len(book))
                return book
            n = self._num_runs()
            length = int(self.config["max_iterations_per_run"])
            master = int(self.config["random"]["master_seed"])
            book = generate_seed_book(n, length, master)
            if p is not None:
                save_seed_book(p, book)
                self.logger.info(
                    "种子簿缺失，已按 master_seed=%d 确定性生成并保存: %s", master, p
                )
            else:
                self.logger.info("种子簿缺失，已按 master_seed=%d 确定性生成（未落盘）", master)
            return book
        legacy = g.get("seed_sequence_file")
        if legacy:
            p = resolve_config_path(legacy)
            if p is not None:
                return [load_seed_sequence(p)]
        return None

    def _seed_sequence_for(self, run_index: int):
        """返回本次创作应使用的固定种子序列（种子簿第 run_index-1 条）。"""
        if self.seed_book:
            return list(self.seed_book[(run_index - 1) % len(self.seed_book)])
        return None

    # ------------------------------------------------------------------ #
    # 公开入口
    # ------------------------------------------------------------------ #
    def run_all(self, resume: bool = False) -> ExperimentResult:
        num_runs = self._num_runs()
        reps = int(self.config["replicates_per_pair"])
        abort = self.config["error_handling"]["abort_on_failure"]
        manifests: List[Dict[str, Any]] = []
        for i in range(1, num_runs + 1):
            pair_id, replicate_id = self._pair_replicate(i, reps)
            self.logger.info(
                "开始运行 %d/%d (pair=%d replicate=%s)", i, num_runs, pair_id, replicate_id
            )
            manifest = self.run_single(i, resume=resume, pair_id=pair_id, replicate_id=replicate_id)
            manifests.append(manifest)
            if manifest["status"] == "failed":
                msg = (manifest.get("error") or {}).get("message", "")
                self.logger.error("运行 %d 失败: %s", i, msg)
                if abort:
                    self.logger.error("abort_on_failure=True，停止后续运行")
                    for j in range(i + 1, num_runs + 1):
                        pj, rj = self._pair_replicate(j, reps)
                        manifests.append(self._skipped_manifest(j, pj, rj))
                    break
        return ExperimentResult(self.experiment_dir, manifests)

    def run_single(
        self,
        run_index: int,
        resume: bool = False,
        pair_id: Optional[int] = None,
        replicate_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if pair_id is None or replicate_id is None:
            pair_id, replicate_id = self._pair_replicate(
                run_index, int(self.config["replicates_per_pair"])
            )
        run_dir = self.state_manager.run_dir(run_index)
        started_at = utcnow_iso()
        seed = resolve_seed(self.config, run_index)
        seed_seq = self._seed_sequence_for(run_index)

        # 幂等恢复：已成功完成的运行直接返回
        if resume:
            manifest_path = run_dir / "manifest.json"
            if manifest_path.exists():
                done = read_json(manifest_path)
                if done.get("status") == "success":
                    self.logger.info("运行 %d 已成功完成，跳过（幂等恢复）", run_index)
                    return done
            checkpoint_path = run_dir / CHECKPOINT_NAME
            if not checkpoint_path.exists() and run_dir.exists():
                self.state_manager.archive_existing(run_index)
            checkpoint = read_json(checkpoint_path) if checkpoint_path.exists() else None
        else:
            checkpoint = None

        # 断点恢复时沿用断点记录的种子（保证 random 策略也能可复现地恢复）
        if checkpoint is not None and "seed" in checkpoint:
            seed = int(checkpoint["seed"])

        generator = self._build_generator()
        # 关键：按 run_index 注入本次创作专属的固定种子序列
        if seed_seq is not None and hasattr(generator, "seed_sequence"):
            generator.seed_sequence = list(seed_seq)
        evaluator = self._build_evaluator()
        self._last_generator = generator
        self._last_evaluator = evaluator

        state: Optional[RunState] = None
        try:
            state = self._prepare_state(
                run_index, seed, checkpoint, pair_id, replicate_id, seed_seq
            )
            self.run_logger = audit.setup_run_logger(run_dir)
            self.run_logger.info(
                "run_id=%s seed=%s pair=%s replicate=%s resume=%s",
                state.run_id,
                seed,
                pair_id,
                replicate_id,
                checkpoint is not None,
            )
            generator.reset()
            self._run_loop(state, generator, evaluator)
            manifest = self._success_manifest(state, started_at)
        except RunFailedError as exc:
            rounds = state.rounds_actual if state is not None else None
            manifest = self._failed_manifest(
                run_index, seed, exc, started_at, rounds, pair_id, replicate_id, seed_seq
            )
        except Exception as exc:  # 兜底：任何未预期异常都显式标记失败
            self.logger.exception("运行 %d 发生未预期异常", run_index)
            wrapped = RunFailedError(f"未预期异常: {exc}", type(exc).__name__)
            rounds = state.rounds_actual if state is not None else None
            manifest = self._failed_manifest(
                run_index, seed, wrapped, started_at, rounds, pair_id, replicate_id, seed_seq
            )

        write_run_manifest(run_dir, manifest)
        self.logger.info("运行 %d 结束: %s", run_index, manifest["status"])
        return manifest

    # ------------------------------------------------------------------ #
    # 内部：状态与循环
    # ------------------------------------------------------------------ #
    def _prepare_state(
        self,
        run_index: int,
        seed: int,
        checkpoint: Optional[Dict[str, Any]],
        pair_id: int,
        replicate_id: int,
        seed_seq: Optional[List[int]],
    ) -> RunState:
        if checkpoint is not None:
            state = self.state_manager.load_for_resume(
                run_index, seed, checkpoint, pair_id, replicate_id
            )
            run_dir = self.state_manager.run_dir(run_index)
            state.best_image = self._load_image(run_dir / BEST_IMAGE_NAME)
            state.current_image = self._load_image(run_dir / CURRENT_IMAGE_NAME)
        else:
            state = self.state_manager.fresh(run_index, seed, pair_id, replicate_id)
        state.seed_sequence = seed_seq
        return state

    @staticmethod
    def _load_image(path: Path) -> GeneratedImage:
        return GeneratedImage(image=Image.open(path).convert("RGB"), format="PNG")

    def _run_loop(self, state: RunState, generator: Any, evaluator: Any) -> None:
        cfg = self.config
        max_iters = cfg["max_iterations_per_run"]
        threshold = cfg["stop_conditions"]["quality_threshold"]
        no_improve_limit = cfg["stop_conditions"]["no_improvement_rounds"]
        rb = cfg["rollback"]
        tol = rb["tolerance"]
        prompt = state.prompt

        # 第 1 轮：初始生成（断点恢复时跳过）
        if state.best_image is None:
            state.rounds_actual = 1
            current = self._retry(
                lambda: generator.generate(prompt, state.seed, state), "generate"
            )
            score = self._evaluate(evaluator, current, prompt, state)
            round_seed = self._round_seed(current)
            state.current_image = current
            state.best_image = current
            state.best_score = score
            state.current_score = score
            state.add_record(
                RoundRecord(
                    1,
                    "generate",
                    score,
                    note="初始生成",
                    seed=round_seed,
                    rollback_count=state.rollback_count,
                    no_improvement_count=state.no_improvement_count,
                )
            )
            self._audit_round(state, 1, "generate", score, round_seed)
            self._checkpoint(state)

        while True:
            # 停止条件（每轮之后检查）
            if state.rounds_actual >= max_iters:
                state.stop_reason = "max_iterations"
                break
            if threshold is not None and state.best_score is not None and state.best_score >= threshold:
                state.stop_reason = "quality_threshold"
                break
            if no_improve_limit is not None and state.no_improvement_count >= no_improve_limit:
                state.stop_reason = "no_improvement"
                break
            if rb["enabled"] and state.rollback_count >= rb["max_consecutive_rollbacks"]:
                state.stop_reason = "rollback_limit"
                break

            round_index = state.rounds_actual + 1
            feedback = EvalFeedback(score=state.current_score)
            candidate = self._retry(
                lambda: generator.modify(
                    state.current_image, feedback, state.seed, round_index, state
                ),
                "modify",
            )
            cand_score = self._evaluate(evaluator, candidate, prompt, state)
            round_seed = self._round_seed(candidate)

            improved = (cand_score - state.best_score) > tol
            if improved:
                state.best_image = candidate
                state.best_score = cand_score
                state.current_image = candidate
                state.current_score = cand_score
                state.rollback_count = 0
                state.no_improvement_count = 0
                state.add_record(
                    RoundRecord(
                        round_index,
                        "accept",
                        cand_score,
                        note="质量改进，接受",
                        seed=round_seed,
                        rollback_count=state.rollback_count,
                        no_improvement_count=state.no_improvement_count,
                    )
                )
                self._audit_round(state, round_index, "accept", cand_score, round_seed)
            else:
                state.no_improvement_count += 1
                if rb["enabled"]:
                    # 回退：丢弃候选，保持 current == best
                    state.rollback_count += 1
                    state.add_record(
                        RoundRecord(
                            round_index,
                            "rollback",
                            cand_score,
                            note="质量未提升，回退",
                            seed=round_seed,
                            rollback_count=state.rollback_count,
                            no_improvement_count=state.no_improvement_count,
                        )
                    )
                    self._audit_round(state, round_index, "rollback", cand_score, round_seed)
                else:
                    state.current_image = candidate
                    state.current_score = cand_score
                    state.add_record(
                        RoundRecord(
                            round_index,
                            "accept_regression",
                            cand_score,
                            note="回退关闭，保留候选",
                            seed=round_seed,
                            rollback_count=state.rollback_count,
                            no_improvement_count=state.no_improvement_count,
                        )
                    )
                    self._audit_round(state, round_index, "accept_regression", cand_score, round_seed)

            state.rounds_actual = round_index
            self._checkpoint(state)

    def _evaluate(self, evaluator: Any, image: GeneratedImage, prompt: str, state: RunState) -> float:
        return self._retry(lambda: evaluator.evaluate(image, prompt, state), "evaluate").score

    def _retry(self, fn: Callable[[], Any], what: str) -> Any:
        err = self.config["error_handling"]
        max_retries = int(err["max_retries"])
        backoff = float(err["retry_backoff_seconds"])
        last_exc: Optional[BaseException] = None
        for attempt in range(max_retries + 1):
            try:
                return fn()
            except Exception as exc:  # 任何后端异常都重试，耗尽后显式失败
                last_exc = exc
                if attempt < max_retries:
                    self.logger.warning(
                        "%s 第 %d 次尝试失败，%.3fs 后重试: %s", what, attempt + 1, backoff, exc
                    )
                    time.sleep(backoff)
        raise RunFailedError(
            f"{what} 在 {max_retries} 次重试后仍失败: {last_exc}",
            type(last_exc).__name__ if last_exc else "UnknownError",
        )

    def _checkpoint(self, state: RunState) -> None:
        if not self.config["error_handling"]["checkpoint_enabled"]:
            return
        run_dir = state.work_dir
        if state.best_image is not None:
            state.best_image.save(run_dir / BEST_IMAGE_NAME)
        if state.current_image is not None:
            state.current_image.save(run_dir / CURRENT_IMAGE_NAME)
        write_json(
            run_dir / CHECKPOINT_NAME,
            {
                "round": state.rounds_actual,
                "seed": state.seed,
                "best_score": state.best_score,
                "rollback_count": state.rollback_count,
                "no_improvement_count": state.no_improvement_count,
                "history_len": len(state.history),
                "saved_at": utcnow_iso(),
            },
        )

    @staticmethod
    def _round_seed(image: Any) -> Optional[int]:
        """从生成图像元数据中取出本轮实际使用的种子。"""
        md = getattr(image, "metadata", None) or {}
        return md.get("seed")

    def _audit_round(
        self,
        state: RunState,
        round_index: int,
        action: str,
        score: Optional[float],
        seed: Optional[int] = None,
    ) -> None:
        msg = (
            "run=%s round=%d action=%s seed=%s score=%s best=%.4f rollback=%d no_improve=%d",
            state.run_id,
            round_index,
            action,
            None if seed is None else str(seed),
            None if score is None else f"{score:.6f}",
            state.best_score if state.best_score is not None else -1.0,
            state.rollback_count,
            state.no_improvement_count,
        )
        self.logger.info(*msg)
        if self.run_logger is not None:
            self.run_logger.info(*msg)

    # ------------------------------------------------------------------ #
    # manifest 组装
    # ------------------------------------------------------------------ #
    def _generator_info(self) -> Dict[str, Any]:
        return {
            "name": getattr(self._last_generator, "name", "unknown"),
            "is_mock": bool(getattr(self._last_generator, "IS_MOCK", False)),
            "evaluator": getattr(self._last_evaluator, "name", "unknown"),
            "evaluator_is_mock": bool(getattr(self._last_evaluator, "IS_MOCK", False)),
        }

    def _model_hashes(self) -> Dict[str, Any]:
        """记录真实模型文件哈希与 ComfyUI git commit；失败时把错误写入 manifest。"""
        try:
            hashes = collect_model_hashes(self.config)
        except Exception as exc:  # pragma: no cover - 依赖真实文件
            hashes = {"error": f"{type(exc).__name__}: {exc}"}
        commit = collect_comfyui_version(self.config)
        if commit:
            hashes["comfyui_git_commit"] = commit
        return hashes

    def _success_manifest(self, state: RunState, started_at: str) -> Dict[str, Any]:
        final_path = state.work_dir / FINAL_IMAGE_NAME
        state.best_image.save(final_path)
        sha = sha256_file(final_path)
        return {
            "run_id": state.run_id,
            "run_index": state.run_index,
            "pair_id": state.pair_id,
            "replicate_id": state.replicate_id,
            "status": "success",
            "seed": state.seed,
            "seed_strategy": self.config["random"]["strategy"],
            "seed_sequence": state.seed_sequence,
            "seed_sequence_index": state.run_index - 1,
            "rounds_actual": state.rounds_actual,
            "stop_reason": state.stop_reason,
            "final_output_path": str(final_path),
            "final_sha256": sha,
            "rollback_count": state.rollback_count,
            "best_score": state.best_score,
            "history": [asdict(r) for r in state.history],
            "config_snapshot": config_snapshot(self.config),
            "software_versions": collect_software_versions(),
            "model_hashes": self._model_hashes(),
            "components": self._generator_info(),
            "started_at": started_at,
            "finished_at": utcnow_iso(),
            "error": None,
        }

    def _failed_manifest(
        self,
        run_index: int,
        seed: int,
        exc: RunFailedError,
        started_at: str,
        rounds: Optional[int],
        pair_id: int,
        replicate_id: int,
        seed_seq: Optional[List[int]],
    ) -> Dict[str, Any]:
        return {
            "run_id": f"run_{run_index:03d}",
            "run_index": run_index,
            "pair_id": pair_id,
            "replicate_id": replicate_id,
            "status": "failed",
            "seed": seed,
            "seed_strategy": self.config["random"]["strategy"],
            "seed_sequence": seed_seq,
            "seed_sequence_index": run_index - 1,
            "rounds_actual": rounds,
            "stop_reason": None,
            "final_output_path": None,
            "final_sha256": None,
            "rollback_count": None,
            "best_score": None,
            "history": [],
            "config_snapshot": config_snapshot(self.config),
            "software_versions": collect_software_versions(),
            "model_hashes": self._model_hashes(),
            "components": self._generator_info(),
            "started_at": started_at,
            "finished_at": utcnow_iso(),
            "error": {"type": exc.error_type, "message": str(exc)},
        }

    def _skipped_manifest(self, run_index: int, pair_id: int, replicate_id: int) -> Dict[str, Any]:
        return {
            "run_id": f"run_{run_index:03d}",
            "run_index": run_index,
            "pair_id": pair_id,
            "replicate_id": replicate_id,
            "status": "skipped",
            "seed": None,
            "seed_strategy": self.config["random"]["strategy"],
            "seed_sequence": None,
            "seed_sequence_index": run_index - 1,
            "rounds_actual": None,
            "stop_reason": "abort_on_failure",
            "final_output_path": None,
            "final_sha256": None,
            "rollback_count": None,
            "best_score": None,
            "history": [],
            "config_snapshot": config_snapshot(self.config),
            "software_versions": collect_software_versions(),
            "model_hashes": self._model_hashes(),
            "components": self._generator_info(),
            "started_at": None,
            "finished_at": None,
            "error": {"type": "SkippedError", "message": "因 abort_on_failure 而跳过"},
        }
