<template>
  <div class="ag-shell" data-ark-theme="endfield" data-ark-depth="moderate">
    <!-- Grid -->
    <div class="ag-grid" aria-hidden="true"></div>

    <!-- ====== Zone A: Header ====== -->
    <section class="ag-zone ag-zone--head">
      <header class="ag-zone__bar">
        <span class="ag-zone__kicker">PROJECT / DETAIL</span>
        <span class="ag-zone__rule" aria-hidden="true"></span>
        <span class="ag-zone__code">{{ project?.name || '' }}</span>
      </header>
      <div class="ag-head">
        <h1 class="ag-head__title">{{ $t('project.projectDetail') }}</h1>
        <div class="ag-head__actions">
          <button class="ag-btn ag-btn--ghost" @click="$router.back()">← {{ $t('common.back') }}</button>
        </div>
      </div>
    </section>

    <!-- ====== Zone B: Content ====== -->
    <section class="ag-zone ag-zone--content">
      <div class="ag-tabs">
        <button class="ag-tab" :class="{ 'is-active': activeTab === 'info' }" @click="activeTab = 'info'">{{ $t('project.projectInfo') }}</button>
        <button class="ag-tab" :class="{ 'is-active': activeTab === 'knowledge' }" @click="activeTab = 'knowledge'">{{ $t('project.knowledgeBaseTab') }}</button>
        <button class="ag-tab" :class="{ 'is-active': activeTab === 'members' }" @click="activeTab = 'members'">{{ $t('project.projectMembers') }}</button>
        <button class="ag-tab" :class="{ 'is-active': activeTab === 'environments' }" @click="activeTab = 'environments'">{{ $t('project.environments') }}</button>
      </div>

      <div v-if="activeTab === 'info'" class="ag-pane">
        <div v-if="project">
          <div class="ag-info">
            <div class="ag-info__row"><label>{{ $t('project.projectName') }}</label><span>{{ project.name }}</span></div>
            <div class="ag-info__row"><label>{{ $t('project.status') }}</label><span class="ag-badge" :class="'ag-badge--' + project.status">{{ getStatusText(project.status) }}</span></div>
            <div class="ag-info__row"><label>{{ $t('project.owner') }}</label><span>{{ project.owner?.username }}</span></div>
            <div class="ag-info__row"><label>{{ $t('project.createdAt') }}</label><span>{{ formatDate(project.created_at) }}</span></div>
            <div class="ag-info__row ag-info__row--wide"><label>{{ $t('project.projectDescription') }}</label><span>{{ project.description || $t('project.noDescription') }}</span></div>
          </div>
        </div>
      </div>

        <!-- 知识背景 Tab -->
        <div v-if="activeTab === 'knowledge'" class="ag-pane">
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
                <input
                  ref="fileInputRef"
                  type="file"
                  accept=".md,.txt,.markdown"
                  style="display: none"
                  @change="handleFileUpload" />
                <button class="ag-btn ag-btn--sm ag-btn--ghost" @click="triggerFileUpload">{{ $t('project.uploadMd') }}</button>
                <button class="ag-btn ag-btn--sm ag-btn--ghost" @click="applyTemplate">{{ $t('project.useTemplate') }}</button>
                <button
                  v-if="parsedSections.length > 0"
                  class="ag-btn ag-btn--sm"
                  :class="{ 'ag-btn--ok': globalEditMode }"
                  @click="globalEditMode = !globalEditMode">
                  {{ globalEditMode ? $t('project.preview') : $t('project.rawEdit') }}
                </button>
                <button class="ag-btn ag-btn--sm ag-btn--ok" @click="saveKnowledgeBase" :disabled="savingKnowledge">
                  {{ savingKnowledge ? '保存中…' : $t('common.save') }}
                </button>
              </div>
            </div>

            <!-- ===== 空状态 ===== -->
            <div v-if="!knowledgeBaseText" class="ag-empty">
              <div class="ag-empty__icon">KB</div>
              <p>{{ $t('project.noKnowledgeBase') }}</p>
              <button class="ag-btn ag-btn--ok" @click="addSection()">{{ $t('project.addFirstSection') }}</button>
              <div class="ag-empty__sub">
                <button class="ag-btn ag-btn--sm ag-btn--ghost" @click="triggerFileUpload">{{ $t('project.uploadMd') }}</button>
                <button class="ag-btn ag-btn--sm ag-btn--ghost" @click="applyTemplate">{{ $t('project.useTemplate') }}</button>
              </div>
            </div>

            <!-- ===== 主体：目录侧边栏 + 内容区 ===== -->
            <div class="kb-content-wrapper" v-else>
              <!-- TOC Sidebar -->
              <aside
                class="kb-toc-sidebar"
                :class="{ 'kb-toc-open': showToc }"
                v-if="parsedSections.length > 0"
              >
                <div class="kb-toc-header">
                  <span>{{ $t('project.tableOfContents') }}</span>
                  <button class="kb-toc-close" @click="showToc = false" aria-label="close">×</button>
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
                <div class="kb-toc-footer">
                  <button class="ag-btn ag-btn--sm ag-btn--ghost ag-w100" @click="addSection()">+ {{ $t('project.addSection') }}</button>
                </div>
              </aside>

              <!-- Content Area -->
              <div class="kb-content-area">
                <!-- Mobile TOC toggle -->
                <button
                  v-if="parsedSections.length > 0"
                  class="ag-btn ag-btn--sm ag-btn--ghost kb-toc-toggle"
                  @click="showToc = !showToc">
                  {{ $t('project.tableOfContents') }}
                </button>

                <!-- ===== 全局 Raw 编辑模式（高级用户） ===== -->
                <div class="kb-editor-area" v-if="globalEditMode">
                  <div class="kb-split-pane">
                    <div class="kb-pane kb-pane-left">
                      <div class="kb-pane-label">{{ $t('common.edit') }}</div>
                      <el-input
                        v-model="knowledgeBaseText"
                        type="textarea"
                        :rows="18"
                        :placeholder="$t('project.knowledgeBasePlaceholder')"
                        class="kb-textarea" />
                    </div>
                    <div class="kb-pane kb-pane-right">
                      <div class="kb-pane-label">{{ $t('project.preview') }}</div>
                      <div class="kb-markdown-preview markdown-body" v-html="renderMarkdown(knowledgeBaseText)" />
                    </div>
                  </div>
                </div>

                <!-- ===== 区块编辑器（默认） ===== -->
                <div class="kb-blocks-area" v-else>
                  <div
                    v-for="(section, idx) in filteredSections"
                    :key="idx"
                    class="kb-section-card"
                    :class="{ 'kb-section-editing': editingSectionIndex === realSectionIndex(idx) }"
                    :id="`kb-section-${idx}`"
                  >
                    <!-- 卡片头部 -->
                    <div class="kb-section-header">
                      <span class="kb-section-heading-icon">📄</span>
                      <span class="kb-section-heading-text">{{ section.heading }}</span>
                      <el-dropdown trigger="click" class="kb-section-menu" popper-class="ag-dropdown">
                        <el-button size="small" text class="kb-section-menu-btn">
                          <el-icon><MoreFilled /></el-icon>
                        </el-button>
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item @click="renameSection(realSectionIndex(idx))">
                              <el-icon><Edit /></el-icon> {{ $t('project.renameSection') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              @click="moveSection(realSectionIndex(idx), -1)"
                              :disabled="realSectionIndex(idx) === 0">
                              <el-icon><Top /></el-icon> {{ $t('project.moveUp') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              @click="moveSection(realSectionIndex(idx), 1)"
                              :disabled="realSectionIndex(idx) === parsedSections.length - 1">
                              <el-icon><Bottom /></el-icon> {{ $t('project.moveDown') }}
                            </el-dropdown-item>
                            <el-dropdown-item divided @click="deleteSection(realSectionIndex(idx))">
                              <span class="is-danger">
                                <el-icon><Delete /></el-icon> {{ $t('project.deleteSection') }}
                              </span>
                            </el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </div>

                    <!-- 正文 -->
                    <div class="kb-section-body">
                      <!-- 编辑模式：textarea + 实时预览 -->
                      <template v-if="editingSectionIndex === realSectionIndex(idx)">
                        <div class="kb-format-toolbar" @click.stop>
                          <button class="kb-fmt-btn" title="粗体" @click="insertMdSyntax(realSectionIndex(idx), 'bold')"><b>B</b></button>
                          <button class="kb-fmt-btn" title="斜体" @click="insertMdSyntax(realSectionIndex(idx), 'italic')"><i>I</i></button>
                          <span class="kb-fmt-sep" aria-hidden="true"></span>
                          <button class="kb-fmt-btn" title="三级标题" @click="insertMdSyntax(realSectionIndex(idx), 'h3')">H3</button>
                          <button class="kb-fmt-btn" title="无序列表" @click="insertMdSyntax(realSectionIndex(idx), 'ul')">•</button>
                          <button class="kb-fmt-btn" title="有序列表" @click="insertMdSyntax(realSectionIndex(idx), 'ol')">1.</button>
                          <span class="kb-fmt-sep" aria-hidden="true"></span>
                          <button class="kb-fmt-btn" title="行内代码" @click="insertMdSyntax(realSectionIndex(idx), 'code')">&lt;/&gt;</button>
                          <button class="kb-fmt-btn" title="代码块" @click="insertMdSyntax(realSectionIndex(idx), 'codeblock')">```</button>
                          <button class="kb-fmt-btn" title="链接" @click="insertMdSyntax(realSectionIndex(idx), 'link')">🔗</button>
                          <button class="kb-fmt-btn" title="表格" @click="insertMdSyntax(realSectionIndex(idx), 'table')">⊞</button>
                        </div>
                        <div class="kb-split-pane">
                          <div class="kb-pane kb-pane-left">
                            <div class="kb-pane-label">{{ $t('common.edit') }}</div>
                            <el-input
                              :ref="el => setTextareaRef(realSectionIndex(idx), el)"
                              v-model="editingContent"
                              type="textarea"
                              :rows="Math.max(6, (editingContent || '').split('\n').length + 2)"
                              :placeholder="$t('project.sectionPlaceholder')"
                              class="kb-section-textarea" />
                          </div>
                          <div class="kb-pane kb-pane-right">
                            <div class="kb-pane-label">{{ $t('project.preview') }}</div>
                            <div class="kb-markdown-preview markdown-body" v-html="renderMarkdown(editingContent)" />
                          </div>
                        </div>
                        <div class="kb-section-edit-actions" @click.stop>
                          <button class="ag-btn ag-btn--sm ag-btn--ok" @click="exitSectionEdit()">✓ {{ $t('project.doneEditing') }}</button>
                          <span class="kb-section-edit-hint">{{ $t('project.clickOutsideHint') }}</span>
                        </div>
                      </template>

                      <!-- 预览模式 -->
                      <div v-else class="kb-section-preview markdown-body" @click="enterSectionEdit(realSectionIndex(idx))" v-html="renderMarkdown(section.content || '*（空）*')" />
                    </div>
                  </div>

                  <!-- 新增板块按钮 -->
                  <div class="kb-add-section-wrapper">
                    <button class="ag-btn kb-add-section-block" @click="addSection()">+ {{ $t('project.addSection') }}</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'members'" class="ag-pane">
          <div class="ag-pane-head">
            <button class="ag-btn ag-btn--ok" @click="showAddMemberDialog = true">+ {{ $t('project.addMember') }}</button>
          </div>
          <div class="ag-table-wrap">
            <table class="ag-table ag-table--sub">
              <thead>
                <tr>
                  <th class="ag-th">{{ $t('project.username') }}</th>
                  <th class="ag-th">{{ $t('project.email') }}</th>
                  <th class="ag-th ag-th--role">{{ $t('project.role') }}</th>
                  <th class="ag-th">{{ $t('project.joinedAt') }}</th>
                  <th class="ag-th ag-th--act">{{ $t('project.actions') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in project?.members || []" :key="row.id" class="ag-tr">
                  <td class="ag-td">{{ row.user?.username }}</td>
                  <td class="ag-td">{{ row.user?.email }}</td>
                  <td class="ag-td">{{ row.role }}</td>
                  <td class="ag-td">{{ formatDate(row.joined_at) }}</td>
                  <td class="ag-td"><button class="ag-btn ag-btn--sm ag-btn--danger" @click="removeMember(row)">{{ $t('common.delete') }}</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="activeTab === 'environments'" class="ag-pane">
          <div class="ag-pane-head">
            <button class="ag-btn ag-btn--ok" @click="showAddEnvDialog = true">+ {{ $t('project.addEnvironment') }}</button>
          </div>
          <div class="ag-table-wrap">
            <table class="ag-table ag-table--sub">
              <thead>
                <tr>
                  <th class="ag-th">{{ $t('project.environmentName') }}</th>
                  <th class="ag-th">{{ $t('project.baseUrl') }}</th>
                  <th class="ag-th">{{ $t('project.description') }}</th>
                  <th class="ag-th ag-th--default">{{ $t('project.defaultEnvironment') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in project?.environments || []" :key="row.id" class="ag-tr">
                  <td class="ag-td">{{ row.name }}</td>
                  <td class="ag-td ag-td--mono">{{ row.base_url }}</td>
                  <td class="ag-td">{{ row.description }}</td>
                  <td class="ag-td">
                    <span v-if="row.is_default" class="ag-badge ag-badge--active">{{ $t('project.yes') }}</span>
                    <span v-else>{{ $t('project.no') }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
    </section>

    <!-- 添加成员弹窗 -->
    <div v-if="showAddMemberDialog" class="ag-modal" @click.self="showAddMemberDialog = false">
      <div class="ag-modal__box ag-modal__box--sm">
        <header class="ag-modal__head">
          <span class="ag-modal__kicker">PROJECT / MEMBER</span>
          <button class="ag-modal__close" @click="showAddMemberDialog = false">×</button>
        </header>
        <div class="ag-modal__body">
          <div class="ag-form">
            <div class="ag-form__group"><label>用户名</label><input v-model="newMember.username" class="ag-input" placeholder="输入用户名" /></div>
            <div class="ag-form__group"><label>角色</label>
              <select v-model="newMember.role" class="ag-select">
                <option value="viewer">观察者</option>
                <option value="tester">测试者</option>
                <option value="developer">开发者</option>
                <option value="admin">管理员</option>
              </select>
            </div>
          </div>
        </div>
        <footer class="ag-modal__foot">
          <button class="ag-btn ag-btn--ghost" @click="showAddMemberDialog = false">取消</button>
          <button class="ag-btn ag-btn--ok" @click="addMember" :disabled="addingMember">{{ addingMember ? '添加中…' : '添加' }}</button>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
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

// ── Knowledge base state ──
const editingKnowledge = ref(false)  // deprecated, kept for compat
const knowledgeBaseText = ref('')
const knowledgeBaseOriginal = ref('')
const savingKnowledge = ref(false)
const fileInputRef = ref(null)
const globalEditMode = ref(false)      // raw markdown textarea mode
const editingSectionIndex = ref(null)  // which section card is in edit mode
const textareaRefs = reactive({})      // section index → textarea element
const editingContent = ref('')         // MD text buffer for inline editing

function setTextareaRef(idx, el) {
  if (el) textareaRefs[idx] = el
}

function enterSectionEdit(idx) {
  if (globalEditMode.value) return
  // Strip leading newlines — they're structural spacing between heading and body
  // They get added back in exitSectionEdit
  const raw = parsedSections.value[idx]?.content || ''
  editingContent.value = raw.replace(/^\n+/, '')
  editingSectionIndex.value = idx
  nextTick(() => {
    // Focus the textarea
    const ta = textareaRefs[idx]
    const el = ta?.$el?.querySelector?.('textarea') || ta?.$el || ta
    if (el) {
      el.focus()
      const len = el.value?.length || 0
      el.setSelectionRange?.(len, len)
    }
  })
}

function exitSectionEdit() {
  if (editingSectionIndex.value === null) return
  const idx = editingSectionIndex.value
  const sections = parsedSections.value.slice()
  if (idx >= 0 && idx < sections.length) {
    let content = editingContent.value || ''
    // Restore leading newline (stripped on enter for clean editing)
    if (content && !content.startsWith('\n')) content = '\n' + content
    if (!content.endsWith('\n')) content += '\n'
    sections[idx].content = content
    knowledgeBaseText.value = sections.map(s => `## ${s.heading}${s.content}`).join('')
  }
  editingSectionIndex.value = null
  editingContent.value = ''
}

// ── Markdown syntax insertion ──

function insertMdSyntax(idx, type) {
  const ta = textareaRefs[idx]
  const el = ta?.$el?.querySelector?.('textarea') || ta?.$el || ta
  if (!el) return
  const text = el.value || ''
  const start = el.selectionStart ?? text.length
  const end = el.selectionEnd ?? text.length
  const selected = text.slice(start, end)

  const tpl = {
    bold:      { before: '**', after: '**', placeholder: 'bold' },
    italic:    { before: '*', after: '*', placeholder: 'italic' },
    h3:        { before: '\n### ', after: '', placeholder: '小标题', line: true },
    ul:        { before: '\n- ', after: '', placeholder: '列表项', line: true },
    ol:        { before: '\n1. ', after: '', placeholder: '列表项', line: true },
    code:      { before: '`', after: '`', placeholder: 'code' },
    codeblock: { before: '\n```\n', after: '\n```\n', placeholder: '代码' },
    link:      { before: '[', after: '](url)', placeholder: '链接文字' },
    table:     { before: '\n| 列1 | 列2 | 列3 |\n|------|------|------|\n| ', after: ' |  |  |\n', placeholder: '内容' },
  }[type]
  if (!tpl) return

  const insert = selected
    ? tpl.before + selected + tpl.after
    : tpl.before + (tpl.placeholder || '') + tpl.after

  const prefix = tpl.line && start > 0 && text[start - 1] !== '\n' ? '\n' : ''
  editingContent.value = text.slice(0, start) + prefix + insert + text.slice(end)

  nextTick(() => {
    const cursor = start + prefix.length + tpl.before.length + (selected ? selected.length : (tpl.placeholder || '').length) + tpl.after.length
    el.value = editingContent.value
    el.setSelectionRange(cursor, cursor)
    el.focus()
  })
}
const activeSection = ref(null)  // null = all, number = section index
const showToc = ref(true)

// ── Section parsing (reuses existing logic) ──

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
    lastIndex = match.index + match[0].length  // skip past the heading line
  }
  if (lastHeading !== null) {
    sections.push({
      heading: lastHeading,
      content: text.slice(lastIndex)
    })
  }
  return sections
}

