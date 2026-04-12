#!/usr/bin/env python3
"""
统一的 API 调用客户端

支持：
- 百炼 Coding Plan (OpenAI 格式)
- OpenRouter (OpenAI 格式)
- 火山引擎 Coding Plan (Anthropic 格式)

用法：
    from api_client import APIClient

    client = APIClient()
    response, meta = client.call("qwen3.5-plus", "你好", max_tokens=1024)
"""

import os
import json
import time
import ssl
import urllib.request
from pathlib import Path
from typing import Dict, Tuple, Optional

try:
    import yaml
except ImportError:
    yaml = None


class APIClient:
    """统一的 API 调用客户端"""

    # 默认系统提示词
    DEFAULT_SYSTEM_PROMPT = "你是一个有帮助的助手。"

    def __init__(self, config_path: str = None):
        """初始化客户端

        Args:
            config_path: 配置文件路径，默认为 zhiwei-bench/config/models.yaml
        """
        if config_path:
            self.config = self._load_config(config_path)
        else:
            # 默认配置路径
            default_path = Path(__file__).parent.parent / "config" / "models.yaml"
            if default_path.exists():
                self.config = self._load_config(str(default_path))
            else:
                self.config = {"models": {}}

    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        if yaml is None:
            # 如果没有 yaml，尝试用 json
            try:
                with open(config_path) as f:
                    return json.load(f)
            except:
                return {"models": {}}

        with open(config_path) as f:
            return yaml.safe_load(f)

    def get_api_key(self, model: str) -> str:
        """获取指定模型的 API Key

        查找顺序：
        1. 环境变量
        2. ~/.secrets/{api_key_env}.txt (OpenRouter)
        3. ~/.secrets/global.env
        4. ~/zhiwei-bot/.env

        Args:
            model: 模型名称

        Returns:
            API Key

        Raises:
            ValueError: 找不到 API Key
        """
        # 从配置获取环境变量名
        if model in self.config.get("models", {}):
            api_key_env = self.config["models"][model].get("api_key_env", "BAILIAN_API_KEY")
        else:
            api_key_env = "BAILIAN_API_KEY"

        # 优先从环境变量
        key = os.getenv(api_key_env)
        if key:
            return key

        # 从密钥文件加载 (OpenRouter 特殊处理)
        if api_key_env == "OPENROUTER_API_KEY":
            key_file = Path.home() / ".secrets" / "openrouter_api_key.txt"
            if key_file.exists():
                return key_file.read_text().strip()

        # 从 env 文件加载
        env_paths = [
            Path.home() / ".secrets" / "global.env",
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

    def call(self, model: str, prompt: str, max_tokens: int = 4096,
             system_prompt: str = None) -> Tuple[str, dict]:
        """调用 API

        Args:
            model: 模型名称（配置中的 key）
            prompt: 用户输入
            max_tokens: 最大输出 token 数
            system_prompt: 系统提示词（可选）

        Returns:
            (response_text, metadata)
            metadata 包含：elapsed_ms, input_tokens, output_tokens, total_tokens
        """
        if model not in self.config.get("models", {}):
            raise ValueError(f"模型 {model} 未在配置中找到")

        model_config = self.config["models"][model]
        endpoint = model_config["endpoint"]
        model_name = model_config["model"]
        api_key = self.get_api_key(model)

        if system_prompt is None:
            system_prompt = self.DEFAULT_SYSTEM_PROMPT

        # 根据端点类型选择调用方式
        if endpoint == "volcengine":
            return self._call_anthropic(model_name, api_key, prompt,
                                         max_tokens, system_prompt)
        else:
            return self._call_openai(endpoint, model_name, api_key, prompt,
                                      max_tokens, system_prompt)

    def _call_anthropic(self, model_name: str, api_key: str, prompt: str,
                        max_tokens: int, system_prompt: str) -> Tuple[str, dict]:
        """火山引擎 Anthropic 格式调用

        Anthropic API 格式：
        - URL: https://ark.cn-beijing.volces.com/api/coding/v1/messages
        - Header: x-api-key (非 Authorization)
        - Header: anthropic-version: 2023-06-01
        - Body: model, max_tokens, system, messages
        - Response: content[{type: "text", text: "..."}], usage
        """
        url = "https://ark.cn-beijing.volces.com/api/coding/v1/messages"

        payload = {
            "model": model_name,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}]
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }

        return self._execute_request(url, payload, headers, "anthropic")

    def _call_openai(self, endpoint: str, model_name: str, api_key: str,
                     prompt: str, max_tokens: int, system_prompt: str) -> Tuple[str, dict]:
        """百炼/OpenRouter OpenAI 格式调用

        OpenAI API 格式：
        - URL: https://{endpoint}/v1/chat/completions
        - Header: Authorization: Bearer {api_key}
        - Body: model, messages[{role, content}], temperature, max_tokens
        - Response: choices[{message: {content}}], usage
        """
        if endpoint == "openrouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/terryhillliu-code/zhiwei-bench",
                "X-Title": "Zhiwei Bench"
            }
        else:
            url = f"https://{endpoint}/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens
        }

        return self._execute_request(url, payload, headers, "openai")

    def _execute_request(self, url: str, payload: dict, headers: dict,
                         response_format: str) -> Tuple[str, dict]:
        """执行 HTTP 请求并解析响应

        Args:
            url: API URL
            payload: 请求体
            headers: 请求头
            response_format: 响应格式类型 ("anthropic" 或 "openai")

        Returns:
            (content, metadata)
        """
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

        # 解析响应
        if response_format == "anthropic":
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
        else:  # openai
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

        return content, {
            "elapsed_ms": elapsed_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }


# 便捷函数
def call_api(model: str, prompt: str, max_tokens: int = 4096,
             system_prompt: str = None, config_path: str = None) -> Tuple[str, dict]:
    """便捷调用函数

    Args:
        model: 模型名称
        prompt: 用户输入
        max_tokens: 最大输出 token
        system_prompt: 系统提示词
        config_path: 配置文件路径

    Returns:
        (response, metadata)
    """
    client = APIClient(config_path)
    return client.call(model, prompt, max_tokens, system_prompt)


if __name__ == "__main__":
    # 测试
    import argparse

    parser = argparse.ArgumentParser(description="API 客户端测试")
    parser.add_argument("--model", required=True, help="模型名称")
    parser.add_argument("--prompt", default="你好，请介绍一下自己", help="测试提示词")

    args = parser.parse_args()

    print(f"测试模型: {args.model}")
    print(f"提示词: {args.prompt}")
    print("-" * 40)

    try:
        response, meta = call_api(args.model, args.prompt)
        print(f"响应: {response[:200]}...")
        print(f"耗时: {meta['elapsed_ms']}ms")
        print(f"Token: {meta['total_tokens']}")
    except Exception as e:
        print(f"错误: {e}")