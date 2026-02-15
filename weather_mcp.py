#!/usr/bin/env python3
"""
和风天气 MCP 服务
使用 FastMCP 框架实现的天气查询服务
使用 JWT Token 鉴权
"""

import os
import sys
import time
from datetime import datetime

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel

# 创建 MCP 服务实例
mcp = FastMCP("weather")


class JWTAuthManager:
    """JWT Token 管理器 - 使用和风天气 JWT 鉴权"""

    TOKEN_EXPIRY = 82800  # 23小时（留1小时缓冲）
    REFRESH_MARGIN = 300  # 提前5分钟刷新

    def __init__(self, project_id: str, key_id: str, private_key_pem: str):
        self.project_id = project_id
        self.key_id = key_id
        self.private_key = self._load_private_key(private_key_pem)
        self._token: str | None = None
        self._expiry: int = 0

    def _load_private_key(self, pem_content: str):
        """加载 Ed25519 私钥"""
        from cryptography.hazmat.primitives import serialization

        try:
            return serialization.load_pem_private_key(
                pem_content.encode(), password=None
            )
        except Exception as e:
            raise ValueError(f"私钥加载失败: {e}")

    def get_token(self) -> str:
        """获取有效 Token（自动刷新）"""
        now = int(time.time())
        if not self._token or now >= (self._expiry - self.REFRESH_MARGIN):
            self._token = self._generate_token(now)
        return self._token

    def _generate_token(self, now: int) -> str:
        """生成新 Token"""
        import jwt

        self._expiry = now + self.TOKEN_EXPIRY
        headers = {"kid": self.key_id}
        payload = {
            "sub": self.project_id,
            "iat": now - 30,  # 提前30秒防止时间误差
            "exp": self._expiry,
        }
        return jwt.encode(payload, self.private_key, algorithm="EdDSA", headers=headers)


# JWT 配置加载
PROJECT_ID = os.getenv("QWEATHER_PROJECT_ID", "")
KEY_ID = os.getenv("QWEATHER_KEY_ID", "")
PRIVATE_KEY = os.getenv("QWEATHER_PRIVATE_KEY", "")
PRIVATE_KEY_PATH = os.getenv("QWEATHER_PRIVATE_KEY_PATH", "")
API_HOST = os.getenv("QWEATHER_API_HOST", "")

# 初始化 JWT 管理器（如果配置完整则自动初始化）
jwt_manager: JWTAuthManager | None = None


def _init_jwt_manager() -> JWTAuthManager | None:
    """初始化 JWT 管理器"""
    global jwt_manager

    if not PROJECT_ID or not KEY_ID:
        return None

    # 获取私钥（优先使用直接配置的私钥内容）
    private_key = None
    if PRIVATE_KEY:
        # 直接配置的私钥内容
        private_key = PRIVATE_KEY.replace("\\n", "\n")
    elif PRIVATE_KEY_PATH and os.path.exists(PRIVATE_KEY_PATH):
        # 从文件读取私钥
        try:
            with open(PRIVATE_KEY_PATH, "r") as f:
                private_key = f.read()
        except Exception:
            return None
    else:
        return None

    try:
        jwt_manager = JWTAuthManager(PROJECT_ID, KEY_ID, private_key)
        return jwt_manager
    except Exception:
        return None


# HTTP 客户端（延迟初始化）
client: httpx.AsyncClient | None = None


def _init_http_client() -> httpx.AsyncClient | None:
    """初始化 HTTP 客户端"""
    global client
    if not API_HOST:
        return None
    client = httpx.AsyncClient(
        base_url=API_HOST,
        headers={"Accept-Encoding": "gzip"},
        timeout=30.0,
    )
    return client


# 尝试自动初始化
_init_jwt_manager()
_init_http_client()


class CurrentWeather(BaseModel):
    """当前天气数据模型"""

    location: str
    obs_time: str
    temp: str
    feels_like: str
    text: str
    wind_dir: str
    wind_scale: str
    humidity: str
    precip: str
    vis: str
    pressure: str = ""


class DailyForecast(BaseModel):
    """每日预报数据模型"""

    fx_date: str
    temp_max: str
    temp_min: str
    text_day: str
    text_night: str
    wind_dir_day: str
    wind_scale_day: str
    humidity: str
    precip: str
    uv_index: str


class CityInfo(BaseModel):
    """城市信息数据模型"""

    name: str
    location_id: str
    adm1: str
    adm2: str


