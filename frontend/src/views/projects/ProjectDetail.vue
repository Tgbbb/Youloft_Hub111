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

            <!-- 知识背景编辑区 -->
            <div class="knowledge-base-section" style="margin-top: 20px;">
              <div class="section-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h3 style="margin: 0;">📋 {{ $t('project.knowledgeBase') }}</h3>
                <el-button type="primary" size="small" @click="editingKnowledge = !editingKnowledge">
                  {{ editingKnowledge ? $t('common.cancel') : $t('common.edit') }}
                </el-button>
              </div>
              <template v-if="editingKnowledge">
                <el-input
                  v-model="knowledgeBaseText"
                  type="textarea"
                  :rows="10"
                  :placeholder="$t('project.knowledgeBasePlaceholder')"
                  style="margin-bottom: 10px;" />
                <el-button type="success" size="small" @click="saveKnowledgeBase" :loading="savingKnowledge">
                  {{ $t('common.save') }}
                </el-button>
              </template>
              <template v-else>
                <div class="knowledge-base-preview" style="background: #f8f9fa; padding: 16px; border-radius: 6px; white-space: pre-wrap; min-height: 60px;">
                  {{ project.knowledge_base || $t('project.noKnowledgeBase') }}
                </div>
              </template>
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
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import dayjs from 'dayjs'

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
const savingKnowledge = ref(false)

const fetchProject = async () => {
  try {
    const response = await api.get(`/projects/${route.params.id}/`)
    project.value = response.data
    knowledgeBaseText.value = response.data.knowledge_base || ''
  } catch (error) {
    ElMessage.error(t('project.fetchDetailFailed'))
  }
}

const saveKnowledgeBase = async () => {
  savingKnowledge.value = true
  try {
    await api.patch(`/projects/${route.params.id}/`, {
      knowledge_base: knowledgeBaseText.value
    })
    ElMessage.success('知识背景已保存')
    editingKnowledge.value = false
    project.value.knowledge_base = knowledgeBaseText.value
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '保存失败')
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
.members-section, .environments-section {
  padding: 20px 0;
}
</style>