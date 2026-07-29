<template>
  <div class="assistant-layout">
    <!-- 左侧侧边栏 -->
    <div class="sidebar">
      <div class="new-chat-btn-wrapper">
        <el-button type="primary" class="new-chat-btn" @click="startNewChat" :icon="Plus">
          {{ $t('assistant.newChat') }}
        </el-button>
      </div>

      <div class="history-list">
        <div class="history-label">{{ $t('assistant.historyChat') }}</div>
        <div class="session-scroll-area">
          <div
            v-for="session in historySessionsDescending"
            :key="session.id"
            :class="['session-item', { active: currentSession?.id === session.id }]"
            @click="switchToSession(session)"
          >
            <div class="session-title-wrapper">
              <el-icon class="chat-icon"><ChatDotRound /></el-icon>
              <span class="session-title" :title="session.title">{{ session.title || $t('assistant.newChat') }}</span>
            </div>
            <div class="session-actions" @click.stop>
              <el-popconfirm :title="$t('assistant.deleteSessionConfirm')" @confirm="deleteSession(session.id)">
                <template #reference>
                  <el-icon class="delete-icon"><Delete /></el-icon>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </div>

      <div class="user-profile">
        <el-dropdown trigger="click" @command="handleCommand">
          <div class="user-info">
            <el-avatar :size="32" :icon="UserFilled" />
            <span class="username">{{ userStore.user?.username || $t('assistant.user') }}</span>
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="home">{{ $t('assistant.goHome') }}</el-dropdown-item>
              <el-dropdown-item command="logout" divided>{{ $t('assistant.logout') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 右侧主内容区 -->
    <div class="main-content">
      <!-- 欢迎页 -->
      <div v-if="isNewChatMode" class="welcome-screen">
        <div class="welcome-content">
          <div class="logo-area">
            <div class="logo-wedge"></div>
            <h1>TestHub <span class="logo-label">AGENT</span></h1>
            <p>{{ $t('assistant.subtitle') }}</p>
            <div class="welcome-project-select">
              <span class="proj-dot"></span>
              <el-select
                v-model="selectedProjectId"
                :placeholder="$t('assistant.selectProject')"
                size="default"
                class="welcome-select"
                @change="onProjectChange"
              >
                <el-option v-for="p in apiProjects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </div>
          </div>

          <div class="center-input-wrapper">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="3"
              :placeholder="$t('assistant.inputPlaceholder')"
              class="center-input"
              resize="none"
              @keydown.enter.exact.prevent="handleEnter"
            />
            <div class="input-actions">
              <input ref="fileInput" type="file" hidden @change="onFileChange" />
              <el-popover placement="top" :width="260" trigger="click">
                <template #reference>
                  <el-button circle :icon="MagicStick" :disabled="sending" />
                </template>
                <div class="skill-popover">
                  <div class="skill-pop-title">选择 Skill</div>
                  <div v-if="skills.length === 0" class="skill-pop-empty">暂无 Skill</div>
                  <div v-for="sk in skills" :key="sk.name" class="skill-pop-item"
                       @click="pickSkill(sk)">
                    <span class="skill-pop-name">{{ sk.display_name }}</span>
                    <span class="skill-pop-desc">{{ sk.description }}</span>
                  </div>
                </div>
              </el-popover>
              <el-button circle :icon="Link" @click="$refs.fileInput.click()" :disabled="sending" />
              <el-button type="primary" circle :icon="Promotion"
                :disabled="(!inputMessage.trim() && uploadedFiles.length === 0) || sending"
                @click="sendMessage" />
            </div>
          </div>

          <div v-for="(f, i) in uploadedFiles" :key="i" class="uploaded-chip">
            <el-icon><Document /></el-icon>
            <span :title="f.path">{{ f.name }}</span>
            <el-icon class="remove-file" @click="uploadedFiles.splice(i, 1)"><Close /></el-icon>
          </div>

          <div class="skills-section">
            <div class="skills-header">
              <span class="skills-label">Skills & MCP</span>
              <div style="display:flex;gap:12px;">
                <span class="skills-import" @click="showMCPDialog = true">
                  <el-icon><Connection /></el-icon> MCP
                </span>
                <span class="skills-import" @click="showSkillImport = true">
                  <el-icon><Plus /></el-icon> 导入
                </span>
              </div>
            </div>
            <div v-if="skills.length > 0" class="skills-chips">
              <div v-for="sk in skills" :key="sk.name" class="skill-chip"
                   :class="{ disabled: !sk.enabled }"
                   :title="sk.description"
                   @click="invokeSkill(sk)">
                <el-icon><MagicStick /></el-icon>
                <span>{{ sk.display_name }}</span>
              </div>
            </div>
            <div v-else class="skills-empty">暂无 Skill，点击"导入"添加</div>
          </div>

          <!-- 弹窗 -->
          <el-dialog v-model="showSkillImport" title="导入 Skill" width="420px" :close-on-click-modal="false">
            <el-upload ref="skillUploadRef" drag :auto-upload="false" accept=".zip" :limit="1"
                       :on-change="onSkillFileChange" :file-list="skillFileList">
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">拖拽或点击上传 Skill 包 (.zip)</div>
              <div class="el-upload__tip">包含 SKILL.md 的 zip 压缩包</div>
            </el-upload>
            <template #footer>
              <el-button @click="showSkillImport = false; skillFileList = []">取消</el-button>
              <el-button type="primary" @click="doImportSkill" :loading="importingSkill">导入</el-button>
            </template>
          </el-dialog>

          <el-dialog v-model="showMCPDialog" title="MCP 服务器管理" width="520px" :close-on-click-modal="false">
            <div class="mcp-section">
              <div class="mcp-section-title">独立 MCP 服务器</div>
              <div v-if="mcpServers.standalone && mcpServers.standalone.length > 0">
                <div v-for="srv in mcpServers.standalone" :key="srv.name" class="mcp-item">
                  <div class="mcp-item-info">
                    <span class="mcp-item-name">{{ srv.name }}</span>
                    <span class="mcp-item-cmd">{{ srv.command || srv.type }}</span>
                  </div>
                  <el-switch :model-value="srv.enabled" size="small" @change="toggleMCPServer(srv.name, $event)" />
                </div>
              </div>
              <div v-else class="mcp-empty">暂无独立 MCP 服务器</div>
              <el-divider />
              <div class="mcp-section-title">Skill 内嵌 MCP</div>
              <div v-if="mcpServers.embedded && mcpServers.embedded.length > 0">
                <div v-for="srv in mcpServers.embedded" :key="srv.name" class="mcp-item">
                  <div class="mcp-item-info">
                    <span class="mcp-item-name">{{ srv.name }}</span>
                    <span class="mcp-item-cmd">{{ srv.skill_name }} / {{ srv.command || srv.type }}</span>
                  </div>
                  <el-tag size="small" :type="srv.enabled ? 'success' : 'info'">{{ srv.enabled ? '启用' : '禁用' }}</el-tag>
                </div>
              </div>
              <div v-else class="mcp-empty">Skill 中暂无 MCP 配置</div>
              <el-divider />
              <div class="mcp-add-form">
                <div class="mcp-section-title">添加 MCP 服务器</div>
                <el-input v-model="mcpForm.name" placeholder="名称" size="small" style="margin-bottom:8px" />
                <el-input v-model="mcpForm.command" placeholder="npx -y @scope/server-name 或 https://..." size="small" style="margin-bottom:8px" />
                <el-button size="small" type="primary" @click="addMCPServer" :loading="addingMCP">添加</el-button>
              </div>
            </div>
          </el-dialog>
        </div>
      </div>

      <!-- 对话页 -->
      <div v-else class="chat-screen">
        <div class="chat-header">
          <div class="chat-header-left">
            <span class="chat-time" v-if="currentSession">{{ formatDate(currentSession.updated_at) }}</span>
            <el-select v-model="selectedProjectId" :placeholder="$t('assistant.selectProject')"
                       size="small" class="header-project-select" @change="onProjectChange">
              <el-option v-for="p in apiProjects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
            <el-button @click="showFilePanel = true; loadFiles()" size="small" :icon="Folder" circle
                       style="margin-left: auto;" />
          </div>
        </div>

        <div class="messages-container" ref="messagesContainer">
          <div v-for="(item, index) in chatItems" :key="index">
            <div v-if="item.type === 'message' && item.role === 'user'" class="message-row user">
              <div class="avatar"><el-avatar :size="32" :icon="User" class="user-avatar" /></div>
              <div class="message-bubble"><div class="message-content">{{ item.content }}</div></div>
            </div>
            <div v-if="item.type === 'message' && item.role === 'assistant'" class="message-row assistant">
              <div class="avatar"><el-avatar :size="32" :icon="Cpu" class="ai-avatar" /></div>
              <div class="message-bubble"><div class="message-content" v-html="formatMessageContent(item.content)"></div></div>
            </div>
            <div v-if="item.type === 'tool_call'" class="tool-line" :class="item.status">
              <el-icon v-if="item.status === 'running' || !item.status" class="is-loading"><Loading /></el-icon>
              <el-icon v-else-if="item.status === 'success'" class="tool-success"><CircleCheck /></el-icon>
              <el-icon v-else-if="item.status === 'error'" class="tool-error"><CircleClose /></el-icon>
              <el-icon v-else class="tool-done"><Check /></el-icon>
              <span>{{ toolLabel(item.name) }}</span>
            </div>
          </div>

          <div v-if="streaming" class="message-row assistant">
            <div class="avatar"><el-avatar :size="32" :icon="Cpu" class="ai-avatar" /></div>
            <div class="message-bubble">
              <div class="message-content" v-html="formatMessageContent(streamBuffer)"></div>
              <div class="message-status" v-if="!streamBuffer">
                <el-icon class="is-loading"><Loading /></el-icon>
                {{ $t('assistant.thinking') }}
              </div>
            </div>
          </div>
          <div style="height: 20px;"></div>
        </div>

        <div class="chat-footer">
          <div v-for="(f, i) in uploadedFiles" :key="i" class="uploaded-chip chat-uploaded">
            <el-icon><Document /></el-icon>
            <span :title="f.path">{{ f.name }}</span>
            <el-icon class="remove-file" @click="uploadedFiles.splice(i, 1)"><Close /></el-icon>
          </div>
          <div class="input-box">
            <el-input v-model="inputMessage" type="textarea" :rows="1"
              :autosize="{ minRows: 1, maxRows: 5 }"
              :placeholder="$t('assistant.chatInputPlaceholder')"
              resize="none"
              @keydown.enter.exact.prevent="handleEnter" />
            <input ref="fileInput2" type="file" hidden @change="onFileChange" />
            <el-popover placement="top" :width="260" trigger="click">
              <template #reference>
                <el-button class="upload-btn" style="right:80px" circle :icon="MagicStick" :disabled="sending" />
              </template>
              <div class="skill-popover">
                <div class="skill-pop-title">选择 Skill</div>
                <div v-if="skills.length === 0" class="skill-pop-empty">暂无 Skill</div>
                <div v-for="sk in skills" :key="sk.name" class="skill-pop-item" @click="pickSkill(sk)">
                  <span class="skill-pop-name">{{ sk.display_name }}</span>
                  <span class="skill-pop-desc">{{ sk.description }}</span>
                </div>
              </div>
            </el-popover>
            <el-button class="upload-btn" circle :icon="Link" @click="$refs.fileInput2.click()" :disabled="sending" />
            <el-button type="primary" class="send-btn"
              :disabled="(!inputMessage.trim() && uploadedFiles.length === 0) || sending"
              @click="sendMessage">
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
          <div class="footer-tip">{{ $t('assistant.aiDisclaimer') }}</div>
        </div>

        <!-- File Panel Dialog -->
        <el-dialog v-model="showFilePanel" title="文件管理" width="480px" :close-on-click-modal="true">
          <div v-if="sessionFiles.uploads.length + sessionFiles.outputs.length === 0" style="text-align:center;color:#bbb;padding:20px;">
            暂无文件，上传文件或让 Agent 生成后即可在此管理
          </div>
          <template v-else>
            <div v-if="sessionFiles.uploads.length > 0">
              <h4 style="font-size:13px;color:#666;margin:0 0 8px;">📤 用户上传</h4>
              <div v-for="f in sessionFiles.uploads" :key="f.id" class="file-item">
                <el-icon><Document /></el-icon>
                <span class="file-name">{{ f.file_name }}</span>
                <span class="file-size">{{ formatSize(f.file_size) }}</span>
                <span class="file-time">{{ formatDate(f.created_at) }}</span>
                <el-button size="small" text type="danger" :icon="Delete" @click="deleteFile(f.id)" />
              </div>
            </div>
            <div v-if="sessionFiles.outputs.length > 0" style="margin-top:16px;">
              <h4 style="font-size:13px;color:#666;margin:0 0 8px;">📥 Agent 产出</h4>
              <div v-for="f in sessionFiles.outputs" :key="f.id" class="file-item">
                <el-icon><Document /></el-icon>
                <span class="file-name">{{ f.file_name }}</span>
                <span class="file-size">{{ formatSize(f.file_size) }}</span>
                <span class="file-time">{{ formatDate(f.created_at) }}</span>
                <el-button size="small" text type="primary" :icon="Download"
                  @click="window.open(downloadUrl(f.id), '_blank')">下载</el-button>
                <el-button size="small" text type="danger" :icon="Delete" @click="deleteFile(f.id)" />
              </div>
            </div>
          </template>
        </el-dialog>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, ChatDotRound, User, Cpu, Promotion, Loading, UserFilled, ArrowDown, Folder, Link, Document, Close, MagicStick, UploadFilled, Connection, CircleCheck, CircleClose, Check, Download } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { getSkills, importSkill } from '@/api/assistant'
import { marked } from 'marked'

// 配置 marked：不过滤 <br> 等简单 HTML（Agent 输出不含用户 HTML）
marked.setOptions({ breaks: true, gfm: true })

const router = useRouter()
const userStore = useUserStore()
const { t, locale } = useI18n()

const historySessions = ref([])
const currentSession = ref(null)
const messages = ref([])
const chatItems = ref([])
const inputMessage = ref('')
const sending = ref(false)
const streaming = ref(false)
const streamBuffer = ref('')
const uploadedFiles = ref([])  // 多文件支持
const messagesContainer = ref(null)
const fileInput = ref(null)
const fileInput2 = ref(null)

const skills = ref([])
const showSkillImport = ref(false)
const importingSkill = ref(false)
const skillFileList = ref([])
const showMCPDialog = ref(false)
const mcpServers = ref({ standalone: [], embedded: [] })
const mcpForm = reactive({ name: '', command: '' })
const addingMCP = ref(false)
const showFilePanel = ref(false)
const sessionFiles = ref({ uploads: [], outputs: [] })

const loadFiles = async () => {
  if (!currentSession.value?.session_id) return
  try {
    const token = userStore.accessToken; const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
    const resp = await fetch(`${baseURL}/assistant/chat/list_files/?session_id=${currentSession.value.session_id}`, { headers: { 'Authorization': `Bearer ${token}` } })
    sessionFiles.value = await resp.json()
  } catch (e) { /* ignore */ }
}
const deleteFile = async (fileId) => {
  try {
    const token = userStore.accessToken; const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
    const resp = await fetch(`${baseURL}/assistant/chat/delete_file/`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify({ id: fileId }) })
    const data = await resp.json()
    if (data.success) { ElMessage.success('已删除'); loadFiles() }
    else { ElMessage.error(data.error || '删除失败') }
  } catch (e) { ElMessage.error('删除失败') }
}

