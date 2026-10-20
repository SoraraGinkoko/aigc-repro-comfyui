# AIGC 可复现性实验（法学知识产权课程论文）

本项目用于检验「同一创作规则下，生成式 AI 最终输出的可复现程度」这一经验问题，
提供一套**配置驱动、可替换后端、可复现、可审计**的实验骨架。

> **技术相似度 ≠ 法律独创性**：本项目的 SHA-256 / 像素 / SSIM / LPIPS 只反映
> **技术层面**的一致程度，不构成著作权法上的独创性判断，也不等同于作者身份或人类实质控制。

---

## 1. 当前状态

- **真实后端**：ComfyUI（本地 HTTP API）+ **Stable Diffusion 1.5** + **Canny ControlNet**。
- **创作对象**：某高校图书馆。控制图 `library_edges.png` 由照片经 Canny 边缘检测（scikit-image，`sigma=2.0`，约 9% 边缘密度）生成，白线黑底、512×512。
- **实验设计**：**10 次独立创作**（`num_runs=10`、`replicates_per_pair=1`），每次使用**不同、预先固定、互不重叠**的种子序列，最终比较 10 张最终图的两两相似度（**C(10,2)=45 组**）。
- **已实测结论**（mock 评价器，真实 ComfyUI 生成）：
  - **同一种子序列跑 3 遍 → 最终图 SHA-256 字节级完全一致**（确定性可复现）；
  - **不同种子序列 → 0/45 字节级相同**，像素相似度均值 ≈ **0.842**，SSIM 均值 ≈ **0.474**。

> mock 评价器只用于预览/诊断（见 §6.3）；正式实验用 CLIP 评价器，需在**本地终端**运行（自动化执行环境无外网，无法下载 CLIP 模型）。

---

## 2. 实验设计

### 2.1 一次创作

从相同初始意图/提示词开始，用相同模型、控制图、分辨率、采样器、步数、CFG、ControlNet 强度，
按同一套规则执行「生成 → 评价 → 接受/回退 → 停止」，最终按规则确定一张最终图像。

### 2.2 10 次独立创作

- 共 **10 次创作**（`num_runs=10`），**不是配对 A/B**。
- 每次创作使用**不同、预先固定、互不重叠**的种子序列（种子簿第 `run_index-1` 条）。
- 每次最多 **20 轮**；若提前停止，如实记录实际轮数与停止原因（不凑轮数）。

### 2.3 种子簿（可审计）

- `config/seed_book.json`：**20 条序列 × 20 个种子**，全部互不重复、无平移重叠，由 `master_seed` 确定性生成，正式实验前落盘，**绝不事后挑选**。
- 第 `run_index` 次创作用第 `run_index-1` 条序列；每轮取 `sequence[round-1]`，实际提交给 KSampler 的种子写入审计与 manifest。

### 2.4 评价与停止（如实描述）

- 评价 = **CLIP 图像-文本相似度**（`device=cpu`，避免与 ComfyUI 争抢 8GB 显存）。
- CLIP 分数**仅用于候选接受/回退门控**，**不反馈到提示词或任何生成参数**——「修改」步实际上是「取序列下一个种子重新生成」。
- 停止规则：硬上限 20 轮；连续回退达 `max_consecutive_rollbacks`（5）次提前停止；每轮记录评分、决策、连续回退次数、停止原因。

---

## 3. 环境要求

- **ComfyUI** + SD1.5 + Canny ControlNet（本地 `http://127.0.0.1:8188`）。
- 运行实验的 Python：`D:\Anaconda_envs\envs\comfyui\python.exe`（含 torch、scikit-image、transformers、lpips）。
- 依赖锁定见 `requirements.txt`（核心为 Pillow；真实后端另需 torch/scikit-image/lpips 等）。

---

## 4. 运行测试

```bat
:: 标准库 unittest（无需 pytest）
python -m unittest discover -s tests -t . -v
```

当前 **37 项测试全部通过**，覆盖：迭代上限、状态隔离、运行次数、失败记录、最终图归档、
报告生成（10 次 → 45 组两两比较）、确定性（fixed 种子字节一致 / run_index 相异）、断点恢复、
种子簿、ComfyUI 集成等。

