# 情境词卡（Context WordCards）

一个支持 Android 和 Windows 桌面的英语词汇学习应用。用户批量导入单词后，AI 从整批词汇的整体关系出发，自动决定场景数量、名称和分类边界，并为新词寻找合适的已掌握旧词作为联想。

单词、复习进度、场景分类、人工调整和词语关联均保存在本地。已有分类不会自动重新调用 AI，只有用户点击“重新分类”才会更新。

## 主要功能

- 粘贴多个单词，每行一个
- 粘贴 `word: 释义`、制表符、等号、逗号等常见格式
- 导入 CSV 前两列
- 导入预览：显示有效项、已有词、本批重复、空行和格式错误
- AI 根据整批单词动态生成场景，不依赖预设分类列表
- 一个单词可以属于多个真正相关的场景
- 显示分类理由、无法判断项和多场景项
- 分类确认前后均可重命名、移动、合并和拆分场景
- 从熟悉或已掌握的旧词中生成自然联想、理由及双词例句
- 离线单词本与间隔复习
- 分类和关联持久保存
- API 密钥验证后安全保存，只需输入一次
- 多套 OpenAI 兼容 API 配置
- 兼容旧版 `words` 表和原有学习记录

## Android 安装

在仓库右侧的 **Releases** 中下载最新版 APK，在 Android 手机上点击安装。最低支持 Android 8.0（API 26）。

升级版沿用旧版应用 ID，以便覆盖安装并继续访问原有的私有 SQLite 数据。应用显示名称、文案、图标含义和业务流程均已改为通用的“情境词卡”。

## Windows 桌面版

需要 Python 3，并且系统自带 Tkinter：

```powershell
python desktop/app.py
```

也可以双击 `desktop/start_desktop.cmd`。在这个已有工作区中，桌面版会优先迁移原 `outputs/words.db`；新克隆的项目默认使用 `desktop/context_words.db`。

## 批量导入流程

1. 粘贴单词文本，或选择 CSV 文件。
2. 查看预览；已有单词和本批重复项自动跳过，空行忽略，格式问题单独列出。
3. 确认有效列表，不需要创建或选择场景。
4. AI 对整批单词生成词卡、动态场景、分类理由、无法判断项和旧词关联。
5. 在分类预览中重命名、移动、合并或拆分。
6. 确认分类。结果和人工调整立即保存在本地。

AI 返回的草稿也会保存。应用重开后可以继续上次导入，不会自动重复调用 API。

## 场景聚类规则

提示词要求 AI：

- 从整批词汇的整体语义关系决定场景
- 场景名称简短、自然、具体
- 避免为每个单词单独创建场景
- 合并含义重复的场景
- 允许真正合理的多场景归属
- 对无法准确判断的词明确列出
- 为每个归属提供一句分类理由

应用会验证 AI 返回的词是否都来自当前批次、每个词是否有唯一词卡、场景数量是否合理、场景成员是否有效，以及关联旧词是否确实存在于用户词库中。验证失败时不会覆盖已有结果。

## 新旧词联想

旧词可标记为“熟悉”或“已掌握”。AI 获取旧词时按掌握程度和复习阶段排序，优先使用掌握程度高的词。

关联依据包括相关场景、近反义、常见共现、自然短语、上下位关系，以及确实有助于记忆的发音或拼写关系。每条关联包含类型、中文理由和同时使用新旧两个单词的英文例句。找不到合理联系时允许没有关联。

## 数据结构与迁移

原有 `words(word, content, stage, due)` 数据完整保留。启动时只做增量迁移：

| 表 | 用途 |
| --- | --- |
| `words` | 原词卡和复习进度；新增 `mastery`、`created_batch` |
| `import_batches` | 导入批次及 parsed / draft / confirmed 状态 |
| `import_items` | 批次中的规范化单词和用户提供的释义 |
| `scenes` | AI 动态生成或用户调整后的场景 |
| `scene_words` | 多对多场景成员和分类理由 |
| `unclassified` | 无法准确判断的单词及理由 |
| `word_links` | 新词与旧词的关联、理由和例句 |
| `api_profiles` | 桌面端 API 地址、模型及协议，不包含密钥 |

迁移不会删除旧词、复习日期或阶段。

## API 设置与密钥

每套配置包括名称、HTTPS Base URL、模型名称、接口格式和 API Key。支持 Responses 与 Chat Completions 的 OpenAI 兼容非流式接口。

- Android 使用 Android Keystore 生成设备内 AES-GCM 密钥，加密后保存 API Key。
- Windows 使用当前 Windows 用户的 DPAPI 加密密钥。
- 页面、日志和错误信息不显示完整密钥。
- 当前个人调试版本允许在 API 设置页截图；API Key 输入框仍使用密码遮罩。
- 修改密钥时重新验证；清除密钥不会影响单词、分类或关联。
- 地址、模型和协议可以保存；词库备份不包含 API 密钥。

首次保存或修改密钥时，应用发送一个很小的验证请求。验证成功后才保存。密钥失效时请求会提示重新设置。

Android 手机直接连接所填写的 API，不会经过电脑。电脑正在使用的系统代理不会自动共享给手机；服务商需要代理或 VPN 时，必须在手机端启用。应用会分别提示域名解析失败、HTTPS 证书失败、连接被拒绝和请求超时，便于定位网络问题。

## 项目结构

```text
app/src/main/java/com/gongdi/wordcards/
├── MainActivity.java    # Android 界面与业务流程
├── DataStore.java       # 数据迁移和场景/关联持久化
├── ImportParser.java    # 粘贴文本与 CSV 解析
├── ApiClient.java       # 两种兼容 API、结构化输出及校验
├── KeyVault.java        # Android Keystore 加密保存密钥
└── Review.java          # 单词规范化和复习日期

desktop/
├── app.py               # Windows Tkinter 桌面界面
├── core.py              # 桌面数据、API、迁移和 DPAPI
└── start_desktop.cmd
```

## Android 构建

仓库包含 Android Studio Gradle 配置，也提供已验证的独立构建脚本。需要 Python 3、JDK、Android Build Tools 35 和 Android Platform 35：

```powershell
python build_apk.py `
  --java "JDK目录" `
  --tools "Android Build Tools目录" `
  --platform "Android Platform目录" `
  --work "临时构建目录" `
  --out "context-wordcards.apk"
```

脚本完成 Java 编译、DEX 转换、资源打包、ZIP 对齐和 APK 签名。`--work` 中的签名文件必须保存，后续版本才能覆盖安装。

## 安全与兼容范围

应用当前支持 HTTPS + Bearer API Key，以及 OpenAI 兼容的 Responses 或 Chat Completions JSON 返回。部分服务商使用专有认证或不支持 JSON Schema，需要针对该服务商单独适配。

不要把 API 密钥写入源码、提交记录或 Issue。面向多人公开分发前，仍建议增加服务端代理、账户限额和滥用保护。

结构化输出设计参考 [OpenAI 官方 Structured Outputs 文档](https://developers.openai.com/api/docs/guides/structured-outputs)。
