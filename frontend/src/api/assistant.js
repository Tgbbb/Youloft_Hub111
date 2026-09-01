import request from '@/utils/api'

// 会话管理
export function getSessions(params) {
  return request({ url: '/assistant/sessions/', method: 'get', params })
}

export function createSession(data) {
  return request({ url: '/assistant/sessions/', method: 'post', data })
}

export function deleteSession(id) {
  return request({ url: `/assistant/sessions/${id}/`, method: 'delete' })
}

export function getSessionMessages(sessionId) {
  return request({ url: `/assistant/sessions/${sessionId}/messages/`, method: 'get' })
}

// Agent 聊天
export function sendAgentMessage(data) {
  return request({
    url: '/assistant/chat/send_message/',
    method: 'post',
    data,
    timeout: 120000,
  })
}

// Agent 配置管理
export function getAgentConfig() {
  return request({ url: '/assistant/config/agent/', method: 'get' })
}

export function createAgentConfig(data) {
  return request({ url: '/assistant/config/agent/', method: 'post', data })
}

export function updateAgentConfig(id, data) {
  return request({ url: `/assistant/config/agent/${id}/`, method: 'put', data })
}

export function testAgentConnection(data) {
  return request({
    url: '/assistant/config/agent/test_connection/',
    method: 'post',
    data,
    timeout: 30000,
  })
}

// Skills 管理
export function getSkills() {
  return request({ url: '/assistant/skills/', method: 'get' })
}

export function importSkill(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request({
    url: '/assistant/skills/import_skill/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function toggleSkill(name, enabled) {
  return request({
    url: '/assistant/skills/toggle_skill/',
    method: 'post',
    data: { name, enabled },
  })
}

export function deleteSkill(name) {
  return request({
    url: '/assistant/skills/delete_skill/',
    method: 'post',
    data: { name },
  })
}

// 知识库管理
export function listKnowledgeBases(params) {
  return request({ url: '/assistant/knowledge-bases/', method: 'get', params })
}

export function createKnowledgeBase(data) {
  return request({ url: '/assistant/knowledge-bases/', method: 'post', data })
}

export function updateKnowledgeBase(id, data) {
  return request({ url: `/assistant/knowledge-bases/${id}/`, method: 'put', data })
}

export function partialUpdateKnowledgeBase(id, data) {
  return request({ url: `/assistant/knowledge-bases/${id}/`, method: 'patch', data })
}

export function deleteKnowledgeBase(id) {
  return request({ url: `/assistant/knowledge-bases/${id}/`, method: 'delete' })
}

export function getActiveKnowledgeBase() {
  return request({ url: '/assistant/knowledge-bases/active/', method: 'get' })
}

export function getKnowledgeBaseDocuments(kbId) {
  return request({ url: `/assistant/knowledge-bases/${kbId}/documents/`, method: 'get' })
}

export function uploadKnowledgeDocument(kbId, formData, onUploadProgress) {
  return request({
    url: `/assistant/knowledge-bases/${kbId}/upload/`,
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
    onUploadProgress,
  })
}

export function deleteKnowledgeDocument(kbId, docId) {
  return request({
    url: `/assistant/knowledge-bases/${kbId}/documents/${docId}/`,
    method: 'delete',
  })
}

export function getKnowledgeBaseChunks(kbId, params) {
  return request({
    url: `/assistant/knowledge-bases/${kbId}/chunks/`,
    method: 'get',
    params,
  })
}

// 知识库变更日志（AI 自动新增/更新/版本/软删除记录）
export function getKnowledgeUpdateLogs(kbId, params) {
  return request({
    url: `/assistant/knowledge-bases/${kbId}/update-logs/`,
    method: 'get',
    params,
  })
}

// 知识库导出（Markdown）。返回 blob 用于下载。
export function exportKnowledgeBaseMarkdown(kbId, params) {
  return request({
    url: `/assistant/knowledge-bases/${kbId}/export/`,
    method: 'get',
    params,
    responseType: 'blob',
    timeout: 120000,
  })
}
