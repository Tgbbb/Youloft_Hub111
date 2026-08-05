<template>
  <div class="ag-shell" data-ark-theme="endfield" data-ark-depth="moderate">
    <!-- Grid -->
    <div class="ag-grid" aria-hidden="true"></div>

    <!-- ====== Zone A: Header ====== -->
    <section class="ag-zone ag-zone--head">
      <header class="ag-zone__bar">
        <span class="ag-zone__kicker">VERSION / INDEX</span>
        <span class="ag-zone__rule" aria-hidden="true"></span>
        <span class="ag-zone__code">{{ total }} RECORDS</span>
      </header>
      <div class="ag-head">
        <h1 class="ag-head__title">{{ $t('version.title') }}</h1>
        <div class="ag-head__actions">
          <button
            v-if="selectedVersions.length > 0"
            class="ag-btn ag-btn--danger"
            @click="batchDeleteVersions"
            :disabled="isDeleting">
            {{ $t('version.batchDelete') }} ({{ selectedVersions.length }})
          </button>
          <button class="ag-btn ag-btn--ok" @click="createVersion">+ {{ $t('version.newVersion') }}</button>
        </div>
      </div>
    </section>

    <!-- ====== Zone B: Content ====== -->
    <section class="ag-zone ag-zone--content">
      <div v-if="loading" class="ag-loading-bar" aria-hidden="true"></div>

      <!-- Filter -->
      <div class="ag-filter">
        <div class="ag-filter__field ag-filter__field--search">
          <span class="ag-filter__label">SEARCH / NAME</span>
          <input v-model="searchText" @input="handleSearch" class="ag-input" :placeholder="$t('version.searchPlaceholder')" />
        </div>
        <div class="ag-filter__field">
          <span class="ag-filter__label">PROJECT</span>
          <select v-model="projectFilter" @change="handleFilter" class="ag-select">
            <option value="">{{ $t('version.relatedProject') }}</option>
            <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
        <div class="ag-filter__field">
          <span class="ag-filter__label">TYPE</span>
          <select v-model="baselineFilter" @change="handleFilter" class="ag-select">
            <option value="">{{ $t('version.versionType') }}</option>
            <option :value="true">{{ $t('version.baselineVersion') }}</option>
            <option :value="false">{{ $t('version.normalVersion') }}</option>
          </select>
        </div>
      </div>

      <!-- Table -->
      <div v-if="versions.length > 0" class="ag-table-wrap">
        <table class="ag-table ag-table--list">
          <thead>
            <tr>
              <th class="ag-th ag-th--sel">
                <input type="checkbox" :checked="pageAllSelected" @change="togglePageAll" :aria-label="$t('version.title')" />
              </th>
              <th class="ag-th ag-th--idx">#</th>
              <th class="ag-th ag-th--name">{{ $t('version.versionName') }}</th>
              <th class="ag-th ag-th--proj">{{ $t('version.relatedProject') }}</th>
              <th class="ag-th ag-th--desc">{{ $t('version.description') }}</th>
              <th class="ag-th ag-th--count">{{ $t('version.testCaseCount') }}</th>
              <th class="ag-th ag-th--creator">{{ $t('version.creator') }}</th>
              <th class="ag-th ag-th--time">{{ $t('version.createdAt') }}</th>
              <th class="ag-th ag-th--act">{{ $t('project.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in versions" :key="row.id" class="ag-tr">
              <td class="ag-td ag-td--sel">
                <input type="checkbox" :checked="isRowSelected(row)" @change="toggleRow(row)" :aria-label="row.name" />
              </td>
              <td class="ag-td ag-td--idx">{{ getSerialNumber(versions.indexOf(row)) }}</td>
              <td class="ag-td ag-td--name">
                <span class="ag-version-name">
                  <span>{{ row.name }}</span>
                  <span v-if="row.is_baseline" class="ag-badge ag-badge--baseline">{{ $t('version.baseline') }}</span>
                </span>
              </td>
              <td class="ag-td ag-td--proj">
                <div v-if="row.projects && row.projects.length > 0" class="ag-project-tags">
                  <span v-for="project in row.projects.slice(0, 2)" :key="project.id" class="ag-tag">{{ project.name }}</span>
                  <span v-if="row.projects.length > 2" class="ag-tag ag-tag--more" :title="getProjectsTooltip(row.projects)">+{{ row.projects.length - 2 }}</span>
                </div>
                <span v-else class="ag-muted">{{ $t('version.noProject') }}</span>
              </td>
              <td class="ag-td ag-td--desc"><div class="ag-clamp">{{ row.description }}</div></td>
              <td class="ag-td ag-td--count"><span class="ag-count">{{ row.testcases_count }}</span></td>
              <td class="ag-td ag-td--creator">{{ row.created_by?.username }}</td>
              <td class="ag-td ag-td--time">{{ formatDate(row.created_at) }}</td>
              <td class="ag-td ag-td--act">
                <div class="ag-actions">
                  <button class="ag-btn ag-btn--sm" @click="openModuleDialog(row)">{{ $t('version.modules') }}</button>
                  <button class="ag-btn ag-btn--sm" @click="editVersion(row)">{{ $t('common.edit') }}</button>
                  <button class="ag-btn ag-btn--sm ag-btn--danger" @click="deleteVersion(row)">{{ $t('common.delete') }}</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Empty -->
      <div v-else-if="!loading" class="ag-empty">
        <span class="ag-empty__code">00 / EMPTY</span>
        <p class="ag-empty__title">暂无版本</p>
        <p class="ag-empty__desc">创建版本后，即可关联项目与测试用例</p>
      </div>

      <!-- Pagination -->
      <div class="ag-page">
        <span class="ag-page__info">共 {{ total }} 条</span>
        <div class="ag-page__ctrls">
          <div class="ag-page__btns">
            <button class="ag-btn ag-btn--sm" :disabled="currentPage <= 1" @click="currentPage--; handlePageChange()">← 上一页</button>
            <span class="ag-page__current">{{ currentPage }} / {{ Math.max(1, Math.ceil(total / pageSize)) }}</span>
            <button class="ag-btn ag-btn--sm" :disabled="currentPage >= Math.max(1, Math.ceil(total / pageSize))" @click="currentPage++; handlePageChange()">下一页 →</button>
          </div>
        </div>
      </div>
    </section>

    <!-- ====== Modal: Module management ====== -->
    <div v-if="moduleDialogVisible" class="ag-modal" @click.self="moduleDialogVisible = false">
      <div class="ag-modal__box ag-modal__box--sm">
        <header class="ag-modal__head">
          <span class="ag-modal__kicker">VERSION / MODULES</span>
          <button class="ag-modal__close" @click="moduleDialogVisible = false">×</button>
        </header>
        <div class="ag-modal__body">
          <div v-if="modules.length === 0" class="ag-modal__empty">{{ $t('version.noModules') }}</div>
          <div v-for="mod in modules" :key="mod.id" class="ag-module-item">
            <span class="ag-module-name">{{ mod.name }}</span>
            <button class="ag-btn ag-btn--sm ag-btn--danger" @click="deleteModule(mod)" :disabled="mod._deleting">{{ $t('common.delete') }}</button>
          </div>
          <div class="ag-module-add">
            <input v-model="newModuleName" class="ag-input" :placeholder="$t('version.moduleNamePlaceholder')" @keyup.enter="addModule" />
            <button class="ag-btn ag-btn--ok" @click="addModule" :disabled="addingModule">{{ $t('version.addModule') }}</button>
          </div>
        </div>
        <footer class="ag-modal__foot">
          <button class="ag-btn ag-btn--ghost" @click="moduleDialogVisible = false">{{ $t('common.close') }}</button>
        </footer>
      </div>
    </div>

    <!-- ====== Modal: Create / Edit version ====== -->
    <div v-if="versionDialogVisible" class="ag-modal">
      <div class="ag-modal__box">
        <header class="ag-modal__head">
          <span class="ag-modal__kicker">{{ isEdit ? 'VERSION / EDIT' : 'VERSION / CREATE' }}</span>
          <button class="ag-modal__close" @click="versionDialogVisible = false">×</button>
        </header>
        <div class="ag-modal__body">
          <el-form ref="versionFormRef" :model="versionForm" :rules="versionRules" label-width="0">
            <div class="ag-form__group">
              <label>{{ $t('version.versionName') }} *</label>
              <el-form-item prop="name" class="ag-form__item">
                <el-input v-model="versionForm.name" :placeholder="$t('version.versionNamePlaceholder')" />
              </el-form-item>
            </div>
            <div class="ag-form__group">
              <label>{{ $t('version.relatedProject') }} *</label>
              <el-form-item prop="project_ids" class="ag-form__item">
                <el-select v-model="versionForm.project_ids" :placeholder="$t('version.selectProjects')" multiple popper-class="ag-dropdown" style="width: 100%">
                  <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
                </el-select>
              </el-form-item>
            </div>
            <div class="ag-form__group">
              <label>{{ $t('version.versionDescription') }}</label>
              <el-form-item prop="description" class="ag-form__item">
                <el-input v-model="versionForm.description" type="textarea" :rows="3" :placeholder="$t('version.versionDescriptionPlaceholder')" />
              </el-form-item>
            </div>
            <div class="ag-form__group">
              <label class="ag-check">
                <input type="checkbox" v-model="versionForm.is_baseline" />
                <span>{{ $t('version.setAsBaseline') }}</span>
              </label>
            </div>
          </el-form>
        </div>
        <footer class="ag-modal__foot">
          <button class="ag-btn ag-btn--ghost" @click="versionDialogVisible = false">{{ $t('common.cancel') }}</button>
          <button class="ag-btn ag-btn--ok" @click="saveVersion" :disabled="saving">{{ saving ? '处理中…' : $t('common.save') }}</button>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import dayjs from 'dayjs'

const { t } = useI18n()
const loading = ref(false)
const versions = ref([])
const projects = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchText = ref('')
const projectFilter = ref('')
const baselineFilter = ref('')
const selectedVersions = ref([])
const isDeleting = ref(false)

const versionDialogVisible = ref(false)
const versionFormRef = ref()
const saving = ref(false)
const isEdit = ref(false)
const editingVersionId = ref(null)

const versionForm = reactive({
  name: '',
  description: '',
  project_ids: [],
  is_baseline: false
})

const versionRules = {
  name: [{ required: true, message: computed(() => t('version.versionNameRequired')), trigger: 'blur' }],
  project_ids: [{ required: true, message: computed(() => t('version.projectRequired')), trigger: 'change' }]
}

const fetchVersions = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      search: searchText.value,
      projects: projectFilter.value,
      is_baseline: baselineFilter.value
    }
    const response = await api.get('/versions/', { params })
    versions.value = response.data.results || []
    total.value = response.data.count || 0
  } catch (error) {
    ElMessage.error(t('version.fetchListFailed'))
  } finally {
    loading.value = false
  }
}

