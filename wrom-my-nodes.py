#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动更新v2ray节点并推送到GitHub
每天凌晨5:15自动执行
"""

import subprocess
import requests
import base64
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, unquote

# ==================== 配置参数区域 ====================

# v2ray节点订阅链接（在此添加您的链接）
NODE_URLS = [
    "http://72.11.152.226:2096/sub/nwecq8x8josiddi3",
    "http://72.11.152.226:2096/sub/dq8b549vs4tn94d2",
    "http://72.11.152.226:2096/sub/oitjhg0exfjlxg0m",
    # 在此添加更多链接...
    


]

# GitHub SSH 链接
GIT_REMOTE_URL = "git@github.com:GaoJunjie-2006/sing-box-NODEtest.git"

# 推送分支
GIT_BRANCH = "main"

# 节点保存文件
OUTPUT_FILE = "mynodes.txt"

# ======================================================


def fetch_nodes():
    """爬取所有链接的节点内容"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始爬取节点...")
    all_nodes = []
    
    for url in NODE_URLS:
        try:
            print(f"  - 爬取: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            all_nodes.append(response.text)
        except Exception as e:
            print(f"  [ERROR] 爬取失败 {url}: {e}")
    
    return "\n".join(all_nodes)


def process_node_names(content):
    """处理节点别名，去掉 -<字母数字> 部分"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 处理节点别名...")
    
    lines = content.strip().split('\n')
    processed_lines = []
    
    for line in lines:
        if not line.strip():
            continue
        
        try:
            # 先尝试base64解码
            decoded = base64.b64decode(line).decode('utf-8').strip()
            
            # 处理解码后的节点
            if '#' in decoded:
                base_part, remark = decoded.rsplit('#', 1)
                remark = unquote(remark)
                if '-' in remark:
                    remark = remark.split('-')[0]
                decoded = base_part + '#' + remark
            
            # 重新编码
            line = base64.b64encode(decoded.encode()).decode()
        except:
            pass
        
        processed_lines.append(line)
    
    return '\n'.join(processed_lines)


def save_nodes(content):
    """保存节点到文件"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 保存节点到 {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  [OK] 已保存")


def run_command(cmd):
    """执行命令"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return False, str(e)


def push_to_github():
    """推送到GitHub"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始推送到GitHub...")
    
    # 设置远程仓库
    run_command(f"git remote set-url origin {GIT_REMOTE_URL}")
    
    # 添加文件
    success, output = run_command("git add .")
    if not success:
        print(f"  [ERROR] 添加文件失败: {output}")
        return False
    
    # 检查是否有更改
    success, output = run_command("git status --porcelain")
    if not success or not output:
        print(f"  [INFO] 没有需要提交的更改")
        return True
    
    # 提交
    commit_msg = f"Auto update nodes - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    success, output = run_command(f'git commit -m "{commit_msg}"')
    if not success:
        print(f"  [ERROR] 提交失败: {output}")
        return False
    
    # 推送
    success, output = run_command(f"git push origin {GIT_BRANCH}")
    if not success:
        print(f"  [ERROR] 推送失败: {output}")
        return False
    
    print(f"  [OK] 推送成功")
    return True


def update_task():
    """执行更新任务"""
    print("\n" + "="*50)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行更新任务")
    print("="*50)
    
    try:
        # 1. 爬取节点
        nodes_content = fetch_nodes()
        
        if not nodes_content:
            print("[ERROR] 未获取到任何节点内容")
            return
        
        # 2. 处理节点名称
        processed_content = process_node_names(nodes_content)
        
        # 3. 保存到文件
        save_nodes(processed_content)
        
        # 4. 推送到GitHub
        push_to_github()
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ 任务完成")
        
    except Exception as e:
        print(f"[ERROR] 任务执行失败: {e}")


def main():
    """主函数"""
    print("="*50)
    print("v2ray节点自动更新程序")
    print("="*50)
    print(f"配置信息:")
    print(f"  - 节点链接数: {len(NODE_URLS)}")
    print(f"  - GitHub仓库: {GIT_REMOTE_URL}")
    print(f"  - 分支: {GIT_BRANCH}")
    print(f"  - 定时: 每天 05:15")
    print("="*50)
    
    # 立即执行一次
    update_task()
    
    print("\n等待下次执行时间: 每天 05:15")
    print("按 Ctrl+C 退出程序\n")
    
    try:
        while True:
            now = datetime.now()
            # 计算下次5:15的时间
            next_run = now.replace(hour=5, minute=15, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            
            # 等待到执行时间
            sleep_seconds = (next_run - datetime.now()).total_seconds()
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            
            # 执行任务
            update_task()
    except KeyboardInterrupt:
        print("\n程序已退出")


if __name__ == "__main__":
    main()