async def _make_request(endpoint: str, params: dict) -> dict:
    """
    发送 API 请求并处理响应

    Args:
        endpoint: API 端点路径
        params: 查询参数

    Returns:
        API 响应数据

    Raises:
        Exception: 当 API 调用失败时
    """
    global client

    if jwt_manager is None:
        raise Exception("JWT 管理器未初始化")

    if client is None:
        if not API_HOST:
            raise Exception("QWEATHER_API_HOST 未配置")
        client = httpx.AsyncClient(
            base_url=API_HOST,
            headers={"Accept-Encoding": "gzip"},
            timeout=30.0,
        )

    try:
        # 获取 JWT Token 并发送请求
        token = jwt_manager.get_token()
        response = await client.get(
            endpoint, params=params, headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code") != "200":
            error_msg = f"API 错误: 状态码 {data.get('code')}"
            if data.get("code") == "401":
                error_msg = "JWT Token 无效或已过期"
            elif data.get("code") == "402":
                error_msg = "API 调用次数已用完"
            elif data.get("code") == "404":
                error_msg = "请求的资源不存在"
            raise Exception(error_msg)

        return data
    except httpx.TimeoutException:
        raise Exception("请求超时，请检查网络连接")
    except httpx.HTTPStatusError as e:
        raise Exception(f"HTTP 错误: {e.response.status_code}")
    except Exception as e:
        raise Exception(f"请求失败: {str(e)}")


async def _get_location_id(location: str) -> tuple[str, str]:
    """
    获取 LocationID 和城市名称

    Args:
        location: 城市名称或 LocationID

    Returns:
        (LocationID, 城市名称) 元组
    """
    # 如果 location 是纯数字，则认为是 LocationID
    if location.isdigit():
        return location, location

    # 否则调用城市搜索 API
    params = {
        "location": location,
        "lang": "zh",
    }

    data = await _make_request("/geo/v2/city/lookup", params)

    if not data.get("location") or len(data["location"]) == 0:
        raise Exception(f"未找到城市: {location}")

    city = data["location"][0]
    location_id = city.get("id", "")
    city_name = city.get("name", location)

    if city.get("adm1") and city.get("adm1") != city_name:
        city_name = f"{city['adm1']}{city_name}"

    return location_id, city_name


async def _search_city(city_name: str) -> list[CityInfo]:
    """
    搜索城市信息（内部函数）

    Args:
        city_name: 城市名称（如"北京"、"上海"）

    Returns:
        城市信息列表

    Raises:
        Exception: 当搜索失败或未找到城市时
    """
    params = {
        "location": city_name,
        "lang": "zh",
    }

    data = await _make_request("/geo/v2/city/lookup", params)

    if not data.get("location") or len(data["location"]) == 0:
        raise Exception(f"未找到城市: {city_name}")

    cities = []
    for city in data["location"][:10]:  # 最多返回10个结果
        city_info = CityInfo(
            name=city.get("name", ""),
            location_id=city.get("id", ""),
            adm1=city.get("adm1", ""),
            adm2=city.get("adm2", ""),
        )
        cities.append(city_info)

    return cities


@mcp.tool()
async def get_current_weather(location: str) -> str:
    """
    获取指定城市的当前天气

    Args:
        location: 城市名称（如"北京"）或 LocationID（如"101010100"）

    Returns:
        格式化后的当前天气信息
    """
    try:
        # 获取 LocationID 和城市名称
        location_id, city_name = await _get_location_id(location)

        # 调用实时天气 API
        params = {
            "location": location_id,
            "lang": "zh",
            "unit": "m",  # 公制单位
        }

        data = await _make_request("/v7/weather/now", params)

        if "now" not in data:
            return f"无法获取 {city_name} 的天气信息"

        now = data["now"]
        weather = CurrentWeather(
            location=city_name,
            obs_time=now.get("obsTime", ""),
            temp=now.get("temp", ""),
            feels_like=now.get("feelsLike", ""),
            text=now.get("text", ""),
            wind_dir=now.get("windDir", ""),
            wind_scale=now.get("windScale", ""),
            humidity=now.get("humidity", ""),
            precip=now.get("precip", ""),
            vis=now.get("vis", ""),
            pressure=now.get("pressure", ""),
        )

        # 格式化输出
        result = [
            f"📍 城市: {weather.location}",
            f"🕐 观测时间: {weather.obs_time}",
            f"🌡️ 温度: {weather.temp}°C",
            f"🤒 体感温度: {weather.feels_like}°C",
            f"☁️ 天气: {weather.text}",
            f"🧭 风向: {weather.wind_dir}",
            f"💨 风力: {weather.wind_scale}级",
            f"💧 湿度: {weather.humidity}%",
        ]

        if weather.pressure:
            result.append(f"📊 气压: {weather.pressure}hPa")

        result.extend(
            [
                f"🌧️ 降水量: {weather.precip}mm",
                f"👁️ 能见度: {weather.vis}km",
            ]
        )

        return "\n".join(result)

    except Exception as e:
        return f"获取天气失败: {str(e)}"


@mcp.tool()
async def get_weather_forecast(location: str, days: int = 7) -> str:
    """
    获取指定城市的未来天气预报

    Args:
        location: 城市名称（如"北京"）或 LocationID（如"101010100"）
        days: 预报天数，支持 3/7/10/15/30，默认 7 天

    Returns:
        格式化后的天气预报信息
    """
    try:
        # 验证 days 参数
        valid_days = [3, 7, 10, 15, 30]
        if days not in valid_days:
            days = 7  # 使用默认值

        # 获取 LocationID 和城市名称
        location_id, city_name = await _get_location_id(location)

        # 调用每日预报 API
        params = {
            "location": location_id,
            "lang": "zh",
            "unit": "m",
        }

        endpoint = f"/v7/weather/{days}d"
        data = await _make_request(endpoint, params)

        if "daily" not in data or not data["daily"]:
            return f"无法获取 {city_name} 的天气预报"

        # 格式化输出
        result = [f"📍 {city_name} 未来{days}天天气预报:\n"]

        for i, day in enumerate(data["daily"][:days], 1):
            forecast = DailyForecast(
                fx_date=day.get("fxDate", ""),
                temp_max=day.get("tempMax", ""),
                temp_min=day.get("tempMin", ""),
                text_day=day.get("textDay", ""),
                text_night=day.get("textNight", ""),
                wind_dir_day=day.get("windDirDay", ""),
                wind_scale_day=day.get("windScaleDay", ""),
                humidity=day.get("humidity", ""),
                precip=day.get("precip", ""),
                uv_index=day.get("uvIndex", ""),
            )

            # 获取星期几
            try:
                date_obj = datetime.strptime(forecast.fx_date, "%Y-%m-%d")
                weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][
                    date_obj.weekday()
                ]
            except Exception:
                weekday = ""

            # UV 指数描述
            uv_desc = ""
            if forecast.uv_index:
                uv_level = int(forecast.uv_index)
                if uv_level <= 2:
                    uv_desc = "弱"
                elif uv_level <= 5:
                    uv_desc = "中等"
                elif uv_level <= 7:
                    uv_desc = "强"
                else:
                    uv_desc = "很强"

            result.extend(
                [
                    f"{i}. 📅 {forecast.fx_date} {weekday}",
                    f"   ☁️ 天气: {forecast.text_day}",
                    f"   🌙 夜间: {forecast.text_night}",
                    f"   🌡️ 温度: {forecast.temp_min}°C ~ {forecast.temp_max}°C",
                    f"   🧭 风向: {forecast.wind_dir_day} {forecast.wind_scale_day}级",
                    f"   💧 湿度: {forecast.humidity}%",
                ]
            )

            if forecast.precip and float(forecast.precip) > 0:
                result.append(f"   🌧️ 降水: {forecast.precip}mm")

            if uv_desc:
                result.append(f"   ☀️ 紫外线: {uv_desc} ({forecast.uv_index})")

            result.append("")  # 空行分隔

        return "\n".join(result)

    except Exception as e:
        return f"获取天气预报失败: {str(e)}"