const fetchProjects = async () => {
  try {
    const response = await api.get('/projects/')
    projects.value = response.data.results || response.data || []
  } catch (error) {
    ElMessage.error(t('version.fetchProjectsFailed'))
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchVersions()
}

const handleFilter = () => {
  currentPage.value = 1
  fetchVersions()
}

const handlePageChange = () => {
  fetchVersions()
}

const createVersion = () => {
  isEdit.value = false
  resetVersionForm()
  versionDialogVisible.value = true
}

const editVersion = (version) => {
  isEdit.value = true
  editingVersionId.value = version.id

  versionForm.name = version.name
  versionForm.description = version.description
  versionForm.project_ids = version.projects.map(p => p.id)
  versionForm.is_baseline = version.is_baseline

  versionDialogVisible.value = true
}

const saveVersion = async () => {
  if (!versionFormRef.value) return

  try {
    await versionFormRef.value.validate()
    saving.value = true

    if (isEdit.value) {
      await api.put(`/versions/${editingVersionId.value}/`, versionForm)
      ElMessage.success(t('version.updateSuccess'))
    } else {
      await api.post('/versions/', versionForm)
      ElMessage.success(t('version.createSuccess'))
    }

    versionDialogVisible.value = false
    fetchVersions()

  } catch (error) {
    if (error.response?.data) {
      const errors = Object.values(error.response.data).flat()
      ElMessage.error(errors[0] || t('version.saveFailed'))
    } else {
      ElMessage.error(t('version.saveFailed'))
    }
  } finally {
    saving.value = false
  }
}

const deleteVersion = async (version) => {
  try {
    await ElMessageBox.confirm(t('version.deleteConfirm'), t('common.warning'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    })

    await api.delete(`/versions/${version.id}/`)
    ElMessage.success(t('version.deleteSuccess'))
    fetchVersions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('version.deleteFailed'))
    }
  }
}

