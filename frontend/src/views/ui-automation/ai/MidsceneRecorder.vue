<template>
  <div class="ms-subpage" data-ark-theme="endfield" data-ark-depth="complex">

    <!-- Zone A: 采集控制 -->
    <section class="ms-zone">
      <header class="ms-zone__head">
        <span class="ms-zone__kicker">MANUAL RECORDER / 01</span>
        <span class="ms-zone__rule" aria-hidden="true"></span>
        <span v-if="recording" class="ms-rec__live"><i class="ms-rec__dot" aria-hidden="true"></i>RECORDING {{ elapsed }}</span>
      </header>
      <div class="ms-zone__body">
        <div class="ms-rec__panel">
          <div class="ms-rec__row">
            <label class="ms-rec__label">目标设备</label>
            <el-select v-model="deviceId" placeholder="选择 Android 设备" filterable class="ms-select ms-select--dev" :disabled="recording">
              <el-option
                v-for="d in androidDevices"
                :key="d.id"
                :label="`${d.name || d.device_id} (${d.platform_display})${d.status === 'locked' ? ' 🔒' : ''}`"
                :value="d.id"
                :disabled="d.status === 'offline'"
              />
            </el-select>
            <el-button size="small" :icon="Refresh" class="ms-btn" @click="loadDevices">刷新</el-button>
          </div>
          <div class="ms-rec__row ms-rec__row--actions">
            <el-button v-if="!recording" size="medium" type="primary" class="ms-btn--action" :disabled="!deviceId" :loading="starting" @click="startRecord">
              <el-icon style="margin-right:6px"><VideoPlay /></el-icon>开始录制
            </el-button>
            <el-button v-else size="medium" type="danger" class="ms-btn--stop" :loading="stopping" @click="stopRecord">
              <el-icon style="margin-right:6px"><SwitchButton /></el-icon>停止录制
            </el-button>
          </div>
          <ul class="ms-rec__guide">
            <li>点击「开始录制」后，直接在手机上真实操作（点击 / 滑动 / 长按）。</li>
            <li>手指抬起后停顿 ≥1.5 秒，会自动切成新的一步；文本输入暂时无法采集，请在预览里补「输入」步骤。</li>
            <li>停止后进入预览：可改步骤名、补输入动作、删多余步骤，再保存为独立用例（绑定项目）。</li>
            <li>保存后的脚本在下方「脚本库」中管理，执行使用纯动作直放（不做 VLM 匹配）。</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- Zone B: 预览编辑 -->
    <section v-if="preview" class="ms-zone">
      <header class="ms-zone__head">
        <span class="ms-zone__kicker">PREVIEW / 02</span>
        <span class="ms-zone__rule" aria-hidden="true"></span>
        <span class="ms-zone__meta">{{ steps.length }} 步 · {{ resolutionText }}</span>
      </header>
      <div class="ms-zone__body">
        <div v-if="steps.length === 0" class="ms-rec__empty">没有解析到动作（可能设备未采集到触摸事件），请重新录制。</div>
        <div v-for="(step, si) in steps" :key="si" class="ms-step">
          <div class="ms-step__head">
            <span class="ms-step__idx">{{ String(si + 1).padStart(2, '0') }}</span>
            <el-input v-model="step.instruction" size="small" class="ms-step__name" placeholder="步骤名称" />
            <el-button size="small" text type="danger" :icon="Delete" class="ms-step__del" @click="removeStep(si)">删除</el-button>
          </div>
          <div class="ms-step__actions">
            <div v-for="(act, ai) in step.actions" :key="ai" class="ms-act">
              <span class="ms-plat-tag" :class="'act-' + act.action">{{ act.action }}</span>
              <span v-if="act.action === 'input'" class="ms-act__text">
                <el-input v-model="act.text" size="small" placeholder="输入文本" class="ms-act__input" />
              </span>
              <span v-else class="ms-act__coord ms-mono">
                {{ fmtAction(act) }}
              </span>
              <el-button size="small" text type="danger" :icon="Delete" @click="step.actions.splice(ai, 1)"></el-button>
            </div>
            <el-button size="small" text type="primary" :icon="Edit" class="ms-btn--text" @click="addInput(step)">补输入步骤</el-button>
          </div>
        </div>
        <el-button size="small" text :icon="Plus" class="ms-btn--text" @click="addEmptyStep">＋ 添加空步骤</el-button>
        <div class="ms-save-bar">
          <el-button type="primary" class="ms-btn--action" :loading="saving" @click="openSave">
            <el-icon style="margin-right:6px"><FolderAdd /></el-icon>保存为独立用例
          </el-button>
        </div>
      </div>
    </section>

    <!-- Zone C: 脚本库 -->
    <section class="ms-zone">
      <header class="ms-zone__head">
        <span class="ms-zone__kicker">SCRIPT LIBRARY / 03</span>
        <span class="ms-zone__rule" aria-hidden="true"></span>
        <el-select v-model="scriptFilter" clearable filterable placeholder="按项目过滤" class="ms-select" style="width:180px" @change="loadScripts">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-button size="small" :icon="Refresh" class="ms-btn" @click="loadScripts">刷新</el-button>
      </header>
      <div class="ms-zone__body">
        <el-table :data="scripts" v-loading="scriptsLoading" class="ms-table" stripe>
          <el-table-column prop="name" label="脚本名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="project" label="项目" width="130" show-overflow-tooltip />
          <el-table-column prop="device" label="录制设备" width="140" show-overflow-tooltip />
          <el-table-column label="分辨率" width="110">
            <template #default="{ row }">
              <span class="ms-mono">{{ fmtRes(row.resolution) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="step_count" label="步骤" width="70" align="center" />
          <el-table-column label="录制时间" width="140">
            <template #default="{ row }">{{ fmtRecorded(row.recorded_at) }}</template>
          </el-table-column>
          <el-table-column label="最近执行" width="130">
            <template #default="{ row }">
              <span v-if="row.latest_result" :class="'ms-run-tag run-' + row.latest_result.status">
                {{ statusText(row.latest_result.status) }}<template v-if="row.latest_result.status === 'passed'"> · {{ row.latest_result.pass_rate }}%</template>
              </span>
              <span v-else class="ms-text--muted">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="230" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text type="primary" class="ms-btn--table" @click="openPreview(row)">预览</el-button>
              <el-button size="small" type="primary" class="ms-btn--table" :disabled="!!activeExec" @click="openExec(row)">执行</el-button>
              <el-button size="small" text class="ms-btn--table" @click="renameScript(row)">重命名</el-button>
              <el-button size="small" text type="danger" class="ms-btn--table" @click="removeScript(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!scriptsLoading && scripts.length === 0" description="暂无手操脚本，先录制一段吧" />
      </div>
    </section>

    <!-- 保存弹窗（只新建独立用例） -->
    <el-dialog v-model="saveVisible" title="保存为独立用例" width="480px" :close-on-click-modal="false">
      <el-form label-width="90px">
        <el-form-item label="用例名称">
          <el-input v-model="saveForm.name" placeholder="留空自动命名：手操录制 MM-DD HH:MM" />
        </el-form-item>
        <el-form-item label="所属项目" required>
          <el-select v-model="saveForm.project_id" filterable placeholder="选择项目" style="width:100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <div class="ms-rec__dialog-hint">保存后即成为独立用例（绑定所选项目），进入下方脚本库，可随时用纯动作直放执行。</div>
      </el-form>
      <template #footer>
        <el-button @click="saveVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!saveForm.project_id" @click="doSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 预览弹窗（只读） -->
    <el-dialog v-model="previewVisible" :title="previewEntry?.name || '脚本预览'" width="620px">
      <div v-if="previewEntry" class="ms-preview">
        <div v-for="(s, si) in previewEntry.steps" :key="si" class="ms-preview__step">
          <div class="ms-preview__head">
            <span class="ms-step__idx">{{ String(si + 1).padStart(2, '0') }}</span>
            <span class="ms-preview__name">{{ s.instruction || '（未命名步骤）' }}</span>
          </div>
          <div v-for="(a, ai) in (s.actions || [])" :key="ai" class="ms-act">
            <span class="ms-plat-tag" :class="'act-' + a.action">{{ a.action }}</span>
            <span v-if="a.action === 'input'" class="ms-mono">输入：{{ a.text }}</span>
            <span v-else class="ms-mono">{{ fmtAction(a) }}</span>
          </div>
          <div v-if="!s.actions || s.actions.length === 0" class="ms-text--muted">（无动作）</div>
        </div>
      </div>
    </el-dialog>

    <!-- 执行弹窗 -->
    <el-dialog v-model="execVisible" :title="`执行脚本 - ${execForm.script?.name || ''}`" width="520px" :close-on-click-modal="!execRunning">
      <el-form label-width="90px">
        <el-form-item label="目标设备" required>
          <el-select v-model="execForm.device_id" filterable placeholder="选择 Android 设备" style="width:100%" :disabled="execRunning">
            <el-option
              v-for="d in androidDevices"
              :key="d.id"
              :label="`${d.name || d.device_id} (${d.platform_display})${d.status === 'locked' ? ' 🔒' : ''}`"
              :value="d.id"
              :disabled="d.status === 'offline'"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="执行选项">
          <el-checkbox v-model="execForm.clear_app_data" :disabled="execRunning">执行前清除数据重启</el-checkbox>
        </el-form-item>
        <el-form-item label="安装包">
          <el-select v-model="execForm.install_package_id" clearable filterable placeholder="可选" style="width:100%" :disabled="execRunning">
            <el-option v-for="p in androidPackages" :key="p.id" :label="`${p.name || p.package_name} ${p.version_name ? 'v' + p.version_name : ''}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="execMatchText" label="脚本匹配">
          <span :class="execMatchBad" class="ms-match-text">{{ execMatchText }}</span>
        </el-form-item>
        <el-form-item v-if="execRunning || execStatus" label="执行状态">
          <el-progress :percentage="execProgress" :status="execFinish ? (execStatus === 'passed' ? 'success' : 'exception') : undefined" style="width:100%" />
          <div class="ms-text--muted" style="font-size:12px">{{ execStatusText }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button v-if="execRunning" @click="stopExec">停止</el-button>
        <el-button v-else @click="execVisible = false">关闭</el-button>
        <el-button v-if="!execRunning" type="primary" :loading="executing" :disabled="!execForm.device_id || !!activeExec" @click="startExec">
          开始执行
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoPlay, SwitchButton, Refresh, Delete, Edit, Plus, FolderAdd } from '@element-plus/icons-vue'
import api from '@/utils/api'

// ---- 录制 ----
const devices = ref([])
const deviceId = ref(null)
const recording = ref(false)
const starting = ref(false)
const stopping = ref(false)
const sessionId = ref(null)
const elapsed = ref('00:00')
const preview = ref(null)
const steps = ref([])
const resolution = ref(null)
let timer = null
let recordStartedAt = 0

// ---- 保存 ----
const saving = ref(false)
const saveVisible = ref(false)
const saveForm = ref({ name: '', project_id: null })

// ---- 脚本库 ----
const projects = ref([])
const scripts = ref([])
const scriptsLoading = ref(false)
const scriptFilter = ref(null)
const previewVisible = ref(false)
const previewEntry = ref(null)

// ---- 执行 ----
const packages = ref([])
const execVisible = ref(false)
const execForm = ref({ script: null, device_id: null, clear_app_data: false, install_package_id: null })
const execRunning = ref(false)
const executing = ref(false)
const execStatus = ref('')
const execProgress = ref(0)
const execExecId = ref(null)
const execMatchText = ref('')
const execMatchBad = ref('')
const activeExec = ref(null)
let execPollTimer = null

const androidDevices = computed(() => devices.value.filter(d => d.platform === 'android'))
const androidPackages = computed(() => packages.value.filter(p => p.platform === 'android'))
const resolutionText = computed(() => (resolution.value ? `${resolution.value.width}x${resolution.value.height}` : ''))
const execFinish = computed(() => ['passed', 'failed', 'error', 'stopped'].includes(execStatus.value))
const execStatusText = computed(() => statusText(execStatus.value))

const fmtAction = act => {
  if (act.action === 'tap' || act.action === 'click' || act.action === 'long_press') {
    return `(${pct(act.x_pct)}, ${pct(act.y_pct)})${act.duration ? ` · ${act.duration}ms` : ''}`
  }
  if (act.action === 'swipe') {
    return `(${pct(act.x1_pct)}, ${pct(act.y1_pct)}) → (${pct(act.x2_pct)}, ${pct(act.y2_pct)}) · ${act.duration}ms`
  }
  return act.action || ''
}
const pct = v => (v === null || v === undefined ? '-' : `${Math.round(v)}%`)
const fmtRes = r => (r?.width && r?.height ? `${r.width}x${r.height}` : '-')
const fmtRecorded = t => (t ? String(t).replace('T', ' ').slice(0, 16) : '-')
const statusText = s => ({ pending: '等待中', running: '执行中', passed: '通过', failed: '失败', error: '异常', stopped: '已停止' }[s] || s)

// ---- 设备/项目/包 ----
const loadDevices = async () => {
  try {
    const { data } = await api.get('/ui-automation/midscene/devices/simple_list/')
    devices.value = data || []
  } catch (e) {
    ElMessage.error('加载设备失败')
  }
}

const loadProjects = async () => {
  try {
    const { data } = await api.get('/ui-automation/midscene/projects/')
    projects.value = data.results || []
  } catch (e) {}
}

const loadPackages = async () => {
  try {
    const { data } = await api.get('/ui-automation/midscene/packages/')
    packages.value = data.results || []
  } catch (e) {}
}

// ---- 脚本库 ----
const loadScripts = async () => {
  scriptsLoading.value = true
  try {
    const params = {}
    if (scriptFilter.value) params.project = scriptFilter.value
    const { data } = await api.get('/ui-automation/midscene/record-sessions/scripts/', { params })
    scripts.value = data || []
  } catch (e) {
    ElMessage.error('加载脚本库失败')
  } finally {
    scriptsLoading.value = false
  }
}

const openPreview = async (row) => {
  try {
    const { data } = await api.get(`/ui-automation/midscene/cases/${row.case_id}/`)
    const entries = data.replay_data || []
    const entry = entries[row.entry_index] || {}
    previewEntry.value = { name: entry.name || row.name, steps: entry.steps || [] }
    previewVisible.value = true
  } catch (e) {
    ElMessage.error('加载脚本详情失败')
  }
}

const renameScript = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('输入新的脚本名称', '重命名', {
      inputValue: row.name,
      inputValidator: v => (v && v.trim() ? true : '名称不能为空'),
    })
    await api.post(`/ui-automation/midscene/cases/${row.case_id}/rename_replay/`, {
      index: row.entry_index,
      name: value.trim(),
    })
    ElMessage.success('已重命名')
    loadScripts()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('重命名失败')
  }
}

