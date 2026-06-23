<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">{{ $t('version.title') }}</h1>
      <div class="header-actions">
        <el-button
          v-if="selectedVersions.length > 0"
          type="danger"
          @click="batchDeleteVersions"
          :disabled="isDeleting">
          <el-icon><Delete /></el-icon>
          {{ $t('version.batchDelete') }} ({{ selectedVersions.length }})
        </el-button>
        <el-button type="primary" @click="createVersion">
          <el-icon><Plus /></el-icon>
          {{ $t('version.newVersion') }}
        </el-button>
      </div>
    </div>

    <div class="card-container">
      <div class="filter-bar">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-input
              v-model="searchText"
              :placeholder="$t('version.searchPlaceholder')"
              clearable
              @input="handleSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </el-col>
          <el-col :span="4">
            <el-select v-model="projectFilter" :placeholder="$t('version.relatedProject')" clearable @change="handleFilter">
              <el-option
                v-for="project in projects"
                :key="project.id"
                :label="project.name"
                :value="project.id"
              />
            </el-select>
          </el-col>
          <el-col :span="3">
            <el-select v-model="baselineFilter" :placeholder="$t('version.versionType')" clearable @change="handleFilter">
              <el-option :label="$t('version.baselineVersion')" :value="true" />
              <el-option :label="$t('version.normalVersion')" :value="false" />
            </el-select>
          </el-col>
        </el-row>
      </div>
      
      <el-table
        :data="versions"
        v-loading="loading"
        style="width: 100%"
        @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55" />
        <el-table-column type="index" :label="$t('version.serialNumber')" width="80" :index="getSerialNumber" />
        <el-table-column prop="name" :label="$t('version.versionName')" min-width="100">
          <template #default="{ row }">
            <div class="version-name">
              <span>{{ row.name }}</span>
              <el-tag v-if="row.is_baseline" type="warning" size="small" class="baseline-tag">{{ $t('version.baseline') }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="projects" :label="$t('version.relatedProject')" width="300">
          <template #default="{ row }">
            <div v-if="row.projects && row.projects.length > 0" class="project-tags">
              <el-tag
                v-for="project in row.projects.slice(0, 2)"
                :key="project.id"
                size="small"
                type="primary"
                class="project-tag"
              >
                {{ project.name }}
              </el-tag>
              <el-tooltip v-if="row.projects.length > 2" :content="getProjectsTooltip(row.projects)">
                <el-tag size="small" type="info" class="project-tag">
                  +{{ row.projects.length - 2 }}
                </el-tag>
              </el-tooltip>
            </div>
            <span v-else class="no-project">{{ $t('version.noProject') }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" :label="$t('version.description')" min-width="200" show-overflow-tooltip />
        <el-table-column prop="testcases_count" :label="$t('version.testCaseCount')" width="100">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.testcases_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by.username" :label="$t('version.creator')" width="120" />
        <el-table-column prop="created_at" :label="$t('version.createdAt')" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('project.actions')" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openModuleDialog(row)">📦 {{ $t('version.modules') }}</el-button>
            <el-button size="small" @click="editVersion(row)">{{ $t('common.edit') }}</el-button>
            <el-button size="small" type="danger" @click="deleteVersion(row)">{{ $t('common.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </div>
    
    <!-- 模块管理对话框 -->
    <el-dialog
      v-model="moduleDialogVisible"
      :title="$t('version.moduleManagement') + ' - ' + currentVersion?.name"
      width="550px"
      :close-on-click-modal="false">
      <div class="module-list">
        <div v-if="modules.length === 0" class="empty-hint">{{ $t('version.noModules') }}</div>
        <div v-for="mod in modules" :key="mod.id" class="module-item">
          <span class="module-name">{{ mod.name }}</span>
          <el-button size="small" type="danger" @click="deleteModule(mod)" :loading="mod._deleting">{{ $t('common.delete') }}</el-button>
        </div>
      </div>
      <div class="add-module-form" style="margin-top: 16px; display: flex; gap: 8px;">
        <el-input v-model="newModuleName" :placeholder="$t('version.moduleNamePlaceholder')" style="flex: 1;" @keyup.enter="addModule" />
        <el-button type="primary" @click="addModule" :loading="addingModule">{{ $t('version.addModule') }}</el-button>
      </div>
      <template #footer>
        <el-button @click="moduleDialogVisible = false">{{ $t('common.close') }}</el-button>
      </template>
    </el-dialog>

    <!-- 版本表单对话框 -->
    <el-dialog
      v-model="versionDialogVisible"
      :title="isEdit ? $t('version.editVersion') : $t('version.newVersion')"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="versionForm" :rules="versionRules" ref="versionFormRef" label-width="120px">
        <el-form-item :label="$t('version.versionName')" prop="name">
          <el-input v-model="versionForm.name" :placeholder="$t('version.versionNamePlaceholder')" />
        </el-form-item>

        <el-form-item :label="$t('version.relatedProject')" prop="project_ids">
          <el-select
            v-model="versionForm.project_ids"
            :placeholder="$t('version.selectProjects')"
            multiple
            style="width: 100%"
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item :label="$t('version.versionDescription')">
          <el-input
            v-model="versionForm.description"
            type="textarea"
            :rows="3"
            :placeholder="$t('version.versionDescriptionPlaceholder')"
          />
        </el-form-item>

        <el-form-item>
          <el-checkbox v-model="versionForm.is_baseline">{{ $t('version.setAsBaseline') }}</el-checkbox>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="versionDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="saveVersion" :loading="saving">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Delete } from '@element-plus/icons-vue'
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

// 处理选择变化
const handleSelectionChange = (selection) => {
  selectedVersions.value = selection
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
.filter-bar {
  margin-bottom: 20px;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.version-name {
  display: flex;
  align-items: center;
  gap: 8px;
  
  .baseline-tag {
    font-size: 12px;
  }
}

.project-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  
  .project-tag {
    margin: 0;
  }
}

.no-project {
  color: #909399;
  font-size: 12px;
  font-style: italic;
}

.module-list {
  max-height: 300px;
  overflow-y: auto;
}
.empty-hint {
  text-align: center;
  color: #909399;
  padding: 20px;
}
.module-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
}
.module-name {
  font-size: 14px;
}
</style>