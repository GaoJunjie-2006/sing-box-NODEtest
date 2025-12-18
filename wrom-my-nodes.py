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
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, unquote

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    success_count = 0
    
    for url in NODE_URLS:
        try:
            print(f"  - 爬取: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            # 统一换行符为Unix格式
            content = response.text.replace('\r\n', '\n').replace('\r', '\n')
            all_nodes.append(content)
            success_count += 1
            print(f"    ✓ 成功")
        except requests.exceptions.Timeout:
            print(f"    ✗ 超时: 连接超过30秒")
        except requests.exceptions.ConnectionError:
            print(f"    ✗ 连接失败: 无法连接到服务器")
        except requests.exceptions.HTTPError as e:
            print(f"    ✗ HTTP错误: {e}")
        except Exception as e:
            print(f"    ✗ 未知错误: {e}")
    
    print(f"  [INFO] 成功爬取 {success_count}/{len(NODE_URLS)} 个链接")
    return "\n".join(all_nodes)


def process_node_names(content):
    """处理节点别名，去掉 -<字母数字> 部分"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 处理节点别名...")
    
    lines = content.strip().split('\n')
    processed_lines = []
    processed_count = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        try:
            # 验证是否为有效的base64字符串
            if not _is_valid_base64(line):
                print(f"  [WARN] 跳过非base64行: {line[:30]}...")
                processed_lines.append(line)
                continue
            
            # base64解码
            decoded = base64.b64decode(line).decode('utf-8').strip()
            
            # 验证解码后是否包含节点信息
            if not any(protocol in decoded for protocol in ['vmess://', 'vless://', 'trojan://', 'ss://']):
                print(f"  [WARN] 解码后非节点格式，保持原样")
                processed_lines.append(line)
                continue
            
            # 处理解码后的节点
            if '#' in decoded:
                try:
                    base_part, remark = decoded.rsplit('#', 1)
                    remark = unquote(remark)
                    # 去掉 -<字母数字> 后缀
                    if '-' in remark and len(remark.split('-')) > 1:
                        # 检查最后一部分是否为字母数字组合
                        last_part = remark.split('-')[-1]
                        if last_part.isalnum() and len(last_part) <= 10:
                            remark = '-'.join(remark.split('-')[:-1])
                            processed_count += 1
                    decoded = base_part + '#' + remark
                except ValueError as e:
                    print(f"  [WARN] 节点名称处理失败: {e}")
            
            # 重新编码
            line = base64.b64encode(decoded.encode()).decode()
            
        except (base64.binascii.Error, UnicodeDecodeError) as e:
            print(f"  [WARN] Base64解码失败，保持原样: {e}")
        except ValueError as e:
            print(f"  [WARN] 节点格式错误，保持原样: {e}")
        except Exception as e:
            print(f"  [ERROR] 处理节点时发生未知错误: {e}")
        
        processed_lines.append(line)
    
    print(f"  ✓ 处理完成: 共 {len(processed_lines)} 个节点，修改了 {processed_count} 个别名")
    return '\n'.join(processed_lines)


def _is_valid_base64(s):
    """检查字符串是否为有效的base64编码"""
    try:
        if len(s) % 4 != 0:
            return False
        base64.b64decode(s, validate=True)
        return True
    except Exception:
        return False


def save_nodes(content):
    """保存节点到文件"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 保存节点到 {OUTPUT_FILE}...")
    try:
        # 清理内容：统一换行符，去除空行和多余空白
        lines = [line.strip() for line in content.replace('\r\n', '\n').replace('\r', '\n').split('\n')]
        lines = [line for line in lines if line]  # 过滤空行
        clean_content = '\n'.join(lines)
        
        # 使用Unix换行符保存（newline='\n'）
        with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(clean_content)
            if clean_content and not clean_content.endswith('\n'):
                f.write('\n')  # 确保文件末尾有换行符
        
        print(f"  ✓ 成功保存到 {OUTPUT_FILE} (共 {len(lines)} 个节点)")
        return True
    except PermissionError as e:
        print(f"  ✗ 权限错误: 无法写入文件 {OUTPUT_FILE} - {e}")
        return False
    except FileNotFoundError as e:
        print(f"  ✗ 文件路径错误: {e}")
        return False
    except OSError as e:
        print(f"  ✗ 系统错误: {e}")
        return False
    except UnicodeEncodeError as e:
        print(f"  ✗ 编码错误: {e}")
        return False


