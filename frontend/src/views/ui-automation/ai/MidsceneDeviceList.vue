<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">Midscene 设备管理</h1>
      <el-button type="primary" @click="showForm(null)"><el-icon><Plus /></el-icon> 添加设备</el-button>
    </div>

    <div class="card-container">
      <el-table :data="devices" v-loading="loading" stripe>
        <el-table-column label="平台" width="80">
          <template #default="{ row }">
            <el-tag :type="row.platform==='android'?'success':''" size="small">{{ row.platform_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="180">
          <template #default="{ row }">
            {{ row.name || row.device_id?.substring(0,16) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="device_id" label="设备标识" width="200" show-overflow-tooltip />
        <el-table-column prop="wda_host" label="WDA地址" width="180">
          <template #default="{ row }">
            <span v-if="row.platform==='ios'">{{ row.wda_host || '未配置' }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="连通" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.platform==='ios'" :type="row.status==='online' ? 'success' : 'danger'" size="small">
              {{ row.status==='online' ? '已通' : '不通' }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="showForm(row)">编辑</el-button>
            <el-button v-if="row.platform==='ios'" size="small" @click="testConnection(row)" :loading="testing[row.id]">测通</el-button>
            <template v-if="row.platform==='android' && row.ip_address">
              <el-button v-if="row.status==='offline'" size="small" type="success" @click="reconnectDevice(row)" :loading="connecting[row.id]">连接</el-button>
              <el-button v-else size="small" type="warning" @click="disconnectDevice(row)" :loading="disconnecting[row.id]">断开</el-button>
            </template>
            <el-button size="small" type="danger" @click="deleteDevice(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="formVisible" :title="editingId ? '编辑设备' : '添加设备'" width="500px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="设备名称">
          <el-input v-model="form.name" placeholder="如：iPhone 13" />
        </el-form-item>
        <el-form-item label="平台" required>
          <el-radio-group v-model="form.platform" :disabled="!!editingId">
            <el-radio value="android">Android</el-radio>
            <el-radio value="ios">iOS</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="设备标识" required>
          <el-input v-model="form.device_id" placeholder="Android: adb序列号 / iOS: UDID" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item v-if="form.platform==='ios'" label="WDA地址">
          <el-input v-model="form.wda_host" placeholder="如：172.16.8.168:8100 或 localhost:8100" />
          <div style="font-size:11px;color:#909399;margin-top:4px">
            WebDriverAgent 的 HTTP 地址，Mac上运行 iproxy 后填 Mac的IP:8100
          </div>
        </el-form-item>
        <el-form-item v-if="form.platform==='ios'" label="tidevice UDID">
          <el-input v-model="form.tidevice_udid" placeholder="同设备标识" />
        </el-form-item>
        <el-form-item v-if="form.platform==='ios'" label="iOS版本">
          <el-input v-model="form.ios_version" placeholder="如：17.5.1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDevice" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '@/utils/api'

const loading = ref(false)
const devices = ref([])
const formVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)
const testing = reactive({})
const connecting = reactive({})
const disconnecting = reactive({})

const form = reactive({
  name: '',
  platform: 'android',
  device_id: '',
  wda_host: '',
  tidevice_udid: '',
  ios_version: '',
})

const statusType = (s) => ({ online:'success', available:'success', locked:'warning', offline:'danger' }[s] || 'info')

const loadDevices = async () => {
  loading.value = true
  try {
    const { data } = await api.get('/ui-automation/midscene/devices/')
    devices.value = data.results || []
  } catch (e) {
    ElMessage.error('加载失败')
  } finally { loading.value = false }
}

const showForm = (row) => {
  if (row) {
    editingId.value = row.id
    form.name = row.name || ''
    form.platform = row.platform
    form.device_id = row.device_id
    form.wda_host = row.wda_host || ''
    form.tidevice_udid = row.tidevice_udid || ''
    form.ios_version = row.ios_version || ''
  } else {
    editingId.value = null
    form.name = ''; form.platform = 'android'; form.device_id = ''
    form.wda_host = ''; form.tidevice_udid = ''; form.ios_version = ''
  }
  formVisible.value = true
}

const saveDevice = async () => {
  if (!form.device_id.trim()) { ElMessage.warning('请输入设备标识'); return }
  saving.value = true
  try {
    const payload = { ...form }
    if (editingId.value) {
      await api.put(`/ui-automation/midscene/devices/${editingId.value}/`, payload)
      ElMessage.success('已更新')
    } else {
      await api.post('/ui-automation/midscene/devices/', payload)
      ElMessage.success('已添加')
    }
    formVisible.value = false
    loadDevices()
  } catch (e) {
    // 解析 DRF 校验错误（字段级错误对象）
    const data = e.response?.data
    let errMsg = e.message
    if (data && typeof data === 'object') {
      const msgs = []
      Object.entries(data).forEach(([field, errors]) => {
        const vals = Array.isArray(errors) ? errors : [errors]
        msgs.push(...vals.map(v => typeof v === 'string' ? `${field}: ${v}` : v))
      })
      if (msgs.length > 0) errMsg = msgs.join('; ')
    }
    ElMessage.error('保存失败: ' + errMsg)
  } finally { saving.value = false }
}

const testConnection = async (row) => {
  testing[row.id] = true
  try {
    const url = row.wda_host || 'localhost:8100'
    const { data } = await api.get(`/ui-automation/midscene/devices/${row.id}/test_wda/?host=${encodeURIComponent(url)}`)
    connectionStatus[row.id] = data.ok
    if (data.ok) {
      row.status = 'online'
      ElMessage.success('WDA 连接成功')
    } else {
      row.status = 'offline'
      ElMessage.warning('WDA 连接失败: ' + (data.error || ''))
    }
  } catch (e) {
    connectionStatus[row.id] = false
    ElMessage.error('测试失败')
  } finally { testing[row.id] = false }
}

const deleteDevice = async (row) => {
  try {
    await ElMessageBox.confirm(`删除设备「${row.name || row.device_id}」？`, '确认', { type: 'warning' })
    await api.delete(`/ui-automation/midscene/devices/${row.id}/`)
    ElMessage.success('已删除')
    loadDevices()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const reconnectDevice = async (row) => {
  connecting[row.id] = true
  try {
    const { data } = await api.post('/ui-automation/midscene/devices/connect_network/', {
      ip: row.ip_address,
      port: row.port || 5555,
    })
    if (data.success) {
      ElMessage.success(data.message || '已连接')
    } else {
      ElMessage.error(data.message || '连接失败')
    }
    loadDevices()
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '连接失败')
  } finally {
    connecting[row.id] = false
  }
}

const disconnectDevice = async (row) => {
  disconnecting[row.id] = true
  try {
    await api.post(`/ui-automation/midscene/devices/${row.id}/disconnect_network/`)
    ElMessage.success('已断开')
    loadDevices()
  } catch (e) {
    ElMessage.error('断开失败')
  } finally {
    disconnecting[row.id] = false
  }
}

onMounted(() => loadDevices())
</script>
