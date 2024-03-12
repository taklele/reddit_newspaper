# reddit_newspaper
自动获取reddit信息处理为newspaper

## 工作流程
1. 从reddit 的 LocalLlama 获取10条最新的内容
2. 把内容交给 AI 处理，然后将处理后的内容写到 mysql。
3. 处理规则见代码中的 `custom_prompt`

## 环境变量
```
# .env
REDDIT_CLIENT_ID=""
REDDIT_CLIENT_SECRET=""
REDDIT_USER_AGENT=""
OPENAI_API_KEY=""
MYSQL_HOST=""
MYSQL_USER=""
MYSQL_PASSWORD=""
MYSQL_DB=""
```