#!/usr/bin/env python3
"""
使用 FastMCP Client 测试和风天气 MCP 服务
"""

import asyncio
import os
import sys

from fastmcp import Client

from weather_mcp import mcp


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
    """测试当前天气查询（包含预警、空气质量和指数）"""
    print("=" * 50)
    print("测试 2: 当前天气查询 - 北京（含预警/空气质量/指数）")
    print("=" * 50)

    async with Client(mcp) as client:
        result = await client.call_tool("get_current_weather", {"location": "北京"})
        # result 是 CallToolResult 对象，包含 content 列表
        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)
    print()


async def test_weather_forecast():
    """测试天气预报查询（包含空气质量和指数）"""
    print("=" * 50)
    print("测试 3: 7天天气预报 - 上海（含空气质量/指数）")
    print("=" * 50)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_weather_forecast", {"location": "上海", "days": 7}
        )
        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)
    print()


async def test_current_weather_no_extras():
    """测试当前天气查询（不包含额外信息）"""
    print("=" * 50)
    print("测试 4: 当前天气查询（不含额外信息）")
    print("=" * 50)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_current_weather",
            {
                "location": "深圳",
                "include_warning": False,
                "include_air_quality": False,
                "include_indices": False,
            },
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

    # 检查 JWT 环境变量
    from weather_mcp import (
        API_HOST,
        KEY_ID,
        PRIVATE_KEY,
        PRIVATE_KEY_PATH,
        PROJECT_ID,
    )

    if (
        not PROJECT_ID
        or not KEY_ID
        or (not PRIVATE_KEY and not PRIVATE_KEY_PATH)
        or not API_HOST
    ):
        print("❌ 错误: 缺少必要的环境变量配置")
        print("\n请配置以下环境变量:")
        print("  QWEATHER_PROJECT_ID=your_project_id")
        print("  QWEATHER_KEY_ID=your_key_id")
        print("  QWEATHER_API_HOST=https://api.qweather.com")
        print("\n私钥配置（二选一）:")
        print("  QWEATHER_PRIVATE_KEY=直接填写私钥内容")
        print("  QWEATHER_PRIVATE_KEY_PATH=/path/to/private_key.pem")
        print("\n示例:")
        print("  export QWEATHER_PROJECT_ID=xxx")
        print("  export QWEATHER_KEY_ID=xxx")
        print("  export QWEATHER_API_HOST=https://api.qweather.com")
        print("  export QWEATHER_PRIVATE_KEY_PATH=/path/to/ed25519-private.pem")
        return 1

    try:
        # 测试 1: 列出工具
        await test_list_tools()

        # 测试 2: 当前天气
        await test_current_weather()

        # 测试 3: 天气预报
        await test_weather_forecast()

        # 测试 4: 当前天气（不含额外信息）
        await test_current_weather_no_extras()

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