const formatSize = (bytes) => {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}
const downloadUrl = (url) => {
  const token = userStore.accessToken; const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
  return `${baseURL}/assistant/chat/download_file/?id=${url}&token=${token}`
}

const apiProjects = ref([])
const selectedProjectId = ref(null)
const selectedProject = computed(() => apiProjects.value.find(p => p.id === selectedProjectId.value))

const toolLabels = {
  get_project_overview: '正在查看项目概况...',
  search_apis: '正在搜索接口...',
  get_api_detail: '正在获取接口详情...',
  search_testcases: '正在搜索测试用例...',
  create_api_test: '正在创建接口测试...',
  update_api_test: '正在修改接口测试...',
  create_collection: '正在创建集合...',
  create_testcase: '正在创建测试用例...',
  execute_api: '正在执行接口请求...',
  parse_swagger: '正在解析 Swagger 文档...',
  parse_yapi: '正在解析 YApi 文档...',
  read_knowledge_base: '正在读取知识库...',
  simple_doc_parser: '正在读取文件...',
  list_api_projects: '正在查找 API 项目...',
  list_midscene_projects: '正在查找 Midscene 项目...',
  list_midscene_cases: '正在获取 Midscene 用例...',
  update_midscene_case: '正在修改 Midscene 用例...',
  get_testcase_detail: '正在查看用例详情...',
  update_testcase: '正在修改用例...',
  delete_testcase: '正在删除用例...',
  update_knowledge_base: '正在更新知识库...',
  bash: '正在执行命令...',
  'agent-browser': '正在操作浏览器...',
  navigate: '正在打开页面...',
  snapshot: '正在获取页面内容...',
  screenshot: '正在截取页面...',
}
const toolLabel = (name) => toolLabels[name] || `正在调用 ${name}...`

