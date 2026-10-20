"""CSV + HTML 报告生成（N 次独立创作 → N 张最终图 → 两两比较 C(N,2)）。

输出：
- ``runs_summary.csv``      每次创作状态汇总；
- ``final_image_index.csv`` 最终图像索引；
- ``pairwise_pairs.csv``    全部 C(N,2) 组两两比较（含全部指标）；
- ``pairwise_matrix.csv``   N×N 两两比较矩阵（主指标：SHA-256 一致性）；
- ``descriptive_stats.csv`` 相似度描述性统计（分布/均值/中位数/最小/最大/完全一致对数）；
- ``round_history.csv``     每轮种子与接受/回退决策；
- ``report.html``           自包含 HTML。

只有成功创作的最终图像进入相似度统计；失败创作仅出现在汇总中。
"""

from __future__ import annotations

import csv
import html as _html
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

from .comparison import compute_pair_metrics
from .manifest import collect_software_versions, utcnow_iso

METRIC_KEYS = [
    "sha256_equal",
    "pixel_exact",
    "pixel_mae",
    "pixel_similarity",
    "ssim",
    "lpips",
]

METRIC_NOTE = {
    "sha256_equal": "字节级一致，1.0=完全相同",
    "pixel_exact": "像素完全一致，1.0=完全相同",
    "pixel_mae": "平均绝对像素误差，越小越相似",
    "pixel_similarity": "像素相似度，越大越相似",
    "ssim": "结构相似性，越大越相似",
    "lpips": "感知距离，越小越相似",
}


