"""统一的异常类型。

设计原则：
- 任何失败都必须显式抛出并记录，不得静默跳过；
- 一次失败的运行以 status="failed" 写入 manifest，且不计为成功；
- ``GeneratorError`` / ``EvaluatorError`` 表示可重试的瞬时后端错误；
- ``MetricUnavailableError`` 表示 SSIM/LPIPS 等预留指标的后端未安装。
"""


class ReproError(Exception):
    """项目所有异常的基类。"""


class ConfigError(ReproError):
    """配置缺失、非法或校验失败。"""


class GeneratorError(ReproError):
    """生成器（可替换后端）在生成/修改时失败，可安全重试。"""


class EvaluatorError(ReproError):
    """评价器在评价时失败，可安全重试。"""


class MetricUnavailableError(ReproError):
    """预留指标（SSIM/LPIPS 等）所需后端未安装，当前不计算、不编造数值。"""


class CheckpointError(ReproError):
    """断点记录/恢复失败。"""


class RunFailedError(ReproError):
    """标记一次运行失败。携带可审计的错误信息，最终写入 manifest。"""

    def __init__(self, message: str, error_type: str, rounds: int = 0):
        super().__init__(message)
        self.error_type = error_type
        self.rounds = rounds
