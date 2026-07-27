<template>
  <div class="tcl-root">
    <!-- 顶栏 -->
    <div class="tcl-top">
      <div class="tcl-top__left">
        <h1 class="tcl-top__title">{{ $t('testcase.title') }}</h1>
        <span v-if="total > 0 && hasAnyFilter()" class="tcl-top__count">{{ total }} 条结果</span>
      </div>
      <div class="tcl-top__actions">
        <button class="tcl-btn" v-if="selectedTestCases.length > 0" @click="batchDeleteTestCases" :disabled="isDeleting">
          🗑 {{ $t('testcase.batchDelete') }} ({{ selectedTestCases.length }})
        </button>
        <button class="tcl-btn" @click="exportToExcel">📥 {{ $t('testcase.exportExcel') }}</button>
        <button class="tcl-btn" @click="downloadImportTemplate">📋 模板</button>
        <button class="tcl-btn" @click="openImportDialog">📤 {{ $t('testcase.importCases') }}</button>
        <button class="tcl-btn" @click="goToImportRecords">📂 记录</button>
        <button class="tcl-btn--primary" @click="$router.push('/ai-generation/testcases/create')">＋ {{ $t('testcase.newCase') }}</button>
      </div>
    </div>

    <!-- 筛选命令区 -->
    <div class="tcl-filter">
      <div class="tcl-filter__row">
        <div class="tcl-filter__group">
          <label class="tcl-filter__label">项目</label>
          <el-select v-model="projectFilter" :placeholder="$t('testcase.relatedProject')" clearable @change="handleProjectFilterChange" class="tcl-filter__select">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </div>
        <span class="tcl-filter__arrow">→</span>
        <div class="tcl-filter__group">
          <label class="tcl-filter__label">版本</label>
          <el-select v-model="versionFilter" :placeholder="$t('testcase.versionFilter')" clearable filterable @change="handleVersionFilterChange" :disabled="!projectFilter" class="tcl-filter__select">
            <el-option v-for="v in versions" :key="v.id" :label="v.name + (v.is_baseline ? ' 基线' : '')" :value="v.id" />
          </el-select>
        </div>
        <span class="tcl-filter__arrow">→</span>
        <div class="tcl-filter__group">
          <label class="tcl-filter__label">模块</label>
          <el-select v-model="moduleFilter" :placeholder="$t('testcase.moduleFilter')" clearable filterable @change="handleFilter" :disabled="!versionFilter" class="tcl-filter__select">
            <el-option v-for="m in filterModules" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </div>
        <div class="tcl-filter__div"></div>
        <div class="tcl-filter__group">
          <label class="tcl-filter__label">优先级</label>
          <el-select v-model="priorityFilter" :placeholder="$t('testcase.priorityFilter')" clearable @change="handleFilter" class="filter-select short">
            <el-option :label="$t('testcase.low')" value="low" />
            <el-option :label="$t('testcase.medium')" value="medium" />
            <el-option :label="$t('testcase.high')" value="high" />
            <el-option :label="$t('testcase.critical')" value="critical" />
          </el-select>
        </div>
        <div class="filter-group search-group">
          <label class="tcl-filter__label">搜索</label>
          <el-input v-model="searchText" :placeholder="$t('testcase.searchPlaceholder')" clearable @input="handleSearch" class="tcl-filter__search">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
      </div>

      <!-- 活跃筛选标签 -->
      <div v-if="activeFilters.length > 0" class="tcl-chips">
        <span class="tcl-chip__label">当前筛选：</span>
        <span v-for="f in activeFilters" :key="f.key" class="tcl-chip" @click="removeFilter(f.key)">
          {{ f.label }} ✕
        </span>
        <span class="tcl-chip__clear" @click="clearAllFilters">清除全部</span>
      </div>
    </div>

    <!-- 表格区 -->
    <div class="tcl-table-card">
      <div v-if="!hasAnyFilter() && !loading" class="tcl-empty">
        <div class="tcl-empty__icon">🔍</div>
        <div class="tcl-empty__title">筛选条件后查看用例</div>
        <div class="tcl-empty__desc">选择 <strong>项目</strong> → <strong>版本</strong> → <strong>模块</strong> 快速定位目标用例</div>
      </div>

      <el-table v-else :data="testcases" v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange" stripe>
        <el-table-column type="selection" width="48" />
        <el-table-column type="index" :label="'#'" width="60" :index="getSerialNumber" />
        <el-table-column prop="title" :label="$t('testcase.caseTitle')" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="tcl-link" @click="goToTestCase(row.id)">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" :label="$t('testcase.priority')" width="90" align="center">
          <template #default="{ row }">
            <span class="tcl-pri" :class="row.priority">{{ getPriorityText(row.priority) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="function_module" :label="$t('testcase.moduleName')" width="130">
          <template #default="{ row }">
            <span v-if="row.function_module" class="tcl-mod">{{ row.function_module.name }}</span>
            <span v-else class="tcl-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('testcase.execution')" width="130" align="center">
          <template #default="{ row }">
            <span v-if="row.execution_status === 'passed'" class="tcl-exec pass">✓ 通过</span>
            <span v-else-if="row.execution_status === 'failed'" class="tcl-exec fail">✕ 不通过</span>
            <span v-else class="tcl-muted">—</span>
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
            <button class="tcl-row-btn" @click="editTestCase(row)">编辑</button>
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
  query.page = currentPage.value
  router.push({ path: `/ai-generation/testcases/${id}`, query })
}

const editTestCase = (tc) => {
  const query = {}
  if (projectFilter.value) query.project = projectFilter.value
  if (versionFilter.value) query.versions = versionFilter.value
  if (moduleFilter.value) query.function_module = moduleFilter.value
  if (priorityFilter.value) query.priority = priorityFilter.value
  if (searchText.value) query.search = searchText.value
  query.page = currentPage.value
  router.push({ path: `/ai-generation/testcases/${tc.id}/edit`, query })
}

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
  if (route.query.page) currentPage.value = Number(route.query.page)
  if (hasAnyFilter()) fetchTestCases()
})
</script>

