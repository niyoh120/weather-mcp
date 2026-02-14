#!/usr/bin/env python3
"""
使用 FastMCP Client 测试和风天气 MCP 服务
"""

import asyncio
import os
import sys

from fastmcp import Client

from weather_server import mcp


async def test_list_tools():
    """测试列出可用工具"""
    print("=" * 50)
    print("测试 1: 列出可用工具")
    print("=" * 50)

    async with Client(mcp) as client:
        tools = await client.list_tools()
        print(f"发现 {len(tools)} 个工具:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
    print()


async def test_current_weather():
    """测试当前天气查询"""
    print("=" * 50)
    print("测试 2: 当前天气查询 (北京)")
    print("=" * 50)

    async with Client(mcp) as client:
        result = await client.call_tool("get_current_weather", {"location": "北京"})
        # result 是 CallToolResult 对象，包含 content 列表
        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)
    print()


async def test_weather_forecast():
    """测试天气预报查询"""
    print("=" * 50)
    print("测试 3: 7天天气预报查询 (上海)")
    print("=" * 50)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_weather_forecast", {"location": "上海", "days": 7}
        )
        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)
    print()


async def test_with_location_id():
    """测试使用 LocationID 查询"""
    print("=" * 50)
    print("测试 4: 使用 LocationID 查询 (101010100)")
    print("=" * 50)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_current_weather", {"location": "101010100"}
        )
        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)
    print()


async def test_invalid_city():
    """测试无效城市名称"""
    print("=" * 50)
    print("测试 5: 无效城市名称测试")
    print("=" * 50)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_current_weather", {"location": "不存在的城市12345"}
        )
        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)
    print()


async def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("和风天气 MCP 服务测试 (使用 FastMCP Client)")
    print("=" * 50 + "\n")

    # 检查 API Key
    api_key = os.getenv("QWEATHER_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        print("⚠️  警告: 未配置 QWEATHER_API_KEY")
        print("请在 .env 文件中设置有效的 API Key\n")
        return 1

    try:
        # 测试 1: 列出工具
        await test_list_tools()

        # 测试 2: 当前天气
        await test_current_weather()

        # 测试 3: 天气预报
        await test_weather_forecast()

        # 测试 4: 使用 LocationID
        await test_with_location_id()

        # 测试 5: 无效城市
        await test_invalid_city()

        print("=" * 50)
        print("✅ 所有测试完成！")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
