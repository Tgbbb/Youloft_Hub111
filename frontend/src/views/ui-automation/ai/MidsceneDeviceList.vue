<template>
  <div class="ms-subpage" data-ark-theme="endfield" data-ark-depth="complex">

    <section class="ms-zone">
      <header class="ms-zone__head">
        <span class="ms-zone__kicker">DEVICES / REGISTRY</span>
        <span class="ms-zone__rule" aria-hidden="true"></span>
        <el-button type="primary" @click="showForm(null)" class="ms-btn--action"><el-icon><Plus /></el-icon> 添加设备</el-button>
      </header>
      <div class="ms-zone__body">
        <el-table :data="devices" v-loading="loading" class="ms-table" stripe>
          <el-table-column label="平台" width="70">
            <template #default="{ row }">
              <span class="ms-plat-tag" :class="'plat-' + row.platform">{{ row.platform_display }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" width="180">
            <template #default="{ row }">{{ row.name || row.device_id?.substring(0,16) || '-' }}</template>
          </el-table-column>
          <el-table-column prop="device_id" label="设备标识" width="200" show-overflow-tooltip />
          <el-table-column label="WDA地址" width="180">
            <template #default="{ row }">
              <span v-if="row.platform==='ios'" class="ms-mono">{{ row.wda_host || '未配置' }}</span>
              <span v-else class="ms-text--muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <span class="ms-status-badge" :class="'sb-' + row.status">
                <span class="ms-status-badge__dot"></span>{{ row.status }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="连通" width="80">
            <template #default="{ row }">
              <span v-if="row.platform==='ios'" class="ms-status-badge" :class="row.status==='online' ? 'sb-passed' : 'sb-failed'">
                <span class="ms-status-badge__dot"></span>{{ row.status==='online' ? '已通' : '不通' }}
              </span>
              <span v-else class="ms-text--muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="340" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showForm(row)" class="ms-btn--table">编辑</el-button>
              <el-button v-if="row.platform==='ios'" size="small" @click="testConnection(row)" :loading="testing[row.id]" class="ms-btn--table">测通</el-button>
              <template v-if="row.platform==='android' && row.ip_address">
                <el-button v-if="row.status==='offline'" size="small" type="success" @click="reconnectDevice(row)" :loading="connecting[row.id]" class="ms-btn--table">连接</el-button>
                <el-button v-else size="small" type="warning" @click="disconnectDevice(row)" :loading="disconnecting[row.id]" class="ms-btn--table">断开</el-button>
              </template>
              <el-button size="small" type="danger" @click="deleteDevice(row)" class="ms-btn--table">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <el-dialog v-model="formVisible" :title="editingId ? '编辑设备' : '添加设备'" width="500px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="设备名称"><el-input v-model="form.name" placeholder="如：iPhone 13" /></el-form-item>
        <el-form-item label="平台" required>
          <el-radio-group v-model="form.platform" :disabled="!!editingId">
            <el-radio value="android">Android</el-radio><el-radio value="ios">iOS</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="设备标识" required><el-input v-model="form.device_id" placeholder="Android: adb序列号 / iOS: UDID" :disabled="!!editingId" /></el-form-item>
        <el-form-item v-if="form.platform==='ios'" label="WDA地址"><el-input v-model="form.wda_host" placeholder="如：172.16.8.168:8100" /><div style="font-size:11px;color:#999;margin-top:4px">WebDriverAgent HTTP 地址</div></el-form-item>
        <el-form-item v-if="form.platform==='ios'" label="tidevice UDID"><el-input v-model="form.tidevice_udid" placeholder="同设备标识" /></el-form-item>
        <el-form-item v-if="form.platform==='ios'" label="iOS版本"><el-input v-model="form.ios_version" placeholder="如：17.5.1" /></el-form-item>
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

const loading = ref(false); const devices = ref([])
const formVisible = ref(false); const editingId = ref(null); const saving = ref(false)
const testing = reactive({}); const connecting = reactive({}); const disconnecting = reactive({})
const form = reactive({ name: '', platform: 'android', device_id: '', wda_host: '', tidevice_udid: '', ios_version: '' })

const loadDevices = async () => { loading.value = true; try { const { data } = await api.get('/ui-automation/midscene/devices/'); devices.value = data.results || [] } catch (e) { ElMessage.error('加载失败') } finally { loading.value = false } }
const showForm = (row) => {
  if (row) { editingId.value = row.id; form.name = row.name || ''; form.platform = row.platform; form.device_id = row.device_id; form.wda_host = row.wda_host || ''; form.tidevice_udid = row.tidevice_udid || ''; form.ios_version = row.ios_version || '' }
  else { editingId.value = null; form.name = ''; form.platform = 'android'; form.device_id = ''; form.wda_host = ''; form.tidevice_udid = ''; form.ios_version = '' }
  formVisible.value = true
}
const saveDevice = async () => { if (!form.device_id.trim()) { ElMessage.warning('请输入设备标识'); return }; saving.value = true; try { const p = { ...form }; if (editingId.value) { await api.put(`/ui-automation/midscene/devices/${editingId.value}/`, p); ElMessage.success('已更新') } else { await api.post('/ui-automation/midscene/devices/', p); ElMessage.success('已添加') }; formVisible.value = false; loadDevices() } catch (e) { const d = e.response?.data; let m = e.message; if (d && typeof d === 'object') { const ms = []; Object.entries(d).forEach(([f, errs]) => { const a = Array.isArray(errs) ? errs : [errs]; ms.push(...a.map(v => typeof v === 'string' ? `${f}: ${v}` : v)) }); if (ms.length > 0) m = ms.join('; ') }; ElMessage.error('保存失败: ' + m) } finally { saving.value = false } }
const testConnection = async (row) => { testing[row.id] = true; try { const u = row.wda_host || 'localhost:8100'; const { data } = await api.get(`/ui-automation/midscene/devices/${row.id}/test_wda/?host=${encodeURIComponent(u)}`); if (data.ok) { row.status = 'online'; ElMessage.success('WDA 连接成功') } else { row.status = 'offline'; ElMessage.warning('连接失败: ' + (data.error || '')) } } catch (e) { ElMessage.error('测试失败') } finally { testing[row.id] = false } }
const deleteDevice = async (row) => { try { await ElMessageBox.confirm(`删除「${row.name || row.device_id}」？`, '确认', { type: 'warning' }); await api.delete(`/ui-automation/midscene/devices/${row.id}/`); ElMessage.success('已删除'); loadDevices() } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') } }
const reconnectDevice = async (row) => { connecting[row.id] = true; try { const { data } = await api.post('/ui-automation/midscene/devices/connect_network/', { ip: row.ip_address, port: row.port || 5555 }); if (data.success) ElMessage.success(data.message || '已连接'); else ElMessage.error(data.message || '连接失败'); loadDevices() } catch (e) { ElMessage.error(e.response?.data?.message || '连接失败') } finally { connecting[row.id] = false } }
const disconnectDevice = async (row) => { disconnecting[row.id] = true; try { await api.post(`/ui-automation/midscene/devices/${row.id}/disconnect_network/`); ElMessage.success('已断开'); loadDevices() } catch (e) { ElMessage.error('断开失败') } finally { disconnecting[row.id] = false } }
onMounted(() => loadDevices())
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
.ms-status-badge {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .05em;
  &__dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
  &.sb-online, &.sb-available, &.sb-passed { color: #1a8051; .ms-status-badge__dot { background: #00ffa2; } }
  &.sb-offline, &.sb-failed { color: #c03939; .ms-status-badge__dot { background: #f56c6c; } }
  &.sb-locked { color: #997a00; .ms-status-badge__dot { background: #fffa00; } }
}
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
  .el-button--danger {
    border-radius: 0 !important; font-size: 12px;
  }
  .el-button--success {
    border-radius: 0 !important; font-size: 12px;
  }
  .el-button--warning {
    border-radius: 0 !important; font-size: 12px;
  }
}
</style>
