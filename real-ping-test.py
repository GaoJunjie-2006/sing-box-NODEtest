#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sing-box 节点真连接延迟测速程序
使用 sing-box 测试节点的真实连接延迟，筛选出低延迟节点
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

# 延迟阈值（毫秒），低于此值的节点将被保留
LATENCY_THRESHOLD = 1200

# 测试地址（用于测试真连接延迟）
TEST_URL = "http://www.gstatic.com/generate_204"

# 单个节点最大等待时间（秒）
TIMEOUT = 10

# 并发测试数量
MAX_WORKERS = 10

# sing-box 可执行文件路径（如果在 PATH 中可直接使用 "sing-box"）
SING_BOX_PATH = "sing-box"

# 输入文件路径
INPUT_FILE = "free-nodes.txt"

# 输出文件路径
OUTPUT_FILE = "pingable-nodes.txt"

# sing-box 监听端口（每个测试会使用不同端口避免冲突）
BASE_PORT = 20000

# sing-box 启动等待时间（秒）
STARTUP_WAIT = 1

# 是否保留原始顺序（False 则按延迟排序）
KEEP_ORIGINAL_ORDER = False

# 是否显示调试信息（显示 sing-box 错误输出）
DEBUG_MODE = True

# ======================================================


def decode_base64_nodes(file_path: str) -> List[str]:
    """
    读取并解码 base64 编码的节点文件
    
    Args:
        file_path: 节点文件路径
        
    Returns:
        节点 URL 列表
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.read().strip().split('\n')
        
        nodes = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 尝试 base64 解码
            try:
                decoded = base64.b64decode(line).decode('utf-8')
                # 如果解码后包含多行，按行分割
                decoded_nodes = [n.strip() for n in decoded.split('\n') if n.strip()]
                nodes.extend(decoded_nodes)
            except:
                # 如果不是 base64，直接作为节点
                nodes.append(line)
        
        print(f"[INFO] 成功读取 {len(nodes)} 个节点")
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


def test_node_latency(node_url: str, index: int) -> Tuple[str, Optional[float]]:
    """测试单个节点的真连接延迟"""
    temp_config = None
    process = None
    
    try:
        config = create_sing_box_config(node_url, BASE_PORT + index)
        if not config:
            protocol = node_url.split('://')[0].lower() if '://' in node_url else 'unknown'
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
            print(f"[FAIL] 节点 {index + 1}: 无可用端口")
            return (node_url, None)
        
        # 测试连接延迟
        start_time = time.time()
        
        try:
            result = subprocess.run(
                ['curl', '-x', f'http://127.0.0.1:{port}', 
                 '-m', str(TIMEOUT), '-s', '-o', '/dev/null', '-w', '%{http_code}', 
                 TEST_URL],
                capture_output=True,
                timeout=TIMEOUT
            )
            
            latency = (time.time() - start_time) * 1000
            
            if result.returncode == 0 and result.stdout.decode().strip() == '204':
                print(f"[OK] 节点 {index + 1}: {latency:.0f}ms")
                return (node_url, latency)
            else:
                print(f"[FAIL] 节点 {index + 1}: 连接失败")
                return (node_url, None)
                
        except subprocess.TimeoutExpired:
            print(f"[TIMEOUT] 节点 {index + 1}: 超时")
            return (node_url, None)
            
    except Exception as e:
        print(f"[ERROR] 节点 {index + 1}: {str(e)[:50]}")
        return (node_url, None)
        
    finally:
        if process and process.poll() is None:
            try:
                if os.name != 'nt':
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()
                process.wait(timeout=1)
            except:
                try:
                    if os.name != 'nt':
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    else:
                        process.kill()
                except:
                    pass
        
        if temp_config and os.path.exists(temp_config):
            try:
                os.unlink(temp_config)
            except:
                pass
        
        time.sleep(0.2)


def save_nodes(nodes: List[str], file_path: str):
    """保存节点到文件（base64 编码）"""
    try:
        content = '\n'.join(nodes)
        encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(encoded)
        
        print(f"\n[SUCCESS] 已保存 {len(nodes)} 个节点到 {file_path}")
    except Exception as e:
        print(f"\n[ERROR] 保存节点失败: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("sing-box 节点真连接延迟测速程序")
    print("=" * 60)
    print(f"配置信息:")
    print(f"  - 延迟阈值: {LATENCY_THRESHOLD}ms")
    print(f"  - 测试地址: {TEST_URL}")
    print(f"  - 超时时间: {TIMEOUT}s")
    print(f"  - 并发数量: {MAX_WORKERS}")
    print(f"  - 输入文件: {INPUT_FILE}")
    print(f"  - 输出文件: {OUTPUT_FILE}")
    print("=" * 60)
    
    try:
        result = subprocess.run([SING_BOX_PATH, 'version'], 
                              capture_output=True, timeout=5)
        if result.returncode != 0:
            print(f"\n[WARNING] sing-box 可能未正确安装")
    except:
        print(f"\n[WARNING] 无法执行 sing-box，请确保已安装")
    
    print(f"\n[1/3] 读取节点文件...")
    nodes = decode_base64_nodes(INPUT_FILE)
    if not nodes:
        print("[ERROR] 没有可用节点")
        return
    
    print(f"\n[2/3] 开始测试节点延迟...")
    print(f"总共 {len(nodes)} 个节点，使用 {MAX_WORKERS} 个并发\n")
    
    valid_nodes = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_node_latency, node, i): (node, i) 
                  for i, node in enumerate(nodes)}
        
        for future in as_completed(futures):
            node_url, latency = future.result()
            if latency is not None and latency < LATENCY_THRESHOLD:
                valid_nodes.append((node_url, latency))
    
    if not KEEP_ORIGINAL_ORDER:
        valid_nodes.sort(key=lambda x: x[1])
    
    print(f"\n[3/3] 保存测试结果...")
    print(f"\n测试完成！")
    print(f"  - 总节点数: {len(nodes)}")
    print(f"  - 可用节点: {len(valid_nodes)}")
    print(f"  - 通过率: {len(valid_nodes)/len(nodes)*100:.1f}%")
    
    if valid_nodes:
        print(f"\n延迟最低的 5 个节点:")
        for i, (node, latency) in enumerate(valid_nodes[:5], 1):
            name = "未知"
            if '#' in node:
                name = node.split('#')[-1]
            print(f"  {i}. {name}: {latency:.0f}ms")
        
        save_nodes([node for node, _ in valid_nodes], OUTPUT_FILE)
    else:
        print(f"\n[WARNING] 没有找到延迟低于 {LATENCY_THRESHOLD}ms 的节点")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
