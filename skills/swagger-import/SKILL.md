---
name: swagger-import
display_name: Swagger 文档导入
description: 解析 OpenAPI 文档并自动生成接口测试集合
enabled: true
order: 1
---

# Swagger 文档导入

## 执行流程
1. 询问用户要导入的 Swagger 文档 URL 或确认已上传的文件
2. 调用 `parse_swagger` 解析文档，获取所有接口
3. 按接口 tag 分组，每组调用 `create_collection` 创建集合
4. 每个接口调用 `create_api_test` 创建测试，包含：
   - 正常参数场景（期望 2xx）
   - 缺少必填参数的异常场景（期望 4xx）
   - 参数类型错误的异常场景（期望 4xx）
5. 完成后列出创建的集合和接口数量

## 注意事项
- 必须先确认用户所在项目和文档 URL
- 跳过已废弃（deprecated）的接口
- 生成的测试默认启用，用户后续可在接口管理页面调整
- 如果接口有认证要求，在 Headers 中标注需要 Token