// 处理选择变化（保留兼容）
const handleSelectionChange = (selection) => {
  selectedVersions.value = selection
}

// ===== 行选择 =====
const isRowSelected = (row) => selectedVersions.value.some(s => s.id === row.id)
const toggleRow = (row) => {
  const idx = selectedVersions.value.findIndex(s => s.id === row.id)
  if (idx >= 0) selectedVersions.value.splice(idx, 1)
  else selectedVersions.value.push(row)
}
const pageAllSelected = computed(() => versions.value.length > 0 && versions.value.every(r => isRowSelected(r)))
const togglePageAll = () => {
  const pageIds = new Set(versions.value.map(r => r.id))
  if (pageAllSelected.value) {
    selectedVersions.value = selectedVersions.value.filter(s => !pageIds.has(s.id))
  } else {
    const selectedIds = new Set(selectedVersions.value.map(s => s.id))
    for (const r of versions.value) {
      if (!selectedIds.has(r.id)) selectedVersions.value.push(r)
    }
  }
}

// 获取序号
const getSerialNumber = (index) => {
  return (currentPage.value - 1) * pageSize.value + index + 1
}

// 批量删除
const batchDeleteVersions = async () => {
  if (selectedVersions.value.length === 0) {
    ElMessage.warning(t('version.selectVersionsFirst'))
    return
  }

  try {
    await ElMessageBox.confirm(
      t('version.batchDeleteConfirm', { count: selectedVersions.value.length }),
      t('common.warning'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning'
      }
    )

    isDeleting.value = true
    let successCount = 0
    let failCount = 0

    // 逐个删除选中的版本
    for (const version of selectedVersions.value) {
      try {
        await api.delete(`/versions/${version.id}/`)
        successCount++
      } catch (error) {
        console.error(`删除版本 ${version.id} 失败:`, error)
        failCount++
      }
    }

    // 显示删除结果
    if (successCount > 0) {
      ElMessage.success(t('version.batchDeleteSuccess', { successCount }) + (failCount > 0 ? `，${failCount} ${t('common.error')}` : ''))
    } else {
      ElMessage.error(t('version.batchDeleteFailed'))
    }

    // 清空选择并重新加载列表
    selectedVersions.value = []
    fetchVersions()

  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
      ElMessage.error(t('version.batchDeleteFailed') + ': ' + (error.message || t('common.error')))
    }
  } finally {
    isDeleting.value = false
  }
}

