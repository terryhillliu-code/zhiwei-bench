# PDF 阅读能力评测方案

> 评测目标: qwen3.5-plus, glm-4.7, glm-5, Hunter Alpha, kimi-k2.5, MiniMax-M2.5
> 方案类型: 多维度评测 + 自动化脚本

---

## 一、评测概述

测试各模型处理 PDF 文档的能力，涵盖文本提取、表格识别、图表理解、多模态处理等维度。

**核心问题**：
1. 模型是否能直接读取 PDF？（需要先转换还是支持多模态）
2. 文本提取准确率如何？
3. 表格、图表能否正确识别？
4. 长文档处理能力如何？

---

## 二、评测维度

| 维度 | 权重 | 测试内容 |
|------|------|----------|
| **文本提取** | 30% | 准确提取纯文本内容 |
| **表格识别** | 25% | 正确解析表格结构 |
| **图表理解** | 20% | 理解图表内容和含义 |
| **长文档处理** | 15% | 多页文档的摘要和问答 |
| **格式保持** | 10% | 保持原文档结构 |

---

## 三、测试样本

### 3.1 样本类型

| 类型 | 文件 | 来源 | 测试点 |
|------|------|------|--------|
| **纯文本** | `sample_text.pdf` | 自建 | 文本提取准确率 |
| **表格** | `sample_table.pdf` | 自建 | 表格结构识别 |
| **图表** | `sample_chart.pdf` | 自建 | 图表数据提取 |
| **学术论文** | `sample_paper.pdf` | arXiv | 综合能力 |
| **长文档** | `sample_long.pdf` | 自建 | 多页处理 |

### 3.2 测试样本生成

使用 Python 生成可控的测试 PDF：

```python
# scripts/generate_test_pdfs.py
"""
生成测试用 PDF 文件
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
import io

def create_text_pdf():
    """创建纯文本 PDF"""
    doc = SimpleDocTemplate("test_pdfs/sample_text.pdf", pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("PDF 阅读能力测试 - 文本提取", styles['Title']))
    story.append(Spacer(1, 0.5*cm))

    test_text = """
    这是一段测试文本，用于评估模型的文本提取能力。

    关键信息点：
    1. 公司名称：知微科技有限公司
    2. 成立日期：2020年3月15日
    3. 注册资本：5000万元人民币
    4. 员工人数：128人
    5. 主营业务：人工智能软件开发

    技术栈包括：Python、TensorFlow、PyTorch、Docker、Kubernetes。

    联系方式：
    - 电话：010-12345678
    - 邮箱：contact@zhiwei.ai
    - 地址：北京市海淀区中关村大街1号

    特殊字符测试：α β γ δ ε → ← ↑ ↓ ✓ ✗ © ® ™

    数字测试：3.14159, 2.71828, 1,234,567, 89%

    英文测试：The quick brown fox jumps over the lazy dog.
    """

    story.append(Paragraph(test_text, styles['Normal']))
    doc.build(story)


def create_table_pdf():
    """创建表格 PDF"""
    doc = SimpleDocTemplate("test_pdfs/sample_table.pdf", pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("PDF 阅读能力测试 - 表格识别", styles['Title']))
    story.append(Spacer(1, 0.5*cm))

    # 表格数据
    data = [
        ['产品名称', '单价(元)', '数量', '总价(元)'],
        ['Python高级教程', '89.00', '10', '890.00'],
        ['机器学习实战', '128.00', '5', '640.00'],
        ['深度学习入门', '99.00', '8', '792.00'],
        ['数据分析手册', '75.00', '15', '1125.00'],
        ['合计', '-', '38', '3447.00'],
    ]

    table = Table(data, colWidths=[5*cm, 3*cm, 2*cm, 3*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))

    story.append(table)
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("问题：请计算平均单价是多少？", styles['Normal']))

    doc.build(story)


def create_chart_pdf():
    """创建图表 PDF"""
    doc = SimpleDocTemplate("test_pdfs/sample_chart.pdf", pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("PDF 阅读能力测试 - 图表理解", styles['Title']))
    story.append(Spacer(1, 0.5*cm))

    # 创建柱状图
    drawing = Drawing(400, 200)
    chart = VerticalBarChart()
    chart.x = 50
    chart.y = 50
    chart.height = 125
    chart.width = 300
    chart.data = [
        [13, 5, 20, 22, 37, 45, 19, 4],
    ]
    chart.categoryAxis.categoryNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug']
    chart.bars[0].fillColor = colors.blue
    drawing.add(chart)
    drawing.add(String(200, 180, '月度销售额(万元)', fontSize=12, textAnchor='middle'))

    story.append(drawing)
    story.append(Spacer(1, 1*cm))

    story.append(Paragraph("问题：", styles['Normal']))
    story.append(Paragraph("1. 哪个月销售额最高？", styles['Normal']))
    story.append(Paragraph("2. 第一季度总销售额是多少？", styles['Normal']))
    story.append(Paragraph("3. 销售额超过30万元的月份有几个？", styles['Normal']))

    doc.build(story)


def create_multi_page_pdf():
    """创建多页长文档"""
    doc = SimpleDocTemplate("test_pdfs/sample_long.pdf", pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    for page in range(1, 6):
        story.append(Paragraph(f"第 {page} 页", styles['Title']))
        story.append(Spacer(1, 0.5*cm))

        story.append(Paragraph(f"""
        这是第 {page} 页的内容。

        本页关键信息：
        - 页码：{page}
        - 随机数：{(page * 17) % 100}
        - 标识符：PAGE-{page:03d}

        内容摘要：这一页讨论了第 {page} 个主题，涉及多个方面的分析。
        具体包括背景介绍、方法论述、实验结果和结论总结四个部分。

        数据点：[{page}, {page*2}, {page*3}, {page*4}, {page*5}]
        """, styles['Normal']))

        story.append(Spacer(1, 2*cm))

    doc.build(story)


if __name__ == "__main__":
    import os
    os.makedirs("test_pdfs", exist_ok=True)
    create_text_pdf()
    create_table_pdf()
    create_chart_pdf()
    create_multi_page_pdf()
    print("测试 PDF 生成完成")
```

