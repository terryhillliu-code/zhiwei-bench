#!/usr/bin/env python3
"""
Hunter Alpha 模型调用脚本
通过 OpenRouter API 调用 1T 参数大模型

用法:
    python3 call_hunter.py "你的问题"
    python3 call_hunter.py --test
    python3 call_hunter.py --structured
"""

import os
import sys
import json
import requests
from pathlib import Path

# 配置
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
API_KEY_FILE = Path.home() / ".secrets" / "openrouter_api_key.txt"
MODEL = "openrouter/hunter-alpha"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

def get_api_key():
    """获取 API Key"""
    if OPENROUTER_API_KEY:
        return OPENROUTER_API_KEY
    if API_KEY_FILE.exists():
        return API_KEY_FILE.read_text().strip()
    return None

def call_hunter(prompt: str, system: str = None, max_tokens: int = 4096, temperature: float = 0.7) -> dict:
    """
    调用 Hunter Alpha 模型

    Args:
        prompt: 用户输入
        system: 系统提示词
        max_tokens: 最大输出 tokens
        temperature: 温度参数

    Returns:
        dict: 包含 response, tokens, elapsed_ms
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("未找到 OpenRouter API Key，请运行:\n  echo '你的密钥' > ~/.secrets/openrouter_api_key.txt")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/terryhillliu-code/zhiwei-bench",
        "X-Title": "Zhiwei Bench"
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    import time
    start = time.time()

    response = requests.post(API_URL, headers=headers, json=payload, timeout=300)

    elapsed_ms = (time.time() - start) * 1000

    if response.status_code != 200:
        raise Exception(f"API 错误: {response.status_code} - {response.text}")

    data = response.json()

    return {
        "response": data["choices"][0]["message"]["content"],
        "tokens": {
            "prompt": data.get("usage", {}).get("prompt_tokens", 0),
            "completion": data.get("usage", {}).get("completion_tokens", 0),
            "total": data.get("usage", {}).get("total_tokens", 0)
        },
        "elapsed_ms": elapsed_ms,
        "model": MODEL
    }

def call_with_tools(prompt: str, tools: list, system: str = None) -> dict:
    """
    使用 Function Calling 调用 Hunter Alpha

    Args:
        prompt: 用户输入
        tools: 工具定义列表
        system: 系统提示词

    Returns:
        dict: 包含 response, tool_calls
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("未找到 OpenRouter API Key")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto"
    }

    import time
    start = time.time()

    response = requests.post(API_URL, headers=headers, json=payload, timeout=300)
    elapsed_ms = (time.time() - start) * 1000

    if response.status_code != 200:
        raise Exception(f"API 错误: {response.status_code} - {response.text}")

    data = response.json()
    message = data["choices"][0]["message"]

    return {
        "response": message.get("content"),
        "tool_calls": message.get("tool_calls"),
        "tokens": data.get("usage", {}),
        "elapsed_ms": elapsed_ms
    }

def call_structured(prompt: str, schema: dict, system: str = None) -> dict:
    """
    结构化输出调用

    Args:
        prompt: 用户输入
        schema: JSON Schema
        system: 系统提示词

    Returns:
        dict: 解析后的 JSON 对象
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("未找到 OpenRouter API Key")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "schema": schema
            }
        }
    }

    import time
    start = time.time()

    response = requests.post(API_URL, headers=headers, json=payload, timeout=300)
    elapsed_ms = (time.time() - start) * 1000

    if response.status_code != 200:
        raise Exception(f"API 错误: {response.status_code} - {response.text}")

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    return {
        "parsed": json.loads(content),
        "raw": content,
        "tokens": data.get("usage", {}),
        "elapsed_ms": elapsed_ms
    }

def test_connection():
    """测试连接"""
    print("测试 Hunter Alpha 连接...")
    print(f"模型: {MODEL}")
    print(f"API Key: {'已配置' if get_api_key() else '未配置'}")
    print()

    if not get_api_key():
        print("❌ 请先配置 API Key:")
        print("   echo '你的密钥' > ~/.secrets/openrouter_api_key.txt")
        return False

    try:
        result = call_hunter("请用一句话介绍你自己", max_tokens=100)
        print(f"✅ 连接成功!")
        print(f"响应时间: {result['elapsed_ms']:.0f}ms")
        print(f"Token 消耗: {result['tokens']['total']}")
        print(f"响应: {result['response'][:200]}...")
        return True
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

def test_structured():
    """测试结构化输出"""
    print("测试结构化输出...")

    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "skills": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["name", "age", "skills"]
    }

    try:
        result = call_structured(
            "生成一个程序员的基本信息",
            schema
        )
        print(f"✅ 结构化输出成功!")
        print(f"响应: {json.dumps(result['parsed'], ensure_ascii=False, indent=2)}")
        return True
    except Exception as e:
        print(f"❌ 结构化输出失败: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    if sys.argv[1] == "--test":
        test_connection()
    elif sys.argv[1] == "--structured":
        test_structured()
    else:
        prompt = " ".join(sys.argv[1:])
        result = call_hunter(prompt)
        print(result["response"])
        print(f"\n--- Token: {result['tokens']['total']} | 耗时: {result['elapsed_ms']:.0f}ms ---", file=sys.stderr)

if __name__ == "__main__":
    main()