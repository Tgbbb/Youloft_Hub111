import request from '@/utils/api'

// 推送对比工具配置
export function getPushCheckConfig() {
  return request({
    url: '/tools/push-check/config/',
    method: 'get'
  })
}

export function savePushCheckConfig(data) {
  return request({
    url: '/tools/push-check/config/',
    method: 'put',
    data
  })
}

// 触发一次推送对比检查
export function triggerPushCheck(data) {
  return request({
    url: '/tools/push-check/run/',
    method: 'post',
    data
  })
}

// 运行历史 / 详情
export function getPushCheckRuns(params) {
  return request({
    url: '/tools/push-check/runs/',
    method: 'get',
    params
  })
}

export function getPushCheckRun(id) {
  return request({
    url: `/tools/push-check/runs/${id}/`,
    method: 'get'
  })
}

// 清空运行历史
export function clearPushCheckRuns() {
  return request({
    url: '/tools/push-check/runs/',
    method: 'delete'
  })
}

// 同步确认工具
export function getSyncCheckConfig() {
  return request({
    url: '/tools/sync-check/config/',
    method: 'get'
  })
}

export function saveSyncCheckConfig(data) {
  return request({
    url: '/tools/sync-check/config/',
    method: 'put',
    data
  })
}

export function triggerSyncCheck(data) {
  return request({
    url: '/tools/sync-check/run/',
    method: 'post',
    data
  })
}

export function getSyncCheckRuns(params) {
  return request({
    url: '/tools/sync-check/runs/',
    method: 'get',
    params
  })
}

export function getSyncCheckToday() {
  return request({
    url: '/tools/sync-check/runs/today/',
    method: 'get'
  })
}

// 清空同步确认按天历史
export function clearSyncCheckRuns() {
  return request({
    url: '/tools/sync-check/runs/',
    method: 'delete'
  })
}

// 配置回复提醒工具
export function getReplyCheckConfig() {
  return request({
    url: '/tools/reply-check/config/',
    method: 'get'
  })
}

export function saveReplyCheckConfig(data) {
  return request({
    url: '/tools/reply-check/config/',
    method: 'put',
    data
  })
}

export function triggerReplyCheck(data) {
  return request({
    url: '/tools/reply-check/run/',
    method: 'post',
    data
  })
}

export function getReplyCheckRuns(params) {
  return request({
    url: '/tools/reply-check/runs/',
    method: 'get',
    params
  })
}

export function getReplyCheckToday() {
  return request({
    url: '/tools/reply-check/runs/today/',
    method: 'get'
  })
}

export function clearReplyCheckRuns() {
  return request({
    url: '/tools/reply-check/runs/',
    method: 'delete'
  })
}
