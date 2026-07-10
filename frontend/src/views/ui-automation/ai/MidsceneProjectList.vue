<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">Midscene 项目管理</h1>
      <el-button type="primary" @click="showForm(null)"><el-icon><Plus /></el-icon> 新建项目</el-button>
    </div>

    <div class="card-container">
      <el-table :data="projects" v-loading="loading" stripe>
        <el-table-column prop="name" label="项目名称" min-width="160" />
        <el-table-column prop="default_app_package" label="默认包名" min-width="220">
          <template #default="{ row }">
            <el-tag v-if="row.default_app_package" type="success">{{ row.default_app_package }}</el-tag>
            <span v-else class="text-muted">未配置</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="case_count" label="用例数" width="80" />
        <el-table-column prop="owner_name" label="负责人" width="100" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="showForm(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteProject(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="formVisible" :title="editingId ? '编辑项目' : '新建项目'" width="500px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="项目名称" required>
          <el-input v-model="form.name" placeholder="如：心动日常" />
        </el-form-item>
        <el-form-item label="默认包名">
          <el-input v-model="form.default_app_package" placeholder="如：com.youloft.icloser" />
          <div style="font-size:11px;color:#909399;margin-top:4px">
            所有关联此项目的用例执行时，将自动启动该应用
          </div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="saveProject" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '@/utils/api'

const loading = ref(false)
const projects = ref([])
const formVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)

const form = reactive({
  name: '',
  default_app_package: '',
  description: '',
})

const loadProjects = async () => {
  loading.value = true
  try {
    const { data } = await api.get('/ui-automation/midscene/projects/')
    projects.value = data.results || []
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const showForm = (row) => {
  if (row) {
    editingId.value = row.id
    form.name = row.name
    form.default_app_package = row.default_app_package || ''
    form.description = row.description || ''
  } else {
    editingId.value = null
    form.name = ''
    form.default_app_package = ''
    form.description = ''
  }
  formVisible.value = true
}

const saveProject = async () => {
  if (!form.name.trim()) { ElMessage.warning('请输入项目名称'); return }
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/ui-automation/midscene/projects/${editingId.value}/`, form)
      ElMessage.success('已更新')
    } else {
      await api.post('/ui-automation/midscene/projects/', form)
      ElMessage.success('已创建')
    }
    formVisible.value = false
    loadProjects()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const deleteProject = async (row) => {
  try {
    await ElMessageBox.confirm(`删除项目「${row.name}」？关联的用例不会被删除。`, '确认', { type: 'warning' })
    await api.delete(`/ui-automation/midscene/projects/${row.id}/`)
    ElMessage.success('已删除')
    loadProjects()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => loadProjects())
</script>
