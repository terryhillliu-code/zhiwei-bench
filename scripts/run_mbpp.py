#!/usr/bin/env python3
"""
MBPP 评测脚本

功能：
- 加载 MBPP 数据集
- 调用指定模型生成代码
- 执行测试用例验证
- 记录评测结果
"""

import os
import sys
import json
import time
import argparse
import ssl
import urllib.request
import re
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
except ImportError:
    print("请安装依赖: pip install pyyaml tqdm")
    sys.exit(1)


@dataclass
class MBPPResult:
    """MBPP 评测结果"""
    task_id: int
    model: str
    passed: bool
    elapsed_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    code: str
    error: Optional[str] = None
    timestamp: str = ""


class MBPPEvaluator:
    """MBPP 评测器"""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.api_key = self._get_api_key()
        self.results_dir = Path(__file__).parent.parent / "results"
        self.benchmarks_dir = Path(__file__).parent.parent / "benchmarks"

    def _load_config(self, config_path: str) -> dict:
        """加载配置"""
        with open(config_path) as f:
            return yaml.safe_load(f)

    def _get_api_key(self) -> str:
        """获取 API Key"""
        key = os.getenv("BAILIAN_API_KEY")
        if key:
            return key

        env_paths = [
            Path.home() / "zhiwei-bot" / ".env",
            Path(__file__).parent.parent.parent / "zhiwei-bot" / ".env",
        ]
        for env_path in env_paths:
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("BAILIAN_API_KEY="):
                            return line.split("=", 1)[1]

        raise ValueError("未找到 BAILIAN_API_KEY")

    def load_problems(self, samples: int = None, seed: int = 42) -> List[dict]:
        """加载 MBPP 问题"""
        mbpp_file = self.benchmarks_dir / "mbpp" / "mbpp.jsonl"

        if not mbpp_file.exists():
            raise FileNotFoundError(f"MBPP 数据未找到: {mbpp_file}")

        problems = []
        with open(mbpp_file) as f:
            for line in f:
                if line.strip():
                    problems.append(json.loads(line))

        # 随机抽样
        if samples and samples < len(problems):
            random.seed(seed)
            problems = random.sample(problems, samples)

        return problems

    def call_api(self, model: str, prompt: str, max_tokens: int = 4096) -> Tuple[str, dict]:
        """调用百炼 API"""
        endpoint = self.config["models"][model]["endpoint"]
        model_name = self.config["models"][model]["model"]

        url = f"https://{endpoint}/v1/chat/completions"

        system_prompt = """你是一个专业的 Python 程序员。根据问题描述编写函数。

要求：
1. 函数名与问题描述一致
2. 实现正确的逻辑
3. 只输出代码，不要解释

直接返回完整的函数实现。"""

        payload = json.dumps({
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens
        })

        context = ssl.create_default_context()
        req = urllib.request.Request(
            url,
            data=payload.encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            },
            method='POST'
        )

        start_time = time.time()
        with urllib.request.urlopen(req, timeout=120, context=context) as resp:
            data = json.loads(resp.read().decode())
        elapsed_ms = (time.time() - start_time) * 1000

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return content, {
            "elapsed_ms": elapsed_ms,
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0)
        }

    def extract_code(self, response: str) -> str:
        """从响应中提取代码"""
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
        return response.strip()

    def run_test(self, code: str, test_cases: List[str]) -> Tuple[bool, str]:
        """执行测试用例"""
        try:
            namespace = {}
            exec(code, namespace)

            for test in test_cases:
                try:
                    exec(test, namespace)
                except AssertionError as e:
                    return False, f"测试失败: {test}\n错误: {e}"

            return True, ""
        except Exception as e:
            return False, str(e)

    def evaluate_problem(self, problem: dict, model: str) -> MBPPResult:
        """评测单个问题"""
        task_id = problem.get("task_id", 0)
        prompt_text = problem.get("prompt", problem.get("text", ""))
        test_list = problem.get("test_list", [])

        # 构造完整 prompt
        full_prompt = f"""编写一个 Python 函数解决以下问题：

{prompt_text}

测试用例：
{chr(10).join(test_list)}

要求：
1. 实现正确的功能
2. 通过所有测试用例
3. 只输出函数代码"""

        try:
            response, meta = self.call_api(model, full_prompt)
            code = self.extract_code(response)
            passed, error = self.run_test(code, test_list)

            return MBPPResult(
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
            return MBPPResult(
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

    def evaluate_model(self, model: str, samples: int = None) -> List[MBPPResult]:
        """评测指定模型"""
        problems = self.load_problems(samples)
        results = []

        print(f"\n评测模型: {model}")
        print(f"问题数量: {len(problems)}")

        for problem in tqdm(problems, desc=f"评测 {model}"):
            result = self.evaluate_problem(problem, model)
            results.append(result)

            if len(results) % 10 == 0:
                self.save_results(results, model)

        return results

    def save_results(self, results: List[MBPPResult], model: str):
        """保存结果"""
        output_dir = self.results_dir / model
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "mbpp_results.json"
        with open(output_file, "w") as f:
            json.dump([asdict(r) for r in results], f, indent=2, ensure_ascii=False)

    def print_summary(self, results: List[MBPPResult]):
        """打印摘要"""
        total = len(results)
        passed = sum(1 for r in results if r.passed)

        avg_elapsed = sum(r.elapsed_ms for r in results) / total if total > 0 else 0
        total_tokens = sum(r.total_tokens for r in results)

        print(f"\n=== MBPP 评测摘要 ===")
        print(f"总题数: {total}")
        print(f"通过数: {passed}")
        print(f"通过率: {passed/total*100:.1f}%")
        print(f"平均耗时: {avg_elapsed:.0f}ms")
        print(f"总 Token: {total_tokens}")


def main():
    parser = argparse.ArgumentParser(description="MBPP 评测")
    parser.add_argument("--model", type=str, help="模型名称")
    parser.add_argument("--all", action="store_true", help="评测所有模型")
    parser.add_argument("--samples", type=int, default=50, help="抽样数量")
    parser.add_argument("--config", type=str, default="config/models.yaml", help="配置文件路径")

    args = parser.parse_args()

    evaluator = MBPPEvaluator(args.config)

    if args.all:
        models = list(evaluator.config["models"].keys())
    elif args.model:
        models = [args.model]
    else:
        print("请指定 --model 或 --all")
        return

    for model in models:
        results = evaluator.evaluate_model(model, args.samples)
        evaluator.save_results(results, model)
        evaluator.print_summary(results)

    print("\n评测完成！")


if __name__ == "__main__":
    main()