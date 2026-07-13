<template>
  <div class="midscene-page">
    <!-- ====== 左侧用例列表 ====== -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">用例列表</span>
        <el-button size="small" @click="newCase" :icon="Plus">新建</el-button>
      </div>
      <div class="case-list">
        <div
          v-for="c in cases"
          :key="c.id"
          class="case-item"
          :class="{ active: c.id === currentCaseId }"
          @click="loadCase(c)"
        >
          <div class="case-item-name">{{ c.name }}</div>
          <div class="case-item-meta">
            {{ getStepCount(c.ai_prompt) }} 步 ·
            <el-tag v-if="c.latest_result" :type="c.latest_result.status === 'passed' ? 'success' : 'danger'" size="small">
              {{ c.latest_result.status === 'passed' ? '✓' : '✗' }} {{ c.latest_result.pass_rate }}%
            </el-tag>
            <span v-else class="text-muted">未执行</span>
          </div>
          <el-button class="case-delete-btn" size="small" type="danger" text @click.stop="deleteCase(c)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
        <div v-if="cases.length === 0" class="empty-hint">暂无用例，点「新建」开始</div>
      </div>
    </aside>

    <!-- ====== 主编辑 + 执行区 ====== -->
    <main class="main-area">
      <div class="editor-section">
        <el-form label-width="80px" size="default">
          <!-- 第一行 -->
          <div class="form-row">
            <el-input v-model="form.name" placeholder="用例名称" style="width:180px" />
            <el-select v-model="form.project_id" placeholder="项目" style="width:150px" clearable>
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
            <span v-if="projectPackage" style="font-size:11px;color:#67c23a">包名: {{ projectPackage }}</span>
          <el-select v-model="form.ai_model_config_id" placeholder="AI 模型" style="width:180px">
              <el-option v-for="m in visionModels" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
            <el-select v-model="selectedDeviceId" placeholder="选择设备" style="width:180px">
              <el-option-group label="Android">
                <el-option v-for="d in androidDevices" :key="d.id"
                  :label="`${d.name || d.device_id} ${d.status === 'locked' ? '🔒' : ''}`"
                  :value="d.id" :disabled="d.status === 'offline'" />
              </el-option-group>
              <el-option-group label="iOS">
                <el-option v-for="d in iosDevices" :key="d.id"
                  :label="`${d.name || d.device_id}`" :value="d.id" :disabled="d.status === 'offline'" />
              </el-option-group>
            </el-select>
            <el-button size="small" @click="discoverDevices" :loading="discovering" icon="Refresh">发现设备</el-button>
          </div>

          <!-- 背景提示 -->
          <el-input v-model="form.ai_act_context" placeholder="全局背景提示，如：遇到权限弹窗先点允许" size="small" clearable style="margin-bottom:8px">
            <template #prepend>全局提示</template>
          </el-input>

          <!-- 步骤编辑 -->
          <div class="steps-editor">
            <el-input
              v-model="form.ai_prompt"
              type="textarea"
              :rows="8"
              placeholder="每行一个自然语言操作步骤，例如：&#10;打开应用&#10;点击登录按钮&#10;输入用户名 admin&#10;输入密码 123456&#10;点击登录&#10;验证页面显示欢迎信息"
              class="steps-textarea"
            />
          </div>

          <!-- 操作按钮 -->
          <div class="action-row">
            <el-button @click="showAiGen = true" icon="MagicStick">AI 展开步骤</el-button>
            <el-button type="primary" @click="saveCase" :loading="saving" icon="DocumentAdd">
              {{ currentCaseId ? '更新' : '保存' }}
            </el-button>
            <span style="margin-left:12px;display:flex;align-items:center;gap:4px">
              <el-switch v-model="autoPlanMode" size="small" />
              <span style="font-size:12px;color:#909399">智能规划</span>
            </span>
            <el-button type="success" @click="doExecute" :loading="executing" :disabled="!canExecute" icon="VideoPlay">
              执行
            </el-button>
            <el-button v-if="isRunning" type="danger" @click="stopExecution" icon="SwitchButton">停止</el-button>
          </div>
        </el-form>
      </div>

      <!-- ====== 执行实时展示（执行时才显示） ====== -->
      <div v-if="execution" class="execution-section">
        <el-divider />

        <!-- 进度条 -->
        <div class="exec-progress">
          <span class="exec-status">
            <el-tag :type="statusTagType">{{ execution.status_display || execution.status }}</el-tag>
          </span>
          <el-progress :percentage="execution.progress || 0" :status="progressStatus" :stroke-width="16" style="flex:1; margin: 0 12px" />
          <span class="exec-step-count">步骤 {{ currentStep }}/{{ execution.total_steps || 0 }}</span>
        </div>

        <!-- 实时画面 + AI推理 -->
        <div class="realtime-row">
          <div class="screenshot-box">
            <div class="box-label">📱 设备截图</div>
            <div class="screenshot-area">
              <img v-if="currentScreenshot" :src="currentScreenshot" class="screen-img" />
              <el-empty v-else description="等待截图..." :image-size="60" />
            </div>
          </div>
          <div class="reasoning-box">
            <div class="box-label">🧠 AI 推理</div>
            <div class="reasoning-area">
              <div v-if="currentReasoning && currentReasoning.length > 0">
                <div v-for="(r, i) in currentReasoning" :key="i" class="reasoning-line">{{ r }}</div>
              </div>
              <el-empty v-else description="等待 AI 分析..." :image-size="60" />
            </div>
          </div>
        </div>

        <!-- 步骤列表 -->
        <div class="step-results">
          <div
            v-for="s in (execution.steps_detail || [])"
            :key="s.step"
            class="step-tag"
            :class="s.status"
            @click="previewStep(s)"
          >
            <span class="step-dot">{{ s.status === 'passed' ? '✓' : s.status === 'failed' ? '✗' : '→' }}</span>
            {{ s.step }}. {{ s.instruction?.substring(0, 20) }}{{ s.instruction?.length > 20 ? '...' : '' }}
          </div>
        </div>
      </div>
    </main>

    <!-- ====== AI 生成步骤弹窗 ====== -->
    <el-dialog v-model="showAiGen" title="AI 生成详细步骤" width="500px">
      <el-input v-model="aiDesc" type="textarea" :rows="3" placeholder="简要描述测试场景，AI 自动展开...&#10;例如：测试微信登录，包括正常登录和密码错误" />
      <template #footer>
        <el-button @click="showAiGen = false">取消</el-button>
        <el-button type="primary" @click="generateSteps" :loading="genLoading">生成</el-button>
      </template>
    </el-dialog>

    <!-- ====== 截图预览弹窗 ====== -->
    <el-dialog v-model="showPreview" title="步骤截图" width="400px">
      <img :src="previewImage" style="width:100%" v-if="previewImage" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, MagicStick, DocumentAdd, VideoPlay, SwitchButton, Refresh } from '@element-plus/icons-vue'
