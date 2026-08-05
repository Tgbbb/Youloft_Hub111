<template>
  <div class="environment-table">
    <el-table :data="data" v-loading="loading" style="width: 100%">
      <el-table-column prop="name" :label="$t('apiTesting.component.environmentTable.environmentName')" min-width="200" />
      <el-table-column prop="scope" :label="$t('apiTesting.component.environmentTable.scope')" width="120">
        <template #default="scope">
          <el-tag :type="scope.row.scope === 'GLOBAL' ? 'primary' : 'success'">
            {{ scope.row.scope === 'GLOBAL' ? $t('apiTesting.component.environmentTable.global') : $t('apiTesting.component.environmentTable.local') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="scope === 'LOCAL'" prop="project_name" :label="$t('apiTesting.component.environmentTable.relatedProject')" width="150" />
      <el-table-column :label="$t('apiTesting.environment.baseURL')" width="130" show-overflow-tooltip>
        <template #default="scope2">
          <span v-if="scope2.row.base_url" class="base-url">{{ scope2.row.base_url }}</span>
          <span v-else style="color:#c0c4cc">-</span>
        </template>
      </el-table-column>
      <el-table-column :label="$t('apiTesting.component.environmentTable.variableCount')" width="100">
        <template #default="scope">
          {{ Object.keys(scope.row.variables || {}).length }}
        </template>
      </el-table-column>
      <el-table-column prop="is_active" :label="$t('apiTesting.component.environmentTable.status')" width="80">
        <template #default="scope">
          <el-tag v-if="scope.row.is_active" type="success" size="small">{{ $t('apiTesting.component.environmentTable.activated') }}</el-tag>
          <el-tag v-else type="info" size="small">{{ $t('apiTesting.component.environmentTable.notActivated') }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_by.username" :label="$t('apiTesting.component.environmentTable.createdBy')" width="120" />
      <el-table-column prop="created_at" :label="$t('apiTesting.component.environmentTable.createdAt')" width="160">
        <template #default="scope">
          {{ formatDate(scope.row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column :label="$t('apiTesting.component.environmentTable.operation')" width="250" fixed="right">
        <template #default="scope">
          <el-button-group>
            <el-button
              v-if="!scope.row.is_active"
              link
              type="success"
              @click="$emit('activate', scope.row)"
              size="small"
            >
              {{ $t('apiTesting.component.environmentTable.activate') }}
            </el-button>
            <el-button link type="primary" @click="viewVariables(scope.row)" size="small">
              {{ $t('apiTesting.component.environmentTable.viewVariables') }}
            </el-button>
            <el-button link type="primary" @click="$emit('edit', scope.row)" size="small">
              {{ $t('apiTesting.component.environmentTable.edit') }}
            </el-button>
            <el-button link type="primary" @click="$emit('duplicate', scope.row)" size="small">
              {{ $t('apiTesting.component.environmentTable.copy') }}
            </el-button>
            <el-button link type="danger" @click="$emit('delete', scope.row)" size="small">
              {{ $t('apiTesting.component.environmentTable.delete') }}
            </el-button>
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <!-- 查看变量对话框 -->
    <el-dialog
      v-model="showViewDialog"
      class="automation-dialog"
      modal-class="automation-modal"
      :title="$t('apiTesting.component.environmentTable.environmentVariables')"
      width="600px"
    >
      <div v-if="viewingEnvironment" class="variables-view">
        <div class="env-info">
          <el-descriptions :column="2" border>
            <el-descriptions-item :label="$t('apiTesting.component.environmentTable.environmentName')">
              {{ viewingEnvironment.name }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('apiTesting.component.environmentTable.scope')">
              <el-tag :type="viewingEnvironment.scope === 'GLOBAL' ? 'primary' : 'success'">
                {{ viewingEnvironment.scope === 'GLOBAL' ? $t('apiTesting.component.environmentTable.global') : $t('apiTesting.component.environmentTable.local') }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item v-if="viewingEnvironment.project_name" :label="$t('apiTesting.component.environmentTable.relatedProject')">
              {{ viewingEnvironment.project_name }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('apiTesting.component.environmentTable.status')">
              <el-tag v-if="viewingEnvironment.is_active" type="success">{{ $t('apiTesting.component.environmentTable.activated') }}</el-tag>
              <el-tag v-else type="info">{{ $t('apiTesting.component.environmentTable.notActivated') }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item v-if="viewingEnvironment.base_url" :label="$t('apiTesting.environment.baseURL')" :span="2">
              {{ viewingEnvironment.base_url }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="defaults-info" v-if="hasDefaults(viewingEnvironment)">
          <h4>{{ $t('apiTesting.component.environmentTable.defaultConfig') }}</h4>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item :label="$t('apiTesting.environment.defaultHeaders')">
              {{ Object.keys(viewingEnvironment.default_headers || {}).length }} 项
            </el-descriptions-item>
            <el-descriptions-item :label="$t('apiTesting.environment.defaultParams')">
              {{ Object.keys(viewingEnvironment.default_params || {}).length }} 项
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="variables-table">
          <h4>{{ $t('apiTesting.component.environmentTable.variableList') }}</h4>
          <el-table :data="formatVariables(viewingEnvironment.variables)" style="width: 100%">
            <el-table-column prop="key" :label="$t('apiTesting.component.environmentTable.variableName')" width="150" />
            <el-table-column prop="initialValue" :label="$t('apiTesting.component.environmentTable.initialValue')" />
            <el-table-column prop="currentValue" :label="$t('apiTesting.component.environmentTable.currentValue')" />
          </el-table>
        </div>
      </div>

      <template #footer>
        <el-button @click="showViewDialog = false">{{ $t('apiTesting.component.environmentTable.close') }}</el-button>
        <el-button type="primary" @click="$emit('edit', viewingEnvironment)">
          {{ $t('apiTesting.component.environmentTable.editEnvironment') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import dayjs from 'dayjs'

defineProps({
  data: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  scope: {
    type: String,
    default: 'GLOBAL'
  }
})

defineEmits(['edit', 'delete', 'activate', 'duplicate'])

const showViewDialog = ref(false)
const viewingEnvironment = ref(null)

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

const formatVariables = (variables) => {
  if (!variables || typeof variables !== 'object') return []
  
  return Object.keys(variables).map(key => {
    const value = variables[key]
    if (typeof value === 'object') {
      return {
        key,
        initialValue: value.initialValue || '',
        currentValue: value.currentValue || value.initialValue || ''
      }
    } else {
      return {
        key,
        initialValue: value || '',
        currentValue: value || ''
      }
    }
  })
}

const hasDefaults = (env) => {
  if (!env) return false
  const h = Object.keys(env.default_headers || {}).length
  const p = Object.keys(env.default_params || {}).length
  return h > 0 || p > 0
}

const viewVariables = (environment) => {
  viewingEnvironment.value = environment
  showViewDialog.value = true
}
</script>

<style scoped>
.environment-table {
  height: 100%;
  color: #191919;
  --ef-ink: #191919;
  --ef-paper: #f2f2f0;
  --ef-signal: #fffa00;
  --ef-muted: #8a8a86;
  --ef-line: #dcdcd7;
  --ef-line-strong: #c9c9c3;
  --ef-line-soft: #f0f0ec;
  --ef-rail: #fafaf8;
  --ef-surface: #ffffff;
  --ef-font-tech: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  --ef-font-display: "Arial Narrow", "Roboto Condensed", "DIN Condensed", sans-serif;
  --ef-font-mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
}

.variables-view {
  max-height: 70vh;
  overflow-y: auto;
}

.env-info {
  margin-bottom: 20px;
}

.base-url {
  font-size: 12px;
  color: var(--ef-ink);
  font-family: var(--ef-font-mono);
}

.variables-table h4 {
  margin: 20px 0 10px 0;
  color: var(--ef-ink);
  font-size: 14px;
  font-weight: 700;
  font-family: var(--ef-font-display);
  letter-spacing: .06em;
  text-transform: uppercase;
}

/* ---------- Element Plus unification ---------- */
.environment-table :deep(.el-button) { border-radius: 2px; }
.environment-table :deep(.el-button--primary.is-link) {
  background: transparent;
  border-color: transparent;
  color: var(--ef-ink);
  font-weight: 600;
}
.environment-table :deep(.el-button--primary.is-link:hover) {
  color: var(--ef-ink);
  background: rgba(255, 250, 0, .18);
  border-color: transparent;
}
.environment-table :deep(.el-button--success.is-link) {
  background: transparent;
  border-color: transparent;
  color: var(--ef-ink);
  font-weight: 600;
}
.environment-table :deep(.el-button--success.is-link:hover) {
  color: #15803d;
  background: rgba(22, 163, 74, .1);
  border-color: transparent;
}
.environment-table :deep(.el-button--danger.is-link) {
  background: transparent;
  border-color: transparent;
  color: var(--ef-ink);
  font-weight: 600;
}
.environment-table :deep(.el-button--danger.is-link:hover) {
  color: #b91c1c;
  background: rgba(220, 38, 38, .08);
  border-color: transparent;
}
.environment-table :deep(.el-button:focus-visible) {
  outline: 2px solid var(--ef-signal);
  outline-offset: 1px;
}

.environment-table :deep(.el-tag) {
  border-radius: 2px;
  font-family: var(--ef-font-tech);
  letter-spacing: .04em;
}
.environment-table :deep(.el-tag--primary) { background: rgba(25, 25, 25, .08); border-color: transparent; color: var(--ef-ink); }
.environment-table :deep(.el-tag--success) { background: rgba(22, 163, 74, .12); border-color: transparent; color: #15803d; }
.environment-table :deep(.el-tag--warning) { background: rgba(217, 119, 6, .12); border-color: transparent; color: #b45309; }
.environment-table :deep(.el-tag--danger) { background: rgba(220, 38, 38, .12); border-color: transparent; color: #b91c1c; }
.environment-table :deep(.el-tag--info) { background: rgba(25, 25, 25, .08); border-color: transparent; color: var(--ef-muted); }

.environment-table :deep(.el-table) {
  --el-table-border-color: var(--ef-line);
  --el-table-header-bg-color: var(--ef-paper);
  --el-table-header-text-color: var(--ef-ink);
  --el-table-row-hover-bg-color: rgba(255, 250, 0, .10);
  --el-table-text-color: var(--ef-ink);
  font-size: 12px;
}
.environment-table :deep(.el-table th.el-table__cell) { font-weight: 700; }

.environment-table :deep(.el-descriptions) {
  --el-descriptions-table-border: 1px solid var(--ef-line);
  --el-descriptions-table-bg-color: var(--ef-surface);
  --el-descriptions-cell-bg-color: var(--ef-rail);
  --el-descriptions-label-bg-color: var(--ef-paper);
  --el-descriptions-text-color: var(--ef-ink);
  --el-descriptions-label-text-color: var(--ef-muted);
}
</style>
