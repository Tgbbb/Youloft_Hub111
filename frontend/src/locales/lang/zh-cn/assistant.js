export default {
  // 侧边栏
  newChat: '新会话',
  historyChat: '历史会话',
  user: '用户',
  goHome: '返回首页',
  logout: '退出登录',
  deleteSessionConfirm: '确定删除此会话吗？',
  logoutConfirm: '确定要退出登录吗？',
  logoutTitle: '提示',
  confirm: '确定',
  cancel: '取消',
  loggedOut: '已退出登录',

  // 欢迎页
  title: 'TestHub Agent',
  subtitle: '我是您的智能测试协作者，可以帮您管理接口测试、创建测试用例、执行测试...',
  inputPlaceholder: '输入您的问题，按回车发送...',
  chatInputPlaceholder: '输入消息...',

  // 项目选择
  selectProject: '选择项目',
  noProject: '未选择项目',

  // 建议提示
  suggestions: {
    viewApis: '查看接口',
    viewApisQuestion: '帮我看看当前项目有哪些接口',
    createTest: '创建接口测试',
    createTestQuestion: '帮我给 /api/login 创建接口测试，包含异常场景的断言',
    parseDoc: '解析文档',
    parseDocQuestion: '帮我解析这个 Swagger 文档 https://api.example.com/swagger.json',
    runTest: '执行测试',
    runTestQuestion: '帮我执行一下用户模块的接口测试'
  },

  // 对话
  thinking: '思考中...',
  toolCalling: '调用工具: {name}',
  aiDisclaimer: '内容由 AI 生成，请仔细甄别',

  // 消息提示
  messages: {
    loadMessageFailed: '加载消息失败',
    sessionDeleted: '会话已删除',
    deleteSessionFailed: '删除会话失败',
    sendFailed: '发送失败，请重试',
    loadHistoryFailed: '加载历史失败'
  }
}
