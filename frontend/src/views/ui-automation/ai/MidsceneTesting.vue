<template>
  <div class="ms-shell" data-ark-theme="endfield" data-ark-depth="complex">
    <!-- ====== Grid Background ====== -->
    <div class="ms-grid" aria-hidden="true"></div>

    <!-- ====== Left Rail: Case List ====== -->
    <nav class="ms-rail" aria-label="用例列表">
      <div class="ms-rail__head">
        <div class="ms-rail__title-row">
          <span class="ms-rail__idx">00</span>
          <span class="ms-rail__label">TEST CASES</span>
          <span class="ms-rail__count">{{ cases.length }}</span>
        </div>
        <el-select v-model="filterProjectId" placeholder="筛选项目" size="small" clearable class="ms-select--dark">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </div>

      <div class="ms-rail__list">
        <button
          v-for="(c, idx) in filteredCases"
          :key="c.id"
          class="ms-case-item"
          :class="{ 'is-active': c.id === currentCaseId, 'is-draft': c._draft }"
          @click="loadCase(c)"
        >
          <span class="ms-case-item__num">{{ String(idx + 1).padStart(2, '0') }}</span>
          <span class="ms-case-item__body">
            <span class="ms-case-item__name">{{ c.name }}</span>
            <span class="ms-case-item__row">
              <span class="ms-case-item__steps">{{ getStepCount(c.ai_prompt) }} 步</span>
              <span v-if="!c._draft && c.latest_result" class="ms-case-item__rate" :class="c.latest_result.status === 'passed' ? 'rate-pass' : 'rate-fail'">
                {{ c.latest_result.pass_rate }}%
              </span>
              <span v-else-if="c._draft" class="ms-case-item__draft-mark">草稿</span>
            </span>
            <span class="ms-case-item__proj" v-if="getProjectName(c.project)">{{ getProjectName(c.project) }}</span>
          </span>
          <span class="ms-case-item__del" @click.stop="deleteCase(c)" title="删除"><el-icon><Delete /></el-icon></span>
        </button>
        <div v-if="filteredCases.length === 0" class="ms-rail__empty">
          {{ filterProjectId ? '该项目暂无用例' : '暂无用例，点击下方新建' }}
        </div>
      </div>

      <div class="ms-rail__foot">
        <el-button @click="newCase" :icon="Plus" class="ms-btn--full">新建用例</el-button>
      </div>
    </nav>

    <!-- ====== Main Stage ====== -->
    <main class="ms-stage">
      <!-- Zone A: 用例信息 + 执行控制 -->
      <section class="ms-zone">
        <header class="ms-zone__head">
          <span class="ms-zone__kicker">CONFIGURATION / 01</span>
          <span class="ms-zone__rule" aria-hidden="true"></span>
        </header>
        <div class="ms-zone__body">
          <div class="ms-field-row">
            <el-input v-model="form.name" placeholder="用例名称" class="ms-input" />
            <el-select v-model="form.project_id" placeholder="所属项目" clearable class="ms-select">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
            <el-select v-model="form.ai_model_config_id" placeholder="AI 模型" class="ms-select">
              <el-option v-for="m in visionModels" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </div>
        </div>
      </section>

      <!-- Zone B: 执行控制 -->
      <section class="ms-zone">
        <header class="ms-zone__head">
          <span class="ms-zone__kicker">EXECUTION / 02</span>
          <span class="ms-zone__rule" aria-hidden="true"></span>
        </header>
        <div class="ms-zone__body">
          <div class="ms-cmd-strip">
            <div class="ms-cmd-strip__left">
              <el-select v-model="selectedDeviceId" placeholder="选择设备" class="ms-select">
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
              <el-button size="small" @click="discoverDevices" :loading="discovering" :icon="Refresh" class="ms-btn">发现设备</el-button>
              <el-button size="small" @click="showNetworkDialog = true" :icon="Connection" class="ms-btn">局域网</el-button>
              <span class="ms-cmd-strip__divider" aria-hidden="true"></span>
              <span class="ms-switch-group">
                <label class="ms-switch"><el-switch v-model="autoPlanMode" size="small" :disabled="replayMode" /><span>智能规划</span></label>
                <label class="ms-switch"><el-switch v-model="recordMode" size="small" /><span>录制</span></label>
                <label class="ms-switch"><el-switch v-model="replayMode" size="small" :disabled="autoPlanMode" /><span>回放</span></label>
                <label class="ms-switch">
                  <el-switch v-model="clearAppData" size="small" :disabled="isIosDevice" />
                  <el-tooltip :content="isIosDevice ? 'iOS 不支持' : '执行前清除App数据'" placement="top">
                    <span style="cursor:help">清除数据</span>
                  </el-tooltip>
                </label>
              </span>
            </div>
            <div class="ms-cmd-strip__right">
              <el-select v-if="replayList.length > 0" v-model="selectedReplayIndex" size="small" class="ms-select" style="width:170px">
                <el-option v-for="(r, i) in replayList" :key="i" :label="`${r.recorded_at?.substring(5,16) || '未知'} ${r.result || ''}`" :value="i" />
              </el-select>
              <el-button v-if="replayList.length > 0" size="small" type="danger" text @click="deleteReplayEntry" class="ms-btn--text">
                <el-icon><Delete /></el-icon>
              </el-button>
              <el-button
                type="primary" @click="doExecute" :loading="executing" :disabled="!canExecute"
                :icon="VideoPlay" class="ms-btn--exec"
              >执行</el-button>
              <el-button v-if="isRunning" @click="stopExecution" :icon="SwitchButton" class="ms-btn--stop">停止</el-button>
            </div>
          </div>
        </div>
      </section>

      <!-- Zone C: 测试步骤 -->
      <section class="ms-zone">
        <header class="ms-zone__head">
          <span class="ms-zone__kicker">PROCEDURE / 03</span>
          <span class="ms-zone__rule" aria-hidden="true"></span>
        </header>
        <div class="ms-zone__body">
          <el-input v-model="form.ai_act_context" placeholder="全局提示：如 遇到权限弹窗先点允许、遇到渠道选择选抖音" size="small" clearable class="ms-input--context">
            <template #prepend>全局提示</template>
          </el-input>
          <div class="ms-editor">
            <el-input
              v-model="form.ai_prompt"
              type="textarea"
              :rows="8"
              placeholder="每行一个自然语言操作步骤，例如：&#10;打开应用&#10;点击登录按钮&#10;输入用户名 admin&#10;输入密码 123456&#10;点击登录&#10;验证页面显示欢迎信息"
            />
          </div>
          <div class="ms-editor__actions">
            <el-button @click="showAiGen = true" :icon="MagicStick" class="ms-btn">AI 展开</el-button>
            <el-button type="primary" @click="saveCase" :loading="saving" :icon="DocumentAdd" class="ms-btn--save">
              {{ currentCaseId && currentCaseId !== draftId ? '更新' : '保存' }}
            </el-button>
          </div>
        </div>
      </section>

      <!-- Zone D: Live Execution Stage -->
      <section v-if="execution" class="ms-stage-live">
        <header class="ms-zone__head">
          <span class="ms-zone__kicker">LIVE / 04</span>
          <span class="ms-zone__rule" aria-hidden="true"></span>
          <span class="ms-stage-live__status">
            <span class="ms-status-dot" :class="'dot-' + execution.status"></span>
            {{ execution.status_display || execution.status }}
          </span>
        </header>

        <!-- Progress instrumentation -->
        <div class="ms-progress-bar">
          <div class="ms-progress-bar__track">
            <div class="ms-progress-bar__fill" :style="{ width: (execution.progress || 0) + '%' }"></div>
          </div>
          <span class="ms-progress-bar__label">{{ currentStep }}/{{ execution.total_steps || 0 }}</span>
        </div>

        <!-- Dual pane: screenshot + reasoning -->
        <div class="ms-dual">
          <div class="ms-dual__pane ms-dual__pane--screen">
            <div class="ms-dual__label">DEVICE SCREEN</div>
            <div class="ms-dual__stage">
              <img v-if="currentScreenshot" :src="currentScreenshot" class="ms-screen-img" />
              <span v-else class="ms-dual__wait">AWAITING FRAME...</span>
            </div>
          </div>
          <div class="ms-dual__pane ms-dual__pane--reason">
            <div class="ms-dual__label">AI REASONING</div>
            <div class="ms-dual__log">
              <div v-if="currentReasoning && currentReasoning.length > 0">
                <div v-for="(r, i) in currentReasoning" :key="i" class="ms-log-line">{{ r }}</div>
              </div>
              <span v-else class="ms-dual__wait">AWAITING ANALYSIS...</span>
            </div>
          </div>
        </div>

        <!-- Step badges -->
        <div class="ms-step-badges">
          <button
            v-for="s in (execution.steps_detail || [])"
            :key="s.step"
            class="ms-step-badge"
            :class="'badge-' + s.status"
            @click="previewStep(s)"
          >
            <span class="ms-step-badge__mark">{{ s.status === 'passed' ? '✓' : s.status === 'failed' ? '✗' : '→' }}</span>
            {{ s.step }}. {{ s.instruction?.substring(0, 24) }}{{ s.instruction?.length > 24 ? '…' : '' }}
          </button>
        </div>
      </section>
    </main>

    <!-- ====== Dialogs (unchanged) ====== -->
    <el-dialog v-model="showAiGen" title="AI 生成详细步骤" width="500px">
      <el-input v-model="aiDesc" type="textarea" :rows="3" placeholder="简要描述测试场景，AI 自动展开..." />
      <template #footer>
        <el-button @click="showAiGen = false">取消</el-button>
        <el-button type="primary" @click="generateSteps" :loading="genLoading">生成</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showPreview" title="步骤截图" width="400px">
      <img :src="previewImage" style="width:100%" v-if="previewImage" />
    </el-dialog>

    <el-dialog v-model="showNetworkDialog" title="连接局域网 Android 设备" width="520px">
      <el-alert type="info" :closable="false" style="margin-bottom:16px">
        <template #title>对方手机需要先开启 WiFi 调试</template>
        <div style="font-size:12px;line-height:1.8;margin-top:4px">
          1. 手机用 <b>USB</b> 连接到自己电脑<br/>
          2. 在自己电脑终端执行：<code>adb tcpip 5555</code><br/>
          3. 拔掉 USB（WiFi 调试已开启）<br/>
          4. 查看手机 WiFi 设置中的 <b>IP 地址</b><br/>
          5. 把 IP 告诉你，在下方输入连接
        </div>
      </el-alert>
      <el-form label-width="60px">
        <el-form-item label="IP 地址"><el-input v-model="networkForm.ip" placeholder="如：192.168.1.100" /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="networkForm.port" :min="1" :max="65535" /></el-form-item>
      </el-form>
      <div v-if="networkDevices.length > 0" style="margin-top:12px">
        <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:#303133">已连接的局域网设备</div>
        <div v-for="d in networkDevices" :key="d.id" style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#f5f7fa;margin-bottom:6px">
          <div>
            <span style="font-size:13px">{{ d.name || d.device_id }}</span>
            <span style="font-size:11px;color:#909399;margin-left:8px">{{ d.ip_address }}:{{ d.port }}</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            <el-tag :type="d.status==='online'||d.status==='available'?'success':'danger'" size="small">{{ d.status }}</el-tag>
            <el-button v-if="d.status==='offline'" size="small" type="success" @click="reconnectDialogDevice(d)" :loading="dialogConnecting[d.id]">连接</el-button>
            <el-button v-else size="small" type="danger" @click="disconnectDevice(d)" :loading="dialogDisconnecting[d.id]">断开</el-button>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showNetworkDialog = false">关闭</el-button>
        <el-button type="primary" @click="connectNetwork" :loading="connecting">连接</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
