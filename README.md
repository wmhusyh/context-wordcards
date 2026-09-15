# 工地词卡（WordCards）

一个面向英语初学者的 Android 单词学习应用。单词、词卡和复习进度全部保存在手机本地；电脑关机后仍可使用。生成新词卡时，可以自由切换 OpenAI 兼容 API。

## 功能

- 离线单词本：添加、搜索、查看和删除单词
- 离线复习：根据“认识 / 有点模糊 / 不认识”安排下一次复习
- AI 生成词卡：生成词义、词性、简单解释、施工场景例句、记忆提示和小测试
- 多套 API 配置：保存并切换接口地址、模型名称和接口格式
- 两种接口格式：Chat Completions 与 Responses
- 手动添加：没有 API 或没有网络时也能录入单词
- 备份与恢复：通过 JSON 文件导出、导入词库
- 内置示例：`scaffold`、`concrete`、`helmet`

## 安装

在 GitHub 仓库右侧的 **Releases** 中下载最新版 APK，传到 Android 手机后点击安装。系统可能要求允许文件管理器“安装未知应用”。

最低支持 Android 8.0（API 26）。当前版本是个人试用版，尚未上架应用商店。

## 使用 API

打开应用右上角的“API 设置”，填写：

| 配置项 | 说明 |
| --- | --- |
| 配置名称 | 自定义名称，例如“日常模型”或“备用服务商” |
| Base URL | 服务商提供的 HTTPS 基础地址或完整接口地址 |
| 模型名称 | 服务商支持的准确模型 ID |
| 接口格式 | Chat Completions 或 Responses |
| API Key | 对应服务商的密钥 |

以 OpenAI 为例，Base URL 可填写 `https://api.openai.com/v1`。应用会根据所选格式添加 `/chat/completions` 或 `/responses`。也可以直接填写完整接口地址。

兼容范围是 **HTTPS + Bearer API Key + OpenAI 兼容的非流式响应**。部分服务商有专有认证或不同的数据格式，需要单独适配。

### 密钥与隐私

- API 密钥只保存在应用当前运行的内存中，不写入安装包、词库或备份文件。
- 应用被系统结束后，需要重新输入密钥。
- API 设置页面禁止系统截图，避免密钥出现在截图和最近任务缩略图中。
- 生成新词时，密钥和待学习单词会直接发送给你选择的 API 服务商。
- 已保存的词卡直接从手机读取，不会重复调用 API。

## 复习规则

新词当天进入复习列表：

- 认识：间隔依次为 1、3、7、14、30 天，之后保持 30 天
- 有点模糊：明天复习，保留当前阶段
- 不认识：明天复习，并重置阶段

这是一套便于理解的入门规则，目前没有主动通知或 AI 自动评分。

## 数据与备份

词库保存在 Android 应用内部的 SQLite 数据库。卸载应用或清除应用数据会删除词库，请定期在“单词本”中导出 JSON 备份。

导入备份时，同名单词会保留手机中的现有内容和复习进度，不会覆盖。

## 项目结构

```text
app/src/main/
├── AndroidManifest.xml
├── assets/demo.json                  # 三张离线示例词卡
├── java/com/gongdi/wordcards/
│   ├── MainActivity.java             # 界面、SQLite、API 配置、备份
│   ├── ApiClient.java                # API 请求及返回校验
│   └── Review.java                   # 单词规范化和复习日期
└── res/                              # 主题和应用图标
```

这是一个原生 Java Android 项目，没有把 Python 网页服务嵌入 APK。

## 构建

仓库包含 Android Studio 使用的 Gradle 配置，也包含已经验证过的无 Gradle 构建脚本。

### Android Studio

1. 使用 Android Studio 打开仓库目录。
2. 安装 Android SDK Platform 35。
3. 使用 JDK 17 和兼容的 Gradle 版本同步项目。
4. 通过 **Build > Build APK(s)** 构建。

Gradle 配置路径尚未在当前开发机完整执行；当前 APK 使用下面的脚本路径构建并验证。

### 构建脚本

需要 Python 3、JDK、Android Build Tools 35 和 Android Platform 35：

```powershell
python build_apk.py `
  --java "JDK目录" `
  --tools "Android Build Tools目录" `
  --platform "Android Platform目录" `
  --work "临时构建目录" `
  --out "wordcards.apk"
```

脚本会完成 Java 编译、DEX 转换、资源打包、ZIP 对齐、APK 签名和签名验证。开发签名生成在 `--work` 指定的目录中，必须妥善保存，才能让后续版本覆盖安装。

## 已验证范围

- APK v2/v3 签名校验通过
- 包名：`com.gongdi.wordcards`
- 最低 Android 版本：8.0（API 26）
- 目标 SDK：35
- 24 项核心逻辑检查通过，包括 API 地址切换、非法地址拒绝、两种请求格式、返回解析和复习日期

尚未完成真实安卓手机的安装和界面验证，也未使用真实密钥验证不同服务商。欢迎在 Issues 中附上手机系统版本和错误文字反馈问题，请勿上传 API 密钥。

## 开发计划

- 真机适配和稳定性修复
- 每日复习通知
- 更成熟的间隔重复算法
- 词卡编辑
- 发音与语音练习
- 正式发布签名和应用商店构建

## 安全提醒

不要把 API 密钥写进源码、提交记录或 Issue。发布给更多用户使用前，建议增加服务端密钥代理、账户限额和滥用保护。