---

## 5. 运行实验

```bat
:: 0) 启动 ComfyUI（另开窗口，等待 http://127.0.0.1:8188 就绪）
powershell -ExecutionPolicy Bypass -File scripts\run_comfyui.ps1

:: 1) 预检（服务/模型/GPU/torch/SSIM/LPIPS/种子簿）
D:\Anaconda_envs\envs\comfyui\python.exe scripts\preflight_check.py --config config\pair_experiment_config.json

:: 2) 单轮冒烟（验证真实出图）
D:\Anaconda_envs\envs\comfyui\python.exe scripts\single_round_smoke_test.py

:: 3) 3 张预览（mock 评价、快速看效果；可选）
D:\Anaconda_envs\envs\comfyui\python.exe run_experiment.py --config config\library_preview_config.json

:: 4) 正式实验（10 次创作 × 至多 20 轮；CLIP 评价）
D:\Anaconda_envs\envs\comfyui\python.exe run_experiment.py --config config\pair_experiment_config.json
```

续跑（跳过已完成的运行）：

```bat
python run_experiment.py --config config\pair_experiment_config.json --experiment-id <已有的实验ID> --resume
```

参数：

| 参数 | 说明 |
| --- | --- |
| `--config` | 配置路径 |
| `--experiment-id` | 显式实验 ID；不指定则自动生成 |
| `--resume` | 断点恢复，已成功的运行幂等跳过 |
| `--force` | 覆盖已存在实验目录（不推荐） |

---

## 6. 配置与评价器

### 6.1 正式配置 `config/pair_experiment_config.json`

```jsonc
{
  "num_runs": 10,                    // 10 次独立创作
  "replicates_per_pair": 1,          // 每次创作独立，不配对
  "max_iterations_per_run": 20,      // 每次最多 20 轮
  "rollback": { "enabled": true, "max_consecutive_rollbacks": 5, "tolerance": 0.0 },
  "generator": {
    "type": "comfyui",
    "checkpoint": "v1-5-pruned-emaonly.safetensors",
    "controlnet": "control_v11p_sd15_canny_fp16.safetensors",
    "control_image": "library_edges.png",
    "prompt": "a grand modern library building, ... photorealistic architectural render, detailed stone texture, sharp focus, soft natural daylight",
    "width": 512, "height": 512, "sampler": "euler", "steps": 20, "cfg": 7.0,
    "control_strength": 1.0, "use_canny_preprocess": false,
    "seed_book_file": "config/seed_book.json"
  },
  "evaluator": { "type": "clip", "clip": { "clip_model": "openai/clip-vit-base-patch32", "device": "cpu" } }
}
```

### 6.2 其他配置

- `config/library_preview_config.json`：快速预览（mock 评价、`num_runs=3`、可调参数），非正式数据。
- `config/determinism_check_config.json`：确定性对照（3 次同种子序列）。
- `config/seed_book.json`：正式种子簿（20×20）。
- `config/seed_book_same3.json`：确定性对照用的「3 条相同序列」簿。

### 6.3 评价器

- 正式实验：`clip`（真实图像-文本相似度，`device=cpu`）。
- 预览/诊断：`mock`（按图像哈希映射 [0,1)，**无语义**，仅驱动接受/回退流程，不代表语义最优）。
- 预览与正式实验的评价器不同，**不可把 mock 结果当作正式实验数据**。

---

## 7. 输出产物

每次实验在 `runs/<experiment_id>/` 下生成：

```
runs/<experiment_id>/
├── experiment.json
├── config_snapshot.json
├── logs/experiment.log
├── reports/
│   ├── runs_summary.csv       # 全部创作状态汇总（含种子序列）
│   ├── final_image_index.csv  # 最终图像索引
│   ├── pairwise_pairs.csv     # C(N,2) 组两两比较（45 组）
│   ├── pairwise_matrix.csv    # N×N 矩阵（SHA-256 一致性）
│   ├── descriptive_stats.csv  # 相似度统计（均值/中位数/最小/最大/完全一致对数）
│   ├── round_history.csv      # 每轮种子与接受/回退决策
│   └── report.html            # 自包含 HTML 报告
└── runs/run_XXX/
    ├── manifest.json          # 轮数/种子/配置/版本/状态/输出路径
    ├── final.png              # 最终图像（主要比较对象）
    ├── best.png / current.png # 中间状态（仅审计）
    ├── checkpoint.json        # 断点记录
    └── audit.log              # 每轮审计日志
```

