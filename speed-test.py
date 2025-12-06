#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sing-box 节点下载速度测试程序
测试节点的实际下载速度，筛选出满足阈值的节点
"""

import base64
import json
import subprocess
import time
import os
import tempfile
import signal
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Optional

# ==================== 配置参数区域 ====================

# 下载速度阈值（KB/s），低于此值的节点将被过滤
SPEED_THRESHOLD = 250

# 测试下载地址（支持多个，会随机选择）
TEST_URLS = [
    "http://lax.download.datapacket.com/100mb.bin"
]

# 单个节点最大测试时间（秒）
TIMEOUT = 20

# 并发测试数量
MAX_WORKERS = 100

# sing-box 可执行文件路径
SING_BOX_PATH = "sing-box"

# 输入文件路径（包含可连接的节点）
INPUT_FILE = "pingable-nodes.txt"

# 输出文件路径（保存速度满足条件的节点）
OUTPUT_FILE = "working-nodes.txt"

# sing-box 监听端口基数（每个测试会使用不同端口避免冲突）
BASE_PORT = 30000

# sing-box 启动等待时间（秒）
STARTUP_WAIT = 1

# 速度超过此值（KB/s）就停止下载，按此值计算（节省流量）
SPEED_CAP = 1024

# 单次下载最大字节数（防止流量过多）
MAX_DOWNLOAD_SIZE = 2 * 1024 * 1024

# 是否按速度排序输出（True 则从快到慢）
SORT_BY_SPEED = True

# 是否显示调试信息
DEBUG_MODE = False

# 限制测试的节点数量（0 表示不限制）
MAX_NODES = 50

# 限制输出的节点数量（0 表示不限制）
MAX_OUTPUT_NODES = 20

# ======================================================


def read_nodes(file_path: str) -> List[str]:
    """读取并解码 base64 编码的节点文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.read().strip().split('\n')
        
        nodes = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            try:
                decoded = base64.b64decode(line).decode('utf-8')
                decoded_nodes = [n.strip() for n in decoded.split('\n') if n.strip()]
                nodes.extend(decoded_nodes)
            except:
                nodes.append(line)
        
        print(f"[INFO] 读取 {len(nodes)} 个节点")
        return nodes
    except Exception as e:
        print(f"[ERROR] 读取节点文件失败: {e}")
        return []


def parse_vmess(url: str) -> Optional[dict]:
    """解析 vmess 协议"""
    try:
        data = json.loads(base64.b64decode(url.split('://')[1]).decode())
        config = {
            "type": "vmess",
            "server": data.get('add'),
            "server_port": int(data.get('port', 443)),
            "uuid": data.get('id'),
            "security": data.get('scy', 'auto'),
            "alter_id": int(data.get('aid', 0))
        }
        
        net = data.get('net', 'tcp')
        if net == 'ws':
            config['transport'] = {
                "type": "ws",
                "path": data.get('path', '/'),
                "headers": {"Host": data.get('host', '')} if data.get('host') else {}
            }
        elif net == 'grpc':
            config['transport'] = {"type": "grpc"}
        
        if data.get('tls') == 'tls':
            config['tls'] = {
                "enabled": True,
                "server_name": data.get('sni') or data.get('host') or data.get('add')
            }
        
        return config
    except:
        return None


def parse_vless(url: str) -> Optional[dict]:
    """解析 vless 协议"""
    try:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        
        config = {
            "type": "vless",
            "server": parsed.hostname,
            "server_port": parsed.port or 443,
            "uuid": parsed.username
        }
        
        flow = params.get('flow', [''])[0]
        if flow:
            config['flow'] = flow
        
        security = params.get('security', [''])[0]
        if security == 'tls':
            config['tls'] = {
                "enabled": True,
                "server_name": params.get('sni', [parsed.hostname])[0]
            }
        
        transport_type = params.get('type', ['tcp'])[0]
        if transport_type == 'ws':
            config['transport'] = {
                "type": "ws",
                "path": params.get('path', ['/'])[0],
                "headers": {"Host": params.get('host', [parsed.hostname])[0]}
            }
        elif transport_type == 'grpc':
            config['transport'] = {"type": "grpc"}
        
        return config
    except:
        return None


