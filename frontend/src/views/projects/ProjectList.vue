<template>
  <div class="ag-shell" data-ark-theme="endfield" data-ark-depth="moderate">
    <!-- Grid -->
    <div class="ag-grid" aria-hidden="true"></div>

    <!-- ====== Zone A: Header ====== -->
    <section class="ag-zone ag-zone--head">
      <header class="ag-zone__bar">
        <span class="ag-zone__kicker">PROJECT / INDEX</span>
        <span class="ag-zone__rule" aria-hidden="true"></span>
        <span class="ag-zone__code">{{ total }} RECORDS</span>
      </header>
      <div class="ag-head">
        <h1 class="ag-head__title">{{ $t('project.projectManagement') }}</h1>
        <div class="ag-head__actions">
          <button class="ag-btn ag-btn--ok" @click="handleCreateProject">+ {{ $t('project.newProject') }}</button>
        </div>
      </div>
    </section>

    <!-- ====== Zone B: Content ====== -->
    <section class="ag-zone ag-zone--content">
      <div v-if="loading" class="ag-loading-bar" aria-hidden="true"></div>

      <!-- Filter -->
      <div class="ag-filter">
        <div class="ag-filter__field ag-filter__field--grow">
          <span class="ag-filter__label">SEARCH / NAME</span>
          <input v-model="searchText" @input="handleSearch" class="ag-input" :placeholder="$t('project.searchPlaceholder')" />
        </div>
        <div class="ag-filter__field">
          <span class="ag-filter__label">STATUS</span>
          <select v-model="statusFilter" @change="handleFilter" class="ag-select">
            <option value="">{{ $t('project.statusFilter') }}</option>
            <option value="active">{{ $t('project.active') }}</option>
            <option value="paused">{{ $t('project.paused') }}</option>
            <option value="completed">{{ $t('project.completed') }}</option>
            <option value="archived">{{ $t('project.archived') }}</option>
          </select>
        </div>
      </div>

      <!-- Table -->
      <div class="ag-table-wrap">
        <table class="ag-table">
          <thead>
            <tr>
              <th class="ag-th ag-th--name">{{ $t('project.projectName') }}</th>
              <th class="ag-th ag-th--desc">{{ $t('project.description') }}</th>
              <th class="ag-th ag-th--status">{{ $t('project.status') }}</th>
              <th class="ag-th ag-th--owner">{{ $t('project.owner') }}</th>
              <th class="ag-th ag-th--time">{{ $t('project.createdAt') }}</th>
              <th class="ag-th ag-th--act">{{ $t('project.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in projects" :key="row.id" class="ag-tr">
              <td class="ag-td ag-td--name"><button class="ag-link" @click="goToProject(row.id)">{{ row.name }}</button></td>
              <td class="ag-td"><div class="ag-clamp">{{ row.description }}</div></td>
              <td class="ag-td ag-td--status">
                <span class="ag-badge" :class="'ag-badge--' + row.status">{{ getStatusText(row.status) }}</span>
              </td>
              <td class="ag-td ag-td--owner">{{ row.owner?.username }}</td>
              <td class="ag-td ag-td--time">{{ formatDate(row.created_at) }}</td>
              <td class="ag-td ag-td--act">
                <div class="ag-actions">
                  <button class="ag-btn ag-btn--sm" @click="openMemberDialog(row)">成员</button>
                  <button class="ag-btn ag-btn--sm" @click="editProject(row)">{{ $t('common.edit') }}</button>
                  <button class="ag-btn ag-btn--sm ag-btn--danger" @click="deleteProject(row)">{{ $t('common.delete') }}</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="ag-page">
        <span class="ag-page__info">共 {{ total }} 条</span>
        <div class="ag-page__ctrls">
          <div class="ag-page__btns">
            <button class="ag-btn ag-btn--sm" :disabled="currentPage <= 1" @click="currentPage--; handlePageChange()">‹ 上一页</button>
            <span class="ag-page__current">{{ currentPage }} / {{ Math.max(1, Math.ceil(total / pageSize)) }}</span>
            <button class="ag-btn ag-btn--sm" :disabled="currentPage >= Math.max(1, Math.ceil(total / pageSize))" @click="currentPage++; handlePageChange()">下一页 ›</button>
          </div>
        </div>
      </div>
    </section>

    <!-- ====== Modal: Members ====== -->
    <div v-if="showMemberDialog" class="ag-modal" @click.self="showMemberDialog = false; memberProjectId = null">
      <div class="ag-modal__box ag-modal__box--sm">
        <header class="ag-modal__head">
          <span class="ag-modal__kicker">PROJECT / MEMBERS</span>
          <button class="ag-modal__close" @click="showMemberDialog = false; memberProjectId = null">×</button>
        </header>
        <div class="ag-modal__body" v-if="memberProjectId">
          <div class="ag-member-add">
            <input v-model="newMemberName" class="ag-input" placeholder="输入用户名" />
            <select v-model="newMemberRole" class="ag-select ag-select--sm">
              <option value="viewer">观察者</option>
              <option value="tester">测试者</option>
              <option value="developer">开发者</option>
              <option value="admin">管理员</option>
            </select>
            <button class="ag-btn ag-btn--ok" @click="addMember" :disabled="addingMember">{{ addingMember ? '添加中…' : '添加' }}</button>
          </div>
          <div class="ag-mini-table-wrap">
            <table class="ag-mini-table">
              <thead>
                <tr>
                  <th class="ag-th">用户名</th>
                  <th class="ag-th">角色</th>
                  <th class="ag-th ag-th--mini-act">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in memberList" :key="m.id" class="ag-tr">
                  <td class="ag-td">{{ m.username }}</td>
                  <td class="ag-td">{{ m.role }}</td>
                  <td class="ag-td">
                    <button v-if="m.role !== 'owner'" class="ag-btn ag-btn--sm ag-btn--danger" @click="removeMember(m)">移除</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="memberList.length === 0" class="ag-modal__empty">暂无成员</div>
        </div>
        <footer class="ag-modal__foot">
          <button class="ag-btn ag-btn--ghost" @click="showMemberDialog = false; memberProjectId = null">关闭</button>
        </footer>
      </div>
    </div>

    <!-- ====== Modal: Create / Edit ====== -->
    <div v-if="showCreateDialog" class="ag-modal">
      <div class="ag-modal__box">
        <header class="ag-modal__head">
          <span class="ag-modal__kicker">{{ isEdit ? 'PROJECT / EDIT' : 'PROJECT / CREATE' }}</span>
          <button class="ag-modal__close" @click="showCreateDialog = false; handleDialogClose()">×</button>
        </header>
        <div class="ag-modal__body">
          <el-form ref="formRef" :model="form" :rules="rules" label-width="0">
            <div class="ag-form__group">
              <label>{{ $t('project.projectName') }} *</label>
              <el-form-item prop="name" class="ag-form__item">
                <el-input v-model="form.name" :placeholder="$t('project.projectNamePlaceholder')" />
              </el-form-item>
            </div>
            <div class="ag-form__group">
              <label>{{ $t('project.projectDescription') }}</label>
              <el-form-item prop="description" class="ag-form__item">
                <el-input v-model="form.description" type="textarea" :rows="4" :placeholder="$t('project.projectDescriptionPlaceholder')" />
              </el-form-item>
            </div>
            <div class="ag-form__group">
              <label>{{ $t('project.status') }} *</label>
              <el-form-item prop="status" class="ag-form__item">
                <el-select v-model="form.status" :placeholder="$t('project.selectStatus')" style="width: 100%">
                  <el-option :label="$t('project.active')" value="active" />
                  <el-option :label="$t('project.paused')" value="paused" />
                  <el-option :label="$t('project.completed')" value="completed" />
                  <el-option :label="$t('project.archived')" value="archived" />
                </el-select>
              </el-form-item>
            </div>
          </el-form>
        </div>
        <footer class="ag-modal__foot">
          <button class="ag-btn ag-btn--ghost" @click="showCreateDialog = false; handleDialogClose()">{{ $t('common.cancel') }}</button>
          <button class="ag-btn ag-btn--ok" @click="handleSubmit" :disabled="submitting">
            {{ submitting ? '处理中…' : (isEdit ? $t('project.update') : $t('project.create')) }}
          </button>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import dayjs from 'dayjs'

const router = useRouter()
const { t } = useI18n()
const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const isEdit = ref(false)
const formRef = ref()

const projects = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchText = ref('')
const statusFilter = ref('')

const form = reactive({
  id: null,
  name: '',
  description: '',
  status: 'active'
})

const rules = {
  name: [
    { required: true, message: computed(() => t('project.projectNameRequired')), trigger: 'blur' },
    { min: 2, max: 200, message: computed(() => t('project.projectNameLength')), trigger: 'blur' }
  ],
  status: [
    { required: true, message: computed(() => t('project.projectStatusRequired')), trigger: 'change' }
  ]
}

const fetchProjects = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      search: searchText.value,
      status: statusFilter.value
    }
    const response = await api.get('/projects/', { params })
    projects.value = response.data.results
    total.value = response.data.count
  } catch (error) {
    ElMessage.error(t('project.fetchListFailed'))
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchProjects()
}

const handleFilter = () => {
  currentPage.value = 1
  fetchProjects()
}

const handlePageChange = () => {
  fetchProjects()
}

const goToProject = (id) => {
  router.push(`/ai-generation/projects/${id}`)
}

const handleCreateProject = () => {
  resetForm()
  showCreateDialog.value = true
}

const editProject = (project) => {
  isEdit.value = true
  form.id = project.id
  form.name = project.name
  form.description = project.description
  form.status = project.status
  showCreateDialog.value = true
}

const handleDialogClose = () => {
  resetForm()
}

const resetForm = () => {
  form.id = null
  form.name = ''
  form.description = ''
  form.status = 'active'
  isEdit.value = false
  // 清除表单验证错误
  if (formRef.value) {
    formRef.value.clearValidate()
  }
}

// 成员管理
const showMemberDialog = ref(false)
const memberProjectId = ref(null)
const memberList = ref([])
const newMemberName = ref('')
const newMemberRole = ref('tester')
const addingMember = ref(false)

const openMemberDialog = async (project) => {
  memberProjectId.value = project.id
  showMemberDialog.value = true
  await fetchMembers()
}

const fetchMembers = async () => {
  try {
    const response = await api.get(`/projects/${memberProjectId.value}/members/`)
    memberList.value = response.data
  } catch (error) {
    ElMessage.error('获取成员列表失败')
  }
}

const addMember = async () => {
  if (!newMemberName.value.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  addingMember.value = true
  try {
    await api.post(`/projects/${memberProjectId.value}/members/add/`, {
      username: newMemberName.value.trim(),
      role: newMemberRole.value
    })
    ElMessage.success('添加成功')
    newMemberName.value = ''
    fetchMembers()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '添加失败')
  } finally {
    addingMember.value = false
  }
}

const removeMember = async (member) => {
  try {
    await api.delete(`/projects/${memberProjectId.value}/members/${member.id}/`)
    ElMessage.success('已移除')
    fetchMembers()
  } catch (error) {
    ElMessage.error('移除失败')
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        if (isEdit.value) {
          await api.put(`/projects/${form.id}/`, form)
          ElMessage.success(t('project.updateSuccess'))
        } else {
          await api.post('/projects/', form)
          ElMessage.success(t('project.createSuccess'))
        }
        showCreateDialog.value = false
        resetForm()
        fetchProjects()
      } catch (error) {
        ElMessage.error(isEdit.value ? t('project.updateFailed') : t('project.createFailed'))
      } finally {
        submitting.value = false
      }
    }
  })
}