---

## 四、评测方法

### 4.1 测试流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  生成测试PDF  │ ──→ │  模型处理PDF  │ ──→ │  评估输出结果  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
               ┌────▼────┐   ┌────▼────┐
               │ 方案A    │   │ 方案B    │
               │ 文本提取  │   │ 多模态   │
               │ + 文本输入│   │ 直接读取  │
               └─────────┘   └─────────┘
```

### 4.2 方案对比

| 方案 | 适用模型 | 方法 |
|------|----------|------|
| **方案A** | 所有模型 | 用 PyMuPDF 提取文本，输入模型 |
| **方案B** | 支持多模态的模型 | 直接传入 PDF 页面图像 |

### 4.3 评测脚本

```python
# scripts/run_pdf_eval.py
"""
PDF 阅读能力评测脚本
"""

import os
import json
import time
import base64
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import fitz  # PyMuPDF

# 模型配置
MODELS = [
    "qwen3.5-plus",
    "glm-4.7",
    "glm-5",
    "hunter-alpha",
    "kimi-k2.5",
    "minimax-m2.5"
]


@dataclass
class PDFEvalResult:
    """评测结果"""
    model: str
    test_type: str
    question: str
    expected: str
    actual: str
    correct: bool
    elapsed_ms: float
    tokens: int


def extract_text_from_pdf(pdf_path: str) -> str:
    """从 PDF 提取文本"""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def pdf_to_images(pdf_path: str) -> list:
    """将 PDF 页面转换为图像"""
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode()
        images.append(img_base64)
    doc.close()
    return images


def call_model_text(model: str, text: str, question: str) -> dict:
    """方案A：文本输入调用模型"""
    # 根据 model 调用不同 API
    # 返回 {response, tokens, elapsed_ms}
    pass


def call_model_vision(model: str, images: list, question: str) -> dict:
    """方案B：多模态调用模型"""
    # 仅支持视觉能力的模型
    pass


def evaluate_text_extraction():
    """评测文本提取能力"""
    pdf_path = "test_pdfs/sample_text.pdf"
    text = extract_text_from_pdf(pdf_path)

    questions = [
        {
            "question": "公司的名称是什么？",
            "expected": "知微科技有限公司",
            "check": lambda r: "知微科技" in r
        },
        {
            "question": "公司的注册资本是多少？",
            "expected": "5000万元",
            "check": lambda r: "5000" in r and "万" in r
        },
        {
            "question": "员工人数是多少？",
            "expected": "128人",
            "check": lambda r: "128" in r
        },
        {
            "question": "列出提到的所有技术栈",
            "expected": ["Python", "TensorFlow", "PyTorch", "Docker", "Kubernetes"],
            "check": lambda r: all(t in r for t in ["Python", "TensorFlow", "PyTorch"])
        }
    ]

    results = []
    for model in MODELS:
        for q in questions:
            result = call_model_text(model, text, q["question"])
            correct = q["check"](result["response"])
            results.append(PDFEvalResult(
                model=model,
                test_type="text_extraction",
                question=q["question"],
                expected=q["expected"],
                actual=result["response"],
                correct=correct,
                elapsed_ms=result["elapsed_ms"],
                tokens=result["tokens"]
            ))

    return results


def evaluate_table_recognition():
    """评测表格识别能力"""
    pdf_path = "test_pdfs/sample_table.pdf"

    questions = [
        {
            "question": "请将表格内容转换为Markdown格式",
            "check": lambda r: "|" in r and "---" in r  # Markdown表格特征
        },
        {
            "question": "哪种产品的单价最高？",
            "expected": "机器学习实战",
            "check": lambda r: "机器学习实战" in r and "128" in r
        },
        {
            "question": "计算平均单价（保留两位小数）",
            "expected": "97.75",  # (89+128+99+75)/4
            "check": lambda r: "97" in r or "平均" in r
        }
    ]

    # 评测逻辑...