const resetVersionForm = () => {
  versionForm.name = ''
  versionForm.description = ''
  versionForm.project_ids = []
  versionForm.is_baseline = false
  editingVersionId.value = null
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

const getProjectsTooltip = (projects) => {
  return projects.map(p => p.name).join('、')
}

// 模块管理
const moduleDialogVisible = ref(false)
const currentVersion = ref(null)
const modules = ref([])
const newModuleName = ref('')
const addingModule = ref(false)

const openModuleDialog = async (version) => {
  currentVersion.value = version
  moduleDialogVisible.value = true
  await fetchModules()
}

const fetchModules = async () => {
  try {
    const response = await api.get(`/versions/${currentVersion.value.id}/modules/`)
    modules.value = (response.data.results || response.data || []).map(m => ({ ...m, _deleting: false }))
  } catch (error) {
    ElMessage.error(t('version.fetchModulesFailed'))
  }
}

const addModule = async () => {
  const name = newModuleName.value.trim()
  if (!name) { ElMessage.warning(t('version.moduleNameRequired')); return }
  addingModule.value = true
  try {
    await api.post(`/versions/${currentVersion.value.id}/modules/`, { name })
    ElMessage.success(t('version.addModuleSuccess'))
    newModuleName.value = ''
    await fetchModules()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || t('version.addModuleFailed'))
  } finally {
    addingModule.value = false
  }
}

