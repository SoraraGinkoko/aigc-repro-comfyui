# AIGC 可复现性实验

本仓库为法学课程论文的实验代码，目的在于考察：在同一创作规则下，生成模型多次输出结果的最终图像之间，技术层面具有何种程度的相似性。文中所有度量均为技术指标，不构成著作权法意义上的独创性判断。

## 一、实验设置

生成采用 ComfyUI 本地接口，模型为 Stable Diffusion 1.5（v1-5-pruned-emaonly.safetensors），ControlNet 为 Canny（control_v11p_sd15_canny_fp16.safetensors）。

控制图由学校图书馆照片经 Canny 边缘检测生成（scikit-image，σ=2.0），尺寸 512×512，白线黑底。

提示词、分辨率 512×512、采样器 euler、步数 20、CFG 7.0、控制强度 1.0 在整个实验中保持固定。

评价采用 CLIP（openai/clip-vit-base-patch32，运行于 CPU），以图像—文本 logits 作为候选图评分，仅用于接受/回退判定，不修改提示词或生成参数。提示词共 89 token，超过该模型 77 token 的上限，评价器据此采用截断处理（truncation=True，max_length=77）。

## 二、实验设计

共进行 10 次独立创作。每次创作使用一条互不重复、预先固定的种子序列；种子簿含 20 条序列、每条 20 个种子，由 master_seed 确定性生成，并于实验前保存。第 i 次创作使用第 i-1 条序列，每轮取 sequence[round-1]；实际提交的种子写入 manifest 与审计日志。

每次创作执行「生成—评价—接受/回退」循环，轮数上限为 20。本次实验将连续回退阈值设为 20，因而 10 次创作均执行满 20 轮（stop=max_iterations）。

比较对象为 10 张最终图像，两两计算 SHA-256、像素相似度与 SSIM，共计 C(10,2)=45 组。LPIPS 未予计算（运行环境无法获取 torchvision 骨干权重），相应指标留空。

## 三、实验结果

10 张最终图像之间无字节级完全相同者（0/45）。像素相似度均值为 0.830（范围 0.754–0.877），SSIM 均值为 0.473（范围 0.367–0.601），LPIPS 缺失。

确定性对照：同一序列重复运行 3 次，最终图像 SHA-256 完全一致。该结果表明，本机上的生成过程具有确定性，前述差异源于种子不同，而非计算噪声。

上述结果仅反映技术层面的相似程度，不构成对独创性、作者身份或人类实质创作控制的证明。

## 四、运行方式

```powershell
# 1. 启动 ComfyUI（等待 http://127.0.0.1:8188 就绪）
powershell -ExecutionPolicy Bypass -File scripts\run_comfyui.ps1

# 2. 预检
D:\Anaconda_envs\envs\comfyui\python.exe scripts\preflight_check.py --config config\pair_experiment_config.json

# 3. 正式实验（10 次 × 20 轮，CLIP 评价）
D:\Anaconda_envs\envs\comfyui\python.exe run_experiment.py --config config\pair_experiment_config.json
```

CLIP 模型须预先下载至本地缓存。若无法访问 HuggingFace，可采用镜像：

```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
D:\Anaconda_envs\envs\comfyui\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('openai/clip-vit-base-patch32')"
```

运行时可设置 `$env:HF_HUB_OFFLINE="1"`，以离线方式加载。

实验结果位于 runs/<实验ID>/：reports/ 下含 pairwise_pairs.csv（45 组）、pairwise_matrix.csv、descriptive_stats.csv 与 report.html；runs/run_XXX/final.png 为各次创作的最终图像。

## 五、配置与脚本

- config/pair_experiment_config.json：正式实验（10 次 × 20 轮，CLIP 评价）
- config/library_preview_config.json：预览配置（mock 评价）
- config/determinism_check_config.json：确定性对照配置
- config/seed_book.json：正式种子簿；config/seed_book_same3.json：对照所用三条相同序列
- scripts/determinism_check.py：同种子重复运行并比对 SHA-256
- scripts/make_grid.py：将 10 张最终图像合成为 5×2 网格
- scripts/preview_compare3.py：3 张图像的两两比较

## 六、已知限制

1. CLIP 于 CPU 运行，速度较慢，但可避免与 ComfyUI 争用显存。
2. LPIPS 未计算，报告中留空，不以其他数值替代。
3. 更换模型即构成新的实验条件。本结论仅适用于 SD1.5 与本 Canny 工作流，不适用于 SDXL、Flux 等其他模型。
4. 「最多 20 轮」与「必须 20 轮」为不同口径。本次实验因将回退阈值调整为 20 才使各次创作均执行满 20 轮；若沿用「连续回退 5 次即停止」，多数创作将在 6 至 11 轮之间提前结束。
5. 仓库中的 mock 生成器与评价器仅用于测试流程，不作为实验结果使用。
