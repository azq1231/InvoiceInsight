# Google OAuth 设置指南 - 云环境版本

## 🔧 问题说明

您的应用需要访问 Google Photos 和 Google Sheets API，因此需要正确配置 OAuth 2.0 认证。

**为什么需要这个设置？**  
应用运行在 Replit 云环境中，无法使用传统的 localhost 回调。我们使用 **Google OAuth Playground** 作为授权码接收器。

---

## ✅ 解决方案：配置 OAuth Playground Redirect URI

### 步骤 1：打开 Google Cloud Console

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 选择您的专案

### 步骤 2：配置 OAuth 2.0 凭证

1. 左侧选单 → **API 与服务** → **凭证**
2. 找到您的 **OAuth 2.0 客户端 ID**（应该已存在）
3. 点击编辑（铅笔图示）

### 步骤 3：添加 Redirect URI

在 **已授权的重新导向 URI** 区段，添加以下 URI：

```
https://developers.google.com/oauthplayground
```

**重要提示：**
- 必须使用 `https://` 协议
- 精确匹配，不要添加额外的斜线或路径
- 这是 Google 官方的 OAuth 测试工具

### 步骤 4：保存设置

点击「**保存**」按钮

---

## 🚀 使用应用程式

### 1. 登入流程（新版 - 使用 OAuth Playground）

配置完成后，按照以下步骤登入：

#### 步骤 1：打开授权链接
- 在应用侧边栏中，点击「**🔗 打开 Google 授权页面**」
- 这会在新标签页打开 Google 授权页面

#### 步骤 2：选择并授权
- 选择您的 Google 帐号
- 授权应用程式访问：
  - **Google Photos**（只读）
  - **Google Sheets**（读写）

#### 步骤 3：复制授权码
- 授权成功后，您会被导向 **OAuth Playground** 页面
- 页面 URL 中包含 `code=` 参数
- **复制整个授权码**（从 `code=` 后面到 `&` 或结束）

**范例：**
```
https://developers.google.com/oauthplayground/?code=4/0AanRRruabc123...xyz&scope=...
                                                     ↑↑↑ 复制这部分 ↑↑↑
```

#### 步骤 4：粘贴授权码
- 返回应用程式
- 将授权码粘贴到「**📋 授权码**」输入框
- 点击「**✅ 确认登入**」

#### 步骤 5：完成
- 系统验证授权码
- 登入成功后自动刷新页面

### 2. 如果登入失败

**常见问题排查：**

| 问题 | 解决方案 |
|-----|---------|
| **"redirect_uri_mismatch"** | 确认 Google Console 中的 URI 完全匹配 `https://developers.google.com/oauthplayground` |
| **"invalid_grant" 错误** | 点击「重新生成」按钮获取新的授权链接，然后重新授权 |
| **"Access blocked"** | 确认 OAuth 同意画面已配置，并添加您的 Email 为测试用户 |
| **"Client secrets not found"** | 确认 `config/client_secrets.json` 存在且格式正确 |
| **授权码过期** | 授权码只能使用一次且有时效性（通常 10 分钟），请重新获取 |

---

## 📋 完整 OAuth 设置检查清单

### Google Cloud Console
- [ ] 已启用 Google Photos Library API
- [ ] 已启用 Google Sheets API
- [ ] 已启用 Google Cloud Vision API（用于 OCR）
- [ ] 已创建 OAuth 2.0 客户端 ID（桌面应用程式类型）
- [ ] 已添加 Redirect URI: `http://localhost:8080/`
- [ ] OAuth 同意画面已配置
- [ ] 已添加测试用户 Email（开发阶段）

### 本地配置
- [ ] `config/client_secrets.json` 文件存在
- [ ] client_secrets.json 包含正确的 client_id 和 client_secret
- [ ] Streamlit 应用正在运行（port 5000）

---

## 🔒 安全注意事项

1. **永不提交机密资讯到 Git**
   - `config/client_secrets.json` 已在 `.gitignore` 中
   - OAuth token 存储在 `data/.token.json`（也在 .gitignore）

2. **Token 安全性**
   - Token 自动加密存储（使用 keyring 或文件备援）
   - Token 会自动刷新（refresh_token）
   - 登出时会清除所有凭证

3. **API 配额**
   - Google Photos API: 10,000 requests/day
   - Google Sheets API: 100 requests/100 seconds/user
   - Cloud Vision API: 1,000 requests/month（免费额度）

---

## 📝 替代方案（高级用户）

如果无法使用 localhost 回调（例如远程服务器），可以：

### 方案 A：使用 Streamlit 内置 OIDC（需要 Streamlit 1.42+）

不过，这个方法仅适用于身份认证，无法获取 API 访问 token。

### 方案 B：使用服务账号密钥

1. 创建服务账号
2. 下载 JSON 密钥文件
3. 设置环境变量 `GOOGLE_APPLICATION_CREDENTIALS`

**优点：** 无需用户交互
**缺点：** 无法访问个人 Google Photos（仅能访问共享资源）

---

## 🆘 需要帮助？

如果您遇到问题：

1. 检查日志：`data/logs/`
2. 查看控制台输出
3. 确认所有 API 已启用
4. 验证 `client_secrets.json` 格式

**日志文件位置：**
- 应用日志：`data/logs/app.log`
- OAuth 错误：查找 "Authentication failed" 讯息

---

## ✨ 成功登入后

登入成功后，您可以：

1. **📷 浏览 Google Photos**
   - 加载照片缩图
   - 选择要辨识的照片

2. **🔍 OCR 辨识**
   - 双引擎辨识（Google Vision + Tesseract）
   - 加权机率融合
   - 智能资料萃取

3. **✏️ 手动核对**
   - 编辑辨识结果
   - 验证总额
   - 修正错误

4. **💾 保存到 Google Sheets**
   - 自动创建试算表
   - 结构化资料输出
   - 完整审计追踪

---

**最后更新：** 2025-10-17  
**适用版本：** OCR 收支辨识系统 v2.0.0
