<template>
  <div class="environment-management">
    <div class="header">
      <h3>{{ $t('apiTesting.environment.title') }}</h3>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        {{ $t('apiTesting.environment.createEnvironment') }}
      </el-button>
    </div>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane :label="$t('apiTesting.environment.scopeTypes.global')" name="GLOBAL">
        <EnvironmentTable
          :data="globalEnvironments"
          :loading="loading"
          scope="GLOBAL"
          @edit="editEnvironment"
          @delete="deleteEnvironment"
          @activate="activateEnvironment"
          @duplicate="duplicateEnvironment"
        />
      </el-tab-pane>
      <el-tab-pane :label="$t('apiTesting.environment.scopeTypes.local')" name="LOCAL">
        <div class="local-env-header">
          <el-select
            v-model="selectedProject"
            popper-class="automation-popper"
            :placeholder="$t('apiTesting.common.selectProject')"
            @change="loadLocalEnvironments"
            style="width: 200px;"
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </div>
        <EnvironmentTable
          :data="localEnvironments"
          :loading="loading"
          scope="LOCAL"
          @edit="editEnvironment"
          @delete="deleteEnvironment"
          @activate="activateEnvironment"
          @duplicate="duplicateEnvironment"
        />
      </el-tab-pane>
    </el-tabs>

    <!-- 创建/编辑环境对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      class="automation-dialog"
      modal-class="automation-modal"
      :title="editingEnvironment ? $t('apiTesting.environment.editEnvironment') : $t('apiTesting.environment.createEnvironment')"
      width="800px"
      :close-on-click-modal="false"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
      >
        <el-form-item :label="$t('apiTesting.environment.environmentName')" prop="name">
          <el-input v-model="form.name" :placeholder="$t('apiTesting.environment.inputEnvironmentName')" />
        </el-form-item>

        <el-form-item :label="$t('apiTesting.environment.scope')" prop="scope">
          <el-radio-group v-model="form.scope" @change="onScopeChange">
            <el-radio value="GLOBAL">{{ $t('apiTesting.environment.scopeTypes.global') }}</el-radio>
            <el-radio value="LOCAL">{{ $t('apiTesting.environment.scopeTypes.local') }}</el-radio>
          </el-radio-group>
          <div class="scope-help">
            <el-text size="small" type="info">
              {{ $t('apiTesting.environment.scopeHelp') }}
            </el-text>
          </div>
        </el-form-item>

        <el-form-item
          v-if="form.scope === 'LOCAL'"
          :label="$t('apiTesting.environment.relatedProject')"
          prop="project"
        >
          <el-select v-model="form.project" popper-class="automation-popper" :placeholder="$t('apiTesting.environment.selectRelatedProject')">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item :label="$t('apiTesting.environment.baseURL')">
          <el-input v-model="form.base_url" placeholder="http://dev.example.com:8080" />
          <div class="field-help">
            <el-text size="small" type="info">{{ $t('apiTesting.environment.baseURLHelp') }}</el-text>
          </div>
        </el-form-item>

        <el-collapse style="width: 100%">
          <el-collapse-item :title="$t('apiTesting.environment.defaultHeaders')">
            <KeyValueEditor
              v-model="form.default_headers"
              :placeholder-key="$t('apiTesting.component.keyValueEditor.key')"
              :placeholder-value="$t('apiTesting.component.keyValueEditor.value')"
            />
          </el-collapse-item>
          <el-collapse-item :title="$t('apiTesting.environment.defaultParams')">
            <KeyValueEditor
              v-model="form.default_params"
              :placeholder-key="$t('apiTesting.component.keyValueEditor.key')"
              :placeholder-value="$t('apiTesting.component.keyValueEditor.value')"
            />
          </el-collapse-item>
        </el-collapse>

        <el-form-item :label="$t('apiTesting.environment.environmentVariables')" prop="variables">
          <div class="variables-editor">
            <div class="variables-header">
              <div class="column">{{ $t('apiTesting.environment.variableName') }}</div>
              <div class="column">{{ $t('apiTesting.environment.initialValue') }}</div>
              <div class="column">{{ $t('apiTesting.environment.currentValue') }}</div>
              <div class="column">{{ $t('apiTesting.common.operation') }}</div>
            </div>

            <div class="variables-body">
              <div
                v-for="(variable, index) in form.variables"
                :key="index"
                class="variable-row"
              >
                <div class="column">
                  <el-input
                    v-model="variable.key"
                    :placeholder="$t('apiTesting.environment.variableName')"
                    size="small"
                  />
                </div>
                <div class="column">
                  <el-input
                    v-model="variable.initialValue"
                    :placeholder="$t('apiTesting.environment.initialValue')"
                    size="small"
                  />
                </div>
                <div class="column">
                  <el-input
                    v-model="variable.currentValue"
                    :placeholder="$t('apiTesting.environment.currentValue')"
                    size="small"
                  />
                </div>
                <div class="column">
                  <el-button
                    size="small"
                    type="danger"
                    :icon="Delete"
                    @click="removeVariable(index)"
                    :disabled="form.variables.length <= 1"
                  />
                </div>
              </div>
            </div>

            <div class="variables-footer">
              <el-button size="small" @click="addVariable">
                <el-icon><Plus /></el-icon>
                {{ $t('apiTesting.environment.addVariable') }}
              </el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">{{ $t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          {{ editingEnvironment ? $t('apiTesting.common.update') : $t('apiTesting.common.create') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 查看变量对话框 -->
    <el-dialog
      v-model="showViewDialog"
      class="automation-dialog"
      modal-class="automation-modal"
      :title="$t('apiTesting.environment.environmentVariableDetail')"
      width="600px"
    >
      <div v-if="viewingEnvironment" class="view-variables">
        <el-table :data="viewVariables" style="width: 100%">
          <el-table-column prop="key" :label="$t('apiTesting.environment.variableName')" width="150" />
          <el-table-column prop="initialValue" :label="$t('apiTesting.environment.initialValue')" />
          <el-table-column prop="currentValue" :label="$t('apiTesting.environment.currentValue')" />
        </el-table>
      </div>

      <template #footer>
        <el-button @click="showViewDialog = false">{{ $t('apiTesting.common.close') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Plus, Delete } from '@element-plus/icons-vue'
import api from '@/utils/api'
import EnvironmentTable from './components/EnvironmentTable.vue'
import KeyValueEditor from './components/KeyValueEditor.vue'

const { t } = useI18n()
const activeTab = ref('GLOBAL')
const globalEnvironments = ref([])
const localEnvironments = ref([])
const projects = ref([])
const selectedProject = ref(null)
const loading = ref(false)
const showCreateDialog = ref(false)
const showViewDialog = ref(false)
const editingEnvironment = ref(null)
const viewingEnvironment = ref(null)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  name: '',
  scope: 'GLOBAL',
  base_url: '',
  project: null,
  default_headers: [],
  default_params: [],
  variables: [
    {
      key: '',
      initialValue: '',
      currentValue: ''
    }
  ]
})

