<template>
  <div class="ag-shell" data-ark-theme="endfield" data-ark-depth="moderate">
    <div class="ag-grid" aria-hidden="true"></div>

    <!-- ====== Zone A: Header ====== -->
    <section class="ag-zone ag-zone--head">
      <header class="ag-zone__bar">
        <span class="ag-zone__kicker">TEST CASE / EDIT</span>
        <span class="ag-zone__rule" aria-hidden="true"></span>
        <span class="ag-zone__code">CASE #{{ route.params.id }}</span>
      </header>
      <div class="ag-head">
        <div class="ag-head__main">
          <button class="ag-btn ag-btn--ghost ag-head__back" :disabled="submitting" @click="goBack">
            ← {{ $t('common.back') }}
          </button>
          <p class="ag-head__eyebrow">用例编辑 · 表单操作</p>
          <h1 class="ag-head__title">{{ $t('testcase.edit') }}</h1>
          <p class="ag-head__meta">{{ headMeta || '—' }}</p>
        </div>
        <div class="ag-head__actions">
          <span class="ag-badge" :class="'ag-badge--' + form.priority">{{ priorityLabel }}</span>
          <span class="ag-head__hint">REQUIRED / *</span>
        </div>
      </div>
    </section>

    <!-- ====== Zone B: Loading ====== -->
    <section v-if="loading" class="ag-zone ag-zone--content ag-empty">
      <div class="ag-empty__icon" aria-hidden="true">LOADING</div>
      <h3>正在读取用例…</h3>
    </section>

    <!-- ====== Zone B: Edit form ====== -->
    <section v-else class="ag-zone ag-zone--content">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="112px" class="edit-form">
        <!-- 01 基础信息 -->
        <div class="ag-panel">
          <header class="ag-panel__head">
            <span class="ag-panel__idx">01</span>
            <span class="ag-panel__label">基础信息 / IDENTITY</span>
            <span class="ag-zone__rule" aria-hidden="true"></span>
            <span class="ag-panel__code">TITLE · DESC</span>
          </header>
          <div class="ag-panel__body">
            <el-form-item :label="$t('testcase.caseTitle')" prop="title">
              <el-input
                v-model="form.title"
                :placeholder="$t('testcase.caseTitlePlaceholder')"
              />
            </el-form-item>
            <el-form-item :label="$t('testcase.caseDescription')" prop="description">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="3"
                :placeholder="$t('testcase.caseDescriptionPlaceholder')"
              />
            </el-form-item>
          </div>
        </div>

        <!-- 02 关联配置 -->
        <div class="ag-panel">
          <header class="ag-panel__head">
            <span class="ag-panel__idx">02</span>
            <span class="ag-panel__label">关联配置 / TARGET</span>
            <span class="ag-zone__rule" aria-hidden="true"></span>
            <span class="ag-panel__code">PROJECT · VERSION · MODULE</span>
          </header>
          <div class="ag-panel__body">
            <el-row :gutter="20">
              <el-col :xs="24" :md="8">
                <el-form-item :label="$t('testcase.project')" prop="project_id">
                  <el-select
                    v-model="form.project_id"
                    :placeholder="$t('testcase.selectProject')"
                    clearable
                    filterable
                    @change="onProjectChange"
                  >
                    <el-option
                      v-for="project in projects"
                      :key="project.id"
                      :label="project.name"
                      :value="project.id"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="8">
                <el-form-item :label="$t('testcase.priority')" prop="priority">
                  <el-select v-model="form.priority" :placeholder="$t('testcase.selectPriority')">
                    <el-option :label="$t('testcase.low')" value="low" />
                    <el-option :label="$t('testcase.medium')" value="medium" />
                    <el-option :label="$t('testcase.high')" value="high" />
                    <el-option :label="$t('testcase.critical')" value="critical" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="8">
                <el-form-item :label="$t('testcase.testType')" prop="test_type">
                  <el-select v-model="form.test_type" :placeholder="$t('testcase.selectTestType')">
                    <el-option :label="$t('testcase.functional')" value="functional" />
                    <el-option :label="$t('testcase.integration')" value="integration" />
                    <el-option :label="$t('testcase.api')" value="api" />
                    <el-option :label="$t('testcase.ui')" value="ui" />
                    <el-option :label="$t('testcase.performance')" value="performance" />
                    <el-option :label="$t('testcase.security')" value="security" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :xs="24" :md="12">
                <el-form-item :label="$t('testcase.relatedVersions')">
                  <el-select
                    v-model="form.version_ids"
                    :placeholder="$t('testcase.selectVersions')"
                    multiple
                    clearable
                    filterable
                    @change="onVersionChange"
                  >
                    <el-option
                      v-for="version in projectVersions"
                      :key="version.id"
                      :label="version.name + (version.is_baseline ? ' (' + $t('testcase.baseline') + ')' : '')"
                      :value="version.id"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :md="12">
                <el-form-item
                  v-if="form.version_ids && form.version_ids.length > 0"
                  :label="$t('testcase.moduleName')"
                >
                  <el-select
                    v-model="form.function_module_id"
                    :placeholder="$t('testcase.selectModule')"
                    clearable
                    filterable
                  >
                    <el-option value="" :label="$t('testcase.noModule')" />
                    <el-option
                      v-for="mod in formModules"
                      :key="mod.id"
                      :label="mod.name"
                      :value="mod.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item v-else>
                  <span class="ag-muted">—</span>
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </div>

        <!-- 03 用例内容 -->
        <div class="ag-panel">
          <header class="ag-panel__head">
            <span class="ag-panel__idx">03</span>
            <span class="ag-panel__label">用例内容 / CONTENT</span>
            <span class="ag-zone__rule" aria-hidden="true"></span>
            <span class="ag-panel__code">PRE · STEP · EXPECT</span>
          </header>
          <div class="ag-panel__body">
            <el-form-item :label="$t('testcase.preconditions')" prop="preconditions">
              <el-input
                v-model="form.preconditions"
                type="textarea"
                :rows="2"
                :placeholder="$t('testcase.preconditionsPlaceholder')"
              />
            </el-form-item>
            <el-form-item :label="$t('testcase.steps')" prop="steps">
              <el-input
                v-model="form.steps"
                type="textarea"
                :rows="5"
                maxlength="1000"
                show-word-limit
                :placeholder="$t('testcase.stepsPlaceholder')"
              />
            </el-form-item>
            <el-form-item :label="$t('testcase.expectedResult')" prop="expected_result">
              <el-input
                v-model="form.expected_result"
                type="textarea"
                :rows="3"
                :placeholder="$t('testcase.expectedResultPlaceholder')"
              />
            </el-form-item>
          </div>
        </div>
      </el-form>

      <!-- ====== Dock ====== -->
      <footer class="ag-dock">
        <span class="ag-dock__state"><i class="ag-dock__dot" aria-hidden="true"></i>DRAFT / EDIT MODE</span>
        <span class="ag-dock__meta">{{ dockMeta }}</span>
        <span class="ag-zone__rule" aria-hidden="true"></span>
        <button class="ag-btn" :disabled="submitting" @click="goBack">{{ $t('common.cancel') }}</button>
        <button class="ag-btn ag-btn--ok" :disabled="submitting" @click="handleSubmit">
          <span class="ag-btn__key">S</span>{{ submitting ? '保存中…' : $t('testcase.saveChanges') }}
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const formRef = ref()
const loading = ref(true)
const submitting = ref(false)
const projects = ref([])
const projectVersions = ref([])
const formModules = ref([])

