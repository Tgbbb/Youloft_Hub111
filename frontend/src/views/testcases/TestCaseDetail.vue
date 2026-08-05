<template>
  <div class="ag-shell" data-ark-theme="endfield" data-ark-depth="moderate">
    <!-- Grid -->
    <div class="ag-grid" aria-hidden="true"></div>

    <!-- ====== Zone A: Header ====== -->
    <section class="ag-zone ag-zone--head">
      <header class="ag-zone__bar">
        <span class="ag-zone__kicker">TEST CASE / DETAIL</span>
        <span class="ag-zone__rule" aria-hidden="true"></span>
        <span v-if="neighbors.current?.position" class="ag-zone__code">#{{ neighbors.current.position }} / {{ neighbors.current.total }}</span>
        <span v-else class="ag-zone__code">{{ testcase?.id || '' }}</span>
      </header>
      <div class="ag-head">
        <h1 class="ag-head__title">{{ $t('testcase.detail') }}</h1>
        <div class="ag-head__actions">
          <button class="ag-btn ag-btn--ghost" @click="goBackToList">← {{ $t('common.back') }}</button>
          <button class="ag-btn ag-btn--ghost" @click="copyTestCase">{{ $t('testcase.copyCase') }}</button>
          <button class="ag-btn ag-btn--ok" @click="editTestCase">{{ $t('common.edit') }}</button>
        </div>
      </div>
    </section>

    <!-- ====== Zone B: Content ====== -->
    <section v-if="testcase" class="ag-zone ag-zone--content">
      <div class="detail-layout">
        <!-- 左侧：执行区 -->
        <div class="execution-panel">
          <div class="ag-panel exec-head">
            <span class="exec-head__seq" v-if="neighbors.current?.position">#{{ neighbors.current.position }}</span>
            <span class="ag-badge" :class="'ag-badge--' + testcase.priority">{{ getPriorityText(testcase.priority) }}</span>
            <h2 class="case-title">{{ testcase.title }}</h2>
            <div class="exec-actions">
              <button
                class="ag-btn ag-btn--pass"
                :class="{ 'is-active': testcase.execution_status === 'passed' }"
                @click="executeCase('passed')"
                :disabled="executing">
                ✓ 通过
              </button>
              <button
                class="ag-btn ag-btn--fail"
                :class="{ 'is-active': testcase.execution_status === 'failed' }"
                @click="executeCase('failed')"
                :disabled="executing">
                ✗ 不通过
              </button>
            </div>
          </div>

          <div v-if="testcase.description" class="ag-block">
            <header class="ag-block__head">
              <span class="ag-block__idx">01</span>
              <span class="ag-block__label">{{ $t('testcase.caseDescription') }}</span>
            </header>
            <p class="ag-block__text">{{ testcase.description }}</p>
          </div>

          <div class="ag-block">
            <header class="ag-block__head">
              <span class="ag-block__idx">02</span>
              <span class="ag-block__label">{{ $t('testcase.preconditions') }}</span>
            </header>
            <div class="ag-block__body" v-html="testcase.preconditions || '—'"></div>
          </div>

          <div class="ag-block ag-block--steps">
            <header class="ag-block__head">
              <span class="ag-block__idx">03</span>
              <span class="ag-block__label">{{ $t('testcase.steps') }}</span>
            </header>
            <div class="ag-block__body ag-block__steps" v-html="testcase.steps || '—'"></div>
          </div>

          <div class="ag-block ag-block--expected">
            <header class="ag-block__head">
              <span class="ag-block__idx">04</span>
              <span class="ag-block__label">{{ $t('testcase.expectedResult') }}</span>
            </header>
            <div class="ag-block__body" v-html="testcase.expected_result || '—'"></div>
          </div>
        </div>

        <!-- 右侧：元信息 -->
        <aside class="meta-panel">
          <div class="ag-meta">
            <div class="ag-meta__head">CASE / META</div>
            <div class="ag-meta__rows">
              <div class="ag-meta__row">
                <label>{{ $t('testcase.priority') }}</label>
                <span><span class="ag-badge" :class="'ag-badge--' + testcase.priority">{{ getPriorityText(testcase.priority) }}</span></span>
              </div>
              <div class="ag-meta__row">
                <label>{{ $t('testcase.testType') }}</label>
                <span>{{ getTypeText(testcase.test_type) }}</span>
              </div>
              <div class="ag-meta__row">
                <label>{{ $t('testcase.project') }}</label>
                <span>{{ testcase.project?.name || '—' }}</span>
              </div>
              <div class="ag-meta__row">
                <label>{{ $t('testcase.moduleName') }}</label>
                <span>
                  <span v-if="testcase.function_module" class="ag-tag">{{ testcase.function_module.name }}</span>
                  <span v-else class="ag-muted">—</span>
                </span>
              </div>
              <div class="ag-meta__row">
                <label>{{ $t('testcase.relatedVersions') }}</label>
                <span>
                  <span v-if="testcase.versions && testcase.versions.length > 0" class="version-list">
                    <span v-for="v in testcase.versions" :key="v.id" class="ver-tag" :class="{ baseline: v.is_baseline }">{{ v.name }}</span>
                  </span>
                  <span v-else class="ag-muted">—</span>
                </span>
              </div>
            </div>
            <div class="ag-meta__divider"></div>
            <div class="ag-meta__rows">
              <div class="ag-meta__row">
                <label>{{ $t('testcase.author') }}</label>
                <span>{{ testcase.author?.username || '—' }}</span>
              </div>
              <div class="ag-meta__row">
                <label>{{ $t('testcase.createdAt') }}</label>
                <span class="ag-meta__date">{{ formatDate(testcase.created_at) }}</span>
              </div>
            </div>
            <div class="ag-meta__divider"></div>
            <div class="ag-meta__history">
              <div class="ag-meta__his-head">{{ $t('testcase.executionHistory') }}</div>
              <div v-if="testcase.executions && testcase.executions.length > 0" class="exec-history">
                <div v-for="exec in testcase.executions.slice(0, 10)" :key="exec.id" class="exec-item">
                  <span class="exec-mark" :class="exec.status">{{ exec.status === 'passed' ? '✓' : '✗' }}</span>
                  <span class="exec-user">{{ exec.user?.username }}</span>
                  <span class="exec-time">{{ formatDate(exec.executed_at) }}</span>
                </div>
              </div>
              <div v-else class="ag-muted">暂无执行记录</div>
            </div>
          </div>
        </aside>
      </div>

      <!-- 底部前后条导航 -->
      <div class="ag-nav">
        <button class="ag-btn ag-btn--sm" :disabled="!neighbors.previous" @click="goToNeighbor(neighbors.previous?.id)">
          ← {{ $t('testcase.previousCase') }}
        </button>
        <span v-if="neighbors.current?.position" class="ag-nav__pos">#{{ neighbors.current.position }} / {{ neighbors.current.total }}</span>
        <button class="ag-btn ag-btn--sm" :disabled="!neighbors.next" @click="goToNeighbor(neighbors.next?.id)">
          {{ $t('testcase.nextCase') }} →
        </button>
      </div>
    </section>
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
    // 重新获取用例数据以刷新执行历史
    const { data } = await api.get(`/testcases/${testcase.value.id}/`)
    testcase.value = data
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