const deleteModule = async (mod) => {
  try {
    mod._deleting = true
    await api.delete(`/versions/modules/${mod.id}/`)
    ElMessage.success(t('version.deleteModuleSuccess'))
    await fetchModules()
  } catch (error) {
    ElMessage.error(t('version.deleteModuleFailed'))
    mod._deleting = false
  }
}

onMounted(() => {
  fetchProjects()
  fetchVersions()
})
</script>

<style lang="scss" scoped>
/* =============================================
   Ark Moderate — Version Index
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

  &--head { flex-shrink: 0; margin-bottom: 16px; }
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
  display: flex; align-items: flex-end; gap: 16px; padding: 16px 20px;
  border-bottom: 1px solid var(--ark-border); flex-wrap: wrap;
  &__field {
    display: flex; flex-direction: column; gap: 6px;
    &--search { flex: 1; min-width: 220px; max-width: 320px; }
  }
  &__label {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .12em; color: #999;
  }
}

/* ============================================
   Input / Select
   ============================================ */
.ag-input {
  padding: 8px 12px; border: 1px solid #ccc; font-size: 13px; color: #333;
  width: 100%; box-sizing: border-box; font-family: inherit;
  &:focus { outline: none; border-color: #fffa00; }
  &:focus-visible { outline: 2px solid #fffa00; outline-offset: 1px; }
}
.ag-select {
  height: 36px; padding: 0 28px 0 10px; box-sizing: border-box; line-height: 1;
  border: 1px solid #ccc; background: #fff;
  font-size: 13px; font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .04em; color: #444;
  cursor: pointer; appearance: none; min-width: 160px;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%23999'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 10px center;
  &:focus { outline: none; border-color: #fffa00; }
  &:focus-visible { outline: 2px solid #fffa00; outline-offset: 1px; }
}

/* ============================================
   Table
   ============================================ */
.ag-table-wrap { flex: 1; overflow: visible; }
.ag-table {
  width: 100%; min-width: 1200px; border-collapse: collapse; font-size: 13px;
  thead { border-bottom: 2px solid var(--ark-ink); }
  th, td { padding: 10px 12px; text-align: left; vertical-align: middle; }
}
.ag-th {
  font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em; color: #999; font-weight: 600;
  &--sel { width: 44px; text-align: center; }
  &--idx { width: 56px; text-align: center; }
  &--name { min-width: 180px; }
  &--proj { min-width: 200px; }
  &--desc { min-width: 220px; }
  &--count { width: 90px; text-align: center; }
  &--creator { width: 110px; }
  &--time { width: 150px; }
  &--act { width: 220px; }
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
  &--name { font-weight: 600; }
  &--proj { color: #666; }
  &--desc { color: #666; }
  &--count { text-align: center; }
  &--creator { color: #666; }
  &--time { color: #888; font-size: 12px; white-space: nowrap; }
  &--act { white-space: nowrap; }
}
.ag-clamp {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; white-space: pre-wrap; line-height: 1.6;
  word-break: break-word; max-width: 320px;
}
.ag-actions { display: flex; gap: 4px; flex-wrap: nowrap; }
.ag-muted { color: #ccc; }
input[type="checkbox"] {
  width: 15px; height: 15px; margin: 0; cursor: pointer; accent-color: var(--ark-ink);
}

/* ============================================
   Version cell / badges
   ============================================ */
.ag-version-name {
  display: inline-flex; align-items: center; gap: 8px;
}
.ag-badge {
  display: inline-block; padding: 3px 10px; font-size: 10px;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em; font-weight: 600; border: 1px solid;
  &--baseline { color: #7d6a16; background: #fdf7e4; border-color: #e0d29a; }
}
.ag-project-tags {
  display: flex; flex-wrap: wrap; gap: 4px;
}
.ag-tag {
  display: inline-block; padding: 2px 10px; font-size: 11px;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .04em;
  color: #555; background: #fafaf8; border: 1px solid var(--ark-border);
  &--more { cursor: help; color: #777; }
}
.ag-count {
  display: inline-block; min-width: 34px; padding: 2px 8px; text-align: center;
  font-family: "Space Grotesk", system-ui, sans-serif; font-size: 12px; font-weight: 700;
  color: var(--ark-ink); background: #f4f5f3; border: 1px solid var(--ark-border);
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
    background: #fff; width: 90%; max-width: 640px; max-height: 84vh;
    display: flex; flex-direction: column; border: 1px solid #888;
    &--sm { max-width: 520px; }
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
  &__empty { text-align: center; color: #999; padding: 24px 0; font-size: 13px; }
}

/* Module management */
.ag-module-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; border-bottom: 1px solid #eee;
  &:last-of-type { border-bottom: none; }
}
.ag-module-name { font-size: 14px; color: #333; }
.ag-module-add {
  display: flex; gap: 8px; margin-top: 16px;
  .ag-input { flex: 1; min-height: 36px; }
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
  &__item { margin-bottom: 0; }
  :deep(.el-input__wrapper), :deep(.el-textarea__inner) {
    border-radius: 0; box-shadow: 0 0 0 1px #c9cbc8 inset; background: #fff;
    font-family: inherit;
  }
  :deep(.el-input__wrapper.is-focus), :deep(.el-textarea__inner:focus) {
    box-shadow: 0 0 0 1px var(--ark-signal) inset;
  }
  :deep(.el-input__inner) { font-family: inherit; }
  :deep(.el-textarea__inner) { font-size: 13px; line-height: 1.7; }
}

/* Native baseline checkbox */
.ag-check {
  display: inline-flex; align-items: center; gap: 8px; cursor: pointer;
  font-size: 13px; color: #444; text-transform: none; letter-spacing: 0;
  input { accent-color: var(--ark-ink); width: 15px; height: 15px; margin: 0; }
}

/* ============================================
   Motion
   ============================================ */
@keyframes ag-enter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}

@media (prefers-reduced-motion: reduce) {
  .ag-zone, .ag-btn, .ag-select, .ag-input, .ag-tr, .ag-modal__close, .ag-loading-bar {
    transition: none !important; animation: none !important;
  }
  .ag-btn:active:not(:disabled) { transform: none; }
}

/* ============================================
   Responsive
   ============================================ */
@media (max-width: 1024px) {
  .ag-shell { padding: 16px 16px 0; }
  .ag-table { min-width: 1080px; }
}
@media (max-width: 768px) {
  .ag-shell { padding: 12px 12px 0; }
  .ag-head { flex-direction: column; align-items: flex-start; }
  .ag-head__actions { width: 100%; justify-content: flex-start; }
  .ag-head__actions .ag-btn { flex: 1; }
  .ag-filter { flex-direction: column; align-items: stretch; }
  .ag-filter__field--search { max-width: none; }
  .ag-select { min-width: 0; }
  .ag-page { flex-direction: column; align-items: flex-start; }
  .ag-page__ctrls { flex-direction: column; align-items: flex-start; width: 100%; }
  .ag-modal__box { width: 95%; }
  .ag-module-add { flex-wrap: wrap; }
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
