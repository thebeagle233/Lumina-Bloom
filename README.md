# Lumi / Lumina Bloom：让每一次走到户外，都长成一点变化

一款用像素植物、轻量记录与温和提醒，探索户外习惯养成的 Web App 原型。

**体验方式：** 下载后预览 `demo/`，或按下方说明运行完整应用。目前尚未配置公开体验链接。

## 1. Demo 简介

Lumi 把「今天在户外待了多久」转化为可记录、可回看、可累积的日常体验。用户手动记录户外时长，在日历里看见自己的轨迹，也让一株像素植物随记录逐步成长。

本仓库提供两个版本：

| 版本 | 用途 | 数据与能力 |
| --- | --- | --- |
| `demo/` 静态演示 | 快速预览、作品展示、Netlify 托管 | 示例天气与地点、本地规则提醒与聊天；无后端、真实 AI、网络数据或定位 |
| `lumi-web-app/` 完整应用 | 本地运行、继续开发、后端部署 | Flask API；可查询天气与附近地点，可选接入 OpenAI、DeepSeek 与独立的 Bloom 模型服务 |

静态演示首次进入包含示例历史记录，便于查看日历和植物成长效果；完整应用从空记录开始。记录时长不等于设备自动测得的日照量。

## 2. 创作思路

### 灵感来源

忙碌、久坐或缺少动力时，「出去走一小会儿」也容易被推迟。Lumi 希望给这个很小的行动一个容易开始、也容易看见反馈的入口。

### 想解决的问题

单纯累计分钟数缺少情感连接；固定的提醒也很难回应「今天很忙」或「现在没有心情」。我们希望记录足够轻，反馈足够直观，也让用户能够表达当下的状态。

### 为什么做这个方向

用像素植物承接积累，用月历呈现过程，再用可以接受或拒绝的提醒保留选择空间。Lumi 探索的是一种低压力的产品体验，目前尚未验证其习惯改善效果。

## 3. 主要功能

### LOG：从几分钟开始记录

以 5 分钟为步长调整户外时长，点击 `SAVE SESSION` 保存到当天。接受提醒会预填建议时长；实际记录仍由用户确认保存。拒绝提醒时可以选择忙碌、缺少动力或心情原因，为后续提示提供上下文。

### JOURNEY：看见自己的日常轨迹

按月查看记录热力日历，切换月份或点击日期查看当天时长。用户记录与拒绝原因保存在当前浏览器的 `localStorage` 中，不提供账号与跨设备同步。

### BLOOM：让记录长成一株植物

累计时长推动植物经历五个成长阶段，每累计 30 小时完成一次收获循环。Bloom 聊天提供陪伴式互动：静态版使用本地规则回复，完整版可连接单独配置的 OpenAI 兼容模型服务。

### LUMI LAB：展示反馈逻辑

查看近期拒绝原因及行为估计。页面中的压力、恢复负荷与行为概率是原型演示指标，并非传感器测量、医学判断或经验证的预测结果。

## 4. 快速体验

### 静态演示：不需要安装依赖或配置密钥

在仓库根目录运行（需要 Python 3.10+）：

```bash
python3 -m http.server 8000 --directory demo
```

Windows 可将 `python3` 替换为 `py -3`。浏览器打开 <http://localhost:8000>。修改源码后，可用 `python3 scripts/build_demo.py` 重新生成演示目录。

### 完整应用：Python 3.10+

macOS / Linux：

```bash
cd lumi-web-app
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python app.py
```

Windows PowerShell：

```powershell
cd lumi-web-app
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe app.py
```

浏览器打开 <http://127.0.0.1:5000>。默认使用规则提醒，无需模型密钥；天气和地点查询需要网络，查询失败时使用回退数据或空结果。Bloom 未配置可用模型服务时返回预设陪伴回复。

可选模型配置、GitHub 上传和上线步骤见 [部署说明](docs/DEPLOYMENT.md)。

## 5. 项目结构与验证

```text
.
├── README.md
├── demo/                    # 已生成、可直接托管的静态演示
├── docs/                    # 部署说明与界面截图
├── lumi-web-app/            # Flask 完整应用、服务、前端与测试
├── scripts/build_demo.py    # 仅依赖 Python 标准库的演示生成脚本
├── netlify.toml             # 构建并发布 demo/
└── render.yaml              # 可选 Flask 后端部署配置
```

在仓库根目录检查静态演示生成脚本（仅需 Python 标准库）：

```bash
python3 -m unittest discover -s tests -v
```

安装完整应用依赖后检查 Flask 应用：

```bash
cd lumi-web-app
python -m unittest discover -s tests -v
```

如已安装 Node.js 18+，还可在仓库根目录运行 `node --test tests/demo.test.cjs` 检查静态演示逻辑。验证范围见 [验证记录](docs/VALIDATION.md)。

## 6. 数据与当前边界

静态版完全在浏览器内演示，天气、地点和聊天均为模拟。完整应用可请求浏览器定位；定位不可用时使用香港默认坐标。天气来自 Open-Meteo，附近地点来自 OpenStreetMap / Overpass，地点候选不保证当时有阳光。

手动记录和拒绝原因保存在当前浏览器，清除站点数据会删除这些内容；聊天记录仅在当前页面会话中保留。完整版启用模型服务后，会向所配置的服务发送生成回复所需的上下文与对话。请用自己的新 API 密钥配置服务器环境变量，不要上传 `.env`。

Lumi 目前是产品原型，没有自动感测、后台系统通知或临床评估能力；植物成长阈值是交互设计参数，不是日照建议。

像素字体随项目附带，来源及许可证见 [第三方说明](THIRD_PARTY_NOTICES.md)。
