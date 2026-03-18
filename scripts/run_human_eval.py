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
import ssl
import urllib.request
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
        self.api_key = self._get_api_key(model)
        self.results_dir = Path(__file__).parent.parent / "results"
        self.benchmarks_dir = Path(__file__).parent.parent / "benchmarks"

    def _load_config(self, config_path: str) -> dict:
        """加载配置"""
        with open(config_path) as f:
            return yaml.safe_load(f)

    def _get_api_key(self, model: str = None) -> str:
        """获取 API Key"""
        if model and model in self.config.get("models", {}):
            api_key_env = self.config["models"][model].get("api_key_env", "BAILIAN_API_KEY")
        else:
            api_key_env = "BAILIAN_API_KEY"

        # 优先从环境变量
        key = os.getenv(api_key_env)
        if key:
            return key

        # 从密钥文件加载
        if api_key_env == "OPENROUTER_API_KEY":
            key_file = Path.home() / ".secrets" / "openrouter_api_key.txt"
            if key_file.exists():
                return key_file.read_text().strip()

        # 从 zhiwei-bot/.env 加载
        env_paths = [
            Path.home() / "zhiwei-bot" / ".env",
            Path(__file__).parent.parent.parent / "zhiwei-bot" / ".env",
        ]
        for env_path in env_paths:
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(f"{api_key_env}="):
                            return line.split("=", 1)[1]

        raise ValueError(f"未找到 {api_key_env}")

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

    def call_api(self, model: str, prompt: str, max_tokens: int = 4096) -> Tuple[str, dict]:
        """调用 API (支持百炼和 OpenRouter)"""
        model_config = self.config["models"][model]
        endpoint = model_config["endpoint"]
        model_name = model_config["model"]

        # 判断是 OpenRouter 还是百炼
        if endpoint == "openrouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            api_key = self._get_api_key(model)
        else:
            url = f"https://{endpoint}/v1/chat/completions"
            api_key = self.api_key

        system_prompt = """你是一个专业的 Python 程序员。请完成给定的函数，确保：
1. 函数签名与要求完全一致
2. 实现正确的逻辑
3. 只输出代码，不要解释

直接返回完整的函数实现，包括函数签名。"""

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # OpenRouter 需要额外的 headers
        if endpoint == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/terryhillliu-code/zhiwei-bench"
            headers["X-Title"] = "Zhiwei Bench"

        context = ssl.create_default_context()
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        start_time = time.time()
        with urllib.request.urlopen(req, timeout=180, context=context) as resp:
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
            # 调用 API
            response, meta = self.call_api(model, full_prompt)

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