// ====== Entire script unchanged ======
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, MagicStick, DocumentAdd, VideoPlay, SwitchButton, Refresh, Connection } from '@element-plus/icons-vue'
import api from '@/utils/api'

const cases = ref([])
const projects = ref([])
const currentCaseId = ref(null)
const visionModels = ref([])
const devices = ref([])
const selectedDeviceId = ref(null)
const saving = ref(false)
const executing = ref(false)
const discovering = ref(false)
const showNetworkDialog = ref(false)
const connecting = ref(false)
const dialogConnecting = reactive({})
const dialogDisconnecting = reactive({})
const networkForm = reactive({ ip: '', port: 5555 })
const autoPlanMode = ref(false)
const recordMode = ref(false)
const replayMode = ref(false)
const clearAppData = ref(false)
const filterProjectId = ref(null)

const isIosDevice = computed(() => {
  if (!selectedDeviceId.value) return false
  const d = devices.value.find(d => d.id === selectedDeviceId.value)
  return d?.platform === 'ios'
})
const filteredCases = computed(() => {
  if (!filterProjectId.value) return cases.value
  return cases.value.filter(c => c.project === filterProjectId.value)
})
const getProjectName = (projectId) => {
  if (!projectId) return ''
  return projects.value.find(p => p.id === projectId)?.name || ''
}
const caseStatusClass = (c) => {
  if (!c.latest_result) return 'never'
  return c.latest_result.status === 'passed' ? 'passed' : 'failed'
}
const form = reactive({
  name: '', project_id: null, ai_prompt: '', ai_model_config_id: null,
  max_steps: 30, action_delay: 0.5, app_package: '', ai_act_context: '',
})
const showAiGen = ref(false)
const aiDesc = ref('')
const genLoading = ref(false)
const execution = ref(null)
const currentScreenshot = ref('')
const currentReasoning = ref([])
const currentStep = ref(0)
const showPreview = ref(false)
const previewImage = ref('')
let pollTimer = null
const androidDevices = computed(() => devices.value.filter(d => d.platform === 'android' && d.status !== 'offline'))
const iosDevices = computed(() => devices.value.filter(d => d.platform === 'ios' && d.status !== 'offline'))
const networkDevices = computed(() => devices.value.filter(d => d.platform === 'android' && d.ip_address))
const isRunning = computed(() => execution.value && ['pending', 'running'].includes(execution.value.status))
const canExecute = computed(() => form.ai_prompt && selectedDeviceId.value && form.ai_model_config_id)
const selectedReplayIndex = ref(0)
const replayList = computed(() => {
  if (!currentCaseId.value) return []
  const c = cases.value.find(c => c.id === currentCaseId.value)
  if (!c?.replay_data) return []
  if (Array.isArray(c.replay_data)) return c.replay_data
  return [c.replay_data]
})
const statusTagType = computed(() => {
  const m = { pending: 'info', running: 'warning', passed: 'success', failed: 'danger', error: 'danger', stopped: 'info' }
  return m[execution.value?.status] || 'info'
})
const draftId = '__draft__'

