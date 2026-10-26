#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
"""企业微信天气定时推送（数据源：和风天气）。

每天 18:30 由 Windows 任务计划程序触发，抓取配置城市的明日天气与生活指数，
拼成一条 markdown 推送到企业微信群机器人。错过 18:30（关机/睡眠）不补发。

首次使用:
    1. 复制 config.example.py 为 config.py，填入企业微信 webhook 与和风天气凭据
    2. python weather_push.py --dry-run   # 只打印消息，不发群
    3. python weather_push.py             # 立即真实推送一条

注册定时任务（python 路径写死，避免任务环境找不到 PATH）:
    schtasks /Create /TN "WeatherPush" /SC DAILY /ST 18:30 /F
        /TR "\"<python.exe 绝对路径>\" \"<本脚本绝对路径>\""

失败策略: 天气 API 与 webhook 各重试 2 次（4xx 类永久错误不重试），
仍失败只写 weather_push.log，群里保持安静。
"""

import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

# ---------------- 配置区 ----------------
try:
    from config import WECHAT_WEBHOOK, QWEATHER_API_KEY, QWEATHER_API_HOST
except ImportError:
    sys.exit('缺少 config.py：请先复制 config.example.py 为 config.py 并填入真实凭据')
CITIES = ['广州', '汕头', '深圳']
RETRIES = 2             # 网络调用失败后的额外重试次数
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'weather_push.log')
# ----------------------------------------

WEEKDAYS = '一二三四五六日'
# 按关键词粗配一个图标，从具体到宽泛排列
ICONS = (('雷', '⛈'), ('雪', '❄'), ('雨', '🌧'), ('雾', '🌫'),
         ('霾', '😷'), ('尘', '😷'), ('阴', '☁'), ('云', '⛅'), ('晴', '☀'))


def icon(text: str) -> str:
    return next((emoji for keyword, emoji in ICONS if keyword in text), '🌤')


def log(message: str) -> None:
    line = f'{datetime.now():%Y-%m-%d %H:%M:%S} {message}'
    with open(LOG_FILE, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')
    try:
        print(line)
    except OSError:
        pass  # 任务计划触发时没有控制台，打印失败不影响推送


def fetch_json(url: str, *, headers: dict | None = None,
               data: bytes | None = None, retries: int = RETRIES,
               timeout: int = 15) -> dict:
    last_error = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, data=data, headers=headers or {})
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                raw = resp.read()
                if raw[:2] == b'\x1f\x8b':  # 和风专属 Host 强制 gzip 返回
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode('utf-8'))
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:  # 客户端错误是永久性的，重试无意义
                detail = exc.read().decode('utf-8', 'replace')[:200]
                raise RuntimeError(f'HTTP {exc.code}: {detail}') from exc
            last_error = exc
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'重试 {retries} 次后仍失败: {last_error}')


def qweather_get(path: str, **params) -> dict:
    query = urllib.parse.urlencode(params)
    url = f'{QWEATHER_API_HOST}{path}?{query}'
    return fetch_json(url, headers={'X-QW-Api-Key': QWEATHER_API_KEY,
                                    'Accept-Encoding': 'identity'})


def qweather_v7(path: str, **params) -> dict:
    """v7 老版接口用 body 里的 code 字段表示业务状态。"""
    result = qweather_get(path, **params)
    if result.get('code') != '200':
        raise RuntimeError(f'和风接口 {path} 返回异常: {result.get("code")}')
    return result


def fetch_alerts(city: str, lat: float, lon: float) -> list:
    """取当前生效预警。新版预警接口按经纬度查询（最多两位小数）。"""
    try:
        result = qweather_get(f'/weatheralert/v1/current/{lat:.2f}/{lon:.2f}')
    except RuntimeError as exc:
        log(f'[{city}] 预警查询失败，按无预警处理: {exc}')
        return []
    return result.get('alerts', [])


def fetch_city(city: str) -> tuple[str, str]:
    """取一个城市的明日天气、生活指数与预警，返回 (markdown 小节, 和风数据更新时间)。"""
    location = qweather_v7('/geo/v2/city/lookup', location=city)['location'][0]
    weather = qweather_v7('/v7/weather/3d', location=location['id'])
    tomorrow = weather['daily'][1]
    alerts = fetch_alerts(city, float(location['lat']), float(location['lon']))
    try:
        daily_indices = qweather_v7('/v7/indices/3d', type='1,2,3,9,14',
                                    location=location['id'])['daily']
    except RuntimeError as exc:
        daily_indices = []
        log(f'[{city}] 生活指数查询失败，跳过: {exc}')
    advice = {item['type']: item for item in daily_indices
              if item['date'] == tomorrow['fxDate']}

    lines = [
        f"**{icon(tomorrow['textDay'])} {city}**",
        f">明天：{tomorrow['textDay']}，{tomorrow['tempMin']}~{tomorrow['tempMax']}℃，"
        f"{tomorrow['windDirDay']}{tomorrow['windScaleDay']}级",
    ]
    for idx_type, emoji, label in (('3', '👔', '穿衣'), ('1', '🏃', '运动'),
                                   ('9', '🤧', '感冒'), ('14', '🧺', '晾晒'),
                                   ('2', '🚗', '洗车')):
        item = advice.get(idx_type)
        if item:
            lines.append(f'>{emoji} {label}·{item["category"]}：{item["text"]}')
    for alert in alerts[:2]:
        lines.append(f'<font color="warning">⚠ {alert["headline"]}</font>')
    updated = datetime.fromisoformat(weather['updateTime']).strftime('%m-%d %H:%M')
    return '\n'.join(lines), updated


def build_message(sections: list[str], failed: list[str], updated: str | None) -> str:
    tomorrow = datetime.now() + timedelta(days=1)
    header = f'**明日天气（{tomorrow:%m月%d日} 周{WEEKDAYS[tomorrow.weekday()]}）**'
    parts = [header, '\n\n'.join(sections)]
    if failed:
        parts.append(f'<font color="comment">本次未获取到：{"、".join(failed)}</font>')
    if updated:
        parts.append(f'<font color="comment">数据来源：和风天气 · 更新于 {updated}</font>')
    return '\n'.join(parts)


def send_markdown(content: str) -> dict:
    payload = {'msgtype': 'markdown', 'markdown': {'content': content}}
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    result = fetch_json(WECHAT_WEBHOOK, data=body,
                        headers={'Content-Type': 'application/json'})
    if result.get('errcode') != 0:
        raise RuntimeError(f'推送被拒绝: {result}')
    return result


def main(argv: list[str]) -> int:
    if '--dry-run' not in argv and not (QWEATHER_API_KEY and QWEATHER_API_HOST):
        log('和风天气凭据未配置：请复制 config.example.py 为 config.py，'
            '填入 API Key 与专属 API Host（企业微信 webhook 在群机器人设置里获取）')
        return 1

    sections, failed, updated = [], [], None
    for city in CITIES:
        try:
            section, city_updated = fetch_city(city)
            sections.append(section)
            updated = updated or city_updated
        except Exception as exc:
            failed.append(city)
            log(f'[{city}] 获取失败: {exc}')
    if not sections:
        log('所有城市均获取失败，本次不推送')
        return 1

    content = build_message(sections, failed, updated)
    if '--dry-run' in argv:
        print(content)
        return 0

    try:
        send_markdown(content)
    except Exception as exc:
        log(f'webhook 推送失败: {exc}')
        return 1
    note = f'（未获取到：{"、".join(failed)}）' if failed else ''
    log(f'已推送 {len(sections)}/{len(CITIES)} 个城市{note}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
