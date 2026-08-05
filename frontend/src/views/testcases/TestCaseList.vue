<template>
  <div class="ag-shell" data-ark-theme="endfield" data-ark-depth="moderate">
    <!-- Grid -->
    <div class="ag-grid" aria-hidden="true"></div>

    <!-- ====== Zone A: Header ====== -->
    <section class="ag-zone ag-zone--head">
      <header class="ag-zone__bar">
        <span class="ag-zone__kicker">TEST CASE / INDEX</span>
        <span class="ag-zone__rule" aria-hidden="true"></span>
        <span class="ag-zone__code">{{ total }} RECORDS</span>
      </header>
      <div class="ag-head">
        <h1 class="ag-head__title">{{ $t('testcase.title') }}</h1>
        <div class="ag-head__actions">
          <button
            v-if="selectedTestCases.length > 0"
            class="ag-btn ag-btn--danger"
            @click="batchDeleteTestCases"
            :disabled="isDeleting">
            {{ $t('testcase.batchDelete') }} ({{ selectedTestCases.length }})
          </button>
          <button class="ag-btn ag-btn--ghost" @click="exportToExcel">{{ $t('testcase.exportExcel') }}</button>
          <button class="ag-btn ag-btn--ghost" @click="downloadImportTemplate">{{ $t('testcase.downloadImportTemplate') }}</button>
          <button class="ag-btn ag-btn--ghost" @click="openImportDialog">{{ $t('testcase.importCases') }}</button>
          <button class="ag-btn ag-btn--ghost" @click="goToImportRecords">{{ $t('testcase.importRecords') }}</button>
          <button class="ag-btn ag-btn--ok" @click="$router.push('/ai-generation/testcases/create')">+ {{ $t('testcase.newCase') }}</button>
        </div>
      </div>
    </section>

    <!-- ====== Zone B: Content ====== -->
    <section class="ag-zone ag-zone--content">
      <div v-if="loading" class="ag-loading-bar" aria-hidden="true"></div>

      <!-- Filter -->
      <div class="ag-filter">
        <div class="ag-filter__field">
          <span class="ag-filter__label">PROJECT</span>
          <el-select
            v-model="projectFilter"
            :placeholder="$t('testcase.relatedProject')"
            clearable
            popper-class="ag-dropdown"
            @change="handleProjectFilterChange"
            class="ag-select-el">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </div>
        <span class="ag-flow__arrow" aria-hidden="true">→</span>
        <div class="ag-filter__field">
          <span class="ag-filter__label">VERSION</span>
          <el-select
            v-model="versionFilter"
            :placeholder="$t('testcase.versionFilter')"
            clearable
            filterable
            popper-class="ag-dropdown"
            @change="handleVersionFilterChange"
            :disabled="!projectFilter"
            class="ag-select-el">
            <el-option v-for="v in versions" :key="v.id" :label="v.name + (v.is_baseline ? ' 基线' : '')" :value="v.id" />
          </el-select>
        </div>
        <span class="ag-flow__arrow" aria-hidden="true">→</span>
        <div class="ag-filter__field">
          <span class="ag-filter__label">MODULE</span>
          <el-select
            v-model="moduleFilter"
            :placeholder="$t('testcase.moduleFilter')"
            clearable
            filterable
            popper-class="ag-dropdown"
            @change="handleFilter"
            :disabled="!versionFilter"
            class="ag-select-el">
            <el-option v-for="m in filterModules" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </div>
        <span class="ag-filter__div" aria-hidden="true"></span>
        <div class="ag-filter__field">
          <span class="ag-filter__label">PRIORITY</span>
          <el-select
            v-model="priorityFilter"
            :placeholder="$t('testcase.priorityFilter')"
            clearable
            popper-class="ag-dropdown"
            @change="handleFilter"
            class="ag-select-el ag-select-el--sm">
            <el-option :label="$t('testcase.low')" value="low" />
            <el-option :label="$t('testcase.medium')" value="medium" />
            <el-option :label="$t('testcase.high')" value="high" />
            <el-option :label="$t('testcase.critical')" value="critical" />
          </el-select>
        </div>
        <div class="ag-filter__field ag-filter__field--search">
          <span class="ag-filter__label">SEARCH</span>
          <el-input v-model="searchText" :placeholder="$t('testcase.searchPlaceholder')" clearable @input="handleSearch" class="ag-search">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
      </div>

      <!-- Active filter chips -->
      <div v-if="activeFilters.length > 0" class="ag-chips">
        <span class="ag-chips__label">当前筛选：</span>
        <span v-for="f in activeFilters" :key="f.key" class="ag-chip" @click="removeFilter(f.key)">
          {{ f.label }} <span class="ag-chip__x" aria-hidden="true">×</span>
        </span>
        <button class="ag-chip__clear" @click="clearAllFilters">清除全部</button>
      </div>

      <!-- Empty state: pick filters first -->
      <div v-if="!hasAnyFilter() && !loading" class="ag-empty">
        <span class="ag-empty__code">00 / PICK</span>
        <p class="ag-empty__title">筛选条件后查看用例</p>
        <p class="ag-empty__desc">选择 <strong>项目</strong> → <strong>版本</strong> → <strong>模块</strong> 快速定位目标用例</p>
      </div>

      <!-- Table -->
      <div v-else class="ag-table-wrap">
        <table class="ag-table ag-table--list">
          <thead>
            <tr>
              <th class="ag-th ag-th--sel">
                <input type="checkbox" :checked="pageAllSelected" @change="togglePageAll" :aria-label="$t('testcase.title')" />
              </th>
              <th class="ag-th ag-th--idx">#</th>
              <th class="ag-th ag-th--title">{{ $t('testcase.caseTitle') }}</th>
              <th class="ag-th ag-th--pri">{{ $t('testcase.priority') }}</th>
              <th class="ag-th ag-th--mod">{{ $t('testcase.moduleName') }}</th>
              <th class="ag-th ag-th--exec">执行状态</th>
              <th class="ag-th ag-th--author">{{ $t('testcase.author') }}</th>
              <th class="ag-th ag-th--time">{{ $t('testcase.createdAt') }}</th>
              <th class="ag-th ag-th--act">{{ $t('project.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in testcases" :key="row.id" class="ag-tr">
              <td class="ag-td ag-td--sel">
                <input type="checkbox" :checked="isRowSelected(row)" @change="toggleRow(row)" :aria-label="row.title" />
              </td>
              <td class="ag-td ag-td--idx">{{ getSerialNumber(testcases.indexOf(row)) }}</td>
              <td class="ag-td ag-td--title">
                <button class="ag-link" @click="goToTestCase(row.id)">{{ row.title }}</button>
              </td>
              <td class="ag-td ag-td--pri">
                <span class="ag-badge" :class="'ag-badge--' + row.priority">{{ getPriorityText(row.priority) }}</span>
              </td>
              <td class="ag-td ag-td--mod">
                <span v-if="row.function_module" class="ag-tag">{{ row.function_module.name }}</span>
                <span v-else class="ag-muted">—</span>
              </td>
              <td class="ag-td ag-td--exec">
                <span v-if="row.execution_status === 'passed'" class="ag-exec ag-exec--pass">✓ 通过</span>
                <span v-else-if="row.execution_status === 'failed'" class="ag-exec ag-exec--fail">✗ 不通过</span>
                <span v-else class="ag-muted">—</span>
              </td>
              <td class="ag-td ag-td--author">{{ row.author?.username }}</td>
              <td class="ag-td ag-td--time">{{ formatDate(row.created_at) }}</td>
              <td class="ag-td ag-td--act">
                <div class="ag-actions">
                  <button class="ag-btn ag-btn--sm ag-btn--pass" @click="executeCase(row, 'passed')" :disabled="row._executing" title="通过">✓</button>
                  <button class="ag-btn ag-btn--sm ag-btn--fail" @click="executeCase(row, 'failed')" :disabled="row._executing" title="不通过">✗</button>
                  <button class="ag-btn ag-btn--sm ag-btn--ghost" @click="editTestCase(row)">{{ $t('common.edit') }}</button>
                  <button class="ag-btn ag-btn--sm ag-btn--danger" @click="deleteTestCase(row)">{{ $t('common.delete') }}</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="hasAnyFilter()" class="ag-page">
        <span class="ag-page__info">共 {{ total }} 条</span>
        <div class="ag-page__ctrls">
          <select v-model="pageSize" @change="handleSizeChange" class="ag-select ag-select--page" aria-label="page size">
            <option v-for="n in [15, 25, 35, 50, 100]" :key="n" :value="n">{{ n }} / PAGE</option>
          </select>
          <div class="ag-page__btns">
            <button class="ag-btn ag-btn--sm" :disabled="currentPage <= 1" @click="currentPage--; handlePageChange()">← 上一页</button>
            <span class="ag-page__current">{{ currentPage }} / {{ Math.max(1, Math.ceil(total / pageSize)) }}</span>
            <button class="ag-btn ag-btn--sm" :disabled="currentPage >= Math.max(1, Math.ceil(total / pageSize))" @click="currentPage++; handlePageChange()">下一页 →</button>
          </div>
        </div>
      </div>
    </section>

    <!-- ====== Modal: Import ====== -->
    <div v-if="importDialogVisible" class="ag-modal" @click.self="importDialogVisible = false">
      <div class="ag-modal__box">
        <header class="ag-modal__head">
          <span class="ag-modal__kicker">TEST CASE / IMPORT</span>
          <button class="ag-modal__close" @click="importDialogVisible = false">×</button>
        </header>
        <div class="ag-modal__body">
          <div class="ag-tip">{{ $t('testcase.uploadTip') }}</div>
          <div class="ag-form">
            <div class="ag-form__group">
              <label>{{ $t('testcase.importProject') }}</label>
              <el-select v-model="importForm.projectId" :placeholder="$t('testcase.selectImportProject')" filterable popper-class="ag-dropdown" style="width: 100%">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </div>
            <div class="ag-form__group">
              <label>{{ $t('testcase.selectImportFile') }}</label>
              <el-upload class="ag-upload" drag action="#" :auto-upload="false" :limit="1" accept=".xlsx" :show-file-list="false" :on-change="handleImportFileChange">
                <el-icon class="el-icon--upload"><Upload /></el-icon>
                <div class="el-upload__text">{{ $t('testcase.chooseFile') }}</div>
                <div class="el-upload__tip">{{ $t('testcase.selectedFile') }}: {{ selectedImportFile?.name || '-' }}</div>
              </el-upload>
            </div>
          </div>
        </div>
        <footer class="ag-modal__foot">
          <button class="ag-btn ag-btn--ghost" @click="importDialogVisible = false">{{ $t('common.cancel') }}</button>
          <button class="ag-btn ag-btn--ghost" @click="downloadImportTemplate">{{ $t('testcase.downloadImportTemplate') }}</button>
          <button class="ag-btn ag-btn--ok" :disabled="isCreatingImport" @click="submitImport">
            {{ isCreatingImport ? $t('testcase.uploading') : $t('common.confirm') }}
          </button>
        </footer>
      </div>
    </div>
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

// ===== 行选择 =====
const isRowSelected = (row) => selectedTestCases.value.some(s => s.id === row.id)
const toggleRow = (row) => {
  const idx = selectedTestCases.value.findIndex(s => s.id === row.id)
  if (idx >= 0) selectedTestCases.value.splice(idx, 1)
  else selectedTestCases.value.push(row)
}
const pageAllSelected = computed(() => testcases.value.length > 0 && testcases.value.every(r => isRowSelected(r)))
const togglePageAll = () => {
  const pageIds = new Set(testcases.value.map(r => r.id))
  if (pageAllSelected.value) {
    selectedTestCases.value = selectedTestCases.value.filter(s => !pageIds.has(s.id))
  } else {
    const selectedIds = new Set(selectedTestCases.value.map(s => s.id))
    for (const r of testcases.value) {
      if (!selectedIds.has(r.id)) selectedTestCases.value.push(r)
    }
  }
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
/* =============================================
   Ark Moderate — Test Case Index
   ============================================= */
.ag-shell {
  --ark-ink: #191919;
  --ark-paper: #f2f2f0;
  --ark-signal: #fffa00;
  --ark-state: #00ffa2;
  --ark-border: #e4e4de;

  height: calc(100vh - 52px);
  background: var(--ark-paper);
  position: relative;
  padding: 24px 24px 0;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  display: flex; flex-direction: column;
  overflow: hidden;
}

/* Grid */
.ag-grid {
  position: absolute; inset: 0; pointer-events: none; z-index: 0;
  background-image:
    linear-gradient(to right, rgba(0,0,0,.03) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0,0,0,.03) 1px, transparent 1px);
  background-size: 72px 72px;
}

/* ============================================
   Zones
   ============================================ */
.ag-zone {
  position: relative; z-index: 1;
  background: #fff;
  border: 1px solid var(--ark-border);
  animation: ag-enter .35s ease-out both;

  &--head { flex-shrink: 0; margin-bottom: 16px; border-top: 3px solid var(--ark-ink); }
  &--content {
    flex: 1; min-height: 0; margin-bottom: 24px;
    display: flex; flex-direction: column; overflow: auto;
    animation-delay: .05s;
  }
  &__bar {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 20px 0;
  }
  &__kicker {
    font-size: 10px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .16em; color: #888; white-space: nowrap;
  }
  &__rule { flex: 1; height: 1px; background: var(--ark-border); }
  &__code {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .1em; color: #aaa; white-space: nowrap;
  }
}

/* ============================================
   Header
   ============================================ */
.ag-head {
  display: flex; justify-content: space-between; align-items: flex-end; gap: 20px;
  padding: 16px 20px 20px;
  &__title {
    margin: 0; font-size: 24px; font-weight: 900; color: var(--ark-ink); line-height: 1.3;
    &::before {
      content: ""; display: block; width: 44px; height: 4px;
      background: var(--ark-signal); margin-bottom: 10px;
    }
  }
  &__actions { display: flex; gap: 10px; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }
}

/* ============================================
   Filter
   ============================================ */
.ag-filter {
  display: flex; align-items: flex-end; gap: 12px; padding: 16px 20px;
  border-bottom: 1px solid var(--ark-border); flex-wrap: wrap;
  &__field {
    display: flex; flex-direction: column; gap: 6px;
    &--search { flex: 1; min-width: 200px; max-width: 300px; }
  }
  &__label {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .12em; color: #999;
  }
  &__div { width: 1px; height: 34px; background: var(--ark-border); align-self: flex-end; margin-bottom: 2px; }
}
.ag-flow__arrow {
  font-family: "Space Grotesk", system-ui, sans-serif;
  color: #c5c7c3; font-size: 13px; padding-bottom: 10px; user-select: none;
}

/* ============================================
   Element Plus overrides (select / search)
   ============================================ */
.ag-select-el {
  width: 180px;
  :deep(.el-input__wrapper) {
    border-radius: 0; box-shadow: 0 0 0 1px #c9cbc8 inset; background: #fff;
    font-family: inherit;
  }
  :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px var(--ark-signal) inset; }
  :deep(.el-input__inner) { font-family: inherit; font-size: 13px; }
  &--sm { width: 120px; }
}
.ag-search {
  width: 100%;
  :deep(.el-input__wrapper) {
    border-radius: 0; box-shadow: 0 0 0 1px #c9cbc8 inset; background: #fff;
    font-family: inherit;
  }
  :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px var(--ark-signal) inset; }
  :deep(.el-input__inner) { font-family: inherit; font-size: 13px; }
  :deep(.el-input__prefix) { color: #999; }
}

/* ============================================
   Chips
   ============================================ */
.ag-chips {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 12px 20px; border-bottom: 1px solid var(--ark-border);
  &__label { font-size: 12px; color: #999; }
}
.ag-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; font-size: 12px; cursor: pointer;
  background: #f2f2f0; color: #555; border: 1px solid #d8dad7;
  transition: background .12s, color .12s, border-color .12s;
  &:hover { background: var(--ark-ink); color: #fff; border-color: var(--ark-ink); }
  &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: 1px; }
  &__x { font-size: 13px; line-height: 1; color: #999; }
}
.ag-chip:hover .ag-chip__x { color: #fff; }
.ag-chip__clear {
  all: unset; cursor: pointer; font-size: 12px; color: #b03a35; padding: 4px 6px;
  &:hover { text-decoration: underline; }
  &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: 1px; }
}

/* ============================================
   Empty
   ============================================ */
.ag-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 72px 20px; color: #999; text-align: center; flex: 1;
  &__code {
    font-size: 20px; font-weight: 900; letter-spacing: .24em;
    font-family: "Space Grotesk", system-ui, sans-serif; color: var(--ark-ink);
    background: #fff; border: 1px solid var(--ark-border);
    border-left: 3px solid var(--ark-signal);
    padding: 12px 24px; margin-bottom: 16px;
  }
  &__title { margin: 0 0 8px; font-size: 15px; font-weight: 700; color: var(--ark-ink); }
  &__desc { margin: 0; font-size: 13px; color: #999; line-height: 1.8; }
}

/* ============================================
   Table
   ============================================ */
.ag-table-wrap { flex: 1; overflow: visible; }
.ag-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
  &--list { min-width: 1120px; }
  thead {
    background: var(--ark-ink);
    input[type="checkbox"] { accent-color: var(--ark-signal); }
  }
  th, td { padding: 10px 12px; text-align: left; vertical-align: middle; }
}
.ag-th {
  font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em; color: rgba(255,255,255,.85); font-weight: 600;
  &--sel { width: 44px; text-align: center; }
  &--idx { width: 56px; text-align: center; }
  &--title { min-width: 240px; }
  &--pri { width: 96px; }
  &--mod { width: 140px; }
  &--exec { width: 110px; text-align: center; }
  &--author { width: 110px; }
  &--time { width: 150px; }
  &--act { width: 200px; }
}
.ag-tr {
  border-bottom: 1px solid #eee;
  transition: background .1s;
  &:hover { background: #f8fafa; }
}
.ag-td {
  color: #444; line-height: 1.6;
  &--sel { text-align: center; }
  &--idx { color: #999; text-align: center; font-family: "Space Grotesk", system-ui, sans-serif; font-size: 12px; }
  &--title { font-weight: 600; }
  &--pri { text-align: center; }
  &--mod { color: #666; }
  &--exec { text-align: center; }
  &--author { color: #666; }
  &--time { color: #888; font-size: 12px; white-space: nowrap; }
  &--act { white-space: nowrap; }
}
.ag-actions { display: flex; gap: 4px; flex-wrap: nowrap; }
.ag-link {
  all: unset; cursor: pointer; color: var(--ark-ink); font-weight: 700;
  text-decoration: underline; text-underline-offset: 3px;
  &:hover { color: #666; }
  &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: 2px; }
}
.ag-muted { color: #ccc; }
input[type="checkbox"] {
  width: 15px; height: 15px; margin: 0; cursor: pointer; accent-color: var(--ark-ink);
}

/* ============================================
   Badges / tags / exec state
   ============================================ */
.ag-badge {
  display: inline-block; padding: 3px 10px; font-size: 10px;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em; font-weight: 600; border: 1px solid;
  &--low { color: #0f8a5c; background: #e6f7f0; border-color: #9edfc2; }
  &--medium { color: #7d6a16; background: #fdf7e4; border-color: #e0d29a; }
  &--high { color: #a04030; background: #fbeef0; border-color: #ecc0c0; }
  &--critical { color: #fff; background: var(--ark-ink); border-color: var(--ark-ink); }
}
.ag-tag {
  display: inline-block; padding: 2px 10px; font-size: 11px;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .04em;
  color: #555; background: #fafaf8; border: 1px solid var(--ark-border);
}
.ag-exec {
  display: inline-block; padding: 3px 10px; font-size: 10px;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .08em; font-weight: 700; border: 1px solid;
  &--pass { color: #0f8a5c; background: #e6f7f0; border-color: #9edfc2; }
  &--fail { color: #b03a35; background: #fbefee; border-color: #e3b9b6; }
}

/* ============================================
   Buttons
   ============================================ */
.ag-btn {
  all: unset; cursor: pointer;
  position: relative;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  min-height: 36px; padding: 8px 18px; box-sizing: border-box;
  white-space: nowrap;
  font-size: 12px; font-weight: 600;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .08em;
  color: var(--ark-ink); background: #fff; border: 1px solid #c9cbc8;
  transition: background .12s, border-color .12s, color .12s, transform .08s;
  user-select: none; -webkit-tap-highlight-color: transparent;

  &::before {
    content: ""; position: absolute; left: -1px; top: -1px; bottom: -1px;
    width: 3px; background: transparent;
    transition: background .12s;
  }
  &:hover:not(:disabled) { background: #e9ebe9; border-color: #a9aca9; }
  &:active:not(:disabled) { transform: translateY(1px); background: #dde0dd; }
  &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: 2px; }
  &:disabled {
    color: #b4b6b3; background: #f5f6f4; border-color: #e1e3e0; cursor: not-allowed;
    &::before { background: transparent; }
  }

  &--sm { min-height: 30px; padding: 4px 10px; font-size: 11px; letter-spacing: .06em; }
  &--ghost {
    background: transparent; border-color: transparent; color: #6b6d6a;
    &:hover:not(:disabled) { background: #eef0ed; border-color: #d4d6d3; color: #222; }
    &:disabled { background: transparent; border-color: transparent; }
  }
  &--ok {
    color: #fff; background: var(--ark-ink); border-color: var(--ark-ink);
    &::before { background: var(--ark-signal); }
    &:hover:not(:disabled) { background: #2e2e2e; border-color: #2e2e2e; }
    &:active:not(:disabled) { background: #3a3a3a; border-color: #3a3a3a; }
    &:disabled { color: #c9cbc8; background: #e8eae7; border-color: #d6d8d5; &::before { background: transparent; } }
  }
  &--danger {
    color: #b03a35; background: #fff; border-color: #e3b9b6;
    &::before { background: #e06060; }
    &:hover:not(:disabled) { background: #fbefee; border-color: #d9a3a0; }
    &:disabled { color: #c9aca9; background: #f8f4f3; border-color: #eadcd9; &::before { background: transparent; } }
  }
  &--pass {
    color: #0f8a5c; background: #fff; border-color: #b9dccb;
    &::before { background: var(--ark-state); }
    &:hover:not(:disabled) { background: #e6f7f0; border-color: #9edfc2; }
    &:disabled { color: #c9d8cf; background: #f4f8f5; border-color: #dce7e0; &::before { background: transparent; } }
  }
  &--fail {
    color: #b03a35; background: #fff; border-color: #e3b9b6;
    &::before { background: #e06060; }
    &:hover:not(:disabled) { background: #fbefee; border-color: #d9a3a0; }
    &:disabled { color: #d8c2c0; background: #faf5f4; border-color: #ecdcd9; &::before { background: transparent; } }
  }
}

/* ============================================
   Pagination
   ============================================ */
.ag-page {
  display: flex; justify-content: space-between; align-items: center; gap: 16px;
  padding: 14px 20px; border-top: 1px solid var(--ark-border); flex-wrap: wrap;
  &__info { font-size: 12px; color: #999; font-family: "Space Grotesk", system-ui, sans-serif; }
  &__ctrls { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
  &__btns { display: flex; align-items: center; gap: 8px; }
  &__current {
    font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #555; padding: 0 4px; white-space: nowrap;
  }
}
.ag-select--page { height: 30px; font-size: 11px; padding: 0 26px 0 8px; }

/* ============================================
   Select (native)
   ============================================ */
.ag-select {
  height: 36px; padding: 0 28px 0 10px; box-sizing: border-box; line-height: 1;
  border: 1px solid #ccc; background: #fff;
  font-size: 13px; font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .04em; color: #444;
  cursor: pointer; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%23999'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 10px center;
  &:focus { outline: none; border-color: #fffa00; }
  &:focus-visible { outline: 2px solid #fffa00; outline-offset: 1px; }
}

/* ============================================
   Loading bar
   ============================================ */
.ag-loading-bar {
  position: absolute; top: -1px; left: 0; right: 0; height: 3px; z-index: 5;
  background: linear-gradient(90deg, transparent 0%, var(--ark-signal) 50%, transparent 100%);
  background-size: 200px 3px; background-repeat: no-repeat;
  animation: ag-scan 1.1s linear infinite;
}
@keyframes ag-scan {
  from { background-position: -200px 0; }
  to { background-position: calc(100% + 200px) 0; }
}

/* ============================================
   Modal
   ============================================ */
.ag-modal {
  position: fixed; inset: 0; background: rgba(4,6,8,.72);
  display: flex; align-items: center; justify-content: center; z-index: 2000;
  &__box {
    background: #fff; width: 90%; max-width: 560px; max-height: 84vh;
    display: flex; flex-direction: column; border: 1px solid #888;
  }
  &__head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 20px; background: var(--ark-ink); color: #fff; flex-shrink: 0;
  }
  &__kicker {
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .14em; color: rgba(255,255,255,.7);
  }
  &__close {
    all: unset; cursor: pointer;
    width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center;
    font-size: 22px; color: rgba(255,255,255,.55); line-height: 1; border: 1px solid transparent;
    transition: color .12s, border-color .12s;
    &:hover { color: #fff; border-color: rgba(255,255,255,.35); }
    &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: 1px; }
  }
  &__body { padding: 20px 24px 24px; overflow-y: auto; flex: 1; }
  &__foot {
    display: flex; justify-content: flex-end; gap: 10px;
    padding: 14px 24px; border-top: 1px solid var(--ark-border);
    background: #fafaf8; flex-shrink: 0;
  }
}
.ag-tip {
  padding: 10px 14px; margin-bottom: 16px;
  background: #fafaf8; border: 1px solid var(--ark-border); border-left: 3px solid var(--ark-signal);
  font-size: 12px; color: #666; line-height: 1.6;
}

/* ============================================
   Form (Element Plus deep overrides)
   ============================================ */
.ag-form {
  &__group {
    display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px;
    label {
      font-weight: 600; font-size: 11px; color: #666;
      font-family: "Space Grotesk", system-ui, sans-serif;
      text-transform: uppercase; letter-spacing: .06em;
    }
  }
  :deep(.el-input__wrapper), :deep(.el-textarea__inner) {
    border-radius: 0; box-shadow: 0 0 0 1px #c9cbc8 inset; background: #fff;
    font-family: inherit;
  }
  :deep(.el-input__wrapper.is-focus), :deep(.el-textarea__inner:focus) {
    box-shadow: 0 0 0 1px var(--ark-signal) inset;
  }
  :deep(.el-input__inner) { font-family: inherit; }
}

/* Upload dropzone */
.ag-upload {
  width: 100%;
  :deep(.el-upload-dragger) {
    border-radius: 0; border: 1px dashed #c9cbc8; background: #fff; padding: 30px 20px;
    &:hover { border-color: var(--ark-ink); }
    &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: -2px; }
  }
  :deep(.el-icon--upload) { color: #999; }
  :deep(.el-upload__text) { color: #666; font-size: 13px; }
  :deep(.el-upload__tip) { color: #999; font-size: 12px; margin-top: 10px; }
}

/* ============================================
   Motion
   ============================================ */
@keyframes ag-enter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}

@media (prefers-reduced-motion: reduce) {
  .ag-zone, .ag-btn, .ag-select, .ag-tr, .ag-chip, .ag-modal__close, .ag-loading-bar {
    transition: none !important; animation: none !important;
  }
  .ag-btn:active:not(:disabled) { transform: none; }
}

/* ============================================
   Responsive
   ============================================ */
@media (max-width: 1024px) {
  .ag-shell { padding: 16px 16px 0; }
  .ag-table { min-width: 1000px; }
}
@media (max-width: 768px) {
  .ag-shell { padding: 12px 12px 0; }
  .ag-head { flex-direction: column; align-items: flex-start; }
  .ag-head__actions { width: 100%; justify-content: flex-start; }
  .ag-head__actions .ag-btn { flex: 1; }
  .ag-filter { flex-direction: column; align-items: stretch; }
  .ag-flow__arrow, .ag-filter__div { display: none; }
  .ag-select-el, .ag-select-el--sm, .ag-filter__field--search { width: 100%; max-width: none; }
  .ag-page { flex-direction: column; align-items: flex-start; }
  .ag-page__ctrls { flex-direction: column; align-items: flex-start; width: 100%; }
  .ag-modal__box { width: 95%; }
}
</style>

<!-- Unscoped styles for teleported Element Plus dropdown poppers -->
<style lang="scss">
.ag-dropdown.el-popper { border-radius: 0; border-color: #191919; }
.ag-dropdown .el-select-dropdown {
  border-radius: 0; border-color: #191919; box-shadow: none;
}
.ag-dropdown .el-select-dropdown__item {
  border-radius: 0; font-size: 13px; color: #333; height: 34px; line-height: 34px;
}
.ag-dropdown .el-select-dropdown__item:hover { background: #f4f5f3; color: #191919; }
.ag-dropdown .el-select-dropdown__item.is-selected { color: #191919; font-weight: 700; }
</style>
