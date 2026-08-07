<template>
  <div class="agent-config-container">
    <div class="page-header">
      <h1>{{ $t('configuration.agent.title') }}</h1>
      <p>{{ $t('configuration.agent.description') }}</p>
    </div>

    <!-- 状态条 -->
    <div class="status-bar">
      <div class="status-item">
        <span class="status-label">{{ $t('configuration.agent.currentConfig') }}</span>
        <span v-if="currentConfigId" class="status-value">
          {{ form.name || $t('configuration.common.unnamed') }}
          <el-tag size="small" type="success" effect="light">{{ $t('configuration.common.enabled') }}</el-tag>
        </span>
        <span v-else class="status-value muted">{{ $t('configuration.common.notConfigured') }}</span>
      </div>
      <div class="status-item" v-if="currentConfigId">
        <span class="status-label">{{ $t('configuration.agent.apiKey') }}</span>
        <span class="status-value">{{ apiKeyMasked }}</span>
      </div>
      <div class="status-item" v-if="currentConfigId">
        <span class="status-label">{{ $t('configuration.agent.protocol') }}</span>
        <span class="status-value">{{ protocolLabel }}</span>
      </div>
    </div>

    <div class="config-content">
      <!-- 连接信息 -->
      <el-card class="section-card">
        <template #header>
          <div class="card-header">
            <div class="card-title">
              <el-icon><Connection /></el-icon>
              <span>{{ $t('configuration.agent.sections.connection') }}</span>
            </div>
          </div>
        </template>

        <el-form :model="form" :rules="rules" ref="formRef" label-width="130px" label-position="left">
          <el-form-item :label="$t('configuration.agent.provider')" prop="provider">
            <el-select v-model="form.provider" @change="onProviderChange" style="width: 320px;">
              <el-option v-for="p in providers" :key="p.value" :label="p.label" :value="p.value" />
            </el-select>
            <div class="form-tip">{{ $t('configuration.agent.providerHint') }}</div>
          </el-form-item>

          <el-form-item :label="$t('configuration.agent.modelName')" prop="model_name">
            <el-input v-model="form.model_name" style="width: 320px;"
              :placeholder="$t('configuration.agent.modelNamePlaceholder')" />
            <div class="form-tip">{{ $t('configuration.agent.modelNameHint') }}</div>
          </el-form-item>

          <el-form-item :label="$t('configuration.agent.apiKey')" prop="api_key">
            <el-input v-model="form.api_key" type="password" show-password style="width: 420px;"
              :placeholder="currentConfigId ? $t('configuration.agent.apiKeyPlaceholderEdit') : $t('configuration.agent.apiKeyPlaceholder')" />
            <div v-if="currentConfigId" class="form-tip">
              {{ $t('configuration.agent.apiKeyMaskHint') }}：{{ apiKeyMasked }}
            </div>
            <div v-else class="form-tip">{{ $t('configuration.agent.apiKeyHint') }}</div>
          </el-form-item>

          <el-form-item :label="$t('configuration.agent.baseUrl')">
            <el-input v-model="form.base_url" style="width: 420px;"
              :placeholder="defaultBaseUrl || $t('configuration.agent.baseUrlPlaceholder')" />
            <div class="form-tip">{{ $t('configuration.agent.baseUrlHint') }}</div>
          </el-form-item>

          <el-form-item :label="$t('configuration.agent.protocol')">
            <el-radio-group v-model="form.api_protocol">
              <el-radio-button value="auto">{{ $t('configuration.agent.protocols.auto') }}</el-radio-button>
              <el-radio-button value="responses">{{ $t('configuration.agent.protocols.responses') }}</el-radio-button>
              <el-radio-button value="chat_completions">{{ $t('configuration.agent.protocols.chatCompletions') }}</el-radio-button>
            </el-radio-group>
            <div class="form-tip">{{ $t('configuration.agent.protocolHint') }}</div>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 模型参数 -->
      <el-card class="section-card">
        <template #header>
          <div class="card-header">
            <div class="card-title">
              <el-icon><Setting /></el-icon>
              <span>{{ $t('configuration.agent.sections.parameters') }}</span>
            </div>
          </div>
        </template>

        <el-form :model="form" label-width="130px" label-position="left">
          <div class="param-grid">
            <el-form-item :label="$t('configuration.agent.temperature')">
              <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input style="width: 240px;" />
            </el-form-item>
            <el-form-item :label="$t('configuration.agent.maxTokens')">
              <el-input-number v-model="form.max_tokens" :min="512" :max="131072" :step="1024" />
            </el-form-item>
            <el-form-item :label="$t('configuration.agent.maxToolCalls')">
              <el-input-number v-model="form.max_tool_calls" :min="5" :max="100" :step="5" />
            </el-form-item>
          </div>
          <el-form-item :label="$t('configuration.agent.toolGroups.label')">
            <el-checkbox-group v-model="form.tool_groups">
              <el-checkbox v-for="g in toolGroupOptions" :key="g.value" :value="g.value">
                {{ g.label }}
              </el-checkbox>
            </el-checkbox-group>
            <div class="tool-group-actions">
              <el-button link type="primary" size="small" @click="form.tool_groups = toolGroupOptions.map(o => o.value)">
                {{ $t('configuration.agent.toolGroups.selectAll') }}
              </el-button>
              <el-button link size="small" @click="form.tool_groups = []">
                {{ $t('configuration.agent.toolGroups.selectNone') }}
              </el-button>
            </div>
            <div class="form-tip">{{ $t('configuration.agent.toolGroups.hint') }}</div>
          </el-form-item>
          <div class="form-tip param-tip">{{ $t('configuration.agent.parametersHint') }}</div>
        </el-form>
      </el-card>

      <!-- 系统提示词 -->
      <el-card class="section-card">
        <template #header>
          <div class="card-header">
            <div class="card-title">
              <el-icon><Document /></el-icon>
              <span>{{ $t('configuration.agent.sections.prompt') }}</span>
            </div>
          </div>
        </template>

        <el-form :model="form" label-width="130px" label-position="left">
          <el-form-item :label="$t('configuration.agent.systemPrompt')">
            <el-input v-model="form.system_prompt_extra" type="textarea" :rows="4" style="width: 100%; max-width: 720px;"
              :placeholder="$t('configuration.agent.systemPromptPlaceholder')" />
            <div class="form-tip">{{ $t('configuration.agent.systemPromptHint') }}</div>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 启用与操作 -->
      <el-card class="section-card">
        <template #header>
          <div class="card-header">
            <div class="card-title">
              <el-icon><Switch /></el-icon>
              <span>{{ $t('configuration.agent.sections.enable') }}</span>
            </div>
          </div>
        </template>

        <el-form :model="form" label-width="130px" label-position="left">
          <el-form-item :label="$t('configuration.dify.enableStatus')">
            <el-switch v-model="form.is_active" />
            <span class="switch-label">{{ form.is_active ? $t('configuration.common.enabled') : $t('configuration.common.disabled') }}</span>
            <div class="form-tip">{{ $t('configuration.agent.enableHint') }}</div>
          </el-form-item>

          <el-form-item>
            <div class="action-row">
              <el-button type="primary" @click="saveConfig" :loading="saving">
                <el-icon><Check /></el-icon> {{ $t('configuration.common.save') }}
              </el-button>
              <el-button @click="testConnection" :loading="testing">
                <el-icon><Connection /></el-icon> {{ $t('configuration.agent.testConnection') }}
              </el-button>
              <el-button v-if="currentConfigId" type="danger" plain @click="deleteConfig" :loading="deleting">
                {{ $t('configuration.common.delete') }}
              </el-button>
            </div>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 测试结果 -->
      <el-card v-if="testResult" class="test-result-card" :class="testResult.success ? 'success' : 'error'">
        <div class="result-header">
          <el-icon :size="20"><CircleCheck v-if="testResult.success" /><CircleClose v-else /></el-icon>
          <div class="result-body">
            <div class="result-message">{{ testResult.message || testResult.error }}</div>
            <div v-if="testResult.success" class="result-meta">
              <el-tag size="small" type="success" effect="plain">
                {{ testResult.protocol_label || testResult.protocol }}
              </el-tag>
              <span class="result-model">{{ testResult.model }}</span>
            </div>
            <div v-else-if="testResult.detail" class="result-detail">{{ testResult.detail }}</div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Connection, CircleCheck, CircleClose, Setting, Document, Switch } from '@element-plus/icons-vue'