const loadCases = async () => { try { const { data } = await api.get('/ui-automation/midscene/cases/'); cases.value = data.results || [] } catch (e) {} }
const loadProjects = async () => { try { const { data } = await api.get('/ui-automation/midscene/projects/'); projects.value = data.results || [] } catch (e) {} }
const loadDevices = async () => { try { const { data } = await api.get('/ui-automation/midscene/devices/'); devices.value = data.results || [] } catch (e) {} }
const loadVisionModels = async () => {
  try { const { data } = await api.get('/requirement-analysis/ai-models/'); visionModels.value = (data.results || data || []).filter(m => m.role === 'app_automation_vision' && m.is_active); if (visionModels.value.length > 0 && !form.ai_model_config_id) form.ai_model_config_id = visionModels.value[0].id } catch (e) {}
}
const discoverDevices = async () => {
  discovering.value = true
  try {
    const results = await Promise.allSettled([api.post('/ui-automation/midscene/devices/discover_android/'), api.post('/ui-automation/midscene/devices/discover_ios/')])
    const ok = [results[0].status === 'fulfilled', results[1].status === 'fulfilled']
    if (ok[0] || ok[1]) { const parts = []; if (ok[0]) parts.push('Android'); if (ok[1]) parts.push('iOS'); ElMessage.success(`${parts.join(' + ')} 扫描完成`) }
    else ElMessage.warning('未发现设备')
    await loadDevices()
  } catch (e) { ElMessage.error('扫描失败: ' + (e.response?.data?.error || e.message)) }
  finally { discovering.value = false }
}
const deleteReplayEntry = async () => {
  if (!currentCaseId.value) return
  try { await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' }); await api.post(`/ui-automation/midscene/cases/${currentCaseId.value}/delete_replay/`, { index: selectedReplayIndex.value }); if (selectedReplayIndex.value > 0) selectedReplayIndex.value--; await loadCases(); ElMessage.success('已删除') } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}
const connectNetwork = async () => {
  if (!networkForm.ip.trim()) { ElMessage.warning('请输入 IP'); return }
  connecting.value = true
  try { const { data } = await api.post('/ui-automation/midscene/devices/connect_network/', { ip: networkForm.ip.trim(), port: networkForm.port }); if (data.success) { ElMessage.success(data.message || '已连接'); networkForm.ip = ''; await loadDevices() } else ElMessage.error(data.message || '连接失败') }
  catch (e) { ElMessage.error(e.response?.data?.message || '连接失败') }
  finally { connecting.value = false }
}
const disconnectDevice = async (device) => { dialogDisconnecting[device.id] = true; try { await api.post(`/ui-automation/midscene/devices/${device.id}/disconnect_network/`); ElMessage.success('已断开'); await loadDevices() } catch (e) { ElMessage.error('断开失败') } finally { dialogDisconnecting[device.id] = false } }
const reconnectDialogDevice = async (device) => { dialogConnecting[device.id] = true; try { const { data } = await api.post('/ui-automation/midscene/devices/connect_network/', { ip: device.ip_address, port: device.port || 5555 }); if (data.success) ElMessage.success(data.message || '已连接'); else ElMessage.error(data.message || '连接失败'); await loadDevices() } catch (e) { ElMessage.error(e.response?.data?.message || '连接失败') } finally { dialogConnecting[device.id] = false } }
const newCase = () => { if (cases.value.some(c => c.id === draftId)) return; currentCaseId.value = draftId; cases.value.unshift({ id: draftId, name: '新建用例', ai_prompt: '', project: filterProjectId.value, _draft: true }); form.name = ''; form.ai_prompt = ''; form.project_id = filterProjectId.value || null; recordMode.value = false; replayMode.value = false; clearAppData.value = false }
const loadCase = (c) => { currentCaseId.value = c.id; form.name = c.name; form.project_id = c.project; form.ai_prompt = c.ai_prompt || ''; form.ai_model_config_id = c.ai_model_config; form.max_steps = c.max_steps || 30; form.action_delay = c.action_delay || 0.5; form.app_package = c.app_package || ''; form.ai_act_context = c.ai_act_context || '' }
const saveCase = async () => {
  if (!form.name.trim()) { ElMessage.warning('请输入用例名称'); return }
  if (!form.ai_prompt.trim()) { ElMessage.warning('请输入测试步骤'); return }
  saving.value = true
  try {
    const payload = { ...form }; const isDraft = currentCaseId.value === draftId
    if (currentCaseId.value && !isDraft) { await api.put(`/ui-automation/midscene/cases/${currentCaseId.value}/`, payload); ElMessage.success('已更新') }
    else { const { data } = await api.post('/ui-automation/midscene/cases/', payload); if (isDraft) { const idx = cases.value.findIndex(c => c.id === draftId); if (idx >= 0) cases.value.splice(idx, 1) }; currentCaseId.value = data.id; ElMessage.success('已保存') }
    await loadCases()
  } catch (e) { const data = e.response?.data; let errMsg = e.message; if (data && typeof data === 'object') { const msgs = []; Object.entries(data).forEach(([field, errors]) => { const vals = Array.isArray(errors) ? errors : [errors]; msgs.push(...vals.map(v => typeof v === 'string' ? `${field}: ${v}` : v)) }); if (msgs.length > 0) errMsg = msgs.join('; ') }; ElMessage.error('保存失败: ' + errMsg) }
  finally { saving.value = false }
}
const deleteCase = async (c) => { try { await ElMessageBox.confirm(`删除「${c.name}」？`, '确认删除', { type: 'warning' }); await api.delete(`/ui-automation/midscene/cases/${c.id}/`); if (currentCaseId.value === c.id) newCase(); await loadCases(); ElMessage.success('已删除') } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') } }
const getStepCount = (prompt) => { if (!prompt) return 0; return prompt.trim().split('\n').filter(l => l.trim()).length }
const generateSteps = async () => { if (!aiDesc.value.trim()) { ElMessage.warning('请输入场景描述'); return }; genLoading.value = true; try { const { data } = await api.post('/ui-automation/midscene/cases/generate_steps/', { description: aiDesc.value, model_config_id: form.ai_model_config_id }); if (data.steps) { form.ai_prompt = data.steps; showAiGen.value = false; aiDesc.value = ''; ElMessage.success('步骤已生成') } } catch (e) { ElMessage.error('生成失败: ' + (e.response?.data?.error || e.message)) } finally { genLoading.value = false } }
const doExecute = async () => {
  if (!selectedDeviceId.value) { ElMessage.warning('请选择设备'); return }
  if (!form.ai_model_config_id) { ElMessage.warning('请选择 AI 模型'); return }
  if (!form.ai_prompt.trim()) { ElMessage.warning('请输入测试步骤'); return }
  if (replayMode.value && replayList.value.length === 0) { ElMessage.warning('暂无录制数据，请先录制'); return }
  executing.value = true
  try {
    if (!currentCaseId.value || currentCaseId.value === draftId) await saveCase()
    const { data } = await api.post(`/ui-automation/midscene/cases/${currentCaseId.value}/execute/`, { device_id: selectedDeviceId.value, auto_plan: autoPlanMode.value, record: recordMode.value, replay: replayMode.value, replay_index: selectedReplayIndex.value, clear_app_data: clearAppData.value })
    execution.value = { id: data.execution_id, status: 'pending', progress: 0, total_steps: 0, steps_detail: [], passed_steps: 0, failed_steps: 0 }
    currentScreenshot.value = ''; currentReasoning.value = []; currentStep.value = 0
    startPolling(data.execution_id)
  } catch (e) { ElMessage.error('执行失败: ' + (e.response?.data?.error || e.message)) }
  finally { executing.value = false }
}
const stopExecution = async () => { if (!execution.value?.id) return; try { await api.post(`/ui-automation/midscene/executions/${execution.value.id}/stop/`); execution.value.status = 'stopped'; ElMessage.info('已停止') } catch (e) {} }
const startPolling = (execId) => { stopPolling(); const poll = async () => { try { const { data } = await api.get(`/ui-automation/midscene/executions/${execId}/`); execution.value = { ...execution.value, ...data }; if (data.steps_detail?.length) { const last = data.steps_detail[data.steps_detail.length - 1]; currentStep.value = last.step; currentScreenshot.value = last.screenshot || ''; currentReasoning.value = last.aiReasoning || [] }; if (!['pending', 'running'].includes(data.status)) stopPolling() } catch (e) {} }; pollTimer = setInterval(poll, 2000); poll() }
const stopPolling = () => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
const previewStep = (s) => { if (s.screenshot) { previewImage.value = s.screenshot; showPreview.value = true } }
onMounted(() => { loadCases(); loadProjects(); loadDevices(); loadVisionModels() })
onUnmounted(() => stopPolling())
</script>

<style scoped lang="scss">
/* =============================================
   Endfield Complex — Midscene Testing Shell
   ============================================= */
.ms-shell {
  --ms-ink: #191919;
  --ms-paper: #f2f2f0;
  --ms-signal: #fffa00;
  --ms-state: #00ffa2;
  --ms-rail-w: 272px;
  --ms-zone-gap: 1px;

  display: flex;
  height: calc(100vh - 52px);
  background: #e8e8e2;
  position: relative;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  overflow: hidden;
}

/* Grid layer */
.ms-grid {
  position: absolute; inset: 0; pointer-events: none; z-index: 0;
  background-image:
    linear-gradient(to right, rgba(0,0,0,.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0,0,0,.04) 1px, transparent 1px);
  background-size: 64px 64px;
}

/* ============================================
   Left Rail (pale Endfield)
   ============================================ */
.ms-rail {
  width: var(--ms-rail-w);
  flex-shrink: 0;
  background: #fafaf8;
  display: flex; flex-direction: column;
  position: relative; z-index: 2;
  border-right: 1px solid #e4e4de;

  &__head {
    padding: 20px 16px 14px;
    border-bottom: 1px solid #e8e8e2;
    display: flex; flex-direction: column; gap: 12px;
  }
  &__title-row {
    display: flex; align-items: baseline; gap: 10px;
  }
  &__idx {
    font-size: 28px; font-weight: 900; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #e0e0da; line-height: 1; letter-spacing: -.02em;
  }
  &__label {
    font-size: 11px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .18em; color: #b0b0a8;
    flex: 1;
  }
  &__count {
    font-size: 13px; font-weight: 700; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #888;
    &::before { content: ''; display: inline-block; width: 6px; height: 6px; background: #00bf7a; margin-right: 6px; vertical-align: middle; }
  }
  &__list {
    flex: 1; overflow-y: auto;
    &::-webkit-scrollbar { width: 3px; }
    &::-webkit-scrollbar-thumb { background: #d8d8d2; border-radius: 0; }
  }
  &__empty {
    padding: 48px 16px; text-align: center; color: #ccc; font-size: 13px; line-height: 1.6;
  }
  &__foot {
    padding: 14px 16px; border-top: 1px solid #e8e8e2;
  }
}

.ms-case-item {
  all: unset;
  display: flex; align-items: center; gap: 0;
  width: 100%; box-sizing: border-box;
  padding: 14px 16px 14px 12px;
  border-bottom: 1px solid #ededed;
  cursor: pointer;
  position: relative;
  transition: background .12s, padding-left .15s;
  &:hover { background: #f2f2ed; }

  &.is-active {
    background: #fefde8;
    border-left: 3px solid #fffa00;
    padding-left: 9px;
  }
  &.is-draft {
    .ms-case-item__name { color: #b8860b; }
    .ms-case-item__draft-mark { color: #b8860b; }
  }

  &__num {
    width: 26px; flex-shrink: 0;
    font-size: 13px; font-weight: 700; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #ccc; text-align: right; margin-right: 12px;
  }
  &:hover &__num { color: #999; }
  &.is-active &__num { color: #b8a800; }

  &__body {
    flex: 1; min-width: 0;
    display: flex; flex-direction: column; gap: 5px;
  }
  &__name {
    font-size: 13px; font-weight: 500; color: #333;
    line-height: 1.3;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  &__row {
    display: flex; align-items: center; gap: 10px;
    font-size: 11px; color: #aaa;
  }
  &__steps {
    font-family: "Space Grotesk", system-ui, sans-serif;
    letter-spacing: .03em;
  }
  &__rate {
    font-family: "Space Grotesk", system-ui, sans-serif; font-weight: 700; font-size: 12px;
    &.rate-pass { color: #00a86b; }
    &.rate-fail { color: #e04040; }
  }
  &__draft-mark {
    font-size: 10px; color: #b8860b; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .08em;
  }
  &__proj {
    font-size: 10px; color: #c0c0b8;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .06em;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  &__del {
    position: absolute; top: 10px; right: 8px; opacity: 0;
    color: #ccc; padding: 4px; cursor: pointer; transition: color .15s;
    &:hover { color: #e04040; }
  }
  &:hover &__del { opacity: 1; }
}

/* Pale rail select override */
.ms-select--dark {
  :deep(.el-input__wrapper) {
    background: #fff; border: 1px solid #d8d8d2;
    box-shadow: none; border-radius: 0;
    .el-input__inner { color: #555; font-size: 12px; }
    .el-input__suffix { color: #bbb; }
  }
}

/* ============================================
   Main Stage
   ============================================ */
.ms-stage {
  flex: 1; overflow-y: auto;
  padding: 20px;
  display: flex; flex-direction: column; gap: var(--ms-zone-gap);
  position: relative; z-index: 1;
  background: var(--ms-paper);
}

.ms-zone {
  background: #fff;
  &__head {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 20px 0;
  }
  &__kicker {
    font-size: 10px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .14em; color: #999;
    white-space: nowrap;
  }
  &__rule {
    flex: 1; height: 1px; background: #e8e8e4;
  }
  &__body {
    padding: 16px 20px;
  }
}

.ms-field-row {
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
}

/* ============================================
   Command Strip
   ============================================ */
.ms-cmd-strip {
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 10px;
  &__left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  &__right { display: flex; align-items: center; gap: 6px; }
  &__divider {
    display: inline-block; width: 1px; height: 20px; background: #e0e0dc; margin: 0 4px;
  }
}

.ms-switch-group {
  display: flex; align-items: center; gap: 14px;
}
.ms-switch {
  display: flex; align-items: center; gap: 4px; cursor: pointer;
  span { font-size: 12px; color: #666; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .04em; }
}

/* ============================================
   Inputs & Buttons
   ============================================ */
.ms-input :deep(.el-input__wrapper) { border-radius: 0 !important; box-shadow: none !important; border: 1px solid #d4d4ce; }
.ms-select :deep(.el-input__wrapper) { border-radius: 0 !important; box-shadow: none !important; border: 1px solid #d4d4ce; }
.ms-input--context { margin-bottom: 12px; :deep(.el-input__wrapper) { border-radius: 0 !important; box-shadow: none !important; } }

.ms-editor {
  :deep(textarea) {
    font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
    font-size: 14px; line-height: 1.8; border-radius: 0 !important;
    border-color: #d4d4ce !important;
  }
  &__actions { display: flex; gap: 8px; margin-top: 10px; }
}

.ms-btn {
  border-radius: 0 !important; font-size: 12px;
  font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .05em;
  &--full { width: 100%; border-radius: 0 !important; }
  &--save { border-radius: 0 !important; font-weight: 600; letter-spacing: .06em; }
  &--text { color: #999; }
}

/* ============================================
   Button color overrides (unscoped — must pierce Element Plus)
   ============================================ */
</style>

<style lang="scss">
.ms-shell {
  /* Execute: signal yellow */
  .ms-btn--exec.el-button--primary {
    --el-button-bg-color: #fffa00;
    --el-button-border-color: #fffa00;
    --el-button-text-color: #191919;
    --el-button-hover-bg-color: #e6e100;
    --el-button-hover-border-color: #e6e100;
    --el-button-hover-text-color: #191919;
    --el-button-disabled-bg-color: #f5f5f0;
    --el-button-disabled-border-color: #e0e0dc;
    --el-button-disabled-text-color: #ccc;
    border-radius: 0 !important; font-weight: 700;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .08em;
  }

  /* Stop: restrained dark */
  .ms-btn--stop.el-button {
    --el-button-bg-color: #191919;
    --el-button-border-color: #191919;
    --el-button-text-color: #f2f2f0;
    --el-button-hover-bg-color: #333;
    --el-button-hover-border-color: #333;
    --el-button-hover-text-color: #fff;
    border-radius: 0 !important; font-weight: 600;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .06em;
  }

  /* Save: dark ink */
  .ms-btn--save.el-button--primary {
    --el-button-bg-color: #191919;
    --el-button-border-color: #191919;
    --el-button-text-color: #f2f2f0;
    --el-button-hover-bg-color: #333;
    --el-button-hover-border-color: #333;
    --el-button-hover-text-color: #fff;
    border-radius: 0 !important; font-weight: 600;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .06em;
  }
}

/* ============================================
   Live Execution Stage
   ============================================ */
.ms-stage-live {
  background: #fff;
  &__status {
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .1em; color: #666;
    display: flex; align-items: center; gap: 6px;
  }
}

.ms-status-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
  &.dot-pending, &.dot-running { background: var(--ms-signal); animation: ms-pulse 1.2s ease-in-out infinite; }
  &.dot-passed { background: var(--ms-state); }
  &.dot-failed, &.dot-error { background: #f56c6c; }
  &.dot-stopped { background: #999; }
}

@keyframes ms-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .25; }
}

.ms-progress-bar {
  display: flex; align-items: center; gap: 14px; padding: 12px 20px 0;
  &__track {
    flex: 1; height: 4px; background: #e8e8e4;
  }
  &__fill {
    height: 100%; background: var(--ms-signal);
    transition: width .4s ease-out;
  }
  &__label {
    font-size: 13px; font-family: "Space Grotesk", system-ui, sans-serif;
    font-weight: 700; color: #666; min-width: 50px; text-align: right;
  }
}

.ms-dual {
  display: grid; grid-template-columns: 1fr 1fr; gap: 1px;
  padding: 16px 20px;
  &__pane {
    background: #1a1a1a;
    &--screen { border-right: 1px solid rgba(255,255,255,.06); }
  }
  &__label {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .14em; color: rgba(255,255,255,.28);
    padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,.06);
  }
  &__stage {
    min-height: 360px; display: flex; align-items: center; justify-content: center;
  }
  &__log {
    min-height: 360px; max-height: 500px; overflow-y: auto; padding: 12px 14px;
  }
  &__wait {
    color: rgba(255,255,255,.18); font-family: "Space Grotesk", system-ui, sans-serif;
    font-size: 12px; letter-spacing: .1em;
  }
}

.ms-screen-img { max-width: 100%; max-height: 520px; object-fit: contain; }

.ms-log-line {
  padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,.04);
  font-size: 13px; color: rgba(255,255,255,.7); line-height: 1.5;
  &:last-child { border-bottom: none; }
}

.ms-step-badges {
  display: flex; flex-wrap: wrap; gap: 6px; padding: 12px 20px 20px;
}

.ms-step-badge {
  all: unset;
  cursor: pointer;
  padding: 5px 12px; font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif;
  background: #f2f2f0; color: #666;
  border: 1px solid #e0e0dc;
  transition: all .15s;
  &:hover { border-color: #999; color: #333; }
  &.badge-passed { background: rgba(0,255,162,.08); border-color: rgba(0,255,162,.25); color: #1a8051; }
  &.badge-failed { background: rgba(245,108,108,.06); border-color: rgba(245,108,108,.2); color: #c03939; }
  &.badge-running { border-color: var(--ms-signal); color: #666; animation: ms-pulse 1s infinite; }
  &__mark { font-weight: 700; margin-right: 2px; }
}

/* ============================================
   Responsive
   ============================================ */
@media (max-width: 1024px) {
  .ms-rail { --ms-rail-w: 220px; }
  .ms-stage { padding: 14px; }
  .ms-dual { grid-template-columns: 1fr; }
  .ms-cmd-strip { flex-direction: column; align-items: flex-start; }
}
@media (max-width: 768px) {
  .ms-shell { flex-direction: column; }
  .ms-rail { width: 100%; max-height: 240px; }
  .ms-dual { grid-template-columns: 1fr; }
}
</style>