const form = reactive({
  title: '',
  description: '',
  project_id: null,
  priority: 'medium',
  test_type: 'functional',
  preconditions: '',
  steps: '',
  expected_result: '',
  version_ids: [],
  function_module_id: null
})

const rules = {
  title: [
    { required: true, message: computed(() => t('testcase.titleRequired')), trigger: 'blur' },
    { min: 5, max: 500, message: computed(() => t('testcase.titleLength')), trigger: 'blur' }
  ],
  expected_result: [
    { required: true, message: computed(() => t('testcase.expectedResultRequired')), trigger: 'blur' }
  ],
  steps: [
    { max: 1000, message: computed(() => t('testcase.stepsMaxLength')), trigger: 'blur' }
  ]
}

const priorityLabel = computed(() => {
  const map = {
    low: t('testcase.low'),
    medium: t('testcase.medium'),
    high: t('testcase.high'),
    critical: t('testcase.critical')
  }
  return map[form.priority] || form.priority
})

const headMeta = computed(() => {
  const projectName = projects.value.find(p => p.id === form.project_id)?.name
  const versionsText = form.version_ids
    .map(id => projectVersions.value.find(v => v.id === id)?.name)
    .filter(Boolean)
    .join(' / ')
  const typeMap = {
    functional: t('testcase.functional'),
    integration: t('testcase.integration'),
    api: t('testcase.api'),
    ui: t('testcase.ui'),
    performance: t('testcase.performance'),
    security: t('testcase.security')
  }
  const typeText = typeMap[form.test_type]
  return [
    projectName ? `项目 · ${projectName}` : '',
    versionsText ? `版本 · ${versionsText}` : '',
    typeText ? `类型 · ${typeText}` : ''
  ].filter(Boolean).join('　│　')
})

