<template>
  <div class="knowledge-base-page">
    <div class="page-header">
      <h1>知识库管理</h1>
      <p>管理 RAG 知识库、上传文档、查看分块。Agent 在回答业务问题时将自动检索已启用的知识库。</p>
    </div>

    <el-row :gutter="16">
      <!-- 左侧：知识库列表 -->
      <el-col :span="9">
        <el-card class="section-card" v-loading="loading">
          <template #header>
            <div class="card-header">
              <div class="card-title">
                <el-icon><Collection /></el-icon>
                <span>知识库列表（{{ knowledgeBases.length }}）</span>
              </div>
              <el-button type="primary" size="small" @click="openCreateDialog">
                <el-icon><Plus /></el-icon>新建
              </el-button>
            </div>
          </template>

          <el-empty v-if="!loading && knowledgeBases.length === 0" description="暂无知识库，点击右上角新建" />

          <div v-else class="kb-list">
            <div
              v-for="kb in knowledgeBases"
              :key="kb.id"
              class="kb-item"
              :class="{ active: selectedKbId === kb.id }"
              @click="selectKb(kb)"
            >
              <div class="kb-item-header">
                <span class="kb-name">
                  <el-tag v-if="kb.is_active" size="small" type="success" effect="light">启用</el-tag>
                  <el-tag v-else size="small" type="info" effect="light">停用</el-tag>
                  <strong>{{ kb.name }}</strong>
                </span>
                <el-dropdown @command="(cmd) => onItemCommand(cmd, kb)" trigger="click">
                  <el-button text size="small" @click.stop>
                    <el-icon><MoreFilled /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">编辑</el-dropdown-item>
                      <el-dropdown-item command="toggle">
                        {{ kb.is_active ? '停用' : '启用' }}
                      </el-dropdown-item>
                      <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
              <div class="kb-item-desc">{{ kb.description || '（无描述）' }}</div>
              <div class="kb-item-stats">
                <span><el-icon><Document /></el-icon> {{ kb.document_count }} 文档</span>
                <span><el-icon><Operation /></el-icon> {{ kb.chunk_count }} 分块</span>
                <span><el-icon><Cpu /></el-icon> {{ kb.embedding_model }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：详情面板 -->
      <el-col :span="15">
        <el-card v-if="!selectedKb" class="section-card">
          <el-empty description="请选择左侧知识库查看详情" />
        </el-card>

        <template v-else>
          <!-- 基本信息 -->
          <el-card class="section-card" style="margin-bottom: 16px;">
            <template #header>
              <div class="card-header">
                <div class="card-title">
                  <el-icon><InfoFilled /></el-icon>
                  <span>基本信息 — {{ selectedKb.name }}</span>
                </div>
                <div>
                  <el-tag :type="selectedKb.is_active ? 'success' : 'info'">
                    {{ selectedKb.is_active ? '已启用' : '已停用' }}
                  </el-tag>
                </div>
              </div>
            </template>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="知识库ID">{{ selectedKb.id }}</el-descriptions-item>
              <el-descriptions-item label="Embedding模型">{{ selectedKb.embedding_model }}</el-descriptions-item>
              <el-descriptions-item label="向量维度">{{ selectedKb.embedding_dim }}</el-descriptions-item>
              <el-descriptions-item label="分块大小">{{ selectedKb.chunk_size }} 字符</el-descriptions-item>
              <el-descriptions-item label="分块重叠">{{ selectedKb.chunk_overlap }} 字符</el-descriptions-item>
              <el-descriptions-item label="创建人">{{ selectedKb.created_by_name || '-' }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatTime(selectedKb.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ formatTime(selectedKb.updated_at) }}</el-descriptions-item>
              <el-descriptions-item label="描述" :span="2">
                {{ selectedKb.description || '（无描述）' }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>

          <!-- 文档管理 -->
          <el-card class="section-card">
            <template #header>
              <div class="card-header">
                <div class="card-title">
                  <el-icon><Folder /></el-icon>
                  <span>文档列表（{{ documents.length }}）</span>
                </div>
                <div>
                  <el-upload
                    :http-request="customUpload"
                    :show-file-list="false"
                    accept=".xmind,.pdf,.docx,.md,.txt"
                    :before-upload="beforeUpload"
                    style="display: inline-block; margin-right: 8px;"
                  >
                    <el-button type="primary" size="small" :loading="uploading">
                      <el-icon><Upload /></el-icon>上传文档
                    </el-button>
                  </el-upload>
                  <el-button size="small" @click="loadDocuments">
                    <el-icon><Refresh /></el-icon>刷新
                  </el-button>
                  <el-button
                    size="small"
                    type="success"
                    :loading="exporting"
                    @click="exportMarkdown"
                    style="margin-left: 8px;"
                  >
                    <el-icon><Download /></el-icon>导出 Markdown
                  </el-button>
                </div>
              </div>
            </template>

            <el-alert
              v-if="uploading"
              :title="`处理中：${uploadingFileName}（可能需要 1-2 分钟）`"
              type="info"
              :closable="false"
              show-icon
              style="margin-bottom: 12px;"
            />

            <el-table :data="documents" border stripe>
              <el-table-column prop="file_name" label="文件名" min-width="180">
                <template #default="{ row }">
                  <el-icon style="vertical-align: middle; margin-right: 4px;">
                    <component :is="getFileIcon(row.file_type)" />
                  </el-icon>
                  {{ row.file_name }}
                </template>
              </el-table-column>
              <el-table-column prop="file_type" label="类型" width="80">
                <template #default="{ row }">
                  <el-tag size="small">{{ row.file_type.toUpperCase() }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="大小" width="100">
                <template #default="{ row }">
                  {{ row.file_size_kb }} KB
                </template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="statusType(row.status)" size="small">
                    {{ statusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="total_chunks" label="分块数" width="80" align="center" />
              <el-table-column label="上传时间" width="160">
                <template #default="{ row }">
                  {{ formatTime(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="180" fixed="right">
                <template #default="{ row }">
                  <el-button text type="primary" size="small" @click="viewChunks(row)">
                    查看分块
                  </el-button>
                  <el-button text type="danger" size="small" @click="deleteDocument(row)">
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-alert
              v-if="documents.length === 0"
              title="暂无文档"
              type="info"
              :closable="false"
              show-icon
              style="margin-top: 12px;"
            />
          </el-card>

          <!-- 变更日志（AI 自动新增/更新/版本/删除） -->
          <el-card class="section-card" style="margin-top: 16px;">
            <template #header>
              <div class="card-header">
                <div class="card-title">
                  <el-icon><Histogram /></el-icon>
                  <span>变更日志（{{ updateLogsTotal }}）</span>
                </div>
                <div>
                  <el-select
                    v-model="updateLogsDays"
                    size="small"
                    style="width: 100px; margin-right: 8px;"
                    @change="loadUpdateLogs"
                  >
                    <el-option label="近 1 天" :value="1" />
                    <el-option label="近 7 天" :value="7" />
                    <el-option label="近 30 天" :value="30" />
                  </el-select>
                  <el-select
                    v-model="updateLogsAction"
                    size="small"
                    style="width: 110px; margin-right: 8px;"
                    clearable
                    placeholder="全部类型"
                    @change="loadUpdateLogs"
                  >
                    <el-option label="新增" value="created" />
                    <el-option label="更新" value="updated" />
                    <el-option label="新增版本" value="new_version" />
                    <el-option label="软删除" value="deleted" />
                  </el-select>
                  <el-button size="small" @click="loadUpdateLogs">
                    <el-icon><Refresh /></el-icon>刷新
                  </el-button>
                </div>
              </div>
            </template>

            <el-table :data="updateLogs" border stripe v-loading="updateLogsLoading" max-height="400">
              <el-table-column label="时间" width="160">
                <template #default="{ row }">
                  {{ formatTime(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column label="动作" width="100">
                <template #default="{ row }">
                  <el-tag :type="actionTagType(row.action)" size="small">
                    {{ row.action_display }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="内容摘要" min-width="280">
                <template #default="{ row }">
                  <span class="log-summary">{{ row.summary }}</span>
                </template>
              </el-table-column>
              <el-table-column label="Chunk" width="100" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.chunk_id" size="small" type="info">#{{ row.chunk_id }}</el-tag>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="替代旧版" width="100" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.superseded_chunk_id" size="small" type="warning">
                    #{{ row.superseded_chunk_id }}
                  </el-tag>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="操作人" width="100">
                <template #default="{ row }">
                  {{ row.user || 'system' }}
                </template>
              </el-table-column>
            </el-table>

            <el-alert
              v-if="!updateLogsLoading && updateLogs.length === 0"
              title="暂无变更记录"
              type="info"
              :closable="false"
              show-icon
              style="margin-top: 12px;"
            />

            <div class="update-log-tip" v-if="updateLogs.length > 0">
              <el-icon><InfoFilled /></el-icon>
              <span>这些记录由 AI 通过 <code>add_or_update_knowledge</code> / <code>delete_knowledge</code> 工具产生，可在助手中说"更新到知识库"触发。</span>
            </div>
          </el-card>
        </template>
      </el-col>
    </el-row>

    <!-- 创建/编辑知识库弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingKb ? '编辑知识库' : '新建知识库'"
      width="500px"
    >
      <el-form :model="kbForm" :rules="kbRules" ref="kbFormRef" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="kbForm.name" placeholder="如：Linkup APP 功能清单" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="kbForm.description" type="textarea" :rows="3" placeholder="可选，描述知识库用途" />
        </el-form-item>
        <el-form-item label="Embedding" prop="embedding_model">
          <el-input v-model="kbForm.embedding_model" placeholder="deepseek-embedding" />
        </el-form-item>
        <el-form-item label="分块大小" prop="chunk_size">
          <el-input-number v-model="kbForm.chunk_size" :min="100" :max="2000" :step="50" />
          <span class="form-tip">字符数，建议 300-800</span>
        </el-form-item>
        <el-form-item label="分块重叠" prop="chunk_overlap">
          <el-input-number v-model="kbForm.chunk_overlap" :min="0" :max="200" :step="10" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="kbForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveKb" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分块查看弹窗 -->
    <el-dialog
      v-model="chunksDialogVisible"
      :title="`分块预览 — ${currentDoc?.file_name || ''}`"
      width="800px"
    >
      <el-table :data="chunks" border max-height="500">
        <el-table-column prop="chunk_index" label="序号" width="80" align="center" />
        <el-table-column prop="content" label="内容">
          <template #default="{ row }">
            <pre class="chunk-content">{{ row.content }}</pre>
          </template>
        </el-table-column>
        <el-table-column label="长度" width="80" align="center">
          <template #default="{ row }">{{ row.content_length }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="chunksPage"
        v-model:page-size="chunksPageSize"
        :page-sizes="[20, 50, 100]"
        :total="chunksTotal"
        layout="total, sizes, prev, pager, next"
        @current-change="loadChunks"
        @size-change="loadChunks"
        style="margin-top: 12px; justify-content: flex-end;"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Collection, Plus, MoreFilled, Document, Operation, Cpu,
  InfoFilled, Folder, Upload, Refresh, Histogram, Download,
} from '@element-plus/icons-vue'
import {
  listKnowledgeBases,
  createKnowledgeBase,
  updateKnowledgeBase,
  partialUpdateKnowledgeBase,
  deleteKnowledgeBase,
  getKnowledgeBaseDocuments,
  uploadKnowledgeDocument,
  deleteKnowledgeDocument,
  getKnowledgeBaseChunks,
  getKnowledgeUpdateLogs,
  exportKnowledgeBaseMarkdown,
} from '@/api/assistant'

const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const uploadingFileName = ref('')
const exporting = ref(false)
const knowledgeBases = ref([])
const selectedKbId = ref(null)
const selectedKb = ref(null)
const documents = ref([])

const dialogVisible = ref(false)
const editingKb = ref(null)
const kbFormRef = ref(null)
const kbForm = reactive({
  name: '',
  description: '',
  embedding_model: 'deepseek-embedding',
  chunk_size: 500,
  chunk_overlap: 50,
  is_active: true,
})
const kbRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  embedding_model: [{ required: true, message: '请输入 embedding 模型', trigger: 'blur' }],
  chunk_size: [{ required: true, message: '请输入分块大小', trigger: 'blur' }],
}

const chunksDialogVisible = ref(false)
const currentDoc = ref(null)
const chunks = ref([])
const chunksTotal = ref(0)
const chunksPage = ref(1)
const chunksPageSize = ref(20)

// 变更日志
const updateLogs = ref([])
const updateLogsTotal = ref(0)
const updateLogsLoading = ref(false)
const updateLogsDays = ref(7)
const updateLogsAction = ref('')

const fileIconMap = {
  xmind: Document,
  pdf: Document,
  docx: Document,
  md: Document,
  txt: Document,
}

const statusMap = {
  pending: { label: '待处理', type: 'info' },
  parsing: { label: '解析中', type: 'warning' },
  embedding: { label: '向量化中', type: 'warning' },
  done: { label: '完成', type: 'success' },
  failed: { label: '失败', type: 'danger' },
}

const actionTagMap = {
  created: 'success',
  updated: 'primary',
  new_version: 'warning',
  deleted: 'danger',
}

const statusLabel = (s) => statusMap[s]?.label || s
const statusType = (s) => statusMap[s]?.type || 'info'
const getFileIcon = (t) => fileIconMap[t] || Document
const actionTagType = (a) => actionTagMap[a] || 'info'
const formatTime = (t) => t ? new Date(t).toLocaleString('zh-CN') : '-'

onMounted(() => {
  loadKnowledgeBases()
})

async function loadKnowledgeBases() {
  loading.value = true
  try {
    const res = await listKnowledgeBases()
    knowledgeBases.value = res.data.results || res.data || []
  } catch (e) {
    ElMessage.error('加载知识库列表失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

function selectKb(kb) {
  selectedKbId.value = kb.id
  selectedKb.value = kb
  loadDocuments()
  loadUpdateLogs()
}

async function loadDocuments() {
  if (!selectedKbId.value) return
  try {
    const res = await getKnowledgeBaseDocuments(selectedKbId.value)
    documents.value = res.data || []
  } catch (e) {
    ElMessage.error('加载文档列表失败: ' + (e.response?.data?.detail || e.message))
  }
}

function openCreateDialog() {
  editingKb.value = null
  Object.assign(kbForm, {
    name: '',
    description: '',
    embedding_model: 'deepseek-embedding',
    chunk_size: 500,
    chunk_overlap: 50,
    is_active: true,
  })
  dialogVisible.value = true
}

function openEditDialog(kb) {
  editingKb.value = kb
  Object.assign(kbForm, {
    name: kb.name,
    description: kb.description,
    embedding_model: kb.embedding_model,
    chunk_size: kb.chunk_size,
    chunk_overlap: kb.chunk_overlap,
    is_active: kb.is_active,
  })
  dialogVisible.value = true
}

async function saveKb() {
  await kbFormRef.value.validate()
  saving.value = true
  try {
    if (editingKb.value) {
      await updateKnowledgeBase(editingKb.value.id, kbForm)
      ElMessage.success('已更新')
    } else {
      await createKnowledgeBase(kbForm)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    loadKnowledgeBases()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

async function onItemCommand(cmd, kb) {
  if (cmd === 'edit') openEditDialog(kb)
  else if (cmd === 'toggle') {
    try {
      await partialUpdateKnowledgeBase(kb.id, { is_active: !kb.is_active })
      ElMessage.success(kb.is_active ? '已停用' : '已启用')
      loadKnowledgeBases()
      if (selectedKbId.value === kb.id) {
        selectedKb.value = { ...kb, is_active: !kb.is_active }
      }
    } catch (e) {
      ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
    }
  } else if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm(
        `确定要删除知识库「${kb.name}」吗？该操作会同时删除所有文档和分块。`,
        '删除确认',
        { type: 'warning' }
      )
      await deleteKnowledgeBase(kb.id)
      ElMessage.success('已删除')
      if (selectedKbId.value === kb.id) {
        selectedKb.value = null
        selectedKbId.value = null
        documents.value = []
      }
      loadKnowledgeBases()
    } catch (e) {
      if (e !== 'cancel') {
        ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
      }
    }
  }
}

function beforeUpload(file) {
  const validExts = ['xmind', 'pdf', 'docx', 'md', 'txt']
  const ext = file.name.split('.').pop().toLowerCase()
  if (!validExts.includes(ext)) {
    ElMessage.error(`不支持的文件类型: .${ext}`)
    return false
  }
  if (file.size > 100 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 100MB')
    return false
  }
  return true
}

async function customUpload(option) {
  const { file } = option
  uploading.value = true
  uploadingFileName.value = file.name
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await uploadKnowledgeDocument(selectedKbId.value, formData)
    ElMessage.success('上传成功，开始处理文档')
    // 定时刷新直到状态变化
    setTimeout(() => {
      loadDocuments()
      loadKnowledgeBases()
    }, 3000)
  } catch (e) {
    ElMessage.error('上传失败: ' + (e.response?.data?.detail || e.response?.data?.error || e.message))
  } finally {
    uploading.value = false
    uploadingFileName.value = ''
  }
}

async function deleteDocument(doc) {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档「${doc.file_name}」吗？相关分块会被一起删除。`,
      '删除确认',
      { type: 'warning' }
    )
    await deleteKnowledgeDocument(selectedKbId.value, doc.id)
    ElMessage.success('已删除')
    loadDocuments()
    loadKnowledgeBases()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

async function viewChunks(doc) {
  currentDoc.value = doc
  chunksDialogVisible.value = true
  chunksPage.value = 1
  await loadChunks()
}

async function loadChunks() {
  if (!currentDoc.value) return
  try {
    const res = await getKnowledgeBaseChunks(selectedKbId.value, {
      limit: chunksPageSize.value,
      offset: (chunksPage.value - 1) * chunksPageSize.value,
    })
    // 后端 chunks API 返回的是该 KB 全部 chunks，不分文档 —— 这里做过滤
    const all = res.data?.items || []
    chunks.value = all.filter((c) => c.document === currentDoc.value.id)
    chunksTotal.value = chunks.value.length
  } catch (e) {
    ElMessage.error('加载分块失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function loadUpdateLogs() {
  if (!selectedKbId.value) return
  updateLogsLoading.value = true
  try {
    const params = { days: updateLogsDays.value, limit: 50 }
    if (updateLogsAction.value) params.action = updateLogsAction.value
    const res = await getKnowledgeUpdateLogs(selectedKbId.value, params)
    updateLogs.value = res.data?.items || []
    updateLogsTotal.value = res.data?.total || 0
  } catch (e) {
    ElMessage.error('加载变更日志失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    updateLogsLoading.value = false
  }
}

async function exportMarkdown() {
  if (!selectedKbId.value) {
    ElMessage.warning('请先选择左侧知识库')
    return
  }
  exporting.value = true
  try {
    const res = await exportKnowledgeBaseMarkdown(selectedKbId.value, {
      include_log: 1,
      log_days: 7,
    })
    // 从 Content-Disposition 提取文件名（兼容中文）
    const dispo = res.headers?.['content-disposition'] || ''
    let filename = `${selectedKb.value?.name || 'knowledge_base'}.md`
    const m = dispo.match(/filename\*=UTF-8''([^;]+)/)
    if (m) {
      filename = decodeURIComponent(m[1])
    } else {
      const m2 = dispo.match(/filename="?([^";]+)"?/)
      if (m2) filename = m2[1]
    }
    // 创建 blob URL 并触发下载
    const blob = new Blob([res.data], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出：${filename}`)
  } catch (e) {
    ElMessage.error('导出失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.knowledge-base-page {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0 0 4px 0;
  font-size: 22px;
}

.page-header p {
  margin: 0;
  color: #909399;
  font-size: 13px;
}

.section-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}

.kb-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 600px;
  overflow-y: auto;
}

.kb-item {
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.kb-item:hover {
  border-color: #409eff;
  background: #f5f7fa;
}

.kb-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.kb-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.kb-name {
  display: flex;
  align-items: center;
  gap: 6px;
}

.kb-item-desc {
  color: #606266;
  font-size: 13px;
  margin-bottom: 8px;
  min-height: 20px;
}

.kb-item-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
}

.kb-item-stats .el-icon {
  vertical-align: middle;
  margin-right: 2px;
}

.form-tip {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}

.chunk-content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Microsoft YaHei', monospace;
  font-size: 13px;
  max-height: 80px;
  overflow-y: auto;
}

.log-summary {
  font-size: 13px;
  color: #303133;
}

.update-log-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 12px;
  background: #f0f9ff;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
}

.update-log-tip code {
  background: #fff;
  padding: 1px 4px;
  border-radius: 3px;
  font-family: 'Consolas', monospace;
  font-size: 12px;
  color: #409eff;
}
</style>