import { getAgentConfig, createAgentConfig, updateAgentConfig, testAgentConnection } from '@/api/assistant'
import api from '@/utils/api'

const { t } = useI18n()

const providers = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'qwen', label: '通义千问' },
  { value: 'siliconflow', label: '硅基流动' },
  { value: 'zhipu', label: '智谱' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'other', label: '其他' },
]

// 与后端 sdk_runtime.PROVIDER_DEFAULT_BASE 保持一致
const providerDefaults = {
  deepseek: { base_url: 'https://api.deepseek.com', model_name: 'deepseek-chat' },
  qwen: { base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model_name: 'qwen-plus' },
  siliconflow: { base_url: 'https://api.siliconflow.cn/v1', model_name: 'Qwen/Qwen3-235B-A22B' },
  zhipu: { base_url: 'https://open.bigmodel.cn/api/paas/v4', model_name: 'glm-4-flash' },
  openai: { base_url: 'https://api.openai.com/v1', model_name: 'gpt-4o' },
}

const toolGroupOptions = [
  { value: 'project', label: t('configuration.agent.toolGroups.project') },
  { value: 'api_testing', label: t('configuration.agent.toolGroups.apiTesting') },
  { value: 'testcases', label: t('configuration.agent.toolGroups.testcases') },
  { value: 'ui_automation', label: t('configuration.agent.toolGroups.uiAutomation') },
  { value: 'documents', label: t('configuration.agent.toolGroups.documents') },
  { value: 'browser', label: t('configuration.agent.toolGroups.browser') },
]

