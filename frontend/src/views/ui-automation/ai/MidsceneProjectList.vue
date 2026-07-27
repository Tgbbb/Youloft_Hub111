<template>
  <div class="ms-subpage" data-ark-theme="endfield" data-ark-depth="complex">

    <section class="ms-zone">
      <header class="ms-zone__head">
        <span class="ms-zone__kicker">PROJECTS / REGISTRY</span>
        <span class="ms-zone__rule" aria-hidden="true"></span>
        <el-button type="primary" @click="showForm(null)" class="ms-btn--action"><el-icon><Plus /></el-icon> 新建项目</el-button>
      </header>

      <div class="ms-zone__body">
        <el-table :data="projects" v-loading="loading" class="ms-table" stripe>
          <el-table-column prop="name" label="项目名称" min-width="180">
            <template #default="{ row }">
              <span class="ms-table__name">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="包名" min-width="200">
            <template #default="{ row }">
              <div class="ms-table__codes">
                <span v-if="row.default_app_package" class="ms-code-tag">AND {{ row.default_app_package }}</span>
                <span v-if="row.default_ios_bundle_id" class="ms-code-tag">IOS {{ row.default_ios_bundle_id }}</span>
                <span v-if="!row.default_app_package && !row.default_ios_bundle_id" class="ms-text--muted">—</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
          <el-table-column prop="case_count" label="用例" width="70" align="right">
            <template #default="{ row }">
              <span class="ms-table__count">{{ row.case_count || 0 }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="owner_name" label="负责人" width="110" />
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showForm(row)" class="ms-btn--table">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteProject(row)" class="ms-btn--table">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <el-dialog v-model="formVisible" :title="editingId ? '编辑项目' : '新建项目'" width="500px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="项目名称" required><el-input v-model="form.name" placeholder="如：心动日常" /></el-form-item>
        <el-form-item label="Android包名"><el-input v-model="form.default_app_package" placeholder="com.youloft.icloser" /></el-form-item>
        <el-form-item label="iOS Bundle ID"><el-input v-model="form.default_ios_bundle_id" placeholder="com.youloft.icloser" /><div style="font-size:11px;color:#999;margin-top:4px">执行时根据设备平台自动选择对应包名</div></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" /></el-form-item>
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
const form = reactive({ name: '', default_app_package: '', default_ios_bundle_id: '', description: '' })

const loadProjects = async () => { loading.value = true; try { const { data } = await api.get('/ui-automation/midscene/projects/'); projects.value = data.results || [] } catch (e) { ElMessage.error('加载失败') } finally { loading.value = false } }
const showForm = (row) => {
  if (row) { editingId.value = row.id; form.name = row.name; form.default_app_package = row.default_app_package || ''; form.default_ios_bundle_id = row.default_ios_bundle_id || ''; form.description = row.description || '' }
  else { editingId.value = null; form.name = ''; form.default_app_package = ''; form.default_ios_bundle_id = ''; form.description = '' }
  formVisible.value = true
}
const saveProject = async () => { if (!form.name.trim()) { ElMessage.warning('请输入项目名称'); return }; saving.value = true; try { if (editingId.value) { await api.put(`/ui-automation/midscene/projects/${editingId.value}/`, form); ElMessage.success('已更新') } else { await api.post('/ui-automation/midscene/projects/', form); ElMessage.success('已创建') }; formVisible.value = false; loadProjects() } catch (e) { ElMessage.error('保存失败') } finally { saving.value = false } }
const deleteProject = async (row) => { try { await ElMessageBox.confirm(`删除项目「${row.name}」？`, '确认', { type: 'warning' }); await api.delete(`/ui-automation/midscene/projects/${row.id}/`); ElMessage.success('已删除'); loadProjects() } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') } }
onMounted(() => loadProjects())
</script>

<style scoped lang="scss">
.ms-subpage {
  height: calc(100vh - 52px);
  background: transparent;
  position: relative;
  padding: 20px;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", sans-serif;
}
.ms-zone {
  position: relative; z-index: 1;
  background: #fff;
  &__head {
    display: flex; align-items: center; gap: 14px; padding: 16px 24px 0;
  }
  &__kicker {
    font-size: 10px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .14em; color: #999; white-space: nowrap;
  }
  &__rule { flex: 1; height: 1px; background: #e8e8e4; }
  &__body { padding: 16px 24px 24px; }
}
.ms-btn--action { border-radius: 0 !important; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .06em; font-size: 12px; }
.ms-btn--table { border-radius: 0 !important; font-size: 12px; }
.ms-table {
  &__name { font-weight: 600; font-size: 14px; }
  &__count { font-family: "Space Grotesk", system-ui, sans-serif; font-weight: 700; font-size: 18px; color: #666; }
  &__codes { display: flex; flex-direction: column; gap: 2px; }
}
.ms-code-tag {
  font-size: 11px; font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  background: #f2f2f0; color: #666; padding: 2px 8px;
  border-left: 2px solid #fffa00;
}
.ms-text--muted { color: #ccc; font-size: 12px; }
</style>

<style lang="scss">
.ms-subpage {
  .el-button--primary {
    --el-button-bg-color: #191919;
    --el-button-border-color: #191919;
    --el-button-text-color: #f2f2f0;
    --el-button-hover-bg-color: #333;
    --el-button-hover-border-color: #333;
    --el-button-hover-text-color: #fff;
    border-radius: 0 !important;
    font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .06em; font-size: 12px;
  }
  .el-button--danger {
    border-radius: 0 !important; font-size: 12px;
  }
}
</style>
