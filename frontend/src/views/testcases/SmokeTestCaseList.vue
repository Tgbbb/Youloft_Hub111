<template>
  <div class="ag-shell" data-ark-theme="endfield" data-ark-depth="moderate">
    <div class="ag-grid" aria-hidden="true"></div>

    <!-- ====== Zone A: Header ====== -->
    <section class="ag-zone ag-zone--head">
      <header class="ag-zone__bar">
        <span class="ag-zone__kicker">SMOKE CASES / FIELD</span>
        <span class="ag-zone__rule" aria-hidden="true"></span>
        <span class="ag-zone__code">ARCHIVE 01</span>
      </header>
      <div class="ag-head__grid">
        <div class="ag-head__title">
          <p class="ag-head__eyebrow">冒烟测试用例 · 正向主流程</p>
          <h1 class="ag-head__h1">冒烟用例</h1>
          <p class="ag-head__meta">
            合并 / 导出 / 重新生成 · 步骤全局连续编号 · 禅道 CSV
          </p>
        </div>
        <div class="ag-head__actions">
          <button
            class="smoke-btn smoke-btn--signal"
            :disabled="!selected.length || merging"
            @click="openMerge"
          >
            <span class="smoke-btn__key">M</span>
            {{ merging ? '合并中…' : `合并选中 (${selected.length})` }}
          </button>
          <button
            class="smoke-btn"
            :disabled="!selected.length"
            @click="exportSelected"
          >
            <span class="smoke-btn__key">E</span>导出选中
          </button>
          <button class="smoke-btn" :disabled="loading" @click="loadAll">
            <span class="smoke-btn__key">R</span>刷新
          </button>
        </div>
      </div>
      <div class="ag-head__filters">
        <label class="smoke-filter">
          <span class="smoke-filter__label">项目 · PROJECT</span>
          <select v-model="projectFilter" class="smoke-select" @change="loadAll">
            <option value="">全部项目</option>
            <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </label>
      </div>
      <div class="ag-head__stats">
        <span class="ag-stat"><b>{{ list.length }}</b> 条记录</span>
        <span class="ag-stat"><b>{{ selected.length }}</b> 已勾选</span>
        <span class="ag-stat"><b>{{ totalSteps }}</b> 总步骤</span>
      </div>
    </section>

    <!-- ====== Zone B: List ====== -->
    <section class="ag-zone ag-zone--body">
      <div v-if="loading" class="ag-empty">
        <div class="ag-empty__icon" aria-hidden="true">LOADING</div>
        <h3>读取冒烟用例中</h3>
      </div>

      <div v-else-if="!list.length" class="ag-empty">
        <div class="ag-empty__icon" aria-hidden="true">EMPTY / 00</div>
        <h3>暂无冒烟测试用例</h3>
        <p>请先在「冒烟用例」生成页或任务详情页生成，再回到这里合并、导出。</p>
      </div>

      <div v-else class="ag-table-wrap">
        <el-table
          :data="list"
          row-key="id"
          class="smoke-table"
          @selection-change="onSelectionChange"
        >
          <el-table-column type="selection" width="52" />
          <el-table-column prop="title" label="用例标题" min-width="220" show-overflow-tooltip>
            <template #header>
              <span class="smoke-th">用例标题 / TITLE</span>
            </template>
            <template #default="{ row }">
              <span class="smoke-cell-title">{{ row.title }}</span>
              <span v-if="(row.merged_from_ids || []).length" class="smoke-flag">合并</span>
            </template>
          </el-table-column>
          <el-table-column label="模块" min-width="150" show-overflow-tooltip>
            <template #header><span class="smoke-th">模块 / MODULE</span></template>
            <template #default="{ row }">{{ formatModules(row.module_names) }}</template>
          </el-table-column>
          <el-table-column label="步骤数" width="86" align="center">
            <template #header><span class="smoke-th">步骤</span></template>
            <template #default="{ row }">
              <span class="smoke-cell-num">{{ (row.steps || []).length }}</span>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="110" align="center">
            <template #header><span class="smoke-th">来源</span></template>
            <template #default="{ row }">
              <span class="smoke-tag" :class="`smoke-tag--${row.source_type}`">
                {{ row.source_type_display }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #header><span class="smoke-th">状态</span></template>
            <template #default="{ row }">
              <span class="smoke-dot" :class="`smoke-dot--${row.status}`"></span>
              <span class="smoke-status">{{ row.status_display }}</span>
            </template>
          </el-table-column>
          <el-table-column label="创建人" width="110" align="center">
            <template #header><span class="smoke-th">创建人</span></template>
            <template #default="{ row }">{{ row.created_by_name }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="176" />
          <el-table-column label="操作" width="250" align="center">
            <template #header><span class="smoke-th">操作 / ACT</span></template>
            <template #default="{ row }">
              <button class="smoke-btn smoke-btn--sm" @click="openDetail(row)">查看</button>
              <button class="smoke-btn smoke-btn--sm" @click="exportOne(row)">导出</button>
              <button
                v-if="row.source_type === 'modao' || row.source_type === 'task'"
                class="smoke-btn smoke-btn--sm"
                :disabled="row.status === 'generating'"
                @click="regenerate(row)"
              >
                重生成
              </button>
              <button class="smoke-btn smoke-btn--sm smoke-btn--danger" @click="remove(row)">
                删除
              </button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <!-- ====== Dialog: Detail ====== -->
    <el-dialog :model-value="detailVisible" width="820px" :show-close="false" @close="detailVisible = false">
      <template #header>
        <div class="smoke-dialog__head">
          <span class="ag-zone__kicker">CASE / DETAIL</span>
          <h2 class="smoke-dialog__title">{{ detailTitle }}</h2>
        </div>
      </template>
      <div v-if="detailRow" class="smoke-detail">
        <div class="smoke-detail__meta">
          <span>来源 · {{ detailRow.source_type_display }}</span>
          <span>步骤数 · {{ (detailRow.steps || []).length }}</span>
          <span>创建时间 · {{ detailRow.created_at }}</span>
        </div>
        <table class="smoke-steps">
          <thead>
            <tr><th class="smoke-steps__no">编号</th><th>步骤</th><th>预期</th></tr>
          </thead>
          <tbody>
            <tr v-for="s in (detailRow.steps || [])" :key="s.no">
              <td class="smoke-steps__no">{{ s.no }}</td>
              <td class="smoke-steps__step">{{ s.step }}</td>
              <td class="smoke-steps__expect">{{ s.expected }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <template #footer>
        <button class="smoke-btn" @click="detailVisible = false">关闭</button>
        <button v-if="detailRow" class="smoke-btn smoke-btn--signal" @click="exportOne(detailRow)">
          导出 CSV
        </button>
      </template>
    </el-dialog>

    <!-- ====== Dialog: Merge ====== -->
    <el-dialog :model-value="mergeVisible" width="560px" :show-close="false" @close="mergeVisible = false">
      <template #header>
        <div class="smoke-dialog__head">
          <span class="ag-zone__kicker">MERGING / {{ selected.length }}</span>
          <h2 class="smoke-dialog__title">合并冒烟用例</h2>
        </div>
      </template>
      <div class="smoke-merge">
        <label class="smoke-field">
          <span class="smoke-field__label">合并后用例标题 · 留空沿用第一个来源标题</span>
          <input
            v-model="mergeTitleInput"
            class="smoke-input"
            placeholder="例如：心动日常v3.9.2冒烟用例"
          />
        </label>
        <p class="smoke-merge__hint">
          选中 {{ selected.length }} 条将按勾选顺序合并为一条，步骤全局重新编号，并保存为一条新记录。
        </p>
      </div>
      <template #footer>
        <button class="smoke-btn" @click="mergeVisible = false">取消</button>
        <button class="smoke-btn smoke-btn--signal" :disabled="merging" @click="doMerge">
          {{ merging ? '合并中…' : '确认合并' }}
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'

export default {
  name: 'SmokeTestCaseList',
  data() {
    return {
      loading: false,
      list: [],
      selected: [],
      detailVisible: false,
      detailRow: null,
      mergeVisible: false,
      mergeTitleInput: '',
      merging: false,
      projects: [],
      projectFilter: '',
    }
  },
  computed: {
    detailTitle() {
      return this.detailRow ? this.detailRow.title : '冒烟用例详情'
    },
    mergeTitle() {
      return `合并选中 (${this.selected.length})`
    },
    totalSteps() {
      return this.list.reduce((sum, r) => sum + (r.steps || []).length, 0)
    },
  },
  created() {
    this.loadProjects().then(() => this.loadAll())
  },
  methods: {
    async loadProjects() {
      try {
        const { data } = await api.get('/projects/')
        this.projects = data.results || data || []
      } catch (e) {
        this.projects = []
      }
    },
    async loadAll() {
      this.loading = true
      const all = []
      let page = 1
      try {
        while (true) {
          const params = { page, page_size: 100 }
          if (this.projectFilter) params.project = this.projectFilter
          const { data } = await api.get('/requirement-analysis/smoke-cases/', { params })
          const rows = data.results || []
          all.push(...rows)
          if (!data.next) break
          page += 1
        }
        this.list = all
      } catch (e) {
        ElMessage.error(e.response?.data?.error || '加载冒烟用例失败')
      } finally {
        this.loading = false
      }
    },
    onSelectionChange(rows) {
      this.selected = rows
    },
    formatModules(names) {
      const arr = names || []
      return arr.filter(Boolean).join(' / ') || '—'
    },
    openDetail(row) {
      this.detailRow = row
      this.detailVisible = true
    },
    openMerge() {
      if (!this.selected.length) return
      this.mergeTitleInput = ''
      this.mergeVisible = true
    },
    async doMerge() {
      if (this.merging) return
      this.merging = true
      try {
        const { data } = await api.post('/requirement-analysis/smoke-cases/merge/', {
          ids: this.selected.map((r) => r.id),
          title: this.mergeTitleInput || '',
        })
        this.mergeVisible = false
        ElMessage.success('合并成功，已生成新冒烟用例')
        await this.loadAll()
        this.detailRow = data
        this.detailVisible = true
      } catch (e) {
        ElMessage.error(e.response?.data?.error || '合并失败')
      } finally {
        this.merging = false
      }
    },
    exportOne(row) {
      window.open(`/api/requirement-analysis/smoke-cases/${row.id}/export/`, '_blank')
    },
    exportSelected() {
      this.selected.forEach((r, i) => {
        setTimeout(() => this.exportOne(r), i * 300)
      })
    },
    async regenerate(row) {
      try {
        await ElMessageBox.confirm('确认用该用例的模块快照重新生成并覆盖当前步骤？', '提示', {
          type: 'warning',
        })
      } catch {
        return
      }
      try {
        const { data } = await api.post(`/requirement-analysis/smoke-cases/${row.id}/regenerate/`)
        ElMessage.success('已重新生成')
        await this.loadAll()
        this.detailRow = data
        this.detailVisible = true
      } catch (e) {
        ElMessage.error(e.response?.data?.error || '重新生成失败')
      }
    },
    async remove(row) {
      try {
        await ElMessageBox.confirm(`确认删除「${row.title}」？`, '提示', { type: 'warning' })
      } catch {
        return
      }
      try {
        await api.delete(`/requirement-analysis/smoke-cases/${row.id}/`)
        ElMessage.success('已删除')
        await this.loadAll()
      } catch (e) {
        ElMessage.error(e.response?.data?.error || '删除失败')
      }
    },
  },
}
</script>

<style scoped>
/* =====================================================
   Endfield / moderate — 冒烟测试用例管理
   ===================================================== */
.ag-shell {
  position: relative;
  min-height: 100vh;
  padding: 0 clamp(16px, 4vw, 48px);
  background: var(--ark-paper);
  color: var(--ark-ink);
  font-family: var(--ark-font-cjk);
}

.ag-grid {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  opacity: 0.5;
  background-image:
    linear-gradient(rgba(0, 0, 0, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 0, 0, 0.045) 1px, transparent 1px);
  background-size: clamp(24px, 3vw, 40px) clamp(24px, 3vw, 40px);
}

.ag-zone {
  position: relative;
  z-index: 1;
}

.ag-zone--head {
  padding: 48px 0 24px;
  border-bottom: 1px solid var(--ark-neutral-300);
}

.ag-zone__bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
}

.ag-zone__kicker {
  font-family: var(--ark-font-tech);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ark-neutral-500);
}