def parse_ss(url: str) -> Optional[dict]:
    """解析 shadowsocks 协议"""
    try:
        parsed = urllib.parse.urlparse(url)
        decoded = base64.b64decode(parsed.username).decode()
        method, password = decoded.split(':', 1)
        return {
            "type": "shadowsocks",
            "server": parsed.hostname,
            "server_port": parsed.port or 8388,
            "method": method,
            "password": password
        }
    except:
        return None


def parse_trojan(url: str) -> Optional[dict]:
    """解析 trojan 协议"""
    try:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        
        config = {
            "type": "trojan",
            "server": parsed.hostname,
            "server_port": parsed.port or 443,
            "password": parsed.username
        }
        
        security = params.get('security', ['tls'])[0]
        if security == 'tls':
            config['tls'] = {
                "enabled": True,
                "server_name": params.get('sni', [parsed.hostname])[0]
            }
        
        transport_type = params.get('type', ['tcp'])[0]
        if transport_type == 'ws':
            config['transport'] = {
                "type": "ws",
                "path": params.get('path', ['/'])[0],
                "headers": {"Host": params.get('host', [parsed.hostname])[0]}
            }
        
        return config
    except:
        return None


def convert_share_url_to_outbound(node_url: str) -> Optional[dict]:
    """将分享链接转换为 sing-box outbound 配置"""
    try:
        protocol = node_url.split('://')[0].lower()
        
        if protocol == 'vmess':
            return parse_vmess(node_url)
        elif protocol == 'vless':
            return parse_vless(node_url)
        elif protocol == 'ss':
            return parse_ss(node_url)
        elif protocol == 'trojan':
            return parse_trojan(node_url)
        else:
            return None
    except:
        return None


def create_sing_box_config(node_url: str, port: int) -> Optional[dict]:
    """为节点创建 sing-box 配置"""
    outbound = convert_share_url_to_outbound(node_url)
    if not outbound:
        return None
    
    outbound['tag'] = 'proxy'
    
    config = {
        "log": {
            "level": "error",
            "disabled": False
        },
        "inbounds": [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": port
            }
        ],
        "outbounds": [
            outbound,
            {
                "type": "direct",
                "tag": "direct"
            }
        ]
    }
    
    return config





