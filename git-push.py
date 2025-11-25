#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git 自动推送程序
自动将当前文件夹的内容推送到 Git 库
"""

import subprocess
from datetime import datetime

# ==================== 配置参数区域 ====================

# Git 提交信息（可自定义）
COMMIT_MESSAGE = f"Auto commit - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

# 要推送的分支
BRANCH = "main"

# ======================================================


def run_command(cmd: str) -> tuple[bool, str]:
    """
    执行命令
    
    Args:
        cmd: 要执行的命令
        
    Returns:
        (成功标志, 输出信息)
    """
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)


def main():
    """主函数"""
    print("[INFO] 开始 Git 推送...")
    print()
    
    # 1. 添加所有文件
    print("[1/4] 添加文件到暂存区...")
    success, output = run_command("git add .")
    if not success:
        print(f"[ERROR] 添加文件失败: {output}")
        return False
    print("[OK] 文件已添加")
    
    # 2. 检查是否有更改
    print("[2/4] 检查更改...")
    success, output = run_command("git status --porcelain")
    if not success:
        print(f"[ERROR] 检查状态失败: {output}")
        return False
    
    if not output:
        print("[INFO] 没有需要提交的更改")
        return True
    
    print(f"[OK] 检测到更改:\n{output}")
    
    # 3. 提交更改
    print(f"[3/4] 提交更改...")
    success, output = run_command(f'git commit -m "{COMMIT_MESSAGE}"')
    if not success:
        print(f"[ERROR] 提交失败: {output}")
        return False
    print(f"[OK] 提交成功")
    
    # 4. 推送到远程
    print(f"[4/4] 推送到远程分支 {BRANCH}...")
    success, output = run_command(f"git push origin {BRANCH}")
    if not success:
        print(f"[ERROR] 推送失败: {output}")
        return False
    print(f"[OK] 推送成功")
    
    print()
    print("[SUCCESS] Git 推送完成！")
    return True


if __name__ == "__main__":
    main()
