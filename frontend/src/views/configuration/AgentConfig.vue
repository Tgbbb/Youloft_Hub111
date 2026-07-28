<template>
  <div class="agent-config-container">
    <div class="page-header">
      <h1>{{ $t('configuration.agent.title') }}</h1>
      <p>{{ $t('configuration.agent.description') }}</p>
    </div>

    <div class="config-content">
      <el-card class="config-card">
        <template #header>
          <div class="card-header">
            <span>{{ $t('configuration.agent.llmConfig') }}</span>
            <el-tag v-if="hasConfig" type="success">{{ $t('configuration.common.configured') }}</el-tag>
            <el-tag v-else type="info">{{ $t('configuration.common.notConfigured') }}</el-tag>
          </div>
        </template>

        <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
          <el-form-item :label="$t('configuration.agent.provider')" prop="provider">
            <el-select v-model="form.provider" @change="onProviderChange" style="width: 300px;">
              <el-option v-for="p in providers" :key="p.value" :label="p.label" :value="p.value" />
            </el-select>
          </el-form-item>

          <el-form-item :label="$t('configuration.agent.modelName')" prop="model_name">
            <div style="display:flex;gap:8px;align-items:center;">
              <el-input v-model="form.model_name" style="width: 300px;" placeholder="如: qwen-plus, deepseek-chat, gpt-4o" />
              <el-button @click="fetchModels" :loading="fetchingModels" size="small">
                {{ fetchingModels ? '获取中...' : '获取模型列表' }}
              </el-button>
            </div>
            <div v-if="availableModels.length > 0" class="model-list">
              <el-tag
                v-for="m in filteredAvailableModels"
                :key="m"
                size="small"
                :type="form.model_name === m ? '' : 'info'"
                :effect="form.model_name === m ? 'dark' : 'plain'"
                @click="form.model_name = m"
              >{{ m }}</el-tag>
            </div>
          </el-form-item>

          <el-form-item :label="$t('configuration.agent.apiKey')" prop="api_key">
            <el-input v-model="form.api_key" type="password" show-password style="width: 500px;"
              :placeholder="hasConfig ? '留空则不修改' : '请输入 API Key'" />
          </el-form-item>

          <el-form-item :label="$t('configuration.agent.baseUrl')">
            <el-input v-model="form.base_url" style="width: 500px;"
              :placeholder="defaultBaseUrl || 'https://api.deepseek.com'" />
            <div class="form-tip">OpenAI 兼容接口地址，留空使用默认地址</div>
          </el-form-item>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('configuration.agent.maxTokens')">
                <el-input-number v-model="form.max_tokens" :min="512" :max="131072" :step="1024" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('configuration.agent.maxToolCalls')">
                <el-input-number v-model="form.max_tool_calls" :min="5" :max="100" :step="5" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('configuration.agent.temperature')">
                <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input style="width: 200px;" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item :label="$t('configuration.agent.systemPrompt')">
            <el-input v-model="form.system_prompt_extra" type="textarea" :rows="3" style="width: 600px;"
              placeholder="追加到 Agent 系统提示词的额外内容（可选）" />
          </el-form-item>

          <el-form-item :label="$t('configuration.dify.enableStatus')">
            <el-switch v-model="form.is_active" />
            <span class="switch-label">{{ form.is_active ? $t('configuration.common.enabled') : $t('configuration.common.disabled') }}</span>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="saveConfig" :loading="saving">
              <el-icon><Check /></el-icon> {{ $t('configuration.common.save') }}
            </el-button>
            <el-button @click="testConnection" :loading="testing">
              <el-icon><Connection /></el-icon> {{ $t('configuration.agent.testConnection') }}
            </el-button>
            <el-button v-if="hasConfig" type="danger" plain @click="deleteConfig" :loading="deleting">
              删除配置
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 测试结果 -->
      <el-card v-if="testResult" class="test-result-card" :class="testResult.success ? 'success' : 'error'">
        <div class="result-header">
          <el-icon :size="20"><CircleCheck v-if="testResult.success" /><CircleClose v-else /></el-icon>
          <span>{{ testResult.message || testResult.error }}</span>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Connection, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { getAgentConfig, createAgentConfig, updateAgentConfig, testAgentConnection } from '@/api/assistant'
import api from '@/utils/api'

const { t } = useI18n()

const providers = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'qwen', label: '通义千问' },
  { value: 'siliconflow', label: '硅基流动' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'other', label: '其他' },
]

// 与 AIModelConfig 复用相同的 base URL 映射
const providerDefaults = {
  deepseek: { base_url: 'https://api.deepseek.com', model_name: 'deepseek-chat' },
  qwen: { base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model_name: 'qwen-plus' },
  siliconflow: { base_url: 'https://api.siliconflow.cn/v1', model_name: 'Qwen/Qwen3-235B' },
  openai: { base_url: 'https://api.openai.com/v1', model_name: 'gpt-4o' },
}

const formRef = ref(null)
const saving = ref(false)
const testing = ref(false)
const deleting = ref(false)
const fetchingModels = ref(false)
const currentConfigId = ref(null)
const testResult = ref(null)
const availableModels = ref([])

const form = reactive({
  name: 'Default',
  provider: 'deepseek',
  model_name: 'deepseek-chat',
  api_key: '',
  base_url: '',
  max_tokens: 8192,
  max_tool_calls: 20,
  temperature: 0.7,
  is_active: true,
  system_prompt_extra: '',
})

const rules = {
  provider: [{ required: true, message: '请选择模型提供商' }],
  model_name: [{ required: true, message: '请输入模型名称' }],
  api_key: [],
}