.ag-zone__rule {
  flex: 1;
  height: 1px;
  background: var(--ark-neutral-300);
}

.ag-zone__code {
  font-family: var(--ark-font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--ark-neutral-500);
}

.ag-head__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: end;
}

.ag-head__eyebrow {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--ark-neutral-500);
}

.ag-head__h1 {
  margin: 0;
  font-size: clamp(32px, 5vw, 52px);
  font-weight: 700;
  line-height: 0.92;
  letter-spacing: -0.04em;
}

.ag-head__meta {
  margin: 12px 0 0;
  font-family: var(--ark-font-tech);
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--ark-neutral-500);
}

.ag-head__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.ag-head__filters {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 22px;
}

.smoke-filter {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.smoke-filter__label {
  font-family: var(--ark-font-tech);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--ark-neutral-500);
}

.smoke-select {
  height: 36px;
  min-width: 180px;
  padding: 0 12px;
  border: 1px solid var(--ark-neutral-300);
  border-radius: var(--ark-radius-sm);
  background: var(--ark-paper);
  color: var(--ark-ink);
  font-family: var(--ark-font-cjk);
  font-size: 13px;
}

.smoke-select:focus {
  outline: 2px solid var(--ark-signal);
  outline-offset: 1px;
  border-color: var(--ark-ink);
}

