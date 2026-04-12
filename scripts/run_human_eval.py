#!/usr/bin/env python3
"""
HumanEval 评测脚本

功能：
- 加载 HumanEval 数据集
- 调用指定模型生成代码
- 执行测试用例验证
- 记录评测结果
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import random

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import yaml
    from tqdm import tqdm
    from api_client import APIClient
except ImportError:
    print("请安装依赖: pip install pyyaml tqdm")
    sys.exit(1)


@dataclass
class EvaluationResult:
    """评测结果"""
    task_id: str
    model: str
    passed: bool
    elapsed_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    code: str
    error: Optional[str] = None
    timestamp: str = ""


class HumanEvalEvaluator:
    """HumanEval 评测器"""

    def __init__(self, config_path: str, model: str = None):
        self.config = self._load_config(config_path)
        self.current_model = model
        self.api_client = APIClient(config_path)
        self.results_dir = Path(__file__).parent.parent / "results"
        self.benchmarks_dir = Path(__file__).parent.parent / "benchmarks"

    def _load_config(self, config_path: str) -> dict:
        """加载配置"""
        with open(config_path) as f:
            return yaml.safe_load(f)

    def load_problems(self, samples: int = None, seed: int = 42) -> List[dict]:
        """加载 HumanEval 问题"""
        human_eval_dir = self.benchmarks_dir / "human-eval" / "data"
        problems_file = human_eval_dir / "HumanEval.jsonl"

        if not problems_file.exists():
            raise FileNotFoundError(f"HumanEval 数据未找到: {problems_file}")

        problems = []
        with open(problems_file) as f:
            for line in f:
                if line.strip():
                    problems.append(json.loads(line))

        # 随机抽样
        if samples and samples < len(problems):
            random.seed(seed)
            problems = random.sample(problems, samples)

        return problems

    def extract_code(self, response: str) -> str:
        """从响应中提取代码"""
        # 尝试提取代码块
        if "```python" in response:
            start = response.find("```python") + 9
            end = response.find("```", start)
            if end > start:
                return response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                return response[start:end].strip()

        # 如果没有代码块，直接返回
        return response.strip()

    def run_test(self, code: str, test_code: str) -> Tuple[bool, str]:
        """执行测试"""
        try:
            # 合并代码和测试
            full_code = code + "\n\n" + test_code

            # 创建临时命名空间
            namespace = {}
            exec(full_code, namespace)
            return True, ""
        except Exception as e:
            return False, str(e)

    def evaluate_problem(self, problem: dict, model: str) -> EvaluationResult:
        """评测单个问题"""
        task_id = problem["task_id"]
        prompt = problem["prompt"]
        test = problem["test"]

        # 构造完整 prompt
        full_prompt = f"""完成以下 Python 函数：

{prompt}

要求：
1. 保持函数签名不变
2. 实现正确的功能
3. 只输出函数代码，不要额外解释"""

        try:
            # 调用 API（使用统一客户端）
            system_prompt = """你是一个专业的 Python 程序员。请完成给定的函数，确保：
1. 函数签名与要求完全一致
2. 实现正确的逻辑
3. 只输出代码，不要解释

直接返回完整的函数实现，包括函数签名。"""
            response, meta = self.api_client.call(model, full_prompt, max_tokens=4096,
                                                   system_prompt=system_prompt)

            # 提取代码
            code = self.extract_code(response)

            # 执行测试
            passed, error = self.run_test(code, test)

            return EvaluationResult(
                task_id=task_id,
                model=model,
                passed=passed,
                elapsed_ms=meta["elapsed_ms"],
                input_tokens=meta["input_tokens"],
                output_tokens=meta["output_tokens"],
                total_tokens=meta["total_tokens"],
                code=code,
                error=error if not passed else None,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            return EvaluationResult(
                task_id=task_id,
                model=model,
                passed=False,
                elapsed_ms=0,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                code="",
                error=f"API 调用失败: {str(e)}",
                timestamp=datetime.now().isoformat()
            )

    def evaluate_model(self, model: str, samples: int = None) -> List[EvaluationResult]:
        """评测指定模型"""
        problems = self.load_problems(samples)
        results = []

        print(f"\n评测模型: {model}")
        print(f"问题数量: {len(problems)}")

        for problem in tqdm(problems, desc=f"评测 {model}"):
            result = self.evaluate_problem(problem, model)
            results.append(result)

            # 每 10 题保存一次
            if len(results) % 10 == 0:
                self.save_results(results, model)

        return results

    def save_results(self, results: List[EvaluationResult], model: str):
        """保存结果"""
        output_dir = self.results_dir / model
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "human_eval_results.json"
        with open(output_file, "w") as f:
            json.dump([asdict(r) for r in results], f, indent=2, ensure_ascii=False)

    def print_summary(self, results: List[EvaluationResult]):
        """打印摘要"""
        total = len(results)
        passed = sum(1 for r in results if r.passed)

        avg_elapsed = sum(r.elapsed_ms for r in results) / total if total > 0 else 0
        total_tokens = sum(r.total_tokens for r in results)

        print(f"\n=== 评测摘要 ===")
        print(f"总题数: {total}")
        print(f"通过数: {passed}")
        print(f"通过率: {passed/total*100:.1f}%")
        print(f"平均耗时: {avg_elapsed:.0f}ms")
        print(f"总 Token: {total_tokens}")


def main():
    parser = argparse.ArgumentParser(description="HumanEval 评测")
    parser.add_argument("--model", type=str, help="模型名称 (qwen3.5-plus/glm-5/minimax-m2.5)")
    parser.add_argument("--all", action="store_true", help="评测所有模型")
    parser.add_argument("--samples", type=int, default=50, help="抽样数量")
    parser.add_argument("--config", type=str, default="config/models.yaml", help="配置文件路径")

    args = parser.parse_args()

    # 初始化评测器
    evaluator = HumanEvalEvaluator(args.config)

    # 确定要评测的模型
    if args.all:
        models = list(evaluator.config["models"].keys())
    elif args.model:
        models = [args.model]
    else:
        print("请指定 --model 或 --all")
        return

    # 评测每个模型
    for model in models:
        results = evaluator.evaluate_model(model, args.samples)
        evaluator.save_results(results, model)
        evaluator.print_summary(results)

    print("\n评测完成！")


if __name__ == "__main__":
    main()