<template>
  <div class="ms-subpage" data-ark-theme="endfield" data-ark-depth="complex">

    <section class="ms-zone">
      <header class="ms-zone__head">
        <span class="ms-zone__kicker">EXECUTIONS / HISTORY</span>
        <span class="ms-zone__rule" aria-hidden="true"></span>
      </header>
      <div class="ms-zone__body">
        <!-- Filter bar -->
        <div class="ms-filter-bar">
          <el-select v-model="filterProject" placeholder="按项目" clearable class="ms-select--filter" @change="loadExecutions">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <el-select v-model="filterStatus" placeholder="按状态" clearable class="ms-select--filter">
            <el-option label="通过" value="passed" /><el-option label="失败" value="failed" /><el-option label="异常" value="error" />
          </el-select>
          <el-select v-model="filterPlatform" placeholder="按平台" clearable class="ms-select--filter">
            <el-option label="Android" value="android" /><el-option label="iOS" value="ios" />
          </el-select>
          <el-input v-model="searchKeyword" placeholder="搜索用例名称" clearable class="ms-input--filter" @keyup.enter="loadExecutions" />
          <el-button @click="loadExecutions" class="ms-btn--table">刷新</el-button>
          <el-button v-if="selectedIds.length > 0" type="danger" @click="batchDelete" :loading="batchDeleting" class="ms-btn--table">
            删除 ({{ selectedIds.length }})
          </el-button>
        </div>

        <el-table :data="records" v-loading="loading" class="ms-table" stripe @selection-change="onSelectionChange">
          <el-table-column type="selection" width="36" />
          <el-table-column prop="case_name" label="用例" min-width="180">
            <template #default="{ row }"><span class="ms-table__name">{{ row.case_name }}</span></template>
          </el-table-column>
          <el-table-column prop="device_name" label="设备" width="150" />
          <el-table-column prop="platform_display" label="平台" width="70" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <span class="ms-status-badge" :class="'sb-' + row.status">
                <span class="ms-status-badge__dot"></span>
                {{ row.status_display || row.status }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="通过率" width="120">
            <template #default="{ row }">
              <div class="ms-rate-bar">
                <div class="ms-rate-bar__track">
                  <div class="ms-rate-bar__fill" :class="row.status === 'passed' ? 'fill-pass' : row.status === 'failed' ? 'fill-fail' : ''"
                    :style="{ width: (row.total_steps > 0 ? Math.round((row.passed_steps / row.total_steps) * 100) : 0) + '%' }"></div>
                </div>
                <span class="ms-rate-bar__pct">{{ row.total_steps > 0 ? Math.round((row.passed_steps / row.total_steps) * 100) : 0 }}%</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="步骤" width="90">
            <template #default="{ row }">
              <span class="ms-step-summary">
                <span class="ss-pass">{{ row.passed_steps }}</span>/<span class="ss-fail">{{ row.failed_steps }}</span>/{{ row.total_steps }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="80">
            <template #default="{ row }">{{ formatDuration(row.duration) }}</template>
          </el-table-column>
          <el-table-column prop="executed_by_name" label="执行人" width="100" />
          <el-table-column label="开始时间" width="160">
            <template #default="{ row }">{{ row.started_at ? new Date(row.started_at).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="viewReport(row)" :disabled="!row.report_path" class="ms-btn--table">报告</el-button>
              <el-button size="small" @click="viewDetail(row)" class="ms-btn--table">详情</el-button>
              <el-button size="small" type="danger" @click="deleteRecord(row)" class="ms-btn--table">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="ms-pagination" v-if="total > 0">
          <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total"
            layout="total, prev, pager, next" @current-change="loadExecutions" />
        </div>
      </div>
    </section>

    <!-- Detail dialog -->
    <el-dialog v-model="showDetail" title="执行详情" width="700px">
      <template v-if="detailRecord">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="用例">{{ detailRecord.case_name }}</el-descriptions-item>
          <el-descriptions-item label="设备">{{ detailRecord.device_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态"><el-tag :type="statusTagType(detailRecord.status)">{{ detailRecord.status_display }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatDuration(detailRecord.duration) }}</el-descriptions-item>
          <el-descriptions-item label="通过/失败/总计">{{ detailRecord.passed_steps }}/{{ detailRecord.failed_steps }}/{{ detailRecord.total_steps }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ detailRecord.started_at ? new Date(detailRecord.started_at).toLocaleString() : '-' }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="detailRecord.error_message" style="margin-top:16px"><el-alert :title="'错误信息'" :description="detailRecord.error_message" type="error" :closable="false" /></div>
        <div class="ms-detail-steps" v-if="detailRecord.steps_detail?.length">
          <h4>步骤详情</h4>
          <div v-for="step in detailRecord.steps_detail" :key="step.step" class="ms-detail-step">
            <div class="ms-detail-step__head">
              <span class="ms-step-badge--sm" :class="'sb-' + step.status">{{ step.status === 'passed' ? '✓' : '✗' }} {{ step.step }}</span>
              <span>{{ step.instruction }}</span>
            </div>
            <img v-if="step.screenshot" :src="step.screenshot" class="ms-detail-step__thumb" @click="previewImg = step.screenshot; showImgPreview = true" />
            <div v-if="step.error" class="ms-detail-step__err">{{ step.error }}</div>
          </div>
        </div>
      </template>
    </el-dialog>
    <el-dialog v-model="showImgPreview" title="截图" width="400px"><img :src="previewImg" style="width:100%" v-if="previewImg" /></el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

const loading = ref(false); const records = ref([])
const filterProject = ref(''); const filterStatus = ref(''); const filterPlatform = ref(''); const searchKeyword = ref('')
const projects = ref([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
const showDetail = ref(false); const detailRecord = ref(null)
const showImgPreview = ref(false); const previewImg = ref('')
const selectedIds = ref([]); const batchDeleting = ref(false)

const loadExecutions = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filterProject.value) params.project = filterProject.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterPlatform.value) params.platform = filterPlatform.value
    if (searchKeyword.value) params.search = searchKeyword.value
    const { data } = await api.get('/ui-automation/midscene/executions/', { params })
    records.value = data.results || []; total.value = data.count || 0
  } catch (e) { console.error(e) } finally { loading.value = false }
}
const statusTagType = (s) => ({ pending:'info', running:'warning', passed:'success', failed:'danger', error:'danger', stopped:'info' }[s] || 'info')
const formatDuration = (s) => { if (!s) return '-'; if (s < 60) return `${Math.round(s)}s`; const m = Math.floor(s/60); return `${m}m${Math.round(s%60)}s` }
const viewReport = (r) => { if (r.report_path) window.open(r.report_path, '_blank') }
const viewDetail = (r) => { detailRecord.value = r; showDetail.value = true }
const onSelectionChange = (rows) => { selectedIds.value = rows.map(r => r.id) }
const batchDelete = async () => { try { await ElMessageBox.confirm(`删除选中的 ${selectedIds.value.length} 条记录？`, '确认', { type: 'warning' }); batchDeleting.value = true; await api.post('/ui-automation/midscene/executions/batch_delete/', { ids: selectedIds.value }); ElMessage.success('已删除'); selectedIds.value = []; loadExecutions() } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') } finally { batchDeleting.value = false } }
const deleteRecord = async (r) => { try { await ElMessageBox.confirm(`删除「${r.case_name}」？`, '确认', { type: 'warning' }); await api.delete(`/ui-automation/midscene/executions/${r.id}/`); ElMessage.success('已删除'); loadExecutions() } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') } }
const loadProjects = async () => { try { const { data } = await api.get('/ui-automation/midscene/projects/'); projects.value = data.results || [] } catch (e) {} }
onMounted(() => { loadProjects(); loadExecutions() })
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
.ms-filter-bar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.ms-select--filter :deep(.el-input__wrapper) { border-radius: 0 !important; box-shadow: none !important; border: 1px solid #d4d4ce; width: 130px; }
.ms-input--filter { width: 200px; :deep(.el-input__wrapper) { border-radius: 0 !important; box-shadow: none !important; border: 1px solid #d4d4ce; } }
.ms-btn--table { border-radius: 0 !important; font-size: 12px; }
.ms-table {
  &__name { font-weight: 600; font-size: 14px; }
}
.ms-status-badge {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .05em;
  &__dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
  &.sb-passed { color: #1a8051; .ms-status-badge__dot { background: #00ffa2; } }
  &.sb-failed, &.sb-error { color: #c03939; .ms-status-badge__dot { background: #f56c6c; } }
  &.sb-running { color: #997a00; .ms-status-badge__dot { background: #fffa00; animation: ms-pulse 1.2s infinite; } }
  &.sb-pending { color: #999; .ms-status-badge__dot { background: #ccc; } }
  &.sb-stopped { color: #999; .ms-status-badge__dot { background: #999; } }
}
@keyframes ms-pulse { 0%,100%{opacity:1} 50%{opacity:.25} }
.ms-rate-bar {
  display: flex; align-items: center; gap: 8px;
  &__track { flex: 1; height: 4px; background: #e8e8e4; }
  &__fill { height: 100%; background: #fffa00; transition: width .3s; &.fill-pass { background: #00ffa2; } &.fill-fail { background: #f56c6c; } }
  &__pct { font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif; font-weight: 700; color: #666; min-width: 32px; }
}
.ms-step-summary { font-family: "Space Grotesk", system-ui, sans-serif; font-size: 13px; color: #666;
  .ss-pass { color: #1a8051; font-weight: 700; }
  .ss-fail { color: #c03939; font-weight: 700; }
}
.ms-pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.ms-detail-steps { margin-top: 16px; h4 { margin-bottom: 10px; } }
.ms-detail-step { padding: 8px 0; border-bottom: 1px solid #ebeef5;
  &:last-child { border-bottom: none; }
  &__head { display: flex; align-items: center; gap: 8px; font-size: 14px; }
  &__thumb { margin-top: 6px; max-height: 80px; cursor: pointer; border: 1px solid #dcdfe6; }
  &__err { margin-top: 4px; color: #f56c6c; font-size: 12px; }
}
.ms-step-badge--sm {
  font-size: 11px; padding: 1px 8px; font-family: "Space Grotesk", system-ui, sans-serif; flex-shrink: 0;
  &.sb-passed { background: rgba(0,255,162,.15); color: #1a8051; }
  &.sb-failed { background: rgba(245,108,108,.1); color: #c03939; }
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
}
</style>
