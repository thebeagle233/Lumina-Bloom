# 上传与部署 Lumi

项目包含可直接托管的静态演示 `demo/`，以及需要 Python 后端的完整应用 `lumi-web-app/`。第一次展示作品，建议先发布静态演示。

## 1. 上传到 GitHub

1. 解压 `lumi-upload.zip`（如使用压缩包），打开其中的 `lumi-upload` 文件夹。
2. 在 GitHub 新建空仓库，选择 **Add file → Upload files**。
3. 上传 `lumi-upload` **内部的文件与文件夹**，使根目录直接出现 `README.md`、`demo/`、`lumi-web-app/` 等内容。不要只上传 ZIP，也不要再套一层 `lumi-upload/`。
4. 确认部署配置与 `.gitignore` 一并上传，且没有 `.env`、真实密钥、虚拟环境或缓存，再提交。

如果文件选择器隐藏点号开头的文件，macOS 可按 `Command + Shift + .` 显示它们。`.env.example` 是配置模板，可以上传；`.env` 保存个人配置，不应上传。也可使用 Git 客户端提交相同目录结构。

## 2. Netlify：发布静态演示

### 手动上传

将 **`demo` 文件夹** 上传到 Netlify 的手动部署入口。文件夹内应直接包含 `index.html` 与静态资源。不要上传整个仓库、`lumi-web-app` 或压缩包。参见 [Netlify 文件夹部署说明](https://docs.netlify.com/deploy/create-deploys/#drag-and-drop)。

`demo/` 已生成，可直接发布。要更新演示，先在仓库根目录运行：

```bash
python3 scripts/build_demo.py
```

Windows 使用 `py -3 scripts/build_demo.py`。生成脚本仅使用 Python 标准库；重新生成后，上传更新后的 `demo/`。

### 连接 GitHub 自动部署

从 Git 导入仓库，并使用根目录的 `netlify.toml`：

| 设置 | 值 |
| --- | --- |
| Base directory | 仓库根目录（留空） |
| Build command | `python3 scripts/build_demo.py` |
| Publish directory | `demo` |

静态演示不需要 API 密钥、Flask 或环境变量。它使用示例天气、地点与本地规则回复；上线不会自动获得真实 AI、天气或定位能力。

部署完成后，打开平台实际生成的 HTTPS 地址，检查四个页面、保存记录、月份切换、聊天以及刷新后的记录保留，再把真实链接填到根 README 的「体验方式」中。

## 3. 本地运行完整应用

完整启动命令见 [README](../README.md#4-快速体验)。在 `lumi-web-app/` 中创建虚拟环境、安装 `requirements.txt`，将 `.env.example` 复制为 `.env`，运行 `python app.py`，然后打开 <http://127.0.0.1:5000>。

默认 `LLM_PROVIDER=heuristic`，提醒由规则生成。完整应用会尝试访问 Open-Meteo 与 Overpass；查询失败仍可记录时长和查看成长反馈。

### 可选：连接提醒模型

编辑本地 `.env`，选择一种提供方并填写自己的新密钥：

| 变量 | 用途 |
| --- | --- |
| `LLM_PROVIDER` | `heuristic`、`openai` 或 `deepseek` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI 密钥与账号可用的模型名称 |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` | DeepSeek 密钥与模型名称 |
| `DEEPSEEK_BASE_URL` | DeepSeek 兼容接口地址 |

模型名称以服务实际可用配置为准。调用失败时，应用回退到规则提醒；可从页面提供方信息及 `/api/health` 查看当前配置状态。

### 可选：连接 Bloom 聊天

Bloom 使用独立的 OpenAI 兼容聊天接口，不随 `LLM_PROVIDER` 自动切换。配置：

```dotenv
BLOOM_API_BASE_URL=http://127.0.0.1:8080/v1
BLOOM_API_KEY=local
BLOOM_MODEL=your-model-name
```

以上地址仅是本地服务示例，需要先自行启动支持该接口的模型服务，并填写实际模型名称与认证信息。未启动或配置不可用时，Bloom 返回预设陪伴回复。修改配置后重启 Flask。

## 4. Render：可选部署完整后端

根目录的 `render.yaml` 提供完整应用配置：导入 GitHub 仓库创建 Blueprint，核对根目录为 `lumi-web-app`，安装命令为 `pip install -r requirements.txt`，启动命令为：

```bash
gunicorn --bind 0.0.0.0:$PORT --timeout 90 app:app
```

平台流程见 [Render Blueprint 说明](https://render.com/docs/infrastructure-as-code)与 [Flask 部署说明](https://render.com/docs/deploy-flask)。

部署后使用 Render 生成的应用地址。该地址直接提供完整页面与 `/api/` 接口；Netlify 静态演示保持独立。

需要模型时，在平台的服务器环境变量中配置对应密钥与模型参数，并设置 `FLASK_DEBUG=0`。云端的 `127.0.0.1` 指向云端容器，无法访问你电脑上的 Bloom 服务；云端聊天需要部署可达的兼容接口。

此配置用于原型部署，不包含账号系统、请求限流或访问控制。公开接入计费模型前，应为服务增加访问控制和调用额度限制。

## 5. 更新与检查

修改完整应用前端后运行 `python3 scripts/build_demo.py`，将源码与生成的 `demo/` 一起提交。静态演示有意替换网络 API，新增后端能力需同时考虑演示逻辑。

在仓库根目录检查演示生成脚本：

```bash
python3 -m unittest discover -s tests -v
```

完整应用安装依赖后，在 `lumi-web-app/` 运行：

```bash
python -m unittest discover -s tests -v
```

人工检查：LOG 保存时长 → JOURNEY 查看当日 → BLOOM 查看成长 → LUMI LAB 查看反馈。静态版天气、地点、回复和 Lab 指标均用于演示；完整应用的 Lab 估计同样不代表真实生理测量或医学判断。