def run_command(cmd):
    """执行命令"""
    try:
        if isinstance(cmd, str):
            # 仅对简单命令使用shell=True
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        else:
            # 对参数列表使用shell=False
            result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
    except (subprocess.SubprocessError, OSError) as e:
        logging.error(f"命令执行失败: {e}")
        return False, str(e)


def push_to_github():
    """推送到GitHub"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始推送到GitHub...")
    
    # 检查git是否安装
    success, output = run_command("git --version")
    if not success:
        print(f"  ✗ Git未安装或不在PATH中")
        return False
    print(f"  ✓ Git已安装: {output}")
    
    # 检查是否在git仓库中
    success, output = run_command("git rev-parse --git-dir")
    if not success:
        print(f"  ✗ 当前目录不是Git仓库，请先执行: git init")
        return False
    print(f"  ✓ Git仓库已初始化")
    
    # 设置远程仓库
    success, output = run_command(f"git remote set-url origin {GIT_REMOTE_URL}")
    if not success:
        # 如果设置失败，尝试添加
        success, output = run_command(f"git remote add origin {GIT_REMOTE_URL}")
        if not success:
            print(f"  ✗ 设置远程仓库失败: {output}")
            return False
    print(f"  ✓ 远程仓库已设置: {GIT_REMOTE_URL}")
    
    # 添加文件
    success, output = run_command("git add .")
    if not success:
        print(f"  ✗ 添加文件失败: {output}")
        return False
    print(f"  ✓ 文件已添加到暂存区")
    
    # 检查是否有更改
    success, output = run_command("git status --porcelain")
    if not success:
        print(f"  ✗ 检查状态失败: {output}")
        return False
    if not output:
        print(f"  ℹ 没有需要提交的更改")
        return True
    print(f"  ✓ 检测到更改")
    
    # 提交
    commit_msg = f"Auto update nodes - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    # 转义提交信息中的特殊字符
    escaped_msg = commit_msg.replace('"', '\"').replace('`', '\`').replace('$', '\$')
    success, output = run_command(f'git commit -m "{escaped_msg}"')
    if not success:
        print(f"  ✗ 提交失败: {output}")
        return False
    print(f"  ✓ 提交成功")
    
    # 推送
    success, output = run_command(f"git push origin {GIT_BRANCH}")
    if not success:
        if "Permission denied" in output or "publickey" in output:
            print(f"  ✗ SSH密钥验证失败")
            print(f"  提示: 请确保已将SSH公钥添加到GitHub")
            print(f"  生成密钥: ssh-keygen -t ed25519 -C 'your_email@example.com'")
            print(f"  查看公钥: cat ~/.ssh/id_ed25519.pub")
        elif "rejected" in output:
            print(f"  ✗ 推送被拒绝: 远程仓库有更新，请先拉取")
        else:
            print(f"  ✗ 推送失败: {output}")
        return False
    print(f"  ✓ 推送成功到 {GIT_BRANCH} 分支")
    return True


def update_task():
    """执行更新任务"""
    print("\n" + "="*50)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行更新任务")
    print("="*50)
    
    try:
        # 1. 爬取节点
        nodes_content = fetch_nodes()
        
        if not nodes_content or not nodes_content.strip():
            print("\n✗ 任务失败: 未获取到任何节点内容")
            return
        
        # 2. 处理节点名称
        processed_content = process_node_names(nodes_content)
        
        if not processed_content:
            print("\n✗ 任务失败: 节点处理后为空")
            return
        
        # 3. 保存到文件
        if not save_nodes(processed_content):
            print("\n✗ 任务失败: 无法保存文件")
            return
        
        # 4. 推送到GitHub
        if not push_to_github():
            print("\n✗ 任务失败: GitHub推送失败")
            return
        
        print("\n" + "="*50)
        print(f"✓✓✓ 任务完成 - {datetime.now().strftime('%H:%M:%S')}")
        print("="*50)
        
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"\n✗ 任务执行失败: {type(e).__name__}: {e}")
        import traceback
        print(f"详细错误:\n{traceback.format_exc()}")


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
    
    # 检查依赖
    try:
        import requests
        print("✓ requests库已安装")
    except ImportError:
        print("✗ 缺少依赖: 请运行 pip install requests")
        return
    
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