.ag-head__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  margin-top: 26px;
}

.ag-stat {
  font-family: var(--ark-font-tech);
  font-size: 12px;
  letter-spacing: 0.1em;
  color: var(--ark-neutral-500);
}

.ag-stat b {
  display: inline-block;
  margin-right: 6px;
  font-family: var(--ark-font-mono);
  font-size: 18px;
  color: var(--ark-ink);
  font-weight: 600;
}

.ag-zone--body {
  padding: 28px 0 64px;
}

/* ---------- Buttons: Endfield square ---------- */
.smoke-btn {
  --btn-bg: transparent;
  --btn-ink: var(--ark-ink);
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid var(--ark-neutral-300);
  border-radius: var(--ark-radius-sm);
  background: var(--btn-bg);
  color: var(--btn-ink);
  font-family: var(--ark-font-cjk);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease;
}

.smoke-btn:disabled {
  opacity: 0.42;
  cursor: not-allowed;
}

.smoke-btn:hover:not(:disabled) {
  border-color: var(--ark-ink);
}

.smoke-btn:focus-visible,
.smoke-input:focus-visible {
  outline: 2px solid var(--ark-signal);
  outline-offset: 2px;
}

.smoke-btn__key {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid currentColor;
  border-radius: 2px;
  font-family: var(--ark-font-tech);
  font-size: 10px;
  letter-spacing: 0.04em;
  opacity: 0.7;
}

