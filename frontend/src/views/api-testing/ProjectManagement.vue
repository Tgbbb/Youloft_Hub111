<template>
  <div class="project-management">
    <div class="header">
      <h2>{{ $t('apiTesting.project.title') }}</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        {{ $t('apiTesting.project.createProject') }}
      </el-button>
    </div>


    <!-- 项目列表 -->
    <el-table :data="projects" v-loading="loading" style="width: 100%">
      <el-table-column prop="name" :label="$t('apiTesting.project.projectName')" min-width="200" />
      <el-table-column prop="project_type" :label="$t('apiTesting.project.projectType')" width="120">
        <template #default="scope">
          <el-tag :type="scope.row.project_type === 'HTTP' ? 'primary' : 'success'">
            {{ scope.row.project_type }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" :label="$t('apiTesting.project.projectStatus')" width="120">
        <template #default="scope">
          <el-tag
            :type="getStatusType(scope.row.status)"
          >
            {{ getStatusText(scope.row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="owner.username" :label="$t('apiTesting.project.owner')" width="150" />
      <el-table-column prop="start_date" :label="$t('apiTesting.project.startDate')" width="120" />
      <el-table-column prop="end_date" :label="$t('apiTesting.project.endDate')" width="120" />
      <el-table-column prop="created_at" :label="$t('apiTesting.project.createdAt')" width="180">
        <template #default="scope">
          {{ formatDate(scope.row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column :label="$t('apiTesting.common.operation')" width="200">
        <template #default="scope">
          <el-button link type="primary" @click="editProject(scope.row)">{{ $t('apiTesting.common.edit') }}</el-button>
          <el-button link type="primary" @click="viewProject(scope.row)">{{ $t('apiTesting.common.view') }}</el-button>
          <el-button link type="danger" @click="deleteProject(scope.row)">{{ $t('apiTesting.common.delete') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      :total="total"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
      class="pagination"
    />

    <!-- 新建/编辑项目对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      class="automation-dialog"
      modal-class="automation-modal"
      :title="editingProject ? $t('apiTesting.project.editProject') : $t('apiTesting.project.createProject')"
      width="600px"
      :close-on-click-modal="false"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item :label="$t('apiTesting.project.projectName')" prop="name">
          <el-input v-model="form.name" :placeholder="$t('apiTesting.project.inputProjectName')" />
        </el-form-item>

        <el-form-item :label="$t('apiTesting.project.projectDescription')" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            :placeholder="$t('apiTesting.project.inputProjectDesc')"
          />
        </el-form-item>

        <el-form-item :label="$t('apiTesting.project.projectType')" prop="project_type">
          <el-radio-group v-model="form.project_type">
            <el-radio value="HTTP">HTTP</el-radio>
            <el-radio value="WEBSOCKET">WebSocket</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item :label="$t('apiTesting.project.projectStatus')" prop="status">
          <el-select v-model="form.status" popper-class="automation-popper" :placeholder="$t('apiTesting.project.selectStatus')">
            <el-option :label="$t('apiTesting.project.status.notStarted')" value="NOT_STARTED" />
            <el-option :label="$t('apiTesting.project.status.inProgress')" value="IN_PROGRESS" />
            <el-option :label="$t('apiTesting.project.status.completed')" value="COMPLETED" />
          </el-select>
        </el-form-item>

        <el-form-item :label="$t('apiTesting.project.owner')" prop="owner">
          <el-select v-model="form.owner" popper-class="automation-popper" :placeholder="$t('apiTesting.project.selectOwner')" filterable>
            <el-option
              v-for="user in users"
              :key="user.id"
              :label="user.username"
              :value="user.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item :label="$t('apiTesting.project.teamMembers')" prop="member_ids">
          <el-select
            v-model="form.member_ids"
            popper-class="automation-popper"
            multiple
            :placeholder="$t('apiTesting.project.selectMembers')"
            filterable
          >
            <el-option
              v-for="user in users"
              :key="user.id"
              :label="user.username"
              :value="user.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item :label="$t('apiTesting.project.startDate')" prop="start_date">
          <el-date-picker
            v-model="form.start_date"
            popper-class="automation-popper"
            type="date"
            :placeholder="$t('apiTesting.project.selectStartDate')"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item :label="$t('apiTesting.project.endDate')" prop="end_date">
          <el-date-picker
            v-model="form.end_date"
            popper-class="automation-popper"
            type="date"
            :placeholder="$t('apiTesting.project.selectEndDate')"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">{{ $t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          {{ editingProject ? $t('apiTesting.common.update') : $t('apiTesting.common.create') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 查看项目详情对话框 -->
    <el-dialog
      v-model="showViewDialog"
      class="automation-dialog"
      modal-class="automation-modal"
      :title="$t('apiTesting.project.viewProject')"
      width="600px"
    >
      <el-descriptions :column="1" border>
        <el-descriptions-item :label="$t('apiTesting.project.projectName')">{{ viewedProject?.name }}</el-descriptions-item>
        <el-descriptions-item :label="$t('apiTesting.project.projectDescription')">{{ viewedProject?.description || $t('apiTesting.project.none') }}</el-descriptions-item>
        <el-descriptions-item :label="$t('apiTesting.project.projectType')">
          <el-tag :type="viewedProject?.project_type === 'HTTP' ? 'primary' : 'success'">
            {{ viewedProject?.project_type }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('apiTesting.project.projectStatus')">
          <el-tag :type="getStatusType(viewedProject?.status)">
            {{ getStatusText(viewedProject?.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('apiTesting.project.owner')">{{ viewedProject?.owner?.username }}</el-descriptions-item>
        <el-descriptions-item :label="$t('apiTesting.project.teamMembers')">
          <div v-if="viewedProject?.members?.length">
            <el-tag
              v-for="member in viewedProject.members"
              :key="member.id"
              size="small"
              style="margin-right: 5px; margin-bottom: 5px;"
            >
              {{ member.username }}
            </el-tag>
          </div>
          <span v-else>{{ $t('apiTesting.project.none') }}</span>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('apiTesting.project.startDate')">{{ viewedProject?.start_date || $t('apiTesting.project.notSet') }}</el-descriptions-item>
        <el-descriptions-item :label="$t('apiTesting.project.endDate')">{{ viewedProject?.end_date || $t('apiTesting.project.notSet') }}</el-descriptions-item>
        <el-descriptions-item :label="$t('apiTesting.project.createdAt')">{{ formatDate(viewedProject?.created_at) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('apiTesting.project.updatedAt')">{{ formatDate(viewedProject?.updated_at) }}</el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <el-button @click="showViewDialog = false">{{ $t('apiTesting.common.close') }}</el-button>
        <el-button type="primary" @click="editProject(viewedProject)">{{ $t('apiTesting.common.edit') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, ElDescriptions, ElDescriptionsItem } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Plus } from '@element-plus/icons-vue'
import api from '@/utils/api'
import dayjs from 'dayjs'

const { t } = useI18n()
const loading = ref(false)
const projects = ref([])
const users = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showCreateDialog = ref(false)
const showViewDialog = ref(false)
const editingProject = ref(null)
const viewedProject = ref(null)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  name: '',
  description: '',
  project_type: 'HTTP',
  status: 'NOT_STARTED',
  owner: null,
  member_ids: [],
  start_date: '',
  end_date: ''
})

const rules = computed(() => ({
  name: [
    { required: true, message: t('apiTesting.project.inputProjectName'), trigger: 'blur' }
  ],
  project_type: [
    { required: true, message: t('apiTesting.common.pleaseSelect'), trigger: 'change' }
  ],
  status: [
    { required: true, message: t('apiTesting.project.selectStatus'), trigger: 'change' }
  ],
  owner: [
    { required: true, message: t('apiTesting.project.selectOwner'), trigger: 'change' }
  ]
}))

const getStatusType = (status) => {
  const typeMap = {
    'NOT_STARTED': 'info',
    'IN_PROGRESS': 'warning',
    'COMPLETED': 'success'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const statusKey = {
    'NOT_STARTED': 'notStarted',
    'IN_PROGRESS': 'inProgress',
    'COMPLETED': 'completed'
  }[status]
  return statusKey ? t(`apiTesting.project.status.${statusKey}`) : status
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

const loadProjects = async () => {
  loading.value = true
  try {
    const response = await api.get('/api-testing/projects/', {
      params: {
        page: currentPage.value,
        page_size: pageSize.value
      }
    })
    projects.value = response.data.results
    total.value = response.data.count
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.loadProjects'))
    console.error(error)
  } finally {
    loading.value = false
  }
}

const loadUsers = async () => {
  try {
    const response = await api.get('/api-testing/users/')
    users.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.loadUsers'))
    console.error(error)
  }
}

const handleSizeChange = (size) => {
  pageSize.value = size
  loadProjects()
}

const handleCurrentChange = (page) => {
  currentPage.value = page
  loadProjects()
}

const editProject = (project) => {
  editingProject.value = project
  form.name = project.name
  form.description = project.description
  form.project_type = project.project_type
  form.status = project.status
  form.owner = project.owner.id
  form.member_ids = project.members.map(m => m.id)
  form.start_date = project.start_date
  form.end_date = project.end_date
  showCreateDialog.value = true
}

const viewProject = (project) => {
  // 显示项目详情弹框
  showViewDialog.value = true
  viewedProject.value = project
}

const deleteProject = async (project) => {
  try {
    await ElMessageBox.confirm(
      t('apiTesting.project.confirmDelete', { name: project.name }),
      t('apiTesting.messages.confirm.deleteTitle'),
      {
        confirmButtonText: t('apiTesting.common.confirm'),
        cancelButtonText: t('apiTesting.common.cancel'),
        type: 'warning',
        customClass: 'automation-messagebox'
      }
    )

    await api.delete(`/api-testing/projects/${project.id}/`)
    ElMessage.success(t('apiTesting.messages.success.delete'))
    await loadProjects()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('apiTesting.messages.error.deleteFailed'))
      console.error(error)
    }
  }
}

const submitForm = async () => {
  if (!formRef.value) return
  
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  
  submitting.value = true
  try {
    const data = { ...form }
    if (data.start_date) {
      data.start_date = dayjs(data.start_date).format('YYYY-MM-DD')
    }
    if (data.end_date) {
      data.end_date = dayjs(data.end_date).format('YYYY-MM-DD')
    }
    
    if (editingProject.value) {
      await api.put(`/api-testing/projects/${editingProject.value.id}/`, data)
      ElMessage.success(t('apiTesting.messages.success.projectUpdated'))
    } else {
      await api.post('/api-testing/projects/', data)
      ElMessage.success(t('apiTesting.messages.success.projectCreated'))
    }

    showCreateDialog.value = false
    await loadProjects()
  } catch (error) {
    ElMessage.error(editingProject.value ? t('apiTesting.messages.error.updateFailed') : t('apiTesting.messages.error.createFailed'))
    console.error(error)
  } finally {
    submitting.value = false
  }
}

const resetForm = () => {
  editingProject.value = null
  Object.assign(form, {
    name: '',
    description: '',
    project_type: 'HTTP',
    status: 'NOT_STARTED',
    owner: null,
    member_ids: [],
    start_date: '',
    end_date: ''
  })
  formRef.value?.resetFields()
}

onMounted(async () => {
  await Promise.all([loadProjects(), loadUsers()])
})
</script>

<style scoped>
.project-management {
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

.header h2 {
  margin: 0;
  color: var(--ef-ink);
  font-family: var(--ef-font-display);
  font-size: 22px;
  letter-spacing: .08em;
  text-transform: uppercase;
  position: relative;
  padding-bottom: 8px;
}

.header h2::after {
  content: "";
  position: absolute;
  left: 0;
  bottom: 0;
  width: 36px;
  height: 3px;
  background: var(--ef-signal);
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

/* ---------- Element Plus unification ---------- */
.project-management :deep(.el-button) { border-radius: 2px; }
.project-management :deep(.el-button--primary) {
  background: var(--ef-ink);
  border-color: var(--ef-ink);
  color: #ffffff;
}
.project-management :deep(.el-button--primary:hover) {
  background: #2c2c2c;
  border-color: var(--ef-signal);
  color: var(--ef-signal);
}
.project-management :deep(.el-button--primary.is-plain) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.project-management :deep(.el-button--primary.is-plain:hover) {
  background: rgba(255, 250, 0, .12);
  border-color: var(--ef-signal);
  color: var(--ef-ink);
}
.project-management :deep(.el-button--danger) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.project-management :deep(.el-button--danger:hover) {
  background: rgba(220, 38, 38, .08);
  border-color: #b91c1c;
  color: #b91c1c;
}
.project-management :deep(.el-button--success) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.project-management :deep(.el-button--success:hover) {
  background: rgba(22, 163, 74, .1);
  border-color: #15803d;
  color: #15803d;
}
.project-management :deep(.el-button--warning) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.project-management :deep(.el-button--warning:hover) {
  background: rgba(217, 119, 6, .1);
  border-color: #b45309;
  color: #b45309;
}
.project-management :deep(.el-button--info) {
  background: transparent;
  border-color: var(--ef-line-strong);
  color: var(--ef-muted);
}
.project-management :deep(.el-button--info:hover) {
  border-color: var(--ef-signal);
  color: var(--ef-ink);
}
.project-management :deep(.el-button--primary.is-link) {
  background: transparent;
  border-color: transparent;
  color: var(--ef-ink);
  font-weight: 600;
}
.project-management :deep(.el-button--primary.is-link:hover) {
  color: var(--ef-ink);
  background: rgba(255, 250, 0, .18);
  border-color: transparent;
}
.project-management :deep(.el-button.is-text) {
  color: var(--ef-muted);
}
.project-management :deep(.el-button.is-text:hover) {
  color: var(--ef-ink);
  background: rgba(255, 250, 0, .14);
}

.project-management :deep(.el-input__wrapper),
.project-management :deep(.el-textarea__inner),
.project-management :deep(.el-select__wrapper) {
  background: var(--ef-surface);
  box-shadow: 0 0 0 1px var(--ef-line-strong) inset;
  border-radius: 2px;
}
.project-management :deep(.el-input__wrapper.is-focus),
.project-management :deep(.el-select__wrapper.is-focused),
.project-management :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--ef-ink) inset;
}
.project-management :deep(.el-input__inner) {
  color: var(--ef-ink);
  font-size: 13px;
}
.project-management :deep(.el-textarea__inner) {
  font-family: var(--ef-font-mono);
  font-size: 12px;
  line-height: 1.6;
}

.project-management :deep(.el-tag) {
  border-radius: 2px;
  font-family: var(--ef-font-tech);
  letter-spacing: .04em;
}
.project-management :deep(.el-tag--primary) { background: rgba(25, 25, 25, .08); border-color: transparent; color: var(--ef-ink); }
.project-management :deep(.el-tag--success) { background: rgba(22, 163, 74, .12); border-color: transparent; color: #15803d; }
.project-management :deep(.el-tag--warning) { background: rgba(217, 119, 6, .12); border-color: transparent; color: #b45309; }
.project-management :deep(.el-tag--danger) { background: rgba(220, 38, 38, .12); border-color: transparent; color: #b91c1c; }
.project-management :deep(.el-tag--info) { background: rgba(25, 25, 25, .08); border-color: transparent; color: var(--ef-muted); }

.project-management :deep(.el-table) {
  --el-table-border-color: var(--ef-line);
  --el-table-header-bg-color: var(--ef-paper);
  --el-table-header-text-color: var(--ef-ink);
  --el-table-row-hover-bg-color: rgba(255, 250, 0, .10);
  --el-table-text-color: var(--ef-ink);
  font-size: 12px;
}
.project-management :deep(.el-table th.el-table__cell) { font-weight: 700; }

.project-management :deep(.el-pagination) { font-family: var(--ef-font-tech); }
.project-management :deep(.el-pagination .el-pager li) { color: var(--ef-muted); }
.project-management :deep(.el-pagination .el-pager li:hover) { color: var(--ef-ink); }
.project-management :deep(.el-pagination .el-pager li.is-active) { color: var(--ef-ink); font-weight: 700; }
.project-management :deep(.el-pagination button:hover) { color: var(--ef-ink); }

.project-management :deep(.el-radio__label) {
  font-family: var(--ef-font-tech);
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--ef-muted);
}
.project-management :deep(.el-radio__input.is-checked .el-radio__inner) {
  background: var(--ef-ink);
  border-color: var(--ef-ink);
}
.project-management :deep(.el-radio__input.is-checked + .el-radio__label) {
  color: var(--ef-ink);
  font-weight: 700;
}

.project-management :deep(.el-descriptions) {
  --el-descriptions-table-border: 1px solid var(--ef-line);
  --el-descriptions-table-bg-color: var(--ef-surface);
  --el-descriptions-cell-bg-color: var(--ef-rail);
  --el-descriptions-label-bg-color: var(--ef-paper);
  --el-descriptions-text-color: var(--ef-ink);
  --el-descriptions-label-text-color: var(--ef-muted);
}

.project-management :deep(.el-button:focus-visible),
.project-management :deep(.el-input__wrapper:focus-visible),
.project-management :deep(.el-textarea__inner:focus-visible),
.project-management :deep(.el-select__wrapper:focus-visible) {
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