def evaluate_chart_understanding():
    """评测图表理解能力"""
    # 需要多模态能力
    pass


def generate_report(results: list) -> str:
    """生成评测报告"""
    report = []
    report.append("# PDF 阅读能力评测报告\n")
    report.append(f"> 评测时间: {time.strftime('%Y-%m-%d %H:%M')}\n")
    report.append(f"> 评测模型: {', '.join(MODELS)}\n\n")

    # 按模型统计
    report.append("## 一、各模型得分\n\n")
    report.append("| 模型 | 文本提取 | 表格识别 | 图表理解 | 长文档 | 总分 |\n")
    report.append("|------|----------|----------|----------|--------|------|\n")

    # ... 计算分数

    return "\n".join(report)


if __name__ == "__main__":
    # 1. 生成测试 PDF
    os.system("python scripts/generate_test_pdfs.py")

    # 2. 运行评测
    all_results = []
    all_results.extend(evaluate_text_extraction())
    all_results.extend(evaluate_table_recognition())
    all_results.extend(evaluate_chart_understanding())

    # 3. 生成报告
    report = generate_report(all_results)
    with open("results/pdf_eval_report.md", "w") as f:
        f.write(report)

    print("PDF 阅读能力评测完成！")
```

---

## 五、测试问题设计

### 5.1 文本提取测试

| 问题 | 预期答案 | 评分点 |
|------|----------|--------|
| 公司名称是什么？ | 知微科技有限公司 | 精确匹配 |
| 注册资本是多少？ | 5000万元 | 数字+单位 |
| 员工人数？ | 128人 | 数字提取 |
| 技术栈有哪些？ | Python, TensorFlow... | 列举完整 |
| 特殊字符识别 | α β γ... | Unicode支持 |

### 5.2 表格识别测试

| 问题 | 预期答案 | 评分点 |
|------|----------|--------|
| 转换为Markdown表格 | \|\... | 格式正确 |
| 单价最高的产品？ | 机器学习实战(128元) | 数据比较 |
| 平均单价是多少？ | 97.75元 | 计算能力 |
| 总计多少元？ | 3447元 | 求和验证 |

### 5.3 图表理解测试

| 问题 | 预期答案 | 评分点 |
|------|----------|--------|
| 哪个月销售额最高？ | 6月(45万) | 极值识别 |
| Q1总销售额？ | 38万 | 计算 |
| 超过30万的月份？ | 2个(5月、6月) | 条件统计 |

### 5.4 长文档测试

| 问题 | 预期答案 | 评分点 |
|------|----------|--------|
| 共几页？ | 5页 | 全局信息 |
| 第3页的标识符？ | PAGE-003 | 定位能力 |
| 所有页码之和？ | 1+2+3+4+5=15 | 跨页计算 |

---

## 六、评分标准

### 6.1 评分公式

```
总分 = 文本提取(30%) + 表格识别(25%) + 图表理解(20%) + 长文档(15%) + 格式保持(10%)
```

### 6.2 单项评分

| 得分 | 标准 |
|------|------|
| 100% | 完全正确，格式完美 |
| 80% | 正确但格式有小问题 |
| 60% | 部分正确 |
| 40% | 有错误但方向对 |
| 20% | 基本错误 |
| 0% | 完全错误或无法处理 |

---

## 七、模型能力对照

| 模型 | 文本输入 | 多模态 | PDF直接读取 |
|------|----------|--------|-------------|
| qwen3.5-plus | ✅ | ✅ | ❌ |
| glm-4.7 | ✅ | ✅ | ❌ |
| glm-5 | ✅ | ✅ | ❌ |
| Hunter Alpha | ✅ | ❓待测 | ❌ |
| kimi-k2.5 | ✅ | ✅ | ❌ |
| MiniMax-M2.5 | ✅ | ❓待测 | ❌ |

**注**：大多数模型需要先提取 PDF 文本再输入，部分模型支持多模态可直接读取 PDF 图像。

---

## 八、预期产出

1. **评测报告**: `results/pdf_eval_report.md`
2. **详细数据**: `results/pdf_eval_details.json`
3. **模型对比**: 各维度雷达图
4. **最佳实践**: 针对不同场景的模型推荐

---

## 九、实施计划

| 阶段 | 任务 | 预计时间 |
|------|------|----------|
| Phase 1 | 生成测试 PDF | 10分钟 |
| Phase 2 | 实现评测脚本 | 30分钟 |
| Phase 3 | 运行六模型评测 | 1小时 |
| Phase 4 | 生成报告分析 | 20分钟 |

---

*方案版本: v1.0*
*创建时间: 2026-03-18*