const rules = computed(() => ({
  name: [
    { required: true, message: t('apiTesting.environment.inputEnvironmentName'), trigger: 'blur' }
  ],
  scope: [
    { required: true, message: t('apiTesting.common.pleaseSelect'), trigger: 'change' }
  ],
  project: [
    {
      validator: (rule, value, callback) => {
        if (form.scope === 'LOCAL' && !value) {
          callback(new Error(t('apiTesting.environment.selectRelatedProject')))
        } else {
          callback()
        }
      },
      trigger: 'change'
    }
  ]
}))

const viewVariables = computed(() => {
  if (!viewingEnvironment.value?.variables) return []
  
  const vars = viewingEnvironment.value.variables
  return Object.keys(vars).map(key => ({
    key,
    initialValue: vars[key]?.initialValue || vars[key] || '',
    currentValue: vars[key]?.currentValue || vars[key] || ''
  }))
})

const loadProjects = async () => {
  try {
    const response = await api.get('/api-testing/projects/')
    projects.value = response.data.results || response.data
    if (projects.value.length > 0 && !selectedProject.value) {
      selectedProject.value = projects.value[0].id
    }
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.projectListLoadFailed'))
  }
}

const loadGlobalEnvironments = async () => {
  loading.value = true
  try {
    const response = await api.get('/api-testing/environments/', {
      params: { scope: 'GLOBAL' }
    })
    globalEnvironments.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.globalEnvLoadFailed'))
  } finally {
    loading.value = false
  }
}