const formRef = ref(null)
const saving = ref(false)
const testing = ref(false)
const deleting = ref(false)
const currentConfigId = ref(null)
const apiKeyMasked = ref('')
const testResult = ref(null)

const form = reactive({
  name: 'Default',
  provider: 'deepseek',
  model_name: 'deepseek-chat',
  api_key: '',
  base_url: '',
  api_protocol: 'auto',
  max_tokens: 8192,
  max_tool_calls: 20,
  tool_groups: [],
  temperature: 0.7,
  is_active: true,
  system_prompt_extra: '',
})

const rules = {
  provider: [{ required: true, message: t('configuration.agent.messages.requiredField', { field: t('configuration.agent.provider') }) }],
  model_name: [{ required: true, message: t('configuration.agent.messages.requiredField', { field: t('configuration.agent.modelName') }) }],
  api_key: [],
}

const defaultBaseUrl = computed(() => providerDefaults[form.provider]?.base_url || '')
const protocolLabel = computed(() => {
  const map = {
    auto: t('configuration.agent.protocols.auto'),
    responses: t('configuration.agent.protocols.responses'),
    chat_completions: t('configuration.agent.protocols.chatCompletions'),
  }
  return map[form.api_protocol] || form.api_protocol
})

const onProviderChange = (val) => {
  const defaults = providerDefaults[val]
  if (defaults) {
    // 仅当 base_url 是之前提供商的默认值（或为空）时覆盖
    const allDefaultUrls = Object.values(providerDefaults).map(d => d.base_url)
    if (!form.base_url || allDefaultUrls.includes(form.base_url)) {
      form.base_url = defaults.base_url
    }
    const allDefaultModels = Object.values(providerDefaults).map(d => d.model_name)
    if (!form.model_name || allDefaultModels.includes(form.model_name)) {
      form.model_name = defaults.model_name
    }
  } else if (!form.base_url) {
    form.base_url = ''
  }
}

const loadConfig = async () => {
  try {
    const response = await getAgentConfig()
    const data = response.data
    if (data && data.id) {
      currentConfigId.value = data.id
      apiKeyMasked.value = data.api_key_masked || ''
      form.name = data.name || 'Default'
      form.provider = data.provider || 'deepseek'
      form.model_name = data.model_name || ''
      form.base_url = data.base_url || ''
      form.api_protocol = data.api_protocol || 'auto'
      if (!form.base_url && providerDefaults[form.provider]) {
        form.base_url = providerDefaults[form.provider].base_url
      }
      form.max_tokens = data.max_tokens || 8192
      form.max_tool_calls = data.max_tool_calls || 20
      form.tool_groups = data.tool_groups || []
      form.temperature = data.temperature ?? 0.7
      form.is_active = data.is_active ?? true
      form.system_prompt_extra = data.system_prompt_extra || ''
    }
  } catch (error) {
    if (error.response?.status !== 404) {
      console.error('Load config failed:', error)
    }
  }
}

