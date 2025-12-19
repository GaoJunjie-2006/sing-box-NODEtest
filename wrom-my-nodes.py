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
    "http://72.11.152.226:2096/sub/ily5oat2lluvrqzm",
    "http://72.11.152.226:2096/sub/utiublgscmbtmxta",
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
    logging.info("开始爬取节点...")
    all_nodes = []
    success_count = 0 
    
    for url in NODE_URLS:
        try:
            logging.info(f"爬取: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            content = response.text.replace('\r\n', '\n').replace('\r', '\n')
            all_nodes.append(content)
            success_count += 1
            logging.info("成功")
        except requests.exceptions.Timeout:
            logging.warning(f"超时: {url}")
        except requests.exceptions.ConnectionError:
            logging.error(f"连接失败: {url}")
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP错误 {url}: {e}")
        except requests.RequestException as e:
            logging.error(f"请求错误 {url}: {e}")
    
    logging.info(f"成功爬取 {success_count}/{len(NODE_URLS)} 个链接")
    return "\n".join(all_nodes)


def process_node_names(content):
    """处理节点别名，去掉 -<字母数字> 部分"""
    logging.info("处理节点别名...")
    
    lines = content.strip().split('\n')
    processed_lines = []
    processed_count = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        try:
            if not _is_valid_base64(line):
                logging.warning(f"跳过非base64行: {line[:30]}...")
                processed_lines.append(line)
                continue
            
            decoded = base64.b64decode(line).decode('utf-8').strip()
            
            if not any(protocol in decoded for protocol in ['vmess://', 'vless://', 'trojan://', 'ss://']):
                logging.warning("解码后非节点格式，保持原样")
                processed_lines.append(line)
                continue
            
            if '#' in decoded:
                try:
                    base_part, remark = decoded.rsplit('#', 1)
                    remark = unquote(remark)
                    if '-' in remark and len(remark.split('-')) > 1:
                        last_part = remark.split('-')[-1]
                        if last_part.isalnum() and len(last_part) <= 10:
                            remark = '-'.join(remark.split('-')[:-1])
                            processed_count += 1
                    decoded = base_part + '#' + remark
                except ValueError as e:
                    logging.warning(f"节点名称处理失败: {e}")
            
            line = base64.b64encode(decoded.encode()).decode()
            
        except (base64.binascii.Error, UnicodeDecodeError) as e:
            logging.warning(f"Base64解码失败，保持原样: {e}")
        except ValueError as e:
            logging.warning(f"节点格式错误，保持原样: {e}")
    
        processed_lines.append(line)
    
    logging.info(f"处理完成: 共 {len(processed_lines)} 个节点，修改了 {processed_count} 个别名")
    return '\n'.join(processed_lines)


def _is_valid_base64(s):
    """检查字符串是否为有效的base64编码"""
    try:
        if len(s) % 4 != 0:
            return False
        base64.b64decode(s, validate=True)
        return True
    except (base64.binascii.Error, ValueError):
        return False


def save_nodes(content):
    """保存节点到文件"""
    logging.info(f"保存节点到 {OUTPUT_FILE}...")
    try:
        lines = [line.strip() for line in content.replace('\r\n', '\n').replace('\r', '\n').split('\n')]
        lines = [line for line in lines if line]
        
        # 先解码所有节点，然后再整体base64编码
        decoded_nodes = []
        for line in lines:
            try:
                decoded = base64.b64decode(line).decode('utf-8')
                decoded_nodes.append(decoded)
            except Exception:
                decoded_nodes.append(line)
        
        # 将所有节点拼接后整体base64编码
        all_nodes_text = '\n'.join(decoded_nodes)
        encoded_subscription = base64.b64encode(all_nodes_text.encode('utf-8')).decode('utf-8')
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(encoded_subscription)
        
        logging.info(f"成功保存到 {OUTPUT_FILE} (共 {len(lines)} 个节点)")
        return True
    except PermissionError as e:
        logging.error(f"权限错误: 无法写入文件 {OUTPUT_FILE} - {e}")
        return False
    except FileNotFoundError as e:
        logging.error(f"文件路径错误: {e}")
        return False
    except OSError as e:
        logging.error(f"系统错误: {e}")
        return False
    except UnicodeEncodeError as e:
        logging.error(f"编码错误: {e}")
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
    logging.info("开始推送到GitHub...")
    
    success, output = run_command("git --version")
    if not success:
        logging.error("Git未安装或不在PATH中")
        return False
    logging.info(f"Git已安装: {output}")
    
    success, output = run_command("git rev-parse --git-dir")
    if not success:
        logging.error("当前目录不是Git仓库，请先执行: git init")
        return False
    logging.info("Git仓库已初始化")
    
    success, output = run_command(f"git remote set-url origin {GIT_REMOTE_URL}")
    if not success:
        success, output = run_command(f"git remote add origin {GIT_REMOTE_URL}")
        if not success:
            logging.error(f"设置远程仓库失败: {output}")
            return False
    logging.info(f"远程仓库已设置: {GIT_REMOTE_URL}")
    
    success, output = run_command("git add .")
    if not success:
        logging.error(f"添加文件失败: {output}")
        return False
    logging.info("文件已添加到暂存区")
    
    success, output = run_command("git status --porcelain")
    if not success:
        logging.error(f"检查状态失败: {output}")
        return False
    if not output:
        logging.info("没有需要提交的更改")
        return True
    logging.info("检测到更改")
    
    commit_msg = f"Auto update nodes - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    escaped_msg = commit_msg.replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    success, output = run_command(f'git commit -m "{escaped_msg}"')
    if not success:
        logging.error(f"提交失败: {output}")
        return False
    logging.info("提交成功")
    
    success, output = run_command(f"git push origin {GIT_BRANCH}")
    if not success:
        if "Permission denied" in output or "publickey" in output:
            logging.error("SSH密钥验证失败")
        elif "rejected" in output:
            logging.error("推送被拒绝: 远程仓库有更新，请先拉取")
        else:
            logging.error(f"推送失败: {output}")
        return False
    logging.info(f"推送成功到 {GIT_BRANCH} 分支")
    return True


def update_task():
    """执行更新任务"""
    logging.info("="*50)
    logging.info("开始执行更新任务")
    logging.info("="*50)
    
    try:
        nodes_content = fetch_nodes()
        
        if not nodes_content or not nodes_content.strip():
            logging.error("任务失败: 未获取到任何节点内容")
            return
        
        processed_content = process_node_names(nodes_content)
        
        if not processed_content:
            logging.error("任务失败: 节点处理后为空")
            return
        
        if not save_nodes(processed_content):
            logging.error("任务失败: 无法保存文件")
            return
        
        if not push_to_github():
            logging.error("任务失败: GitHub推送失败")
            return
        
        logging.info("="*50)
        logging.info("任务完成")
        logging.info("="*50)
        
    except KeyboardInterrupt:
        raise
    except (OSError, IOError) as e:
        logging.error(f"IO错误: {e}")
    except Exception as e:
        logging.error(f"任务执行失败: {type(e).__name__}: {e}", exc_info=True)


def main():
    """主函数"""
    logging.info("="*50)
    logging.info("v2ray节点自动更新程序")
    logging.info("="*50)
    logging.info(f"节点链接数: {len(NODE_URLS)}")
    logging.info(f"GitHub仓库: {GIT_REMOTE_URL}")
    logging.info(f"分支: {GIT_BRANCH}")
    logging.info(f"定时: 每天 05:15")
    logging.info("="*50)
    
    try:
        import requests
        logging.info("requests库已安装")
    except ImportError:
        logging.error("缺少依赖: 请运行 pip install requests")
        return
    
    update_task()
    
    logging.info("等待下次执行时间: 每天 05:15")
    logging.info("按 Ctrl+C 退出程序")
    
    try:
        while True:
            now = datetime.now()
            next_run = now.replace(hour=5, minute=15, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            
            sleep_seconds = (next_run - now).total_seconds()
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            
            update_task()
    except KeyboardInterrupt:
        logging.info("程序已退出")


if __name__ == "__main__":
    main()
