#!/usr/bin/env python3
"""
报告生成模块

功能：
- 生成 Markdown 格式的评测报告
- 包含单模型详情和模型对比
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List
import yaml

from metrics import MetricsCollector, ModelMetrics


class ReportGenerator:
    """报告生成器"""

    def __init__(self, results_dir: str, config_path: str):
        self.results_dir = Path(results_dir)
        self.config_path = config_path
        self.collector = MetricsCollector(results_dir, config_path)

    def generate_model_report(self, metrics: ModelMetrics) -> str:
        """生成单模型报告"""
        model_info = self.collector.config["models"].get(metrics.model_name, {})
        description = model_info.get("description", metrics.model_name)

        report = f"""# {description} 评测报告

> 评测时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}
> 模型 ID: {metrics.model_name}

## 综合得分

**总分**: {metrics.total_score:.1f}/100

## 分项得分

| 维度 | 得分 | 满分 |
|------|------|------|
| 准确率 | {metrics.accuracy_score:.1f} | 50 |
| 速度 | {metrics.speed_score:.1f} | 20 |
| 效率 | {metrics.efficiency_score:.1f} | 15 |

## 准确率详情

| Benchmark | 通过数 | 总数 | 通过率 |
|-----------|--------|------|--------|
| HumanEval | {metrics.human_eval_passed} | {metrics.human_eval_total} | {metrics.human_eval_passed/max(metrics.human_eval_total,1)*100:.1f}% |
| MBPP | {metrics.mbpp_passed} | {metrics.mbpp_total} | {metrics.mbpp_passed/max(metrics.mbpp_total,1)*100:.1f}% |

## 性能指标

| 指标 | 数值 |
|------|------|
| 平均响应时间 | {metrics.avg_elapsed_ms:.0f}ms |
| P95 响应时间 | {metrics.p95_elapsed_ms:.0f}ms |
| 总 Token 消耗 | {metrics.total_tokens:,} |
| 平均每题 Token | {metrics.avg_tokens_per_task:.0f} |

## 分析

### 优势
- {self._analyze_strengths(metrics)}

### 劣势
- {self._analyze_weaknesses(metrics)}
"""
        return report

    def _analyze_strengths(self, metrics: ModelMetrics) -> str:
        """分析优势"""
        strengths = []

        if metrics.human_eval_total > 0:
            rate = metrics.human_eval_passed / metrics.human_eval_total
            if rate > 0.7:
                strengths.append("HumanEval 通过率较高")
            if rate > 0.9:
                strengths.append("HumanEval 表现优秀")

        if metrics.mbpp_total > 0:
            rate = metrics.mbpp_passed / metrics.mbpp_total
            if rate > 0.7:
                strengths.append("MBPP 通过率较高")
            if rate > 0.9:
                strengths.append("MBPP 表现优秀")

        if metrics.avg_elapsed_ms < 3000:
            strengths.append("响应速度较快")

        if metrics.avg_tokens_per_task < 500:
            strengths.append("Token 使用效率高")

        return "；".join(strengths) if strengths else "暂无明显优势"

    def _analyze_weaknesses(self, metrics: ModelMetrics) -> str:
        """分析劣势"""
        weaknesses = []

        if metrics.human_eval_total > 0:
            rate = metrics.human_eval_passed / metrics.human_eval_total
            if rate < 0.5:
                weaknesses.append("HumanEval 通过率较低")

        if metrics.mbpp_total > 0:
            rate = metrics.mbpp_passed / metrics.mbpp_total
            if rate < 0.5:
                weaknesses.append("MBPP 通过率较低")

        if metrics.avg_elapsed_ms > 5000:
            weaknesses.append("响应速度较慢")

        if metrics.avg_tokens_per_task > 1000:
            weaknesses.append("Token 消耗较高")

        return "；".join(weaknesses) if weaknesses else "暂无明显劣势"

    def generate_comparison_report(self, metrics_list: List[ModelMetrics]) -> str:
        """生成对比报告"""
        ranking = self.collector.get_ranking(metrics_list)

        report = f"""# LLM Agent 编程能力评测报告

> 评测时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}
> 评测工具: zhiwei-bench
> 评测模型: {", ".join(m.model_name for m in metrics_list)}

## 排名