import api from '@/utils/api'

// ---- 状态 ----
const cases = ref([])
const projects = ref([])
const currentCaseId = ref(null)
const visionModels = ref([])
const devices = ref([])
const selectedDeviceId = ref(null)
const saving = ref(false)
const executing = ref(false)
const discovering = ref(false)

const autoPlanMode = ref(false)

const form = reactive({
  name: '',
  project_id: null,
  ai_prompt: '',
  ai_model_config_id: null,
  max_steps: 30,
  action_delay: 0.5,
  app_package: '',
  ai_act_context: '',
})

// AI 生成
const showAiGen = ref(false)
const aiDesc = ref('')
const genLoading = ref(false)

// 执行
const execution = ref(null)
const currentScreenshot = ref('')
const currentReasoning = ref([])
const currentStep = ref(0)
const showPreview = ref(false)
const previewImage = ref('')
let pollTimer = null

// ---- 计算属性 ----
const projectPackage = computed(() => {
  const p = projects.value.find(p => p.id === form.project_id)
  return p?.default_app_package || ''
})
const androidDevices = computed(() => devices.value.filter(d => d.platform === 'android' && d.status !== 'offline'))
const iosDevices = computed(() => devices.value.filter(d => d.platform === 'ios' && d.status !== 'offline'))
const isRunning = computed(() => execution.value && ['pending', 'running'].includes(execution.value.status))
const canExecute = computed(() => form.ai_prompt && selectedDeviceId.value && form.ai_model_config_id)
const statusTagType = computed(() => {
  const m = { pending: 'info', running: 'warning', passed: 'success', failed: 'danger', error: 'danger', stopped: 'info' }
  return m[execution.value?.status] || 'info'
})
const progressStatus = computed(() => {
  if (!execution.value) return ''
  if (execution.value.status === 'passed') return 'success'
  if (['failed', 'error'].includes(execution.value.status)) return 'exception'
  return ''
})

// ---- 数据加载 ----
const loadCases = async () => {
  try {
    const { data } = await api.get('/ui-automation/midscene/cases/')
    cases.value = data.results || []
  } catch (e) { /* ignore */ }
}

const loadProjects = async () => {
  try {
    const { data } = await api.get('/ui-automation/midscene/projects/')
    projects.value = data.results || []
  } catch (e) { /* ignore */ }
}