const loadLocalEnvironments = async () => {
  if (!selectedProject.value) return

  loading.value = true
  try {
    const response = await api.get('/api-testing/environments/', {
      params: {
        scope: 'LOCAL',
        project: selectedProject.value
      }
    })
    localEnvironments.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.localEnvLoadFailed'))
  } finally {
    loading.value = false
  }
}

const onTabChange = (tab) => {
  if (tab === 'GLOBAL') {
    loadGlobalEnvironments()
  } else {
    loadLocalEnvironments()
  }
}

const onScopeChange = () => {
  if (form.scope === 'GLOBAL') {
    form.project = null
  }
}

const addVariable = () => {
  form.variables.push({
    key: '',
    initialValue: '',
    currentValue: ''
  })
}

const removeVariable = (index) => {
  if (form.variables.length > 1) {
    form.variables.splice(index, 1)
  }
}

const objectToKvArray = (obj) => {
  if (!obj || typeof obj !== 'object') return []
  if (Array.isArray(obj)) return obj
  return Object.entries(obj).map(([k, v]) => ({
    key: k, value: String(v), description: '', enabled: true, type: 'text'
  }))
}

const kvArrayToObject = (arr) => {
  const result = {}
  for (const item of arr || []) {
    if (item.enabled !== false && item.key) result[item.key] = item.value || ''
  }
  return result
}

const editEnvironment = (environment) => {
  editingEnvironment.value = environment
  form.name = environment.name
  form.scope = environment.scope
  form.base_url = environment.base_url || ''
  form.project = environment.project
  form.default_headers = objectToKvArray(environment.default_headers)
  form.default_params = objectToKvArray(environment.default_params)

  // 转换变量格式
  const variables = environment.variables || {}
  form.variables = Object.keys(variables).map(key => {
    const value = variables[key]
    if (typeof value === 'object') {
      return {
        key,
        initialValue: value.initialValue || '',
        currentValue: value.currentValue || ''
      }
    } else {
      return {
        key,
        initialValue: value || '',
        currentValue: value || ''
      }
    }
  })

  if (form.variables.length === 0) {
    form.variables.push({
      key: '',
      initialValue: '',
      currentValue: ''
    })
  }

  showCreateDialog.value = true
}

const deleteEnvironment = async (environment) => {
  try {
    await ElMessageBox.confirm(
      t('apiTesting.environment.confirmDeleteEnv', { name: environment.name }),
      t('apiTesting.messages.confirm.deleteTitle'),
      {
        confirmButtonText: t('apiTesting.common.confirm'),
        cancelButtonText: t('apiTesting.common.cancel'),
        type: 'warning',
        customClass: 'automation-messagebox'
      }
    )

    await api.delete(`/api-testing/environments/${environment.id}/`)
    ElMessage.success(t('apiTesting.messages.success.delete'))

    if (activeTab.value === 'GLOBAL') {
      await loadGlobalEnvironments()
    } else {
      await loadLocalEnvironments()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('apiTesting.messages.error.deleteFailed'))
    }
  }
}

const activateEnvironment = async (environment) => {
  try {
    await api.post(`/api-testing/environments/${environment.id}/activate/`)
    ElMessage.success(t('apiTesting.messages.success.environmentActivated'))

    if (activeTab.value === 'GLOBAL') {
      await loadGlobalEnvironments()
    } else {
      await loadLocalEnvironments()
    }
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.activateFailed'))
  }
}

const duplicateEnvironment = async (environment) => {
  const newEnv = {
    name: `${environment.name} - Copy`,
    scope: environment.scope,
    base_url: environment.base_url || '',
    project: environment.scope === 'LOCAL' ?
      (typeof environment.project === 'object' ? environment.project.id : environment.project) :
      null,
    default_headers: environment.default_headers || {},
    default_params: environment.default_params || {},
    variables: environment.variables || {}
  }

  try {
    await api.post('/api-testing/environments/', newEnv)
    ElMessage.success(t('apiTesting.messages.success.copy'))

    if (activeTab.value === 'GLOBAL') {
      await loadGlobalEnvironments()
    } else {
      await loadLocalEnvironments()
    }
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.copyFailed'))
  }
}

