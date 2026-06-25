<template>
  <div class="page-container">
    <!-- 顶栏 -->
    <div class="top-bar">
      <div class="top-left">
        <h1 class="page-title">{{ $t('testcase.title') }}</h1>
        <span v-if="total > 0 && hasAnyFilter()" class="result-count">{{ total }} 条结果</span>
      </div>
      <div class="top-actions">
        <button class="act-btn" v-if="selectedTestCases.length > 0" @click="batchDeleteTestCases" :disabled="isDeleting">
          🗑 {{ $t('testcase.batchDelete') }} ({{ selectedTestCases.length }})
        </button>
        <button class="act-btn" @click="exportToExcel">📥 {{ $t('testcase.exportExcel') }}</button>
        <button class="act-btn" @click="downloadImportTemplate">📋 模板</button>
        <button class="act-btn" @click="openImportDialog">📤 {{ $t('testcase.importCases') }}</button>
        <button class="act-btn" @click="goToImportRecords">📂 记录</button>
        <button class="act-btn primary" @click="$router.push('/ai-generation/testcases/create')">＋ {{ $t('testcase.newCase') }}</button>
      </div>
    </div>

    <!-- 筛选命令区 -->
    <div class="filter-command">
      <div class="filter-row">
        <div class="filter-group">
          <label class="filter-label">项目</label>
          <el-select v-model="projectFilter" :placeholder="$t('testcase.relatedProject')" clearable @change="handleProjectFilterChange" class="filter-select">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </div>
        <span class="cascade-arrow">→</span>
        <div class="filter-group">
          <label class="filter-label">版本</label>
          <el-select v-model="versionFilter" :placeholder="$t('testcase.versionFilter')" clearable filterable @change="handleVersionFilterChange" :disabled="!projectFilter" class="filter-select">
            <el-option v-for="v in versions" :key="v.id" :label="v.name + (v.is_baseline ? ' 基线' : '')" :value="v.id" />
          </el-select>
        </div>
        <span class="cascade-arrow">→</span>
        <div class="filter-group">
          <label class="filter-label">模块</label>
          <el-select v-model="moduleFilter" :placeholder="$t('testcase.moduleFilter')" clearable filterable @change="handleFilter" :disabled="!versionFilter" class="filter-select">
            <el-option v-for="m in filterModules" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </div>
        <div class="filter-divider"></div>
        <div class="filter-group">
          <label class="filter-label">优先级</label>
          <el-select v-model="priorityFilter" :placeholder="$t('testcase.priorityFilter')" clearable @change="handleFilter" class="filter-select short">
            <el-option :label="$t('testcase.low')" value="low" />
            <el-option :label="$t('testcase.medium')" value="medium" />
            <el-option :label="$t('testcase.high')" value="high" />
            <el-option :label="$t('testcase.critical')" value="critical" />
          </el-select>
        </div>
        <div class="filter-group search-group">
          <label class="filter-label">搜索</label>
          <el-input v-model="searchText" :placeholder="$t('testcase.searchPlaceholder')" clearable @input="handleSearch" class="filter-search">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
      </div>

      <!-- 活跃筛选标签 -->
      <div v-if="activeFilters.length > 0" class="active-filters">
        <span class="af-label">当前筛选：</span>
        <span v-for="f in activeFilters" :key="f.key" class="af-chip" @click="removeFilter(f.key)">
          {{ f.label }} ✕
        </span>
        <span class="af-clear" @click="clearAllFilters">清除全部</span>
      </div>
    </div>

    <!-- 表格区 -->
    <div class="table-card">
      <div v-if="!hasAnyFilter() && !loading" class="empty-filter-hint">
        <div class="empty-icon">🔍</div>
        <div class="empty-title">筛选条件后查看用例</div>
        <div class="empty-desc">选择 <strong>项目</strong> → <strong>版本</strong> → <strong>模块</strong> 快速定位目标用例</div>
      </div>

      <el-table v-else :data="testcases" v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange" stripe>
        <el-table-column type="selection" width="48" />
        <el-table-column type="index" :label="'#'" width="60" :index="getSerialNumber" />
        <el-table-column prop="title" :label="$t('testcase.caseTitle')" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="case-link" @click="goToTestCase(row.id)">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" :label="$t('testcase.priority')" width="90" align="center">
          <template #default="{ row }">
            <span class="pri-dot" :class="row.priority">{{ getPriorityText(row.priority) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="function_module" :label="$t('testcase.moduleName')" width="130">
          <template #default="{ row }">
            <span v-if="row.function_module" class="mod-tag">{{ row.function_module.name }}</span>
            <span v-else class="cell-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('testcase.execution')" width="130" align="center">
          <template #default="{ row }">
            <span v-if="row.execution_status === 'passed'" class="exec-badge pass">✓ 通过</span>
            <span v-else-if="row.execution_status === 'failed'" class="exec-badge fail">✕ 不通过</span>
            <span v-else class="cell-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="author.username" :label="$t('testcase.author')" width="100" />
        <el-table-column prop="created_at" :label="$t('testcase.createdAt')" width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="$t('project.actions')" width="200" fixed="right">
          <template #default="{ row }">
            <button class="row-btn pass" @click="executeCase(row, 'passed')" :disabled="row._executing">✓</button>
            <button class="row-btn fail" @click="executeCase(row, 'failed')" :disabled="row._executing">✕</button>
            <button class="row-btn" @click="editTestCase(row)">编辑</button>
            <button class="row-btn danger" @click="deleteTestCase(row)">删除</button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div class="pager-bar" v-if="hasAnyFilter()">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[15, 25, 35, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <!-- 导入弹窗（不变） -->
    <el-dialog v-model="importDialogVisible" :title="$t('testcase.importDialogTitle')" width="560px">
      <el-alert :title="$t('testcase.uploadTip')" type="info" :closable="false" show-icon class="import-alert" />
      <el-form label-width="100px">
        <el-form-item :label="$t('testcase.importProject')">
          <el-select v-model="importForm.projectId" style="width: 100%" :placeholder="$t('testcase.selectImportProject')" filterable>
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('testcase.selectImportFile')">
          <el-upload class="import-upload" drag action="#" :auto-upload="false" :limit="1" accept=".xlsx" :show-file-list="false" :on-change="handleImportFileChange">
            <el-icon class="el-icon--upload"><Upload /></el-icon>
            <div class="el-upload__text">{{ $t('testcase.chooseFile') }}</div>
            <template #tip><div class="el-upload__tip">{{ $t('testcase.selectedFile') }}: {{ selectedImportFile?.name || '-' }}</div></template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button @click="downloadImportTemplate">{{ $t('testcase.downloadImportTemplate') }}</el-button>
        <el-button type="primary" :loading="isCreatingImport" @click="submitImport">{{ isCreatingImport ? $t('testcase.uploading') : $t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Upload } from '@element-plus/icons-vue'
import api from '@/utils/api'
import dayjs from 'dayjs'
import * as XLSX from 'xlsx'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const loading = ref(false)
const testcases = ref([])
const projects = ref([])
const currentPage = ref(1)
const pageSize = ref(15)
const total = ref(0)
const searchText = ref('')
const projectFilter = ref('')
const priorityFilter = ref('')
const versionFilter = ref('')
const moduleFilter = ref('')
const filterModules = ref([])
const versions = ref([])
const selectedTestCases = ref([])
const isDeleting = ref(false)
const importDialogVisible = ref(false)
const isCreatingImport = ref(false)
const selectedImportFile = ref(null)
const importForm = ref({ projectId: '' })

// 活跃筛选标签
const activeFilters = computed(() => {
  const f = []
  if (projectFilter.value) {
    const p = projects.value.find(x => x.id === Number(projectFilter.value))
    f.push({ key: 'project', label: '项目: ' + (p?.name || projectFilter.value) })
  }
  if (versionFilter.value) {
    const v = versions.value.find(x => x.id === Number(versionFilter.value))
    f.push({ key: 'version', label: '版本: ' + (v?.name || versionFilter.value) })
  }
  if (moduleFilter.value) {
    const m = filterModules.value.find(x => x.id === Number(moduleFilter.value))
    f.push({ key: 'module', label: '模块: ' + (m?.name || moduleFilter.value) })
  }
  if (priorityFilter.value) {
    f.push({ key: 'priority', label: '优先级: ' + getPriorityText(priorityFilter.value) })
  }
  if (searchText.value) {
    f.push({ key: 'search', label: '搜索: ' + searchText.value })
  }
  return f
})

const removeFilter = (key) => {
  switch (key) {
    case 'project': projectFilter.value = ''; handleProjectFilterChange(); break
    case 'version': versionFilter.value = ''; handleVersionFilterChange(); break
    case 'module': moduleFilter.value = ''; handleFilter(); break
    case 'priority': priorityFilter.value = ''; handleFilter(); break
    case 'search': searchText.value = ''; handleSearch(); break
  }
}

const clearAllFilters = () => {
  projectFilter.value = ''
  versionFilter.value = ''
  moduleFilter.value = ''
  priorityFilter.value = ''
  searchText.value = ''
  filterModules.value = []
  currentPage.value = 1
}

// ===== API =====
const fetchTestCases = async () => {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (searchText.value) params.search = searchText.value
    if (projectFilter.value) params.project = projectFilter.value
    if (priorityFilter.value) params.priority = priorityFilter.value
    if (versionFilter.value) params.versions = versionFilter.value
    if (moduleFilter.value) params.function_module = moduleFilter.value
    const response = await api.get('/testcases/', { params })
    testcases.value = response.data.results || []
    total.value = response.data.count || 0
  } catch (error) {
    ElMessage.error(t('testcase.fetchListFailed'))
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { currentPage.value = 1; fetchTestCases() }
const handleFilter = () => { currentPage.value = 1; fetchTestCases() }

const fetchVersions = async () => {
  try {
    const params = {}
    if (projectFilter.value) params.projects = projectFilter.value
    const response = await api.get('/versions/', { params })
    versions.value = response.data.results || response.data || []
  } catch (error) { console.error('Fetch versions failed:', error); versions.value = [] }
}

const handleProjectFilterChange = () => {
  versionFilter.value = ''; moduleFilter.value = ''; filterModules.value = []
  fetchVersions(); handleFilter()
}

const handleVersionFilterChange = () => {
  moduleFilter.value = ''
  if (versionFilter.value) fetchModulesForFilter()
  else filterModules.value = []
  handleFilter()
}

const fetchModulesForFilter = async () => {
  try {
    const response = await api.get(`/versions/${versionFilter.value}/modules/`)
    filterModules.value = response.data.results || response.data || []
  } catch (error) { console.error('Fetch modules failed:', error); filterModules.value = [] }
}

const handlePageChange = () => fetchTestCases()
const handleSizeChange = () => { currentPage.value = 1; fetchTestCases() }

const goToTestCase = (id) => {
  const query = {}
  if (projectFilter.value) query.project = projectFilter.value
  if (versionFilter.value) query.versions = versionFilter.value
  if (moduleFilter.value) query.function_module = moduleFilter.value
  if (priorityFilter.value) query.priority = priorityFilter.value
  if (searchText.value) query.search = searchText.value
  router.push({ path: `/ai-generation/testcases/${id}`, query })
}

const editTestCase = (tc) => router.push(`/ai-generation/testcases/${tc.id}/edit`)

const executeCase = async (tc, status) => {
  try {
    tc._executing = true
    await api.patch(`/testcases/${tc.id}/execute/`, { execution_status: status })
    tc.execution_status = status
    ElMessage.success(status === 'passed' ? '已标记通过' : '已标记不通过')
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    tc._executing = false
  }
}

const deleteTestCase = async (tc) => {
  try {
    await ElMessageBox.confirm(t('testcase.deleteConfirm'), t('common.warning'), { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: 'warning' })
    await api.delete(`/testcases/${tc.id}/`)
    ElMessage.success(t('testcase.deleteSuccess'))
    fetchTestCases()
  } catch (error) { if (error !== 'cancel') ElMessage.error(t('testcase.deleteFailed')) }
}

const handleSelectionChange = (s) => { selectedTestCases.value = s }
const getSerialNumber = (i) => (currentPage.value - 1) * pageSize.value + i + 1

const batchDeleteTestCases = async () => {
  if (selectedTestCases.value.length === 0) { ElMessage.warning(t('testcase.selectFirst')); return }
  try {
    await ElMessageBox.confirm(t('testcase.batchDeleteConfirm', { count: selectedTestCases.value.length }), t('common.warning'), { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: 'warning' })
    isDeleting.value = true
    let ok = 0, fail = 0
    for (const tc of selectedTestCases.value) {
      try { await api.delete(`/testcases/${tc.id}/`); ok++ } catch (e) { fail++ }
    }
    if (ok > 0) ElMessage.success(t('testcase.batchDeleteSuccess', { successCount: ok }) + (fail ? `，${fail} 失败` : ''))
    else ElMessage.error(t('testcase.batchDeleteFailed'))
    selectedTestCases.value = []; fetchTestCases()
  } catch (error) { if (error !== 'cancel') ElMessage.error(t('testcase.batchDeleteError')) }
  finally { isDeleting.value = false }
}

const getPriorityText = (p) => ({ low: t('testcase.low'), medium: t('testcase.medium'), high: t('testcase.high'), critical: t('testcase.critical') }[p] || p)
const getTypeText = (type) => ({ functional: t('testcase.functional'), integration: t('testcase.integration'), api: t('testcase.api'), ui: t('testcase.ui'), performance: t('testcase.performance'), security: t('testcase.security') }[type] || '-')
const formatDate = (d) => dayjs(d).format('YYYY-MM-DD HH:mm')
const convertBrToNewline = (t) => t ? t.replace(/<br\s*\/?>/gi, '\n') : ''

const exportToExcel = async () => {
  try {
    loading.value = true
    let data = []
    if (selectedTestCases.value.length > 0) {
      data = selectedTestCases.value
    } else {
      let page = 1
      while (true) {
        const params = { page, page_size: 100 }
        if (searchText.value) params.search = searchText.value
        if (projectFilter.value) params.project = projectFilter.value
        if (priorityFilter.value) params.priority = priorityFilter.value
        if (versionFilter.value) params.versions = versionFilter.value
        const res = await api.get('/testcases/', { params })
        const results = res.data.results || []
        data.push(...results)
        if (results.length < 100) break
        page++
      }
    }
    if (data.length === 0) { ElMessage.warning(t('testcase.noDataToExport')); loading.value = false; return }

    const wb = XLSX.utils.book_new()
    const rows = [[t('testcase.excelNumber'), t('testcase.excelTitle'), t('testcase.excelProject'), t('testcase.excelVersions'), t('testcase.excelPreconditions'), t('testcase.excelSteps'), t('testcase.excelExpectedResult'), t('testcase.excelPriority'), t('testcase.excelTestType'), t('testcase.excelAuthor'), t('testcase.excelCreatedAt')]]
    data.forEach((tc, i) => {
      const vers = tc.versions?.length ? tc.versions.map(v => v.name + (v.is_baseline ? '(基线)' : '')).join('、') : t('testcase.noVersion')
      rows.push([`TC${String(i+1).padStart(3,'0')}`, tc.title||'', tc.project?.name||'', vers, convertBrToNewline(tc.preconditions||''), convertBrToNewline(tc.steps||''), convertBrToNewline(tc.expected_result||''), getPriorityText(tc.priority), getTypeText(tc.test_type), tc.author?.username||'', formatDate(tc.created_at)])
    })
    const ws = XLSX.utils.aoa_to_sheet(rows)
    XLSX.utils.book_append_sheet(wb, ws, t('testcase.excelSheetName'))
    XLSX.writeFile(wb, t('testcase.excelFileName', { date: new Date().toISOString().slice(0,10) }))
    ElMessage.success(t('testcase.exportSuccess'))
  } catch (error) { ElMessage.error(t('testcase.exportFailed')) }
  finally { loading.value = false }
}

const downloadBlob = (blob, name) => { const u = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = u; a.download = name; document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(u) }
const downloadImportTemplate = async () => {
  try { const r = await api.get('/testcases/import/template/', { responseType: 'blob' }); downloadBlob(r.data, 'testcase_import_template_v1.xlsx'); ElMessage.success(t('testcase.downloadTemplateSuccess')) }
  catch (e) { ElMessage.error(t('testcase.downloadTemplateFailed')) }
}
const openImportDialog = () => { importForm.value.projectId = projectFilter.value || ''; selectedImportFile.value = null; importDialogVisible.value = true }
const handleImportFileChange = (f) => { if (f?.raw) selectedImportFile.value = f.raw }
const submitImport = async () => {
  if (!importForm.value.projectId) { ElMessage.warning(t('testcase.importProjectRequired')); return }
  if (!selectedImportFile.value) { ElMessage.warning(t('testcase.importFileRequired')); return }
  const fd = new FormData(); fd.append('project_id', importForm.value.projectId); fd.append('file', selectedImportFile.value)
  isCreatingImport.value = true
  try { await api.post('/testcases/import-records/', fd, { headers: { 'Content-Type': 'multipart/form-data' } }); ElMessage.success(t('testcase.importCreated')); importDialogVisible.value = false; goToImportRecords() }
  catch (e) { ElMessage.error(e.response?.data?.error || t('testcase.importCreateFailed')) }
  finally { isCreatingImport.value = false }
}
const goToImportRecords = () => router.push('/ai-generation/testcases/import-records')
const fetchProjects = async () => {
  try { const r = await api.get('/projects/'); projects.value = r.data.results || r.data || [] }
  catch (e) { ElMessage.error(t('testcase.fetchProjectsFailed')) }
}
const hasAnyFilter = () => projectFilter.value || versionFilter.value || moduleFilter.value || priorityFilter.value || searchText.value

onMounted(() => {
  fetchProjects(); fetchVersions()
  if (route.query.project) projectFilter.value = Number(route.query.project)
  if (route.query.versions) { versionFilter.value = Number(route.query.versions); fetchModulesForFilter() }
  if (route.query.function_module) moduleFilter.value = Number(route.query.function_module)
  if (route.query.priority) priorityFilter.value = route.query.priority
  if (route.query.search) searchText.value = route.query.search
  if (hasAnyFilter()) fetchTestCases()
})
</script>

<style lang="scss" scoped>
/* ===== 页面 ===== */
.page-container {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
  min-height: 100vh;
  background: #f5f7fa;
}

/* ===== 顶栏 ===== */
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.top-left { display: flex; align-items: baseline; gap: 16px; }
.page-title { margin: 0; font-size: 1.4rem; font-weight: 600; color: #1a1a2e; }
.result-count { font-size: .88rem; color: #a0aec0; }

.top-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.act-btn {
  padding: 7px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #4a5568;
  font-size: .82rem;
  cursor: pointer;
  transition: all .15s;
  white-space: nowrap;
  &:hover { border-color: #667eea; color: #667eea; }
  &:disabled { opacity: .4; cursor: not-allowed; }
  &.primary { background: #667eea; color: #fff; border-color: #667eea; font-weight: 500; }
  &.primary:hover { background: #5a6fd6; }
}

/* ===== 筛选命令区 ===== */
.filter-command {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.filter-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}
.filter-group { display: flex; flex-direction: column; gap: 4px; }
.filter-label {
  font-size: .72rem;
  font-weight: 600;
  color: #a0aec0;
  text-transform: uppercase;
  letter-spacing: .5px;
}
.filter-select { width: 160px; }
.filter-select.short { width: 100px; }
.filter-search { width: 200px; }
.search-group { flex: 1; min-width: 180px; max-width: 280px; }
.cascade-arrow { color: #cbd5e0; font-size: 1.1rem; padding-bottom: 8px; }
.filter-divider { width: 1px; height: 36px; background: #e2e8f0; align-self: center; }

/* 活跃筛选标签 */
.active-filters { margin-top: 14px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.af-label { font-size: .78rem; color: #a0aec0; }
.af-chip {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: .78rem;
  background: #edf2f7;
  color: #4a5568;
  cursor: pointer;
  transition: all .15s;
  &:hover { background: #667eea; color: #fff; }
}
.af-clear { font-size: .78rem; color: #e53e3e; cursor: pointer; margin-left: 4px; &:hover { text-decoration: underline; } }

/* ===== 表格 ===== */
.table-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
  overflow: hidden;
}

.empty-filter-hint {
  text-align: center;
  padding: 80px 40px;
}
.empty-icon { font-size: 3rem; margin-bottom: 16px; }
.empty-title { font-size: 1.1rem; color: #1a1a2e; font-weight: 600; margin-bottom: 8px; }
.empty-desc { font-size: .9rem; color: #a0aec0; line-height: 1.6; }

.case-link { color: #1a1a2e; cursor: pointer; font-weight: 500; &:hover { color: #667eea; } }

.pri-dot {
  display: inline-block;
  padding: 2px 10px; border-radius: 4px; font-size: .78rem; font-weight: 600;
  &.low { color: #67c23a; background: #f0f9eb; }
  &.medium { color: #e6a23c; background: #fdf6ec; }
  &.high { color: #f56c6c; background: #fef0f0; }
  &.critical { color: #fff; background: #f56c6c; }
}

.mod-tag {
  display: inline-block;
  padding: 2px 8px; border-radius: 4px; font-size: .77rem;
  color: #059669; background: #ecfdf5;
}
.cell-muted { color: #cbd5e0; }

.row-btn {
  padding: 4px 10px; border: none; background: none; color: #667eea; font-size: .8rem; cursor: pointer;
  &:hover { text-decoration: underline; }
  &.danger { color: #e53e3e; }
  &.pass { color: #48bb78; font-size: 1rem; }
  &.pass:hover { color: #38a169; }
  &.fail { color: #fc8181; font-size: 1rem; }
  &.fail:hover { color: #e53e3e; }
  &:disabled { opacity: .3; cursor: not-allowed; }
}

.exec-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: .78rem;
  font-weight: 600;
  &.pass { background: #f0fff4; color: #22543d; }
  &.fail { background: #fff5f5; color: #742a2a; }
}

/* ===== 分页 ===== */
.pager-bar { display: flex; justify-content: center; padding: 20px 0; }

/* ===== Element Plus 微调 ===== */
:deep(.el-table) {
  --el-table-header-bg-color: #f8f9fb;
  font-size: .9rem;
}
:deep(.el-table th) {
  color: #a0aec0;
  font-weight: 600;
  font-size: .78rem;
  text-transform: uppercase;
  letter-spacing: .3px;
  border-bottom: 2px solid #e2e8f0;
}
:deep(.el-table .el-table__row) { cursor: pointer; }
:deep(.el-table .el-table__row:hover) { background: #f7f8fb; }

@media (max-width: 768px) {
  .page-container { padding: 12px; }
  .top-bar { flex-direction: column; gap: 12px; }
  .cascade-arrow, .filter-divider { display: none; }
  .filter-select, .filter-search { width: 100%; }
  .filter-row { flex-direction: column; }
}
</style>