const removeScript = async (row) => {
  try {
    await ElMessageBox.confirm(`删除脚本「${row.name}」？${row.entry_count === 1 ? '该用例将一并删除。' : '仅删除该手操条目。'}`, '确认删除', { type: 'warning' })
    if (row.entry_count === 1) {
      await api.delete(`/ui-automation/midscene/cases/${row.case_id}/`)
    } else {
      await api.post(`/ui-automation/midscene/cases/${row.case_id}/delete_replay/`, { index: row.entry_index })
    }
    ElMessage.success('已删除')
    loadScripts()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// ---- 执行 ----
const openExec = (row) => {
  execForm.value = { script: row, device_id: null, clear_app_data: false, install_package_id: null }
  execStatus.value = ''
  execProgress.value = 0
  execExecId.value = null
  execMatchText.value = ''
  execMatchBad.value = ''
  loadDevices()
  loadPackages()
  execVisible.value = true
}

const checkExecMatch = async () => {
  if (!execForm.value.device_id || !execForm.value.script) return true
  try {
    const { data } = await api.get(`/ui-automation/midscene/cases/${execForm.value.script.case_id}/replay_match/`, {
      params: { device_id: execForm.value.device_id, replay_index: execForm.value.script.entry_index },
    })
    const level = data.match_level
    if (level === 'exact' || level === 'ok') {
      execMatchText.value = '脚本与设备匹配良好'
      execMatchBad.value = 'ms-match--ok'
      return true
    }
    if (level === 'unknown') {
      execMatchText.value = '无法读取设备分辨率，坐标可能偏移'
      execMatchBad.value = 'ms-match--warn'
      return true
    }
    execMatchText.value = level === 'no_match' ? '未找到该设备的匹配脚本，坐标可能偏移' : '分辨率与录制设备不符，坐标可能偏移'
    execMatchBad.value = 'ms-match--bad'
    return false
  } catch (e) {
    return true
  }
}

const startExec = async () => {
  const row = execForm.value
  if (!row.device_id) { ElMessage.warning('请选择设备'); return }
  const matched = await checkExecMatch()
  if (matched === false) {
    try {
      await ElMessageBox.confirm('脚本与设备不匹配，坐标可能偏移。仍要执行？', '脚本不匹配', { type: 'warning' })
    } catch (e) {
      return
    }
  }
  executing.value = true
  try {
    const { data } = await api.post(`/ui-automation/midscene/cases/${row.script.case_id}/execute/`, {
      device_id: row.device_id,
      replay: true,
      script_replay: true,
      replay_index: row.script.entry_index,
      clear_app_data: row.clear_app_data,
      install_package_id: row.install_package_id || null,
      auto_plan: false,
    })
    execExecId.value = data.execution_id
    activeExec.value = { execution_id: data.execution_id, case_id: row.script.case_id }
    execRunning.value = true
    execStatus.value = 'running'
    execProgress.value = 2
    execPollTimer = setInterval(pollExec, 2000)
    ElMessage.success('执行已开始（纯动作直放）')
    loadScripts()
  } catch (e) {
    ElMessage.error('发起执行失败: ' + (e.response?.data?.error || e.message))
  } finally {
    executing.value = false
  }
}

const pollExec = async () => {
  if (!execExecId.value) return
  try {
    const { data } = await api.get(`/ui-automation/midscene/executions/${execExecId.value}/`)
    execStatus.value = data.status
    execProgress.value = data.progress || 0
    if (execFinish.value) {
      if (execPollTimer) { clearInterval(execPollTimer); execPollTimer = null }
      execRunning.value = false
      activeExec.value = null
      ElMessage[data.status === 'passed' ? 'success' : 'warning'](`执行结束: ${data.status}`)
      loadScripts()
    }
  } catch (e) {
    if (execPollTimer) { clearInterval(execPollTimer); execPollTimer = null }
    execRunning.value = false
    activeExec.value = null
  }
}

const stopExec = async () => {
  if (!execExecId.value) return
  try {
    await api.post(`/ui-automation/midscene/executions/${execExecId.value}/stop/`)
    ElMessage.info('已请求停止')
  } catch (e) {
    ElMessage.error('停止失败')
  }
}

// ---- 录制流程 ----
const tick = () => {
  const s = Math.max(0, Math.floor((Date.now() - recordStartedAt) / 1000))
  const mm = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  elapsed.value = `${mm}:${ss}`
}

const startRecord = async () => {
  if (!deviceId.value) { ElMessage.warning('请选择设备'); return }
  starting.value = true
  try {
    const { data } = await api.post('/ui-automation/midscene/record-sessions/start/', { device_id: deviceId.value })
    sessionId.value = data.session_id
    recording.value = true
    recordStartedAt = Date.now()
    elapsed.value = '00:00'
    timer = setInterval(tick, 1000)
    preview.value = null
    steps.value = []
    resolution.value = null
    ElMessage.success('录制已开始，请在手机上操作')
  } catch (e) {
    ElMessage.error('开始录制失败: ' + (e.response?.data?.error || e.message))
  } finally {
    starting.value = false
  }
}

const stopRecord = async () => {
  if (!sessionId.value) return
  stopping.value = true
  try {
    const { data } = await api.post(`/ui-automation/midscene/record-sessions/${sessionId.value}/stop/`)
    recording.value = false
    if (timer) { clearInterval(timer); timer = null }
    preview.value = data
    steps.value = (data.steps || []).map(s => ({
      instruction: s.instruction || '步骤',
      actions: (s.actions || []).map(a => ({ ...a })),
    }))
    resolution.value = data.resolution || null
    ElMessage.success(data.message || '录制已停止')
  } catch (e) {
    ElMessage.error('停止录制失败: ' + (e.response?.data?.error || e.message))
  } finally {
    stopping.value = false
  }
}

const removeStep = si => {
  steps.value.splice(si, 1)
}

const addInput = step => {
  step.actions.push({ action: 'input', text: '' })
}

const addEmptyStep = () => {
  steps.value.push({ instruction: `步骤 ${steps.value.length + 1}`, actions: [] })
}

const openSave = () => {
  saveForm.value = { name: '', project_id: null }
  saveVisible.value = true
}

const doSave = async () => {
  if (!sessionId.value) return
  if (!saveForm.value.project_id) { ElMessage.warning('请选择所属项目'); return }
  saving.value = true
  try {
    const body = { project_id: saveForm.value.project_id }
    if (saveForm.value.name.trim()) body.name = saveForm.value.name.trim()
    const { data } = await api.post(`/ui-automation/midscene/record-sessions/${sessionId.value}/save/`, body)
    ElMessage.success(data.message || '已保存')
    saveVisible.value = false
    preview.value = null
    steps.value = []
    loadScripts()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.error || e.message))
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadDevices()
  loadProjects()
  loadScripts()
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  if (execPollTimer) clearInterval(execPollTimer)
})
</script>

