"""复制本文件为 config.py 并填入真实凭据。

config.py 已被 .gitignore 排除，不会被提交或上传。
"""

# 企业微信群机器人 webhook：
# 手机/电脑端群聊 → 右键群设置 → 群机器人 → 添加机器人 → 复制 webhook 地址
WECHAT_WEBHOOK = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=替换成你的key'

# 和风天气凭据（https://console.qweather.com 注册，订阅「免费开发版」）：
# 控制台 → 项目管理 → 创建项目 → 项目内创建「API Key」凭据
QWEATHER_API_KEY = '替换成你的APIKey'

# 控制台 → 设置（或项目页）查看专属 API Host（形如 abc123.qweatherapi.com，不带 https:// 也可以）
QWEATHER_API_HOST = 'https://abc123.qweatherapi.com'
