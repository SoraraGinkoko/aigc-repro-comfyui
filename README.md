# AIGC 可复现性实验（法学课程论文）

这个仓库是一篇法学课程论文的实验代码。问题很具体：在同一套创作规则下，让生成模型反复出图，看最终结果到底有多「像」。这里只做技术层面的相似度度量（哈希、像素、SSIM），不涉及、也不主张任何法律上的独创性结论。

## 实验设置

生成走 ComfyUI 的本地接口，模型是 Stable Diffusion 1.5（`v1-5-pruned-emaonly.safetensors`），搭配 Canny ControlNet（`control_v11p_sd15_canny_fp16.safetensors`）。

创作对象是学校图书馆。控制图由图书馆照片经 Canny 边缘检测得到（scikit-image，`sigma=2.0`），512×512 白线黑底。提示词、分辨率 512×512、euler 采样器、20 步、CFG 7.0、控制强度 1.0 在所有创作里固定不变。

评价用 CLIP（`openai/clip-vit-base-patch32`，跑在 CPU 上），拿图像—文本 logits 作为每张候选图的分数，只用来决定「接受」还是「回退」，不反过来改提示词或生成参数。提示词有 89 个 token，超过 CLIP 文本编码器 77 的上限，评价器里加了截断（`truncation=True, max_length=77`），否则会直接报错。

## 实验设计

一共做 10 次独立创作。每次用一条不同的、事先固定好的种子序列——种子簿是 20 条 × 20 个种子，互不重复、无平移重叠，由 `master_seed` 确定性生成，实验前落盘，不做事后挑选。第 `run_index` 次创作取第 `run_index-1` 条序列，每轮用 `sequence[round-1]`，实际提交给 KSampler 的种子会写进 manifest 和审计日志。

每次创作按「生成—评价—接受/回退」循环，上限 20 轮。这轮实验把连续回退阈值也设成了 20，所以 10 次都跑满 20 轮（`stop=max_iterations`）。

比较对象是 10 张最终图，两两计算 SHA-256、像素相似度和 SSIM，共 C(10,2)=45 组。LPIPS 这次没算——环境里下不了 torchvision 的骨干权重，指标留空，不编数。

## 结果

10 张图没有两张字节级相同（0/45）。像素相似度均值 0.830（0.754–0.877），SSIM 均值 0.473（0.367–0.601），LPIPS 缺失。

另外做了一个对照：同一条种子序列重复跑 3 次，最终图的 SHA-256 完全一致。也就是说这台机器上生成过程本身是确定的，前面那些差异来自种子不同，而不是计算噪声。

这些数字只反映技术上的相似程度，不能拿来证明 AI 生成内容享有著作权，也不能证明人对其有实质控制。

## 跑起来

```powershell
# 1. 启动 ComfyUI（另开窗口，等 http://127.0.0.1:8188 就绪）
powershell -ExecutionPolicy Bypass -File scripts\run_comfyui.ps1

# 2. 预检
D:\Anaconda_envs\envs\comfyui\python.exe scripts\preflight_check.py --config config\pair_experiment_config.json

# 3. 正式实验（10 次 × 20 轮，CLIP 评价）
D:\Anaconda_envs\envs\comfyui\python.exe run_experiment.py --config config\pair_experiment_config.json
```

第一次跑 CLIP 需要先把模型下到本地缓存。如果 HuggingFace 连不上，用国内镜像：

```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
D:\Anaconda_envs\envs\comfyui\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('openai/clip-vit-base-patch32')"
```

之后运行实验时加 `$env:HF_HUB_OFFLINE="1"` 即可离线加载。

结果都在 `runs/<实验ID>/` 下：`reports/` 有 `pairwise_pairs.csv`（45 组明细）、`pairwise_matrix.csv`、`descriptive_stats.csv` 和 `report.html`；`runs/run_XXX/final.png` 是每次创作的最终图。

## 配置和脚本

- `config/pair_experiment_config.json`：正式实验（10 次 × 20 轮，CLIP 评价）。
- `config/library_preview_config.json`：快速预览（mock 评价，跑得慢的话先看效果用）。
- `config/determinism_check_config.json`：同种子重复跑的确定性对照。
- `config/seed_book.json`：正式种子簿；`config/seed_book_same3.json` 是确定性对照用的三条相同序列。
- `scripts/determinism_check.py`：同一种子跑 3 遍，比对 SHA-256。
- `scripts/make_grid.py`：把 10 张最终图拼成 5×2 网格（论文插图用）。
- `scripts/preview_compare3.py`：临时练手脚本，算 3 张图的两两相似度。

## 已知限制

1. **CLIP 跑在 CPU 上**，速度比 GPU 慢，但避免和 ComfyUI 抢 8GB 显存。
2. **LPIPS 没有算**，原因见上，报告里留空。
3. **换模型就等于换实验条件**：结论只针对 SD1.5 + 这套 Canny 工作流 + 这个图书馆任务，换成 SDXL/Flux 是另一组实验，不能混着算。
4. **「最多 20 轮」不等于「必须 20 轮」**：这轮把回退阈值调到 20 才让每次都跑满；如果按原来的「连续回退 5 次即停」，多数创作会在 6 到 11 轮之间提前结束。
5. **模拟数据不是真实实验**：仓库里的 mock 生成器/评价器只用于测试管线，不能当实验结果。

## 说明

代码里的技术指标只是度量工具。哈希、像素误差、SSIM、LPIPS 反映的是图像在技术层面有多接近，和著作权法上的独创性判断是两回事，写论文时不要把两者混为一谈。