const stepLines = computed(() => form.steps ? form.steps.split('\n').filter(l => l.trim()).length : 0)
const dockMeta = computed(() => `标题 ${form.title.length} 字符 · 步骤 ${stepLines.value} 行`)

const goBack = () => {
  if (submitting.value) return
  router.back()
}

// 将HTML的<br>标签转换为换行符（用于编辑时显示）
const convertBrToNewline = (text) => {
  if (!text) return ''
  return text.replace(/<br\s*\/?>/gi, '\n')
}

// 将换行符转换为HTML的<br>标签（用于保存）
const convertNewlineToBr = (text) => {
  if (!text) return ''
  return text.replace(/\n/g, '<br>')
}

const fetchProjects = async () => {
  try {
    const response = await api.get('/projects/list/')
    projects.value = response.data.results || []
  } catch (error) {
    ElMessage.error(t('testcase.fetchProjectsFailed'))
  }
}

const fetchProjectVersions = async (projectId) => {
  if (!projectId) {
    projectVersions.value = []
    return
  }

  try {
    const response = await api.get(`/versions/projects/${projectId}/versions/`)
    projectVersions.value = response.data || []
  } catch (error) {
    console.error(t('testcase.fetchVersionsFailed'), error)
    ElMessage.error(t('testcase.fetchVersionsFailed'))
    projectVersions.value = []
  }
}

const onProjectChange = (projectId) => {
  form.version_ids = []
  formModules.value = []
  form.function_module_id = null
  fetchProjectVersions(projectId)
}

const onVersionChange = async () => {
  if (form.version_ids && form.version_ids.length > 0) {
    try {
      const vid = form.version_ids[0]
      const response = await api.get(`/versions/${vid}/modules/`)
      formModules.value = response.data.results || response.data || []
    } catch (error) {
      formModules.value = []
    }
  } else {
    formModules.value = []
    form.function_module_id = null
  }
}

const fetchTestCase = async () => {
  try {
    const response = await api.get(`/testcases/${route.params.id}/`)
    const testcase = response.data

    // Fill form data
    form.title = testcase.title
    form.description = testcase.description
    form.project_id = testcase.project?.id || null
    form.priority = testcase.priority
    form.test_type = testcase.test_type
    form.preconditions = convertBrToNewline(testcase.preconditions || '')
    form.expected_result = convertBrToNewline(testcase.expected_result || '')

    // Fill steps data (convert <br> to newlines)
    form.steps = convertBrToNewline(testcase.steps || '')

    // Fill version associations
    form.version_ids = testcase.versions ? testcase.versions.map(v => v.id) : []

    // If project exists, fetch versions for that project
    if (form.project_id) {
      await fetchProjectVersions(form.project_id)
    }

    // Fill function module and load module list for the first version
    form.function_module_id = testcase.function_module?.id || null
    if (form.version_ids && form.version_ids.length > 0) {
      await onVersionChange()
    }

    loading.value = false
  } catch (error) {
    ElMessage.error(t('testcase.fetchDetailFailed'))
    router.back()
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // Convert newlines back to <br> tags before submitting
        const submitData = {
          ...form,
          preconditions: convertNewlineToBr(form.preconditions || ''),
          steps: convertNewlineToBr(form.steps || ''),
          expected_result: convertNewlineToBr(form.expected_result || '')
        }

        await api.put(`/testcases/${route.params.id}/`, submitData)
        ElMessage.success(t('testcase.updateSuccess'))
        router.push({ path: `/ai-generation/testcases/${route.params.id}`, query: route.query })
      } catch (error) {
        ElMessage.error(t('testcase.updateFailed'))
        console.error('Submit error:', error)
      } finally {
        submitting.value = false
      }
    }
  })
}