const doSave = async () => {
  saving.value = true
  try {
    const data = { ...form }
    if (!data.api_key) delete data.api_key // 留空不覆盖已保存的 Key
    if (currentConfigId.value) {
      await updateAgentConfig(currentConfigId.value, data)
    } else {
      const response = await createAgentConfig(data)
      currentConfigId.value = response.data.id
    }
    ElMessage.success(t('configuration.agent.messages.saveSuccess'))
  } catch (error) {
    ElMessage.error(t('configuration.agent.messages.saveFailed') + ': ' +
      (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const saveConfig = async () => {
  if (!formRef.value?.validate) { await doSave(); return }
  const valid = await formRef.value.validate().catch(() => false)
  if (valid) await doSave()
}

const testConnection = async () => {
  if (!form.api_key && !currentConfigId.value) {
    ElMessage.warning(t('configuration.agent.messages.enterApiKey'))
    return
  }
  testing.value = true
  testResult.value = null
  try {
    const payload = {
      provider: form.provider,
      model_name: form.model_name,
      base_url: form.base_url,
      api_protocol: form.api_protocol,
    }
    if (currentConfigId.value && !form.api_key) {
      payload.config_id = currentConfigId.value
      payload.use_stored_key = true
    } else {
      payload.api_key = form.api_key
    }
    const response = await testAgentConnection(payload)
    testResult.value = response.data
  } catch (error) {
    testResult.value = {
      success: false,
      error: error.response?.data?.error || error.message,
      detail: error.response?.data?.detail,
    }
  } finally {
    testing.value = false
  }
}

const deleteConfig = async () => {
  try {
    await ElMessageBox.confirm(
      t('configuration.agent.messages.deleteConfirm'),
      t('configuration.agent.messages.deleteTitle'),
      { type: 'warning' }
    )
    if (currentConfigId.value) {
      await api.delete(`/assistant/config/agent/${currentConfigId.value}/`)
      currentConfigId.value = null
      apiKeyMasked.value = ''
      form.api_key = ''
      form.name = 'Default'
      ElMessage.success(t('configuration.agent.messages.deleteSuccess'))
    }
  } catch (error) {
    if (error !== 'cancel') { /* 用户取消 */ }
  }
}

onMounted(() => {
  loadConfig().then(() => {
    if (form.provider && !form.base_url) {
      onProviderChange(form.provider)
    }
  })
})
</script>

<style scoped lang="scss">
.agent-config-container {
  padding: 24px;
  max-width: 960px;
}
.page-header {
  margin-bottom: 20px;
  h1 { font-size: 24px; color: #303133; margin: 0 0 8px; }
  p { color: #909399; margin: 0; }
}

.status-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 32px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px 20px;
  margin-bottom: 16px;

  .status-item {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .status-label {
    font-size: 13px;
    color: #909399;
  }
  .status-value {
    font-size: 14px;
    color: #303133;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    &.muted { color: #c0c4cc; font-weight: 400; }
  }
}

.config-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .card-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    color: #303133;
    .el-icon { color: #409eff; }
  }
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.6;
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 0 24px;
  align-items: start;

  :deep(.el-form-item) {
    margin-bottom: 8px;
  }
}

.param-tip {
  margin-top: 4px;
}

.tool-group-actions {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}

.switch-label {
  margin-left: 8px;
  font-size: 14px;
  color: #606266;
}

.action-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.test-result-card {
  &.success { border-left: 3px solid #67c23a; }
  &.error { border-left: 3px solid #f56c6c; }

  .result-header {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    font-size: 15px;
  }
  .result-body { display: flex; flex-direction: column; gap: 6px; }
  .result-message { font-weight: 500; }
  .result-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
    color: #606266;
  }
  .result-detail {
    font-size: 12px;
    color: #909399;
    word-break: break-all;
  }
}
</style>