.smoke-btn--signal {
  --btn-bg: var(--ark-ink);
  --btn-ink: var(--ark-paper);
  border-color: var(--ark-ink);
  padding-left: 20px;
}

.smoke-btn--signal::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 5px;
  background: var(--ark-signal);
}

.smoke-btn--signal:hover:not(:disabled) {
  background: var(--ark-signal);
  border-color: var(--ark-ink);
  color: var(--ark-ink);
}

.smoke-btn--sm {
  min-height: 30px;
  padding: 0 10px;
  font-size: 12px;
}

.smoke-btn--sm .smoke-btn__key {
  display: none;
}

.smoke-btn--danger {
  color: #d03050;
  border-color: #d03050;
}

.smoke-btn--danger:hover:not(:disabled) {
  background: #fff1f0;
  border-color: #d03050;
}

/* ---------- Table: Endfield ---------- */
.ag-table-wrap {
  border: 1px solid var(--ark-neutral-300);
}

.smoke-table {
  --el-table-border-color: var(--ark-neutral-300);
  --el-table-header-bg-color: var(--ark-neutral-200);
  --el-table-row-hover-bg-color: rgba(255, 250, 0, 0.08);
  --el-table-current-row-bg-color: rgba(255, 250, 0, 0.13);
  /* checkbox → Endfield tokens（用 EP 变量，避免破坏对勾） */
  --el-checkbox-bg-color: var(--ark-paper);
  --el-checkbox-input-border-color: var(--ark-neutral-500);
  --el-checkbox-input-border-color-hover: var(--ark-ink);
  --el-checkbox-checked-bg-color: var(--ark-ink);
  --el-checkbox-checked-input-border-color: var(--ark-ink);
  --el-checkbox-checked-icon-color: var(--ark-paper);
  --el-checkbox-border-radius: 2px;
  font-family: var(--ark-font-cjk);
}

.smoke-table :deep(.el-table__header th) {
  height: 44px;
  background: var(--ark-neutral-200);
  border-bottom: 1px solid var(--ark-neutral-300);
  font-family: var(--ark-font-tech);
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ark-neutral-700);
}

.smoke-table :deep(.el-table__row td) {
  height: 52px;
  border-bottom: 1px solid var(--ark-neutral-300);
  color: var(--ark-ink);
}

.smoke-table :deep(.el-table__row:hover td) {
  box-shadow: inset 3px 0 0 var(--ark-signal);
}

.smoke-th {
  font-family: var(--ark-font-tech);
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--ark-neutral-700);
}

.smoke-cell-title {
  font-weight: 600;
}

.smoke-flag {
  margin-left: 8px;
  padding: 1px 6px;
  border: 1px solid var(--ark-signal);
  color: var(--ark-ink);
  background: rgba(255, 250, 0, 0.28);
  font-size: 11px;
}

