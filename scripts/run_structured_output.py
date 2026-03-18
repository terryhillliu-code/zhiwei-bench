#!/usr/bin/env python3
"""
结构化输出能力评测脚本

评测维度：
1. JSON 格式输出 - 有效性、复杂嵌套、特殊字符
2. JSON Schema 遵循 - 类型、必填字段、枚举值
3. 函数调用模拟 - 函数名、参数类型、参数值
4. 格式控制 - Markdown 表格、代码块、列表

评分：
- JSON 格式：20 分
- Schema 遵循：30 分
- 函数调用：30 分
- 格式控制：20 分
总分：100 分
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
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import random

try:
    import yaml
    from tqdm import tqdm
except ImportError:
    print("请安装依赖: pip install pyyaml tqdm")
    sys.exit(1)


@dataclass
class StructuredOutputResult:
    """结构化输出评测结果"""
    task_id: str
    category: str  # json_format / schema_adherence / function_calling / format_control
    model: str
    passed: bool
    score: float  # 0-1
    elapsed_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    output: str
    parsed_result: Optional[dict] = None
    error: Optional[str] = None
    timestamp: str = ""


# ==================== 测试用例定义 ====================

JSON_FORMAT_TESTS = [
    {
        "id": "json_simple",
        "description": "简单 JSON 对象",
        "prompt": "请输出一个包含 name, age, email 字段的 JSON 对象，name 是字符串，age 是数字，email 是字符串。",
        "validation": lambda x: isinstance(x, dict) and "name" in x and "age" in x and "email" in x
    },
    {
        "id": "json_nested",
        "description": "嵌套 JSON 对象",
        "prompt": "请输出一个用户信息 JSON 对象，包含 name, address 字段。address 是一个嵌套对象，包含 city, street, zipcode。",
        "validation": lambda x: (
            isinstance(x, dict) and
            "name" in x and
            "address" in x and
            isinstance(x["address"], dict) and
            all(k in x["address"] for k in ["city", "street", "zipcode"])
        )
    },
    {
        "id": "json_array",
        "description": "JSON 数组",
        "prompt": "请输出一个包含 3 个用户对象的 JSON 数组，每个用户对象包含 id(数字) 和 name(字符串)。",
        "validation": lambda x: (
            isinstance(x, list) and
            len(x) >= 3 and
            all(isinstance(item, dict) and "id" in item and "name" in item for item in x)
        )
    },
    {
        "id": "json_special_chars",
        "description": "特殊字符处理",
        "prompt": '请输出一个 JSON 对象，包含一个 message 字段，值是：He said "Hello" and left\\nNew line here.',
        "validation": lambda x: isinstance(x, dict) and "message" in x
    },
    {
        "id": "json_numbers",
        "description": "数字类型",
        "prompt": "请输出一个 JSON 对象，包含 integer(整数), float(小数), negative(负数), scientific(科学计数法表示的数字) 四个字段。",
        "validation": lambda x: (
            isinstance(x, dict) and
            all(k in x for k in ["integer", "float", "negative", "scientific"]) and
            all(isinstance(x[k], (int, float)) for k in ["integer", "float", "negative", "scientific"])
        )
    }
]

SCHEMA_ADHERENCE_TESTS = [
    {
        "id": "schema_required",
        "description": "必填字段",
        "schema": {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "optional": {"type": "string"}
            }
        },
        "prompt": "请严格按照以下 JSON Schema 输出一个对象：\n{schema}\n\n只输出 JSON，不要解释。",
    },
    {
        "id": "schema_types",
        "description": "类型约束",
        "schema": {
            "type": "object",
            "properties": {
                "string_field": {"type": "string"},
                "number_field": {"type": "number"},
                "boolean_field": {"type": "boolean"},
                "array_field": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["string_field", "number_field", "boolean_field", "array_field"]
        },
        "prompt": "请严格按照以下 JSON Schema 输出一个对象：\n{schema}\n\n只输出 JSON。",
    },
    {
        "id": "schema_enum",
        "description": "枚举值约束",
        "schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["active", "inactive", "pending"]},
                "priority": {"type": "integer", "enum": [1, 2, 3, 4, 5]}
            },
            "required": ["status", "priority"]
        },
        "prompt": "请严格按照以下 JSON Schema 输出一个对象：\n{schema}\n\n只输出 JSON。",
    },
    {
        "id": "schema_nested",
        "description": "嵌套对象约束",
        "schema": {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "contacts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "value": {"type": "string"}
                                },
                                "required": ["type", "value"]
                            }
                        }
                    },
                    "required": ["name", "contacts"]
                }
            },
            "required": ["user"]
        },
        "prompt": "请严格按照以下 JSON Schema 输出一个对象：\n{schema}\n\n只输出 JSON。",
    },
    {
        "id": "schema_array_constraints",
        "description": "数组约束",
        "schema": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 5
                },
                "scores": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3
                }
            },
            "required": ["tags", "scores"]
        },
        "prompt": "请严格按照以下 JSON Schema 输出一个对象：\n{schema}\n\n只输出 JSON。",
    }
]

FUNCTION_CALLING_TESTS = [
    {
        "id": "func_simple",
        "description": "简单函数调用",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "description": "温度单位"}
                },
                "required": ["city"]
            }
        },
        "prompt": "用户问：北京今天天气怎么样？\n\n请调用 get_weather 函数来回答。输出 JSON 格式的函数调用。",
    },
    {
        "id": "func_multiple_params",
        "description": "多参数函数",
        "function": {
            "name": "search_products",
            "description": "搜索商品",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "category": {"type": "string", "description": "商品类别"},
                    "min_price": {"type": "number", "description": "最低价格"},
                    "max_price": {"type": "number", "description": "最高价格"},
                    "sort_by": {"type": "string", "enum": ["price", "rating", "sales"], "description": "排序方式"}
                },
                "required": ["keyword"]
            }
        },
        "prompt": "用户问：我想找一些价格在100到500元之间的手机配件，按销量排序。\n\n请调用 search_products 函数。输出 JSON 格式。",
    },
    {
        "id": "func_nested_params",
        "description": "嵌套参数",
        "function": {
            "name": "create_order",
            "description": "创建订单",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "phone": {"type": "string"},
                            "address": {"type": "string"}
                        },
                        "required": ["name", "phone", "address"]
                    },
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "string"},
                                "quantity": {"type": "integer"}
                            },
                            "required": ["product_id", "quantity"]
                        }
                    }
                },
                "required": ["customer", "items"]
            }
        },
        "prompt": "用户说：我要下单，我叫张三，电话13800138000，地址是北京市朝阳区xxx，买2个商品A和1个商品B。\n\n请调用 create_order 函数。输出 JSON 格式。",
    },
    {
        "id": "func_array_param",
        "description": "数组参数",
        "function": {
            "name": "send_notification",
            "description": "发送通知",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "接收者列表"
                    },
                    "message": {"type": "string", "description": "消息内容"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "优先级"}
                },
                "required": ["recipients", "message"]
            }
        },
        "prompt": "用户说：给张三、李四、王五发送一条高优先级消息，内容是「明天开会」。\n\n请调用 send_notification 函数。输出 JSON 格式。",
    },
    {
        "id": "func_no_params",
        "description": "无参数函数",
        "function": {
            "name": "get_current_time",
            "description": "获取当前时间",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        "prompt": "用户问：现在几点了？\n\n请调用 get_current_time 函数。输出 JSON 格式。",
    }
]

FORMAT_CONTROL_TESTS = [
    {
        "id": "markdown_table",
        "description": "Markdown 表格",
        "prompt": "请用 Markdown 表格格式输出 3 种编程语言的名称、创建年份和主要用途。",
        "validation": lambda x: "|" in x and "---" in x and x.count("|") >= 6
    },
    {
        "id": "markdown_code_block",
        "description": "代码块",
        "prompt": "请用 Python 代码块输出一个计算斐波那契数列的函数。",
        "validation": lambda x: "```python" in x.lower() or "```" in x
    },
    {
        "id": "markdown_list",
        "description": "列表结构",
        "prompt": "请用 Markdown 无序列表列出 5 个编程最佳实践。",
        "validation": lambda x: x.count("- ") >= 5 or x.count("* ") >= 5 or x.count("+ ") >= 5
    },
    {
        "id": "markdown_heading",
        "description": "标题层级",
        "prompt": "请写一篇关于 AI 的简短文章，包含一级标题、二级标题和三级标题。",
        "validation": lambda x: x.count("#") >= 3
    },
    {
        "id": "mixed_format",
        "description": "混合格式",
        "prompt": "请输出一段内容，包含：1) 一个二级标题 2) 一个 Markdown 表格（2行数据）3) 一个代码块",
        "validation": lambda x: "##" in x and "|" in x and "```" in x
    }
]


class StructuredOutputEvaluator:
    """结构化输出评测器"""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.api_key = self._get_api_key()
        self.results_dir = Path(__file__).parent.parent / "results"

    def _load_config(self, config_path: str) -> dict:
        with open(config_path) as f:
            return yaml.safe_load(f)

    def _get_api_key(self) -> str:
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

    def call_api(self, model: str, prompt: str, max_tokens: int = 2048) -> Tuple[str, dict]:
        """调用 API"""
        endpoint = self.config["models"][model]["endpoint"]
        model_name = self.config["models"][model]["model"]

        url = f"https://{endpoint}/v1/chat/completions"

        system_prompt = """你是一个精确的结构化输出专家。请严格按照用户要求的格式输出，不要添加额外解释。"""

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
        with urllib.request.urlopen(req, timeout=60, context=context) as resp:
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

    def extract_json(self, text: str) -> Tuple[Optional[Any], Optional[str]]:
        """从文本中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text), None
        except:
            pass

        # 尝试提取代码块中的 JSON
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group(1)), None
                except:
                    continue

        # 尝试找到 JSON 对象/数组
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start = text.find(start_char)
            if start != -1:
                depth = 0
                for i, char in enumerate(text[start:], start):
                    if char == start_char:
                        depth += 1
                    elif char == end_char:
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(text[start:i+1]), None
                            except:
                                break

        return None, "无法解析 JSON"

    def validate_json_schema(self, data: Any, schema: dict) -> Tuple[bool, List[str]]:
        """验证 JSON Schema"""
        errors = []

        def validate(value, schm, path=""):
            # 类型检查
            if "type" in schm:
                expected_type = schm["type"]
                if expected_type == "object" and not isinstance(value, dict):
                    errors.append(f"{path}: 期望 object，实际 {type(value).__name__}")
                elif expected_type == "array" and not isinstance(value, list):
                    errors.append(f"{path}: 期望 array，实际 {type(value).__name__}")
                elif expected_type == "string" and not isinstance(value, str):
                    errors.append(f"{path}: 期望 string，实际 {type(value).__name__}")
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"{path}: 期望 number，实际 {type(value).__name__}")
                elif expected_type == "integer" and not isinstance(value, int):
                    errors.append(f"{path}: 期望 integer，实际 {type(value).__name__}")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"{path}: 期望 boolean，实际 {type(value).__name__}")

            # 枚举检查
            if "enum" in schm and value not in schm["enum"]:
                errors.append(f"{path}: 值 {value} 不在枚举 {schm['enum']} 中")

            # 必填字段
            if isinstance(value, dict) and "required" in schm:
                for req in schm["required"]:
                    if req not in value:
                        errors.append(f"{path}: 缺少必填字段 {req}")

            # 属性检查
            if isinstance(value, dict) and "properties" in schm:
                for key, val in value.items():
                    if key in schm["properties"]:
                        validate(val, schm["properties"][key], f"{path}.{key}")

            # 数组元素检查
            if isinstance(value, list) and "items" in schm:
                for i, item in enumerate(value):
                    validate(item, schm["items"], f"{path}[{i}]")

            # 数组长度检查
            if isinstance(value, list):
                if "minItems" in schm and len(value) < schm["minItems"]:
                    errors.append(f"{path}: 数组长度 {len(value)} 小于最小值 {schm['minItems']}")
                if "maxItems" in schm and len(value) > schm["maxItems"]:
                    errors.append(f"{path}: 数组长度 {len(value)} 大于最大值 {schm['maxItems']}")

        validate(data, schema)
        return len(errors) == 0, errors

    def evaluate_json_format(self, model: str) -> List[StructuredOutputResult]:
        """评测 JSON 格式输出"""
        results = []

        for test in tqdm(JSON_FORMAT_TESTS, desc=f"JSON格式评测-{model}"):
            try:
                response, meta = self.call_api(model, test["prompt"])
                parsed, error = self.extract_json(response)

                if parsed is not None and test["validation"](parsed):
                    passed = True
                    score = 1.0
                    error = None
                else:
                    passed = False
                    score = 0.0
                    if error is None:
                        error = "验证失败"

                results.append(StructuredOutputResult(
                    task_id=test["id"],
                    category="json_format",
                    model=model,
                    passed=passed,
                    score=score,
                    elapsed_ms=meta["elapsed_ms"],
                    input_tokens=meta["input_tokens"],
                    output_tokens=meta["output_tokens"],
                    total_tokens=meta["total_tokens"],
                    output=response,
                    parsed_result=parsed,
                    error=error,
                    timestamp=datetime.now().isoformat()
                ))
            except Exception as e:
                results.append(StructuredOutputResult(
                    task_id=test["id"],
                    category="json_format",
                    model=model,
                    passed=False,
                    score=0.0,
                    elapsed_ms=0,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    output="",
                    error=str(e),
                    timestamp=datetime.now().isoformat()
                ))

        return results

    def evaluate_schema_adherence(self, model: str) -> List[StructuredOutputResult]:
        """评测 Schema 遵循"""
        results = []

        for test in tqdm(SCHEMA_ADHERENCE_TESTS, desc=f"Schema评测-{model}"):
            try:
                prompt = test["prompt"].format(schema=json.dumps(test["schema"], indent=2, ensure_ascii=False))
                response, meta = self.call_api(model, prompt, max_tokens=4096)
                parsed, error = self.extract_json(response)

                if parsed is not None:
                    valid, errors = self.validate_json_schema(parsed, test["schema"])
                    if valid:
                        passed = True
                        score = 1.0
                        error = None
                    else:
                        passed = False
                        score = 0.5 if len(errors) <= 2 else 0.0
                        error = "; ".join(errors[:3])
                else:
                    passed = False
                    score = 0.0

                results.append(StructuredOutputResult(
                    task_id=test["id"],
                    category="schema_adherence",
                    model=model,
                    passed=passed,
                    score=score,
                    elapsed_ms=meta["elapsed_ms"],
                    input_tokens=meta["input_tokens"],
                    output_tokens=meta["output_tokens"],
                    total_tokens=meta["total_tokens"],
                    output=response,
                    parsed_result=parsed,
                    error=error,
                    timestamp=datetime.now().isoformat()
                ))
            except Exception as e:
                results.append(StructuredOutputResult(
                    task_id=test["id"],
                    category="schema_adherence",
                    model=model,
                    passed=False,
                    score=0.0,
                    elapsed_ms=0,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    output="",
                    error=str(e),
                    timestamp=datetime.now().isoformat()
                ))

        return results

    def evaluate_function_calling(self, model: str) -> List[StructuredOutputResult]:
        """评测函数调用"""
        results = []

        for test in tqdm(FUNCTION_CALLING_TESTS, desc=f"函数调用评测-{model}"):
            try:
                # 构造函数调用 prompt
                prompt = f"""可用函数：
{test['function']['name']}: {test['function']['description']}
参数: {json.dumps(test['function']['parameters'], indent=2, ensure_ascii=False)}

{test['prompt']}

输出格式：
{{"function": "函数名", "arguments": {{参数对象}}}}"""

                response, meta = self.call_api(model, prompt)
                parsed, error = self.extract_json(response)

                if parsed is not None:
                    # 验证函数调用格式
                    func_name = parsed.get("function", "")
                    arguments = parsed.get("arguments", {})

                    if func_name == test["function"]["name"]:
                        # 验证参数
                        valid, errors = self.validate_json_schema(
                            arguments,
                            test["function"]["parameters"]
                        )
                        if valid:
                            passed = True
                            score = 1.0
                        else:
                            passed = True  # 函数名正确也算部分通过
                            score = 0.7
                            error = "; ".join(errors[:2])
                    else:
                        passed = False
                        score = 0.3
                        error = f"函数名错误: 期望 {test['function']['name']}, 实际 {func_name}"
                else:
                    passed = False
                    score = 0.0

                results.append(StructuredOutputResult(
                    task_id=test["id"],
                    category="function_calling",
                    model=model,
                    passed=passed,
                    score=score,
                    elapsed_ms=meta["elapsed_ms"],
                    input_tokens=meta["input_tokens"],
                    output_tokens=meta["output_tokens"],
                    total_tokens=meta["total_tokens"],
                    output=response,
                    parsed_result=parsed,
                    error=error,
                    timestamp=datetime.now().isoformat()
                ))
            except Exception as e:
                results.append(StructuredOutputResult(
                    task_id=test["id"],
                    category="function_calling",
                    model=model,
                    passed=False,
                    score=0.0,
                    elapsed_ms=0,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    output="",
                    error=str(e),
                    timestamp=datetime.now().isoformat()
                ))

        return results

    def evaluate_format_control(self, model: str) -> List[StructuredOutputResult]:
        """评测格式控制"""
        results = []

        for test in tqdm(FORMAT_CONTROL_TESTS, desc=f"格式控制评测-{model}"):
            try:
                response, meta = self.call_api(model, test["prompt"])

                if test["validation"](response):
                    passed = True
                    score = 1.0
                    error = None
                else:
                    passed = False
                    score = 0.0
                    error = "格式验证失败"

                results.append(StructuredOutputResult(
                    task_id=test["id"],
                    category="format_control",
                    model=model,
                    passed=passed,
                    score=score,
                    elapsed_ms=meta["elapsed_ms"],
                    input_tokens=meta["input_tokens"],
                    output_tokens=meta["output_tokens"],
                    total_tokens=meta["total_tokens"],
                    output=response[:500],  # 截断输出
                    error=error,
                    timestamp=datetime.now().isoformat()
                ))
            except Exception as e:
                results.append(StructuredOutputResult(
                    task_id=test["id"],
                    category="format_control",
                    model=model,
                    passed=False,
                    score=0.0,
                    elapsed_ms=0,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    output="",
                    error=str(e),
                    timestamp=datetime.now().isoformat()
                ))

        return results

    def evaluate_model(self, model: str) -> List[StructuredOutputResult]:
        """评测单个模型"""
        all_results = []

        print(f"\n评测模型: {model}")
        print("=" * 50)

        # JSON 格式评测
        print("\n[1/4] JSON 格式输出评测...")
        results = self.evaluate_json_format(model)
        all_results.extend(results)
        passed = sum(1 for r in results if r.passed)
        print(f"  通过: {passed}/{len(results)}")

        # Schema 遵循评测
        print("\n[2/4] JSON Schema 遵循评测...")
        results = self.evaluate_schema_adherence(model)
        all_results.extend(results)
        passed = sum(1 for r in results if r.passed)
        print(f"  通过: {passed}/{len(results)}")

        # 函数调用评测
        print("\n[3/4] 函数调用评测...")
        results = self.evaluate_function_calling(model)
        all_results.extend(results)
        passed = sum(1 for r in results if r.passed)
        print(f"  通过: {passed}/{len(results)}")

        # 格式控制评测
        print("\n[4/4] 格式控制评测...")
        results = self.evaluate_format_control(model)
        all_results.extend(results)
        passed = sum(1 for r in results if r.passed)
        print(f"  通过: {passed}/{len(results)}")

        return all_results

    def save_results(self, results: List[StructuredOutputResult], model: str):
        """保存结果"""
        output_dir = self.results_dir / model
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "structured_output_results.json"
        with open(output_file, "w") as f:
            json.dump([asdict(r) for r in results], f, indent=2, ensure_ascii=False)

    def print_summary(self, results: List[StructuredOutputResult]):
        """打印摘要"""
        categories = ["json_format", "schema_adherence", "function_calling", "format_control"]
        weights = [20, 30, 30, 20]

        print("\n" + "=" * 50)
        print("评测摘要")
        print("=" * 50)

        total_score = 0
        for cat, weight in zip(categories, weights):
            cat_results = [r for r in results if r.category == cat]
            if cat_results:
                passed = sum(1 for r in cat_results if r.passed)
                avg_score = sum(r.score for r in cat_results) / len(cat_results)
                cat_score = avg_score * weight
                total_score += cat_score
                print(f"\n{cat}:")
                print(f"  通过: {passed}/{len(cat_results)}")
                print(f"  得分: {cat_score:.1f}/{weight}")

        print(f"\n总分: {total_score:.1f}/100")


def main():
    parser = argparse.ArgumentParser(description="结构化输出能力评测")
    parser.add_argument("--model", type=str, help="模型名称")
    parser.add_argument("--all", action="store_true", help="评测所有模型")
    parser.add_argument("--config", type=str, default="config/models.yaml", help="配置文件")

    args = parser.parse_args()

    evaluator = StructuredOutputEvaluator(args.config)

    if args.all:
        models = list(evaluator.config["models"].keys())
    elif args.model:
        models = [args.model]
    else:
        print("请指定 --model 或 --all")
        return

    for model in models:
        results = evaluator.evaluate_model(model)
        evaluator.save_results(results, model)
        evaluator.print_summary(results)

    print("\n评测完成！")


if __name__ == "__main__":
    main()