const loadDevices = async () => {
  try {
    const { data } = await api.get('/ui-automation/midscene/devices/')
    devices.value = data.results || []
  } catch (e) { /* ignore */ }
}

const loadVisionModels = async () => {
  try {
    const { data } = await api.get('/requirement-analysis/ai-models/')
    visionModels.value = (data.results || data || []).filter(m => m.role === 'app_automation_vision' && m.is_active)
    if (visionModels.value.length > 0 && !form.ai_model_config_id) {
      form.ai_model_config_id = visionModels.value[0].id
    }
  } catch (e) { /* ignore */ }
}

const discoverDevices = async () => {
  discovering.value = true
  try {
    await api.post('/ui-automation/midscene/devices/discover_android/')
    ElMessage.success('设备扫描完成')
    await loadDevices()
  } catch (e) {
    ElMessage.error('扫描失败: ' + (e.response?.data?.error || e.message))
  } finally {
    discovering.value = false
  }
}

// ---- 用例操作 ----
const newCase = () => {
  currentCaseId.value = null
  form.name = ''
  form.ai_prompt = ''
  form.project_id = null
}

const loadCase = (c) => {
  currentCaseId.value = c.id
  form.name = c.name
  form.project_id = c.project
  form.ai_prompt = c.ai_prompt || ''
  form.ai_model_config_id = c.ai_model_config
  form.max_steps = c.max_steps || 30
  form.action_delay = c.action_delay || 0.5
  form.app_package = c.app_package || ''
  form.ai_act_context = c.ai_act_context || ''
}