<style scoped lang="scss">
.ms-subpage {
  height: calc(100vh - 52px); background: transparent; position: relative; padding: 20px;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", sans-serif;
}
.ms-zone {
  position: relative; z-index: 1; background: #fff; margin-bottom: 16px;
  &__head { display: flex; align-items: center; gap: 14px; padding: 16px 24px 0; }
  &__kicker { font-size: 10px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .14em; color: #999; white-space: nowrap; }
  &__rule { flex: 1; height: 1px; background: #e8e8e4; }
  &__meta { font-size: 12px; color: #666; white-space: nowrap; }
  &__body { padding: 16px 24px 24px; }
}
.ms-btn--action { border-radius: 0 !important; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .06em; font-size: 12px; }
.ms-btn--stop { border-radius: 0 !important; font-size: 12px; }
.ms-btn--table { border-radius: 0 !important; font-size: 12px; }
.ms-rec__live { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-family: "IBM Plex Mono", Consolas, monospace; color: #c0392b; }
.ms-rec__dot { width: 8px; height: 8px; border-radius: 50%; background: #c0392b; animation: ms-blink 1s steps(2, start) infinite; }
@keyframes ms-blink { 50% { opacity: .25; } }
.ms-rec__panel { padding: 4px 0; }
.ms-rec__row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; flex-wrap: wrap;
  &--actions { margin-bottom: 10px; }
}
.ms-rec__label { font-size: 12px; color: #666; white-space: nowrap; }
.ms-select--dev { width: 360px; max-width: 100%; }
.ms-rec__guide { margin: 0; padding: 12px 16px 12px 34px; background: #f7f7f5; border-left: 2px solid #d4a017; font-size: 12px; color: #555; line-height: 1.9; }
.ms-rec__empty { padding: 24px; text-align: center; color: #999; font-size: 13px; }
.ms-rec__dialog-hint { font-size: 12px; color: #999; line-height: 1.7; }
.ms-save-bar { margin-top: 14px; }
.ms-step { border: 1px solid #ecebe7; border-left: 3px solid #d4a017; margin-bottom: 10px;
  &__head { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: #fafaf8; }
  &__idx { font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif; font-size: 14px; font-weight: 700; color: #d4a017; white-space: nowrap; }
  &__name { flex: 1; max-width: 480px; }
  &__del { margin-left: auto; }
  &__actions { padding: 8px 12px; display: flex; flex-direction: column; gap: 6px; }
}
.ms-act { display: flex; align-items: center; gap: 10px; font-size: 12px;
  &__coord { color: #333; }
  &__input { width: 280px; }
}
.ms-plat-tag {
  font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .06em; font-weight: 700; padding: 2px 6px; border: 1px solid;
  &.act-tap { color: #1a8051; border-color: #1a8051; }
  &.act-swipe { color: #2e5ea8; border-color: #2e5ea8; }
  &.act-long_press { color: #a85a2e; border-color: #a85a2e; }
  &.act-input { color: #7a5ea8; border-color: #7a5ea8; }
}
.ms-mono { font-family: "IBM Plex Mono", Consolas, monospace; }
.ms-btn--text { border-radius: 0 !important; font-size: 12px; }
.ms-run-tag { font-size: 12px;
  &.run-passed { color: #1a8051; }
  &.run-failed, &.run-error { color: #c0392b; }
  &.run-pending, &.run-running { color: #a8761a; }
  &.run-stopped { color: #888; }
}
.ms-match-text { font-size: 12px;
  &.ms-match--ok { color: #1a8051; }
  &.ms-match--warn { color: #a8761a; }
  &.ms-match--bad { color: #c0392b; }
}
.ms-preview__step { margin-bottom: 14px; }
.ms-preview__head { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.ms-preview__name { font-size: 13px; color: #333; }
</style>

<style lang="scss">
.ms-subpage {
  .el-button--primary { --el-button-bg-color: #191919; --el-button-border-color: #191919; --el-button-text-color: #f2f2f0; --el-button-hover-bg-color: #333; --el-button-hover-border-color: #333; --el-button-hover-text-color: #fff; border-radius: 0 !important; }
  .el-button--danger { border-radius: 0 !important; }
  .el-dialog__title { font-family: "Space Grotesk", system-ui, sans-serif; }
}
</style>
