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
