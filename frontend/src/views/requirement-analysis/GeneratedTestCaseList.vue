<template>
  <div class="ag-shell" data-ark-theme="endfield" data-ark-depth="complex">
    <!-- Grid -->
    <div class="ag-grid" aria-hidden="true"></div>

    <!-- ====== Zone A: Header + Stats ====== -->
    <section class="ag-zone ag-zone--head">
      <header class="ag-zone__bar">
        <span class="ag-zone__kicker">INDEX / GENERATED</span>
        <span class="ag-zone__rule" aria-hidden="true"></span>
        <span class="ag-zone__code">{{ allStats.total }} RECORDS</span>
      </header>

      <!-- Stats -->
      <div class="ag-stats" v-if="allStats.total > 0">
        <div class="ag-stat">
          <span class="ag-stat__num">{{ allStats.total }}</span>
          <span class="ag-stat__label">{{ $t('generatedTestCases.totalTasks') }}</span>
        </div>
        <div class="ag-stat ag-stat--ok">
          <span class="ag-stat__num">{{ allStats.completed }}</span>
          <span class="ag-stat__label">{{ $t('generatedTestCases.completedCount') }}</span>
        </div>
        <div class="ag-stat ag-stat--run">
          <span class="ag-stat__num">{{ allStats.running }}</span>
          <span class="ag-stat__label">{{ $t('generatedTestCases.runningCount') }}</span>
        </div>
        <div class="ag-stat ag-stat--fail">
          <span class="ag-stat__num">{{ allStats.failed }}</span>
          <span class="ag-stat__label">{{ $t('generatedTestCases.failedCount') }}</span>
        </div>
      </div>

      <!-- Filter bar -->
      <div class="ag-filter-bar">
        <select v-model="selectedStatus" @change="loadTasks" class="ag-select">
          <option value="">{{ $t('generatedTestCases.allStatus') }}</option>
          <option value="pending">{{ $t('generatedTestCases.statusPending') }}</option>
          <option value="generating">{{ $t('generatedTestCases.statusGenerating') }}</option>
          <option value="reviewing">{{ $t('generatedTestCases.statusReviewing') }}</option>
          <option value="completed">{{ $t('generatedTestCases.statusCompleted') }}</option>
          <option value="failed">{{ $t('generatedTestCases.statusFailed') }}</option>
        </select>
        <div class="ag-filter-actions">
          <button v-if="selectedTasks.length > 0" class="ag-btn ag-btn--danger" @click="batchDeleteTasks" :disabled="isDeleting">
            {{ isDeleting ? $t('generatedTestCases.deleting') : $t('generatedTestCases.batchDelete', { count: selectedTasks.length }) }}
          </button>
          <button class="ag-btn" @click="loadTasks" :disabled="isLoading">
            {{ isLoading ? $t('generatedTestCases.loading') : $t('generatedTestCases.refresh') }}
          </button>
        </div>
      </div>
    </section>

    <!-- ====== Zone B: Task Table ====== -->
    <section class="ag-zone ag-zone--table">
      <div v-if="isLoading" class="ag-empty">
        <p>{{ $t('generatedTestCases.loadingTasks') }}</p>
      </div>
      <div v-else-if="tasks.length === 0" class="ag-empty">
        <div class="ag-empty__icon">ARCHIVE</div>
        <h3>{{ $t('generatedTestCases.noTasks') }}</h3>
        <p>{{ $t('generatedTestCases.emptyHint') }}<router-link to="/ai-generation/requirement-analysis">{{ $t('generatedTestCases.aiGeneration') }}</router-link>{{ $t('generatedTestCases.createTask') }}</p>
      </div>
      <div v-else class="ag-table-wrap">
        <table class="ag-table">
          <thead>
            <tr>
              <th class="ag-th ag-th--check"><input type="checkbox" @change="toggleSelectAll" :checked="isAllSelected" /></th>
              <th class="ag-th ag-th--num">#</th>
              <th class="ag-th ag-th--id">TASK ID</th>
              <th class="ag-th ag-th--req">{{ $t('generatedTestCases.requirement') }}</th>
              <th class="ag-th ag-th--status">{{ $t('generatedTestCases.status') }}</th>
              <th class="ag-th ag-th--count">{{ $t('generatedTestCases.caseCount') }}</th>
              <th class="ag-th ag-th--time">{{ $t('generatedTestCases.generationTime') }}</th>
              <th class="ag-th ag-th--act">{{ $t('generatedTestCases.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(task, index) in tasks" :key="task.task_id" class="ag-tr" :class="{ 'is-selected': isTaskSelected(task.task_id) }">
              <td class="ag-td ag-td--check"><input type="checkbox" :checked="isTaskSelected(task.task_id)" @change="toggleTaskSelection(task.task_id)" /></td>
              <td class="ag-td ag-td--num">{{ getSerialNumber(index) }}</td>
              <td class="ag-td ag-td--id">{{ task.task_id }}</td>
              <td class="ag-td ag-td--req">{{ task.title }}</td>
              <td class="ag-td ag-td--status">
                <span class="ag-badge" :class="'ag-badge--' + task.status">{{ getStatusText(task.status) }}</span>
              </td>
              <td class="ag-td ag-td--count"><span class="ag-count">{{ getTestCaseCount(task) }}</span></td>
              <td class="ag-td ag-td--time">{{ formatDateTime(task.created_at) }}</td>
              <td class="ag-td ag-td--act">
                <button class="ag-btn ag-btn--sm" @click="viewTaskDetail(task)">{{ $t('generatedTestCases.viewDetail') }}</button>
                <button v-if="task.status === 'completed'" class="ag-btn ag-btn--sm ag-btn--ok" @click="batchAdoptTask(task)">{{ $t('generatedTestCases.batchAdopt') }}</button>
                <button v-if="task.status === 'completed'" class="ag-btn ag-btn--sm ag-btn--danger" @click="batchDiscardTask(task)">{{ $t('generatedTestCases.batchDiscard') }}</button>
                <button v-if="task.status === 'failed'" class="ag-btn ag-btn--sm ag-btn--warn" @click="retryTask(task)">{{ $t('generatedTestCases.retry') }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ====== Zone C: Pagination ====== -->
    <section class="ag-zone ag-zone--page" v-if="tasks.length > 0">
      <div class="ag-page">
        <span class="ag-page__info">{{ paginationInfo }}</span>
        <div class="ag-page__ctrls">
          <select v-model="pagination.pageSize" @change="onPageSizeChange" class="ag-select ag-select--sm">
            <option v-for="size in pagination.pageSizeOptions" :key="size" :value="size">{{ size }} / page</option>
          </select>
          <div class="ag-page__btns">
            <button class="ag-btn ag-btn--sm" :disabled="pagination.currentPage <= 1" @click="goToPage(pagination.currentPage - 1)">←</button>
            <span v-for="page in getVisiblePages()" :key="page">
              <button v-if="page !== '...'" class="ag-btn ag-btn--sm ag-page__num" :class="{ 'is-active': page === pagination.currentPage }" @click="goToPage(page)">{{ page }}</button>
              <span v-else class="ag-page__dots">…</span>
            </span>
            <button class="ag-btn ag-btn--sm" :disabled="pagination.currentPage >= totalPages" @click="goToPage(pagination.currentPage + 1)">→</button>
          </div>
          <div class="ag-page__jump">
            <input v-model="jumpPage" type="number" :min="1" :max="totalPages" @keyup.enter="jumpToPage" class="ag-input--sm" />
            <button class="ag-btn ag-btn--sm" @click="jumpToPage">GO</button>
          </div>
        </div>
      </div>
    </section>

    <!-- ====== Modal: Test Case Detail ====== -->
    <div v-if="selectedTestCaseDetail" class="ag-modal" @click.self="closeTestCaseDetail">
      <div class="ag-modal__box">
        <header class="ag-modal__head">
          <span class="ag-modal__kicker">CASE / DETAIL</span>
          <button class="ag-modal__close" @click="closeTestCaseDetail">×</button>
        </header>
        <div class="ag-modal__body">
          <div class="ag-detail">
            <div class="ag-detail__row"><label>{{ $t('generatedTestCases.caseNumber') }}</label><span>{{ selectedTestCaseDetail.case_id }}</span></div>
            <div class="ag-detail__row"><label>{{ $t('generatedTestCases.relatedRequirement') }}</label><span>{{ selectedTestCaseDetail.requirement_name }} ({{ selectedTestCaseDetail.requirement_id_display }})</span></div>
            <div class="ag-detail__row"><label>{{ $t('generatedTestCases.priority') }}</label><span class="ag-badge" :class="'ag-badge--' + selectedTestCaseDetail.priority.toLowerCase()">{{ selectedTestCaseDetail.priority_display }}</span></div>
            <div class="ag-detail__row"><label>{{ $t('generatedTestCases.status') }}</label><span class="ag-badge" :class="'ag-badge--' + selectedTestCaseDetail.status">{{ selectedTestCaseDetail.status_display }}</span></div>
            <div class="ag-detail__row"><label>{{ $t('generatedTestCases.preconditions') }}</label><p>{{ selectedTestCaseDetail.precondition }}</p></div>
            <div class="ag-detail__row"><label>{{ $t('generatedTestCases.testSteps') }}</label><div class="ag-code-block" v-html="selectedTestCaseDetail.test_steps"></div></div>
            <div class="ag-detail__row"><label>{{ $t('generatedTestCases.expectedResult') }}</label><p v-html="selectedTestCaseDetail.expected_result"></p></div>
            <div class="ag-detail__row" v-if="selectedTestCaseDetail.review_comments"><label>{{ $t('generatedTestCases.reviewComments') }}</label><p>{{ selectedTestCaseDetail.review_comments }}</p></div>
            <div class="ag-detail__row"><label>{{ $t('generatedTestCases.generatedTime') }}</label><span>{{ formatDateTime(selectedTestCaseDetail.created_at) }}</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== Modal: Adopt ====== -->
    <div v-if="showAdoptModal" class="ag-modal" @click.self="closeAdoptModal">
      <div class="ag-modal__box ag-modal__box--wide">
        <header class="ag-modal__head">
          <span class="ag-modal__kicker">ADOPT / CASE</span>
          <button class="ag-modal__close" @click="closeAdoptModal">×</button>
        </header>
        <div class="ag-modal__body">
          <form class="ag-form">
            <div class="ag-form__row">
              <div class="ag-form__group"><label>{{ $t('generatedTestCases.caseTitle') }}</label><input v-model="adoptForm.title" type="text" class="ag-input" /></div>
            </div>
            <div class="ag-form__row">
              <div class="ag-form__group"><label>{{ $t('generatedTestCases.caseDescription') }}</label><textarea v-model="adoptForm.description" rows="3" class="ag-input"></textarea></div>
            </div>
            <div class="ag-form__row ag-form__row--2">
              <div class="ag-form__group"><label>{{ $t('generatedTestCases.belongsToProject') }} <span class="ag-req">*</span></label><select v-model="adoptForm.project_id" @change="onAdoptProjectChange" class="ag-select"><option value="">{{ $t('generatedTestCases.selectProject') }}</option><option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
              <div class="ag-form__group"><label>{{ $t('generatedTestCases.relatedVersion') }} <span class="ag-req">*</span></label><select v-model="adoptForm.version_id" class="ag-select"><option value="">{{ $t('generatedTestCases.selectVersion') }}</option><option v-for="v in availableVersions" :key="v.id" :value="v.id">{{ v.name }}{{ v.is_baseline ? $t('generatedTestCases.baseline') : '' }}</option></select></div>
            </div>
            <div class="ag-form__row ag-form__row--2">
              <div class="ag-form__group"><label>{{ $t('generatedTestCases.priority') }}</label><select v-model="adoptForm.priority" class="ag-select"><option value="low">{{ $t('generatedTestCases.priorityLow') }}</option><option value="medium">{{ $t('generatedTestCases.priorityMedium') }}</option><option value="high">{{ $t('generatedTestCases.priorityHigh') }}</option><option value="critical">{{ $t('generatedTestCases.priorityCritical') }}</option></select></div>
              <div class="ag-form__group"><label>{{ $t('generatedTestCases.testType') }}</label><select v-model="adoptForm.test_type" class="ag-select"><option value="functional">{{ $t('generatedTestCases.testTypeFunctional') }}</option><option value="integration">{{ $t('generatedTestCases.testTypeIntegration') }}</option><option value="api">{{ $t('generatedTestCases.testTypeAPI') }}</option><option value="ui">{{ $t('generatedTestCases.testTypeUI') }}</option><option value="performance">{{ $t('generatedTestCases.testTypePerformance') }}</option><option value="security">{{ $t('generatedTestCases.testTypeSecurity') }}</option></select></div>
            </div>
            <div class="ag-form__row">
              <div class="ag-form__group"><label>{{ $t('generatedTestCases.status') }}</label><select v-model="adoptForm.status" class="ag-select"><option value="draft">{{ $t('generatedTestCases.statusDraft') }}</option><option value="active">{{ $t('generatedTestCases.statusActive') }}</option></select></div>
            </div>
            <div class="ag-form__row">
              <div class="ag-form__group"><label>{{ $t('generatedTestCases.preconditions') }}</label><textarea v-model="adoptForm.preconditions" rows="3" class="ag-input"></textarea></div>
            </div>
            <div class="ag-form__row">
              <div class="ag-form__group"><label>{{ $t('generatedTestCases.operationSteps') }}</label><textarea v-model="adoptForm.steps" rows="6" class="ag-input ag-input--mono"></textarea></div>
            </div>
            <div class="ag-form__row">
              <div class="ag-form__group"><label>{{ $t('generatedTestCases.expectedResult') }}</label><textarea v-model="adoptForm.expected_result" rows="3" class="ag-input"></textarea></div>
            </div>
            <div class="ag-form__actions">
              <button type="button" class="ag-btn ag-btn--ok" @click="confirmAdopt" :disabled="isAdopting">{{ isAdopting ? $t('generatedTestCases.adopting') : $t('generatedTestCases.confirmAdopt') }}</button>
              <button type="button" class="ag-btn" @click="closeAdoptModal">{{ $t('generatedTestCases.cancel') }}</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage } from 'element-plus'

export default {
  name: 'GeneratedTestCaseList',
  data() { return { isLoading: false, tasks: [], selectedStatus: '', selectedTaskDetail: null, selectedTestCaseDetail: null, showAdoptModal: false, isAdopting: false, projects: [], projectVersions: [], allVersions: [], adoptForm: { title: '', description: '', project_id: null, priority: 'low', test_type: 'functional', status: 'draft', preconditions: '', steps: '', expected_result: '', version_id: null }, currentAdoptingTask: null, selectedTasks: [], isDeleting: false, pagination: { currentPage: 1, pageSize: 10, total: 0, pageSizeOptions: [10, 20, 50] }, jumpPage: '', allStats: { total: 0, completed: 0, running: 0, failed: 0 } } },
  computed: {
    availableVersions() { return this.adoptForm.project_id ? this.projectVersions : this.allVersions },
    totalPages() { return Math.ceil(this.pagination.total / this.pagination.pageSize) },
    paginationInfo() { const s = (this.pagination.currentPage - 1) * this.pagination.pageSize + 1; const e = Math.min(this.pagination.currentPage * this.pagination.pageSize, this.pagination.total); return this.$t('generatedTestCases.paginationInfo', { start: s, end: e, total: this.pagination.total }) },
    isAllSelected() { return this.tasks.length > 0 && this.selectedTasks.length === this.tasks.length }
  },
  mounted() { this.loadTasks(); this.fetchProjects(); this.fetchAllVersions() },
  methods: {
    async loadTasks() { this.isLoading = true; try { let url = '/requirement-analysis/testcase-generation/'; const params = new URLSearchParams(); params.append('page', String(this.pagination.currentPage)); params.append('page_size', String(this.pagination.pageSize)); if (this.selectedStatus) params.append('status', this.selectedStatus); if (params.toString()) url += '?' + params.toString(); const response = await api.get(url); this.tasks = response.data.results ? response.data.results : (response.data || []); this.pagination.total = response.data.count || this.tasks.length; this.updateStats() } catch (error) { this.tasks = []; this.pagination.total = 0 } finally { this.isLoading = false; this.selectedTasks = [] } },
    getSerialNumber(index) { return (this.pagination.currentPage - 1) * this.pagination.pageSize + index + 1 },
    toggleTaskSelection(taskId) { const i = this.selectedTasks.indexOf(taskId); if (i > -1) this.selectedTasks.splice(i, 1); else this.selectedTasks.push(taskId) },
    isTaskSelected(taskId) { return this.selectedTasks.includes(taskId) },
    toggleSelectAll() { this.selectedTasks = this.isAllSelected ? [] : this.tasks.map(t => t.task_id) },
    async batchDeleteTasks() { if (!this.selectedTasks.length) { ElMessage.warning(this.$t('generatedTestCases.selectTasksFirst')); return }; if (!confirm(this.$t('generatedTestCases.batchDeleteConfirm', { count: this.selectedTasks.length }))) return; this.isDeleting = true; let ok = 0, fail = 0; try { for (const id of this.selectedTasks) { try { await api.delete(`/requirement-analysis/testcase-generation/${id}/`); ok++ } catch (e) { fail++ } }; if (ok > 0) ElMessage.success(this.$t('generatedTestCases.deleteSuccess', { success: ok, failed: fail })); else ElMessage.error(this.$t('generatedTestCases.deleteFailed')); this.selectedTasks = []; this.loadTasks() } catch (e) { ElMessage.error(this.$t('generatedTestCases.batchDeleteFailed')) } finally { this.isDeleting = false } },
    updateStats() { this.loadAllStats() },
    async loadAllStats() { try { let url = '/requirement-analysis/testcase-generation/'; const params = new URLSearchParams(); params.append('page_size', '10000'); params.append('page', '1'); if (this.selectedStatus) params.append('status', this.selectedStatus); url += '?' + params.toString(); const response = await api.get(url); const all = response.data.results || response.data || []; this.allStats.total = all.length; this.allStats.completed = all.filter(t => t.status === 'completed').length; this.allStats.running = all.filter(t => ['pending', 'generating', 'reviewing'].includes(t.status)).length; this.allStats.failed = all.filter(t => t.status === 'failed').length } catch (e) { this.allStats.total = this.pagination.total || 0; this.allStats.completed = 0; this.allStats.running = 0; this.allStats.failed = 0 } },
    getStatusText(status) { const m = { pending: this.$t('generatedTestCases.statusPending'), generating: this.$t('generatedTestCases.statusGenerating'), reviewing: this.$t('generatedTestCases.statusReviewing'), completed: this.$t('generatedTestCases.statusCompleted'), failed: this.$t('generatedTestCases.statusFailed') }; return m[status] || status },
    getTestCaseCount(task) { if (!task.final_test_cases) return 0; const lines = task.final_test_cases.split('\n').filter(l => l.trim()); let rows = 0, first = true, table = false; for (let line of lines) { if (line.includes('|') && !line.includes('--------')) { const cells = line.split('|').map(c => c.trim()).filter(c => c); if (cells.length > 1) { if (first) { first = false; if (line.includes('测试用例编号') || line.includes('ID') || line.includes('用例ID') || line.includes('场景') || line.includes('步骤')) { table = true; continue } }; rows++; if (rows >= 1) table = true } } }; if (table && rows > 0) return rows; let cnt = 0; for (const line of lines) { if (line.includes('测试用例') || line.includes('Test Case') || line.match(/^(\d+\.|测试场景)/)) cnt++ }; return cnt || 0 },
    viewTaskDetail(task) { const url = this.$router.resolve({ name: 'TaskDetail', params: { taskId: task.task_id } }).href; window.open(url, '_blank') },
    async batchAdoptTask(task) { if (!confirm(this.$t('generatedTestCases.adoptConfirm', { title: task.title }))) return; try { await api.post(`/requirement-analysis/testcase-generation/${task.task_id}/batch_adopt/`); ElMessage.success(this.$t('generatedTestCases.adoptSuccess')); this.loadTasks() } catch (e) { ElMessage.error(this.$t('generatedTestCases.adoptFailed')) } },
    async batchDiscardTask(task) { if (!confirm(this.$t('generatedTestCases.discardConfirm', { title: task.title }))) return; try { await api.post(`/requirement-analysis/testcase-generation/${task.task_id}/batch_discard/`); ElMessage.success(this.$t('generatedTestCases.discardSuccess')); this.loadTasks() } catch (e) { ElMessage.error(this.$t('generatedTestCases.discardFailed')) } },
    async retryTask(task) { if (!confirm(`确认重试「${task.title}」？`)) return; try { const r = await api.post(`/requirement-analysis/testcase-generation/${task.task_id}/retry/`); ElMessage.success(r.data.message || '已启动'); this.loadTasks() } catch (e) { ElMessage.error('重试失败') } },
    formatDateTime(d) { if (!d) return ''; const dt = new Date(d); return dt.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) },
    async fetchProjects() { try { const r = await api.get('/projects/list/'); this.projects = r.data.results || [] } catch (e) {} },
    async fetchAllVersions() { try { const r = await api.get('/versions/'); this.allVersions = r.data.results || r.data || [] } catch (e) { this.allVersions = [] } },
    async fetchProjectVersions(projectId) { if (!projectId) { this.projectVersions = []; return }; try { const r = await api.get(`/versions/projects/${projectId}/versions/`); this.projectVersions = r.data || [] } catch (e) { this.projectVersions = [] } },
    async onAdoptProjectChange() { if (this.adoptForm.project_id) { await this.fetchProjectVersions(this.adoptForm.project_id); if (this.adoptForm.version_id && !this.projectVersions.some(v => v.id === this.adoptForm.version_id)) this.adoptForm.version_id = null } else { this.projectVersions = [] } },
    async confirmAdopt() { if (!this.adoptForm.project_id) { alert(this.$t('generatedTestCases.selectProjectRequired')); return }; if (!this.adoptForm.version_id) { alert(this.$t('generatedTestCases.selectVersionRequired')); return }; if (!this.adoptForm.title.trim()) { alert(this.$t('generatedTestCases.enterCaseTitle')); return }; if (!this.adoptForm.expected_result.trim()) { alert(this.$t('generatedTestCases.enterExpectedResult')); return }; this.isAdopting = true; try { await api.post('/testcases/', { title: this.adoptForm.title, description: this.adoptForm.description, project_id: this.adoptForm.project_id, priority: this.adoptForm.priority || 'low', test_type: this.adoptForm.test_type, status: this.adoptForm.status, preconditions: this.adoptForm.preconditions, steps: this.adoptForm.steps, expected_result: this.adoptForm.expected_result, version_ids: this.adoptForm.version_id ? [this.adoptForm.version_id] : [] }); alert(this.$t('generatedTestCases.adoptModalSuccess')); this.closeAdoptModal(); this.loadTestCases() } catch (e) { alert(this.$t('generatedTestCases.adoptCaseFailedRetry')) } finally { this.isAdopting = false } },
    closeAdoptModal() { this.showAdoptModal = false; this.currentAdoptingTask = null; this.projectVersions = [] },
    closeTestCaseDetail() { this.selectedTestCaseDetail = null },
    loadTestCases() { this.loadTasks() },
    getProjectName(projectId) { const p = this.projects.find(p => p.id === projectId); return p ? p.name : '' },
    onPageSizeChange() { this.pagination.currentPage = 1; this.loadTasks() },
    goToPage(page) { if (page >= 1 && page <= this.totalPages) { this.pagination.currentPage = page; this.loadTasks() } },
    jumpToPage() { const page = parseInt(this.jumpPage); if (page >= 1 && page <= this.totalPages) { this.pagination.currentPage = page; this.jumpPage = ''; this.loadTasks() } else alert(`请输入 1-${this.totalPages}`) },
    getVisiblePages() { const cur = this.pagination.currentPage, total = this.totalPages, pages = []; if (total <= 7) { for (let i = 1; i <= total; i++) pages.push(i) } else if (cur <= 4) { for (let i = 1; i <= 5; i++) pages.push(i); pages.push('...'); pages.push(total) } else if (cur >= total - 3) { pages.push(1); pages.push('...'); for (let i = total - 4; i <= total; i++) pages.push(i) } else { pages.push(1); pages.push('...'); for (let i = cur - 1; i <= cur + 1; i++) pages.push(i); pages.push('...'); pages.push(total) }; return pages }
  }
}
</script>

<style scoped lang="scss">
/* =============================================
   Ark Complex — Generated Test Cases
   ============================================= */
.ag-shell {
  --ark-ink: #191919;
  --ark-paper: #f2f2f0;
  --ark-signal: #fffa00;
  --ark-state: #00ffa2;
  --ark-border: #e4e4de;

  height: calc(100vh - 52px);
  background: #f2f2f0;
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
   Zone
   ============================================ */
.ag-zone {
  position: relative; z-index: 1;
  background: #fff;
  border: 1px solid var(--ark-border);
  &--head { flex-shrink: 0; }
  &--table { flex: 1; min-height: 0; overflow: auto; display: flex; flex-direction: column; margin: 0 0 16px; }
  &--page { flex-shrink: 0; margin-bottom: 24px; }
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
   Stats
   ============================================ */
.ag-stats {
  display: flex; gap: 0;
  padding: 16px 20px 20px;
}
.ag-stat {
  flex: 1; text-align: center;
  padding: 12px 0;
  border-right: 1px solid var(--ark-border);
  &:last-child { border-right: none; }
  &__num {
    display: block; font-size: 2.4rem; font-weight: 900;
    font-family: "Space Grotesk", system-ui, sans-serif;
    color: var(--ark-ink); line-height: 1; margin-bottom: 6px;
  }
  &__label {
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .08em; color: #999;
  }
  &--ok .ag-stat__num { color: #00bf7a; }
  &--run .ag-stat__num { color: #c8a821; }
  &--fail .ag-stat__num { color: #e06060; }
}

/* ============================================
   Filter Bar
   ============================================ */
.ag-filter-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; border-top: 1px solid var(--ark-border);
  flex-wrap: wrap; gap: 10px;
}
.ag-filter-actions { display: flex; gap: 8px; }

/* ============================================
   Select / Input
   ============================================ */
.ag-select {
  padding: 7px 28px 7px 10px; border: 1px solid #ccc; background: #fff;
  font-size: 13px; font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .04em; color: #444;
  cursor: pointer; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%23999'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 10px center;
  &:focus { outline: none; border-color: #fffa00; }
  &--sm { padding: 5px 24px 5px 8px; font-size: 11px; }
}
.ag-input {
  padding: 8px 12px; border: 1px solid #ccc; font-size: 13px; color: #333; width: 100%; box-sizing: border-box;
  &:focus { outline: none; border-color: #fffa00; }
  &--mono { font-family: "IBM Plex Mono", Consolas, monospace; font-size: 13px; line-height: 1.7; }
  &--sm { width: 48px; padding: 5px 6px; text-align: center; font-size: 12px; border: 1px solid #ccc; }
}
textarea.ag-input { resize: vertical; font-family: inherit; }

/* ============================================
   Buttons
   ============================================ */
.ag-btn {
  all: unset; cursor: pointer;
  display: inline-flex; align-items: center; gap: 4px;
  padding: 8px 16px; font-size: 12px;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .06em;
  color: #555; background: #f0f2f2; border: 1px solid #d0d2d2;
  transition: all .12s;
  &:hover:not(:disabled) { background: #e4e6e6; border-color: #bbb; }
  &:disabled { opacity: .35; cursor: not-allowed; }
  &--sm { padding: 4px 10px; font-size: 11px; }
  &--ok { color: #16803a; background: #e0f5e8; border-color: #b8dcc4; &:hover:not(:disabled) { background: #c8edcf; } }
  &--danger { color: #c03939; background: #fef0f0; border-color: #f0c8c8; &:hover:not(:disabled) { background: #fce4e4; } }
  &--warn { color: #8a6d14; background: #fefae0; border-color: #e8d888; &:hover:not(:disabled) { background: #fcf2c0; } }
}

/* ============================================
   Table
   ============================================ */
.ag-table-wrap { flex: 1; overflow: auto; }
.ag-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
  thead { border-bottom: 2px solid var(--ark-ink); }
  th, td { padding: 10px 12px; text-align: left; white-space: nowrap; }
}
.ag-th {
  font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em; color: #999; font-weight: 600;
  &--check { width: 36px; text-align: center; }
  &--num { width: 40px; text-align: right; }
  &--id { width: 170px; }
  &--req { min-width: 240px; }
  &--status { width: 90px; text-align: center; }
  &--count { width: 60px; text-align: center; }
  &--time { width: 150px; }
  &--act { width: 220px; }
}
.ag-tr {
  border-bottom: 1px solid #eee;
  transition: background .1s;
  &:hover { background: #f8fafa; }
  &.is-selected { background: #fefde8; }
  &.is-selected:hover { background: #fcf8d0; }
}
.ag-td {
  color: #444;
  &--check { text-align: center; input { accent-color: #fffa00; } }
  &--num { text-align: right; color: #aaa; font-family: "Space Grotesk", system-ui, sans-serif; font-size: 12px; }
  &--id { font-family: "IBM Plex Mono", Consolas, monospace; font-size: 12px; color: #666; }
  &--req { font-weight: 500; color: #222; min-width: 240px; max-width: 320px; white-space: normal; word-break: break-word; }
  &--status { text-align: center; }
  &--count { text-align: center; }
  &--time { color: #888; font-size: 12px; }
  &--act { display: flex; gap: 4px; }
}

/* ============================================
   Badges
   ============================================ */
.ag-badge {
  display: inline-block; padding: 2px 10px; font-size: 10px;
  font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .08em;
  font-weight: 600; border: 1px solid;
  &--pending { color: #8a6d14; background: #fefae0; border-color: #e8d888; }
  &--generating, &--reviewing { color: #0d6ea8; background: #e0f3ff; border-color: #88d0f8; }
  &--completed { color: #16803a; background: #e0f5e8; border-color: #88d4a0; }
  &--failed { color: #c03939; background: #fef0f0; border-color: #f0b0b0; }
}
.ag-count {
  display: inline-block; min-width: 24px; text-align: center;
  padding: 2px 10px; font-size: 13px; font-weight: 700;
  font-family: "Space Grotesk", system-ui, sans-serif;
  color: #191919; background: #fffa00;
}

/* ============================================
   Pagination
   ============================================ */
.ag-page {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 20px; flex-wrap: wrap; gap: 12px;
  &__info { font-size: 12px; color: #999; font-family: "Space Grotesk", system-ui, sans-serif; }
  &__ctrls { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  &__btns { display: flex; align-items: center; gap: 2px; }
  &__num.is-active { background: #fffa00; color: #191919; border-color: #fffa00; }
  &__dots { padding: 0 4px; color: #ccc; }
  &__jump { display: flex; align-items: center; gap: 4px; }
}

/* ============================================
   Empty
   ============================================ */
.ag-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 64px 20px; text-align: center; color: #aaa;
  &__icon { font-size: 24px; font-weight: 900; font-family: "Space Grotesk", system-ui, sans-serif; letter-spacing: .2em; color: #ddd; margin-bottom: 16px; }
  h3 { color: #666; margin: 0 0 8px; font-size: 16px; }
  p { font-size: 13px; color: #aaa; }
  a { color: #191919; text-decoration: underline; &:hover { color: #666; } }
}

/* ============================================
   Modal
   ============================================ */
.ag-modal {
  position: fixed; inset: 0; background: rgba(4,6,8,.72);
  display: flex; align-items: center; justify-content: center; z-index: 2000;
  &__box {
    background: #fff; width: 90%; max-width: 720px; max-height: 80vh;
    overflow-y: auto; border: 1px solid #888;
    &--wide { max-width: 860px; }
  }
  &__head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 20px; background: var(--ark-ink); color: #fff;
  }
  &__kicker {
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .14em; color: rgba(255,255,255,.7);
  }
  &__close {
    all: unset; cursor: pointer; font-size: 22px; color: rgba(255,255,255,.5); line-height: 1;
    &:hover { color: #fff; }
  }
  &__body { padding: 20px 24px 24px; }
}

/* Detail rows */
.ag-detail {
  &__row {
    margin-bottom: 16px;
    label { display: block; font-weight: 600; font-size: 12px; color: #999; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .06em; font-family: "Space Grotesk", system-ui, sans-serif; }
    span, p { font-size: 13px; color: #333; line-height: 1.6; margin: 0; }
  }
}
.ag-code-block {
  background: #f2f2f0; padding: 14px 16px; border-left: 3px solid #fffa00;
  font-size: 13px; line-height: 1.7; white-space: pre-line;
}

/* Form */
.ag-form {
  &__row { display: flex; gap: 16px; margin-bottom: 16px; &--2 > * { flex: 1; } }
  &__group {
    flex: 1; display: flex; flex-direction: column; gap: 6px;
    label { font-weight: 600; font-size: 12px; color: #666; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .04em; }
  }
  &__actions { display: flex; gap: 12px; justify-content: flex-end; padding-top: 16px; border-top: 1px solid #eee; margin-top: 16px; }
}
.ag-req { color: #e04040; }

/* ============================================
   Responsive
   ============================================ */
@media (max-width: 1024px) {
  .ag-shell { padding: 16px 16px 0; }
  .ag-stats { flex-wrap: wrap; .ag-stat { flex: 1 1 40%; border-bottom: 1px solid var(--ark-border); &:nth-child(2) { border-right: none; } } }
  .ag-th--id, .ag-td--id { display: none; }
}
@media (max-width: 768px) {
  .ag-shell { padding: 12px 12px 0; }
  .ag-stats { .ag-stat { flex: 1 1 50%; } }
  .ag-filter-bar { flex-direction: column; align-items: stretch; }
  .ag-th--time, .ag-td--time { display: none; }
  .ag-page { flex-direction: column; align-items: flex-start; }
  .ag-page__ctrls { flex-direction: column; align-items: flex-start; width: 100%; }
  .ag-modal__box { width: 95%; }
}
</style>
