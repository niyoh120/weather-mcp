# 和风天气 MCP 服务

使用 Python 和 FastMCP 构建的 Model Context Protocol 服务，集成和风天气 API，提供实时天气查询和未来7天天气预报功能。

## 功能特性

- **实时天气查询**: 支持通过城市名称（如"北京"）或 LocationID（如"101010100"）查询当前天气
- **未来天气预报**: 支持3/7/10/15/30天天气预报（默认7天）
- **中文响应**: 所有天气数据返回中文描述
- **MCP标准协议**: 兼容 Claude Desktop、Cursor 等 MCP 客户端

**说明**: 工具会自动将城市名称转换为 LocationID。如果城市名称无效，会返回错误信息。

## 快速开始

### 1. 获取 API Key

访问 [和风天气开发者平台](https://dev.qweather.com/) 注册账号并创建项目，获取 API Key。

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```bash
QWEATHER_API_KEY=your_api_key_here
```

### 3. 安装依赖

使用 **mise** 和 **uv** 管理项目：

```bash
# 安装依赖
mise run install

# 或者使用 uv 直接安装
uv sync
```

### 4. 运行服务

**开发模式** (stdio 传输):
```bash
mise run server

# 或者
uv run python weather_server.py
```

**SSE 模式** (HTTP 传输):
```bash
uv run python weather_server.py --transport sse
```

### 5. 运行测试

```bash
mise run test

# 或者
uv run python test_server.py
```

## Claude Desktop 配置

在 Claude Desktop 的 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "weather": {
      "command": "mise",
      "args": ["run", "server"],
      "env": {
        "QWEATHER_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

或者使用 uv 直接运行：

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": ["run", "python", "/path/to/weather_server.py"],
      "env": {
        "QWEATHER_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

## 使用示例

配置完成后，你可以在 Claude 中直接询问：

- "北京今天天气怎么样？"
- "查询上海的7天天气预报"
- "深圳明天会下雨吗？"

## 可用工具

### 1. `get_current_weather(location: str)`

获取指定城市的当前天气信息。

**参数:**
- `location`: 城市名称（如"北京"、"上海"）或 LocationID（如"101010100"）
  - 支持中文城市名称，会自动搜索匹配的 LocationID
  - 如果城市名称无效，会返回错误信息

**返回示例:**
```
城市: 北京市
观测时间: 2024-01-15 14:30
温度: 5°C
体感温度: 2°C
天气: 多云
风向: 东北风
风力: 3级
湿度: 45%
降水量: 0.0mm
能见度: 10km
```

### 2. `get_weather_forecast(location: str, days: int = 7)`

获取指定城市的未来天气预报。

**参数:**
- `location`: 城市名称（如"北京"、"上海"）或 LocationID（如"101010100"）
  - 支持中文城市名称，会自动搜索匹配的 LocationID
  - 如果城市名称无效，会返回错误信息
- `days`: 预报天数，支持 3/7/10/15/30，默认 7 天

**返回示例:**
```
北京市 未来7天天气预报:

2024-01-16:
  天气: 晴
  温度: -2°C ~ 8°C
  风向: 北风 2级
  湿度: 35%
  紫外线: 弱

2024-01-17:
  天气: 多云
  温度: 0°C ~ 6°C
  风向: 东北风 3级
  湿度: 50%
  紫外线: 中等
```

## 技术栈

- [FastMCP](https://github.com/jlowin/fastmcp): MCP 服务框架
- [httpx](https://www.python-httpx.org/): 异步 HTTP 客户端
- [Pydantic](https://docs.pydantic.dev/): 数据验证
- [python-dotenv](https://saurabh-kumar.com/python-dotenv/): 环境变量管理
- [mise](https://mise.jdx.dev/): 开发环境管理
- [uv](https://docs.astral.sh/uv/): Python 包管理器

## 注意事项

1. **API 调用限制**: 免费版 API 每天限制 1000 次调用
2. **数据延迟**: 实况数据相比真实物理世界有 5-20 分钟延迟
3. **Gzip 压缩**: API 返回 Gzip 压缩数据，已自动处理
4. **LocationID**: 中国城市的 LocationID 可以在[常见城市列表](https://dev.qweather.com/docs/resource/location-list/)中查询

## 错误处理

服务会自动处理以下情况：
- API Key 无效或过期
- 城市名称不存在
- 网络连接超时
- API 返回错误码

## 许可证

MIT License

## 相关链接

- [和风天气开发文档](https://dev.qweather.com/docs/)
- [FastMCP 文档](https://github.com/jlowin/fastmcp)
- [MCP 协议规范](https://modelcontextprotocol.io/)