const deleteProject = async (project) => {
  try {
    await ElMessageBox.confirm(t('project.deleteConfirm'), t('common.warning'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    })

    await api.delete(`/projects/${project.id}/`)
    ElMessage.success(t('project.deleteSuccess'))
    fetchProjects()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('project.deleteFailed'))
    }
  }
}

const getStatusType = (status) => {
  const typeMap = {
    active: 'success',
    paused: 'warning',
    completed: 'info',
    archived: 'info'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    active: t('project.active'),
    paused: t('project.paused'),
    completed: t('project.completed'),
    archived: t('project.archived')
  }
  return textMap[status] || status
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

onMounted(() => {
  fetchProjects()
})
</script>

<style lang="scss" scoped>
/* =============================================
   Ark Moderate — Project Index
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
  display: flex; justify-content: space-between; align-items: flex-end; gap: 20px;
  padding: 16px 20px 20px;
  &__title {
    margin: 0; font-size: 24px; font-weight: 900; color: var(--ark-ink); line-height: 1.3;
    &::before {
      content: ""; display: block; width: 44px; height: 4px;
      background: var(--ark-signal); margin-bottom: 10px;
    }
  }
  &__actions { display: flex; gap: 10px; flex-shrink: 0; }
}

/* ============================================
   Filter
   ============================================ */
.ag-filter {
  display: flex; gap: 16px; padding: 16px 20px;
  border-bottom: 1px solid var(--ark-border);
  &__field {
    display: flex; flex-direction: column; gap: 6px;
    &--grow { flex: 1; min-width: 220px; }
  }
  &__label {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .12em; color: #999;
  }
}

/* ============================================
   Input / Select
   ============================================ */
.ag-input {
  padding: 8px 12px; border: 1px solid #ccc; font-size: 13px; color: #333;
  width: 100%; box-sizing: border-box; font-family: inherit;
  &:focus { outline: none; border-color: #fffa00; }
  &:focus-visible { outline: 2px solid #fffa00; outline-offset: 1px; }
}
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
   Table
   ============================================ */
.ag-table-wrap { flex: 1; overflow: visible; }
.ag-table {
  width: 100%; min-width: 960px; border-collapse: collapse; font-size: 13px;
  thead { border-bottom: 2px solid var(--ark-ink); }
  th, td { padding: 10px 12px; text-align: left; vertical-align: top; }
}
.ag-th {
  font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em; color: #999; font-weight: 600;
  &--name { min-width: 180px; }
  &--desc { min-width: 260px; }
  &--status { width: 90px; text-align: center; }
  &--owner { width: 120px; }
  &--time { width: 160px; }
  &--act { width: 220px; }
}
.ag-tr {
  border-bottom: 1px solid #eee;
  transition: background .1s;
  &:hover { background: #f8fafa; }
}
.ag-td {
  color: #444; line-height: 1.6;
  &--name { font-weight: 600; }
  &--status { text-align: center; }
  &--owner { color: #666; }
  &--time { color: #888; font-size: 12px; white-space: nowrap; }
  &--act { white-space: nowrap; }
}
.ag-clamp {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; white-space: pre-wrap; line-height: 1.6;
  word-break: break-word; max-width: 340px;
}
.ag-actions { display: flex; gap: 4px; flex-wrap: nowrap; }
.ag-link {
  all: unset; cursor: pointer; color: var(--ark-ink); font-weight: 700;
  text-decoration: underline; text-underline-offset: 3px;
  &:hover { color: #666; }
  &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: 2px; }
}

/* ============================================
   Badges
   ============================================ */
.ag-badge {
  display: inline-block; padding: 3px 12px; font-size: 10px;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em; font-weight: 600; border: 1px solid;
  &--active { color: #0f8a5c; background: #e6f7f0; border-color: #9edfc2; }
  &--paused { color: #7d6a16; background: #fdf7e4; border-color: #e0d29a; }
  &--completed { color: #444; background: #f4f5f3; border-color: #d8dad7; }
  &--archived { color: #777; background: #fafbfa; border-color: #e0e2df; }
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
}

/* ============================================
   Pagination
   ============================================ */
.ag-page {
  display: flex; justify-content: space-between; align-items: center; gap: 16px;
  padding: 14px 20px; border-top: 1px solid var(--ark-border); flex-wrap: wrap;
  &__info { font-size: 12px; color: #999; font-family: "Space Grotesk", system-ui, sans-serif; }
  &__ctrls { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
  &__btns { display: flex; align-items: center; gap: 8px; }
  &__current {
    font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #555; padding: 0 4px; white-space: nowrap;
  }
}

/* ============================================
   Loading bar
   ============================================ */
.ag-loading-bar {
  position: absolute; top: -1px; left: 0; right: 0; height: 3px; z-index: 5;
  background: linear-gradient(90deg, transparent 0%, var(--ark-signal) 50%, transparent 100%);
  background-size: 200px 3px; background-repeat: no-repeat;
  animation: ag-scan 1.1s linear infinite;
}
@keyframes ag-scan {
  from { background-position: -200px 0; }
  to { background-position: calc(100% + 200px) 0; }
}

/* ============================================
   Modal
   ============================================ */
.ag-modal {
  position: fixed; inset: 0; background: rgba(4,6,8,.72);
  display: flex; align-items: center; justify-content: center; z-index: 2000;
  &__box {
    background: #fff; width: 90%; max-width: 640px; max-height: 84vh;
    display: flex; flex-direction: column; border: 1px solid #888;
    &--sm { max-width: 520px; }
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
  &__empty { text-align: center; color: #999; padding: 24px 0; font-size: 13px; }
}

/* Member add row */
.ag-member-add {
  display: flex; gap: 8px; margin-bottom: 16px;
  .ag-input { flex: 1; min-height: 36px; }
}
.ag-mini-table-wrap { overflow-x: auto; }
.ag-mini-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
  thead { border-bottom: 2px solid var(--ark-ink); }
  th, td { padding: 8px 12px; text-align: left; }
  .ag-th--mini-act { width: 90px; }
}

/* ============================================
   Form (Element Plus deep overrides)
   ============================================ */
.ag-form {
  &__group {
    display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px;
    label {
      font-weight: 600; font-size: 11px; color: #666;
      font-family: "Space Grotesk", system-ui, sans-serif;
      text-transform: uppercase; letter-spacing: .06em;
    }
  }
  &__item { margin-bottom: 0; }
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
  .ag-zone, .ag-btn, .ag-select, .ag-input, .ag-tr, .ag-modal__close, .ag-loading-bar {
    transition: none !important; animation: none !important;
  }
  .ag-btn:active:not(:disabled) { transform: none; }
}

/* ============================================
   Responsive
   ============================================ */
@media (max-width: 1024px) {
  .ag-shell { padding: 16px 16px 0; }
  .ag-table { min-width: 880px; }
}
@media (max-width: 768px) {
  .ag-shell { padding: 12px 12px 0; }
  .ag-head { flex-direction: column; align-items: flex-start; }
  .ag-head__actions { width: 100%; }
  .ag-head__actions .ag-btn { flex: 1; }
  .ag-filter { flex-direction: column; }
  .ag-page { flex-direction: column; align-items: flex-start; }
  .ag-page__ctrls { flex-direction: column; align-items: flex-start; width: 100%; }
  .ag-modal__box { width: 95%; }
  .ag-member-add { flex-wrap: wrap; }
}
</style>
