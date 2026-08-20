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
