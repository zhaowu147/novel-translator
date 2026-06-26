# 小说翻译发布流水线

## 项目简介

自动化抓取日语轻小说，通过 AI 翻译成阿拉伯语，发布到 Blogger 平台的小说阅读网站。

## 架构

```
日本小说网站 → 采集 → 日→英→阿两跳翻译 → Blogger API 发布
         (成为小说家吧)    (MiMo API)         
```

## 模块说明

| 模块 | 文件 | 功能 |
|------|------|------|
| 配置 | `config.py` | API 密钥、路径、Blog ID |
| 采集 | `scraper_syosetu.py` | 调用 syosetu API 搜索/获取小说，Jina Reader 抓取正文 |
| 翻译 | `translator.py` | MiMo API 日→英→阿两跳翻译 |
| 发布 | `publisher.py` | Blogger API v3 发布文章。
| 流水线 | `pipeline.py` | 主控：发现→翻译→发布 |

## 使用方法

```bash
cd D:/novel-pipeline/code

# 测试 API
python pipeline.py test

# 发现小说
python pipeline.py discover

# 翻译（limit: 本数, max_chapters: 每本最多章节）
python pipeline.py translate 1 3

# 发布
python pipeline.py publish 5

# 全流程一键运行
python pipeline.py run 1 3
```


## MiMo API

- Endpoint：`https://token-plan-cn.xiaomimimo.com/anthropic/v1/messages`
- Model：`mimo-v2.5-pro`
- 额度：约 4 亿，截止 2026-06-23 06:00

## 文件结构

```
D:/novel-pipeline/
├── code/
│   ├── config.py          # 配置
│   ├── scraper_syosetu.py # 采集
│   ├── translator.py      # 翻译
│   ├── publisher.py       # 发布
│   └── pipeline.py        # 主控
├── secrets/
│   ├── blogger_token.json # OAuth 令牌
│   └── client_secret_*.json
├── output/                # 翻译结果 JSON
├── tmp/
└── state.json             # 流水线状态
```
