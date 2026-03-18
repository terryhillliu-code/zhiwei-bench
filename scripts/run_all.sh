#!/bin/bash
# 一键运行所有评测
# 用法: ./run_all.sh [--samples N]

set -e

cd "$(dirname "$0")/.."
source venv/bin/activate

SAMPLES=${1:-50}
CONFIG="config/models.yaml"

echo "============================================"
echo "  LLM Agent 编程能力评测"
echo "  评测样本数: ${SAMPLES}"
echo "============================================"

# 1. 检查环境
echo ""
echo "[1/4] 检查环境..."
python3 -c "import yaml, tqdm" 2>/dev/null || {
    echo "安装依赖..."
    pip install pyyaml tqdm
}

# 2. 检查数据集
echo ""
echo "[2/4] 检查数据集..."
if [ ! -f "benchmarks/human-eval/data/HumanEval.jsonl" ]; then
    echo "错误: HumanEval 数据集未找到"
    exit 1
fi

# 3. 运行 HumanEval
echo ""
echo "[3/4] 运行 HumanEval 评测..."
python3 scripts/run_human_eval.py --all --samples $SAMPLES --config $CONFIG

# 4. 生成报告
echo ""
echo "[4/4] 生成报告..."
python3 scripts/report.py --config $CONFIG

echo ""
echo "============================================"
echo "  评测完成！"
echo "  报告位置: results/comparison_report.md"
echo "============================================"