// Clean up duplicated headings caused by previous bug
// Pattern: ## H1## H1\ncontent → ## H1\ncontent
function dedupeKnowledgeBase(text) {
  if (!text) return ''
  let fixed = text
  // Iterate until no more duplicates found (handles nested cases)
  let prev = ''
  while (prev !== fixed) {
    prev = fixed
    fixed = fixed.replace(/(## [^\n]+?)\1/g, '$1')
  }
  return fixed
}

const parsedSections = computed(() => parseSections(knowledgeBaseText.value))

// Filtered sections based on activeSection: null=all, number=single
const filteredSections = computed(() => {
  if (activeSection.value === null) return parsedSections.value
  const sec = parsedSections.value[activeSection.value]
  return sec ? [sec] : parsedSections.value
})

// Map filtered index back to real index in parsedSections
function realSectionIndex(filteredIdx) {
  if (activeSection.value === null) return filteredIdx
  return activeSection.value
}

// ── Full-text rebuild from sections ──

function rebuildFullText() {
  if (parsedSections.value.length === 0) return knowledgeBaseText.value
  const parts = parsedSections.value.map(s => {
    let content = s.content
    if (content && !content.startsWith('\n')) content = '\n' + content
    if (!content.endsWith('\n')) content += '\n'
    return `## ${s.heading}${content}`
  })
  return parts.join('')
}

function selectSection(index) {
  if (index === null) {
    activeSection.value = null
  } else if (index >= 0 && index < parsedSections.value.length) {
    activeSection.value = index
    if (window.innerWidth <= 768) {
      showToc.value = false
    }
    nextTick(() => {
      const el = document.getElementById(`kb-section-${index}`)
      if (el) {
        // Scroll within the content area, not the full page
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      }
    })
  }
}

// ── Section CRUD ──

async function addSection(heading) {
  if (!heading) {
    try {
      const { value } = await ElMessageBox.prompt(
        t('project.addSectionPrompt'),
        t('project.addSection'),
        { confirmButtonText: t('common.ok'), cancelButtonText: t('common.cancel') }
      )
      if (!value || !value.trim()) return
      heading = value.trim()
    } catch {
      return  // user cancelled
    }
  }
  const newBlock = `\n## ${heading}\n\n`
  knowledgeBaseText.value = knowledgeBaseText.value
    ? knowledgeBaseText.value.replace(/\n*$/, '\n') + newBlock
    : `## ${heading}\n\n`
  knowledgeBaseOriginal.value = knowledgeBaseText.value
  // Auto-enter edit on new section
  await nextTick()
  const newIdx = parsedSections.value.length - 1
  editingSectionIndex.value = newIdx
  activeSection.value = newIdx
  await nextTick()
  // Focus the new section's textarea
  await nextTick()
  const ta = textareaRefs[newIdx]
  const el = ta?.$el?.querySelector?.('textarea') || ta?.$el || ta
  if (el) {
    el.focus()
    const len = el.value?.length || 0
    el.setSelectionRange?.(len, len)
  }
}

async function renameSection(idx) {
  const section = parsedSections.value[idx]
  if (!section) return
  try {
    const { value } = await ElMessageBox.prompt(
      t('project.renameSectionPrompt'),
      t('project.renameSection'),
      {
        confirmButtonText: t('common.ok'),
        cancelButtonText: t('common.cancel'),
        inputValue: section.heading,
      }
    )
    if (!value || !value.trim()) return
    const newHeading = value.trim()
    // Replace the heading in the raw text
    const oldBlock = `## ${section.heading}`
    const newBlock = `## ${newHeading}`
    knowledgeBaseText.value = knowledgeBaseText.value.replace(oldBlock, newBlock)
    knowledgeBaseOriginal.value = knowledgeBaseText.value
  } catch {
    // cancelled
  }
}

async function deleteSection(idx) {
  const section = parsedSections.value[idx]
  if (!section) return
  try {
    await ElMessageBox.confirm(
      t('project.deleteSectionConfirm', { name: section.heading }),
      t('project.deleteSection'),
      { type: 'warning', confirmButtonText: t('common.ok'), cancelButtonText: t('common.cancel') }
    )
  } catch {
    return
  }
  // Remove the ## heading + content from raw text
  const block = `## ${section.heading}${section.content}`
  knowledgeBaseText.value = knowledgeBaseText.value.replace(block, '')
  // Clean up extra blank lines
  knowledgeBaseText.value = knowledgeBaseText.value.replace(/\n{3,}/g, '\n\n').trim()
  knowledgeBaseText.value += '\n'
  knowledgeBaseOriginal.value = knowledgeBaseText.value
  if (editingSectionIndex.value === idx) editingSectionIndex.value = null
  if (activeSection.value === idx) activeSection.value = null
}

function moveSection(idx, dir) {
  const sections = parsedSections.value.slice()
  const target = idx + dir
  if (target < 0 || target >= sections.length) return
  // Swap in array
  ;[sections[idx], sections[target]] = [sections[target], sections[idx]]
  // Rebuild full text
  knowledgeBaseText.value = sections.map(s => `## ${s.heading}${s.content}`).join('')
  knowledgeBaseOriginal.value = knowledgeBaseText.value
  if (editingSectionIndex.value === idx) editingSectionIndex.value = target
  if (activeSection.value === idx) activeSection.value = target
}

// ── Markdown rendering ──

marked.setOptions({
  breaks: true,
  gfm: true
})

const renderMarkdown = (text) => {
  if (!text) return ''
  return marked(text)
}

// ── Data & persistence ──

const fetchProject = async () => {
  try {
    const response = await api.get(`/projects/${route.params.id}/`)
    project.value = response.data
    let raw = response.data.knowledge_base || ''
    // Auto-clean duplicates from previous bug
    raw = dedupeKnowledgeBase(raw)
    if (raw !== (response.data.knowledge_base || '')) {
      // Silently fix server data
      api.patch(`/projects/${route.params.id}/`, { knowledge_base: raw }).catch(() => {})
    }
    knowledgeBaseText.value = raw
    knowledgeBaseOriginal.value = raw
    activeSection.value = null
    editingSectionIndex.value = null
    globalEditMode.value = false
  } catch (error) {
    ElMessage.error(t('project.fetchDetailFailed'))
  }
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
    knowledgeBaseOriginal.value = knowledgeBaseText.value
    activeSection.value = null
    editingSectionIndex.value = null
    ElMessage.success(t('project.fileImported', { name: file.name }))
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
  knowledgeBaseOriginal.value = knowledgeBaseText.value
  activeSection.value = null
  editingSectionIndex.value = null
  ElMessage.success(t('project.templateApplied'))
}

const saveKnowledgeBase = async () => {
  savingKnowledge.value = true
  try {
    // If editing a section, rebuild full text first
    if (editingSectionIndex.value !== null) {
      knowledgeBaseText.value = rebuildFullText()
    }
    await api.patch(`/projects/${route.params.id}/`, {
      knowledge_base: knowledgeBaseText.value
    })
    ElMessage.success(t('project.knowledgeBaseSaved'))
    editingSectionIndex.value = null
    globalEditMode.value = false
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
/* =============================================
   Ark Moderate — Project Detail
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
    display: flex; flex-direction: column; overflow: hidden;
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
   Tabs
   ============================================ */
.ag-tabs {
  display: flex; gap: 0; padding: 0 20px;
  border-bottom: 2px solid var(--ark-ink); flex-shrink: 0;
}
.ag-tab {
  all: unset; cursor: pointer;
  padding: 12px 18px 10px; font-size: 12px; font-weight: 600;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em;
  color: #777; border-bottom: 3px solid transparent; margin-bottom: -2px;
  white-space: nowrap;
  &:hover { color: var(--ark-ink); }
  &.is-active { color: var(--ark-ink); border-bottom-color: var(--ark-signal); }
  &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: 1px; }
}
.ag-pane { padding: 20px; overflow: auto; flex: 1; }

/* ============================================
   Info
   ============================================ */
.ag-info {
  border: 1px solid var(--ark-border);
  &__row {
    display: grid; grid-template-columns: 160px 1fr; gap: 16px;
    padding: 12px 16px; border-bottom: 1px solid var(--ark-border);
    &:last-child { border-bottom: none; }
    label {
      font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
      text-transform: uppercase; letter-spacing: .12em; color: #999; padding-top: 3px;
    }
    span { font-size: 13px; color: #333; line-height: 1.7; word-break: break-word; }
  }
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
.ag-w100 { width: 100%; }

/* ============================================
   Select / Input
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
}
.ag-input {
  padding: 8px 12px; border: 1px solid #ccc; font-size: 13px; color: #333;
  width: 100%; box-sizing: border-box; font-family: inherit;
  &:focus { outline: none; border-color: #fffa00; }
  &:focus-visible { outline: 2px solid #fffa00; outline-offset: 1px; }
}

/* ============================================
   Sub tables (members / environments)
   ============================================ */
.ag-pane-head { display: flex; justify-content: flex-start; margin-bottom: 14px; }
.ag-table-wrap { overflow-x: auto; }
.ag-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
  &--sub { min-width: 720px; }
  thead { border-bottom: 2px solid var(--ark-ink); }
  th, td { padding: 10px 12px; text-align: left; vertical-align: middle; }
}
.ag-th {
  font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em; color: #999; font-weight: 600;
  &--role { width: 110px; }
  &--default { width: 140px; }
  &--act { width: 110px; }
}
.ag-tr {
  border-bottom: 1px solid #eee;
  transition: background .1s;
  &:hover { background: #f8fafa; }
}
.ag-td {
  color: #444; line-height: 1.6;
  &--mono { font-family: "IBM Plex Mono", Consolas, monospace; font-size: 12px; color: #666; word-break: break-all; }
}

/* ============================================
   Knowledge base
   ============================================ */
.knowledge-base-layout { display: flex; flex-direction: column; gap: 16px; }
.kb-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; background: #fafaf8; border: 1px solid var(--ark-border);
  flex-wrap: wrap; gap: 8px;
}
.kb-toolbar-left {
  display: flex; align-items: center; gap: 8px; font-size: 12px; color: #888; flex-wrap: wrap;
}
.kb-char-count { font-weight: 700; color: var(--ark-ink); font-family: "Space Grotesk", system-ui, sans-serif; }
.kb-update-info { color: #999; font-size: 12px; }
.kb-toolbar-right { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

.kb-content-wrapper { display: flex; gap: 16px; align-items: flex-start; }

.kb-toc-sidebar {
  width: 210px; min-width: 210px; border: 1px solid var(--ark-border); background: #fff;
  display: flex; flex-direction: column; flex-shrink: 0;
  position: sticky; top: 8px; max-height: calc(100vh - 230px);
}
.kb-toc-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; font-size: 11px; font-weight: 700;
  font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .1em;
  color: var(--ark-ink); background: #fafaf8; border-bottom: 1px solid var(--ark-border); flex-shrink: 0;
}
.kb-toc-close {
  all: unset; cursor: pointer; display: none;
  width: 26px; height: 26px; align-items: center; justify-content: center;
  font-size: 18px; color: #888; line-height: 1;
  &:hover { color: var(--ark-ink); }
  &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: 1px; }
}
.kb-toc-list { overflow-y: auto; flex: 1; padding: 6px 0; }
.kb-toc-footer { padding: 8px 10px; border-top: 1px solid var(--ark-border); flex-shrink: 0; }
.kb-toc-item {
  padding: 9px 14px 9px 16px; font-size: 13px; color: #666; cursor: pointer;
  border-left: 3px solid transparent; line-height: 1.4;
  transition: background .1s, color .1s;
  &:hover { background: #f4f5f3; color: var(--ark-ink); }
  &.kb-toc-item-active { background: #fbfbe8; color: var(--ark-ink); border-left-color: var(--ark-signal); font-weight: 600; }
}
.kb-toc-item-all { font-weight: 600; border-bottom: 1px solid var(--ark-border); margin-bottom: 2px; padding-bottom: 10px; }
.kb-toc-item-text { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.kb-content-area { flex: 1; min-width: 0; max-height: calc(100vh - 250px); overflow-y: auto; }
.kb-toc-toggle { display: none; margin-bottom: 10px; width: 100%; justify-content: flex-start; }

.kb-blocks-area { display: flex; flex-direction: column; gap: 16px; }
.kb-section-card {
  border: 1px solid var(--ark-border); background: #fff;
  transition: border-color .15s;
  &:hover { border-color: #c8cac8; }
  &.kb-section-editing { border-color: var(--ark-signal); box-shadow: inset 0 3px 0 var(--ark-signal); }
}
.kb-section-header {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; background: #fafaf8; border-bottom: 1px solid var(--ark-border);
}
.kb-section-heading-icon { font-size: 14px; }
.kb-section-heading-text { flex: 1; font-size: 14px; font-weight: 700; color: var(--ark-ink); }
.kb-section-menu-btn { opacity: .45; &:hover { opacity: 1; } }

.kb-section-body { cursor: pointer; transition: background .15s; &:hover { background: #fafaf7; } }
.kb-section-preview { padding: 16px 20px; min-height: 60px; font-size: 14px; line-height: 1.7; color: #333; }

.kb-format-toolbar {
  display: flex; align-items: center; gap: 2px; padding: 6px 12px;
  background: #fafaf8; border-bottom: 1px solid var(--ark-border); flex-wrap: wrap;
  position: sticky; top: 0; z-index: 10;
}
.kb-fmt-btn {
  all: unset; cursor: pointer;
  min-width: 30px; height: 28px; padding: 0 6px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 13px; color: #666; border: 1px solid transparent;
  &:hover { color: var(--ark-ink); background: #fff; border-color: var(--ark-border); }
  &:focus-visible { outline: 2px solid var(--ark-signal); outline-offset: -2px; }
}
.kb-fmt-sep { width: 1px; height: 16px; background: var(--ark-border); margin: 0 6px; }

.kb-section-edit-actions {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 14px; background: #fafaf8; border-top: 1px solid var(--ark-border);
}
.kb-section-edit-hint { font-size: 11px; color: #999; }

.kb-add-section-wrapper { display: flex; justify-content: center; padding: 8px 0; }
.kb-add-section-block {
  width: 100%; min-height: 44px;
  border: 1px dashed #c8cac8; color: #666; background: transparent;
  &:hover { border-color: var(--ark-ink); color: var(--ark-ink); background: #fafaf7; }
}

.kb-editor-area { display: flex; flex-direction: column; gap: 12px; }
.kb-split-pane { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; min-height: 420px; }
.kb-pane { display: flex; flex-direction: column; border: 1px solid var(--ark-border); background: #fff; }
.kb-pane-label {
  padding: 8px 14px; font-size: 11px; font-weight: 700;
  font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .1em;
  color: #999; background: #fafaf8; border-bottom: 1px solid var(--ark-border); flex-shrink: 0;
}
.kb-pane-left {
  .kb-textarea {
    flex: 1;
    :deep(.el-textarea__inner) {
      height: 100%; min-height: 380px; border-radius: 0; resize: none;
      font-family: "IBM Plex Mono", Consolas, monospace;
      font-size: 13px; line-height: 1.7; padding: 14px;
      box-shadow: none;
      &:focus { box-shadow: none; }
    }
  }
}
.kb-pane-right { background: #fff; }

.kb-section-textarea {
  :deep(.el-textarea__inner) {
    border-radius: 0; box-shadow: 0 0 0 1px #c9cbc8 inset;
    font-family: inherit; font-size: 13px; line-height: 1.7;
  }
  :deep(.el-textarea__inner:focus) { box-shadow: 0 0 0 1px var(--ark-signal) inset; }
}

/* Markdown preview in cards (scoped) */
.markdown-body {
  padding: 24px 28px;
  font-size: 14px; line-height: 1.75; color: #333;
  word-wrap: break-word; overflow-x: auto;
}

/* Empty state */
.ag-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 56px 20px; color: #999; text-align: center;
  &__icon {
    font-size: 22px; font-weight: 900; font-family: "Space Grotesk", system-ui, sans-serif;
    letter-spacing: .2em; color: #ddd; margin-bottom: 14px;
  }
  p { margin: 0 0 16px; font-size: 14px; }
  &__sub { display: flex; gap: 8px; margin-top: 12px; }
}

/* ============================================
   Modal
   ============================================ */
.ag-modal {
  position: fixed; inset: 0; background: rgba(4,6,8,.72);
  display: flex; align-items: center; justify-content: center; z-index: 2000;
  &__box {
    background: #fff; width: 90%; max-width: 560px; max-height: 84vh;
    display: flex; flex-direction: column; border: 1px solid #888;
    &--sm { max-width: 480px; }
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

.ag-form {
  &__group {
    display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px;
    label {
      font-weight: 600; font-size: 11px; color: #666;
      font-family: "Space Grotesk", system-ui, sans-serif;
      text-transform: uppercase; letter-spacing: .06em;
    }
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
  .ag-zone, .ag-btn, .ag-select, .ag-input, .ag-tr, .ag-tab, .kb-toc-item, .kb-section-card,
  .kb-section-body, .kb-section-menu-btn, .kb-fmt-btn, .ag-modal__close {
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
  .ag-head__actions { width: 100%; }
  .ag-head__actions .ag-btn { flex: 1; }
  .ag-tabs { overflow-x: auto; }
  .ag-pane { padding: 14px; }
  .ag-info__row { grid-template-columns: 110px 1fr; }
  .kb-content-wrapper { flex-direction: column; }
  .kb-toc-toggle { display: inline-flex; }
  .kb-toc-sidebar {
    position: fixed; left: 0; top: 0; z-index: 1000;
    width: 260px; height: 100vh; max-height: 100vh;
    transform: translateX(-100%);
    transition: transform .25s ease;
    box-shadow: none;
    &.kb-toc-open { transform: translateX(0); box-shadow: 6px 0 20px rgba(0,0,0,.18); }
  }
  .kb-toc-close { display: inline-flex; }
  .kb-split-pane { grid-template-columns: 1fr; }
  .kb-toolbar { flex-direction: column; align-items: flex-start; }
  .kb-format-toolbar { gap: 0; }
  .ag-modal__box { width: 95%; }
}
</style>

<!-- Unscoped styles for v-html rendered markdown content -->
<style lang="scss">
/* Endfield-styled markdown (rendered via v-html) */
.markdown-body {
  h1, h2, h3, h4, h5, h6 {
    margin-top: 24px; margin-bottom: 12px;
    font-weight: 700; line-height: 1.4; color: #191919;
    &:first-child { margin-top: 0; }
  }
  h1 { font-size: 1.6em; border-bottom: 2px solid #191919; padding-bottom: 8px; }
  h2 { font-size: 1.35em; border-bottom: 1px solid #d8dad7; padding-bottom: 6px; }
  h3 { font-size: 1.18em; }
  h4 { font-size: 1.05em; }

  p { margin-top: 0; margin-bottom: 12px; }
  ul, ol { padding-left: 24px; margin-bottom: 12px; }
  li { margin-bottom: 4px; }

  code {
    padding: 2px 6px; font-size: .88em;
    background: #eceeeb; color: #191919; border: 1px solid #d8dad7;
    font-family: "IBM Plex Mono", Consolas, monospace;
  }

  pre {
    padding: 14px 18px; background: #191919;
    overflow-x: auto; margin-bottom: 14px;
    code {
      padding: 0; background: transparent; color: #f2f2f0;
      border: none; font-size: .85em; line-height: 1.6;
    }
  }

  blockquote {
    margin: 0 0 14px; padding: 10px 16px;
    border-left: 4px solid #fffa00; background: #fafaf7; color: #555;
    p:last-child { margin-bottom: 0; }
  }

  table {
    width: 100%; border-collapse: collapse; margin-bottom: 16px;
    font-size: 13px; border: 1px solid #d0d2d0;
  }
  thead th, th {
    background: #f2f2f0; color: #191919; font-weight: 700; font-size: 12.5px;
    padding: 10px 14px; border: 1px solid #d0d2d0; text-align: left;
  }
  tbody td, td {
    padding: 10px 14px; border: 1px solid #d0d2d0; color: #333; vertical-align: middle;
  }
  tbody tr, tr {
    transition: background .1s;
    &:nth-child(even) { background: #fcfcfb; }
    &:hover { background: #f4f5f3; }
  }

  hr { border: none; height: 1px; background: #d8dad7; margin: 20px 0; }
  a { color: #191919; text-decoration: underline; text-underline-offset: 3px; &:hover { color: #666; } }
  img { max-width: 100%; }
}

/* Endfield-styled section dropdown (teleported to body) */
.ag-dropdown.el-dropdown__popper {
  border-radius: 0; border: 1px solid #191919;
}
.ag-dropdown .el-dropdown-menu { padding: 4px 0; }
.ag-dropdown .el-dropdown-menu__item {
  font-size: 13px; color: #333; border-radius: 0;
  &:hover, &:focus { background: #f4f5f3; color: #191919; }
}
.ag-dropdown .el-dropdown-menu__item .is-danger,
.ag-dropdown .el-dropdown-menu__item .is-danger .el-icon {
  color: #b03a35;
}
</style>
