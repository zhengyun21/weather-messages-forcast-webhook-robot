# weather-messages-forcast-webhook-robot

基于**企业微信群机器人 webhook** 的定时天气预报推送脚本：每天固定时间自动触发（Windows 任务计划程序，或 GitHub Actions 云端定时），调用[和风天气](https://www.qweather.com/) API，把多个城市的**明日天气 + 生活指数 + 气象预警**拼成一条 markdown 消息推到群里。

单文件、纯 Python 标准库（3.10+），零第三方依赖，密钥全部走本地配置文件、不入库。

## 消息效果

```text
**明日天气（10月27日 周二）**
**☀ 广州**
>明天：晴，20~31℃，北风1-3级
>👔 穿衣·炎热：天气炎热，建议着短衫、短裙、短裤、薄型T恤衫等清凉夏季服装。
>🏃 运动·较适宜：天气较好，户外运动请注意防晒。
>🤧 感冒·少发：各项气象条件适宜，发生感冒机率较低。但请避免长期处于空调房间中，以防感冒。
>🧺 晾晒·极适宜：天气不错，适宜晾晒。抓紧时机把久未见阳光的衣物搬出来晒晒太阳吧！
>🚗 洗车·较适宜：较适宜洗车，未来一天无雨，风力较小，擦洗一新的汽车至少能保持一天。
（…每个城市一节；有气象预警时附加红色高亮行）
<font color="comment">数据来源：和风天气 · 更新于 10-26 16:11</font>
```

在群里实际渲染后：标题加粗、预警红色高亮、来源灰色小字。

## 功能

- **多城市**：配置列表里的每个城市一节，合并在一条消息里（默认广州/汕头/深圳）
- **明日天气**：天气现象、温度范围、风向风力
- **生活指数**：穿衣 👔、运动 🏃、感冒 🤧、晾晒 🧺、洗车 🚗（可自行增删，见下文）
- **气象预警**：当前生效的官方预警，红色高亮，最多显示 2 条
- **失败静默**：天气 API 与 webhook 各自失败重试 2 次（4xx 永久错误不重试），仍失败只写本地日志，不会往群里发报错
- **错过不补发**：18:30 电脑关机/睡眠则当天跳过，第二天照常

## 准备工作

1. **企业微信机器人 webhook**：进入目标群聊 → 群设置 → 群机器人 → 添加机器人 → 复制 webhook 地址（形如 `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx`）
2. **和风天气 API Key**（免费开发版，每天 1000 次调用，本脚本每个城市只用 4 次）：
   - 打开 [console.qweather.com](https://console.qweather.com) 注册并订阅「免费开发版」
   - 控制台 → 项目管理 → 创建项目 → 项目内创建「API Key」凭据
   - 控制台 → 设置，查看专属 API Host（形如 `https://abc123.qweatherapi.com`）

> 注意：新版和风账号必须使用**专属 API Host**，老的 `devapi.qweather.com` 等通用域名会返回 403 Invalid Host。

## 快速开始

```bash
git clone https://github.com/zhengyun21/weather-messages-forcast-webhook-robot.git
cd weather-messages-forcast-webhook-robot

# 填配置
cp config.example.py config.py
# 编辑 config.py，填入 webhook 地址、和风 API Key 与专属 API Host

# 验证
python weather_push.py --dry-run   # 只打印消息内容，不发群
python weather_push.py             # 立即真实推送一条
```

## 注册定时任务（Windows）

以管理员不需要、当前用户身份即可。任务计划默认「错过不补发」，与脚本设计一致：

```bat
schtasks /Create /TN "WeatherPush" /SC DAILY /ST 18:30 /F ^
    /TR "\"C:\Python314\python.exe\" \"C:\path\to\weather_push.py\""
```

- python 请写**绝对路径**（`where python` 查看），任务环境不继承终端的 PATH
- 立即触发一次验证调度链路：`schtasks /Run /TN "WeatherPush"`
- 查看下次运行时间：`schtasks /Query /TN "WeatherPush" /V /FO LIST`
- 修改推送时间：`schtasks /Change /TN "WeatherPush" /ST 19:30`
- 取消任务：`schtasks /Delete /TN "WeatherPush" /F`

## GitHub Actions 云端定时（可选，不依赖本机开机）

仓库自带 workflow（`.github/workflows/weather.yml`），在仓库 **Settings → Secrets and variables → Actions → New repository secret** 依次添加三个 secret 后即自动生效：

| Secret 名 | 值 |
|---|---|
| `WECHAT_WEBHOOK` | 企业微信机器人 webhook 完整地址 |
| `QWEATHER_API_KEY` | 和风天气 API Key |
| `QWEATHER_API_HOST` | 和风天气专属 API Host |

- 定时为 `cron '30 10 * * *'`——**cron 用 UTC**，即北京时间每天 18:30
- GitHub 调度是尽力而为，高峰期可能迟到几分钟到十几分钟；想要准点秒推就用下面的 Windows 任务计划
- 手动验证：仓库 Actions 页 → daily-weather-push → Run workflow
- 仓库连续 60 天无提交活动，GitHub 会自动停用定时并邮件提醒，到 Actions 页重新启用即可
- 与本机任务二选一切换：`schtasks /Change /TN "WeatherPush" /Disable`（停用）/ `/Enable`（恢复）

## 配置说明

全部密钥在 `config.py`（本地文件，已被 .gitignore 排除）：

| 字段 | 说明 |
|---|---|
| `WECHAT_WEBHOOK` | 企业微信群机器人 webhook 完整地址 |
| `QWEATHER_API_KEY` | 和风天气 API Key |
| `QWEATHER_API_HOST` | 和风天气专属 API Host |

脚本内可调的公开配置（`weather_push.py` 顶部）：

| 字段 | 默认值 | 说明 |
|---|---|---|
| `CITIES` | `['广州', '汕头', '深圳']` | 推送城市列表，城市名交给和风 GeoAPI 解析 |
| `RETRIES` | `2` | 每次网络调用失败后的额外重试次数 |

### 增删生活指数

`fetch_city` 里的 `type='1,2,3,9,14'` 是和风生活指数类型代码（一次查询可带多个），展示循环里的 `(type, emoji, 名称)` 三元组与之对应。常用代码：1 运动、2 洗车、3 穿衣、5 旅游、6 紫外线、8 舒适度、9 感冒、14 晾晒，完整列表见[和风生活指数文档](https://dev.qweather.com/docs/api/)。

## 目录结构

```text
├── .github/workflows/weather.yml  # GitHub Actions 云端定时（可选）
├── weather_push.py                # 主脚本（明日天气 + 生活指数 + 预警 + 重试日志）
├── config.example.py              # 配置模板，复制为 config.py 后填写
├── config.py                      # 本地真实凭据（不入库）
├── .gitignore
├── LICENSE                        # Apache-2.0
└── README.md
```

## 已知适配点

- **和风专属 Host 强制 gzip 返回**：无论客户端是否声明 `Accept-Encoding: identity`，脚本按响应体 gzip 魔数自动解压
- **旧版预警接口已弃用**：`/v7/warning/now` 在新专属 Host 上返回 403 Deprecated，本脚本使用新版 `weatheralert/v1/current/{lat}/{lon}`（按经纬度查询，标题取 `headline` 字段）

## License

[Apache-2.0](LICENSE) © 2026 zhengyun21