onMounted(async () => {
  await fetchProjects()
  await fetchTestCase()  // fetchTestCase中会根据项目获取版本列表
})
</script>

<style lang="scss" scoped>
/* =============================================
   Ark Moderate — Test Case Edit (Endfield)
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
    overflow: auto; padding: 20px;
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

  &__main { min-width: 0; }
  &__back {
    flex-shrink: 0; align-self: flex-start; margin-right: 6px; margin-bottom: 8px;
    background: #eef0ed; border-color: #b7bab7; color: #222;
  }
  &__eyebrow {
    margin: 0 0 6px; font-size: 10px; color: #888;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .14em;
  }
  &__title {
    margin: 0; font-size: 26px; font-weight: 900; color: var(--ark-ink); line-height: 1.25;
    &::before {
      content: ""; display: block; width: 44px; height: 4px;
      background: var(--ark-signal); margin-bottom: 10px;
    }
  }
  &__meta {
    margin: 10px 0 0; font-size: 12px; color: #777; line-height: 1.7;
    word-break: break-all;
  }
  &__actions {
    display: flex; align-items: center; gap: 12px; flex-shrink: 0;
    flex-wrap: wrap; justify-content: flex-end;
    padding-bottom: 2px;
  }
  &__hint {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .14em; color: #b0b2af;
  }
}

/* ============================================
   Form panels
   ============================================ */
.edit-form { display: block; }
.ag-panel {
  background: #fff; border: 1px solid var(--ark-border);
  margin-bottom: 16px;
  animation: ag-enter .4s ease-out both;

  &:nth-child(2) { animation-delay: .06s; }
  &:nth-child(3) { animation-delay: .12s; }

  &__head {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px; background: #fafaf8; border-bottom: 1px solid var(--ark-border);
  }
  &__idx {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    letter-spacing: .1em; color: #aaa;
  }
  &__label {
    font-size: 11px; font-weight: 700; color: #555;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .12em; white-space: nowrap;
  }
  &__code {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .1em; color: #bbb; white-space: nowrap;
  }
  &__body { padding: 20px 18px 2px; }
}

/* Element Plus 控件：方形 / 1px 规则 / 信号黄聚焦 */
.edit-form {
  :deep(.el-form-item) { margin-bottom: 20px; }
  :deep(.el-form-item__label) {
    font-size: 11px; font-weight: 600; color: #555; letter-spacing: .04em;
    justify-content: flex-start; line-height: 20px;
  }
  :deep(.el-form-item__label::after) { content: none; }
  :deep(.el-form-item__content) { line-height: 20px; }

  :deep(.el-input__wrapper),
  :deep(.el-select .el-input__wrapper),
  :deep(.el-select__wrapper) {
    border-radius: 0;
    background: #fff;
    box-shadow: 0 0 0 1px #c9cbc8 inset;
    transition: box-shadow .14s ease;
    padding: 1px 12px;
  }
  :deep(.el-input__wrapper:hover),
  :deep(.el-select .el-input__wrapper:hover),
  :deep(.el-select__wrapper:hover) {
    box-shadow: 0 0 0 1px var(--ark-ink) inset;
  }
  :deep(.el-input__wrapper.is-focus),
  :deep(.el-select .el-input__wrapper.is-focus),
  :deep(.el-select__wrapper.is-focused) {
    box-shadow: 0 0 0 2px var(--ark-ink) inset;
  }
  :deep(.el-input__inner) {
    height: 32px; font-size: 13px; color: var(--ark-ink);
    font-family: "Noto Sans SC", "PingFang SC", sans-serif;
  }
  :deep(.el-textarea__inner) {
    border-radius: 0; box-shadow: 0 0 0 1px #c9cbc8 inset;
    padding: 10px 12px; font-size: 13px; line-height: 1.7; color: var(--ark-ink);
    font-family: "Noto Sans SC", "PingFang SC", sans-serif;
    transition: box-shadow .14s ease;
  }
  :deep(.el-textarea__inner:hover) { box-shadow: 0 0 0 1px var(--ark-ink) inset; }
  :deep(.el-textarea__inner:focus) { box-shadow: 0 0 0 2px var(--ark-ink) inset; }
  :deep(.el-form-item.is-error .el-input__wrapper),
  :deep(.el-form-item.is-error .el-textarea__inner) {
    box-shadow: 0 0 0 1px #c0503c inset;
  }
  :deep(.el-select__tags) { padding-left: 8px; }
}