const saveCase = async () => {
  if (!form.name.trim()) { ElMessage.warning('请输入用例名称'); return }
  if (!form.ai_prompt.trim()) { ElMessage.warning('请输入测试步骤'); return }
  saving.value = true
  try {
    const payload = { ...form }
    if (currentCaseId.value) {
      await api.put(`/ui-automation/midscene/cases/${currentCaseId.value}/`, payload)
      ElMessage.success('已更新')
    } else {
      const { data } = await api.post('/ui-automation/midscene/cases/', payload)
      currentCaseId.value = data.id
      ElMessage.success('已保存')
    }
    await loadCases()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const deleteCase = async (c) => {
  try {
    await ElMessageBox.confirm(`删除「${c.name}」？`, '确认删除', { type: 'warning' })
    await api.delete(`/ui-automation/midscene/cases/${c.id}/`)
    if (currentCaseId.value === c.id) newCase()
    await loadCases()
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const getStepCount = (prompt) => {
  if (!prompt) return 0
  return prompt.trim().split('\n').filter(l => l.trim()).length
}

// ---- AI 生成步骤 ----
const generateSteps = async () => {
  if (!aiDesc.value.trim()) { ElMessage.warning('请输入场景描述'); return }
  genLoading.value = true
  try {
    const { data } = await api.post('/ui-automation/midscene/cases/generate_steps/', {
      description: aiDesc.value,
      model_config_id: form.ai_model_config_id,
    })
    if (data.steps) {
      form.ai_prompt = data.steps
      showAiGen.value = false
      aiDesc.value = ''
      ElMessage.success('步骤已生成，可手动调整')
    }
  } catch (e) {
    ElMessage.error('生成失败: ' + (e.response?.data?.error || e.message))
  } finally {
    genLoading.value = false
  }
}

// ---- 执行 ----
const doExecute = async () => {
  if (!selectedDeviceId.value) { ElMessage.warning('请选择设备'); return }
  if (!form.ai_model_config_id) { ElMessage.warning('请选择 AI 模型'); return }
  if (!form.ai_prompt.trim()) { ElMessage.warning('请输入测试步骤'); return }

  executing.value = true
  try {
    // 如果没有保存过的用例，先自动保存
    if (!currentCaseId.value) {
      await saveCase()
    }
    const { data } = await api.post(`/ui-automation/midscene/cases/${currentCaseId.value}/execute/`, {
      device_id: selectedDeviceId.value,
      auto_plan: autoPlanMode.value,
    })
    execution.value = { id: data.execution_id, status: 'pending', progress: 0, total_steps: 0, steps_detail: [], passed_steps: 0, failed_steps: 0 }
    currentScreenshot.value = ''
    currentReasoning.value = []
    currentStep.value = 0
    startPolling(data.execution_id)
  } catch (e) {
    ElMessage.error('执行失败: ' + (e.response?.data?.error || e.message))
  } finally {
    executing.value = false
  }
}

const stopExecution = async () => {
  if (!execution.value?.id) return
  try {
    await api.post(`/ui-automation/midscene/executions/${execution.value.id}/stop/`)
    execution.value.status = 'stopped'
    ElMessage.info('已停止')
  } catch (e) { /* ignore */ }
}

const startPolling = (execId) => {
  stopPolling()
  const poll = async () => {
    try {
      const { data } = await api.get(`/ui-automation/midscene/executions/${execId}/`)
      execution.value = { ...execution.value, ...data }

      if (data.steps_detail?.length) {
        const last = data.steps_detail[data.steps_detail.length - 1]
        currentStep.value = last.step
        currentScreenshot.value = last.screenshot || ''
        currentReasoning.value = last.aiReasoning || []
      }
      if (!['pending', 'running'].includes(data.status)) stopPolling()
    } catch (e) { /* ignore */ }
  }
  pollTimer = setInterval(poll, 2000)
  poll() // 立即执行一次
}

const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

const previewStep = (s) => {
  if (s.screenshot) { previewImage.value = s.screenshot; showPreview.value = true }
}

// ---- 生命周期 ----
onMounted(() => {
  loadCases()
  loadProjects()
  loadDevices()
  loadVisionModels()
})

onUnmounted(() => stopPolling())
</script>

<style scoped lang="scss">
.midscene-page {
  display: flex;
  height: calc(100vh - 84px);
  background: #f5f7fa;

  // === 左侧栏 ===
  .sidebar {
    width: 250px;
    flex-shrink: 0;
    background: #fff;
    border-right: 1px solid #e4e7ed;
    display: flex;
    flex-direction: column;
    .sidebar-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 12px;
      border-bottom: 1px solid #ebeef5;
      .sidebar-title { font-weight: 600; font-size: 14px; }
    }
    .case-list {
      flex: 1;
      overflow-y: auto;
      .case-item {
        padding: 10px 12px;
        border-bottom: 1px solid #f2f3f5;
        cursor: pointer;
        position: relative;
        &:hover { background: #f5f7fa; }
        &.active { background: #ecf5ff; border-left: 3px solid #409eff; }
        .case-item-name { font-size: 13px; font-weight: 500; margin-bottom: 4px; }
        .case-item-meta { font-size: 11px; color: #909399; }
        .case-delete-btn { position: absolute; top: 6px; right: 4px; opacity: 0; }
        &:hover .case-delete-btn { opacity: 1; }
      }
      .empty-hint { padding: 40px 12px; text-align: center; color: #c0c4cc; font-size: 13px; }
    }
  }

  // === 主区域 ===
  .main-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 20px;

    .editor-section {
      background: #fff;
      border-radius: 4px;
      padding: 20px;
      box-shadow: 0 1px 4px rgba(0,0,0,.06);
      .form-row {
        display: flex;
        gap: 10px;
        margin-bottom: 12px;
        align-items: center;
      }
      .steps-editor {
        margin-bottom: 12px;
        .steps-textarea :deep(textarea) {
          font-family: 'SF Mono','Menlo','Consolas',monospace;
          font-size: 14px;
          line-height: 1.8;
        }
      }
      .action-row {
        display: flex;
        gap: 8px;
      }
    }

    .execution-section {
      margin-top: 16px;
      .exec-progress {
        display: flex;
        align-items: center;
        margin-bottom: 16px;
        .exec-status { min-width: 70px; }
        .exec-step-count { min-width: 80px; font-size: 13px; color: #606266; text-align: right; }
      }
      .realtime-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        margin-bottom: 16px;
        .screenshot-box, .reasoning-box {
          background: #fff;
          border-radius: 4px;
          padding: 12px;
          box-shadow: 0 1px 4px rgba(0,0,0,.06);
          .box-label { font-weight: 600; font-size: 13px; margin-bottom: 8px; }
        }
        .screenshot-area {
          min-height: 300px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #1a1a2e;
          border-radius: 4px;
          .screen-img { max-width: 100%; max-height: 500px; object-fit: contain; }
        }
        .reasoning-area {
          min-height: 300px;
          max-height: 500px;
          overflow-y: auto;
          .reasoning-line {
            padding: 4px 0;
            border-bottom: 1px dashed #ebeef5;
            font-size: 13px;
            color: #606266;
            &:last-child { border-bottom: none; }
          }
        }
      }
      .step-results {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        .step-tag {
          padding: 4px 10px;
          border-radius: 4px;
          font-size: 12px;
          cursor: pointer;
          background: #ecf5ff;
          color: #409eff;
          &.passed { background: #f0f9eb; color: #67c23a; }
          &.failed { background: #fef0f0; color: #f56c6c; }
          &.running { background: #fdf6ec; color: #e6a23c; animation: pulse 1s infinite; }
          .step-dot { font-weight: bold; }
        }
      }
    }
  }
}

.text-muted { color: #c0c4cc; font-size: 11px; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