const submitForm = async () => {
  if (!formRef.value) return
  
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  
  submitting.value = true
  try {
    // 转换变量格式
    const variables = {}
    form.variables.forEach(variable => {
      if (variable.key) {
        variables[variable.key] = {
          initialValue: variable.initialValue || '',
          currentValue: variable.currentValue || variable.initialValue || ''
        }
      }
    })
    
    const data = {
      name: form.name,
      scope: form.scope,
      base_url: form.base_url || '',
      project: form.scope === 'LOCAL' ? form.project : null,
      default_headers: kvArrayToObject(form.default_headers),
      default_params: kvArrayToObject(form.default_params),
      variables
    }
    
    if (editingEnvironment.value) {
      await api.put(`/api-testing/environments/${editingEnvironment.value.id}/`, data)
      ElMessage.success(t('apiTesting.messages.success.environmentUpdated'))
    } else {
      await api.post('/api-testing/environments/', data)
      ElMessage.success(t('apiTesting.messages.success.environmentCreated'))
    }

    showCreateDialog.value = false

    if (activeTab.value === 'GLOBAL') {
      await loadGlobalEnvironments()
    } else {
      await loadLocalEnvironments()
    }
  } catch (error) {
    ElMessage.error(editingEnvironment.value ? t('apiTesting.messages.error.updateFailed') : t('apiTesting.messages.error.createFailed'))
  } finally {
    submitting.value = false
  }
}

const resetForm = () => {
  editingEnvironment.value = null
  Object.assign(form, {
    name: '',
    scope: 'GLOBAL',
    base_url: '',
    project: null,
    default_headers: [],
    default_params: [],
    variables: [
      {
        key: '',
        initialValue: '',
        currentValue: ''
      }
    ]
  })
  formRef.value?.resetFields()
}

onMounted(async () => {
  await loadProjects()
  await loadGlobalEnvironments()
  if (selectedProject.value) {
    await loadLocalEnvironments()
  }
})
</script>

<style scoped>
.environment-management {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f2f2f0;
  color: #191919;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  --ef-ink: #191919;
  --ef-paper: #f2f2f0;
  --ef-signal: #fffa00;
  --ef-state: #00ffa2;
  --ef-muted: #8a8a86;
  --ef-line: #dcdcd7;
  --ef-line-strong: #c9c9c3;
  --ef-line-soft: #f0f0ec;
  --ef-rail: #fafaf8;
  --ef-surface: #ffffff;
  --ef-dock: #191919;
  --ef-font-tech: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  --ef-font-display: "Arial Narrow", "Roboto Condensed", "DIN Condensed", sans-serif;
  --ef-font-mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--ef-line);
}

.header h3 {
  margin: 0;
  color: var(--ef-ink);
  font-family: var(--ef-font-display);
  font-size: 22px;
  letter-spacing: .08em;
  text-transform: uppercase;
  position: relative;
  padding-bottom: 8px;
}

.header h3::after {
  content: "";
  position: absolute;
  left: 0;
  bottom: 0;
  width: 36px;
  height: 3px;
  background: var(--ef-signal);
}

.local-env-header {
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--ef-line);
}

.scope-help, .field-help {
  margin-top: 5px;
}

.variables-editor {
  border: 1px solid var(--ef-line);
  border-radius: 2px;
  background: var(--ef-rail);
}

.variables-header {
  display: flex;
  background: var(--ef-paper);
  border-bottom: 1px solid var(--ef-line);
  padding: 8px;
  font-weight: 600;
  font-size: 11px;
  font-family: var(--ef-font-tech);
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--ef-muted);
}

.variables-body {
  max-height: 300px;
  overflow-y: auto;
}

.variable-row {
  display: flex;
  border-bottom: 1px solid var(--ef-line-soft);
  padding: 8px;
  min-height: 40px;
  align-items: center;
}