/* ============================================
   Dock
   ============================================ */
.ag-dock {
  display: flex; align-items: center; gap: 14px;
  padding: 12px 16px;
  background: var(--ark-ink); color: rgba(255,255,255,.82);
  margin-top: 18px;
  animation: ag-enter .4s ease-out both;
  animation-delay: .16s;

  &__state {
    display: inline-flex; align-items: center; gap: 8px;
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .16em; white-space: nowrap;
  }
  &__dot {
    width: 8px; height: 8px; background: var(--ark-signal);
    display: inline-block; flex-shrink: 0;
  }
  &__meta { font-size: 11px; color: rgba(255,255,255,.55); white-space: nowrap; }

  :deep(.ag-zone__rule) { background: rgba(255,255,255,.18); min-width: 12px; }
  .ag-zone__rule { background: rgba(255,255,255,.18); min-width: 12px; }
  .ag-btn {
    color: rgba(255,255,255,.85);
    background: transparent; border-color: rgba(255,255,255,.35);
    &:hover:not(:disabled) { background: rgba(255,255,255,.1); border-color: rgba(255,255,255,.6); color: #fff; }
  }
  .ag-btn--ok {
    color: var(--ark-ink); background: var(--ark-signal); border-color: var(--ark-signal);
    &::before { background: var(--ark-ink); }
    &:hover:not(:disabled) { background: #e8e600; border-color: #e8e600; color: var(--ark-ink); }
  }
}

/* ============================================
   Badges
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
.ag-muted { color: #bbb; font-size: 12px; }

/* ============================================
   Empty / loading
   ============================================ */
.ag-empty {
  display: grid; place-items: center; align-content: center; gap: 10px;
  min-height: 240px; text-align: center;
  &__icon {
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif;
    letter-spacing: .22em; color: #b5b7b4;
  }
  h3 { margin: 0; font-size: 14px; color: #666; font-weight: 600; }
}

/* ============================================
   Buttons (同 TestCaseDetail)
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
  &__key {
    display: inline-flex; align-items: center; justify-content: center;
    width: 18px; height: 18px; font-size: 10px;
    background: rgba(0,0,0,.08); border: 1px solid currentColor;
  }
  &:hover:not(:disabled) { background: #e9ebe9; border-color: #a9aca9; }
  &:active:not(:disabled) { transform: translateY(1px); background: #dde0dd; }
  &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: 2px; }
  &:disabled {
    color: #b4b6b3; background: #f5f6f4; border-color: #e1e3e0; cursor: not-allowed;
    &::before { background: transparent; }
  }

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
}

/* ============================================
   Motion
   ============================================ */
@keyframes ag-enter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}

@media (prefers-reduced-motion: reduce) {
  .ag-zone, .ag-panel, .ag-dock, .ag-btn {
    transition: none !important; animation: none !important;
  }
  .ag-btn:active:not(:disabled) { transform: none; }
}

/* ============================================
   Responsive
   ============================================ */
@media (max-width: 1024px) {
  .ag-shell { padding: 16px 16px 0; }
}
@media (max-width: 768px) {
  .ag-shell { padding: 12px 12px 0; }
  .ag-head { flex-direction: column; align-items: flex-start; }
  .ag-head__actions { width: 100%; justify-content: flex-start; }
  .ag-zone--content { padding: 14px; }
  .ag-panel__code { display: none; }
  .ag-dock { flex-wrap: wrap; }
  .ag-dock__meta { display: none; }
  .ag-dock .ag-btn { flex: 1; }
  .ag-head__hint { display: none; }
}
</style>
