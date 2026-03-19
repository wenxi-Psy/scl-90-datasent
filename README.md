# scl-90-datasent

一个支持 SCL-90 在线测评、CSV 导出、以及云端自动发送咨询师邮箱的单页应用。

## 当前推荐部署方式

- **前端**：部署到 GitHub Pages
- **后端**：单独部署 `server.py` 到可运行 Python 的主机或平台

> GitHub Pages 只能托管静态文件，不能直接执行 `server.py`。因此自动发送邮件必须依赖独立后端。

## 前端（GitHub Pages）配置

仓库中新增了 `config.js`。部署 GitHub Pages 前，请把里面的 `apiBaseUrl` 改成你后端服务的完整地址，例如：

```js
window.SCL90_APP_CONFIG = {
  apiBaseUrl: 'https://your-api.example.com'
};
```

前端会把自动发送请求发到：

- `https://your-api.example.com/api/send-report`
- `https://your-api.example.com/api/health`

## 后端本地运行

```bash
python server.py
```

默认访问地址：`http://localhost:3000`

## 后端环境变量

服务端通过 SMTP 自动发送邮件到咨询师邮箱 `wenxi_deng@qq.com`。启动前可设置以下环境变量：

- `SMTP_HOST`：SMTP 服务器地址
- `SMTP_PORT`：SMTP 端口，默认 `465`
- `SMTP_USER`：SMTP 登录账号
- `SMTP_PASS`：SMTP 登录密码 / 授权码
- `SMTP_FROM`：发件人邮箱，默认同 `SMTP_USER`
- `SMTP_USE_TLS`：是否使用 STARTTLS，`true` / `false`
- `COUNSELOR_EMAIL`：咨询师收件邮箱，默认 `wenxi_deng@qq.com`
- `ALLOWED_ORIGINS`：允许跨域访问后端的前端来源，逗号分隔；默认包含 `https://wenxi-psy.github.io`
- `RATE_LIMIT_MAX`：限流窗口内允许的最大发送次数，默认 `3`
- `RATE_LIMIT_WINDOW_SECONDS`：限流窗口秒数，默认 `1800`
- `MIN_COMPLETION_SECONDS`：最短完成时长，默认 `20`
- `MOCK_EMAIL=1`：启用模拟发信模式，便于本地测试接口而不真正发送邮件

## 联调建议

1. 先部署后端，并确认 `https://your-api.example.com/api/health` 能返回 JSON。
2. 再修改 `config.js` 中的 `apiBaseUrl` 并发布 GitHub Pages。
3. 打开 GitHub Pages 页面，生成报告并测试“自动发送给咨询师”。

## 说明

- 用户只有在结果页勾选“已同意上传给咨询师”后，才会调用云端发送接口。
- 如果自动发送失败，前端会自动下载 CSV，并提示用户人工发送给咨询师。
- 服务端包含基础防刷：同意校验、隐藏蜜罐字段、最短提交时长校验、以及基于 IP 的简单频率限制。
