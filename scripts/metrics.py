#!/usr/bin/env python3
"""
指标收集模块

功能：
- 汇总各模型评测结果
- 计算综合评分
- 生成对比报告
"""

import json
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass
import yaml


@dataclass
class ModelMetrics:
    """模型指标"""
    model_name: str

    # 准确率指标
    human_eval_passed: int = 0
    human_eval_total: int = 0
    mbpp_passed: int = 0
    mbpp_total: int = 0

    # 速度指标
    avg_elapsed_ms: float = 0
    p95_elapsed_ms: float = 0

    # 效率指标
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    avg_tokens_per_task: float = 0

    # 计算得分
    accuracy_score: float = 0
    speed_score: float = 0
    efficiency_score: float = 0
    total_score: float = 0


class MetricsCollector:
    """指标收集器"""

    def __init__(self, results_dir: str, config_path: str):
        self.results_dir = Path(results_dir)
        self.config = self._load_config(config_path)
        self.weights = self.config.get("weights", {
            "accuracy": 0.50,
            "speed": 0.20,
            "efficiency": 0.15,
            "quality": 0.10,
            "tools": 0.05
        })

    def _load_config(self, config_path: str) -> dict:
        """加载配置"""
        with open(config_path) as f:
            return yaml.safe_load(f)

    def load_results(self, model: str, benchmark: str) -> List[dict]:
        """加载评测结果"""
        result_file = self.results_dir / model / f"{benchmark}_results.json"
        if not result_file.exists():
            return []

        with open(result_file) as f:
            return json.load(f)

    def calculate_percentile(self, values: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def collect_model_metrics(self, model: str) -> ModelMetrics:
        """收集单个模型的指标"""
        metrics = ModelMetrics(model_name=model)

        # HumanEval 指标
        human_eval_results = self.load_results(model, "human_eval")
        if human_eval_results:
            metrics.human_eval_total = len(human_eval_results)
            metrics.human_eval_passed = sum(1 for r in human_eval_results if r.get("passed", False))

        # MBPP 指标
        mbpp_results = self.load_results(model, "mbpp")
        if mbpp_results:
            metrics.mbpp_total = len(mbpp_results)
            metrics.mbpp_passed = sum(1 for r in mbpp_results if r.get("passed", False))

        # 合并所有结果计算速度和效率
        all_results = human_eval_results + mbpp_results

        if all_results:
            elapsed_times = [r.get("elapsed_ms", 0) for r in all_results if r.get("elapsed_ms", 0) > 0]
            if elapsed_times:
                metrics.avg_elapsed_ms = sum(elapsed_times) / len(elapsed_times)
                metrics.p95_elapsed_ms = self.calculate_percentile(elapsed_times, 95)

            metrics.total_input_tokens = sum(r.get("input_tokens", 0) for r in all_results)
            metrics.total_output_tokens = sum(r.get("output_tokens", 0) for r in all_results)
            metrics.total_tokens = sum(r.get("total_tokens", 0) for r in all_results)
            metrics.avg_tokens_per_task = metrics.total_tokens / len(all_results) if all_results else 0

        return metrics

    def calculate_scores(self, metrics_list: List[ModelMetrics]) -> List[ModelMetrics]:
        """计算各模型得分"""
        if not metrics_list:
            return metrics_list

        # 找出最优值用于归一化
        best_accuracy = max(
            (m.human_eval_passed + m.mbpp_passed) / max(m.human_eval_total + m.mbpp_total, 1)
            for m in metrics_list
        )
        best_speed = min(m.avg_elapsed_ms for m in metrics_list if m.avg_elapsed_ms > 0) or 1
        best_efficiency = min(m.total_tokens for m in metrics_list if m.total_tokens > 0) or 1

        for metrics in metrics_list:
            # 准确率得分 (50%)
            total_tasks = metrics.human_eval_total + metrics.mbpp_total
            if total_tasks > 0:
                accuracy_rate = (metrics.human_eval_passed + metrics.mbpp_passed) / total_tasks
                metrics.accuracy_score = (accuracy_rate / best_accuracy) * 50 if best_accuracy > 0 else 0

            # 速度得分 (20%)
            if metrics.avg_elapsed_ms > 0:
                metrics.speed_score = (best_speed / metrics.avg_elapsed_ms) * 20

            # 效率得分 (15%)
            if metrics.total_tokens > 0:
                metrics.efficiency_score = (best_efficiency / metrics.total_tokens) * 15

            # 总分
            metrics.total_score = (
                metrics.accuracy_score +
                metrics.speed_score +
                metrics.efficiency_score
            )

        return metrics_list

    def collect_all(self) -> List[ModelMetrics]:
        """收集所有模型指标"""
        models = list(self.config.get("models", {}).keys())
        metrics_list = []

        for model in models:
            metrics = self.collect_model_metrics(model)
            metrics_list.append(metrics)

        return self.calculate_scores(metrics_list)

    def get_ranking(self, metrics_list: List[ModelMetrics]) -> List[ModelMetrics]:
        """按总分排名"""
        return sorted(metrics_list, key=lambda m: m.total_score, reverse=True)


def main():
    """测试指标收集"""
    collector = MetricsCollector("results", "config/models.yaml")
    metrics_list = collector.collect_all()
    ranking = collector.get_ranking(metrics_list)

    print("\n=== 模型排名 ===")
    for i, m in enumerate(ranking, 1):
        print(f"\n#{i} {m.model_name}")
        print(f"  总分: {m.total_score:.1f}/100")
        print(f"  准确率: {m.accuracy_score:.1f}/50")
        print(f"  速度: {m.speed_score:.1f}/20")
        print(f"  效率: {m.efficiency_score:.1f}/15")
        print(f"  HumanEval: {m.human_eval_passed}/{m.human_eval_total}")
        print(f"  MBPP: {m.mbpp_passed}/{m.mbpp_total}")


if __name__ == "__main__":
    main()