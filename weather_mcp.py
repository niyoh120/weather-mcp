#!/usr/bin/env python3
"""
和风天气 MCP 服务
使用 FastMCP 框架实现的天气查询服务
使用 JWT Token 鉴权
"""

import asyncio
import os
import sys
import time
from datetime import datetime

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel

# 配置日志输出到 stderr
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

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
    lat: str = ""  # 纬度，用于预警和空气质量 API
    lon: str = ""  # 经度，用于预警和空气质量 API


class WeatherWarning(BaseModel):
    """天气预警数据模型"""

    sender_name: str
    event_type: str
    severity: str
    headline: str
    description: str
    instruction: str
    effective_time: str
    expire_time: str
    color: str


class AirQuality(BaseModel):
    """空气质量数据模型"""

    aqi: str
    category: str
    primary_pollutant: str
    pm25: str
    pm10: str
    no2: str
    o3: str
    co: str
    so2: str
    health_effect: str
    health_advice_general: str
    health_advice_sensitive: str


class WeatherIndex(BaseModel):
    """天气指数数据模型"""

    name: str
    category: str
    text: str


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


async def _get_city_info(city_name: str) -> tuple[str, str, str, str, str, str]:
    """
    获取城市完整信息（LocationID、名称、经纬度等）

    Args:
        city_name: 城市名称（如"北京"、"上海浦东"）

    Returns:
        (LocationID, 城市名称, 纬度, 经度, 省份, 城市/区县) 元组
    """
    # 调用城市搜索 API
    params = {
        "location": city_name,
        "lang": "zh",
    }

    data = await _make_request("/geo/v2/city/lookup", params)

    if not data.get("location") or len(data["location"]) == 0:
        raise Exception(f"未找到城市: {city_name}")

    city = data["location"][0]
    location_id = city.get("id", "")
    name = city.get("name", city_name)
    adm1 = city.get("adm1", "")
    adm2 = city.get("adm2", "")
    lat = city.get("lat", "")
    lon = city.get("lon", "")

    # 构造完整城市名（如"北京市"）
    display_name = name
    if adm1 and adm1 != name:
        display_name = f"{adm1}{name}"

    return location_id, display_name, lat, lon, adm1, adm2


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


