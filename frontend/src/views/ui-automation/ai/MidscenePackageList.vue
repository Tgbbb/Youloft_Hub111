<template>
  <div class="ms-subpage" data-ark-theme="endfield" data-ark-depth="complex">

    <section class="ms-zone">
      <header class="ms-zone__head">
        <span class="ms-zone__kicker">PACKAGES / REGISTRY</span>
        <span class="ms-zone__rule" aria-hidden="true"></span>
        <el-button type="primary" @click="uploadVisible = true" class="ms-btn--action"><el-icon><Upload /></el-icon> 上传安装包</el-button>
      </header>
      <div class="ms-zone__body">
        <el-table :data="packages" v-loading="loading" class="ms-table" stripe>
          <el-table-column label="平台" width="80">
            <template #default="{ row }">
              <span class="ms-plat-tag" :class="'plat-' + row.platform">{{ row.platform_display }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="应用名称" width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.name || row.package_name || '-' }}</template>
          </el-table-column>
          <el-table-column prop="package_name" label="包名 / Bundle ID" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="ms-mono">{{ row.package_name || '未解析' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="版本" width="130">
            <template #default="{ row }">
              <span v-if="row.version_name">{{ row.version_name }}<span v-if="row.version_code" class="ms-text--muted"> ({{ row.version_code }})</span></span>
              <span v-else class="ms-text--muted">未解析</span>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="90">
            <template #default="{ row }">{{ row.size_display || '-' }}</template>
          </el-table-column>
          <el-table-column label="上传信息" width="170">
            <template #default="{ row }">
              <div class="ms-subline">{{ row.created_by_name || '-' }}</div>
              <div class="ms-subline ms-text--muted">{{ fmtTime(row.created_at) }}</div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.platform === 'android'" size="small" type="primary" @click="openInstall(row)" class="ms-btn--table">安装</el-button>
              <el-tooltip v-else content="iOS 安装暂未支持" placement="top">
                <el-button size="small" disabled class="ms-btn--table">安装</el-button>
              </el-tooltip>
              <el-button size="small" @click="openRecords(row)" class="ms-btn--table">安装记录</el-button>
              <el-button size="small" type="danger" @click="deletePackage(row)" class="ms-btn--table">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <!-- 上传弹窗 -->
    <el-dialog v-model="uploadVisible" title="上传安装包" width="520px" :close-on-click-modal="false">
      <el-form :model="uploadForm" label-width="80px">
        <el-form-item label="安装包" required>
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            accept=".apk,.ipa"
            :on-change="onFileChange"
            :on-remove="() => { uploadForm.file = null; uploadForm.fileName = '' }"
            :file-list="uploadFileList"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件到此处，或<em>点击选择</em></div>
            <template #tip>
              <div class="el-upload__tip">仅支持 .apk / .ipa，上传后自动解析包名与版本</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="应用名称">
          <el-input v-model="uploadForm.name" placeholder="留空则使用包名或文件名" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="uploadForm.description" type="textarea" :rows="2" placeholder="可选，如：冒烟测试包 / 预发布包" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="doUpload">上传</el-button>
      </template>
    </el-dialog>

    <!-- 安装弹窗 -->
    <el-dialog v-model="installVisible" :title="`安装到设备 - ${currentPackage?.name || ''}`" width="560px">
      <el-form label-width="90px">
        <el-form-item label="目标设备" required>
          <el-select v-model="installDeviceIds" multiple placeholder="选择在线/可用的 Android 设备" style="width: 100%">
            <el-option
              v-for="d in installableDevices"
              :key="d.id"
              :label="`${d.name || d.device_id} (${d.platform_display})`"
              :value="d.id"
              :disabled="d.status === 'locked'"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="安装选项">
          <el-checkbox v-model="installOptions.overwrite">覆盖安装（-r）</el-checkbox>
          <el-checkbox v-model="installOptions.downgrade">允许降级（-d）</el-checkbox>
          <el-checkbox v-model="installOptions.launch">安装后启动</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="installVisible = false">取消</el-button>
        <el-button type="primary" :loading="installing" :disabled="installDeviceIds.length === 0" @click="doInstall">
          开始安装 ({{ installDeviceIds.length }})
        </el-button>
      </template>
    </el-dialog>

    <!-- 安装记录抽屉 -->
    <el-drawer v-model="recordsVisible" :title="`安装记录 - ${currentPackage?.name || ''}`" size="520px">
      <div v-loading="recordsLoading" class="records-wrap">
        <el-table :data="records" size="small">
          <el-table-column label="设备" min-width="120">
            <template #default="{ row }">{{ row.device_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ row.status_display }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="80">
            <template #default="{ row }">{{ row.duration ? row.duration.toFixed(1) + 's' : '-' }}</template>
          </el-table-column>
          <el-table-column label="时间" width="110">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="日志" width="70">
            <template #default="{ row }">
              <el-button v-if="row.log || row.error_message" size="small" text type="primary" @click="showLog(row)">查看</el-button>
              <span v-else class="ms-text--muted">-</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!recordsLoading && records.length === 0" description="暂无安装记录" />
      </div>
    </el-drawer>

    <!-- 日志弹窗 -->
    <el-dialog v-model="logVisible" :title="`安装日志 - ${logRecord?.device_name || ''}`" width="640px">
      <pre class="ms-log">{{ logRecord?.error_message || logRecord?.log || '无输出' }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, UploadFilled } from '@element-plus/icons-vue'
import api from '@/utils/api'

const loading = ref(false)
const packages = ref([])

// 上传
const uploadVisible = ref(false)
const uploading = ref(false)
const uploadFileList = ref([])
const uploadForm = reactive({ name: '', description: '', file: null, fileName: '' })

// 安装
const devices = ref([])
const installVisible = ref(false)
const installing = ref(false)
const currentPackage = ref(null)
const installDeviceIds = ref([])
const installOptions = reactive({ overwrite: true, downgrade: false, launch: false })

// 安装记录
const recordsVisible = ref(false)
const recordsLoading = ref(false)
const records = ref([])
let recordsTimer = null
const logVisible = ref(false)
const logRecord = ref(null)

const fmtTime = (t) => (t ? String(t).replace('T', ' ').slice(0, 16) : '-')

const loadPackages = async () => {
  loading.value = true
  try {
    const { data } = await api.get('/ui-automation/midscene/packages/')
    packages.value = data.results || []
  } catch (e) {
    ElMessage.error('加载安装包失败')
  } finally {
    loading.value = false
  }
}

const loadDevices = async () => {
  try {
    const { data } = await api.get('/ui-automation/midscene/devices/')
    devices.value = data.results || []
  } catch (e) {}
}

const installableDevices = computed(() => devices.value.filter(d => d.platform === 'android' && d.status !== 'offline'))

const onFileChange = (file) => {
  if (!file || !file.raw) return
  uploadForm.file = file.raw
  uploadForm.fileName = file.name || ''
}

const doUpload = async () => {
  const rawFile = uploadForm.file
  if (!rawFile) {
    ElMessage.warning('请先选择安装包文件')
    return
  }
  if (!(rawFile instanceof File)) {
    console.error('[Upload] 文件对象异常:', rawFile)
    ElMessage.error('文件未正确读取，请重新选择文件')
    return
  }
  uploading.value = true
  const fd = new FormData()
  fd.append('file', rawFile)
  if (uploadForm.name.trim()) fd.append('name', uploadForm.name.trim())
  if (uploadForm.description.trim()) fd.append('description', uploadForm.description.trim())
  try {
    // 注意：api 实例全局默认 Content-Type: application/json，
    // axios 会把 FormData 转成 JSON 字符串导致文件丢失，必须显式指定 multipart
    const { data } = await api.post('/ui-automation/midscene/packages/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600000, // 大安装包上传+解析可能超过全局默认 30s，放宽到 10 分钟
    })
    ElMessage.success(`上传成功: ${data.name || data.package_name}`)
    uploadVisible.value = false
    uploadFileList.value = []
    uploadForm.name = ''
    uploadForm.description = ''
    uploadForm.file = null
    loadPackages()
  } catch (e) {
    const d = e.response?.data
    ElMessage.error(d?.error || '上传失败')
  } finally {
    uploading.value = false
  }
}

const deletePackage = async (row) => {
  try {
    await ElMessageBox.confirm(`删除「${row.name || row.package_name}」？文件将一并移除。`, '确认删除', { type: 'warning' })
    await api.delete(`/ui-automation/midscene/packages/${row.id}/`)
    ElMessage.success('已删除')
    loadPackages()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const openInstall = (row) => {
  currentPackage.value = row
  installDeviceIds.value = []
  installOptions.overwrite = true
  installOptions.downgrade = false
  installOptions.launch = false
  installVisible.value = true
}

const doInstall = async () => {
  if (installDeviceIds.value.length === 0) {
    ElMessage.warning('请选择设备')
    return
  }
  installing.value = true
  try {
    const { data } = await api.post(`/ui-automation/midscene/packages/${currentPackage.value.id}/install/`, {
      device_ids: installDeviceIds.value,
      overwrite: installOptions.overwrite,
      downgrade: installOptions.downgrade,
      launch: installOptions.launch,
    })
    ElMessage.success(data.message || '安装任务已提交')
    installVisible.value = false
    if (data.failed && data.failed.length > 0) {
      ElMessage.warning(data.failed.map(f => f.error).join('；'))
    }
    openRecords(currentPackage.value)
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '提交安装失败')
  } finally {
    installing.value = false
  }
}

const openRecords = (row) => {
  currentPackage.value = row
  recordsVisible.value = true
  loadRecords()
}

const loadRecords = async () => {
  if (!currentPackage.value) return
  recordsLoading.value = true
  try {
    const { data } = await api.get(`/ui-automation/midscene/install-records/?package=${currentPackage.value.id}`)
    records.value = data.results || []
    const hasActive = records.value.some(r => ['pending', 'running'].includes(r.status))
    if (recordsVisible.value && hasActive) {
      clearTimeout(recordsTimer)
      recordsTimer = setTimeout(loadRecords, 2000)
    }
  } catch (e) {
    ElMessage.error('加载安装记录失败')
  } finally {
    recordsLoading.value = false
  }
}

const statusType = (s) => ({ success: 'success', failed: 'danger', running: 'warning', pending: 'info' }[s] || 'info')

const showLog = (row) => {
  logRecord.value = row
  logVisible.value = true
}

onMounted(() => {
  loadPackages()
  loadDevices()
})

onBeforeUnmount(() => clearTimeout(recordsTimer))
</script>

<style scoped lang="scss">
.ms-subpage {
  height: calc(100vh - 52px); background: transparent; position: relative; padding: 20px;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", sans-serif;
}
.ms-zone { position: relative; z-index: 1; background: #fff;
  &__head { display: flex; align-items: center; gap: 14px; padding: 16px 24px 0; }
  &__kicker { font-size: 10px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .14em; color: #999; white-space: nowrap; }
  &__rule { flex: 1; height: 1px; background: #e8e8e4; }
  &__body { padding: 16px 24px 24px; }
}
.ms-btn--action { border-radius: 0 !important; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .06em; font-size: 12px; }
.ms-btn--table { border-radius: 0 !important; font-size: 12px; }
.ms-plat-tag {
  font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .08em; font-weight: 700;
  &.plat-android { color: #1a8051; } &.plat-ios { color: #666; }
}
.ms-mono { font-family: "IBM Plex Mono", Consolas, monospace; font-size: 12px; color: #666; }
.ms-text--muted { color: #ccc; font-size: 12px; }
.ms-subline { font-size: 12px; line-height: 1.5; }
.records-wrap { min-height: 200px; }
.ms-log { background: #161616; color: #d6f5d6; font-family: Consolas, monospace; font-size: 12px; padding: 14px; border-radius: 4px; max-height: 480px; overflow: auto; white-space: pre-wrap; word-break: break-all; }
</style>

<style lang="scss">
.ms-subpage {
  .el-button--primary {
    --el-button-bg-color: #191919;
    --el-button-border-color: #191919;
    --el-button-text-color: #f2f2f0;
    --el-button-hover-bg-color: #333;
    --el-button-hover-border-color: #333;
    --el-button-hover-text-color: #fff;
    border-radius: 0 !important;
    font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .06em; font-size: 12px;
  }
  .el-button--danger { border-radius: 0 !important; font-size: 12px; }
  .el-drawer__header { font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .06em; }
}
</style>
