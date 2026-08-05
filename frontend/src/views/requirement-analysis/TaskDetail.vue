<template>
  <div class="ag-shell" data-ark-theme="endfield" data-ark-depth="moderate">
    <!-- Grid -->
    <div class="ag-grid" aria-hidden="true"></div>

    <!-- ====== Zone A: Header ====== -->
    <section class="ag-zone ag-zone--head">
      <header class="ag-zone__bar">
        <span class="ag-zone__kicker">TASK / DETAIL</span>
        <span class="ag-zone__rule" aria-hidden="true"></span>
        <span class="ag-zone__code">{{ taskId }}</span>
      </header>
      <div class="ag-head">
        <div class="ag-head__main">
          <h1 class="ag-head__title">{{ $t('taskDetail.title') }}<span v-if="task.title" class="ag-head__sub"> — {{ task.title }}</span></h1>
          <div class="ag-head__meta">
            <span class="ag-head__id">{{ $t('taskDetail.taskId') }}: {{ taskId }}</span>
            <span class="ag-badge" :class="'ag-badge--' + task.status">{{ getStatusText(task.status) }}</span>
          </div>
        </div>
        <div class="ag-head__actions">
          <button
            v-if="testCases.length > 0"
            class="ag-btn ag-btn--ok"
            @click="exportToExcel"
            :disabled="isExporting">
            {{ isExporting ? $t('taskDetail.exporting') : $t('taskDetail.exportBtn') }}
          </button>
        </div>
      </div>
    </section>

    <!-- ====== Zone B: Requirement ====== -->
    <section class="ag-zone ag-zone--req" v-if="task.requirement_text">
      <details class="ag-req">
        <summary class="ag-req__head">
          <span class="ag-req__title">{{ $t('taskDetail.requirementTitle') }}</span>
          <span class="ag-req__hint">{{ $t('taskDetail.requirementHint') }}</span>
        </summary>
        <div class="ag-req__body">
          <div class="ag-req__text">{{ task.requirement_text }}</div>
          <div class="ag-req__actions">
            <button class="ag-btn ag-btn--sm ag-btn--ghost" @click="copyRequirementText">
              <el-icon><DocumentCopy /></el-icon>
              {{ $t('taskDetail.copyRequirement') }}
            </button>
          </div>
        </div>
      </details>
    </section>

    <!-- ====== Zone C: Content ====== -->
    <section class="ag-zone ag-zone--content">
      <div v-if="isLoading" class="ag-empty">
        <p>{{ $t('taskDetail.loading') }}</p>
      </div>

      <div v-else-if="!task.task_id" class="ag-empty">
        <div class="ag-empty__icon">404</div>
        <h3>{{ $t('taskDetail.taskNotExist') }}</h3>
        <router-link to="/ai-generation/generated-testcases">{{ $t('taskDetail.backToList') }}</router-link>
      </div>

      <div v-else class="ag-content">
        <!-- Batch bar -->
        <div class="ag-batch" v-if="testCases.length > 0">
          <div class="ag-batch__select">
            <label class="ag-check">
              <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll">
              {{ $t('taskDetail.selectAll') }}
            </label>
            <span class="ag-batch__count" v-if="selectedCases.length > 0">
              {{ $t('taskDetail.selectedCount', { count: selectedCases.length }) }}
            </span>
          </div>
          <div class="ag-batch__actions">
            <button class="ag-btn ag-btn--ok" :disabled="selectedCases.length === 0" @click="batchAdopt">
              {{ $t('taskDetail.batchAdopt', { count: selectedCases.length }) }}
            </button>
            <button class="ag-btn ag-btn--danger" :disabled="selectedCases.length === 0" @click="batchDiscard">
              {{ $t('taskDetail.batchDiscard', { count: selectedCases.length }) }}
            </button>
          </div>
        </div>

        <!-- Table -->
        <div class="ag-table-wrap" v-if="testCases.length > 0">
          <table class="ag-table">
            <thead>
              <tr>
                <th class="ag-th ag-th--check">{{ $t('taskDetail.tableSelect') }}</th>
                <th class="ag-th ag-th--id">{{ $t('taskDetail.tableCaseId') }}</th>
                <th class="ag-th ag-th--scenario">{{ $t('taskDetail.tableScenario') }}</th>
                <th class="ag-th">{{ $t('taskDetail.tablePrecondition') }}</th>
                <th class="ag-th">{{ $t('taskDetail.tableSteps') }}</th>
                <th class="ag-th">{{ $t('taskDetail.tableExpected') }}</th>
                <th class="ag-th ag-th--prio">{{ $t('taskDetail.tablePriority') }}</th>
                <th class="ag-th ag-th--act">{{ $t('taskDetail.tableActions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(testCase, index) in paginatedTestCases" :key="testCase.id || index" class="ag-tr">
                <td class="ag-td ag-td--check">
                  <input type="checkbox" :value="testCase" v-model="selectedCases" @change="updateSelectAll">
                </td>
                <td class="ag-td ag-td--id">{{ testCase.caseId || `TC${String(index + 1).padStart(3, '0')}` }}</td>
                <td class="ag-td ag-td--scenario">{{ testCase.scenario }}</td>
                <td class="ag-td"><div class="ag-clamp">{{ formatTextForList(testCase.precondition) }}</div></td>
                <td class="ag-td"><div class="ag-clamp">{{ formatTextForList(testCase.steps) }}</div></td>
                <td class="ag-td"><div class="ag-clamp">{{ formatTextForList(testCase.expected) }}</div></td>
                <td class="ag-td ag-td--prio">
                  <span class="ag-prio" :class="'ag-prio--' + (testCase.priority || 'P2').toLowerCase()">{{ testCase.priority || 'P2' }}</span>
                </td>
                <td class="ag-td ag-td--act">
                  <div class="ag-actions">
                    <button class="ag-btn ag-btn--sm" @click="viewCaseDetail(testCase, index)">{{ $t('taskDetail.viewDetail') }}</button>
                    <button class="ag-btn ag-btn--sm ag-btn--ok" @click="adoptSingleCase(testCase, index)">{{ $t('taskDetail.adopt') }}</button>
                    <button class="ag-btn ag-btn--sm ag-btn--danger" @click="discardSingleCase(testCase, index)">{{ $t('taskDetail.discard') }}</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-else class="ag-empty">
          <div class="ag-empty__icon">ARCHIVE</div>
          <h3>{{ $t('taskDetail.emptyTitle') }}</h3>
          <p>{{ $t('taskDetail.emptyHint') }}</p>
        </div>

        <!-- Pagination -->
        <div class="ag-page" v-if="testCases.length > 0">
          <span class="ag-page__info">
            {{ $t('taskDetail.paginationInfo', { start: paginationStart, end: paginationEnd, total: testCases.length }) }}
          </span>
          <div class="ag-page__ctrls">
            <div class="ag-page__size">
              <span class="ag-page__label">{{ $t('taskDetail.pageSizeLabel') }}</span>
              <select v-model="pageSize" @change="currentPage = 1" class="ag-select ag-select--sm">
                <option value="10">{{ $t('taskDetail.pageSizeOption', { size: 10 }) }}</option>
                <option value="20">{{ $t('taskDetail.pageSizeOption', { size: 20 }) }}</option>
                <option value="50">{{ $t('taskDetail.pageSizeOption', { size: 50 }) }}</option>
              </select>
            </div>
            <div class="ag-page__btns">
              <button class="ag-btn ag-btn--sm" :disabled="currentPage <= 1" @click="currentPage--">{{ $t('taskDetail.previousPage') }}</button>
              <span class="ag-page__current">{{ $t('taskDetail.currentPageInfo', { current: currentPage, total: totalPages }) }}</span>
              <button class="ag-btn ag-btn--sm" :disabled="currentPage >= totalPages" @click="currentPage++">{{ $t('taskDetail.nextPage') }}</button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ====== Modal: Case Detail ====== -->
    <div v-if="showCaseDetail" class="ag-modal" @click.self="closeCaseDetail">
      <div class="ag-modal__box">
        <header class="ag-modal__head">
          <span class="ag-modal__kicker">{{ isEditing ? 'CASE / EDIT' : 'CASE / DETAIL' }}</span>
          <button class="ag-modal__close" @click="closeCaseDetail">×</button>
        </header>

        <!-- View mode -->
        <div v-if="!isEditing" class="ag-modal__body">
          <div class="ag-detail">
            <div class="ag-detail__row"><label>{{ $t('taskDetail.labelCaseId') }}</label><span>{{ selectedCase.caseId || `TC${String(selectedCaseIndex + 1).padStart(3, '0')}` }}</span></div>
            <div class="ag-detail__row"><label>{{ $t('taskDetail.labelScenario') }}</label><p v-html="formatMarkdown(selectedCase.scenario)"></p></div>
            <div class="ag-detail__row"><label>{{ $t('taskDetail.labelPrecondition') }}</label><p v-html="formatMarkdown(selectedCase.precondition || $t('taskDetail.labelNone'))"></p></div>
            <div class="ag-detail__row"><label>{{ $t('taskDetail.labelSteps') }}</label><div class="ag-code-block" v-html="formatMarkdown(selectedCase.steps)"></div></div>
            <div class="ag-detail__row"><label>{{ $t('taskDetail.labelExpected') }}</label><p v-html="formatMarkdown(selectedCase.expected)"></p></div>
            <div class="ag-detail__row"><label>{{ $t('taskDetail.labelPriority') }}</label><span class="ag-prio" :class="'ag-prio--' + (selectedCase.priority || 'P2').toLowerCase()">{{ selectedCase.priority || 'P2' }}</span></div>
          </div>
        </div>

        <!-- Edit mode -->
        <div v-else class="ag-modal__body">
          <div class="ag-form">
            <div class="ag-form__group"><label>{{ $t('taskDetail.labelCaseId') }}</label><span class="ag-form__readonly">{{ editForm.caseId || `TC${String(selectedCaseIndex + 1).padStart(3, '0')}` }}</span></div>
            <div class="ag-form__group"><label>{{ $t('taskDetail.labelScenario') }}</label><el-input v-model="editForm.scenario" type="textarea" :rows="2" :placeholder="$t('taskDetail.placeholderScenario')" /></div>
            <div class="ag-form__group"><label>{{ $t('taskDetail.labelPrecondition') }}</label><el-input v-model="editForm.precondition" type="textarea" :rows="3" :placeholder="$t('taskDetail.placeholderPrecondition')" /></div>
            <div class="ag-form__group"><label>{{ $t('taskDetail.labelSteps') }}</label><el-input v-model="editForm.steps" type="textarea" :rows="6" :placeholder="$t('taskDetail.placeholderSteps')" /></div>
            <div class="ag-form__group"><label>{{ $t('taskDetail.labelExpected') }}</label><el-input v-model="editForm.expected" type="textarea" :rows="4" :placeholder="$t('taskDetail.placeholderExpected')" /></div>
            <div class="ag-form__group"><label>{{ $t('taskDetail.labelPriority') }}</label>
              <el-select v-model="editForm.priority" :placeholder="$t('taskDetail.placeholderPriority')">
                <el-option label="P0" value="P0"></el-option>
                <el-option label="P1" value="P1"></el-option>
                <el-option label="P2" value="P2"></el-option>
                <el-option label="P3" value="P3"></el-option>
              </el-select>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <footer class="ag-modal__foot">
          <template v-if="!isEditing">
            <button class="ag-btn ag-btn--ghost" @click="closeCaseDetail">{{ $t('taskDetail.btnClose') }}</button>
            <button class="ag-btn ag-btn--ok" @click="startEdit">{{ $t('taskDetail.btnEdit') }}</button>
          </template>
          <template v-else>
            <button class="ag-btn ag-btn--ghost" @click="cancelEdit" :disabled="isSaving">{{ $t('taskDetail.btnCancel') }}</button>
            <button class="ag-btn ag-btn--ok" @click="saveEdit" :disabled="isSaving">
              {{ isSaving ? $t('taskDetail.btnSaveing') : $t('taskDetail.btnSave') }}
            </button>
          </template>
        </footer>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DocumentCopy } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'

export default {
  name: 'TaskDetail',
  data() {
    return {
      taskId: '',
      task: {},
      testCases: [],
      selectedCases: [],
      isLoading: true,
      showCaseDetail: false,
      selectedCase: {},
      selectedCaseIndex: 0,
      currentPage: 1,
      pageSize: 10,
      isExporting: false,
      // 编辑相关状态
      isEditing: false,
      isSaving: false,
      editForm: {
        caseId: '',
        scenario: '',
        precondition: '',
        steps: '',
        expected: '',
        priority: 'P2'
      }
    }
  },

  computed: {
    isAllSelected() {
      return this.testCases.length > 0 && this.selectedCases.length === this.testCases.length
    },

    totalPages() {
      return Math.ceil(this.testCases.length / this.pageSize)
    },

    paginatedTestCases() {
      const start = (this.currentPage - 1) * this.pageSize
      const end = start + this.pageSize
      return this.testCases.slice(start, end)
    },

    paginationStart() {
      return (this.currentPage - 1) * this.pageSize + 1
    },

    paginationEnd() {
      return Math.min(this.currentPage * this.pageSize, this.testCases.length)
    }
  },

  mounted() {
    this.taskId = this.$route.params.taskId
    this.loadTaskDetail()
  },

  methods: {
    // 复制需求描述文本
    async copyRequirementText() {
      try {
        await navigator.clipboard.writeText(this.task.requirement_text)
        ElMessage.success(this.$t('taskDetail.copySuccess'))
      } catch (error) {
        // 如果 navigator.clipboard 不可用，使用备用方法
        const textArea = document.createElement('textarea')
        textArea.value = this.task.requirement_text
        textArea.style.position = 'fixed'
        textArea.style.opacity = '0'
        document.body.appendChild(textArea)
        textArea.select()
        try {
          document.execCommand('copy')
          ElMessage.success(this.$t('taskDetail.copySuccess'))
        } catch (err) {
          ElMessage.error(this.$t('taskDetail.copyFailed'))
        }
        document.body.removeChild(textArea)
      }
    },

    async loadTaskDetail() {
      try {
        // 获取任务基本信息
        const taskResponse = await api.get(`/requirement-analysis/testcase-generation/${this.taskId}/`)
        this.task = taskResponse.data

        // 未完成且有澄清问题 → 跳回需求分析页恢复流程
        if (this.task.status !== 'completed' && this.task.clarification_questions?.length > 0) {
          this.$router.push({ name: 'RequirementAnalysis', query: { taskId: this.taskId } })
          return
        }

        // 解析最终测试用例
        if (this.task.final_test_cases) {
          this.testCases = this.parseTestCases(this.task.final_test_cases)
        }
      } catch (error) {
        console.error('Failed to load task details:', error)
        ElMessage.error(this.$t('taskDetail.loadFailed'))
      } finally {
        this.isLoading = false
      }
    },

    parseTestCases(content) {
      // 复用RequirementAnalysisView中的解析逻辑
      if (!content) return []

      // 去除markdown加粗标记，保留纯净文本
      let cleanContent = content.replace(/\*\*([^*]+)\*\*/g, '$1')

      const lines = cleanContent.split('\n').filter(line => line.trim())
      const testCases = []

      // 尝试解析表格格式
      let isTableFormat = false
      const tableData = []

      for (let line of lines) {
        const trimmedLine = line.trim()
        if (trimmedLine.includes('|') && !trimmedLine.includes('--------')) {
          const cells = trimmedLine.split('|').map(cell => cell.trim()).filter(cell => cell)
          if (cells.length > 1) {
            tableData.push(cells)
            isTableFormat = true
          }
        }
      }
      
      if (isTableFormat && tableData.length > 1) {
        // 表格格式解析 — 检测第一行是否为表头
        const firstRow = tableData[0]
        const headerKeywords = ['用例id', '测试目标', '测试场景', '优先级', 'id', '编号', 'caseid', 'priority']
        const isHeaderRow = firstRow.some(cell => {
          const c = cell.trim().toLowerCase()
          return headerKeywords.some(kw => c === kw || c.includes(kw))
        })

        let headers, startIndex
        if (isHeaderRow) {
          headers = firstRow
          startIndex = 1
        } else {
          // 兜底：无表头行，按8列位置硬解析
          headers = ['用例ID', '测试目标', '前置条件', '操作步骤', '预期结果', '优先级', '测试类型', '关联需求']
          startIndex = 0
        }

        for (let i = startIndex; i < tableData.length; i++) {
          const row = tableData[i]
          const testCase = {}

          // 清理<br>标签的辅助函数
          const cleanBrTags = (text) => {
            if (!text) return ''
            return text.replace(/<br\s*\/?>/gi, '\n')
          }

          headers.forEach((header, index) => {
            const value = cleanBrTags(row[index] || '')

            // 使用更精确的匹配逻辑，避免误判
            const cleanHeader = header.trim().toLowerCase()

            // 优先级匹配，避免误判
            if (cleanHeader === '优先级' || cleanHeader === 'priority' || cleanHeader === 'priority（优先级）' || cleanHeader === '优先级（priority）') {
              testCase.priority = value
            } else if (cleanHeader === '用例id' || cleanHeader === '编号' || cleanHeader === 'id' || cleanHeader.includes('用例id')) {
              testCase.caseId = value
            } else if (cleanHeader === '测试目标' || cleanHeader === '测试场景' || cleanHeader === '场景' || cleanHeader === '标题' || cleanHeader.includes('测试目标')) {
              testCase.scenario = value
            } else if (cleanHeader === '前置条件' || cleanHeader === '前置' || cleanHeader === '前提条件') {
              testCase.precondition = value
            } else if (cleanHeader === '测试步骤' || cleanHeader === '操作步骤' || cleanHeader === '步骤') {
              // 确保不要误匹配"预期结果"中包含的"步骤"字样
              if (!cleanHeader.includes('预期') && !cleanHeader.includes('结果')) {
                testCase.steps = value
              }
            } else if (cleanHeader === '预期结果' || cleanHeader === '预期' || cleanHeader === '结果' || cleanHeader.includes('预期结果')) {
              testCase.expected = value
            }
          })

          if (testCase.scenario || testCase.caseId) {
            // If steps field is empty, use scenario as default
            if (!testCase.steps && testCase.scenario) {
              testCase.steps = testCase.scenario
            }
            // 如果没有priority，设置默认值
            if (!testCase.priority) {
              testCase.priority = 'P2'
            }
            testCases.push(testCase)
          }
        }
      } else {
        // 结构化文本格式解析
        let currentTestCase = {}
        let caseNumber = 1
        
        for (const line of lines) {
          if (line.includes('测试用例') || line.includes('Test Case') || 
              line.match(/^(\d+\.|\*|\-|\d+、)/)) {
            
            if (Object.keys(currentTestCase).length > 0) {
              testCases.push(currentTestCase)
              caseNumber++
            }
            
            currentTestCase = {
              caseId: `TC${String(caseNumber).padStart(3, '0')}`,
              scenario: line.replace(/^(\d+\.|\*|\-|\d+、)\s*/, '').replace(/测试用例\d*[:：]?\s*/, '').replace(/Test Case\s*\d*[:：]?\s*/i, ''),
              precondition: '',
              steps: '',
              expected: '',
              priority: 'P2'
            }
          } else if (line.includes('前置条件') || line.includes('前提')) {
            currentTestCase.precondition = line.replace(/.*?[:：]\s*/, '')
          } else if (line.includes('测试步骤') || line.includes('操作步骤') || line.includes('步骤')) {
            currentTestCase.steps = line.replace(/.*?[:：]\s*/, '')
          } else if (line.includes('预期结果') || line.includes('Expected')) {
            currentTestCase.expected = line.replace(/.*?[:：]\s*/, '')
          } else if (line.includes('优先级')) {
            currentTestCase.priority = line.replace(/.*?[:：]\s*/, '')
          }
        }
        
        if (Object.keys(currentTestCase).length > 0) {
          testCases.push(currentTestCase)
        }
      }
      
      return testCases
    },

    getStatusText(status) {
      if (!status) return ''
      const statusKey = 'status' + status.charAt(0).toUpperCase() + status.slice(1)
      return this.$t('taskDetail.' + statusKey) || status
    },

    // 格式化列表中的文本，将<br>转换为换行
    formatTextForList(text) {
      if (!text) return ''
      // 将<br>、<br/>、<br />等标签替换为换行符
      return text.replace(/<br\s*\/?>/gi, '\n')
    },

    // 格式化文本，去除markdown标记并保留格式
    formatMarkdown(text) {
      if (!text) return ''

      // 先转义HTML标签，防止XSS
      let formatted = text.replace(/&/g, '&amp;')
                         .replace(/</g, '&lt;')
                         .replace(/>/g, '&gt;')

      // 去除markdown加粗标记 **text**，保留纯文本
      formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '$1')

      // 转换换行符为<br>
      formatted = formatted.replace(/\n/g, '<br>')

      return formatted
    },

    toggleSelectAll() {
      if (this.isAllSelected) {
        this.selectedCases = []
      } else {
        this.selectedCases = [...this.testCases]
      }
    },

    updateSelectAll() {
      // 这个方法会在单个checkbox变化时触发，用于更新全选状态
      // Vue的v-model会自动处理selectedCases数组的更新
    },

    async batchAdopt() {
      if (this.selectedCases.length === 0) {
        ElMessage.warning(this.$t('taskDetail.pleaseSelectFirst', { action: this.$t('taskDetail.adopt') }))
        return
      }

      try {
        await ElMessageBox.confirm(
          this.$t('taskDetail.confirmAdopt', { count: this.selectedCases.length }),
          this.$t('taskDetail.confirmAdoptTitle'),
          {
            confirmButtonText: this.$t('taskDetail.btnConfirm'),
            cancelButtonText: this.$t('taskDetail.btnCancelOperation'),
            type: 'success',
            customClass: 'ag-confirm'
          }
        )
      } catch {
        return
      }

      try {
        const casesData = this.selectedCases.map((testCase, index) => ({
          title: testCase.scenario || `Test Case ${index + 1}`,
          description: testCase.scenario || '',
          preconditions: testCase.precondition || '',
          steps: testCase.steps || '',
          expected_result: testCase.expected || '',
          priority: this.mapPriority(testCase.priority),
          test_type: 'functional',
          status: 'draft'
        }))

        await api.post(`/requirement-analysis/testcase-generation/${this.taskId}/batch-adopt-selected/`, {
          test_cases: casesData
        })

        ElMessage.success(this.$t('taskDetail.adoptSuccess', { count: this.selectedCases.length }))
        this.selectedCases = []

        // Keep adopted cases in the list for multiple adoptions
        // this.testCases = this.testCases.filter(tc => !this.selectedCases.includes(tc))

      } catch (error) {
        console.error('Batch adopt failed:', error)
        ElMessage.error(this.$t('taskDetail.batchAdoptFailed') + ': ' + (error.response?.data?.message || error.message))
      }
    },

    async batchDiscard() {
      if (this.selectedCases.length === 0) {
        ElMessage.warning(this.$t('taskDetail.pleaseSelectFirst', { action: this.$t('taskDetail.discard') }))
        return
      }

      try {
        await ElMessageBox.confirm(
          this.$t('taskDetail.confirmDiscard', { count: this.selectedCases.length }),
          this.$t('taskDetail.confirmDiscardTitle'),
          {
            confirmButtonText: this.$t('taskDetail.btnConfirm'),
            cancelButtonText: this.$t('taskDetail.btnCancelOperation'),
            type: 'warning',
            confirmButtonClass: 'el-button--danger',
            customClass: 'ag-confirm'
          }
        )
      } catch {
        return
      }

      try {
        // 获取选中用例的全局索引（不是分页索引）
        const caseIndices = this.selectedCases.map(selectedCase => {
          // 在完整列表中查找索引
          const globalIndex = this.testCases.findIndex(tc =>
            tc.scenario === selectedCase.scenario &&
            tc.steps === selectedCase.steps &&
            tc.expected === selectedCase.expected
          )
          return globalIndex
        }).filter(index => index !== -1) // 过滤掉未找到的(-1)

        const response = await api.post(`/requirement-analysis/testcase-generation/${this.taskId}/discard-selected-cases/`, {
          case_indices: caseIndices
        })

        if (response.data.task_deleted) {
          ElMessage.success(this.$t('taskDetail.allDiscardedSuccess'))
          // 返回到AI生成用例记录列表
          this.$router.push('/generated-testcases')
        } else {
          ElMessage.success(this.$t('taskDetail.discardSuccess', { count: response.data.discarded_count }))

          // 重新解析更新后的测试用例
          if (response.data.updated_test_cases) {
            this.testCases = this.parseTestCases(response.data.updated_test_cases)
            this.selectedCases = []
            this.currentPage = 1 // 重置到第一页
          }
        }

      } catch (error) {
        console.error('Batch discard failed:', error)
        ElMessage.error(this.$t('taskDetail.batchDiscardFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    viewCaseDetail(testCase, index) {
      this.selectedCase = testCase
      this.selectedCaseIndex = index
      this.showCaseDetail = true
    },

    closeCaseDetail() {
      this.showCaseDetail = false
      this.selectedCase = {}
      this.isEditing = false
      this.editForm = {
        caseId: '',
        scenario: '',
        precondition: '',
        steps: '',
        expected: '',
        priority: 'P2'
      }
    },

    // 开始编辑
    startEdit() {
      this.isEditing = true

      this.editForm = {
        caseId: this.selectedCase.caseId || '',
        scenario: this.selectedCase.scenario || '',
        // 将<br>转换为换行符以便编辑
        precondition: this.convertBrToNewline(this.selectedCase.precondition || ''),
        steps: this.convertBrToNewline(this.selectedCase.steps || ''),
        expected: this.convertBrToNewline(this.selectedCase.expected || ''),
        // 直接使用原始优先级值，不转换
        priority: this.selectedCase.priority || 'P2'
      }
    },

    // 取消编辑
    cancelEdit() {
      this.isEditing = false
      this.editForm = {
        caseId: '',
        scenario: '',
        precondition: '',
        steps: '',
        expected: '',
        priority: 'P2'
      }
    },

    // 保存编辑
    async saveEdit() {
      // 简单验证
      if (!this.editForm.scenario?.trim()) {
        ElMessage.warning(this.$t('taskDetail.enterScenario'))
        return
      }

      this.isSaving = true

      try {
        // 将换行符转换回<br>
        const updatedCase = {
          ...this.selectedCase,
          scenario: this.editForm.scenario,
          precondition: this.convertNewlineToBr(this.editForm.precondition),
          steps: this.convertNewlineToBr(this.editForm.steps),
          expected: this.convertNewlineToBr(this.editForm.expected),
          priority: this.editForm.priority
        }

        // 更新本地数组中的数据
        const index = this.testCases.findIndex(tc => tc === this.selectedCase)
        if (index !== -1) {
          this.testCases[index] = updatedCase
          this.selectedCase = updatedCase
        }

        // 重新生成表格格式的测试用例字符串
        const updatedTestCases = this.generateTestCasesString()

        // 调用后端API保存（使用自定义action接口）
        await api.post(`/requirement-analysis/testcase-generation/${this.taskId}/update-test-cases/`, {
          final_test_cases: updatedTestCases
        })

        // 更新内存中的task数据
        this.task.final_test_cases = updatedTestCases

        ElMessage.success(this.$t('taskDetail.updateSuccess'))
        this.isEditing = false
      } catch (error) {
        console.error('Update failed:', error)
        ElMessage.error(this.$t('taskDetail.updateFailed') + ': ' + (error.response?.data?.error || error.message))
      } finally {
        this.isSaving = false
      }
    },

    // 将testCases数组重新生成为表格格式的字符串
    generateTestCasesString() {
      if (this.testCases.length === 0) return ''

      // 表头
      const headers = [
        this.$t('taskDetail.tableCaseId'),
        this.$t('taskDetail.tableScenario'),
        this.$t('taskDetail.tablePrecondition'),
        this.$t('taskDetail.tableSteps'),
        this.$t('taskDetail.tableExpected'),
        this.$t('taskDetail.tablePriority')
      ]
      let result = headers.join(' | ') + '\n'
      result += '|'.repeat(headers.length) + '\n'

      // 数据行
      this.testCases.forEach((testCase, index) => {
        const row = [
          testCase.caseId || `TC${String(index + 1).padStart(3, '0')}`,
          testCase.scenario || '',
          testCase.precondition || '',
          testCase.steps || '',
          testCase.expected || '',
          testCase.priority || 'P2'
        ]
        result += row.join(' | ') + '\n'
      })

      return result
    },

    // 将HTML的<br>标签转换为换行符
    convertBrToNewline(text) {
      if (!text) return ''
      return text.replace(/<br\s*\/?>/gi, '\n')
    },

    // 将换行符转换为HTML的<br>标签
    convertNewlineToBr(text) {
      if (!text) return ''
      return text.replace(/\n/g, '<br>')
    },

    async adoptSingleCase(testCase, index) {
      try {
        await ElMessageBox.confirm(
          this.$t('taskDetail.confirmAdoptSingle', { scenario: testCase.scenario }),
          this.$t('taskDetail.confirmAdoptTitle'),
          {
            confirmButtonText: this.$t('taskDetail.btnConfirm'),
            cancelButtonText: this.$t('taskDetail.btnCancelOperation'),
            type: 'success',
            customClass: 'ag-confirm'
          }
        )
      } catch {
        return
      }

      try {
        const caseData = {
          title: testCase.scenario || `测试用例${index + 1}`,
          description: testCase.scenario || '',
          preconditions: testCase.precondition || '',
          steps: testCase.steps || '',
          expected_result: testCase.expected || '',
          priority: this.mapPriority(testCase.priority),
          test_type: 'functional',
          status: 'draft',
          project: this.task?.project,
        }

        await api.post('/testcases/', caseData)
        ElMessage.success(this.$t('taskDetail.adoptSuccess', { count: 1 }))

        // 不再移除已采纳的用例，保留在列表中供多次采纳
        // this.testCases.splice(this.testCases.indexOf(testCase), 1)

      } catch (error) {
        console.error('Adopt case failed:', error)
        ElMessage.error(this.$t('taskDetail.adoptFailed') + ': ' + (error.response?.data?.message || error.message))
      }
    },

    async discardSingleCase(testCase, index) {
      try {
        await ElMessageBox.confirm(
          this.$t('taskDetail.confirmDiscardSingle', { scenario: testCase.scenario }),
          this.$t('taskDetail.confirmDiscardTitle'),
          {
            confirmButtonText: this.$t('taskDetail.btnConfirm'),
            cancelButtonText: this.$t('taskDetail.btnCancelOperation'),
            type: 'warning',
            confirmButtonClass: 'el-button--danger',
            customClass: 'ag-confirm'
          }
        )
      } catch {
        return
      }

      try {
        // 计算全局索引（当前页面起始位置 + 当前索引）
        const globalIndex = (this.currentPage - 1) * this.pageSize + index

        // 调用后端API弃用单个测试用例（优先 scenario 匹配，索引备选）
        const response = await api.post(`/requirement-analysis/testcase-generation/${this.taskId}/discard-single-case/`, {
          case_scenario: testCase.scenario || '',
          case_index: globalIndex
        })

        if (response.data.task_deleted) {
          ElMessage.success(this.$t('taskDetail.allDiscardedSuccess'))
          // 返回到AI生成用例记录列表
          this.$router.push('/generated-testcases')
        } else {
          ElMessage.success(this.$t('taskDetail.caseDiscardedSuccess'))

          // 重新解析更新后的测试用例
          if (response.data.updated_test_cases) {
            this.testCases = this.parseTestCases(response.data.updated_test_cases)

            // 如果当前页没有数据了，回到上一页
            if (this.currentPage > 1 && this.paginatedTestCases.length === 0) {
              this.currentPage--
            }
          }
        }

      } catch (error) {
        console.error('Discard case failed:', error)
        ElMessage.error(this.$t('taskDetail.discardFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    mapPriority(priority) {
      const priorityMap = {
        '最高': 'critical',
        '高': 'high',
        '中': 'medium',
        '低': 'low',
        'P0': 'critical',
        'P1': 'high',
        'P2': 'medium',
        'P3': 'low'
      }
      return priorityMap[priority] || 'medium'
    },

    // 将英文优先级转换为本地化显示
    priorityToChinese(priority) {
      const priorityMap = {
        'critical': this.$t('generatedTestCases.priorityCritical'),
        'high': this.$t('generatedTestCases.priorityHigh'),
        'medium': this.$t('generatedTestCases.priorityMedium'),
        'low': this.$t('generatedTestCases.priorityLow')
      }
      return priorityMap[priority] || this.$t('generatedTestCases.priorityMedium')
    },

    // 导出到Excel
    exportToExcel() {
      if (this.testCases.length === 0) {
        ElMessage.warning(this.$t('taskDetail.noCasesToExport'))
        return
      }

      this.isExporting = true

      try {
        // 创建工作簿
        const workbook = XLSX.utils.book_new()

        // 准备数据
        const worksheetData = []

        // 添加表头
        worksheetData.push([
          this.$t('taskDetail.tableCaseId'),
          this.$t('taskDetail.tableScenario'),
          this.$t('taskDetail.tablePrecondition'),
          this.$t('taskDetail.tableSteps'),
          this.$t('taskDetail.tableExpected'),
          this.$t('taskDetail.tablePriority')
        ])

        // 添加数据行
        this.testCases.forEach((testCase, index) => {
          worksheetData.push([
            testCase.caseId || `TC${String(index + 1).padStart(3, '0')}`,
            testCase.scenario || '',
            this.formatTextForList(testCase.precondition || ''),
            this.formatTextForList(testCase.steps || ''),
            this.formatTextForList(testCase.expected || ''),
            testCase.priority || 'P2'
          ])
        })

        // 创建工作表
        const worksheet = XLSX.utils.aoa_to_sheet(worksheetData)

        // 设置列宽
        const colWidths = [
          { wch: 15 }, // 测试用例编号
          { wch: 30 }, // 测试场景
          { wch: 25 }, // 前置条件
          { wch: 50 }, // 操作步骤（增加宽度）
          { wch: 40 }, // 预期结果（增加宽度）
          { wch: 10 }  // 优先级
        ]
        worksheet['!cols'] = colWidths

        // 为所有单元格添加自动换行样式
        const range = XLSX.utils.decode_range(worksheet['!ref'])
        for (let row = range.s.r; row <= range.e.r; row++) {
          for (let col = range.s.c; col <= range.e.c; col++) {
            const cellAddress = XLSX.utils.encode_cell({ r: row, c: col })
            if (!worksheet[cellAddress]) continue
            worksheet[cellAddress].s = {
              alignment: {
                wrapText: true,
                vertical: 'top'
              }
            }
          }
        }

        // 将工作表添加到工作簿
        XLSX.utils.book_append_sheet(workbook, worksheet, this.$t('taskDetail.excelSheetName'))

        // 生成文件名
        const dateStr = new Date().toISOString().slice(0, 10)
        const fileName = this.$t('taskDetail.excelFileName', { taskId: this.taskId, date: dateStr })

        // 导出文件
        XLSX.writeFile(workbook, fileName)

        ElMessage.success(this.$t('taskDetail.exportSuccess'))
      } catch (error) {
        console.error('Export Excel failed:', error)
        ElMessage.error(this.$t('taskDetail.exportFailed') + ': ' + (error.message || ''))
      } finally {
        this.isExporting = false
      }
    }
  }
}
</script>

<style scoped lang="scss">
/* =============================================
   Ark Moderate — Task Detail
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
  &--req { flex-shrink: 0; margin-bottom: 16px; }
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
  display: flex; justify-content: space-between; align-items: flex-start; gap: 20px;
  padding: 16px 20px 20px;
  &__title {
    margin: 0 0 12px; font-size: 24px; font-weight: 900;
    color: var(--ark-ink); line-height: 1.3;
    &::before {
      content: ""; display: block; width: 44px; height: 4px;
      background: var(--ark-signal); margin-bottom: 10px;
    }
  }
  &__sub { font-weight: 500; color: #666; font-size: 17px; }
  &__meta { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
  &__id {
    font-size: 12px; font-family: "IBM Plex Mono", Consolas, monospace;
    color: #666; letter-spacing: .02em;
  }
  &__actions { display: flex; gap: 10px; flex-shrink: 0; }
}

/* ============================================
   Requirement
   ============================================ */
.ag-req {
  &__head {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 20px; cursor: pointer; list-style: none;
    font-size: 14px; font-weight: 600; color: var(--ark-ink);
    user-select: none; transition: background .12s;
    &::-webkit-details-marker { display: none; }
    &::after {
      content: ""; margin-left: auto; flex-shrink: 0;
      width: 0; height: 0;
      border-left: 5px solid transparent; border-right: 5px solid transparent;
      border-top: 6px solid #999;
      transition: transform .15s;
    }
    &:hover { background: #fafaf7; }
    &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: -2px; }
  }
  &[open] .ag-req__head::after { transform: rotate(180deg); }
  &__title { font-size: 14px; font-weight: 700; color: var(--ark-ink); }
  &__hint { font-size: 12px; color: #999; font-weight: 400; }
  &__body { padding: 4px 20px 18px; }
  &__text {
    background: var(--ark-paper); border-left: 3px solid var(--ark-signal);
    padding: 14px 16px; font-size: 13px; line-height: 1.8; color: #444;
    white-space: pre-wrap; word-break: break-word; max-height: 320px; overflow-y: auto;
  }
  &__actions { margin-top: 12px; display: flex; justify-content: flex-end; }
}

/* ============================================
   Content
   ============================================ */
.ag-content { display: flex; flex-direction: column; min-height: 0; }

.ag-batch {
  display: flex; justify-content: space-between; align-items: center; gap: 16px;
  padding: 14px 20px; border-bottom: 1px solid var(--ark-border); flex-wrap: wrap;
  &__select { display: flex; align-items: center; gap: 14px; }
  &__actions { display: flex; gap: 8px; }
  &__count {
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #7d6a16; background: #fdf7e4; border: 1px solid #e0d29a;
    padding: 2px 10px; letter-spacing: .05em;
  }
}
.ag-check {
  display: inline-flex; align-items: center; gap: 8px;
  cursor: pointer; font-size: 13px; color: #444;
  input {
    accent-color: var(--ark-signal);
    &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: 1px; }
  }
}

/* ============================================
   Table
   ============================================ */
.ag-table-wrap { flex: 1; overflow: visible; }
.ag-table {
  width: 100%; min-width: 1060px; border-collapse: collapse; font-size: 13px;
  thead { border-bottom: 2px solid var(--ark-ink); }
  th, td { padding: 10px 12px; text-align: left; vertical-align: top; }
}
.ag-th {
  font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em; color: #999; font-weight: 600;
  &--check { width: 44px; text-align: center; }
  &--id { width: 110px; }
  &--scenario { min-width: 180px; }
  &--prio { width: 84px; text-align: center; }
  &--act { width: 220px; }
}
.ag-tr {
  border-bottom: 1px solid #eee;
  transition: background .1s;
  &:hover { background: #f8fafa; }
}
.ag-td {
  color: #444; line-height: 1.6;
  &--check {
    text-align: center;
    input {
      accent-color: var(--ark-signal);
      &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: 1px; }
    }
  }
  &--id { font-family: "IBM Plex Mono", Consolas, monospace; font-size: 12px; color: #666; white-space: nowrap; }
  &--scenario { font-weight: 500; color: #222; }
  &--prio { text-align: center; }
  &--act { white-space: nowrap; }
}
.ag-clamp {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; white-space: pre-wrap; line-height: 1.6;
  word-break: break-word; max-width: 260px;
}
.ag-actions { display: flex; gap: 4px; flex-wrap: nowrap; }

/* ============================================
   Priority / Status
   ============================================ */
.ag-prio {
  display: inline-block; padding: 2px 10px; font-size: 11px; font-weight: 700;
  font-family: "Space Grotesk", system-ui, sans-serif; letter-spacing: .06em;
  border: 1px solid; text-transform: uppercase;
  &--p0, &--critical, &--最高 { color: #b03a35; background: #fdf0ef; border-color: #e8c4c1; }
  &--p1, &--high, &--高 { color: #9a6a12; background: #fdf7e8; border-color: #e5d49a; }
  &--p2, &--medium, &--中 { color: #555; background: #f4f5f3; border-color: #d8dad7; }
  &--p3, &--low, &--低 { color: #777; background: #fafbfa; border-color: #e0e2df; }
}
.ag-badge {
  display: inline-block; padding: 3px 12px; font-size: 10px;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em; font-weight: 600; border: 1px solid;
  &--pending { color: #666; background: #f4f5f3; border-color: #d8dad7; }
  &--generating, &--reviewing { color: #7d6a16; background: #fdf7e4; border-color: #e0d29a; }
  &--completed { color: #0f8a5c; background: #e6f7f0; border-color: #9edfc2; }
  &--failed { color: #b03a35; background: #fdf0ef; border-color: #e8c4c1; }
}

/* ============================================
   Select
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
  &--sm { height: 30px; padding: 0 24px 0 8px; font-size: 11px; }
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
  &--warn {
    color: #7d6a16; background: #fffdf4; border-color: #dccc8e;
    &::before { background: #c8a821; }
    &:hover:not(:disabled) { background: #faf3d8; border-color: #cdbb76; }
    &:disabled { color: #b6ab7f; background: #f8f6ee; border-color: #e5dfc4; &::before { background: transparent; } }
  }

  :deep(.el-icon) { font-size: 13px; }
}

/* ============================================
   Pagination
   ============================================ */
.ag-page {
  display: flex; justify-content: space-between; align-items: center; gap: 16px;
  padding: 14px 20px; border-top: 1px solid var(--ark-border); flex-wrap: wrap;
  &__info { font-size: 12px; color: #999; font-family: "Space Grotesk", system-ui, sans-serif; }
  &__ctrls { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
  &__size { display: flex; align-items: center; gap: 8px; }
  &__label {
    font-size: 11px; color: #999; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .08em;
  }
  &__btns { display: flex; align-items: center; gap: 8px; }
  &__current {
    font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #555; padding: 0 4px; white-space: nowrap;
  }
}

/* ============================================
   Empty
   ============================================ */
.ag-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 64px 20px; text-align: center; color: #aaa;
  &__icon {
    font-size: 24px; font-weight: 900; font-family: "Space Grotesk", system-ui, sans-serif;
    letter-spacing: .2em; color: #ddd; margin-bottom: 16px;
  }
  h3 { color: #666; margin: 0 0 8px; font-size: 16px; }
  p { font-size: 13px; color: #aaa; margin: 0 0 8px; }
  a { color: var(--ark-ink); text-decoration: underline; &:hover { color: #666; } }
}

/* ============================================
   Modal
   ============================================ */
.ag-modal {
  position: fixed; inset: 0; background: rgba(4,6,8,.72);
  display: flex; align-items: center; justify-content: center; z-index: 2000;
  &__box {
    background: #fff; width: 90%; max-width: 860px; max-height: 84vh;
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

/* Detail rows */
.ag-detail {
  &__row {
    margin-bottom: 16px;
    label {
      display: block; font-weight: 600; font-size: 11px; color: #999; margin-bottom: 6px;
      text-transform: uppercase; letter-spacing: .08em;
      font-family: "Space Grotesk", system-ui, sans-serif;
    }
    span, p { font-size: 13px; color: #333; line-height: 1.7; margin: 0; white-space: pre-wrap; word-break: break-word; }
  }
}
.ag-code-block {
  background: var(--ark-paper); padding: 14px 16px; border-left: 3px solid var(--ark-signal);
  font-size: 13px; line-height: 1.7; white-space: pre-line;
}

/* Edit form */
.ag-form {
  display: flex; flex-direction: column; gap: 16px;
  &__group {
    display: flex; flex-direction: column; gap: 6px;
    label {
      font-weight: 600; font-size: 11px; color: #666;
      font-family: "Space Grotesk", system-ui, sans-serif;
      text-transform: uppercase; letter-spacing: .06em;
    }
  }
  &__readonly {
    color: #666; padding: 8px 12px; background: #f4f5f3; border: 1px solid #e0e2df;
    font-family: "IBM Plex Mono", Consolas, monospace; font-size: 13px;
  }
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

/* ============================================
   Motion
   ============================================ */
@keyframes ag-enter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}

@media (prefers-reduced-motion: reduce) {
  .ag-zone, .ag-btn, .ag-select, .ag-tr, .ag-req__head, .ag-req__head::after, .ag-modal__close {
    transition: none !important; animation: none !important;
  }
  .ag-btn:active:not(:disabled) { transform: none; }
}

/* ============================================
   Responsive
   ============================================ */
@media (max-width: 1024px) {
  .ag-shell { padding: 16px 16px 0; }
  .ag-table { min-width: 960px; }
}
@media (max-width: 768px) {
  .ag-shell { padding: 12px 12px 0; }
  .ag-head { flex-direction: column; }
  .ag-head__actions { width: 100%; }
  .ag-head__actions .ag-btn { flex: 1; }
  .ag-batch { flex-direction: column; align-items: stretch; }
  .ag-batch__actions { justify-content: flex-end; }
  .ag-page { flex-direction: column; align-items: flex-start; }
  .ag-page__ctrls { flex-direction: column; align-items: flex-start; width: 100%; }
  .ag-modal__box { width: 95%; }
}
</style>

<style>
/* Endfield-styled confirmation dialogs (rendered at body level) */
.ag-confirm.el-message-box {
  border-radius: 0; border: 1px solid #191919; padding: 20px 24px;
}
.ag-confirm .el-message-box__header { padding: 0 0 10px; }
.ag-confirm .el-message-box__title {
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-weight: 700; color: #191919; font-size: 16px;
}
.ag-confirm .el-message-box__message { color: #555; line-height: 1.8; }
.ag-confirm .el-message-box__btns {
  padding: 14px 0 0; display: flex; justify-content: flex-end; gap: 8px;
}
.ag-confirm .el-button {
  border-radius: 0; font-family: "Space Grotesk", "Noto Sans SC", sans-serif;
}
.ag-confirm .el-button--primary {
  background: #191919; border-color: #191919; color: #fff;
}
.ag-confirm .el-button--primary:hover,
.ag-confirm .el-button--primary:focus {
  background: #2e2e2e; border-color: #2e2e2e; color: #fff;
}
.ag-confirm .el-button--danger {
  background: #b03a35; border-color: #b03a35; color: #fff;
}
.ag-confirm .el-button--danger:hover,
.ag-confirm .el-button--danger:focus {
  background: #c04840; border-color: #c04840; color: #fff;
}
.ag-confirm .el-button--default {
  background: #fff; border-color: #c9cbc8; color: #191919;
}
.ag-confirm .el-button--default:hover,
.ag-confirm .el-button--default:focus {
  background: #eef0ed; border-color: #a9aca9; color: #191919;
}
</style>
