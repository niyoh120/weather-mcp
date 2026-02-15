# 和风天气 MCP 服务

使用 Python 和 FastMCP 构建的 Model Context Protocol 服务，集成和风天气 API，提供实时天气查询和未来7天天气预报功能。

## 功能特性

- **实时天气查询**: 支持通过城市名称查询当前天气
- **未来天气预报**: 支持3/7/10/15/30天天气预报（默认7天）
- **天气预警**: 集成实时天气预警信息
- **空气质量**: 集成实时空气质量和3天预报
- **天气指数**: 集成生活指数预报（运动、洗车、穿衣、紫外线、感冒等）
- **中文响应**: 所有天气数据返回中文描述
- **MCP标准协议**: 兼容 Claude Desktop、Cursor 等 MCP 客户端
- **JWT 鉴权**: 使用和风水官方推荐的 JWT Token 鉴权，更安全

## 快速开始

### 1. 创建 JWT 凭据

访问 [和风天气开发者平台](https://dev.qweather.com/) 注册账号并创建项目。

#### 生成 Ed25519 密钥对

```bash
openssl genpkey -algorithm ED25519 -out ed25519-private.pem
openssl pkey -pubout -in ed25519-private.pem > ed25519-public.pem
```

#### 上传公钥

1. 前往 [控制台 - 项目管理](https://console.qweather.com/project)
2. 选择你的项目，点击"添加凭据"
3. 选择身份认证方式为 "JSON Web Token"
4. 复制 `ed25519-public.pem` 的内容粘贴到公钥文本框
5. 保存后记录凭据 ID（Key ID）和项目 ID（Project ID）

### 2. 配置环境变量

```bash
# JWT 鉴权配置
QWEATHER_PROJECT_ID=your_project_id_here      # 项目 ID
QWEATHER_KEY_ID=your_key_id_here              # 凭据 ID

# 私钥配置（二选一）
# 方式1: 直接填写私钥内容
QWEATHER_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIA...
-----END PRIVATE KEY-----"

# 方式2: 指定私钥文件路径
QWEATHER_PRIVATE_KEY_PATH=/path/to/ed25519-private.pem

# API 主机地址
QWEATHER_API_HOST=https://api.qweather.com
```

### 3. 运行服务

使用 **uvx** 直接从 GitHub 运行：

```bash
uvx git+https://github.com/niyoh120/weather-mcp
```

**本地开发**（可选）：

```bash
# 安装依赖
uv sync

# 运行服务
uv run python weather_mcp.py

# SSE 模式
uv run python weather_mcp.py --transport sse

# 运行测试
uv run python test.py
```

## Claude Desktop 配置

在 Claude Desktop 的 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "weather": {
      "command": "uvx",
      "args": [
        "git+https://github.com/niyoh120/weather-mcp"
      ],
      "env": {
        "QWEATHER_PROJECT_ID": "your_project_id",
        "QWEATHER_KEY_ID": "your_key_id",
        "QWEATHER_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_CONTENT\n-----END PRIVATE KEY-----",
        "QWEATHER_API_HOST": "https://api.qweather.com"
      }
    }
  }
}
```

**配置说明**:
- `QWEATHER_PROJECT_ID`: 项目 ID（在控制台查看）
- `QWEATHER_KEY_ID`: 凭据 ID（创建 JWT 凭据后显示）
- `QWEATHER_PRIVATE_KEY`: 私钥内容（注意 JSON 中需要使用 `\n` 表示换行）
- `QWEATHER_API_HOST`: API 主机地址（必填，无默认值）

**注意**: 私钥内容需要替换为你实际生成的私钥，JSON 中所有换行符必须替换为 `\n`。

## 使用示例

配置完成后，你可以在 Claude 中直接询问：

- "北京今天天气怎么样？"
- "查询上海的7天天气预报"
- "深圳明天会下雨吗？"

## 可用工具

### 1. `get_current_weather(location: str, include_warning?: bool, include_air_quality?: bool, include_indices?: bool)`

获取指定城市的当前天气信息，包含天气预警、空气质量和天气指数。

**参数:**
- `location`: 城市名称（如"北京"、"上海"）
- `include_warning`: 是否包含天气预警（默认 true）
- `include_air_quality`: 是否包含空气质量（默认 true）
- `include_indices`: 是否包含天气指数（默认 true）

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
气压: 1020hPa
降水量: 0.0mm
能见度: 10km

空气质量:
  AQI: 45 (优)
  PM2.5: 12 μg/m³
  建议: 各类人群可正常活动。

今日指数:
  • 运动指数: 较适宜
  • 洗车指数: 适宜
  • 穿衣指数: 较冷
```

### 2. `get_weather_forecast(location: str, days: int = 7, include_air_quality?: bool, include_indices?: bool)`

获取指定城市的未来天气预报，包含空气质量和天气指数。

**参数:**
- `location`: 城市名称（如"北京"、"上海"）
- `days`: 预报天数，支持 3/7/10/15/30，默认 7 天
- `include_air_quality`: 是否包含空气质量预报（默认 true）
- `include_indices`: 是否包含天气指数（默认 true）

**返回示例:**
```
北京市 未来7天天气预报:

2024-01-16:
  天气: 晴
  温度: -2°C ~ 8°C
  风向: 北风 2级
  湿度: 35%
  紫外线: 弱
  空气质量: 45 (优)

2024-01-17:
  天气: 多云
  温度: 0°C ~ 6°C
  风向: 东北风 3级
  湿度: 50%
  紫外线: 中等

未来3天生活指数:
  • 运动指数: 较适宜
  • 洗车指数: 适宜
```

## 技术栈

- [FastMCP](https://github.com/jlowin/fastmcp): MCP 服务框架
- [httpx](https://www.python-httpx.org/): 异步 HTTP 客户端
- [Pydantic](https://docs.pydantic.dev/): 数据验证
- [PyJWT](https://pyjwt.readthedocs.io/): JWT Token 生成
- [cryptography](https://cryptography.io/): Ed25519 签名
- [uv](https://docs.astral.sh/uv/): Python 包管理器

## 注意事项

1. **API 调用限制**: 根据订阅等级有不同的调用限制
2. **数据延迟**: 实况数据相比真实物理世界有 5-20 分钟延迟
3. **Gzip 压缩**: API 返回 Gzip 压缩数据，已自动处理
4. **空气质量预报**: 最多显示3天预报数据
5. **天气指数**: 支持运动、洗车、穿衣、紫外线、感冒、空气污染扩散等指数
6. **私钥安全**: 私钥文件应设置 600 权限，不要提交到代码仓库
7. **系统时间**: 确保服务器时间准确，否则 JWT 鉴权会失败

## 错误处理

服务会自动处理以下情况：
- JWT Token 无效或过期（自动刷新）
- 私钥加载失败
- 环境变量配置缺失
- 城市名称不存在
- 网络连接超时
- API 返回错误码

## 许可证

MIT License

## 相关链接

- [和风天气开发文档](https://dev.qweather.com/docs/)
- [和风天气 JWT 鉴权文档](https://dev.qweather.com/docs/configuration/authentication/)
- [FastMCP 文档](https://github.com/jlowin/fastmcp)
- [MCP 协议规范](https://modelcontextprotocol.io/)
