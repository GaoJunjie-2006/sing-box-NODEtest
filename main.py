#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程序：循环执行测速和推送
"""

import runpy
import time
import sys

scripts = ['real-ping-test.py', 'speed-test.py', 'git-push.py']
pauses = [10, 10, 600*12]  # 每个脚本执行后的暂停时间（秒）

def main():
    """主函数"""
    iteration = 0
    
    while True:
        iteration += 1
        print(f"\n{'='*60}")
        print(f"[CYCLE {iteration}] 开始新一轮执行")
        print(f"{'='*60}\n")
        
        for i, script in enumerate(scripts):
            try:
                print(f"\n[{i+1}/{len(scripts)}] 执行 {script}...")
                runpy.run_path(script, run_name="__main__")
                
                pause_time = pauses[i]
                print(f"\n[INFO] {script} 执行完成，暂停 {pause_time} 秒...")
                time.sleep(pause_time)
                
            except Exception as e:
                print(f"[ERROR] 执行 {script} 失败: {e}")
                time.sleep(10)
        
        print(f"\n[INFO] 第 {iteration} 轮执行完成，准备开始下一轮...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] 程序被中断")
        sys.exit(0)
