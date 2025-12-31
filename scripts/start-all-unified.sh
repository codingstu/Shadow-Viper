#!/bin/bash

# 快速启动脚本 - Viper Node Store + SpiderFlow 统一启动
# 适用于：/Users/ikun/study/Learning 目录

UNIFIED_SCRIPT="/Users/ikun/study/Learning/start-all-projects.sh"

# 检查脚本是否存在
if [ ! -f "$UNIFIED_SCRIPT" ]; then
    echo "❌ 错误: 找不到统一启动脚本"
    echo "请确保 $UNIFIED_SCRIPT 存在"
    exit 1
fi

# 运行统一启动脚本
bash "$UNIFIED_SCRIPT"