async def _get_weather_warning(lat: str, lon: str) -> list[WeatherWarning]:
    """
    获取天气预警信息

    Args:
        lat: 纬度
        lon: 经度

    Returns:
        天气预警列表
    """
    if not lat or not lon:
        return []

    try:
        # 格式化坐标为最多2位小数
        lat_formatted = f"{float(lat):.2f}"
        lon_formatted = f"{float(lon):.2f}"

        endpoint = f"/weatheralert/v1/current/{lat_formatted}/{lon_formatted}"

        # 直接发送请求，不经过 _make_request（因为新 API 没有 code 字段）
        token = jwt_manager.get_token()
        response = await client.get(
            endpoint, headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        data = response.json()

        # 检查 zeroResult 字段
        metadata = data.get("metadata", {})
        if metadata.get("zeroResult", False):
            return []  # 没有预警数据

        warnings = []
        for alert in data.get("alerts", []):
            warning = WeatherWarning(
                sender_name=alert.get("senderName", ""),
                event_type=alert.get("eventType", {}).get("name", ""),
                severity=alert.get("severity", ""),
                headline=alert.get("headline", ""),
                description=alert.get("description", ""),
                instruction=alert.get("instruction", ""),
                effective_time=alert.get("effectiveTime", ""),
                expire_time=alert.get("expireTime", ""),
                color=alert.get("color", {}).get("code", ""),
            )
            warnings.append(warning)

        return warnings
    except Exception as e:
        logger.warning(f"获取天气预警失败: {e}")
        return []


async def _get_air_quality_current(lat: str, lon: str) -> AirQuality | None:
    """
    获取实时空气质量

    Args:
        lat: 纬度
        lon: 经度

    Returns:
        空气质量数据，失败返回 None
    """
    if not lat or not lon:
        return None

    try:
        # 格式化坐标为最多2位小数
        lat_formatted = f"{float(lat):.2f}"
        lon_formatted = f"{float(lon):.2f}"

        endpoint = f"/airquality/v1/current/{lat_formatted}/{lon_formatted}"

        # 直接发送请求，不经过 _make_request（因为新 API 没有 code 字段）
        token = jwt_manager.get_token()
        response = await client.get(
            endpoint, headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        data = response.json()

        indexes = data.get("indexes", [])
        if not indexes:
            return None

        # 使用第一个 AQI 数据（通常是当地标准）
        aqi_data = indexes[0]

        # 获取污染物数据
        pollutants = {p.get("code", "").lower(): p for p in data.get("pollutants", [])}

        def get_pollutant_value(code: str) -> str:
            p = pollutants.get(code.lower(), {})
            conc = p.get("concentration", {})
            return f"{conc.get('value', '')} {conc.get('unit', '')}".strip()

        # 安全获取嵌套字段
        primary_pollutant_data = aqi_data.get("primaryPollutant") or {}
        health = aqi_data.get("health") or {}
        advice = health.get("advice") or {}

        return AirQuality(
            aqi=str(aqi_data.get("aqiDisplay", "")),
            category=aqi_data.get("category", ""),
            primary_pollutant=primary_pollutant_data.get("name", ""),
            pm25=get_pollutant_value("pm2p5"),
            pm10=get_pollutant_value("pm10"),
            no2=get_pollutant_value("no2"),
            o3=get_pollutant_value("o3"),
            co=get_pollutant_value("co"),
            so2=get_pollutant_value("so2"),
            health_effect=health.get("effect", ""),
            health_advice_general=advice.get("generalPopulation", ""),
            health_advice_sensitive=advice.get("sensitivePopulation", ""),
        )
    except Exception as e:
        logger.warning(f"获取空气质量失败: {e}")
        return None


async def _get_air_quality_forecast(lat: str, lon: str) -> list[dict]:
    """
    获取空气质量预报（3天）

    Args:
        lat: 纬度
        lon: 经度

    Returns:
        每日空气质量预报列表
    """
    if not lat or not lon:
        return []

    try:
        # 格式化坐标为最多2位小数
        lat_formatted = f"{float(lat):.2f}"
        lon_formatted = f"{float(lon):.2f}"

        endpoint = f"/airquality/v1/daily/{lat_formatted}/{lon_formatted}"

        # 直接发送请求，不经过 _make_request（因为新 API 没有 code 字段）
        token = jwt_manager.get_token()
        response = await client.get(
            endpoint, headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        data = response.json()

        return data.get("days", [])
    except Exception as e:
        logger.warning(f"获取空气质量预报失败: {e}")
        return []


async def _get_weather_indices(
    location_id: str, days: str = "3d"
) -> list[WeatherIndex]:
    """
    获取天气指数预报

    Args:
        location_id: LocationID
        days: 预报天数 ("1d" 或 "3d")

    Returns:
        天气指数列表
    """
    try:
        endpoint = f"/v7/indices/{days}"
        params = {
            "location": location_id,
            "type": "1,2,3,5,8,9",  # 运动、洗车、穿衣、紫外线、感冒、空气污染扩散
            "lang": "zh",
        }
        data = await _make_request(endpoint, params)

        indices = []
        for item in data.get("daily", []):
            index = WeatherIndex(
                name=item.get("name", ""),
                category=item.get("category", ""),
                text=item.get("text", ""),
            )
            indices.append(index)

        return indices
    except Exception as e:
        logger.warning(f"获取天气指数失败: {e}")
        return []


@mcp.tool()
async def get_current_weather(
    location: str,
    include_warning: bool = True,
    include_air_quality: bool = True,
    include_indices: bool = True,
) -> str:
    """
    获取指定城市的当前天气，包含天气预警、空气质量和天气指数

    Args:
        location: 城市名称（如"北京"）
        include_warning: 是否包含天气预警（默认True）
        include_air_quality: 是否包含空气质量（默认True）
        include_indices: 是否包含天气指数（默认True）

    Returns:
        格式化后的当前天气信息，包含预警、空气质量和指数
    """
    try:
        # 获取城市完整信息
        location_id, city_name, lat, lon, adm1, adm2 = await _get_city_info(location)

        # 并行获取天气数据和其他信息
        weather_task = _make_request(
            "/v7/weather/now",
            {"location": location_id, "lang": "zh", "unit": "m"},
        )

        # 根据参数决定是否获取额外信息
        tasks = [weather_task]
        if include_warning:
            tasks.append(_get_weather_warning(lat, lon))
        if include_air_quality:
            tasks.append(_get_air_quality_current(lat, lon))
        if include_indices:
            tasks.append(_get_weather_indices(location_id, "1d"))

        # 等待所有请求完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 解析结果
        weather_data = results[0]
        if isinstance(weather_data, Exception):
            raise weather_data

        warning_list = results[1] if include_warning else []
        air_quality = results[2] if include_air_quality else None
        indices = results[3] if include_indices else []

        if "now" not in weather_data:
            return f"无法获取 {city_name} 的天气信息"

        now = weather_data["now"]
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

        # 添加天气预警
        if include_warning and warning_list and not isinstance(warning_list, Exception):
            result.append("\n⚠️ 天气预警:")
            for i, warning in enumerate(warning_list[:3], 1):  # 最多显示3条
                result.append(f"\n  {i}. {warning.headline}")
                result.append(f"     类型: {warning.event_type}")
                result.append(f"     级别: {warning.severity}")
                result.append(f"     描述: {warning.description[:100]}...")

        # 添加空气质量
        if (
            include_air_quality
            and air_quality
            and not isinstance(air_quality, Exception)
        ):
            result.append("\n🌫️ 空气质量:")
            result.append(f"  AQI: {air_quality.aqi} ({air_quality.category})")
            result.append(f"  首要污染物: {air_quality.primary_pollutant}")
            result.append(f"  PM2.5: {air_quality.pm25}")
            result.append(f"  PM10: {air_quality.pm10}")
            if air_quality.health_effect:
                result.append(f"  健康影响: {air_quality.health_effect}")
            if air_quality.health_advice_general:
                result.append(f"  建议: {air_quality.health_advice_general}")

        # 添加天气指数
        if include_indices and indices and not isinstance(indices, Exception):
            result.append("\n📊 今日指数:")
            for index in indices:
                result.append(f"  • {index.name}: {index.category}")
                if index.text:
                    result.append(f"    {index.text}")

        return "\n".join(result)

    except Exception as e:
        return f"获取天气失败: {str(e)}"


@mcp.tool()
async def get_weather_forecast(
    location: str,
    days: int = 7,
    include_air_quality: bool = True,
    include_indices: bool = True,
) -> str:
    """
    获取指定城市的未来天气预报，包含空气质量预报和天气指数

    Args:
        location: 城市名称（如"北京"）
        days: 预报天数，支持 3/7/10/15/30，默认 7 天
        include_air_quality: 是否包含空气质量预报（默认True）
        include_indices: 是否包含天气指数（默认True）

    Returns:
        格式化后的天气预报信息，包含空气质量和指数
    """
    try:
        # 验证 days 参数
        valid_days = [3, 7, 10, 15, 30]
        if days not in valid_days:
            days = 7  # 使用默认值

        # 获取城市完整信息
        location_id, city_name, lat, lon, adm1, adm2 = await _get_city_info(location)

        # 并行获取天气数据和其他信息
        weather_task = _make_request(
            f"/v7/weather/{days}d",
            {"location": location_id, "lang": "zh", "unit": "m"},
        )

        # 根据参数决定是否获取额外信息
        tasks = [weather_task]
        if include_air_quality:
            tasks.append(_get_air_quality_forecast(lat, lon))
        if include_indices:
            tasks.append(_get_weather_indices(location_id, "3d"))

        # 等待所有请求完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 解析结果
        data = results[0]
        if isinstance(data, Exception):
            raise data

        air_quality_days = results[1] if include_air_quality else []
        indices = results[2] if include_indices else []

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

            # 添加空气质量预报（仅前3天）
            if (
                include_air_quality
                and air_quality_days
                and not isinstance(air_quality_days, Exception)
                and i <= len(air_quality_days)
            ):
                aq_day = air_quality_days[i - 1]
                indexes = aq_day.get("indexes", [])
                if indexes:
                    aqi_data = indexes[0]
                    result.append(
                        f"   🌫️ 空气质量: {aqi_data.get('aqiDisplay', '')} ({aqi_data.get('category', '')})"
                    )

            result.append("")  # 空行分隔

        # 添加天气指数
        if include_indices and indices and not isinstance(indices, Exception):
            result.append("\n📊 未来3天生活指数:\n")
            # 按指数类型分组显示
            index_groups = {}
            for idx in indices:
                if idx.name not in index_groups:
                    index_groups[idx.name] = []
                index_groups[idx.name].append(idx)

            for name, idx_list in index_groups.items():
                result.append(f"  • {name}:")
                for idx in idx_list:
                    result.append(f"    {idx.category} - {idx.text}")

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
        logger.error("错误: JWT 鉴权初始化失败")
        logger.error("")
        logger.error("请检查以下环境变量:")

        if not PROJECT_ID:
            logger.error("  ❌ QWEATHER_PROJECT_ID: 未配置")
        else:
            logger.error("  ✓ QWEATHER_PROJECT_ID: 已配置")

        if not KEY_ID:
            logger.error("  ❌ QWEATHER_KEY_ID: 未配置")
        else:
            logger.error("  ✓ QWEATHER_KEY_ID: 已配置")

        if not PRIVATE_KEY and not PRIVATE_KEY_PATH:
            logger.error(
                "  ❌ 私钥: 未配置 (QWEATHER_PRIVATE_KEY 或 QWEATHER_PRIVATE_KEY_PATH)"
            )
        elif PRIVATE_KEY:
            logger.error("  ✓ 私钥: 已通过 QWEATHER_PRIVATE_KEY 配置")
        elif PRIVATE_KEY_PATH:
            if os.path.exists(PRIVATE_KEY_PATH):
                logger.error(f"  ✓ 私钥: 文件存在 ({PRIVATE_KEY_PATH})")
            else:
                logger.error(f"  ❌ 私钥: 文件不存在 ({PRIVATE_KEY_PATH})")

        logger.error("")
        logger.error("示例:")
        logger.error("  export QWEATHER_PROJECT_ID=xxx")
        logger.error("  export QWEATHER_KEY_ID=xxx")
        logger.error("  export QWEATHER_PRIVATE_KEY_PATH=/path/to/ed25519-private.pem")
        sys.exit(1)

    # 检查 API_HOST
    if not API_HOST:
        logger.error("错误: 未配置 QWEATHER_API_HOST 环境变量")
        logger.error("")
        logger.error("请设置 API 主机地址:")
        logger.error("  export QWEATHER_API_HOST=https://api.qweather.com")
        sys.exit(1)

    logger.info("✓ JWT 鉴权初始化成功")
    mcp.run()


if __name__ == "__main__":
    main()