def test_node_speed(node_url: str, index: int) -> Tuple[str, Optional[float]]:
    """测试单个节点的下载速度"""
    temp_config = None
    process = None
    
    try:
        config = create_sing_box_config(node_url, BASE_PORT + index)
        if not config:
            protocol = node_url.split('://')[0].lower() if '://' in node_url else 'unknown'
            if DEBUG_MODE:
                print(f"[SKIP] 节点 {index + 1}: 不支持的协议 ({protocol})")
            return (node_url, None)
        
        # 尝试多个端口
        for port_offset in range(10):
            port = BASE_PORT + index + port_offset * 1000
            config['inbounds'][0]['listen_port'] = port
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                json.dump(config, f, indent=2)
                temp_config = f.name
            
            if DEBUG_MODE:
                process = subprocess.Popen(
                    [SING_BOX_PATH, 'run', '-c', temp_config],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid if os.name != 'nt' else None
                )
            else:
                process = subprocess.Popen(
                    [SING_BOX_PATH, 'run', '-c', temp_config],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid if os.name != 'nt' else None
                )
            
            time.sleep(STARTUP_WAIT)
            
            if process.poll() is None:
                break
            else:
                if os.path.exists(temp_config):
                    os.unlink(temp_config)
                time.sleep(0.1)
        else:
            if DEBUG_MODE:
                print(f"[FAIL] 节点 {index + 1}: 无可用端口")
            return (node_url, None)
        
        # 测试下载速度
        test_url = TEST_URLS[index % len(TEST_URLS)]
        proxy = f"http://127.0.0.1:{port}"
        
        try:
            import urllib.request
            proxy_handler = urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
            opener = urllib.request.build_opener(proxy_handler)
            
            start_time = time.time()
            downloaded = 0
            
            response = opener.open(test_url, timeout=TIMEOUT)
            
            while True:
                elapsed = time.time() - start_time
                if elapsed > TIMEOUT:
                    break
                    
                chunk = response.read(8192)
                if not chunk:
                    break
                    
                downloaded += len(chunk)
                
                if elapsed > 0:
                    current_speed = downloaded / elapsed / 1024
                    if current_speed > SPEED_CAP:
                        break
                
                if downloaded > MAX_DOWNLOAD_SIZE:
                    break
            
            response.close()
            elapsed = time.time() - start_time
            
            if elapsed > 0:
                speed_kbs = downloaded / elapsed / 1024
                print(f"[OK] 节点 {index + 1}: {speed_kbs:.2f} KB/s")
                return (node_url, speed_kbs)
            else:
                if DEBUG_MODE:
                    print(f"[FAIL] 节点 {index + 1}: 测试时间过短")
                return (node_url, None)
                
        except Exception as e:
            if DEBUG_MODE:
                print(f"[FAIL] 节点 {index + 1}: 下载失败 - {str(e)[:50]}")
            return (node_url, None)
        
    except Exception as e:
        if DEBUG_MODE:
            print(f"[ERROR] 节点 {index + 1}: {str(e)[:50]}")
        return (node_url, None)
    
    finally:
        if process and process.poll() is None:
            try:
                if os.name != 'nt':
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()
                process.wait(timeout=2)
            except:
                try:
                    process.kill()
                except:
                    pass
        
        if temp_config and os.path.exists(temp_config):
            try:
                os.remove(temp_config)
            except:
                pass
        
        time.sleep(0.1)


def main():
    """主函数"""
    print("[INFO] 开始测试节点下载速度...")
    print(f"[INFO] 速度阈值: {SPEED_THRESHOLD} KB/s")
    print(f"[INFO] 速度上限: {SPEED_CAP} KB/s (节省流量)")
    print(f"[INFO] 并发数: {MAX_WORKERS}")
    print()
    
    nodes = read_nodes(INPUT_FILE)
    if not nodes:
        print("[ERROR] 没有可用的节点")
        return
    
    if MAX_NODES > 0 and len(nodes) > MAX_NODES:
        nodes = nodes[:MAX_NODES]
        print(f"[INFO] 限制测试数量: {len(nodes)} 个节点")
    
    results = []
    total_nodes = len(nodes)
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_node_speed, node, i): (node, i) 
                   for i, node in enumerate(nodes)}
        
        completed = 0
        for future in as_completed(futures, timeout=TIMEOUT*total_nodes+60):
            completed += 1
            node_url, speed = future.result()
            if speed is not None and speed >= SPEED_THRESHOLD:
                results.append((node_url, speed))
            print(f"[PROGRESS] {completed}/{total_nodes}")
    
    if SORT_BY_SPEED:
        results.sort(key=lambda x: x[1], reverse=True)
    
    output_results = results
    if MAX_OUTPUT_NODES > 0 and len(results) > MAX_OUTPUT_NODES:
        output_results = results[:MAX_OUTPUT_NODES]
    
    print()
    print(f"[SUCCESS] 测试完成！")
    print(f"[INFO] 满足条件的节点: {len(results)}/{total_nodes}")
    print(f"[INFO] 输出节点数: {len(output_results)}")
    
    if len(results) < 4:
        print(f"[WARNING] 满足条件的节点少于4个，不更新 {OUTPUT_FILE}")
    else:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for node_url, speed in output_results:
                f.write(f"{node_url}\n")
        print(f"[INFO] 结果已保存到: {OUTPUT_FILE}")
    
    if output_results:
        print(f"\n[TOP 5 最快节点]")
        for i, (node_url, speed) in enumerate(output_results[:5], 1):
            print(f"  {i}. {speed:.2f} KB/s - {node_url[:60]}...")
    else:
        print(f"\n[WARNING] 没有找到满足条件的节点")


if __name__ == "__main__":
    main()
