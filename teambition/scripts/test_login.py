#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teambition 登录测试脚本
支持 email/password 和 Cookie 两种方式
"""

import sys
import os
import json
import time
import logging
from pathlib import Path
from typing import Optional

# 确保能找到 teambition_mcp_server 模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from teambition_mcp_server import (
    _do_login,
    _do_cookie_login,
    _ensure_logged_in,
    _get_client,
    _retry_request,
    login,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("teambition-test")

def test_email_password():
    """测试 email + password 方式"""
    print("\n" + "="*60)
    print("1. 测试 email + password 登录方式")
    print("="*60)

    email = os.getenv("TB_EMAIL", "huanglshu26@gmail.com")
    password = os.getenv("TB_PASSWORD", "Alpha@2026")

    print(f"邮箱: {email}")
    print(f"密码: {'*' * len(password)}")

    result = _do_login(email, password)
    print(f"\n返回结果: {result}")

    try:
        data = json.loads(result)
        if data.get("status") == "success":
            print(f"✅ 登录成功！用户: {data.get('name')} ({data.get('userId')})")
            return True
        else:
            print(f"❌ 登录失败: {data.get('message', result)}")
            return False
    except:
        print(f"❌ 解析失败: {result}")
        return False

def test_cookie_login():
    """测试 Cookie 登录"""
    print("\n" + "="*60)
    print("2. 测试 Cookie 登录方式")
    print("="*60)

    cookie = input("\n请输入 Cookie 字符串（JSESSIONID=xxx; csrftoken=yyy...）: ").strip()

    if not cookie:
        print("未输入 Cookie，跳过")
        return False

    print("正在使用 Cookie 登录...")
    result = _do_cookie_login(cookie)
    print(f"\n返回结果: {result}")

    try:
        data = json.loads(result)
        if data.get("status") == "success":
            print(f"✅ Cookie 登录成功！用户: {data.get('name')} ({data.get('userId')})")
            return True
        else:
            print(f"❌ Cookie 登录失败: {data.get('message', result)}")
            return False
    except:
        print(f"❌ 解析失败: {result}")
        return False

def test_mcp_login():
    """测试 MCP login 工具（email+password）"""
    print("\n" + "="*60)
    print("3. 测试 MCP login 工具（email+password）")
    print("="*60)

    email = input("请输入邮箱: ").strip() or os.getenv("TB_EMAIL", "huanglshu26@gmail.com")
    password = input("请输入密码: ").strip() or os.getenv("TB_PASSWORD", "Alpha@2026")

    print(f"\n正在调用 MCP login(email={email}, password=***...)")

    # 使用 MCP login 工具（返回 JSON 字符串）
    result = login(email=email, password=password)
    print(f"\n返回结果: {result}")

    try:
        data = json.loads(result)
        if data.get("status") == "success":
            print(f"✅ 登录成功！用户: {data.get('name')} ({data.get('userId')})")
            return True
        else:
            print(f"❌ 登录失败: {data.get('message', result)}")
            return False
    except:
        print(f"❌ 解析失败: {result}")
        return False

def main():
    print("Teambition 登录测试工具")
    print("支持两种登录方式：")
    print("  1. email + password（经典方式）")
    print("  2. Cookie 方式（推荐，用于持久化 Session）")
    print()

    while True:
        print("\n请选择测试方式:")
        print("1. 测试 email + password 登录")
        print("2. 测试 Cookie 登录")
        print("3. 测试 MCP login 工具")
        print("4. 退出")

        choice = input("\n请输入选项 (1-4): ").strip()

        if choice == "1":
            test_email_password()
        elif choice == "2":
            test_cookie_login()
        elif choice == "3":
            test_mcp_login()
        elif choice == "4":
            print("测试结束")
            break
        else:
            print("无效选项，请重新选择")

if __name__ == "__main__":
    main()