<style lang="scss" scoped>
.tcl-root { padding: 24px; max-width: 1400px; margin: 0 auto; min-height: calc(100vh - 52px); background: #f2f2f0; font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif; }
.tcl-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; &__left { display: flex; align-items: baseline; gap: 14px; } &__title { margin: 0; font-size: 1.5rem; font-weight: 800; color: #191919; letter-spacing: -.01em; } &__count { font-size: .85rem; color: #999; font-family: "Space Grotesk", system-ui, sans-serif; } &__actions { display: flex; gap: 6px; flex-wrap: wrap; } }
.tcl-btn { all: unset; cursor: pointer; padding: 7px 16px; font-size: 12px; font-weight: 600; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .05em; color: #555; background: #fff; border: 1px solid #ccc; white-space: nowrap; transition: all .12s; &:hover:not(:disabled) { border-color: #999; color: #333; } &:disabled { opacity: .3; cursor: not-allowed; } &--primary { background: #fffa00; color: #191919; border-color: #fffa00; font-weight: 700; &:hover:not(:disabled) { background: #e6e100; } } }
.tcl-filter { background: #fff; padding: 20px 24px; margin-bottom: 16px; border: 1px solid #e4e4de; &__row { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; } &__group { display: flex; flex-direction: column; gap: 4px; } &__label { font-size: 10px; font-weight: 700; color: #999; text-transform: uppercase; letter-spacing: .08em; font-family: "Space Grotesk", system-ui, sans-serif; } &__select { width: 160px; :deep(.el-input__wrapper) { border-radius: 0 !important; box-shadow: 0 0 0 1px #d0cec8 inset !important; } } &__select--short { width: 100px; :deep(.el-input__wrapper) { border-radius: 0 !important; } } &__search { width: 200px; :deep(.el-input__wrapper) { border-radius: 0 !important; box-shadow: 0 0 0 1px #d0cec8 inset !important; } } &__arrow { color: #ccc; font-size: 1.1rem; padding-bottom: 8px; } &__div { width: 1px; height: 36px; background: #e4e4de; align-self: center; } &__search-group { flex: 1; min-width: 180px; max-width: 280px; } }
.tcl-chips { margin-top: 14px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tcl-chip { display: inline-block; padding: 3px 12px; font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .04em; background: #f2f2f0; color: #555; cursor: pointer; border: 1px solid #e0ded8; &:hover { background: #191919; color: #fff; border-color: #191919; } &__label { font-size: 12px; color: #999; } &__clear { font-size: 12px; color: #c03939; cursor: pointer; margin-left: 4px; &:hover { text-decoration: underline; } } }
.tcl-table-card { background: #fff; border: 1px solid #e4e4de; overflow: hidden; }
.tcl-empty { text-align: center; padding: 80px 40px; &__icon { font-size: 3rem; margin-bottom: 16px; } &__title { font-size: 1.1rem; color: #191919; font-weight: 700; margin-bottom: 8px; } &__desc { font-size: .9rem; color: #999; line-height: 1.6; } }
.tcl-link { color: #191919; cursor: pointer; font-weight: 600; &:hover { text-decoration: underline; } }
.tcl-muted { color: #ccc; }
.tcl-pri { display: inline-block; padding: 2px 10px; font-size: 11px; font-weight: 700; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .05em; border: 1px solid; &.low { color: #1a8051; background: #e0f5e8; border-color: #88d4a0; } &.medium { color: #8a6d14; background: #fefae0; border-color: #e8d888; } &.high { color: #a04030; background: #fef0f0; border-color: #f0b0b0; } &.critical { color: #fff; background: #191919; border-color: #191919; } }
.tcl-mod { display: inline-block; padding: 2px 8px; font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .04em; color: #1a8051; background: #e0f5e8; }
.tcl-exec { display: inline-block; padding: 3px 12px; font-size: 11px; font-weight: 600; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .05em; &.pass { background: #e0f5e8; color: #1a8051; } &.fail { background: #fef0f0; color: #a04030; } }
.tcl-row-btn { all: unset; cursor: pointer; padding: 2px 8px; font-size: 13px; color: #999; &:hover { color: #191919; } &--pass { &:hover { color: #00a86b; } } &--fail { &:hover { color: #e04040; } } &--danger { color: #ccc; &:hover { color: #e04040; } } &:disabled { opacity: .2; cursor: not-allowed; } }
.pager-bar { display: flex; justify-content: center; padding: 24px 0; }
:deep(.el-table) { font-size: .88rem; }
:deep(.el-table th) { color: #999; font-weight: 700; font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .06em; border-bottom: 2px solid #191919; background: #fafaf8; }
:deep(.el-table .el-table__row) { cursor: pointer; }
:deep(.el-table .el-table__row:hover) { background: #fafaf8; }
:deep(.el-checkbox__input.is-checked .el-checkbox__inner) { background-color: #191919; border-color: #191919; }
@media (max-width: 768px) { .tcl-root { padding: 12px; } .tcl-top { flex-direction: column; gap: 12px; } .tcl-filter__arrow, .tcl-filter__div { display: none; } .tcl-filter__select, .tcl-filter__search, .tcl-filter__search-group { width: 100%; } .tcl-filter__row { flex-direction: column; } }
</style>