const hasConfig = computed(() => !!currentConfigId.value || form.api_key)
const filteredAvailableModels = computed(() => {
  if (!form.model_name) return availableModels.value
  const kw = form.model_name.toLowerCase()
  return availableModels.value.filter(m => m.toLowerCase().includes(kw))
})

// 切换提供商时自动更新 Base URL 和模型名
const onProviderChange = (val) => {
  availableModels.value = []
  const defaults = providerDefaults[val]
  if (defaults) {
    form.base_url = defaults.base_url
    // 如果模型名是之前提供商的默认值，则更新为新的默认值
    const allDefaultModels = Object.values(providerDefaults).map(d => d.model_name)
    if (!form.model_name || allDefaultModels.includes(form.model_name)) {
      form.model_name = defaults.model_name
    }
  } else {
    form.base_url = ''
  }
}

// 获取可用模型列表（复用 AIModelConfig 的 API）
const fetchModels = async () => {
  if (!form.api_key) {
    ElMessage.warning('请先输入 API Key')
    return
  }
  if (!form.base_url) {
    ElMessage.warning('请先选择模型提供商以自动填充 Base URL')
    return
  }
  fetchingModels.value = true
  try {
    const response = await api.post('/requirement-analysis/ai-models/available_models/', {
      name: form.name,
      model_type: form.provider,
      role: 'writer',
      api_key: form.api_key,
      base_url: form.base_url,
      model_name: form.model_name || 'temp-model',
      max_tokens: form.max_tokens,
      temperature: form.temperature,
      top_p: 0.9,
    }, { timeout: 90000 })
    availableModels.value = Array.isArray(response.data?.models) ? response.data.models : []
    if (availableModels.value.length === 0) {
      ElMessage.warning('未获取到可用模型列表')
    } else {
      ElMessage.success(`获取到 ${availableModels.value.length} 个模型`)
    }
  } catch (error) {
    ElMessage.error('获取模型列表失败: ' + (error.response?.data?.error || error.message))
  } finally {
    fetchingModels.value = false
  }
}

const loadConfig = async () => {
  try {
    const response = await getAgentConfig()
    const data = response.data
    if (data && data.id) {
      currentConfigId.value = data.id
      form.name = data.name || 'Default'
      form.provider = data.provider || 'deepseek'
      form.model_name = data.model_name || ''
      form.base_url = data.base_url || ''
      // 如果 API 返回的 base_url 为空，从默认值补
      if (!form.base_url && providerDefaults[form.provider]) {
        form.base_url = providerDefaults[form.provider].base_url
      }
      form.max_tokens = data.max_tokens || 8192
      form.max_tool_calls = data.max_tool_calls || 20
      form.temperature = data.temperature || 0.7
      form.is_active = data.is_active ?? true
      form.system_prompt_extra = data.system_prompt_extra || ''
      // API key 被 masked 后不显示，需要用户重新输入
    }
  } catch (error) {
    if (error.response?.status !== 404) {
      console.error('Load config failed:', error)
    }
  }
}

const saveConfig = async () => {
  if (!formRef.value?.validate) { await doSave(); return }
  formRef.value.validate(async (valid) => {
    if (valid) await doSave()
  })
}

const doSave = async () => {
  saving.value = true
  try {
    const data = { ...form }
    if (!data.api_key) delete data.api_key // 不覆盖已有 key

    if (currentConfigId.value) {
      await updateAgentConfig(currentConfigId.value, data)
    } else {
      const response = await createAgentConfig(data)
      currentConfigId.value = response.data.id
    }
    ElMessage.success('配置保存成功')
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const testConnection = async () => {
  if (!form.api_key) {
    ElMessage.warning('请先输入 API Key')
    return
  }
  testing.value = true
  testResult.value = null
  try {
    const response = await testAgentConnection({
      provider: form.provider,
      model_name: form.model_name,
      api_key: form.api_key,
      base_url: form.base_url,
    })
    testResult.value = response.data
  } catch (error) {
    testResult.value = {
      success: false,
      error: error.response?.data?.error || error.message,
    }
  } finally {
    testing.value = false
  }
}

const deleteConfig = async () => {
  try {
    await ElMessageBox.confirm('确定要删除 Agent 配置吗？删除后将使用 AI 用例生成的模型配置。', '确认删除', { type: 'warning' })
    if (currentConfigId.value) {
      await api.delete(`/assistant/config/agent/${currentConfigId.value}/`)
      currentConfigId.value = null
      form.api_key = ''
      ElMessage.success('配置已删除')
    }
  } catch (error) {
    if (error !== 'cancel') { /* 用户取消 */ }
  }
}

onMounted(() => {
  loadConfig().then(() => {
    // 确保 base_url 初始化（onProviderChange 仅 @change 触发）
    if (form.provider && !form.base_url) {
      onProviderChange(form.provider)
    }
  })
})
</script>

<style scoped lang="scss">
.agent-config-container {
  padding: 24px;
  max-width: 900px;
}
.page-header {
  margin-bottom: 24px;
  h1 { font-size: 24px; color: #303133; margin: 0 0 8px; }
  p { color: #909399; margin: 0; }
}
.config-card {
  .card-header { display: flex; align-items: center; justify-content: space-between; }
}
.form-tip { font-size: 12px; color: #909399; margin-top: 4px; }
.switch-label { margin-left: 8px; font-size: 14px; color: #606266; }

.model-list {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  .el-tag { cursor: pointer; }
}

.test-result-card {
  margin-top: 16px;
  &.success { border-left: 3px solid #67c23a; }
  &.error { border-left: 3px solid #f56c6c; }
  .result-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
  }
}
</style>