.smoke-cell-num {
  font-family: var(--ark-font-mono);
  font-size: 15px;
  color: var(--ark-ink);
}

.smoke-tag {
  display: inline-block;
  padding: 2px 8px;
  border: 1px solid var(--ark-neutral-300);
  border-radius: 2px;
  font-family: var(--ark-font-tech);
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--ark-neutral-700);
}

.smoke-tag--modao { background: rgba(255, 250, 0, 0.16); }
.smoke-tag--task { background: rgba(0, 255, 162, 0.12); }
.smoke-tag--manual { background: var(--ark-neutral-200); }

.smoke-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 7px;
  border-radius: 50%;
  background: var(--ark-neutral-500);
}

.smoke-dot--completed { background: var(--ark-state); }
.smoke-dot--generating { background: var(--ark-signal); }
.smoke-dot--failed { background: #d03050; }

.smoke-status {
  font-size: 12px;
  color: var(--ark-neutral-700);
}

/* ---------- Empty ---------- */
.ag-empty {
  padding: 72px 24px;
  text-align: center;
  border: 1px dashed var(--ark-neutral-300);
}

.ag-empty__icon {
  font-family: var(--ark-font-mono);
  font-size: 24px;
  letter-spacing: 0.14em;
  color: var(--ark-neutral-300);
  margin-bottom: 16px;
}

.ag-empty h3 {
  margin: 0 0 8px;
  font-size: 18px;
}

.ag-empty p {
  margin: 0;
  color: var(--ark-neutral-500);
  font-size: 14px;
}

/* ---------- Dialogs: Endfield panel ---------- */
.smoke-dialog__head {
  border-bottom: 1px solid var(--ark-neutral-300);
  padding-bottom: 12px;
}

.smoke-dialog__title {
  margin: 6px 0 0;
  font-size: 20px;
  line-height: 1;
  letter-spacing: -0.02em;
}

:deep(.el-dialog) {
  border-radius: 0;
  border: 1px solid var(--ark-neutral-300);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
}

:deep(.el-dialog__body) {
  color: var(--ark-ink);
}

:deep(.el-dialog__footer) {
  border-top: 1px solid var(--ark-neutral-300);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.smoke-detail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 16px;
  font-family: var(--ark-font-tech);
  font-size: 12px;
  letter-spacing: 0.06em;
  color: var(--ark-neutral-500);
}

.smoke-steps {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.smoke-steps th,
.smoke-steps td {
  border: 1px solid var(--ark-neutral-300);
  padding: 10px 12px;
  text-align: left;
  vertical-align: top;
}

.smoke-steps th {
  background: var(--ark-neutral-200);
  font-family: var(--ark-font-tech);
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ark-neutral-700);
}

.smoke-steps__no {
  width: 60px;
  text-align: center;
  font-family: var(--ark-font-mono);
  color: var(--ark-neutral-500);
}

.smoke-steps__step {
  width: 34%;
}

.smoke-steps__expect {
  width: 38%;
}

/* ---------- Merge form ---------- */
.smoke-merge {
  padding: 4px 0 8px;
}

.smoke-field {
  display: block;
}

.smoke-field__label {
  display: block;
  margin-bottom: 8px;
  font-family: var(--ark-font-tech);
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--ark-neutral-500);
}

.smoke-input {
  width: 100%;
  height: 44px;
  padding: 0 14px;
  border: 1px solid var(--ark-neutral-300);
  border-radius: var(--ark-radius-sm);
  background: var(--ark-paper);
  color: var(--ark-ink);
  font-family: var(--ark-font-cjk);
  font-size: 14px;
}

.smoke-input:focus {
  outline: none;
  border-color: var(--ark-ink);
  box-shadow: 0 0 0 2px var(--ark-signal);
}

.smoke-merge__hint {
  margin: 16px 0 0;
  padding: 12px 14px;
  border-left: 3px solid var(--ark-signal);
  background: var(--ark-neutral-100);
  color: var(--ark-neutral-700);
  font-size: 13px;
  line-height: 1.6;
}

/* ---------- Responsive ---------- */
@media (max-width: 760px) {
  .ag-head__grid {
    grid-template-columns: 1fr;
    align-items: start;
  }
  .ag-head__actions {
    justify-content: flex-start;
  }
  .ag-zone__code {
    display: none;
  }
  .ag-table-wrap {
    overflow-x: auto;
  }
  .smoke-table {
    min-width: 860px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .smoke-btn,
  .smoke-table :deep(.el-table__row td) {
    transition: none;
  }
}
</style>