"""
        for i, m in enumerate(ranking, 1):
            model_info = self.collector.config["models"].get(m.model_name, {})
            desc = model_info.get("description", m.model_name)
            report += f"{i}. **{desc}**: {m.total_score:.1f}/100\n"

        report += """
## 各维度对比

| 模型 | 总分 | 准确率(50) | 速度(20) | 效率(15) | HumanEval | MBPP |
|------|------|-----------|---------|---------|-----------|------|
"""
        for m in ranking:
            model_info = self.collector.config["models"].get(m.model_name, {})
            desc = model_info.get("description", m.model_name)
            report += f"| {desc} | {m.total_score:.1f} | {m.accuracy_score:.1f} | {m.speed_score:.1f} | {m.efficiency_score:.1f} | {m.human_eval_passed}/{m.human_eval_total} | {m.mbpp_passed}/{m.mbpp_total} |\n"

        # 性能对比
        report += """
## 性能对比

| 模型 | 平均响应时间 | P95响应时间 | 总Token |
|------|-------------|------------|---------|
"""
        for m in ranking:
            model_info = self.collector.config["models"].get(m.model_name, {})
            desc = model_info.get("description", m.model_name)
            report += f"| {desc} | {m.avg_elapsed_ms:.0f}ms | {m.p95_elapsed_ms:.0f}ms | {m.total_tokens:,} |\n"

        # 结论
        report += f"""
## 结论

### 最佳模型
**{self.collector.config["models"].get(ranking[0].model_name, {}).get("description", ranking[0].model_name)}** 以 {ranking[0].total_score:.1f} 分排名第一。

### 建议
{self._generate_recommendations(ranking)}

---
*报告由 zhiwei-bench 自动生成*
"""
        return report

    def _generate_recommendations(self, ranking: List[ModelMetrics]) -> str:
        """生成建议"""
        if not ranking:
            return "暂无建议"

        best = ranking[0]
        recommendations = []

        # 准确率建议
        if best.human_eval_total > 0 or best.mbpp_total > 0:
            total_tasks = best.human_eval_total + best.mbpp_total
            total_passed = best.human_eval_passed + best.mbpp_passed
            if total_passed / max(total_tasks, 1) > 0.8:
                recommendations.append(f"**{self.collector.config['models'].get(best.model_name, {}).get('description', best.model_name)}** 在编程任务上表现优秀，适合用于代码生成场景。")

        # 速度建议
        fastest = min(ranking, key=lambda m: m.avg_elapsed_ms)
        if fastest.avg_elapsed_ms > 0:
            recommendations.append(f"**{self.collector.config['models'].get(fastest.model_name, {}).get('description', fastest.model_name)}** 响应最快（{fastest.avg_elapsed_ms:.0f}ms），适合对延迟敏感的场景。")

        # 效率建议
        most_efficient = min(ranking, key=lambda m: m.total_tokens)
        recommendations.append(f"**{self.collector.config['models'].get(most_efficient.model_name, {}).get('description', most_efficient.model_name)}** Token 消耗最少，适合大批量处理场景。")

        return "\n\n".join(recommendations)

    def save_reports(self, output_dir: str = None):
        """保存所有报告"""
        output_dir = Path(output_dir or self.results_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        metrics_list = self.collector.collect_all()

        # 保存各模型报告
        for metrics in metrics_list:
            report = self.generate_model_report(metrics)
            report_file = output_dir / metrics.model_name / "report.md"
            report_file.parent.mkdir(parents=True, exist_ok=True)
            with open(report_file, "w") as f:
                f.write(report)
            print(f"已保存: {report_file}")

        # 保存对比报告
        comparison_report = self.generate_comparison_report(metrics_list)
        comparison_file = output_dir / "comparison_report.md"
        with open(comparison_file, "w") as f:
            f.write(comparison_report)
        print(f"已保存: {comparison_file}")

        return comparison_file


def main():
    import argparse

    parser = argparse.ArgumentParser(description="生成评测报告")
    parser.add_argument("--output", type=str, default="results", help="输出目录")
    parser.add_argument("--config", type=str, default="config/models.yaml", help="配置文件")

    args = parser.parse_args()

    generator = ReportGenerator(args.output, args.config)
    comparison_file = generator.save_reports()

    print(f"\n报告已生成: {comparison_file}")


if __name__ == "__main__":
    main()