def _rows_to_csv(path: Path, header: List[str], rows: List[List[Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(["" if v is None else v for v in row])
    return path


def descriptive(values: List[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"count": 0, "mean": None, "std": None, "min": None, "max": None, "median": None}
    return {
        "count": len(values),
        "mean": round(statistics.mean(values), 6),
        "std": round(statistics.pstdev(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "median": round(statistics.median(values), 6),
    }


def generate_reports(
    experiment_dir: Path | str, config: Dict[str, Any], manifests: List[Dict[str, Any]]
) -> Dict[str, Path]:
    experiment_dir = Path(experiment_dir)
    reports_dir = experiment_dir / config["paths"]["reports_dir"]
    reports_dir.mkdir(parents=True, exist_ok=True)

    success = [m for m in manifests if m.get("status") == "success"]
    images = [m["final_output_path"] for m in success]
    labels = [f"run_{m['run_index']:03d}" for m in success]
    n = len(images)

    # ---- 1. 状态汇总 -------------------------------------------------- #
    summary_rows = []
    for m in manifests:
        err = m.get("error") or {}
        seed_seq = m.get("seed_sequence")
        seed_seq_s = "" if seed_seq is None else ",".join(str(x) for x in seed_seq)
        summary_rows.append(
            [
                m["run_index"], m["run_id"], m["status"], m["seed"], m["seed_strategy"],
                seed_seq_s, m["rounds_actual"], m["stop_reason"],
                m["final_output_path"], m["final_sha256"], err.get("type"), err.get("message"),
            ]
        )
    summary_csv = _rows_to_csv(
        reports_dir / "runs_summary.csv",
        ["run_index", "run_id", "status", "seed", "seed_strategy", "seed_sequence",
         "rounds_actual", "stop_reason", "final_output_path", "final_sha256",
         "error_type", "error_message"],
        summary_rows,
    )

    # ---- 2. 最终图像索引 ---------------------------------------------- #
    index_rows = []
    for m in success:
        p = Path(m["final_output_path"])
        size_bytes = p.stat().st_size if p.exists() else None
        index_rows.append(
            [m["run_index"], m["run_id"], m["final_output_path"], m["final_sha256"],
             size_bytes, m["rounds_actual"], m["stop_reason"]]
        )
    index_csv = _rows_to_csv(
        reports_dir / "final_image_index.csv",
        ["run_index", "run_id", "final_output_path", "final_sha256",
         "size_bytes", "rounds_actual", "stop_reason"],
        index_rows,
    )

    # ---- 3. 两两比较（C(N,2)） ---------------------------------------- #
    pairs: List[Dict[str, Any]] = []
    for i in range(n):
        for j in range(i + 1, n):
            metrics = compute_pair_metrics(images[i], images[j])
            pairs.append(
                {"i": i + 1, "j": j + 1, "run_i": labels[i], "run_j": labels[j], **metrics}
            )

    pair_rows = []
    for p in pairs:
        pair_rows.append([p["i"], p["j"], p["run_i"], p["run_j"]] + [p.get(k) for k in METRIC_KEYS])
    pairs_csv = _rows_to_csv(
        reports_dir / "pairwise_pairs.csv",
        ["i", "j", "run_i", "run_j"] + METRIC_KEYS,
        pair_rows,
    )

    # N×N 矩阵（sha256_equal）
    sha_mat = [[1.0] * n for _ in range(n)] if n else []
    for p in pairs:
        v = p["sha256_equal"]
        sha_mat[p["i"] - 1][p["j"] - 1] = v
        sha_mat[p["j"] - 1][p["i"] - 1] = v
    if n > 0:
        mat_header = [""] + labels
        mat_rows = [[labels[i]] + [sha_mat[i][j] for j in range(n)] for i in range(n)]
        matrix_csv = _rows_to_csv(reports_dir / "pairwise_matrix.csv", mat_header, mat_rows)
    else:
        matrix_csv = _rows_to_csv(reports_dir / "pairwise_matrix.csv", ["(无成功创作)"], [])

    # ---- 4. 描述性统计 ------------------------------------------------ #
    stats_rows = []
    for key in METRIC_KEYS:
        values = [p[key] for p in pairs if p.get(key) is not None]
        d = descriptive(values)
        identical = ""
        if key in ("sha256_equal", "pixel_exact"):
            identical = sum(1 for v in values if v == 1.0)
        note = METRIC_NOTE.get(key, "")
        if not values:
            note = (note + "；") if note else ""
            note += "未计算（后端未安装或图像缺失）"
        stats_rows.append(
            [key, d["count"], d["mean"], d["median"], d["min"], d["max"], identical, note]
        )
    stats_csv = _rows_to_csv(
        reports_dir / "descriptive_stats.csv",
        ["metric", "count", "mean", "median", "min", "max", "identical_pairs", "note"],
        stats_rows,
    )

    # ---- 5. 每轮记录 -------------------------------------------------- #
    round_rows = []
    for m in manifests:
        for rec in m.get("history", []):
            round_rows.append(
                [m["run_index"], rec.get("round"), rec.get("action"), rec.get("score"),
                 rec.get("seed"), rec.get("rollback_count"), rec.get("no_improvement_count"),
                 rec.get("note")]
            )
    round_csv = _rows_to_csv(
        reports_dir / "round_history.csv",
        ["run_index", "round", "action", "score", "seed", "rollback_count",
         "no_improvement_count", "note"],
        round_rows,
    )

    # ---- 6. HTML ----------------------------------------------------- #
    html_path = _write_html(
        reports_dir / "report.html", experiment_dir, config, manifests,
        summary_rows, index_rows, pairs, stats_rows, labels, sha_mat,
    )

    return {
        "runs_summary": summary_csv,
        "final_image_index": index_csv,
        "pairwise_pairs": pairs_csv,
        "pairwise_matrix": matrix_csv,
        "descriptive_stats": stats_csv,
        "round_history": round_csv,
        "html": html_path,
    }


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #


def _esc(x: Any) -> str:
    return _html.escape("" if x is None else str(x))


def _table(headers: List[str], rows: List[List[Any]]) -> str:
    thead = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = ""
    for r in rows:
        tds = "".join(f"<td>{_esc(c)}</td>" for c in r)
        body += f"<tr>{tds}</tr>"
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>"


def _matrix_table(labels: List[str], mat: List[List[float]]) -> str:
    if not labels:
        return "<p>无成功创作。</p>"
    thead = "<th></th>" + "".join(f"<th>{_esc(l)}</th>" for l in labels)
    body = ""
    for i, l in enumerate(labels):
        tds = [f"<th>{_esc(l)}</th>"]
        for j in range(len(labels)):
            v = mat[i][j]
            color = "#c8e6c9" if v == 1.0 else ("#ffcdd2" if v == 0.0 else "#fff9c4")
            tds.append(f'<td style="background:{color};text-align:center">{_esc(v)}</td>')
        body += "<tr>" + "".join(tds) + "</tr>"
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>"


def _write_html(
    path: Path,
    experiment_dir: Path,
    config: Dict[str, Any],
    manifests: List[Dict[str, Any]],
    summary_rows: List[List[Any]],
    index_rows: List[List[Any]],
    pairs: List[Dict[str, Any]],
    stats_rows: List[List[Any]],
    labels: List[str],
    sha_mat: List[List[float]],
) -> Path:
    n_total = len(manifests)
    n_success = sum(1 for m in manifests if m.get("status") == "success")
    n_pairs = len(pairs)
    n_identical = sum(1 for p in pairs if p.get("sha256_equal") == 1.0)

    pair_rows = []
    for p in pairs:
        pair_rows.append([p["i"], p["j"], p["run_i"], p["run_j"]] + [p.get(k) for k in METRIC_KEYS])

    versions = collect_software_versions()
    versions_html = (
        "<ul>" + "".join(f"<li>{_esc(k)}: {_esc(v)}</li>" for k, v in versions.items()) + "</ul>"
    )

    mock_banner = ""
    if config["generator"]["type"] == "mock":
        mock_banner = (
            '<div style="background:#fff3cd;border:1px solid #ffc107;padding:10px;margin:10px 0;">'
            "<strong>⚠ 本报告由 MOCK_ONLY 模拟生成器产生，仅用于验证工作流与报告管线，"
            "不构成任何真实图像生成实验结论。</strong></div>"
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>AIGC 可复现性实验报告</title>
<style>
body {{ font-family: "Segoe UI", "Microsoft YaHei", sans-serif; margin: 24px; color: #222; }}
h1, h2 {{ color: #1a3d6e; }}
table {{ border-collapse: collapse; margin: 12px 0; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; font-size: 13px; text-align: left; }}
th {{ background: #eef3fa; }}
td {{ word-break: break-all; }}
.banner {{ background:#e3f2fd; border:1px solid #2196f3; padding:10px; margin:10px 0; }}
</style>
</head>
<body>
<h1>AIGC 可复现性实验报告（N 次独立创作两两比较）</h1>
{mock_banner}
<div class="banner">
<p><strong>实验 ID：</strong>{_esc(experiment_dir.name)}</p>
<p><strong>创作次数：</strong>{n_total}（<strong>成功：</strong>{n_success}）</p>
<p><strong>两两比较组数：</strong>{n_pairs}（C({n_success},2)）</p>
<p><strong>字节级完全一致的对数：</strong>{n_identical}</p>
<p><strong>生成时间：</strong>{_esc(utcnow_iso())}</p>
</div>

<h2>1. 每次创作状态汇总</h2>
{_table(["run_index","run_id","status","seed","seed_strategy","rounds_actual","stop_reason","final_sha256","error_type","error_message"], summary_rows)}

<h2>2. 两两比较矩阵（SHA-256 字节级一致性，1.0=完全相同）</h2>
{_matrix_table(labels, sha_mat)}

<h2>3. 两两比较长表（C({n_success},2) = {n_pairs} 组）</h2>
{_table(["i","j","run_i","run_j"] + METRIC_KEYS, pair_rows)}

<h2>4. 相似度描述性统计</h2>
{_table(["metric","count","mean","median","min","max","identical_pairs","note"], stats_rows)}

<h2>5. 软件与模型版本</h2>
{versions_html}

<footer><p>注：文件哈希不同不代表图像内容必然不同；SSIM/LPIPS 不能直接等同于法律意义上的表达相似性。</p></footer>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")
    return path
