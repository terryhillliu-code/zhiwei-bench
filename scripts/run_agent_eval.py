#!/usr/bin/env python3
"""
Agent 场景评测脚本

评估 LLM 的 Agent 编程能力：
- 项目理解：能否正确分析项目结构
- 任务分解：能否合理规划任务步骤
- 代码生成：能否生成正确的代码
- 错误处理：能否处理异常情况

用法:
    python3 scripts/run_agent_eval.py --model volc-doubao-pro
    python3 scripts/run_agent_eval.py --model qwen3.6-plus
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple
import yaml

from api_client import APIClient


class AgentEvaluator:
    """Agent 场景评测器"""

    def __init__(self, config_path: str = None):
        self.benchmarks_dir = Path(__file__).parent.parent / "benchmarks"
        self.config_dir = Path(__file__).parent.parent / "config"
        self.results_dir = Path(__file__).parent.parent / "results"
        self.api_client = APIClient(config_path)

        # 加载场景
        scenarios_file = self.config_dir / "agent_scenarios.yaml"
        if scenarios_file.exists():
            self.scenarios = yaml.safe_load(open(scenarios_file))
        else:
            self.scenarios = {"scenarios": {}}

    def evaluate_planning(self, response: str, scenario: dict) -> dict:
        """评估任务规划能力"""
        scores = {}

        # 检查是否包含步骤规划
        has_steps = False
        step_keywords = ["步骤", "step", "首先", "然后", "最后", "1.", "2.", "3."]
        for kw in step_keywords:
            if kw in response.lower():
                has_steps = True
                break

        scores["has_steps"] = 10 if has_steps else 0

        # 检查是否提到文件名
        files_mentioned = []
        if "files_to_modify" in scenario.get("evaluation", {}):
            expected_files = scenario.get("expected_files", [])
            for f in expected_files:
                if f in response:
                    files_mentioned.append(f)

        scores["file_identification"] = len(files_mentioned) * 5

        # 检查是否包含代码
        has_code = "```python" in response or "```" in response
        scores["has_code"] = 10 if has_code else 0

        return scores

    def evaluate_scenario(self, model: str, scenario_id: str) -> dict:
        """评测单个场景"""
        scenario = self.scenarios["scenarios"][scenario_id]

        # 构造评测 prompt
        prompt = f"""作为一个软件工程师，请完成以下任务：

{scenario['task_prompt']}

请详细说明：
1. 你的分析和理解
2. 你的实现计划（分步骤）
3. 你的代码实现（用代码块包裹）
4. 如何验证你的实现正确

请尽可能详细地回答，展示你的思考过程。"""

        # 调用 API
        system_prompt = "你是一个专业的软件工程师，擅长分析和实现复杂的编程任务。请详细展示你的思考过程和代码实现。"
        response, meta = self.api_client.call(model, prompt, max_tokens=8192,
                                               system_prompt=system_prompt)

        # 评估
        planning_scores = self.evaluate_planning(response, scenario)

        # 计算总分
        total_score = sum(planning_scores.values())

        return {
            "scenario_id": scenario_id,
            "scenario_name": scenario["name"],
            "model": model,
            "response": response,
            "elapsed_ms": meta["elapsed_ms"],
            "input_tokens": meta["input_tokens"],
            "output_tokens": meta["output_tokens"],
            "total_tokens": meta["total_tokens"],
            "planning_scores": planning_scores,
            "total_score": total_score,
            "timestamp": datetime.now().isoformat()
        }

    def run_evaluation(self, model: str) -> List[dict]:
        """运行完整评测"""
        results = []

        print(f"\n评测模型: {model}")
        print("=" * 50)

        scenario_ids = list(self.scenarios["scenarios"].keys())

        for i, scenario_id in enumerate(scenario_ids, 1):
            print(f"\n[{i}/{len(scenario_ids)}] 场景: {scenario_id}")

            try:
                result = self.evaluate_scenario(model, scenario_id)
                results.append(result)

                print(f"  耗时: {result['elapsed_ms']:.0f}ms")
                print(f"  Token: {result['total_tokens']}")
                print(f"  规划得分: {result['total_score']}/30")

            except Exception as e:
                print(f"  错误: {e}")
                results.append({
                    "scenario_id": scenario_id,
                    "model": model,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })

        return results

    def save_results(self, model: str, results: List[dict]):
        """保存结果"""
        model_dir = self.results_dir / model
        model_dir.mkdir(parents=True, exist_ok=True)

        output_file = model_dir / "agent_eval_results.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n结果保存至: {output_file}")

    def generate_report(self, results: List[dict]) -> dict:
        """生成评测摘要"""
        total_score = sum(r.get("total_score", 0) for r in results if "total_score" in r)
        avg_time = sum(r.get("elapsed_ms", 0) for r in results if "elapsed_ms" in r) / len(results)
        total_tokens = sum(r.get("total_tokens", 0) for r in results if "total_tokens" in r)

        return {
            "total_scenarios": len(results),
            "total_score": total_score,
            "avg_time_ms": avg_time,
            "total_tokens": total_tokens,
            "scenarios_passed": len([r for r in results if "total_score" in r and r["total_score"] >= 20])
        }


def main():
    parser = argparse.ArgumentParser(description="Agent 场景评测")
    parser.add_argument("--model", required=True, help="模型名称")
    parser.add_argument("--config", help="配置文件路径")

    args = parser.parse_args()

    evaluator = AgentEvaluator(args.config)

    # 运行评测
    results = evaluator.run_evaluation(args.model)

    # 保存结果
    evaluator.save_results(args.model, results)

    # 生成摘要
    summary = evaluator.generate_report(results)

    print("\n" + "=" * 50)
    print("评测摘要")
    print("=" * 50)
    print(f"场景数: {summary['total_scenarios']}")
    print(f"总分: {summary['total_score']}")
    print(f"平均耗时: {summary['avg_time_ms']:.0f}ms")
    print(f"总Token: {summary['total_tokens']}")
    print(f"通过场景: {summary['scenarios_passed']}/{summary['total_scenarios']}")

    print("\n评测完成！")


if __name__ == "__main__":
    main()