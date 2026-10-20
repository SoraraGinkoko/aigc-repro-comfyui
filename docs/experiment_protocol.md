# 实验方案（AIGC 著作权课程论文 · 真实图像生成可复现性实验）

> 本文件是正式实验的**方法学说明**，与代码、配置、脚本、测试配套使用。
> 论文撰写时可直接引用本方案的参数与流程。

## 1. 研究问题

在**相同条件**下，生成式 AI 多次独立运行，其最终输出「在多大程度上相同」——
即验证生成式 AI 是否具有**工具意义上的确定性（可复现性）**。

## 2. 实验设计（确定性组）

- 独立运行 **5 次**；每次运行**最多 20 轮**（「生成 → 评价 → 修改/回退」）。
- **固定全部条件**（见 §3），仅比较 **5 张最终图像**（C(5,2)=10 组两两比较）。
- 中间日志仅用于审计，不纳入最终图像相似度统计。

> 「最多 20 轮」与「必须 20 轮」是两种口径：本实验用「最多 20 轮」，
> 允许按停止/回退规则提前结束；实际轮数与停止原因写入 manifest。
> 「固定种子」与「不同种子」是不同实验问题：本实验用固定种子验证确定性；
> 若验证可变性，改用 `random.strategy="run_index"` 另做一组，不得混同。

## 3. 固定条件清单（全部写入配置并快照）

| 类别 | 固定值 |
| --- | --- |
| 基础模型 | `v1-5-pruned-emaonly.safetensors`（SD 1.5） |
| ControlNet | `control_v11p_sd15_canny.pth`（Canny） |
| 提示词 | `a geometric still life of a balance scale, flat vector illustration, clean lines, minimal` |
| 负向提示词 | `lowres, bad anatomy, bad hands, text, watermark, worst quality, jpeg artifacts` |
| 控制图 | `assets/control_image.png`（原创、白线黑底边缘图，确定性生成） |
| 分辨率 | 512×512 |
| 采样器 / 调度器 | `euler` / `normal` |
| 步数 / CFG | 20 / 7.0 |
| 控制强度 | 1.0 |
| Canny 预处理 | 关闭（直接送预生成边缘图，更可复现） |
| 种子序列 | `config/seed_sequence.json`（20 个固定种子，5 次运行共用同一份） |
| 软件依赖 | Python 3.12 + torch 2.5.1+cu121 + ComfyUI（git commit 记录） |
| 运行规则 | 评价/回退规则见 §5 |

## 4. 随机种子序列

- 使用**预先保存**的 20 个整数种子（LCG 确定性生成，见 `config/seed_sequence.json`）。
- 第 r 轮使用 `sequence[r-1]`；5 次运行共用同一序列，保证「相同条件」可比。
- **每轮实际种子**写入审计日志与 manifest，供审计与复现。

## 5. 评价、修改与回退规则（写入配置，不由模型临时更改）

- 评价：CLIP 图像-文本相似度（`openai/clip-vit-base-patch32`，纯技术指标）。
- 修改：下一轮使用序列中的下一个种子，其余参数不变。
- 回退：若本轮分数未超过历史最优（容差 0.0），丢弃候选、回退到最优；
  连续回退达 `max_consecutive_rollbacks=5` 次则提前停止（停止原因 `rollback_limit`）。

## 6. 主要度量（仅对 5 张最终图像）

| 指标 | 语义 | 方向 |
| --- | --- | --- |
| SHA-256 | 字节级一致 | 相同=1.0 |
| 像素 MAE / 像素相似度 | 解码后像素一致 | 误差越小越相似 |
| SSIM | 结构相似性 | 越大越相似 |
| LPIPS | 感知距离 | 越小越相似 |

输出：10 组两两比较矩阵 + 描述性统计（CSV + HTML）。

## 7. 环境与版本记录（manifest 自动记录）

GPU 名称/显存、NVIDIA 驱动、Python、PyTorch/CUDA、Pillow、平台、ComfyUI git commit、
模型文件 SHA-256、每轮种子、实际轮数、停止原因、配置快照。

## 8. 失败处理（不静默跳过）

OOM / 生成失败 / 模型调用失败 → `GeneratorError` → 按 `max_retries` 安全重试 →
耗尽则标记 `failed` 并写 manifest；模型文件缺失 → `ConfigError` 记录到 manifest；
失败运行**不计为成功**，且不进入主要相似度统计。

## 9. 法律边界

技术相似度（哈希/SSIM/LPIPS）只反映**技术层面**的一致程度，**不构成**著作权法上的
独创性判断；论文不得把技术相似度直接解释为法律独创性。

## 10. 运行顺序

预检 → 单轮生成冒烟测试 → 20 轮试运行（`num_runs=1`）→ 正式 5 次实验，
详见 `README.md` 第 10 节。
