<template>
  <div class="page-container">
    <!-- 导航栏 -->
    <div class="nav-strip">
      <button class="nav-btn prev" :disabled="!neighbors.previous" @click="goToNeighbor(neighbors.previous?.id)">
        <span class="nav-arrow">←</span>
        <span class="nav-label">{{ $t('testcase.previousCase') }}</span>
      </button>
      <button class="nav-btn back" @click="router.push({ path: '/ai-generation/testcases', query: route.query })">
        <span class="nav-label">{{ $t('common.back') }}</span>
      </button>
      <button class="nav-btn edit" @click="editTestCase">
        <span class="nav-label">{{ $t('common.edit') }}</span>
      </button>
      <button class="nav-btn next" :disabled="!neighbors.next" @click="goToNeighbor(neighbors.next?.id)">
        <span class="nav-label">{{ $t('testcase.nextCase') }}</span>
        <span class="nav-arrow">→</span>
      </button>
    </div>

    <div class="detail-layout" v-if="testcase">
      <!-- 左侧：执行区 -->
      <div class="execution-panel">
        <!-- 标题 -->
        <div class="title-block">
          <span class="priority-dot" :class="testcase.priority"></span>
          <h1 class="case-title">{{ testcase.title }}</h1>
          <div class="exec-actions">
            <button class="exec-btn pass" :class="{ active: testcase.execution_status === 'passed' }" @click="executeCase('passed')" :disabled="executing">✓ 通过</button>
            <button class="exec-btn fail" :class="{ active: testcase.execution_status === 'failed' }" @click="executeCase('failed')" :disabled="executing">✕ 不通过</button>
          </div>
        </div>

        <!-- 描述 -->
        <div v-if="testcase.description" class="content-block description-block">
          <div class="block-label">📝 {{ $t('testcase.caseDescription') }}</div>
          <p class="description-text">{{ testcase.description }}</p>
        </div>

        <!-- 前置条件 -->
        <div class="content-block precondition-block">
          <div class="block-label">⚙️ {{ $t('testcase.preconditions') }}</div>
          <div class="block-body" v-html="testcase.preconditions || '—'"></div>
        </div>

        <!-- 操作步骤 -->
        <div class="content-block steps-block">
          <div class="block-label">📋 {{ $t('testcase.steps') }}</div>
          <div class="step-list" v-html="testcase.steps || '—'"></div>
        </div>

        <!-- 预期结果 -->
        <div class="content-block expected-block">
          <div class="block-label">✅ {{ $t('testcase.expectedResult') }}</div>
          <div class="block-body expected-body" v-html="testcase.expected_result || '—'"></div>
        </div>
      </div>

      <!-- 右侧：元信息 -->
      <div class="meta-panel">
        <div class="meta-card">
          <div class="meta-row">
            <span class="meta-key">{{ $t('testcase.priority') }}</span>
            <span class="meta-value">
              <span class="pri-badge" :class="testcase.priority">{{ getPriorityText(testcase.priority) }}</span>
            </span>
          </div>
          <div class="meta-row">
            <span class="meta-key">{{ $t('testcase.testType') }}</span>
            <span class="meta-value">{{ getTypeText(testcase.test_type) }}</span>
          </div>
          <div class="meta-row">
            <span class="meta-key">{{ $t('testcase.project') }}</span>
            <span class="meta-value">{{ testcase.project?.name || '—' }}</span>
          </div>
          <div class="meta-row">
            <span class="meta-key">{{ $t('testcase.moduleName') }}</span>
            <span class="meta-value">
              <span v-if="testcase.function_module" class="module-tag">{{ testcase.function_module.name }}</span>
              <span v-else class="meta-muted">—</span>
            </span>
          </div>
          <div class="meta-row">
            <span class="meta-key">{{ $t('testcase.relatedVersions') }}</span>
            <span class="meta-value">
              <span v-if="testcase.versions && testcase.versions.length > 0" class="version-list">
                <span v-for="v in testcase.versions" :key="v.id" class="ver-tag" :class="{ baseline: v.is_baseline }">{{ v.name }}</span>
              </span>
              <span v-else class="meta-muted">—</span>
            </span>
          </div>
          <div class="meta-divider"></div>
          <div class="meta-row">
            <span class="meta-key">{{ $t('testcase.author') }}</span>
            <span class="meta-value">{{ testcase.author?.username || '—' }}</span>
          </div>
          <div class="meta-row">
            <span class="meta-key">{{ $t('testcase.createdAt') }}</span>
            <span class="meta-value meta-date">{{ formatDate(testcase.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部导航条 -->
    <div class="bottom-nav">
      <button class="bn-btn" :disabled="!neighbors.previous" @click="goToNeighbor(neighbors.previous?.id)">
        ← {{ $t('testcase.previousCase') }}
      </button>
      <span class="bn-pos" v-if="neighbors.current">
        {{ neighbors.current.id }}
      </span>
      <button class="bn-btn" :disabled="!neighbors.next" @click="goToNeighbor(neighbors.next?.id)">
        {{ $t('testcase.nextCase') }} →
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import dayjs from 'dayjs'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const testcase = ref(null)
const neighbors = ref({ previous: null, next: null, current: null })
const executing = ref(false)

const executeCase = async (status) => {
  if (!testcase.value) return
  executing.value = true
  try {
    await api.patch(`/testcases/${testcase.value.id}/execute/`, { execution_status: status })
    testcase.value.execution_status = status
    ElMessage.success(status === 'passed' ? '已标记通过' : '已标记不通过')
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    executing.value = false
  }
}

const fetchTestCase = async () => {
  try {
    const response = await api.get(`/testcases/${route.params.id}/`)
    testcase.value = response.data
    fetchNeighbors()
  } catch (error) {
    ElMessage.error(t('testcase.fetchDetailFailed'))
  }
}

const fetchNeighbors = async () => {
  try {
    const query = { ...route.query }
    const response = await api.get(`/testcases/${route.params.id}/neighbors/`, { params: query })
    neighbors.value = {
      previous: response.data.previous,
      next: response.data.next,
      current: response.data.current
    }
  } catch (error) {
    neighbors.value = { previous: null, next: null, current: null }
  }
}

const goToNeighbor = (id) => {
  if (!id) return
  router.push({ path: `/ai-generation/testcases/${id}`, query: route.query })
  window.scrollTo(0, 0)
}

const editTestCase = () => {
  router.push({ path: `/ai-generation/testcases/${route.params.id}/edit`, query: route.query })
}

const getPriorityText = (priority) => {
  const textMap = { low: t('testcase.low'), medium: t('testcase.medium'), high: t('testcase.high'), critical: t('testcase.critical') }
  return textMap[priority] || priority
}

const getTypeText = (type) => {
  const textMap = { functional: t('testcase.functional'), integration: t('testcase.integration'), api: t('testcase.api'), ui: t('testcase.ui'), performance: t('testcase.performance'), security: t('testcase.security') }
  return textMap[type] || '-'
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

onMounted(() => { fetchTestCase() })
watch(() => route.params.id, () => { fetchTestCase() })
</script>

<style lang="scss" scoped>
/* ===== 顶层导航条 ===== */
.nav-strip {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  padding: 8px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.nav-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #4a5568;
  font-size: .88rem;
  cursor: pointer;
  transition: all .15s;
  &:hover:not(:disabled) { border-color: #667eea; color: #667eea; }
  &:disabled { opacity: .35; cursor: not-allowed; }
  &.edit { margin-left: auto; background: #667eea; color: #fff; border-color: #667eea; font-weight: 500; }
  &.edit:hover { background: #5a6fd6; }
}
.nav-arrow { font-size: 1.1rem; }

/* ===== 双栏布局 ===== */
.detail-layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

/* ===== 左侧执行区 ===== */
.execution-panel {
  flex: 1 1 65%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.title-block {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.priority-dot {
  flex-shrink: 0;
  width: 14px; height: 14px;
  border-radius: 50%;
  margin-top: 6px;
  &.low { background: #67c23a; }
  &.medium { background: #e6a23c; }
  &.high { background: #f56c6c; }
  &.critical { background: #f56c6c; box-shadow: 0 0 0 4px rgba(245,108,108,.25); }
}
.case-title {
  margin: 0;
  font-size: 1.3rem;
  font-weight: 600;
  color: #1a1a2e;
  line-height: 1.5;
  word-break: break-word;
  flex: 1;
}
.exec-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.exec-btn {
  padding: 6px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  font-size: .82rem;
  cursor: pointer;
  transition: all .15s;
  &.pass:hover, &.pass.active { background: #f0fff4; border-color: #48bb78; color: #22543d; }
  &.fail:hover, &.fail.active { background: #fff5f5; border-color: #fc8181; color: #742a2a; }
  &:disabled { opacity: .5; cursor: not-allowed; }
}

.content-block {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.block-label {
  font-size: .78rem;
  font-weight: 600;
  color: #667eea;
  text-transform: uppercase;
  letter-spacing: .5px;
  margin-bottom: 14px;
}
.block-body {
  color: #2d3748;
  line-height: 1.75;
  font-size: .95rem;
}
.description-text {
  color: #4a5568;
  line-height: 1.7;
  font-size: .95rem;
  margin: 0;
}

/* 步骤特殊样式 */
.steps-block {
  border-left: 4px solid #667eea;
}
.step-list {
  color: #1a1a2e;
  line-height: 1.85;
  font-size: .97rem;
  :deep(br) { display: block; content: ''; margin-top: 8px; }
}

/* 预期结果特殊样式 */
.expected-block {
  border-left: 4px solid #48bb78;
  background: #f0fff4;
}
.expected-body {
  color: #22543d;
  font-weight: 500;
}

/* ===== 右侧元信息 ===== */
.meta-panel {
  flex: 0 0 300px;
  position: sticky;
  top: 20px;
}
.meta-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f7fafc;
  &:last-of-type { border-bottom: none; }
}
.meta-key {
  font-size: .8rem;
  color: #a0aec0;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: .3px;
}
.meta-value {
  font-size: .88rem;
  color: #2d3748;
  font-weight: 500;
  text-align: right;
}
.meta-muted { color: #cbd5e0; }
.meta-date { font-size: .8rem; font-weight: 400; color: #a0aec0; }
.meta-divider {
  height: 1px;
  background: #e2e8f0;
  margin: 8px 0;
}

.pri-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: .8rem;
  font-weight: 600;
  &.low { color: #67c23a; background: #f0f9eb; }
  &.medium { color: #e6a23c; background: #fdf6ec; }
  &.high { color: #f56c6c; background: #fef0f0; }
  &.critical { color: #fff; background: #f56c6c; }
}
.module-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: .8rem;
  color: #059669;
  background: #ecfdf5;
}
.version-list { display: flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; }
.ver-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: .77rem;
  background: #edf2f7;
  color: #4a5568;
  &.baseline { background: #fef3c7; color: #92400e; }
}

/* ===== 底部导航条 ===== */
.bottom-nav {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 32px;
  padding: 16px;
}
.bn-btn {
  padding: 10px 24px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #4a5568;
  font-size: .9rem;
  cursor: pointer;
  transition: all .15s;
  &:hover:not(:disabled) { border-color: #667eea; color: #667eea; box-shadow: 0 2px 8px rgba(102,126,234,.15); }
  &:disabled { opacity: .3; cursor: not-allowed; }
}
.bn-pos {
  font-size: .8rem;
  color: #cbd5e0;
  font-weight: 500;
  padding: 4px 12px;
  background: #f7fafc;
  border-radius: 6px;
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .detail-layout { flex-direction: column; }
  .meta-panel { flex: 1 1 auto; position: static; }
  .nav-strip { flex-wrap: wrap; .nav-btn.edit { margin-left: 0; } }
}
</style>