.variable-row:hover {
  background: rgba(255, 250, 0, .06);
}

.column {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
}

.column:last-child {
  flex: 0 0 60px;
  justify-content: center;
}

.variables-footer {
  padding: 8px;
  border-top: 1px solid var(--ef-line);
  background: var(--ef-paper);
}

.view-variables {
  max-height: 400px;
  overflow-y: auto;
}

/* ---------- Element Plus unification ---------- */
.environment-management :deep(.el-button) { border-radius: 2px; }
.environment-management :deep(.el-button--primary) {
  background: var(--ef-ink);
  border-color: var(--ef-ink);
  color: #ffffff;
}
.environment-management :deep(.el-button--primary:hover) {
  background: #2c2c2c;
  border-color: var(--ef-signal);
  color: var(--ef-signal);
}
.environment-management :deep(.el-button--primary.is-plain) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.environment-management :deep(.el-button--primary.is-plain:hover) {
  background: rgba(255, 250, 0, .12);
  border-color: var(--ef-signal);
  color: var(--ef-ink);
}
.environment-management :deep(.el-button--danger) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.environment-management :deep(.el-button--danger:hover) {
  background: rgba(220, 38, 38, .08);
  border-color: #b91c1c;
  color: #b91c1c;
}
.environment-management :deep(.el-button--success) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.environment-management :deep(.el-button--success:hover) {
  background: rgba(22, 163, 74, .1);
  border-color: #15803d;
  color: #15803d;
}
.environment-management :deep(.el-button--warning) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.environment-management :deep(.el-button--warning:hover) {
  background: rgba(217, 119, 6, .1);
  border-color: #b45309;
  color: #b45309;
}
.environment-management :deep(.el-button--info) {
  background: transparent;
  border-color: var(--ef-line-strong);
  color: var(--ef-muted);
}
.environment-management :deep(.el-button--info:hover) {
  border-color: var(--ef-signal);
  color: var(--ef-ink);
}
.environment-management :deep(.el-button--primary.is-link) {
  background: transparent;
  border-color: transparent;
  color: var(--ef-ink);
  font-weight: 600;
}
.environment-management :deep(.el-button--primary.is-link:hover) {
  color: var(--ef-ink);
  background: rgba(255, 250, 0, .18);
  border-color: transparent;
}
.environment-management :deep(.el-button.is-text) {
  color: var(--ef-muted);
}
.environment-management :deep(.el-button.is-text:hover) {
  color: var(--ef-ink);
  background: rgba(255, 250, 0, .14);
}

.environment-management :deep(.el-input__wrapper),
.environment-management :deep(.el-textarea__inner),
.environment-management :deep(.el-select__wrapper) {
  background: var(--ef-surface);
  box-shadow: 0 0 0 1px var(--ef-line-strong) inset;
  border-radius: 2px;
}
.environment-management :deep(.el-input__wrapper.is-focus),
.environment-management :deep(.el-select__wrapper.is-focused),
.environment-management :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--ef-ink) inset;
}
.environment-management :deep(.el-input__inner) {
  color: var(--ef-ink);
  font-size: 13px;
}
.environment-management :deep(.el-textarea__inner) {
  font-family: var(--ef-font-mono);
  font-size: 12px;
  line-height: 1.6;
}