const handleCommand = (command) => {
  if (command === 'logout') { handleLogout() }
  else if (command === 'home') { router.push('/home') }
}

const handleLogout = () => {
  ElMessageBox.confirm(t('assistant.logoutConfirm'), t('assistant.logoutTitle'), {
    confirmButtonText: t('assistant.confirm'), cancelButtonText: t('assistant.cancel'), type: 'warning'
  }).then(() => { userStore.logout(); router.push('/login'); ElMessage.success(t('assistant.loggedOut')) }).catch(() => {})
}

const historySessionsDescending = computed(() =>
  [...historySessions.value].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
)
const isNewChatMode = computed(() =>
  !currentSession.value || (!currentSession.value.id && messages.value.length === 0 && chatItems.value.length === 0)
)

const loadProjects = async () => {
  try {
    const response = await api.get('/projects/')
    apiProjects.value = response.data.results || response.data || []
    if (apiProjects.value.length > 0 && !selectedProjectId.value) selectedProjectId.value = apiProjects.value[0].id
  } catch (error) { console.error('Load projects failed:', error) }
}

const onProjectChange = (val) => {
  selectedProjectId.value = val
  // 同步更新会话的 project_id
  if (currentSession.value?.id) {
    api.patch(`/assistant/sessions/${currentSession.value.id}/`, { project_id: val }).catch(() => {})
  }
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const d = new Date(dateString)
  const now = new Date()
  const lc = locale.value === 'zh-cn' ? 'zh-CN' : 'en-US'
  return d.toDateString() === now.toDateString()
    ? d.toLocaleTimeString(lc, { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString(lc, { month: '2-digit', day: '2-digit' })
}

const formatMessageContent = (content) => {
  if (!content) return ''
  let text = content
  // 0. 标题后紧跟表格拆行：###标题| col | → ###标题\n| col |
  text = text.replace(/^(#{1,3}\s*.+?)\|(.+)$/gm, '$1\n|$2')
  // 0.5. 普通文本后紧跟表格：text✅| col | val | → text✅\n| col | val |
  // 触发条件：行首非|、非标题，且含3个以上|（表格特征）
  text = text.replace(/^(?![#|])(.+?)\|((?:.+\|){2,}.*)$/gm, '$1\n|$2')
  // 1. 全局拆行：Qwen 用 || 拼接行，无条件拆分
  text = text.replace(/\|\|/g, '|\n|')
  // 2. 逐行规范化：任何以|开头的行都处理
  text = text.replace(/^\|.+/gm, (line) => {
    const inner = line.replace(/^\|\s*|\s*\|$/g, '')
    const cells = inner.split('|').map(c => c.trim())
    return '| ' + cells.join(' | ') + ' |'
  })
  // 3. marked 渲染
  return marked.parse(text)
}

const scrollToBottom = () => nextTick(() => { if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight })

const startNewChat = () => {
  currentSession.value = { title: t('assistant.newChat') }
  messages.value = []; chatItems.value = []; inputMessage.value = ''; streamBuffer.value = ''
}

const switchToSession = async (session) => {
  if (currentSession.value?.id === session.id) return
  try {
    currentSession.value = { ...session }
    // 恢复会话关联的项目
    selectedProjectId.value = session.project_id || apiProjects.value[0]?.id || null
    const response = await api.get(`/assistant/sessions/${session.id}/messages/`)
    messages.value = response.data
    chatItems.value = (response.data || []).map(msg => ({ type: 'message', role: msg.role, content: msg.content, created_at: msg.created_at }))
    scrollToBottom()
    loadFiles()
  } catch (error) { console.error('Load messages failed:', error); ElMessage.error(t('assistant.messages.loadMessageFailed')) }
}

const deleteSession = async (sessionId) => {
  try {
    await api.delete(`/assistant/sessions/${sessionId}/`)
    historySessions.value = historySessions.value.filter(s => s.id !== sessionId)
    if (currentSession.value?.id === sessionId) startNewChat()
    ElMessage.success(t('assistant.messages.sessionDeleted'))
  } catch (error) { console.error('Delete session failed:', error); ElMessage.error(t('assistant.messages.deleteSessionFailed')) }
}

const pickSkill = (sk) => { inputMessage.value = `/skill:${sk.name}` }
const invokeSkill = (sk) => { inputMessage.value = `/skill:${sk.name}`; sendMessage() }

const useSuggestion = (text) => { inputMessage.value = text; sendMessage() }
const handleEnter = (e) => { if (!e.shiftKey && !sending.value) sendMessage() }

const onFileChange = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  const formData = new FormData(); formData.append('file', file)
  if (currentSession.value?.session_id) formData.append('session_id', currentSession.value.session_id)
  try {
    const token = userStore.accessToken; const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
    const resp = await fetch(`${baseURL}/assistant/chat/upload_file/`, { method: 'POST', headers: { 'Authorization': `Bearer ${token}` }, body: formData })
    const data = await resp.json()
    if (data.file_path) { uploadedFiles.value.push({ name: data.file_name, path: data.file_path, url: data.file_url }); ElMessage.success('文件已上传') }
    else { ElMessage.error(data.error || '上传失败') }
  } catch (error) { ElMessage.error('上传失败: ' + error.message) }
  e.target.value = ''
}

const sendMessage = async () => {
  const text = inputMessage.value.trim()
  if (!text || sending.value) return
  inputMessage.value = ''
  sending.value = true; streaming.value = true; streamBuffer.value = ''
  // Agent 可通过 list_session_files/read_session_file 自行发现和读取文件
  chatItems.value.push({ type: 'message', role: 'user', content: text })
  scrollToBottom()

  try {
    let sessionId = currentSession.value?.session_id
    if (!sessionId) {
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`
      const title = text.length > 10 ? text.substring(0, 10) + '...' : text
      const sessionRes = await api.post('/assistant/sessions/', { session_id: newSessionId, title, project_id: selectedProjectId.value })
      currentSession.value = sessionRes.data; sessionId = sessionRes.data.session_id
      historySessions.value.unshift(currentSession.value)
    }

    const token = userStore.accessToken; const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
    const response = await fetch(`${baseURL}/assistant/chat/send_message_stream/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ session_id: sessionId, message: text, project_id: selectedProjectId.value }),
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const reader = response.body.getReader(); const decoder = new TextDecoder()
    let buffer = ''; let currentEventType = 'text'
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n'); buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('event: ')) { currentEventType = line.slice(7).trim(); continue }
        if (line.startsWith('data: ')) {
          try { handleSSEEvent(currentEventType || 'text', JSON.parse(line.slice(6))) } catch { /* skip */ }
        }
      }
    }
  } catch (error) { console.error('Send failed:', error); ElMessage.error(t('assistant.messages.sendFailed')) }
  finally { sending.value = false; streaming.value = false; streamBuffer.value = ''; scrollToBottom() }
}

const handleSSEEvent = (eventType, data) => {
  switch (eventType) {
    case 'text': streamBuffer.value += data.content || ''; scrollToBottom(); break
    case 'tool':
      chatItems.value.push({ type: 'tool_call', name: data.name, status: 'running' })
      scrollToBottom()
      break
    case 'tool_result': {
      // 找到最近的同名 tool_call 并更新状态
      const lastTool = [...chatItems.value].reverse().find(
        item => item.type === 'tool_call' && item.name === data.name && item.status === 'running'
      )
      if (lastTool) {
        lastTool.status = data.result?.includes('"success": true') || data.result?.includes('"success":true')
          ? 'success' : data.result?.includes('"error"') || data.result?.includes('"success": false')
          ? 'error' : 'done'
        lastTool.result = data.result || ''
      }
      scrollToBottom()
      break
    }
    case 'done':
      if (streamBuffer.value.trim()) {
        // 幻觉提示：如果 Agent 没有任何 tool 调用但回复看起来像操作结果
        const tcCount = data.tool_calls_count || 0
        const tcMade = data.tool_calls_made || []
        let finalContent = streamBuffer.value
        if (tcCount === 0 && /已(创建|删除|修改|执行|更新|添加|导入|保存|生成)/.test(finalContent)) {
          finalContent += '\n\n⚠️ 系统提示：以上内容未经 Tool 实际执行，可能是模型生成的幻觉信息，请谨慎核实。'
        }
        chatItems.value.push({ type: 'message', role: 'assistant', content: finalContent })
        streamBuffer.value = ''
      }
      if (currentSession.value) { const idx = historySessions.value.findIndex(s => s.id === currentSession.value.id); if (idx !== -1) { const u = historySessions.value.splice(idx, 1)[0]; u.updated_at = new Date().toISOString(); historySessions.value.unshift(u) } }
      break
    case 'error': ElMessage.error(data.content || 'Agent 错误'); break
  }
}

const loadSkills = async () => { try { const r = await getSkills(); skills.value = r.data || [] } catch (e) {} }
const loadHistory = async () => { try { const r = await api.get('/assistant/sessions/'); historySessions.value = r.data.results || r.data || [] } catch (e) {} }

const loadMCPServers = async () => { try { const r = await api.get('/assistant/mcp/'); mcpServers.value = r.data || { standalone: [], embedded: [] } } catch (e) {} }
const addMCPServer = async () => {
  if (!mcpForm.name || !mcpForm.command) return
  addingMCP.value = true
  try {
    const isUrl = mcpForm.command.startsWith('http')
    const parts = mcpForm.command.split(' ')
    await api.post('/assistant/mcp/add_server/', { name: mcpForm.name, type: isUrl ? 'sse' : 'stdio', command: isUrl ? '' : parts[0], args: isUrl ? [] : parts.slice(1), url: isUrl ? mcpForm.command : '' })
    ElMessage.success('MCP 已添加，重启 Agent 后生效'); mcpForm.name = ''; mcpForm.command = ''; await loadMCPServers()
  } catch (e) { ElMessage.error('添加失败') } finally { addingMCP.value = false }
}
const toggleMCPServer = async (name, enabled) => { try { await api.post('/assistant/mcp/toggle_server/', { name, enabled }); await loadMCPServers() } catch (e) {} }

const onSkillFileChange = (file) => { skillFileList.value = [file] }
const doImportSkill = async () => {
  if (skillFileList.value.length === 0) return
  importingSkill.value = true
  try { await importSkill(skillFileList.value[0].raw); ElMessage.success('Skill 导入成功'); showSkillImport.value = false; skillFileList.value = []; await loadSkills() }
  catch (e) { ElMessage.error('导入失败: ' + (e.response?.data?.error || e.message)) }
  finally { importingSkill.value = false }
}

onMounted(async () => {
  await loadHistory(); await loadProjects(); await loadSkills(); await loadMCPServers()
  if (historySessions.value.length > 0) await switchToSession(historySessions.value[0])
  else startNewChat()
})
</script>

<style scoped lang="scss">
// ====================================
// Endfield Moderate — Agent Chat Shell
// white/charcoal/signal-yellow
// ====================================
$bg-rail: #191919;
$bg-page: #f5f5f0;
$bg-surface: #ffffff;
$text-primary: #191919;
$text-secondary: #6b6b6b;
$text-rail: rgba(255,255,255,.55);
$text-rail-dim: rgba(255,255,255,.35);
$accent: #fffa00;
$rule: 1px solid #e0e0dc;
$rule-dark: 1px solid rgba(255,255,255,.06);

.assistant-layout {
  display: flex; height: 100vh; background: $bg-page; overflow: hidden;
}

// ====== Left Rail ======
.sidebar {
  width: 260px; background: $bg-rail; border-right: $rule-dark;
  display: flex; flex-direction: column; flex-shrink: 0;
  .new-chat-btn-wrapper {
    padding: 20px 16px 12px;
    .new-chat-btn {
      width: 100%; height: 40px; border-radius: 2px; font-size: 13px;
      font-weight: 600; letter-spacing: 0.5px; background: $accent;
      border: none; color: $bg-rail; text-transform: uppercase;
      transition: opacity 0.15s; &:hover { opacity: 0.85; }
    }
  }
  .history-list {
    flex: 1; display: flex; flex-direction: column; overflow: hidden; margin-top: 4px;
    .history-label {
      padding: 0 16px 6px; font-size: 10px; text-transform: uppercase;
      letter-spacing: 1px; color: $text-rail-dim;
    }
    .session-scroll-area {
      flex: 1; overflow-y: auto; padding: 0 8px;
      &::-webkit-scrollbar { width: 3px; } &::-webkit-scrollbar-thumb { background: rgba(255,255,255,.1); }
    }
    .session-item {
      display: flex; align-items: center; justify-content: space-between;
      padding: 8px 12px; margin-bottom: 1px; border-radius: 2px; cursor: pointer;
      color: $text-rail; font-size: 13px; transition: background 0.12s;
      border-left: 2px solid transparent;
      &:hover { background: rgba(255,255,255,.05); .session-actions { opacity: 1; } }
      &.active { background: rgba(255,255,255,.08); border-left-color: $accent; color: #fff; }
      .session-title-wrapper { display: flex; align-items: center; gap: 8px; flex: 1; overflow: hidden;
        .chat-icon { font-size: 15px; opacity: 0.5; }
        .session-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      }
      .session-actions { opacity: 0; transition: opacity 0.15s;
        .delete-icon { font-size: 13px; color: $text-rail-dim; &:hover { color: #f56c6c; } }
      }
    }
  }
  .user-profile {
    padding: 14px 16px; border-top: $rule-dark;
    .user-info { display: flex; align-items: center; cursor: pointer; padding: 6px 8px; border-radius: 2px;
      &:hover { background: rgba(255,255,255,.05); }
      .username { margin: 0 8px; font-size: 13px; color: rgba(255,255,255,.75); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .el-icon { color: $text-rail-dim; }
    }
  }
}

// ====== Main ======
.main-content { flex: 1; display: flex; flex-direction: column; background: $bg-surface; }

// ====== Welcome ======
.welcome-screen {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding-bottom: 80px; background: $bg-surface;
  .welcome-content { width: 100%; max-width: 720px; padding: 0 24px; display: flex; flex-direction: column; align-items: center; }
  .logo-area {
    text-align: center; margin-bottom: 36px;
    .logo-wedge {
      width: 48px; height: 40px; background: $accent;
      clip-path: polygon(0 0, 80% 0, 100% 100%, 20% 100%);
      margin: 0 auto 16px;
    }
    h1 { font-size: 26px; font-weight: 700; color: $text-primary; margin: 0 0 4px; letter-spacing: -0.5px; }
    .logo-label { font-size: 10px; color: $text-secondary; letter-spacing: 2px; vertical-align: super; text-transform: uppercase; }
    p { color: $text-secondary; font-size: 14px; margin: 8px 0 0; font-weight: 400; }
  }
  .welcome-project-select {
    display: inline-flex; align-items: center; gap: 8px; margin-top: 12px; padding: 6px 14px;
    background: $bg-page; border: $rule;
    .proj-dot { width: 6px; height: 6px; background: $accent; }
    .welcome-select { width: 200px; }
  }
  .center-input-wrapper {
    width: 100%; position: relative; margin-bottom: 24px;
    .center-input :deep(.el-textarea__inner) {
      border-radius: 3px; padding: 14px 48px 14px 16px; font-size: 15px;
      border: $rule; background: $bg-page; resize: none; transition: border-color 0.15s;
      &:focus { border-color: $text-primary; background: #fff; }
    }
    .input-actions { position: absolute; right: 8px; bottom: 8px; display: flex; gap: 6px; }
  }
  .skills-section {
    width: 100%; margin-bottom: 16px;
    .skills-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; padding: 0 2px; }
    .skills-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1.2px; color: $text-secondary; }
    .skills-import { font-size: 12px; color: $text-secondary; cursor: pointer; display: flex; align-items: center; gap: 3px; &:hover { color: $text-primary; } }
    .skills-chips { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
    .skill-chip {
      display: flex; align-items: center; gap: 5px; padding: 6px 14px;
      background: $bg-rail; color: $accent; font-size: 13px; font-weight: 500;
      cursor: pointer; transition: opacity 0.12s;
      &.disabled { opacity: 0.3; } &:not(.disabled):hover { opacity: 0.8; }
    }
    .skills-empty { text-align: center; font-size: 12px; color: #bbb; padding: 6px; }
  }
}

// ====== Chat ======
.chat-screen {
  flex: 1; display: flex; flex-direction: column; height: 100%;
  .chat-header {
    height: 52px; border-bottom: $rule; display: flex; align-items: center;
    gap: 12px; padding: 0 20px; flex-shrink: 0; background: #fff;
    .chat-header-left { display: flex; align-items: center; gap: 10px; }
    .chat-title { font-size: 14px; font-weight: 600; color: $text-primary; letter-spacing: -0.2px; }
    .chat-time { font-size: 11px; color: #bbb; }
    .header-project-select { width: 180px; }
  }
  .messages-container { flex: 1; overflow-y: auto; padding: 20px; background: $bg-page; }
  .message-row {
    display: flex; gap: 12px; margin-bottom: 16px;
    &.user { flex-direction: row-reverse; .message-bubble { background: $bg-rail; color: #fff; } }
    &.assistant { .message-bubble { background: #fff; color: $text-primary; border: $rule; } }
    .avatar { flex-shrink: 0; }
    .user-avatar { background: #555; }
    .ai-avatar { background: $bg-rail; :deep(.el-icon) { color: $accent; } }
    .message-bubble {
      max-width: 72%; padding: 10px 14px; font-size: 14px; line-height: 1.55;
      overflow-x: auto;
      .message-content {
        word-wrap: break-word; word-break: break-word;
        :deep(table) {
          border-collapse: collapse; margin: 8px 0; font-size: 13px; max-width: 100%;
          th, td { border: 1px solid #e0e0dc; padding: 6px 10px; text-align: left; word-break: break-all; }
          th { background: $bg-page; font-weight: 600; color: $text-primary; }
          td { color: $text-secondary; }
        }
        :deep(pre) { background: $bg-page; padding: 10px; overflow-x: auto; font-size: 12px; margin: 8px 0; border-radius: 2px; }
        :deep(code) { background: $bg-page; padding: 1px 4px; font-size: 12px; border-radius: 2px; }
        :deep(pre code) { background: none; padding: 0; }
        :deep(p) { margin: 4px 0; &:first-child { margin-top: 0; } &:last-child { margin-bottom: 0; } }
        :deep(ul) { padding-left: 18px; margin: 4px 0; }
        :deep(ol) { padding-left: 18px; margin: 4px 0; }
        :deep(blockquote) { border-left: 2px solid $accent; margin: 6px 0; padding: 2px 10px; color: $text-secondary; }
        :deep(hr) { border: none; border-top: $rule; margin: 10px 0; }
        :deep(h1) { font-size: 16px; margin: 8px 0 4px; }
        :deep(h2) { font-size: 15px; margin: 8px 0 4px; }
        :deep(h3) { font-size: 14px; margin: 6px 0 3px; }
      }
      .message-status { display: flex; align-items: center; gap: 5px; font-size: 12px; color: $text-secondary; margin-top: 6px;
        .is-loading { animation: rotating 2s linear infinite; }
      }
    }
  }
  .chat-footer {
    padding: 14px 20px; border-top: $rule; background: #fff;
    .input-box {
      position: relative; border: $rule; background: $bg-page; padding: 6px;
      transition: border-color 0.15s;
      &:focus-within { border-color: $text-primary; background: #fff; }
      :deep(.el-textarea__inner) { border: none; box-shadow: none; padding: 8px 90px 8px 8px; background: transparent; font-size: 14px; }
      .send-btn { position: absolute; right: 6px; bottom: 6px; width: 30px; height: 30px; padding: 0; background: $accent; border: none; color: $bg-rail; &:hover { opacity: 0.85; } }
    }
    .footer-tip { text-align: center; font-size: 11px; color: #c0c0c0; margin-top: 6px; }
  }
}

// ====== Shared ======
.uploaded-chip {
  display: inline-flex; align-items: center; gap: 5px; padding: 5px 10px;
  background: $bg-page; border: $rule; font-size: 12px; color: $text-secondary; margin-bottom: 10px;
  &.chat-uploaded { margin: 0 0 6px 0; }
  .remove-file { cursor: pointer; color: #bbb; &:hover { color: #f56c6c; } }
}
.upload-btn { position: absolute; right: 44px; bottom: 6px; width: 30px; height: 30px; padding: 0; }
.tool-line { margin: 2px 48px; display: flex; align-items: center; gap: 5px; font-size: 12px; color: $text-secondary;
  .is-loading { animation: rotating 2s linear infinite; }
  .tool-success { color: #67c23a; }
  .tool-error { color: #f56c6c; }
  .tool-done { color: #909399; }
}
.skill-popover {
  .skill-pop-title { font-size: 12px; font-weight: 600; color: $text-primary; padding-bottom: 6px; margin-bottom: 6px; border-bottom: $rule; text-transform: uppercase; letter-spacing: 0.8px; }
  .skill-pop-empty { font-size: 12px; color: #bbb; padding: 10px 0; text-align: center; }
  .skill-pop-item { padding: 7px 8px; cursor: pointer; border-left: 2px solid transparent; &:hover { background: $bg-page; border-left-color: $accent; }
    .skill-pop-name { display: block; font-size: 13px; color: $text-primary; font-weight: 500; }
    .skill-pop-desc { display: block; font-size: 11px; color: $text-secondary; margin-top: 1px; }
  }
}
.mcp-section {
  .mcp-section-title { font-size: 12px; font-weight: 600; color: $text-primary; margin-bottom: 6px; }
  .mcp-item { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; border-bottom: $rule;
    .mcp-item-info { flex: 1; } .mcp-item-name { font-size: 13px; color: $text-primary; display: block; } .mcp-item-cmd { font-size: 11px; color: $text-secondary; }
  }
  .mcp-empty { font-size: 12px; color: #bbb; padding: 6px 0; }
  .mcp-add-form { margin-top: 4px; }
}

.file-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px;
  .file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .file-size { color: #999; font-size: 11px; }
  .file-time { color: #bbb; font-size: 11px; }
}
@keyframes rotating { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