def main():
    """主函数"""
    global jwt_manager

    # 尝试初始化 JWT 管理器
    if jwt_manager is None:
        _init_jwt_manager()

    # 检查是否成功初始化
    if jwt_manager is None:
        print("错误: JWT 鉴权初始化失败", file=sys.stderr)
        print("\n请检查以下环境变量:", file=sys.stderr)

        if not PROJECT_ID:
            print("  ❌ QWEATHER_PROJECT_ID: 未配置", file=sys.stderr)
        else:
            print("  ✓ QWEATHER_PROJECT_ID: 已配置", file=sys.stderr)

        if not KEY_ID:
            print("  ❌ QWEATHER_KEY_ID: 未配置", file=sys.stderr)
        else:
            print("  ✓ QWEATHER_KEY_ID: 已配置", file=sys.stderr)

        if not PRIVATE_KEY and not PRIVATE_KEY_PATH:
            print(
                "  ❌ 私钥: 未配置 (QWEATHER_PRIVATE_KEY 或 QWEATHER_PRIVATE_KEY_PATH)",
                file=sys.stderr,
            )
        elif PRIVATE_KEY:
            print("  ✓ 私钥: 已通过 QWEATHER_PRIVATE_KEY 配置", file=sys.stderr)
        elif PRIVATE_KEY_PATH:
            if os.path.exists(PRIVATE_KEY_PATH):
                print(f"  ✓ 私钥: 文件存在 ({PRIVATE_KEY_PATH})", file=sys.stderr)
            else:
                print(f"  ❌ 私钥: 文件不存在 ({PRIVATE_KEY_PATH})", file=sys.stderr)

        print("\n示例:", file=sys.stderr)
        print("  export QWEATHER_PROJECT_ID=xxx", file=sys.stderr)
        print("  export QWEATHER_KEY_ID=xxx", file=sys.stderr)
        print(
            "  export QWEATHER_PRIVATE_KEY_PATH=/path/to/ed25519-private.pem",
            file=sys.stderr,
        )
        sys.exit(1)

    # 检查 API_HOST
    if not API_HOST:
        print("错误: 未配置 QWEATHER_API_HOST 环境变量", file=sys.stderr)
        print("\n请设置 API 主机地址:", file=sys.stderr)
        print("  export QWEATHER_API_HOST=https://api.qweather.com", file=sys.stderr)
        sys.exit(1)

    print("✓ JWT 鉴权初始化成功")
    mcp.run()


if __name__ == "__main__":
    main()