.environment-management :deep(.el-tag) {
  border-radius: 2px;
  font-family: var(--ef-font-tech);
  letter-spacing: .04em;
}
.environment-management :deep(.el-tag--primary) { background: rgba(25, 25, 25, .08); border-color: transparent; color: var(--ef-ink); }
.environment-management :deep(.el-tag--success) { background: rgba(22, 163, 74, .12); border-color: transparent; color: #15803d; }
.environment-management :deep(.el-tag--warning) { background: rgba(217, 119, 6, .12); border-color: transparent; color: #b45309; }
.environment-management :deep(.el-tag--danger) { background: rgba(220, 38, 38, .12); border-color: transparent; color: #b91c1c; }
.environment-management :deep(.el-tag--info) { background: rgba(25, 25, 25, .08); border-color: transparent; color: var(--ef-muted); }

.environment-management :deep(.el-table) {
  --el-table-border-color: var(--ef-line);
  --el-table-header-bg-color: var(--ef-paper);
  --el-table-header-text-color: var(--ef-ink);
  --el-table-row-hover-bg-color: rgba(255, 250, 0, .10);
  --el-table-text-color: var(--ef-ink);
  font-size: 12px;
}
.environment-management :deep(.el-table th.el-table__cell) { font-weight: 700; }

.environment-management :deep(.el-tabs__nav-wrap::after) { background: var(--ef-line); height: 1px; }
.environment-management :deep(.el-tabs__item) {
  font-family: var(--ef-font-tech);
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--ef-muted);
}
.environment-management :deep(.el-tabs__item.is-active) { color: var(--ef-ink); font-weight: 700; }
.environment-management :deep(.el-tabs__active-bar) { background: var(--ef-signal); height: 2px; }

.environment-management :deep(.el-radio__label) {
  font-family: var(--ef-font-tech);
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--ef-muted);
}
.environment-management :deep(.el-radio__input.is-checked .el-radio__inner) {
  background: var(--ef-ink);
  border-color: var(--ef-ink);
}
.environment-management :deep(.el-radio__input.is-checked + .el-radio__label) {
  color: var(--ef-ink);
  font-weight: 700;
}

.environment-management :deep(.el-collapse) {
  border-top: 1px solid var(--ef-line);
  border-bottom: 1px solid var(--ef-line);
}
.environment-management :deep(.el-collapse-item__header) {
  background: var(--ef-paper);
  border-bottom: 1px solid var(--ef-line);
  font-family: var(--ef-font-tech);
  font-size: 12px;
  letter-spacing: .04em;
  color: var(--ef-ink);
}
.environment-management :deep(.el-collapse-item__header.is-active) { color: var(--ef-ink); }
.environment-management :deep(.el-collapse-item__arrow) { color: var(--ef-muted); }
.environment-management :deep(.el-collapse-item__wrap) { border-bottom: 1px solid var(--ef-line); }

.environment-management :deep(.el-descriptions) {
  --el-descriptions-table-border: 1px solid var(--ef-line);
  --el-descriptions-table-bg-color: var(--ef-surface);
  --el-descriptions-cell-bg-color: var(--ef-rail);
  --el-descriptions-label-bg-color: var(--ef-paper);
  --el-descriptions-text-color: var(--ef-ink);
  --el-descriptions-label-text-color: var(--ef-muted);
}

.environment-management :deep(.el-button:focus-visible),
.environment-management :deep(.el-input__wrapper:focus-visible),
.environment-management :deep(.el-textarea__inner:focus-visible),
.environment-management :deep(.el-select__wrapper:focus-visible) {
  outline: 2px solid var(--ef-signal);
  outline-offset: 1px;
}
</style>

<style>
/* ============================================================
   Endfield / moderate - teleported surfaces
   ============================================================ */
.automation-modal {
  background: rgba(25, 25, 25, .5) !important;
  -webkit-backdrop-filter: blur(2px);
  backdrop-filter: blur(2px);
}
.automation-dialog {
  border-radius: 2px;
  border: 1px solid #c9c9c3;
  box-shadow: 12px 12px 0 rgba(25, 25, 25, .08);
  background: #fafaf8;
  color: #191919;
  overflow: hidden;
}
.automation-dialog .el-dialog__header {
  margin: 0;
  padding: 14px 18px;
  background: #191919;
  color: #ffffff;
  border-bottom: 2px solid #fffa00;
}
.automation-dialog .el-dialog__title {
  font-family: "Arial Narrow", "Roboto Condensed", "DIN Condensed", sans-serif;
  font-size: 16px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #ffffff;
}
.automation-dialog .el-dialog__headerbtn { top: 14px; }
.automation-dialog .el-dialog__headerbtn .el-dialog__close { color: rgba(255, 255, 255, .6); }
.automation-dialog .el-dialog__headerbtn:hover .el-dialog__close { color: #fffa00; }
.automation-dialog .el-dialog__body { padding: 16px 18px; }
.automation-dialog .el-dialog__footer {
  padding: 10px 18px 14px;
  border-top: 1px solid #dcdcd7;
  text-align: right;
}

.automation-dialog .el-form-item__label {
  font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #8a8a86;
}

.automation-dialog .el-input__wrapper,
.automation-dialog .el-textarea__inner,
.automation-dialog .el-select__wrapper {
  background: #ffffff;
  box-shadow: 0 0 0 1px #c9c9c3 inset;
  border-radius: 2px;
}
.automation-dialog .el-input__wrapper.is-focus,
.automation-dialog .el-select__wrapper.is-focused,
.automation-dialog .el-textarea__inner:focus {
  box-shadow: 0 0 0 1px #191919 inset;
}
.automation-dialog .el-textarea__inner {
  font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
}

.automation-dialog .el-button { border-radius: 2px; }
.automation-dialog .el-button--primary {
  background: #191919;
  border-color: #191919;
  color: #ffffff;
}
.automation-dialog .el-button--primary:hover {
  background: #2c2c2c;
  border-color: #fffa00;
  color: #fffa00;
}
.automation-dialog .el-button--primary.is-plain {
  background: transparent;
  border-color: #191919;
  color: #191919;
}
.automation-dialog .el-button--primary.is-plain:hover {
  background: rgba(255, 250, 0, .12);
  border-color: #fffa00;
  color: #191919;
}
.automation-dialog .el-button--danger {
  background: transparent;
  border-color: #191919;
  color: #191919;
}
.automation-dialog .el-button--danger:hover {
  background: rgba(220, 38, 38, .08);
  border-color: #b91c1c;
  color: #b91c1c;
}
.automation-dialog .el-button--success {
  background: transparent;
  border-color: #191919;
  color: #191919;
}
.automation-dialog .el-button--success:hover {
  background: rgba(22, 163, 74, .1);
  border-color: #15803d;
  color: #15803d;
}
.automation-dialog .el-button--warning {
  background: transparent;
  border-color: #191919;
  color: #191919;
}
.automation-dialog .el-button--warning:hover {
  background: rgba(217, 119, 6, .1);
  border-color: #b45309;
  color: #b45309;
}
.automation-dialog .el-button--info {
  background: transparent;
  border-color: #c9c9c3;
  color: #8a8a86;
}
.automation-dialog .el-button--info:hover {
  border-color: #fffa00;
  color: #191919;
}
.automation-dialog .el-button--primary.is-link {
  background: transparent;
  border-color: transparent;
  color: #191919;
  font-weight: 600;
}
.automation-dialog .el-button--primary.is-link:hover {
  color: #191919;
  background: rgba(255, 250, 0, .18);
  border-color: transparent;
}
.automation-dialog .el-button:focus-visible,
.automation-dialog .el-input__wrapper:focus-visible,
.automation-dialog .el-textarea__inner:focus-visible,
.automation-dialog .el-select__wrapper:focus-visible {
  outline: 2px solid #fffa00;
  outline-offset: 1px;
}

.automation-dialog .el-table {
  --el-table-border-color: #dcdcd7;
  --el-table-header-bg-color: #f2f2f0;
  --el-table-header-text-color: #191919;
  --el-table-row-hover-bg-color: rgba(255, 250, 0, .10);
  --el-table-text-color: #191919;
  font-size: 12px;
}
.automation-dialog .el-table th.el-table__cell { font-weight: 700; }

.automation-dialog .el-tag {
  border-radius: 2px;
  font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  letter-spacing: .04em;
}
.automation-dialog .el-tag--primary { background: rgba(25, 25, 25, .08); border-color: transparent; color: #191919; }
.automation-dialog .el-tag--success { background: rgba(22, 163, 74, .12); border-color: transparent; color: #15803d; }
.automation-dialog .el-tag--warning { background: rgba(217, 119, 6, .12); border-color: transparent; color: #b45309; }
.automation-dialog .el-tag--danger { background: rgba(220, 38, 38, .12); border-color: transparent; color: #b91c1c; }
.automation-dialog .el-tag--info { background: rgba(25, 25, 25, .08); border-color: transparent; color: #8a8a86; }

.automation-dialog .el-radio__label {
  font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #8a8a86;
}
.automation-dialog .el-radio__input.is-checked .el-radio__inner {
  background: #191919;
  border-color: #191919;
}
.automation-dialog .el-radio__input.is-checked + .el-radio__label {
  color: #191919;
  font-weight: 700;
}

.automation-dialog .el-collapse {
  border-top: 1px solid #dcdcd7;
  border-bottom: 1px solid #dcdcd7;
}
.automation-dialog .el-collapse-item__header {
  background: #f2f2f0;
  border-bottom: 1px solid #dcdcd7;
  font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  font-size: 12px;
  letter-spacing: .04em;
  color: #191919;
}
.automation-dialog .el-collapse-item__header.is-active { color: #191919; }
.automation-dialog .el-collapse-item__arrow { color: #8a8a86; }
.automation-dialog .el-collapse-item__wrap { border-bottom: 1px solid #dcdcd7; }

.automation-dialog .el-descriptions {
  --el-descriptions-table-border: 1px solid #dcdcd7;
  --el-descriptions-table-bg-color: #ffffff;
  --el-descriptions-cell-bg-color: #fafaf8;
  --el-descriptions-label-bg-color: #f2f2f0;
  --el-descriptions-text-color: #191919;
  --el-descriptions-label-text-color: #8a8a86;
}

.automation-popper {
  border-radius: 2px;
  border-color: #c9c9c3;
  box-shadow: 6px 6px 0 rgba(25, 25, 25, .06);
}
.automation-popper .el-select-dropdown__item.is-hovering {
  background: rgba(255, 250, 0, .14);
  color: #191919;
}
.automation-popper .el-select-dropdown__item.is-selected {
  color: #191919;
  font-weight: 700;
}
.automation-popper .el-picker-panel { border-radius: 2px; border-color: #c9c9c3; }
.automation-popper .el-date-table td.current:not(.disabled) .el-date-table-cell__text {
  background: #191919;
  color: #fffa00;
}
.automation-popper .el-date-table td.today:not(.current) .el-date-table-cell__text {
  color: #191919;
  font-weight: 700;
}
.automation-popper .el-date-table td.available:hover .el-date-table-cell__text {
  background: rgba(255, 250, 0, .18);
  color: #191919;
}
.automation-popper .el-picker-panel__icon-btn:hover { color: #191919; }
.automation-popper .el-date-picker__header-label { font-family: "Arial Narrow", "Roboto Condensed", "DIN Condensed", sans-serif; letter-spacing: .06em; color: #191919; }

.automation-messagebox {
  border-radius: 2px;
  border: 1px solid #c9c9c3;
  box-shadow: 12px 12px 0 rgba(25, 25, 25, .08);
  background: #fafaf8;
  padding: 0;
}
.automation-messagebox .el-message-box__header {
  margin: 0;
  padding: 12px 16px;
  background: #191919;
}
.automation-messagebox .el-message-box__title {
  color: #ffffff;
  font-family: "Arial Narrow", "Roboto Condensed", "DIN Condensed", sans-serif;
  font-size: 14px;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.automation-messagebox .el-message-box__headerbtn .el-message-box__close { color: rgba(255, 255, 255, .6); }
.automation-messagebox .el-message-box__headerbtn:hover .el-message-box__close { color: #fffa00; }
.automation-messagebox .el-message-box__content { color: #191919; padding: 18px 16px; }
.automation-messagebox .el-message-box__btns {
  padding: 10px 16px 14px;
  border-top: 1px solid #dcdcd7;
  text-align: right;
}
.automation-messagebox .el-message-box__btns .el-button { border-radius: 2px; }
.automation-messagebox .el-message-box__btns .el-button--primary {
  background: #191919;
  border-color: #191919;
  color: #ffffff;
}
.automation-messagebox .el-message-box__btns .el-button--primary:hover {
  background: #2c2c2c;
  border-color: #fffa00;
  color: #fffa00;
}
.automation-messagebox .el-button--default {
  background: transparent;
  border-color: #c9c9c3;
  color: #191919;
}
.automation-messagebox .el-button--default:hover {
  border-color: #191919;
  color: #191919;
}
</style>