相似度指标：

| 指标 | 含义 | 状态 |
| --- | --- | --- |
| `sha256_equal` | 字节级一致性（1.0=完全相同） | ✅ |
| `pixel_exact` / `pixel_similarity` | 解码后像素一致性 | ✅ |
| `ssim` | 结构相似性（越高越相似） | ✅ 需 `numpy`+`scikit-image` |
| `lpips` | 感知距离（越小越相似） | ✅ 需 `lpips`+`torch`+`torchvision`；**下载骨干失败时降级为空，不崩溃** |

> 原则：不编造阈值或数据；指标不可用时留空并标注原因，不当作 0。

---

## 8. 确定性对照（关键结论）

除正式实验外，另设「同一种子序列跑 3 遍」的对照（`scripts/determinism_check.py`）：

- **同种子 × 3 遍 → 最终图 SHA-256 完全一致**（字节级可复现）。
- 这说明：**在这台硬件上，SD1.5 + Canny 工作流对同一种子是确定性的**。
- 因此，正式实验中 10 张图之间的差异（0/45 字节一致、像素 0.84、SSIM 0.47）**可归因于种子（随机轨迹）差异，而非 GPU 计算噪声**。

---

## 9. 项目结构

```
exp/
├── run_experiment.py              # CLI 入口
├── config/                        # 实验配置与种子簿
├── aicg_repro/
│   ├── config.py                  # 配置加载/校验/快照/种子策略
│   ├── controller.py              # 控制器（循环/停止/回退/重试/断点/种子簿）
│   ├── state.py                   # 状态重置与隔离
│   ├── seeds.py                   # 种子序列与种子簿
│   ├── generators/                # 生成器（mock / comfyui_generator）
│   ├── evaluators/                # 评价器（mock / clip）
│   ├── build.py                   # 配置 → 生成器/评价器 工厂
│   ├── comparison.py              # SHA-256/像素/SSIM/LPIPS
│   ├── manifest.py                # manifest 与版本收集
│   ├── reporting.py               # CSV + HTML（N 次两两比较）
│   └── errors.py / audit.py
├── scripts/
│   ├── run_comfyui.ps1            # 启动 ComfyUI 服务
│   ├── preflight_check.py         # 预检
│   ├── single_round_smoke_test.py # 单轮冒烟
│   ├── generate_seed_book.py      # 预生成种子簿
│   ├── determinism_check.py       # 同种子 × 3 遍确定性对照
│   ├── make_grid.py               # 10 张图合成 5×2 网格（论文插图）
│   └── preview_compare3.py        # 3 张图快速比较
├── tests/                         # 37 项 unittest
└── README.md
```

---

## 10. 已知限制

1. **预览用 mock 评价**：本地自动化环境无外网，CLIP 模型无法下载，预览实验用 mock 伪随机分数；正式实验须在本地终端用 CLIP。
2. **LPIPS 在受限环境降级为空**：若无法下载 torchvision 骨干权重，LPIPS 留空（不崩溃、不编造）。
3. **「最多 20 轮」≠「必须 20 轮」**：实际轮数由停止/回退规则决定，论文应如实写实际轮数与停止原因。
4. **换模型 = 换实验条件**：本实验的结论限于 SD1.5 + 该 Canny 工作流 + 该任务；换 SDXL/Flux 属另一组实验，不可混算。
5. **技术指标 ≠ 法律结论**：参见开头声明。

---

## 11. 免责声明

本项目仅用于法学课程论文的方法学讨论（「生成式 AI 是否具有工具意义上的确定性」），
不构成任何法律意见，也不对任何生成式 AI 的确定性/非确定性作最终结论；技术相似度指标
不构成著作权法上的独创性判断。
