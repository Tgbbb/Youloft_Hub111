<template>
  <div class="page-container midscene-executions">
    <div class="page-header">
      <h1 class="page-title">Midscene 执行历史</h1>
    </div>

    <div class="card-container">
      <!-- 筛选 -->
      <div class="filter-bar">
        <el-select v-model="filterProject" placeholder="按项目筛选" clearable style="width: 160px" @change="loadExecutions">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="按状态筛选" clearable style="width: 140px">
          <el-option label="通过" value="passed" />
          <el-option label="失败" value="failed" />
          <el-option label="异常" value="error" />
        </el-select>
        <el-select v-model="filterPlatform" placeholder="按平台筛选" clearable style="width: 130px">
          <el-option label="Android" value="android" />
          <el-option label="iOS" value="ios" />
        </el-select>
        <el-input
          v-model="searchKeyword"
          placeholder="搜索用例名称"
          clearable
          style="width: 240px"
          @keyup.enter="loadExecutions"
        />
        <el-button @click="loadExecutions">刷新</el-button>
        <el-button v-if="selectedIds.length > 0" type="danger" @click="batchDelete" :loading="batchDeleting">
          批量删除 ({{ selectedIds.length }})
        </el-button>
      </div>

      <el-table :data="records" v-loading="loading" stripe @selection-change="onSelectionChange">
        <el-table-column type="selection" width="40" />
        <el-table-column prop="case_name" label="用例名称" min-width="180" />
        <el-table-column prop="device_name" label="设备" width="150" />
        <el-table-column prop="platform_display" label="平台" width="80" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tooltip v-if="row.status === 'failed' && row.error_message" :content="row.error_message" placement="top">
              <el-tag :type="statusTagType(row.status)">{{ row.status_display || row.status }}</el-tag>
            </el-tooltip>
            <el-tag v-else :type="statusTagType(row.status)">{{ row.status_display || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="通过率" width="100">
          <template #default="{ row }">
            <el-progress
              :percentage="row.total_steps > 0 ? Math.round((row.passed_steps / row.total_steps) * 100) : 0"
              :status="row.status === 'passed' ? 'success' : row.status === 'failed' ? 'exception' : ''"
              :stroke-width="14"
            />
          </template>
        </el-table-column>
        <el-table-column label="步骤" width="100">
          <template #default="{ row }">
            {{ row.passed_steps }}/{{ row.failed_steps }}/{{ row.total_steps }}
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="100">
          <template #default="{ row }">
            {{ formatDuration(row.duration) }}
          </template>
        </el-table-column>
        <el-table-column prop="executed_by_name" label="执行人" width="100" />
        <el-table-column label="开始时间" width="160">
          <template #default="{ row }">
            {{ row.started_at ? new Date(row.started_at).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewReport(row)" :disabled="!row.report_path">
              查看报告
            </el-button>
            <el-button size="small" @click="viewDetail(row)">详情</el-button>
            <el-button size="small" type="danger" @click="deleteRecord(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper" v-if="total > 0">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadExecutions"
        />
      </div>
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="showDetail" title="执行详情" width="700px">
      <template v-if="detailRecord">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="用例">{{ detailRecord.case_name }}</el-descriptions-item>
          <el-descriptions-item label="设备">{{ detailRecord.device_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(detailRecord.status)">{{ detailRecord.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatDuration(detailRecord.duration) }}</el-descriptions-item>
          <el-descriptions-item label="通过/失败/总计">
            {{ detailRecord.passed_steps }}/{{ detailRecord.failed_steps }}/{{ detailRecord.total_steps }}
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">
            {{ detailRecord.started_at ? new Date(detailRecord.started_at).toLocaleString() : '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="detailRecord.error_message" style="margin-top: 16px">
          <el-alert :title="'错误信息'" :description="detailRecord.error_message" type="error" :closable="false" />
        </div>

        <!-- 步骤详情 -->
        <div class="detail-steps" style="margin-top: 16px" v-if="detailRecord.steps_detail && detailRecord.steps_detail.length > 0">
          <h4>步骤详情</h4>
          <div v-for="step in detailRecord.steps_detail" :key="step.step" class="detail-step">
            <div class="detail-step-header">
              <el-tag :type="step.status === 'passed' ? 'success' : 'danger'" size="small">
                {{ step.status === 'passed' ? '✓' : '✗' }} 步骤 {{ step.step }}
              </el-tag>
              <span>{{ step.instruction }}</span>
            </div>
            <div class="detail-step-screenshot" v-if="step.screenshot" @click="previewImg = step.screenshot; showImgPreview = true">
              <img :src="step.screenshot" alt="截图" class="thumb" />
            </div>
            <div class="detail-step-error" v-if="step.error">
              {{ step.error }}
            </div>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 截图大图 -->
    <el-dialog v-model="showImgPreview" title="截图" width="400px">
      <img :src="previewImg" style="width: 100%;" v-if="previewImg" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

const router = useRouter()
const loading = ref(false)
const records = ref([])
const filterProject = ref('')
const filterStatus = ref('')
const filterPlatform = ref('')
const searchKeyword = ref('')
const projects = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const showDetail = ref(false)
const detailRecord = ref(null)
const showImgPreview = ref(false)
const previewImg = ref('')
const selectedIds = ref([])
const batchDeleting = ref(false)

const loadExecutions = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filterProject.value) params.project = filterProject.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterPlatform.value) params.platform = filterPlatform.value
    if (searchKeyword.value) params.search = searchKeyword.value

    const { data } = await api.get('/ui-automation/midscene/executions/', { params })
    records.value = data.results || []
    total.value = data.count || 0
  } catch (e) {
    console.error('加载执行记录失败:', e)
  } finally {
    loading.value = false
  }
}

const statusTagType = (status) => {
  const map = { pending: 'info', running: 'warning', passed: 'success', failed: 'danger', error: 'danger', stopped: 'info' }
  return map[status] || 'info'
}

const formatDuration = (seconds) => {
  if (!seconds) return '-'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m${s}s`
}

const viewReport = (row) => {
  if (row.report_path) {
    window.open(row.report_path, '_blank')
  }
}

const viewDetail = (row) => {
  detailRecord.value = row
  showDetail.value = true
}

const onSelectionChange = (rows) => {
  selectedIds.value = rows.map(r => r.id)
}

const batchDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedIds.value.length} 条执行记录吗？相关截图也将被删除。`,
      '批量删除确认', { type: 'warning' }
    )
    batchDeleting.value = true
    await api.post('/ui-automation/midscene/executions/batch_delete/', { ids: selectedIds.value })
    ElMessage.success('批量删除成功')
    selectedIds.value = []
    loadExecutions()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  } finally {
    batchDeleting.value = false
  }
}

const deleteRecord = async (row) => {
  try {
    await ElMessageBox.confirm(`删除执行记录「${row.case_name}」？相关截图也将被删除。`, '确认删除', { type: 'warning' })
    await api.delete(`/ui-automation/midscene/executions/${row.id}/`)
    ElMessage.success('已删除')
    loadExecutions()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const loadProjects = async () => {
  try {
    const { data } = await api.get('/ui-automation/midscene/projects/')
    projects.value = data.results || []
  } catch (e) { /* ignore */ }
}

onMounted(() => {
  loadProjects()
  loadExecutions()
})
</script>

<style scoped lang="scss">
.midscene-executions {
  .filter-bar {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
  }
  .pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
  .detail-steps {
    h4 { margin-bottom: 8px; }
    .detail-step {
      padding: 8px 0;
      border-bottom: 1px solid #ebeef5;
      &:last-child { border-bottom: none; }
      .detail-step-header {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
      }
      .detail-step-screenshot {
        margin-top: 6px;
        cursor: pointer;
        .thumb {
          max-height: 80px;
          border-radius: 4px;
          border: 1px solid #dcdfe6;
        }
      }
      .detail-step-error {
        margin-top: 4px;
        color: #f56c6c;
        font-size: 12px;
      }
    }
  }
}
</style>
