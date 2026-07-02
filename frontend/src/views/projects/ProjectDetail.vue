<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">{{ $t('project.projectDetail') }}</h1>
      <el-button type="primary" @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        {{ $t('common.back') }}
      </el-button>
    </div>

    <div class="card-container">
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="$t('project.projectInfo')" name="info">
          <div v-if="project">
            <el-descriptions :column="2" border>
              <el-descriptions-item :label="$t('project.projectName')">{{ project.name }}</el-descriptions-item>
              <el-descriptions-item :label="$t('project.status')">
                <el-tag :type="getStatusType(project.status)">{{ getStatusText(project.status) }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item :label="$t('project.owner')">{{ project.owner?.username }}</el-descriptions-item>
              <el-descriptions-item :label="$t('project.createdAt')">{{ formatDate(project.created_at) }}</el-descriptions-item>
              <el-descriptions-item :label="$t('project.projectDescription')" :span="2">{{ project.description || $t('project.noDescription') }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-tab-pane>

        <!-- 知识背景 Tab -->
        <el-tab-pane :label="$t('project.knowledgeBaseTab')" name="knowledge">
          <div class="knowledge-base-layout">
            <!-- 工具栏 -->
            <div class="kb-toolbar">
              <div class="kb-toolbar-left">
                <span class="kb-char-count">
                  {{ knowledgeBaseText.length }} {{ $t('project.characters') }}
                </span>
                <span class="kb-update-info" v-if="project?.knowledge_base_updated_at">
                  · {{ $t('project.lastUpdated') }}: {{ formatDate(project.knowledge_base_updated_at) }}
                  <template v-if="project?.knowledge_base_updated_by">
                    by {{ project.knowledge_base_updated_by.username }}
                  </template>
                </span>
                <span class="kb-update-info" v-else-if="!knowledgeBaseText">
                  {{ $t('project.neverUpdated') }}
                </span>
              </div>
              <div class="kb-toolbar-right">
                <el-button size="small" text @click="triggerFileUpload" v-if="editingKnowledge">
                  📂 {{ $t('project.uploadMd') }}
                </el-button>
                <input
                  ref="fileInputRef"
                  type="file"
                  accept=".md,.txt,.markdown"
                  style="display: none"
                  @change="handleFileUpload" />
                <el-button size="small" text @click="applyTemplate" v-if="editingKnowledge">
                  📄 {{ $t('project.useTemplate') }}
                </el-button>
                <el-button
                  size="small"
                  :type="editingKnowledge ? 'primary' : 'default'"
                  @click="toggleEdit">
                  {{ editingKnowledge ? $t('project.preview') : $t('project.edit') }}
                </el-button>
              </div>
            </div>

            <!-- 主体：目录侧边栏 + 内容区 -->
            <div class="kb-content-wrapper" v-if="knowledgeBaseText || editingKnowledge">
              <!-- ===== TOC Sidebar ===== -->
              <aside
                class="kb-toc-sidebar"
                :class="{ 'kb-toc-open': showToc }"
                v-if="parsedSections.length > 0"
              >
                <div class="kb-toc-header">
                  <span>{{ $t('project.tableOfContents') }}</span>
                  <el-button size="small" text class="kb-toc-close" @click="showToc = false">
                    <el-icon><Close /></el-icon>
                  </el-button>
                </div>
                <div class="kb-toc-list">
                  <div
                    class="kb-toc-item kb-toc-item-all"
                    :class="{ 'kb-toc-item-active': activeSection === null }"
                    @click="selectSection(null)">
                    <span>{{ $t('project.allSections') }}</span>
                  </div>
                  <div
                    v-for="(section, index) in parsedSections"
                    :key="index"
                    class="kb-toc-item"
                    :class="{ 'kb-toc-item-active': activeSection === index }"
                    @click="selectSection(index)"
                    :title="section.heading">
                    <span class="kb-toc-item-text">{{ section.heading }}</span>
                  </div>
                </div>
              </aside>

              <!-- ===== Content Area ===== -->
              <div class="kb-content-area">
                <!-- Mobile TOC toggle -->
                <el-button
                  v-if="parsedSections.length > 0"
                  size="small"
                  text
                  class="kb-toc-toggle"
                  @click="showToc = !showToc">
                  <el-icon><Menu /></el-icon>
                  {{ $t('project.tableOfContents') }}
                </el-button>

                <!-- Section indicator tag -->
                <div class="kb-section-indicator" v-if="activeSection !== null && parsedSections[activeSection]">
                  <el-tag type="warning" size="small" closable @close="selectSection(null)">
                    {{ parsedSections[activeSection].heading }}
                  </el-tag>
                  <span class="kb-section-hint">{{ $t('project.sectionEditingHint') }}</span>
                </div>

                <!-- === Edit Mode === -->
                <div class="kb-editor-area" v-if="editingKnowledge">
                  <div class="kb-split-pane">
                    <div class="kb-pane kb-pane-left">
                      <div class="kb-pane-label">
                        {{ $t('common.edit') }}
                        <span v-if="activeSection !== null" class="kb-pane-sub-label">
                          · {{ parsedSections[activeSection]?.heading }}
                        </span>
                      </div>
                      <el-input
                        v-model="effectiveText"
                        type="textarea"
                        :rows="18"
                        :placeholder="$t('project.knowledgeBasePlaceholder')"
                        class="kb-textarea" />
                    </div>
                    <div class="kb-pane kb-pane-right">
                      <div class="kb-pane-label">
                        {{ $t('project.preview') }}
                        <span v-if="activeSection !== null" class="kb-pane-sub-label">
                          · {{ parsedSections[activeSection]?.heading }}
                        </span>
                      </div>
                      <div
                        class="kb-markdown-preview markdown-body"
                        v-html="renderMarkdown(effectiveText)" />
                    </div>
                  </div>
                  <div class="kb-actions">
                    <el-button @click="cancelEdit">{{ $t('common.cancel') }}</el-button>
                    <el-button type="primary" @click="saveKnowledgeBase" :loading="savingKnowledge">
                      {{ $t('common.save') }}
                    </el-button>
                  </div>
                </div>

                <!-- === Preview Mode === -->
                <div class="kb-preview-area" v-else>
                  <div
                    class="kb-markdown-preview markdown-body"
                    v-html="renderMarkdown(effectiveText)" />
                </div>
              </div>
            </div>

            <!-- 空状态 -->
            <div class="kb-preview-area" v-if="!knowledgeBaseText && !editingKnowledge">
              <div class="kb-empty">
                <div class="kb-empty-icon">📋</div>
                <p>{{ $t('project.noKnowledgeBase') }}</p>
                <el-button type="primary" @click="toggleEdit">
                  {{ $t('common.edit') }}
                </el-button>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="$t('project.projectMembers')" name="members">
          <div class="members-section">
            <el-button type="primary" @click="showAddMemberDialog = true">{{ $t('project.addMember') }}</el-button>
            <el-table :data="project?.members || []" style="width: 100%; margin-top: 20px;">
              <el-table-column prop="user.username" :label="$t('project.username')" />
              <el-table-column prop="user.email" :label="$t('project.email')" />
              <el-table-column prop="role" :label="$t('project.role')" />
              <el-table-column prop="joined_at" :label="$t('project.joinedAt')">
                <template #default="{ row }">
                  {{ formatDate(row.joined_at) }}
                </template>
              </el-table-column>
              <el-table-column :label="$t('project.actions')" width="100">
                <template #default="{ row }">
                  <el-button size="small" type="danger" @click="removeMember(row)">{{ $t('common.delete') }}</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="$t('project.environments')" name="environments">
          <div class="environments-section">
            <el-button type="primary" @click="showAddEnvDialog = true">{{ $t('project.addEnvironment') }}</el-button>
            <el-table :data="project?.environments || []" style="width: 100%; margin-top: 20px;">
              <el-table-column prop="name" :label="$t('project.environmentName')" />
              <el-table-column prop="base_url" :label="$t('project.baseUrl')" />
              <el-table-column prop="description" :label="$t('project.description')" />
              <el-table-column prop="is_default" :label="$t('project.defaultEnvironment')">
                <template #default="{ row }">
                  <el-tag v-if="row.is_default" type="success">{{ $t('project.yes') }}</el-tag>
                  <span v-else>{{ $t('project.no') }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 添加成员弹窗 -->
    <el-dialog v-model="showAddMemberDialog" title="添加成员" width="400px">
      <el-form>
        <el-form-item label="用户名">
          <el-input v-model="newMember.username" placeholder="输入用户名" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="newMember.role" style="width: 100%">
            <el-option label="观察者" value="viewer" />
            <el-option label="测试者" value="tester" />
            <el-option label="开发者" value="developer" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddMemberDialog = false">取消</el-button>
        <el-button type="primary" @click="addMember" :loading="addingMember">添加</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import dayjs from 'dayjs'
import { marked } from 'marked'

const route = useRoute()
const { t } = useI18n()
const project = ref(null)
const activeTab = ref('info')
const showAddMemberDialog = ref(false)
const showAddEnvDialog = ref(false)
const addingMember = ref(false)
const newMember = reactive({ username: '', role: 'tester' })
const editingKnowledge = ref(false)
const knowledgeBaseText = ref('')
const knowledgeBaseOriginal = ref('')
const savingKnowledge = ref(false)
const fileInputRef = ref(null)

// TOC state
const activeSection = ref(null)  // null = all, number = section index
const showToc = ref(true)

// ── Section parsing ──

function parseSections(text) {
  if (!text || !text.trim()) return []
  const sections = []
  const regex = /^## .+$/gm
  let match
  let lastIndex = 0
  let lastHeading = null

  while ((match = regex.exec(text)) !== null) {
    if (lastHeading !== null) {
      sections.push({
        heading: lastHeading,
        content: text.slice(lastIndex, match.index)
      })
    }
    lastHeading = match[0].replace(/^## /, '').trim()
    lastIndex = match.index
  }
  if (lastHeading !== null) {
    sections.push({
      heading: lastHeading,
      content: text.slice(lastIndex)
    })
  }
  return sections
}

const parsedSections = computed(() => parseSections(knowledgeBaseText.value))

// effectiveText: what to show in the editor/preview
// get: slice of knowledgeBaseText for current section (or full text for "all")
// set: write back to the correct section, rebuild full text
const effectiveText = computed({
  get() {
    if (activeSection.value === null) return knowledgeBaseText.value
    const sec = parsedSections.value[activeSection.value]
    return sec ? sec.content : knowledgeBaseText.value
  },
  set(val) {
    if (activeSection.value === null) {
      knowledgeBaseText.value = val
    } else if (activeSection.value < parsedSections.value.length) {
      const parts = parsedSections.value.map(s => s.content)
      parts[activeSection.value] = val
      knowledgeBaseText.value = parts.join('')
    }
  }
})

function selectSection(index) {
  if (index === null) {
    activeSection.value = null
  } else if (index >= 0 && index < parsedSections.value.length) {
    activeSection.value = index
    if (window.innerWidth <= 768) {
      showToc.value = false
    }
  }
}

// Configure marked for safe rendering
marked.setOptions({
  breaks: true,
  gfm: true
})

const renderMarkdown = (text) => {
  if (!text) return ''
  return marked(text)
}

const fetchProject = async () => {
  try {
    const response = await api.get(`/projects/${route.params.id}/`)
    project.value = response.data
    knowledgeBaseText.value = response.data.knowledge_base || ''
    knowledgeBaseOriginal.value = knowledgeBaseText.value
    activeSection.value = null
  } catch (error) {
    ElMessage.error(t('project.fetchDetailFailed'))
  }
}

const toggleEdit = () => {
  editingKnowledge.value = !editingKnowledge.value
}

const cancelEdit = () => {
  knowledgeBaseText.value = knowledgeBaseOriginal.value
  editingKnowledge.value = false
  activeSection.value = null
}

const triggerFileUpload = () => {
  fileInputRef.value?.click()
}

const handleFileUpload = (event) => {
  const file = event.target.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target.result
    if (knowledgeBaseText.value && knowledgeBaseText.value.trim()) {
      knowledgeBaseText.value = knowledgeBaseText.value.trim() + '\n\n' + content
    } else {
      knowledgeBaseText.value = content
    }
    activeSection.value = null
    ElMessage.success(`已导入: ${file.name}`)
  }
  reader.readAsText(file, 'UTF-8')
  event.target.value = ''
}

const applyTemplate = () => {
  const template = t('project.templateContent')
  if (knowledgeBaseText.value && knowledgeBaseText.value.trim()) {
    knowledgeBaseText.value = knowledgeBaseText.value.trim() + '\n\n' + template
  } else {
    knowledgeBaseText.value = template
  }
  activeSection.value = null
  ElMessage.success(t('project.templateApplied'))
}

const saveKnowledgeBase = async () => {
  savingKnowledge.value = true
  try {
    await api.patch(`/projects/${route.params.id}/`, {
      knowledge_base: knowledgeBaseText.value
    })
    ElMessage.success(t('project.knowledgeBaseSaved'))
    editingKnowledge.value = false
    knowledgeBaseOriginal.value = knowledgeBaseText.value
    activeSection.value = null
    await fetchProject()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || t('project.knowledgeBaseSaveFailed'))
  } finally {
    savingKnowledge.value = false
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
  if (!dateString) return ''
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

const addMember = async () => {
  if (!newMember.username.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  addingMember.value = true
  try {
    await api.post(`/projects/${route.params.id}/members/add/`, {
      username: newMember.username.trim(),
      role: newMember.role
    })
    ElMessage.success('成员添加成功')
    showAddMemberDialog.value = false
    newMember.username = ''
    newMember.role = 'tester'
    fetchProject()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '添加失败')
  } finally {
    addingMember.value = false
  }
}

const removeMember = async (member) => {
  try {
    await api.delete(`/projects/${route.params.id}/members/${member.id}/`)
    ElMessage.success(t('project.memberDeleteSuccess'))
    fetchProject()
  } catch (error) {
    ElMessage.error(t('project.memberDeleteFailed'))
  }
}

onMounted(() => {
  fetchProject()
})
</script>

<style lang="scss" scoped>
// Design tokens
$primary: #667eea;
$primary-light: #f0f2ff;
$bg-card: #ffffff;
$bg-subtle: #f8f9fb;
$border: #e8ecf1;
$text-primary: #1a1a2e;
$text-secondary: #8b8fa3;
$radius: 8px;

// ── Knowledge Base Layout ──

.knowledge-base-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

// Toolbar
.kb-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: $bg-subtle;
  border-radius: $radius;
  border: 1px solid $border;
}

.kb-toolbar-left {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: $text-secondary;
}

.kb-char-count {
  font-weight: 500;
  color: $text-primary;
}

.kb-update-info {
  color: $text-secondary;
}

.kb-toolbar-right {
  display: flex;
  gap: 8px;
}

// ── Two-column wrapper ──

.kb-content-wrapper {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

// ── TOC Sidebar ──

.kb-toc-sidebar {
  width: 200px;
  min-width: 200px;
  border: 1px solid $border;
  border-radius: $radius;
  background: $bg-card;
  overflow: hidden;
  position: sticky;
  top: 8px;
  max-height: calc(100vh - 200px);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.kb-toc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  color: $text-primary;
  background: $bg-subtle;
  border-bottom: 1px solid $border;
  flex-shrink: 0;
}

.kb-toc-close {
  display: none;
}

.kb-toc-list {
  overflow-y: auto;
  flex: 1;
  padding: 4px 0;
}

.kb-toc-item {
  padding: 9px 14px 9px 16px;
  font-size: 13px;
  color: $text-secondary;
  cursor: pointer;
  transition: all 0.15s ease;
  border-left: 3px solid transparent;
  line-height: 1.4;

  &:hover {
    background: $primary-light;
    color: $primary;
  }

  &.kb-toc-item-active {
    background: $primary-light;
    color: $primary;
    border-left-color: $primary;
    font-weight: 500;
  }
}

.kb-toc-item-all {
  font-weight: 500;
  border-bottom: 1px solid $border;
  margin-bottom: 2px;
  padding-bottom: 10px;
}

.kb-toc-item-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

// ── Content area ──

.kb-content-area {
  flex: 1;
  min-width: 0;
}

.kb-toc-toggle {
  display: none;
  margin-bottom: 10px;
  width: 100%;
  justify-content: flex-start;
}

// Section indicator
.kb-section-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.kb-section-hint {
  font-size: 12px;
  color: $text-secondary;
}

// Pane sub-label
.kb-pane-sub-label {
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  color: $primary;
}

// ── Split Pane (Edit Mode) ──

.kb-editor-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kb-split-pane {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  min-height: 420px;
}

.kb-pane {
  display: flex;
  flex-direction: column;
  border: 1px solid $border;
  border-radius: $radius;
  overflow: hidden;
}

.kb-pane-label {
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: $text-secondary;
  background: $bg-subtle;
  border-bottom: 1px solid $border;
  flex-shrink: 0;
}

.kb-pane-left {
  .kb-textarea {
    flex: 1;
    :deep(.el-textarea__inner) {
      height: 100%;
      min-height: 380px;
      border: none;
      border-radius: 0;
      resize: none;
      font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
      font-size: 13px;
      line-height: 1.7;
      padding: 14px;
      &:focus {
        box-shadow: none;
      }
    }
  }
}

.kb-pane-right {
  background: #fff;
}

// Save/cancel buttons
.kb-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 4px;
}

// Preview Mode
.kb-preview-area {
  border: 1px solid $border;
  border-radius: $radius;
  min-height: 300px;
  background: #fff;
}

// Empty state
.kb-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: $text-secondary;

  .kb-empty-icon {
    font-size: 48px;
    margin-bottom: 12px;
  }

  p {
    margin: 0 0 16px 0;
    font-size: 14px;
  }
}

// ── Markdown Preview Container (scoped — applies to the wrapper div) ──

.markdown-body {
  padding: 24px 28px;
  font-size: 14px;
  line-height: 1.75;
  color: $text-primary;
  word-wrap: break-word;
  overflow-x: auto;
}

// ── Members & Environments ──

.members-section, .environments-section {
  padding: 20px 0;
}

// ── Responsive ──

@media (max-width: 768px) {
  .kb-content-wrapper {
    flex-direction: column;
  }

  .kb-toc-toggle {
    display: inline-flex;
  }

  .kb-toc-sidebar {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 1000;
    width: 260px;
    height: 100vh;
    max-height: 100vh;
    border-radius: 0;
    transform: translateX(-100%);
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 0 0 rgba(0,0,0,0);

    &.kb-toc-open {
      transform: translateX(0);
      box-shadow: 4px 0 24px rgba(0,0,0,0.12);
    }
  }

  .kb-toc-close {
    display: inline-flex;
  }

  .kb-split-pane {
    grid-template-columns: 1fr;
  }

  .kb-toolbar {
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }
}
</style>

<!-- Unscoped styles for v-html rendered markdown content -->
<style lang="scss">
// Design tokens (duplicated since unscoped can't access scoped vars)
$primary: #667eea;
$primary-light: #f0f2ff;
$border: #e8ecf1;
$text-primary: #1a1a2e;
$text-secondary: #8b8fa3;
$radius: 8px;
$table-border: #d0d5dd;

.markdown-body {
  // ── Headings ──
  h1, h2, h3, h4, h5, h6 {
    margin-top: 24px;
    margin-bottom: 12px;
    font-weight: 600;
    line-height: 1.4;
    color: $text-primary;

    &:first-child {
      margin-top: 0;
    }
  }

  h1 { font-size: 1.6em; border-bottom: 2px solid $border; padding-bottom: 8px; }
  h2 { font-size: 1.35em; border-bottom: 1px solid $border; padding-bottom: 6px; }
  h3 { font-size: 1.18em; }
  h4 { font-size: 1.05em; }

  // ── Paragraphs & Lists ──
  p {
    margin-top: 0;
    margin-bottom: 12px;
  }

  ul, ol {
    padding-left: 24px;
    margin-bottom: 12px;
  }

  li {
    margin-bottom: 4px;
  }

  // ── Inline Code ──
  code {
    padding: 2px 6px;
    font-size: 0.88em;
    background: #f0f0f5;
    border-radius: 3px;
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
    color: #d63384;
  }

  // ── Code Blocks ──
  pre {
    padding: 14px 18px;
    background: #1e1e2e;
    border-radius: $radius;
    overflow-x: auto;
    margin-bottom: 14px;

    code {
      padding: 0;
      background: transparent;
      color: #cdd6f4;
      font-size: 0.85em;
      line-height: 1.6;
    }
  }

  // ── Blockquote ──
  blockquote {
    margin: 0 0 14px 0;
    padding: 10px 16px;
    border-left: 4px solid $primary;
    background: $primary-light;
    color: darken($primary, 15%);
    border-radius: 0 $radius $radius 0;

    p:last-child {
      margin-bottom: 0;
    }
  }

  // ── Tables ──
  table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 16px;
    font-size: 13px;
    border: 1px solid $table-border;
    border-radius: $radius;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  }

  thead th {
    background: #f5f6fa;
    color: $text-primary;
    font-weight: 600;
    font-size: 12.5px;
    padding: 10px 14px;
    border: 1px solid $table-border;
    text-align: left;
  }

  tbody {
    td {
      padding: 10px 14px;
      border: 1px solid $table-border;
      color: $text-primary;
      vertical-align: middle;

      &:first-child {
        font-weight: 600;
        color: darken($primary, 5%);
        background: #fafbff;
        white-space: nowrap;
      }
    }

    tr {
      transition: background 0.1s ease;

      &:nth-child(even) {
        background: #fcfcfd;
      }

      &:hover {
        background: #f3f4fa;
      }
    }
  }

  // Fallback: bare th/td (no thead/tbody)
  th {
    background: #f5f6fa;
    color: $text-primary;
    font-weight: 600;
    font-size: 12.5px;
    padding: 10px 14px;
    border: 1px solid $table-border;
    text-align: left;
  }

  td {
    padding: 10px 14px;
    border: 1px solid $table-border;
    text-align: left;
    vertical-align: middle;

    &:first-child {
      font-weight: 600;
      color: darken($primary, 5%);
      background: #fafbff;
      white-space: nowrap;
    }
  }

  tr {
    transition: background 0.1s ease;

    &:nth-child(even) {
      background: #fcfcfd;
    }

    &:hover {
      background: #f3f4fa;
    }
  }

  // ── Misc ──
  hr {
    border: none;
    height: 1px;
    background: $border;
    margin: 20px 0;
  }

  a {
    color: $primary;
    text-decoration: none;
    &:hover {
      text-decoration: underline;
    }
  }

  img {
    max-width: 100%;
    border-radius: $radius;
  }
}
</style>