const goBackToList = () => {
  const query = { ...route.query }
  // 根据序号计算所在页码
  const pos = neighbors.value.current?.position
  if (pos) {
    const pageSize = 15
    query.page = Math.ceil(pos / pageSize)
  }
  router.push({ path: '/ai-generation/testcases', query })
}

const copyTestCase = () => {
  router.push({ path: '/ai-generation/testcases/create', query: { copy_from: route.params.id, ...route.query } })
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
/* =============================================
   Ark Moderate — Test Case Detail
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
   Layout
   ============================================ */
.detail-layout {
  display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 20px;
  align-items: start;
}
.execution-panel {
  display: flex; flex-direction: column; gap: 16px; min-width: 0;
}

/* ============================================
   Execution header
   ============================================ */
.exec-head {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 16px 20px; background: #fff;
  border: 1px solid var(--ark-border); border-top: 3px solid var(--ark-ink);
  &__seq {
    font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #888; white-space: nowrap;
  }
}
.case-title {
  margin: 0; font-size: 18px; font-weight: 800; color: var(--ark-ink);
  line-height: 1.5; word-break: break-word; flex: 1; min-width: 220px;
}
.exec-actions { display: flex; gap: 8px; flex-shrink: 0; }

/* ============================================
   Content blocks
   ============================================ */
.ag-block {
  background: #fff; border: 1px solid var(--ark-border);
  &__head {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 14px; background: #fafaf8; border-bottom: 1px solid var(--ark-border);
  }
  &__idx {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    letter-spacing: .1em; color: #aaa;
  }
  &__label {
    font-size: 11px; font-weight: 700; color: #555;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .12em;
  }
  &__text { margin: 0; padding: 16px 20px; font-size: 14px; line-height: 1.8; color: #444; }
  &__body { padding: 16px 20px; font-size: 14px; line-height: 1.8; color: #333; word-break: break-word; }

  &--steps { border-left: 3px solid var(--ark-signal); }
  &--expected { border-left: 3px solid var(--ark-state); }
}

/* v-html 内容（后端富文本/换行） */
.ag-block__body {
  :deep(p) { margin: 0 0 10px; &:last-child { margin-bottom: 0; } }
  :deep(br) { display: block; content: ''; margin-top: 6px; }
  :deep(ol), :deep(ul) { padding-left: 22px; margin: 0 0 10px; }
  :deep(li) { margin-bottom: 4px; }
  :deep(code) {
    padding: 2px 6px; font-size: .88em;
    background: #eceeeb; color: #191919; border: 1px solid #d8dad7;
    font-family: "IBM Plex Mono", Consolas, monospace;
  }
}
.ag-block__steps :deep(br) { margin-top: 10px; }

/* ============================================
   Meta panel
   ============================================ */
.meta-panel { position: sticky; top: 0; }
.ag-meta {
  background: #fff; border: 1px solid var(--ark-border);
  &__head {
    padding: 10px 14px; background: var(--ark-ink); color: rgba(255,255,255,.75);
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .16em;
  }
  &__rows { padding: 4px 0; }
  &__row {
    display: grid; grid-template-columns: 100px 1fr; gap: 12px; align-items: start;
    padding: 10px 16px; border-bottom: 1px solid #f0f1ef;
    &:last-child { border-bottom: none; }
    label {
      font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
      text-transform: uppercase; letter-spacing: .1em; color: #999; padding-top: 3px;
    }
    span { font-size: 13px; color: #333; line-height: 1.6; text-align: right; word-break: break-word; }
  }
  &__divider { height: 2px; background: var(--ark-ink); margin: 8px 0; }
  &__history { padding: 12px 16px; }
  &__his-head {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .12em; color: #999;
    margin-bottom: 10px;
  }
  &__date { font-size: 12px; color: #888; }
}
.version-list { display: flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; }
.ver-tag {
  display: inline-block; padding: 2px 8px; font-size: 11px;
  font-family: "Space Grotesk", system-ui, sans-serif;
  background: #f4f5f3; color: #555; border: 1px solid var(--ark-border);
  &.baseline { background: #fdf7e4; color: #7d6a16; border-color: #e0d29a; }
}

/* Execution history */
.exec-history { max-height: 200px; overflow-y: auto; }
.exec-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 0; border-bottom: 1px solid #f0f1ef; font-size: 12px;
  &:last-child { border-bottom: none; }
}
.exec-mark {
  width: 18px; height: 18px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; border: 1px solid;
  &.passed { color: #0f8a5c; background: #e6f7f0; border-color: #9edfc2; }
  &.failed { color: #b03a35; background: #fbefee; border-color: #e3b9b6; }
}
.exec-user {
  color: #555; flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.exec-time {
  color: #999; font-size: 11px; white-space: nowrap;
  font-family: "Space Grotesk", system-ui, sans-serif;
}

/* ============================================
   Bottom nav
   ============================================ */
.ag-nav {
  display: flex; align-items: center; justify-content: center; gap: 16px;
  margin-top: 20px; padding: 14px 16px;
  border: 1px solid var(--ark-border); background: #fff;
  &__pos {
    font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #888; padding: 4px 10px;
    border: 1px solid var(--ark-border); background: #fafaf8;
  }
}

/* ============================================
   Badges / tags
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
.ag-muted { color: #ccc; }

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
    &.is-active { color: #fff; background: #0f8a5c; border-color: #0f8a5c; &::before { background: #fff; } }
    &:disabled { color: #c9d8cf; background: #f4f8f5; border-color: #dce7e0; &::before { background: transparent; } }
  }
  &--fail {
    color: #b03a35; background: #fff; border-color: #e3b9b6;
    &::before { background: #e06060; }
    &:hover:not(:disabled) { background: #fbefee; border-color: #d9a3a0; }
    &.is-active { color: #fff; background: #b03a35; border-color: #b03a35; &::before { background: #fff; } }
    &:disabled { color: #d8c2c0; background: #faf5f4; border-color: #ecdcd9; &::before { background: transparent; } }
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
  .ag-zone, .ag-btn, .ag-block, .ag-meta, .exec-head, .ag-nav {
    transition: none !important; animation: none !important;
  }
  .ag-btn:active:not(:disabled) { transform: none; }
}

/* ============================================
   Responsive
   ============================================ */
@media (max-width: 1024px) {
  .ag-shell { padding: 16px 16px 0; }
  .detail-layout { grid-template-columns: minmax(0, 1fr) 260px; }
}
@media (max-width: 768px) {
  .ag-shell { padding: 12px 12px 0; }
  .ag-head { flex-direction: column; align-items: flex-start; }
  .ag-head__actions { width: 100%; justify-content: flex-start; }
  .ag-head__actions .ag-btn { flex: 1; }
  .ag-zone--content { padding: 14px; }
  .detail-layout { grid-template-columns: 1fr; }
  .meta-panel { position: static; }
  .exec-head { flex-direction: column; align-items: flex-start; }
  .exec-actions { width: 100%; }
  .exec-actions .ag-btn { flex: 1; }
  .ag-nav { flex-wrap: wrap; }
}
</style>
