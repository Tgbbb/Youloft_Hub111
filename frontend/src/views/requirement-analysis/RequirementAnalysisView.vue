<template>
  <div class="ef-root" data-ark-theme="endfield" data-ark-depth="maximal">
    <div class="ef-grid" aria-hidden="true"></div>
    <div class="ef-grid__diag" aria-hidden="true"></div>

    <!-- ======== Config Guide Modal ======== -->
    <div v-if="showConfigGuide && !checkingConfig" class="ef-modal" @click.self="showConfigGuide = false" :key="modalKey">
      <div class="ef-modal__box">
        <header class="ef-modal__bar">
          <span class="ef-modal__idx">00</span>
          <span>系统配置</span>
          <button class="ef-modal__x" @click="showConfigGuide = false">×</button>
        </header>
        <div class="ef-modal__body">
          <h2>{{ $t('configGuide.title') }}</h2>
          <p class="ef-modal__desc">{{ $t('configGuide.subtitle') }}</p>
          <div class="ef-guide-list">
            <div v-for="g in [
              {key:'writer_model',label:$t('configGuide.modelConfig'),sub:$t('configGuide.caseWriter'),v:configStatus.writer_model},
              {key:'reviewer_model',label:$t('configGuide.modelConfig'),sub:$t('configGuide.caseReviewer'),v:configStatus.reviewer_model},
              {key:'writer_prompt',label:$t('configGuide.promptConfig'),sub:$t('configGuide.caseWriter'),v:configStatus.writer_prompt},
              {key:'reviewer_prompt',label:$t('configGuide.promptConfig'),sub:$t('configGuide.caseReviewer'),v:configStatus.reviewer_prompt},
              {key:'generation_config',label:$t('configGuide.generationConfig'),sub:$t('configGuide.generationSettings'),v:configStatus.generation_config}
            ]" :key="g.key" class="ef-guide-item">
              <span class="ef-guide-item__label">{{ g.label }} / {{ g.sub }}</span>
              <span class="ef-guide-item__val" :class="g.v?.configured ? (g.v?.enabled ? 'is-ok' : 'is-warn') : 'is-fail'">
                <i class="ef-guide-item__dot"></i>{{ g.v?.name || $t('configGuide.unconfigured') }}
              </span>
            </div>
          </div>
          <div class="ef-actions">
            <button class="ef-btn ef-btn--signal" @click="goToConfig">{{ $t('configGuide.goToConfig') }}</button>
            <button class="ef-btn ef-btn--text" @click="showConfigGuide = false">{{ $t('configGuide.configureLater') }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ======== Stage ======== -->
    <div class="ef-stage">
      <!-- ---- Output Mode (pre-generation) ---- -->
      <div class="ef-section ef-section--alt" v-if="!isGenerating && !showResults">
        
        <div class="ef-section__body">
          <p class="ef-section__label">输出模式</p>
          <div class="ef-mode-row">
            <label class="ef-mode" :class="{ 'is-on': globalOutputMode === 'stream' }">
              <input type="radio" v-model="globalOutputMode" value="stream" hidden>
              <span class="ef-mode__letter">A</span>
              <span class="ef-mode__title">{{ $t('requirementAnalysis.realtimeStream') }}</span>
              <span class="ef-mode__desc">{{ $t('requirementAnalysis.realtimeStreamDesc') }}</span>
            </label>
            <label class="ef-mode" :class="{ 'is-on': globalOutputMode === 'complete' }">
              <input type="radio" v-model="globalOutputMode" value="complete" hidden>
              <span class="ef-mode__letter">B</span>
              <span class="ef-mode__title">{{ $t('requirementAnalysis.completeOutput') }}</span>
              <span class="ef-mode__desc">{{ $t('requirementAnalysis.completeOutputDesc') }}</span>
            </label>
          </div>
        </div>
      </div>

      <!-- ---- Input Zone ---- -->
      <div class="ef-section ef-section--alt" v-if="!isGenerating && !showResults && !showClarificationPanel">
        
        <div class="ef-section__body">
          <p class="ef-section__label">输入来源</p>
          <div class="ef-tabs">
            <button class="ef-tab" :class="{ 'is-on': manualTab === 'modao' }" @click="manualTab = 'modao'">墨刀</button>
            <button class="ef-tab" :class="{ 'is-on': manualTab === 'input' }" @click="manualTab = 'input'">手动</button>
          </div>

          <!-- Modao -->
          <div v-if="manualTab === 'modao'" class="ef-tab-body">
            <div v-if="modaoHistory.length > 0" class="ef-history">
              <span class="ef-history__label">历史</span>
              <span v-for="(h, i) in modaoHistory" :key="i" class="ef-history-pill">
  <button class="ef-pill" @click="loadModaoHistory(i)">{{ h.title || 'Import ' + (i+1) }}</button>
  <button class="ef-pill__del" @click.stop="deleteModaoHistory(i)" title="删除">×</button>
</span>
            </div>
            <div class="ef-fields">
              <div class="ef-field"><label>项目</label><select v-model="manualInput.selectedProject" class="ef-select" @change="onManualProjectChange"><option value="">{{ $t('requirementAnalysis.selectProject') }}</option><option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
              <div class="ef-field" v-show="manualInput.selectedProject"><label>版本</label><select v-model="manualInput.selectedVersionIds" class="ef-select" multiple size="3" @change="loadVersionModules(manualInput.selectedVersionIds, 'manual')"><option v-for="v in projectVersions" :key="v.id" :value="v.id">{{ v.name }}{{ v.is_baseline ? ' ★' : '' }}</option></select></div>
              <div class="ef-field" v-show="manualInput.selectedVersionIds && manualInput.selectedVersionIds.length > 0"><label>模块</label><select v-model="manualInput.selectedModuleId" class="ef-select"><option value="">{{ $t('requirementAnalysis.selectModule') }}</option><option v-for="m in manualModules" :key="m.id" :value="m.id">{{ m.name }}</option></select></div>
            </div>
            <div class="ef-fields">
              <div class="ef-field ef-field--wide"><label>墨刀链接</label><input v-model="modaoUrl" class="ef-input" placeholder="https://modao.cc/proto/..." /></div>
              <div class="ef-field"><label>Cookie 密钥</label><input v-model="modaoToken" class="ef-input" type="password" placeholder="_imock_session=..." /></div>
            </div>
            <div class="ef-actions">
              <button class="ef-btn ef-btn--signal" @click="importFromModao" :disabled="isImportingModao || !modaoUrl || !modaoToken">{{ isImportingModao ? `导入中 ${_importProgress}%` : '从墨刀导入' }}</button>
              <button v-if="modaoCanvases.length > 0" class="ef-btn ef-btn--dark" @click="generateFromModao" :disabled="isGenerating || selectedCanvasCount === 0">生成 ({{ selectedCanvasCount }})</button>
            </div>
            <!-- Canvases -->
            <div v-if="modaoCanvases.length > 0" class="ef-canvas-bar">
              <button class="ef-btn ef-btn--text" @click="selectAllCanvases">
                {{ selectedCanvasCount === modaoCanvases.length ? '取消全选' : '全选' }} ({{ selectedCanvasCount }}/{{ modaoCanvases.length }})
              </button>
            </div>
            <div v-if="modaoCanvases.length > 0" class="ef-canvases">
              <div v-for="(c, i) in modaoCanvases" :key="i" class="ef-canvas" :class="{ 'is-on': c.selected }" @click="c.selected = !c.selected">
                <span class="ef-canvas__check" v-if="c.selected">✓</span>
                <span class="ef-canvas__n">{{ String(i + 1).padStart(2, '0') }}</span>
                <div class="ef-canvas__thumbs" v-if="c.screenshots && c.screenshots.length">
                  <img v-for="(s, si) in c.screenshots" :key="si" :src="s.url" style="width:40px;height:40px;object-fit:cover;flex-shrink:0;border:1px solid #e8e6e0" @click.stop="previewCanvas = c; previewIdx = si" />
                </div>
                <div v-else class="ef-canvas__noimg" @click.stop="previewCanvas = c; previewIdx = 0">无截图</div>
                <span class="ef-canvas__name">{{ c.name }}</span>
              </div>
            </div>
            <!-- Lightbox -->
            <div v-if="previewCanvas" class="ef-lightbox" @click.self="closePreview">
              <div class="ef-lightbox__nav" v-if="previewCanvas.screenshots?.length > 1"><button v-for="(s, si) in previewCanvas.screenshots" :key="si" class="ef-lightbox__dot" :class="{ 'is-on': si === previewIdx }" @click.stop="previewIdx = si">{{ si + 1 }}</button></div>
              <div class="ef-lightbox__stage">
                <img v-if="previewCanvas.screenshots?.[previewIdx]?.url" :src="previewCanvas.screenshots[previewIdx].url" style="display:block;max-width:90vw;max-height:86vh;width:auto;height:auto;object-fit:contain" :style="{ transform: `scale(${previewZoom})` }" @wheel.stop.prevent="onPreviewWheel" />
              </div>
              <button class="ef-lightbox__close" @click="closePreview">×</button>
            </div>
          </div>

          <!-- Manual -->
          <div v-if="manualTab === 'input'" class="ef-tab-body">
            <div class="ef-fields">
              <div class="ef-field ef-field--wide"><label>Title</label><input v-model="manualInput.title" class="ef-input" :placeholder="$t('requirementAnalysis.titlePlaceholder')" /></div>
            </div>
            <div class="ef-fields">
              <div class="ef-field ef-field--wide"><label>Description</label><textarea v-model="manualInput.description" class="ef-input ef-input--area" rows="6" :placeholder="$t('requirementAnalysis.descriptionPlaceholder')"></textarea></div>
            </div>
            <div class="ef-fields">
              <div class="ef-field"><label>项目</label><select v-model="manualInput.selectedProject" class="ef-select" @change="onManualProjectChange"><option value="">{{ $t('requirementAnalysis.selectProject') }}</option><option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
              <div class="ef-field" v-show="manualInput.selectedProject"><label>版本</label><select v-model="manualInput.selectedVersionIds" class="ef-select" multiple size="3" @change="loadVersionModules(manualInput.selectedVersionIds, 'manual')"><option v-for="v in projectVersions" :key="v.id" :value="v.id">{{ v.name }}{{ v.is_baseline ? ' ★' : '' }}</option></select></div>
              <div class="ef-field" v-show="manualInput.selectedVersionIds && manualInput.selectedVersionIds.length > 0"><label>模块</label><select v-model="manualInput.selectedModuleId" class="ef-select"><option value="">{{ $t('requirementAnalysis.selectModule') }}</option><option v-for="m in manualModules" :key="m.id" :value="m.id">{{ m.name }}</option></select></div>
            </div>
            <div class="ef-actions">
              <button class="ef-btn ef-btn--signal" @click="generateFromManualInput" :disabled="!canGenerateManual || isGenerating">{{ isGenerating ? $t('requirementAnalysis.generating') : $t('requirementAnalysis.generateButton') }}</button>
            </div>
          </div>

          <!-- Extract (hidden tab, functional) -->
          <div v-if="manualTab === 'extract'" class="ef-tab-body">
            <div class="ef-fields">
              <div class="ef-field"><label>Project</label><select v-model="manualInput.selectedProject" class="ef-select"><option value="">{{ $t('requirementAnalysis.selectProject') }}</option><option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            </div>
            <div class="ef-dropzone" @drop.prevent="handleExtractDrop" @dragover.prevent="isExtractDragOver = true" @dragleave.prevent="isExtractDragOver = false" :class="{ 'is-over': isExtractDragOver }">
              <div v-if="!extractFile"><span class="ef-dropzone__icon">PDF</span><p>拖拽文件到此处</p><input type="file" ref="extractFileInput" @change="handleExtractFileSelect" accept=".pdf,.doc,.docx,.txt,.md" hidden><button class="ef-btn" @click="$refs.extractFileInput.click()">选择文件</button></div>
              <div v-else class="ef-dropzone__file"><span>{{ extractFile.name }}</span><span class="ef-dropzone__size">{{ formatFileSize(extractFile.size) }}</span><button class="ef-btn ef-btn--text" @click="removeExtractFile">移除</button></div>
            </div>
            <div class="ef-actions"><button class="ef-btn ef-btn--signal" @click="extractDocument" :disabled="!extractFile || isExtracting">{{ isExtracting ? '提取中...' : '提取' }}</button></div>
            <textarea v-if="extractedMarkdown" v-model="extractedMarkdown" class="ef-input ef-input--area" rows="10" style="margin-top:16px"></textarea>
            <div class="ef-actions" v-if="extractedMarkdown"><button class="ef-btn ef-btn--signal" @click="generateFromExtracted" :disabled="!extractedMarkdown || isGenerating">生成</button></div>
          </div>
        </div>
      </div>


      <!-- ---- Document Upload ---- -->
      <div class="ef-section ef-section--alt" v-if="!isGenerating && !showResults && !showClarificationPanel">
        <div class="ef-section__body">
          <p class="ef-section__label">文档上传</p>
          <div class="ef-dropzone"
            @drop.prevent="handleDrop" @dragover.prevent="isDragOver = true"
            @dragleave.prevent="isDragOver = false" :class="{ 'is-over': isDragOver }">
            <div v-if="!selectedFile">
              <span class="ef-dropzone__icon">文档</span>
              <p>拖拽 PDF、Word、TXT 或图片到此处</p>
              <div class="ef-dropzone__btns">
                <input type="file" ref="fileInput" @change="handleFileSelect" multiple accept=".pdf,.doc,.docx,.txt,.md,.png,.jpg,.jpeg" hidden>
                <input type="file" ref="folderInput" @change="handleFileSelect" webkitdirectory hidden>
                <button class="ef-btn" @click="$refs.fileInput.click()">文件</button>
                <button class="ef-btn" @click="$refs.folderInput.click()">文件夹</button>
              </div>
            </div>
            <div v-else class="ef-dropzone__file">
              <span>{{ selectedFile.name }}</span>
              <span class="ef-dropzone__size">{{ formatFileSize(selectedFile.size) }}</span>
              <span class="ef-dropzone__more" v-if="selectedFiles.length > 1">+{{ selectedFiles.length - 1 }}</span>
              <button class="ef-btn ef-btn--text" @click="removeFile">移除</button>
            </div>
          </div>
          <div v-if="selectedFile" class="ef-fields" style="margin-top:20px">
            <div class="ef-field"><label>标题</label><input v-model="documentTitle" class="ef-input" /></div>
            <div class="ef-field"><label>项目</label><select v-model="selectedProject" class="ef-select" @change="onDocProjectChange"><option value="">{{ $t('requirementAnalysis.selectProject') }}</option><option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="ef-field" v-show="selectedProject"><label>版本</label><select v-model="selectedVersionIds" class="ef-select" multiple size="3" @change="loadVersionModules(selectedVersionIds, 'doc')"><option v-for="v in projectVersions" :key="v.id" :value="v.id">{{ v.name }}{{ v.is_baseline ? ' ★' : '' }}</option></select></div>
            <div class="ef-field" v-show="selectedVersionIds && selectedVersionIds.length > 0"><label>模块</label><select v-model="docSelectedModuleId" class="ef-select"><option value="">{{ $t('requirementAnalysis.selectModule') }}</option><option v-for="m in docModules" :key="m.id" :value="m.id">{{ m.name }}</option></select></div>
          </div>
          <div class="ef-actions" v-if="selectedFile">
            <label class="ef-check" v-if="isMultimodalFile"><input type="checkbox" v-model="enableMultimodal"><span>{{ $t('requirementAnalysis.enableMultimodal') }}</span></label>
            <button class="ef-btn ef-btn--signal" @click="generateFromDocument" :disabled="isGenerating">{{ isGenerating ? $t('requirementAnalysis.generating') : $t('requirementAnalysis.generateButton') }}</button>
          </div>
        </div>
      </div>

      <!-- ---- Clarification ---- -->
      <div class="ef-section ef-section--clarify" v-if="showClarificationPanel">
        <div class="ef-section__body">
          <p class="ef-section__label">需求澄清</p>
          <div v-if="isClarifying" class="ef-wait"><span class="ef-wait__dot"></span>分析中...</div>
          <div v-else-if="clarificationQuestions.length === 0" class="ef-wait">✓ 未发现歧义</div>
          <div v-else class="ef-questions">
            <div v-for="q in clarificationQuestions" :key="q.id" class="ef-q">
              <div class="ef-q__head">
                <span class="ef-q__n">Q{{ String(q.id).padStart(2,'0') }}</span>
                <span class="ef-q__text">{{ q.question }}</span>
              </div>
              <textarea v-model="clarificationAnswers[q.id]" class="ef-input ef-input--area" rows="3" placeholder="请输入您的回答..."></textarea>
            </div>
          </div>
          <div class="ef-actions" v-if="!isClarifying">
            <button class="ef-btn ef-btn--signal" @click="confirmWithClarification">确认并生成</button>
            <button class="ef-btn" @click="skipClarification">跳过，直接生成</button>
          </div>
        </div>
      </div>

      <!-- ---- Generation / Results ---- -->
      <div class="ef-section ef-section--results" v-if="isGenerating || showResults">
        <div class="ef-section__body">
          <p class="ef-section__label">{{ isGenerating ? '生成中' : '生成结果' }}
            <span class="ef-section__badge is-live" v-if="isGenerating">{{ currentStep }}/4</span>
          </p>
          <!-- Steps -->
          <div class="ef-pipeline" v-if="isGenerating">
            <span class="ef-pipe" :class="{ 'is-on': currentStep >= 1, 'is-past': currentStep > 1 }">分析</span>
            <span class="ef-pipe__line"></span>
            <span class="ef-pipe" :class="{ 'is-on': currentStep >= 2, 'is-past': currentStep > 2 }">编写</span>
            <span class="ef-pipe__line"></span>
            <span class="ef-pipe" :class="{ 'is-on': currentStep >= 3, 'is-past': currentStep > 3 }">评审</span>
            <span class="ef-pipe__line"></span>
            <span class="ef-pipe" :class="{ 'is-on': currentStep >= 4, 'is-past': currentStep > 4 }">完成</span>
          </div>
          <!-- Content -->
          <div v-if="streamedContent" class="ef-prose">
            <p class="ef-prose__label">测试用例</p>
            <div class="ef-prose__body" v-html="formatMarkdown(streamedContent)"></div>
          </div>
          <div v-if="streamedReviewContent" class="ef-prose ef-prose--review">
            <p class="ef-prose__label">评审</p>
            <div class="ef-prose__body" v-html="formatMarkdown(streamedReviewContent)"></div>
          </div>
          <div v-if="finalTestCases" class="ef-prose ef-prose--final">
            <p class="ef-prose__label">最终</p>
            <div class="ef-prose__body" v-html="formatMarkdown(finalTestCases)"></div>
          </div>
          <div class="ef-actions" v-if="showResults">
            <button class="ef-btn ef-btn--signal" @click="downloadTestCases('xlsx')">下载 XLSX</button>
            <button class="ef-btn ef-btn--dark" @click="saveToTestCaseRecords" :disabled="!generationResult?.task_id">保存到记录</button>
            <button class="ef-btn" @click="resetGeneration">新建</button>
          </div>
          <div class="ef-actions" v-else>
            <button class="ef-btn ef-btn--text" @click="cancelGeneration">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ======== Bottom Dock ======== -->
    <footer class="ef-dock">
      <span>系统 / 在线</span><span class="ef-dock__div"></span>
      <span v-if="currentTaskId">任务 {{ currentTaskId?.substring(0,8) }}</span>
      <span v-else>无活跃任务</span>
      <span class="ef-dock__dot" :class="{ 'is-live': !!currentTaskId }"></span>
    </footer>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as XLSX from 'xlsx'
import { useUserStore } from '@/stores/user'

export default {
  name: 'RequirementAnalysisView',
  data() {
    return {
      // 全局输出模式设置
      globalOutputMode: 'stream',  // 默认使用流式输出

      // 手动输入需求
      manualInput: {
        title: '',
        description: '',
        selectedProject: '',
        selectedVersionIds: [],
        selectedModuleId: ''
      },

      // 文件上传
      selectedFile: null,
      selectedFiles: [],  // 多文件列表
      showFileList: false,
      documentTitle: '',
      selectedProject: '',
      selectedVersionIds: [],
      docSelectedModuleId: '',
      manualModules: [],
      docModules: [],
      projectVersions: [],
      projects: [],
      isDragOver: false,

      // 生成状态
      isGenerating: false,
      currentTaskId: null,
      progressText: '',
      currentStep: 0,
      pollInterval: null,
      eventSource: null,  // SSE连接
      streamedContent: '',  // 流式接收的内容
      streamedReviewContent: '',  // 流式接收的评审内容
      finalTestCases: '',  // 最终版用例
      hasShownCompletionMessage: false,  // 是否已经显示过完成消息
      showReviewStep: true,  // 是否显示评审步骤（根据生成配置决定）

      // 生成结果
      showResults: false,
      generationResult: null,

      // AI配置状态
      configStatus: {
        overall_status: 'unknown',
        message: '',
        writer_model: {
          configured: false,
          enabled: false,
          name: null,
          provider: null,
          id: null,
          required: true
        },
        writer_prompt: {
          configured: false,
          enabled: false,
          name: null,
          id: null,
          required: true
        },
        reviewer_model: {
          configured: false,
          enabled: false,
          name: null,
          id: null,
          required: true
        },
        reviewer_prompt: {
          configured: false,
          enabled: false,
          name: null,
          id: null,
          required: true
        },
        generation_config: {
          configured: false,
          enabled: false,
          name: null,
          id: null,
          required: true,
          default_output_mode: null
        }
      },
      showConfigGuide: false,
      checkingConfig: true,
      modalKey: 0,  // 用于强制重新渲染弹窗

      // 多模态模式
      enableMultimodal: false,

      // 手动输入区 Tab
      manualTab: 'modao',

      // AI文档提取
      extractFile: null,
      isExtractDragOver: false,
      isExtracting: false,
      extractedMarkdown: '',

      // 墨刀导入
      modaoUrl: '',
      modaoToken: '',
      modaoTitle: '',
      _modaoHistoryId: null,   // 当前历史记录ID（更新用）
      _modaoImportId: '',      // 导入批次ID（截图文件夹）
      modaoCanvases: [],       // [{name, screenshots: [{url, width, height}], selected}]
      modaoHistory: [],
      previewCanvas: null,     // 当前预览的画布（lightbox）
      previewIdx: 0,           // 当前预览的截图索引
      previewZoom: 1,          // 预览缩放比例
      replaceInputs: {},       // 添加截图的 file input refs
      isImportingModao: false,
      _importProgress: 0,          // 导入进度（0-100）

      // 需求澄清
      showClarificationPanel: false,  // 是否显示澄清面板
      isClarifying: false,  // 是否正在执行澄清分析
      clarificationQuestions: [],  // AI返回的澄清问题 [{id, question}]
      clarificationAnswers: {},  // 用户对每个问题的回答 {questionId: answerText}
      clarificationRaw: '',  // AI原始返回文本（用于调试）
      clarificationTaskId: null,  // 澄清阶段创建的task_id
      pendingGeneration: null  // 待执行的生成上下文
    }
  },

  computed: {
    versionModules() { return this.manualModules },
    selectedCanvasCount() {
      return this.modaoCanvases.filter(c => c.selected).length
    },
    canGenerateManual() {
      return this.manualInput.title.trim() &&
             this.manualInput.description.trim() &&
             this.manualInput.description.length <= 2000
    },

    isMultimodalFile() {
      if (this.selectedFiles.length === 0) return false
      return this.selectedFiles.some(f => /\.(pdf|png|jpg|jpeg|webp)$/i.test(f.name))
    }
  },

  mounted() {
    // 加载已保存的墨刀 Cookie
    const savedCookie = localStorage.getItem('modao_cookie')
    if (savedCookie) this.modaoToken = savedCookie
    this.loadModaoHistoryList()
    this.progressText = this.$t('requirementAnalysis.preparing')
    this.loadProjects()
    this.checkConfigStatus()

    // 从任务记录恢复澄清流程
    const taskId = this.$route.query.taskId
    if (taskId) {
      this.restoreTask(taskId)
    }
  },

  activated() {
    // 当从其他页面返回时，重新检查配置状态
    // 立即隐藏弹窗和遮罩层，强制重新渲染
    this.showConfigGuide = false
    this.checkingConfig = true
    this.modalKey += 1  // 改变key值，强制重新渲染弹窗

    // 延迟检查配置，确保页面完全加载后再显示弹窗
    setTimeout(async () => {
      await this.checkConfigStatus()
    }, 200)
  },

  beforeUnmount() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval)
    }
    // 停止token自动刷新定时器
    const userStore = useUserStore()
    userStore.stopAutoRefresh()
  },

  methods: {
    async loadProjects() {
      try {
        const response = await api.get('/projects/')
        this.projects = response.data.results || response.data
      } catch (error) {
        console.error(this.$t('requirementAnalysis.loadProjectsFailed'), error)
      }
    },

    async loadProjectVersions(projectId) {
      if (!projectId) {
        this.projectVersions = []
        return
      }
      try {
        const response = await api.get(`/versions/projects/${projectId}/versions/`)
        this.projectVersions = response.data || []
      } catch (error) {
        console.error('加载版本列表失败:', error)
        this.projectVersions = []
      }
    },

    async loadVersionModules(versionIds, target) {
      if (!versionIds || versionIds.length === 0) {
        if (target === 'manual') this.manualModules = []
        else this.docModules = []
        return
      }
      try {
        const vid = Array.isArray(versionIds) ? versionIds[0] : versionIds
        const response = await api.get(`/versions/${vid}/modules/`)
        const modules = response.data.results || response.data || []
        if (target === 'manual') this.manualModules = modules
        else this.docModules = modules
      } catch (error) {
        console.error('加载功能模块失败:', error)
        if (target === 'manual') this.manualModules = []
        else this.docModules = []
      }
    },

    async quickAddModule(target) {
      // target: 'manual' | 'doc'
      const versionIds = target === 'manual' ? this.manualInput.selectedVersionIds : this.selectedVersionIds
      if (!versionIds || versionIds.length === 0) return
      const vid = Array.isArray(versionIds) ? versionIds[0] : versionIds
      try {
        const { value } = await ElMessageBox.prompt(
          target === 'manual' ? '请输入新功能模块名称' : '请输入新功能模块名称',
          '新增功能模块',
          { confirmButtonText: '创建', cancelButtonText: '取消' }
        )
        if (value && value.trim()) {
          await api.post(`/versions/${vid}/modules/`, { name: value.trim() })
          ElMessage.success('模块创建成功')
          // 重新加载模块列表
          await this.loadVersionModules(versionIds, target)
          // 自动选中新创建的模块（最后一个）
          this.$nextTick(() => {
            const modules = target === 'manual' ? this.manualModules : this.docModules
            if (modules.length > 0) {
              const newMod = modules[modules.length - 1]
              if (target === 'manual') this.manualInput.selectedModuleId = newMod.id
              else this.docSelectedModuleId = newMod.id
            }
          })
        }
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error(error.response?.data?.error || '创建失败')
        }
      }
    },

    onManualProjectChange() {
      this.manualInput.selectedVersionIds = []
      this.manualInput.selectedModuleId = ''
      this.manualModules = []
      this.loadProjectVersions(this.manualInput.selectedProject)
    },

    onDocProjectChange() {
      this.selectedVersionIds = []
      this.docSelectedModuleId = ''
      this.docModules = []
      this.loadProjectVersions(this.selectedProject)
    },

    async checkConfigStatus() {
      try {
        this.checkingConfig = true
        const response = await api.get('/requirement-analysis/config/check/')
        this.configStatus = response.data

        // 判断逻辑：只有当"用例编写模型"、"用例评审模型"、"用例编写提示词"和"用例评审提示词"都配置且启用时，才不显示弹框
        const writerModelReady = response.data.writer_model &&
                                response.data.writer_model.configured &&
                                response.data.writer_model.enabled

        const reviewerModelReady = response.data.reviewer_model &&
                                  response.data.reviewer_model.configured &&
                                  response.data.reviewer_model.enabled

        const writerPromptReady = response.data.writer_prompt &&
                                 response.data.writer_prompt.configured &&
                                 response.data.writer_prompt.enabled

        const reviewerPromptReady = response.data.reviewer_prompt &&
                                   response.data.reviewer_prompt.configured &&
                                   response.data.reviewer_prompt.enabled

        // 检查生成行为配置
        const generationConfigReady = response.data.generation_config &&
                                      response.data.generation_config.configured

        // 只有五项都准备好时才不显示引导弹框
        if (writerModelReady && reviewerModelReady && writerPromptReady && reviewerPromptReady && generationConfigReady) {
          this.showConfigGuide = false

          // 如果生成配置允许用户修改，则使用配置的默认输出模式
          if (response.data.generation_config && response.data.generation_config.default_output_mode) {
            this.globalOutputMode = response.data.generation_config.default_output_mode
          }

          // 根据生成配置的enable_auto_review决定是否显示评审步骤
          if (response.data.generation_config && response.data.generation_config.enable_auto_review !== null) {
            this.showReviewStep = response.data.generation_config.enable_auto_review
          } else {
            this.showReviewStep = true  // 默认显示
          }
        } else {
          this.showConfigGuide = true
        }
      } catch (error) {
        console.error('Failed to check config status:', error)
        // 如果检查失败，默认不显示引导，避免影响正常使用
        this.showConfigGuide = false
        this.checkingConfig = false
      } finally {
        this.checkingConfig = false
      }
    },

    goToConfig() {
      // 智能判断跳转目标：优先跳转到未配置/未启用的页面
      // 优先级：必需配置 > 可选配置，提示词 > 模型

      // 0. 首先检查生成行为配置（generation_config）
      if (!this.configStatus.generation_config || !this.configStatus.generation_config.configured) {
        this.$router.push('/configuration/generation-config')
        return
      }

      // 1. 优先检查必需的提示词配置（writer_prompt）
      if (!this.configStatus.writer_prompt.configured || !this.configStatus.writer_prompt.enabled) {
        this.$router.push('/configuration/prompt-config')
        return
      }

      // 2. 检查必需的模型配置（writer_model）
      if (!this.configStatus.writer_model.configured || !this.configStatus.writer_model.enabled) {
        this.$router.push('/configuration/ai-model')
        return
      }

      // 3. 检查可选的评审提示词（reviewer_prompt）
      if (!this.configStatus.reviewer_prompt.configured || !this.configStatus.reviewer_prompt.enabled) {
        this.$router.push('/configuration/prompt-config')
        return
      }

      // 4. 检查可选的评审模型（reviewer_model）
      if (!this.configStatus.reviewer_model.configured || !this.configStatus.reviewer_model.enabled) {
        this.$router.push('/configuration/ai-model')
        return
      }

      // 默认跳转到生成行为配置
      this.$router.push('/configuration/generation-config')
    },

    goToPromptConfig() {
      this.$router.push('/configuration/prompt-config')
    },

    getConfigItemClass(configKey) {
      const config = this.configStatus[configKey]
      if (config.enabled) {
        return 'status-enabled'
      } else if (config.configured) {
        return 'status-disabled'
      } else {
        return 'status-unconfigured'
      }
    },

    getStatusIcon(configKey) {
      const config = this.configStatus[configKey]
      if (config.enabled) {
        // 绿色对号
        return '<path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm193.5 301.7l-210.6 292c-12.7 17.7-39 17.7-51.7 0L318.5 484.9c-3.8-5.3 0-12.7 6.5-12.7h46.9c10.2 0 19.9 4.9 25.9 13.3l71.2 98.8 157.2-218c6-8.3 15.6-13.3 25.9-13.3H699c6.5 0 10.3 7.4 6.5 12.7z" fill="#27ae60"/>'
      } else if (config.configured) {
        // 禁用图标（灰色圆圈和斜线）
        return '<path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372zm128-412c0 4.4-3.6 8-8 8H392c-4.4 0-8-3.6-8-8v-48c0-4.4 3.6-8 8-8h240c4.4 0 8 3.6 8 8v48z" fill="#95a5a6"/>'
      } else {
        // 红色叉号
        return '<path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm165.4 618.2l-66-70.7c-10.6-10.1-28.1-10.1-38.8 0l-66.7 71.5-66.7-71.5c-10.6-10.1-28.1-10.1-38.8 0l-66 70.7c-9.9 10.6-9.9 27.4 0 38l66 70.7c10.6 10.1 28.1 10.1 38.8 0l66.7-71.5 66.7 71.5c10.6 10.1 28.1 10.1 38.8 0l66-70.7c9.9-10.6 9.9-27.4 0-38z" fill="#e74c3c"/>'
      }
    },

    getStatusSymbol(configKey) {
      const config = this.configStatus[configKey]
      if (config.enabled) {
        // 绿色对勾
        return '<span style="color: #27ae60; font-size: 18px;">✓</span>'
      } else if (config.configured) {
        // 禁用图标
        return '<span style="color: #95a5a6; font-size: 18px;">○</span>'
      } else {
        // 红色叉号
        return '<span style="color: #e74c3c; font-size: 18px;">✗</span>'
      }
    },

    handleDrop(event) {
      event.preventDefault()
      this.isDragOver = false
      const files = event.dataTransfer.files
      if (files.length > 0) {
        this.handleFileSelect({ target: { files } })
      }
    },

    handleFileSelect(event) {
      const fileList = event.target.files
      if (!fileList || fileList.length === 0) return
      const allowedExt = /\.(pdf|doc|docx|txt|md|png|jpg|jpeg|webp)$/i
      for (let i = 0; i < fileList.length; i++) {
        const f = fileList[i]
        if (allowedExt.test(f.name)) {
          this.selectedFiles.push(f)
        }
      }
      if (this.selectedFiles.length > 0) {
        this.selectedFile = this.selectedFiles[0]
        if (!this.documentTitle) this.documentTitle = this.selectedFile.name.replace(/\.[^/.]+$/, '')
        this.showFileList = this.selectedFiles.length > 3
      } else {
        ElMessage.error(this.$t('requirementAnalysis.invalidFileFormatDetail'))
      }
    },

    handleFolderSelect(event) {
      const fileList = event.target.files
      if (!fileList || fileList.length === 0) return
      const allowedExt = /\.(pdf|doc|docx|txt|md|png|jpg|jpeg|webp)$/i
      const added = []
      for (let i = 0; i < fileList.length; i++) {
        const f = fileList[i]
        if (allowedExt.test(f.name)) {
          this.selectedFiles.push(f)
          added.push(f)
        }
      }
      if (added.length > 0) {
        this.selectedFile = this.selectedFiles[0]
        // 用文件夹名作为默认标题
        if (!this.documentTitle) {
          const relativePath = fileList[0].webkitRelativePath || ''
          const folderName = relativePath.split('/')[0] || ''
          this.documentTitle = folderName || this.selectedFile.name.replace(/\.[^/.]+$/, '')
        }
        this.showFileList = true
        ElMessage.success(`已导入 ${added.length} 个文件`)
      } else {
        ElMessage.error('文件夹中未找到支持的文档格式')
      }
      event.target.value = ''
    },

    removeFile() {
      this.selectedFile = null
      this.selectedFiles = []
      this.documentTitle = ''
      this.enableMultimodal = false
      this.showFileList = false
      if (this.$refs.fileInput) this.$refs.fileInput.value = ''
      if (this.$refs.folderInput) this.$refs.folderInput.value = ''
    },

    formatFileSize(bytes) {
      if (bytes === 0) return '0 Bytes'
      const k = 1024
      const sizes = ['Bytes', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    },

    // ========== AI文档提取相关方法 ==========

    handleExtractDrop(e) {
      this.isExtractDragOver = false
      const file = e.dataTransfer.files[0]
      if (file) {
        this.handleExtractFile(file)
      }
    },

    handleExtractFileSelect(e) {
      const file = e.target.files[0]
      if (file) {
        this.handleExtractFile(file)
      }
    },

    handleExtractFile(file) {
      const allowedTypes = ['.pdf', '.doc', '.docx', '.txt', '.md']
      const ext = '.' + file.name.split('.').pop().toLowerCase()
      if (!allowedTypes.includes(ext)) {
        ElMessage.error(this.$t('requirementAnalysis.invalidFileFormat'))
        return
      }
      this.extractFile = file
    },

    removeExtractFile() {
      this.extractFile = null
      this.extractedMarkdown = ''
    },

    selectAllCanvases() {
      const all = this.selectedCanvasCount === this.modaoCanvases.length
      this.modaoCanvases.forEach(c => c.selected = !all)
    },
    toggleCanvasSelection(i) {
      this.modaoCanvases[i].selected = !this.modaoCanvases[i].selected
    },
    closePreview() {
      this.previewCanvas = null
      this.previewIdx = 0
      this.previewZoom = 1
    },
    onPreviewWheel(e) {
      this.previewZoom = Math.max(0.2, Math.min(5, this.previewZoom + (e.deltaY > 0 ? -0.1 : 0.1)))
    },
    triggerReplace(i) {
      this.replaceInputs[i]?.click()
    },
    clearScreenshots(i) {
      this.modaoCanvases[i].screenshots = []
      this.saveModaoHistory(true)
    },
    async onAddScreenshot(i, e) {
      const file = e.target.files?.[0]
      if (!file) return
      // 用 import_id 定位文件夹，没有或为 upload 则生成新的
      let dir = this._modaoImportId
      if (!dir || dir === 'upload') {
        dir = Date.now().toString(36)
        this._modaoImportId = dir
      }
      const canvas = this.modaoCanvases[i]
      const filename = Date.now() + '.png'
      const relPath = `modao_screenshots/${dir}/${filename}`
      const form = new FormData()
      form.append('file', file)
      form.append('path', relPath)
      try {
        await api.post('/requirement-analysis/testcase-generation/replace-modao-screenshot/', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        canvas.screenshots.push({ url: '/media/' + relPath, width: 0, height: 0 })
        canvas.imgBroken = false
        this.saveModaoHistory(true)  // 静默持久化，不刷历史列表
        ElMessage.success('已添加')
      } catch (ex) {
        ElMessage.error('添加失败')
      }
      e.target.value = ''
    },
    deleteSelectedCanvases() {
      this.modaoCanvases = this.modaoCanvases.filter(c => !c.selected)
    },
    async saveModaoHistory(silent = false) {
      if (!this.modaoUrl || !this.modaoCanvases.length) return
      try {
        const canvases = this.modaoCanvases.map(c => ({
          name: c.name,
          screenshots: c.screenshots,
        }))
        const pId = this.manualInput.selectedProject || this.selectedProject || null
        const vIds = this.manualInput.selectedVersionIds?.length ? this.manualInput.selectedVersionIds : (this.selectedVersionIds || [])
        const payload = {
          title: this.modaoTitle,
          url: this.modaoUrl,
          data: { canvases, import_id: this._modaoImportId, project_id: pId, version_ids: vIds },
          project_id: pId,
          version_ids: vIds,
        }
        if (this._modaoHistoryId) {
          await api.put(`/requirement-analysis/wx/${this._modaoHistoryId}/`, payload)
        } else {
          const { data } = await api.post('/requirement-analysis/wx/', payload)
          this._modaoHistoryId = data.id
        }
        if (!silent) this.loadModaoHistoryList()
      } catch (e) { console.error('保存历史失败', e) }
    },
    async loadModaoHistory(i) {
      this.manualTab = 'modao'
      const h = this.modaoHistory[i]
      if (!h?.id) return
      try {
        const { data } = await api.get(`/requirement-analysis/wx/${h.id}/`)
        this.modaoUrl = data.url
        this.modaoTitle = data.title
        this._modaoHistoryId = data.id
        // 从截图URL恢复 import_id
        const firstUrl = data.data?.canvases?.[0]?.screenshots?.[0]?.url
                       || data.data?.canvases?.[0]?.screenshotUrl
                       || ''
        this._modaoImportId = firstUrl.match(/modao_screenshots\/([^/]+)\//)?.[1] || ''
        // 恢复项目/版本/模块选择
        if (data.data?.project_id) {
          this.manualInput.selectedProject = data.data.project_id
          this.loadProjectVersions(data.data.project_id)
        }
        if (data.data?.version_ids?.length) {
          this.manualInput.selectedVersionIds = data.data.version_ids
          this.loadVersionModules(data.data.version_ids, 'manual')
        }
        this.modaoCanvases = (data.data?.canvases || []).map(c => ({
          name: c.name,
          screenshots: c.screenshots || (c.screenshot_url ? [{ url: c.screenshot_url, width: c.width, height: c.height }] : []),
          selected: true,
        }))
      } catch (e) { ElMessage.error('加载历史失败') }
    },
    async deleteModaoHistory(i) {
      const h = this.modaoHistory[i]
      if (!h?.id) return
      try {
        await ElMessageBox.confirm(`确定删除「${h.title || h.url}」？`, '确认删除', { type: 'warning' })
        await api.delete(`/requirement-analysis/wx/${h.id}/`)
        this.loadModaoHistoryList()
        ElMessage.success('已删除')
      } catch (e) {
        if (e !== 'cancel') ElMessage.error('删除失败')
      }
    },
    async loadModaoHistoryList() {
      try {
        const { data } = await api.get('/requirement-analysis/wx/')
        this.modaoHistory = data || []
      } catch (e) { this.modaoHistory = [] }
    },

    async importFromModao() {
      if (!this.modaoUrl || !this.modaoToken) return
      this.isImportingModao = true
      this._importProgress = 0
      try {
        if (this.modaoToken) {
          localStorage.setItem('modao_cookie', this.modaoToken)
        }
        // 提交异步任务
        const { data } = await api.post('/requirement-analysis/testcase-generation/import-from-modao/', {
          url: this.modaoUrl,
          auth_token: this.modaoToken,
        }, { timeout: 30000 })
        if (!data.success || !data.import_id) {
          ElMessage.error(data.error || '提交失败')
          this.isImportingModao = false
          return
        }
        const importId = data.import_id

        // 轮询进度
        const poll = async () => {
          try {
            const { data: r } = await api.get(`/requirement-analysis/wx/${importId}/`)
            this._importProgress = r.progress || 0
            if (r.status === 'completed') {
              // 加载结果
              this.modaoCanvases = (r.data?.canvases || []).map(c => ({
                name: c.name,
                screenshots: (c.screenshot_url || c.screenshots)
                  ? (c.screenshots || [{ url: c.screenshot_url, width: c.width, height: c.height }])
                  : [],
                selected: true,
              }))
              this.modaoTitle = r.title || ''
              this._modaoHistoryId = r.id
              this._modaoImportId = r.data?.import_id || ''
              this.isImportingModao = false
              ElMessage.success(`导入成功: ${this.modaoCanvases.length}个画布`)
              this.loadModaoHistoryList()
              return
            }
            if (r.status === 'failed') {
              this.isImportingModao = false
              const msg = r.error_message || '未知错误'
              if (msg.includes('Cookie已失效')) {
                localStorage.removeItem('modao_cookie')
                this.modaoToken = ''
                ElMessage.warning(msg)
              } else {
                ElMessage.error('导入失败: ' + msg)
              }
              return
            }
            // 继续轮询
            setTimeout(poll, 2000)
          } catch (e) {
            this.isImportingModao = false
            ElMessage.error('查询进度失败')
          }
        }
        setTimeout(poll, 1000)
      } catch (e) {
        this.isImportingModao = false
        const msg = e.response?.data?.error || e.message || ''
        if (msg.includes('401') || msg.includes('403') || msg.includes('登录') || msg.includes('auth')) {
          localStorage.removeItem('modao_cookie')
          ElMessage.warning('Cookie 已失效，请重新获取')
        } else {
          ElMessage.error('导入失败: ' + msg)
        }
      }
    },

    async generateFromModao() {
      if (this.selectedCanvasCount === 0) {
        ElMessage.warning('请至少选择一个画布')
        return
      }
      const selected = this.modaoCanvases.filter(c => c.selected)
      this.isClarifying = true
      this.showClarificationPanel = true
      const projectId = this.manualInput.selectedProject || this.selectedProject || null
      const versionIds = this.manualInput.selectedVersionIds?.length ? this.manualInput.selectedVersionIds : (this.selectedVersionIds || [])
      this.pendingGeneration = {
        type: 'modao',
        title: this.modaoTitle || '墨刀需求',
        requirementText: `墨刀原型图「${this.modaoTitle}」，共 ${selected.length} 个画布`,
        projectId: projectId,
        versionIds: versionIds,
        functionModuleId: this.manualInput.selectedModuleId || '',
        outputMode: 'stream',
        pageImages: selected.flatMap(c =>
          (c.screenshots || []).filter(s => s.url).map(s => ({ screenshot_url: s.url, media_type: 'image/png' }))
        ),
      }
      // 更新历史记录中的项目/版本选择
      this.saveModaoHistory(true)
      try {
        const payload = {
          requirement_text: this.pendingGeneration.requirementText,
          project_id: projectId,
          version_ids: versionIds,
          function_module_id: this.manualInput.selectedModuleId || undefined,
          page_images: selected.flatMap(c =>
            (c.screenshots || []).filter(s => s.url).map(s => ({ screenshot_url: s.url, media_type: 'image/png' }))
          ),
        }
        const { data } = await api.post('/requirement-analysis/testcase-generation/clarify/', payload, { timeout: 300000 })
        this.clarificationQuestions = data.questions || []
        this.clarificationTaskId = data.task_id
        this.currentTaskId = data.task_id
        if (this.clarificationQuestions.length === 0) {
          this.skipClarification()
        }
      } catch (e) {
        this.showClarificationPanel = false
        ElMessage.error('澄清失败: ' + (e.response?.data?.error || e.message))
      } finally {
        this.isClarifying = false
      }
    },

    async extractDocument() {
      if (!this.extractFile) return
      this.isExtracting = true
      this.extractedMarkdown = ''
      try {
        const formData = new FormData()
        formData.append('title', this.extractFile.name)
        formData.append('file', this.extractFile)
        if (this.manualInput.selectedProject) {
          formData.append('project', this.manualInput.selectedProject)
        }
        const response = await api.post('/requirement-analysis/testcase-generation/extract/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 300000
        })
        this.extractedMarkdown = response.data.markdown || ''
        ElMessage.success(this.$t('requirementAnalysis.extractSuccess'))
      } catch (error) {
        ElMessage.error(this.$t('requirementAnalysis.extractFailed') + ': ' + (error.response?.data?.error || error.message))
      } finally {
        this.isExtracting = false
      }
    },

    async restoreTask(taskId) {
      try {
        const response = await api.get(`/requirement-analysis/testcase-generation/${taskId}/`)
        const task = response.data

        // 恢复需求文本和标题
        this.manualInput.title = task.title || ''
        this.manualInput.description = task.requirement_text || ''
        this.activeTab = 'manual'

        // 恢复项目
        if (task.project) {
          this.manualInput.selectedProject = task.project
          this.loadProjectVersions(task.project)
        }

        // 恢复澄清状态
        if (task.clarification_questions?.length > 0) {
          this.clarificationTaskId = task.task_id
          this.currentTaskId = task.task_id
          this.clarificationQuestions = task.clarification_questions

          // 恢复已回答
          this.clarificationAnswers = {}
          if (task.clarification_answers) {
            for (const a of task.clarification_answers) {
              if (a.question_id !== undefined) {
                this.clarificationAnswers[a.question_id] = a.answer || ''
              }
            }
          }

          // 构建生成上下文，确保确认生成时可用
          // 多模态任务带上图片引用（screenshot_url），startGeneration 走 JSON 传
          const pageImages = (task.multimodal_mode && task.page_images_base64?.length > 0)
            ? task.page_images_base64 : null
          this.pendingGeneration = {
            type: 'manual',
            title: task.title || '',
            requirementText: task.requirement_text || '',
            projectId: task.project || this.manualInput.selectedProject || null,
            versionIds: task.version_ids || [],
            functionModuleId: task.function_module || '',
            outputMode: task.output_mode || 'stream',
            pageImages
          }
          this.showClarificationPanel = true
          ElMessage.success(`已恢复任务 ${taskId}，可继续澄清或直接生成`)
        } else if (task.status === 'completed') {
          ElMessage.info('该任务已完成，请查看结果')
        }
      } catch (error) {
        console.error('恢复任务失败:', error)
        ElMessage.error('加载任务失败')
      }
    },

    async generateFromExtracted() {
      if (!this.extractedMarkdown) return
      const title = (this.extractFile?.name || '文档提取').replace(/\.[^.]+$/, '')
      const requirementText = `${this.$t('requirementAnalysis.requirementTitle')}: ${title}\n\n${this.$t('requirementAnalysis.extractedContent')}:\n${this.extractedMarkdown}`
      // AI文档提取跳过澄清，直接生成
      await this.startGeneration(
        title,
        requirementText,
        this.manualInput.selectedProject,
        this.globalOutputMode,
        this.manualInput.selectedVersionIds,
        [],
        this.manualInput.selectedModuleId || ''
      )
    },

    // ========================================

    // ========== 需求澄清相关方法 ==========

    async requestClarification(requirementText) {
      this.showClarificationPanel = true
      this.isClarifying = true
      this.clarificationQuestions = []
      this.clarificationAnswers = {}
      this.clarificationRaw = ''

      try {
        const requestBody = { requirement_text: requirementText }
        // 传递项目ID以加载知识背景
        const projectId = this.pendingGeneration?.projectId
        if (projectId) {
          requestBody.project_id = projectId
        }
        const response = await api.post('/requirement-analysis/testcase-generation/clarify/', requestBody, { timeout: 120000 })

        const questions = response.data.questions || []
        this.clarificationQuestions = questions
        this.clarificationRaw = response.data.raw || ''
        this.clarificationTaskId = response.data.task_id || null

        if (questions.length === 0) {
          // 没有不明确点，提示用户可以跳过
          ElMessage.info(this.$t('requirementAnalysis.clarificationNoQuestions'))
        } else {
          ElMessage.success(`AI发现 ${questions.length} 个需要确认的问题`)
        }
      } catch (error) {
        console.error('需求澄清失败:', error)
        const errorMsg = error.response?.data?.error || error.message
        ElMessage.error(this.$t('requirementAnalysis.clarificationFailed') + ': ' + errorMsg)

        // 出错时让用户选择是否跳过
        this.clarificationQuestions = [{
          id: 1,
          question: this.$t('requirementAnalysis.clarificationError')
        }]
      } finally {
        this.isClarifying = false
      }
    },

    async requestMultimodalClarification() {
      this.showClarificationPanel = true
      this.isClarifying = true
      this.clarificationQuestions = []
      this.clarificationAnswers = {}
      this.clarificationRaw = ''

      try {
        const formData = new FormData()
        formData.append('title', this.documentTitle)
        for (const f of this.selectedFiles) {
          formData.append('files', f)
        }
        if (this.selectedProject) {
          formData.append('project', this.selectedProject)
        }

        ElMessage.info(this.$t('requirementAnalysis.clarifying'))
        const response = await api.post('/requirement-analysis/testcase-generation/clarify/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 300000  // 5分钟超时（包含文件上传+图片提取+AI分析）
        })

        const questions = response.data.questions || []
        this.clarificationQuestions = questions
        this.clarificationRaw = response.data.raw || ''
        this.clarificationTaskId = response.data.task_id || null

        if (questions.length === 0) {
          ElMessage.info(this.$t('requirementAnalysis.clarificationNoQuestions'))
        } else {
          ElMessage.success(`AI发现 ${questions.length} 个需要确认的问题`)
        }
      } catch (error) {
        console.error('多模态需求澄清失败:', error)
        const errorMsg = error.response?.data?.error || error.message
        ElMessage.error(this.$t('requirementAnalysis.clarificationFailed') + ': ' + errorMsg)

        this.clarificationQuestions = [{
          id: 1,
          question: this.$t('requirementAnalysis.clarificationError')
        }]
      } finally {
        this.isClarifying = false
      }
    },

    async confirmWithClarification() {
      // 构建澄清回答列表
      const answers = this.clarificationQuestions
        .map(q => ({
          question_id: q.id,
          question: q.question,
          answer: this.clarificationAnswers[q.id] || ''
        }))
        .filter(a => a.answer.trim())  // 只发送有回答的问题

      // 隐藏澄清面板
      this.showClarificationPanel = false

      // 如果已有 task_id，先保存澄清答案到 task
      if (this.clarificationTaskId) {
        try {
          await api.post(`/requirement-analysis/testcase-generation/${this.clarificationTaskId}/save-answers/`, {
            clarification_answers: answers
          })
        } catch (e) {
          console.error('保存澄清答案失败:', e)
          // 不阻塞流程，继续往下
        }
      }

      // 根据pendingGeneration类型执行对应的生成
      const ctx = this.pendingGeneration
      if (!ctx) {
        ElMessage.error('生成上下文丢失，请重新填写需求')
        return
      }

      if (ctx.type === 'multimodal') {
        await this.startMultimodalGenerationWithAnswers(answers)
      } else {
        await this.startGeneration(
          ctx.title,
          ctx.requirementText,
          ctx.projectId,
          ctx.outputMode,
          ctx.versionIds,
          answers,
          ctx.functionModuleId || '',
          ctx.pageImages || null
        )
      }

      this.pendingGeneration = null
    },

    async skipClarification() {
      // 跳过澄清，直接生成
      this.showClarificationPanel = false

      const ctx = this.pendingGeneration
      if (!ctx) {
        ElMessage.error('生成上下文丢失，请重新填写需求')
        return
      }

      if (ctx.type === 'multimodal') {
        await this.startMultimodalGeneration()
      } else {
        await this.startGeneration(
          ctx.title,
          ctx.requirementText,
          ctx.projectId,
          ctx.outputMode,
          ctx.versionIds,
          [],
          ctx.functionModuleId || '',
          ctx.pageImages || null
        )
      }

      this.pendingGeneration = null
    },

    // ========================================

    async generateFromManualInput() {
      if (!this.canGenerateManual) {
        ElMessage.error(this.$t('requirementAnalysis.fillRequiredInfo'))
        return
      }

      const requirementText = `${this.$t('requirementAnalysis.requirementTitle')}: ${this.manualInput.title}\n\n${this.$t('requirementAnalysis.requirementDescription')}:\n${this.manualInput.description}`

      // 手动输入跳过澄清，直接生成
      await this.startGeneration(
        this.manualInput.title,
        requirementText,
        this.manualInput.selectedProject,
        this.globalOutputMode,
        this.manualInput.selectedVersionIds,
        [],
        this.manualInput.selectedModuleId || ''
      )
    },

    async generateFromDocument() {
      if (!this.selectedFile || !this.documentTitle) {
        ElMessage.error(this.$t('requirementAnalysis.selectFileAndTitle'))
        return
      }

      // 图片文件自动开启多模态
      if (this.isMultimodalFile && !this.enableMultimodal) {
        this.enableMultimodal = true
      }

      // 多模态模式：直接上传到多模态端点
      if (this.enableMultimodal && this.isMultimodalFile) {
        this.pendingGeneration = {
          type: 'multimodal',
          title: this.documentTitle,
          projectId: this.selectedProject,
          versionIds: this.selectedVersionIds,
          outputMode: this.globalOutputMode,
          functionModuleId: this.docSelectedModuleId || ''
        }
        await this.requestMultimodalClarification()
        return
      }

      try {
        // 文本模式：首先上传并提取文档内容
        const formData = new FormData()
        formData.append('title', this.documentTitle)
        formData.append('file', this.selectedFile)
        if (this.selectedProject) {
          formData.append('project', this.selectedProject)
        }

        ElMessage.info(this.$t('requirementAnalysis.extractingContent'))
        const uploadResponse = await api.post('/requirement-analysis/documents/', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 120000,  // 文件上传超时2分钟
        })

        // 提取文档内容（OCR可能需要较长时间，设置10分钟超时）
        ElMessage.info(this.$t('requirementAnalysis.extractingContent'))
        const extractResponse = await api.get(`/requirement-analysis/documents/${uploadResponse.data.id}/extract_text/`, {
          timeout: 600000,  // OCR提取超时10分钟
        })
        const extractedText = extractResponse.data.extracted_text

        if (!extractedText || extractedText.trim().length === 0) {
          ElMessage.error(this.$t('requirementAnalysis.extractionFailed'))
          return
        }

        const requirementText = `${this.$t('requirementAnalysis.documentTitle')}: ${this.documentTitle}\n\n${this.$t('requirementAnalysis.documentContent')}:\n${extractedText}`

        // 保存上下文，先执行需求澄清
        this.pendingGeneration = {
          type: 'document',
          title: this.documentTitle,
          requirementText: requirementText,
          projectId: this.selectedProject,
          versionIds: this.selectedVersionIds,
          outputMode: this.globalOutputMode,
          functionModuleId: this.docSelectedModuleId || ''
        }

        await this.requestClarification(requirementText)

      } catch (error) {
        console.error(this.$t('requirementAnalysis.documentProcessingFailed'), error)
        ElMessage.error(this.$t('requirementAnalysis.documentProcessingFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    async startMultimodalGeneration(clarificationAnswers = []) {
      // 生成前强制刷新token，避免停留过久导致401
      try {
        const userStore = useUserStore()
        if (userStore.refreshToken) {
          console.log('Refreshing token before multimodal generation...')
          await userStore.refreshAccessToken()
        }
      } catch (e) {
        console.error('Token refresh failed:', e)
        ElMessage.error('登录已过期，请刷新页面重新登录')
        return
      }

      this.isGenerating = true
      this.currentStep = 1
      this.progressText = '准备多模态生成...'
      this.streamedContent = ''
      this.finalTestCases = ''
      this.streamedReviewContent = ''
      this.hasShownCompletionMessage = false
      this.showResults = false

      try {
        const formData = new FormData()
        formData.append('title', this.documentTitle)
        for (const f of this.selectedFiles) {
          formData.append('files', f)
        }
        formData.append('output_mode', this.globalOutputMode)
        if (this.selectedProject) {
          formData.append('project', this.selectedProject)
        }
        if (this.selectedVersionIds && this.selectedVersionIds.length > 0) {
          formData.append('version_ids', JSON.stringify(this.selectedVersionIds))
        }
        if (clarificationAnswers && clarificationAnswers.length > 0) {
          formData.append('clarification_answers', JSON.stringify(clarificationAnswers))
        }
        // 传递功能模块ID
        const moduleId = this.pendingGeneration?.functionModuleId || this.docSelectedModuleId
        if (moduleId) {
          formData.append('function_module_id', moduleId)
        }
        // 传递 clarify task_id 复用已有任务
        if (this.clarificationTaskId) {
          formData.append('task_id', this.clarificationTaskId)
        }

        ElMessage.info('正在上传PDF并提取图文...')
        const response = await api.post(
          '/requirement-analysis/testcase-generation/generate_multimodal/',
          formData,
          {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 600000  // 10分钟超时（包含上传+图片提取+AI生成）
          }
        )

        this.currentTaskId = response.data.task_id
        this.progressText = '视觉模型正在分析文档图片...'

        if (this.globalOutputMode === 'stream') {
          this.startStreamingProgress()
        } else {
          this.startPolling()
        }

      } catch (error) {
        console.error('多模态生成任务创建失败:', error)
        ElMessage.error('多模态生成失败: ' + (error.response?.data?.error || error.message))
        this.isGenerating = false
        if (this.clarificationQuestions.length > 0) {
          this.showClarificationPanel = true
        }
      }
    },

    async startMultimodalGenerationWithAnswers(answers) {
      await this.startMultimodalGeneration(answers)
    },

    async startGeneration(title, requirementText, projectId, outputMode = 'stream', versionIds = [], clarificationAnswers = [], functionModuleId = '', pageImages = null) {
      // 在开始生成前，强制刷新token确保生成过程中不会过期
      try {
        const userStore = useUserStore()
        if (userStore.refreshToken) {
          console.log('Refreshing token before generation...')
          await userStore.refreshAccessToken()
          console.log('Token refreshed successfully, safe to start generation')
        }
      } catch (error) {
        console.error('Token refresh failed:', error)
        ElMessage.error('登录已过期，请刷新页面重新登录')
        return
      }

      this.isGenerating = true
      this.currentStep = 1
      this.progressText = this.$t('requirementAnalysis.creatingTask')
      this.streamedContent = ''  // 清空流式内容
      this.finalTestCases = ''  // 清空最终版用例
      this.streamedReviewContent = ''  // 清空评审内容
      this.hasShownCompletionMessage = false  // 重置完成消息标志位
      this.showResults = false  // 隐藏上一次的结果

      try {
        // 调用新的生成API
        const requestData = {
          title: title,
          requirement_text: requirementText,
          use_writer_model: true,
          use_reviewer_model: true,
          output_mode: outputMode  // 添加输出模式参数
        }

        // 如果选择了项目，添加到请求中
        if (projectId) {
          requestData.project_id = projectId
        }

        // 如果选择了版本，添加到请求中
        if (versionIds && versionIds.length > 0) {
          requestData.version_ids = versionIds
        }

        // 如果提供了澄清回答，添加到请求中
        if (clarificationAnswers && clarificationAnswers.length > 0) {
          requestData.clarification_answers = clarificationAnswers
        }

        // 如果有截图（墨刀导入），添加到请求中
        if (pageImages && pageImages.length > 0) {
          requestData.page_images = pageImages
        }

        // 如果选择了功能模块，添加到请求中
        if (functionModuleId) {
          requestData.function_module_id = functionModuleId
        }
        // 传递 clarify task_id 复用已有任务
        if (this.clarificationTaskId) {
          requestData.task_id = this.clarificationTaskId
        }

        const response = await api.post('/requirement-analysis/testcase-generation/generate/', requestData)

        this.currentTaskId = response.data.task_id
        this.progressText = this.$t('requirementAnalysis.taskCreated')

        ElMessage.success(this.$t('requirementAnalysis.generateSuccess'))

        // 根据输出模式选择不同的进度获取方式
        if (outputMode === 'stream') {
          this.startStreamingProgress()
        } else {
          this.startPolling()
        }

      } catch (error) {
        console.error(this.$t('requirementAnalysis.createTaskFailed'), error)
        ElMessage.error(this.$t('requirementAnalysis.createTaskFailed') + ': ' + (error.response?.data?.error || error.message))
        this.isGenerating = false
        if (this.clarificationQuestions.length > 0) {
          this.showClarificationPanel = true
        }
      }
    },

    startStreamingProgress() {
      // 使用SSE进行流式进度获取
      // 注意：EventSource不使用axios代理，需要直接指向后端服务器
      // 完整的URL路径: /api/requirement-analysis/testcase-generation/{task_id}/stream_progress/

      // 动态获取后端URL：使用当前页面的协议和主机名
      // 在生产环境中(如Docker部署)，通常通过Nginx反向代理访问，端口应该是80或443(与当前页面一致)
      // 而不是直接访问后端端口8000
      const currentOrigin = window.location.origin
      const apiUrl = `${currentOrigin}/api/requirement-analysis/testcase-generation/${this.currentTaskId}/stream_progress/`

      console.log('SSE连接URL:', apiUrl)

      // 创建EventSource（不支持自定义headers，使用withCredentials发送cookie）
      this.eventSource = new EventSource(apiUrl, { withCredentials: true })

      // 监听连接打开事件
      this.eventSource.onopen = (event) => {
        console.log('✅ SSE连接已打开', event)
      }

      this.eventSource.onmessage = (event) => {
        console.log('📨 收到SSE消息:', event.data)

        try {
          const data = JSON.parse(event.data)
          console.log('📦 解析后的数据:', data)

          if (data.type === 'progress') {
            // Update progress status
            if (data.status === 'generating') {
              this.currentStep = 2
              this.progressText = `${this.$t('requirementAnalysis.statusGenerating')} ${data.progress}%`
            } else if (data.status === 'reviewing') {
              this.currentStep = 3
              this.progressText = `${this.$t('requirementAnalysis.statusReviewing')} ${data.progress}%`
            } else if (data.status === 'revising') {
              this.currentStep = 3
              this.progressText = `${this.$t('requirementAnalysis.statusRevising')} ${data.progress}%`
            }
          } else if (data.type === 'content') {
            // Real-time streaming content (case generation)
            console.log('✍️ Received streaming content:', data.content.length, 'characters')
            this.streamedContent += data.content
            this.currentStep = 2
            this.progressText = this.$t('requirementAnalysis.statusGenerating')
          } else if (data.type === 'review_content') {
            // Real-time review content
            console.log('📝 Received review content:', data.content.length, 'characters', 'Total length:', this.streamedReviewContent.length + data.content.length)
            this.streamedReviewContent += data.content
            this.currentStep = 3
            this.progressText = this.$t('requirementAnalysis.statusReviewing')
          } else if (data.type === 'final_content') {
            // Real-time final test cases content
            console.log('🎯 Received final cases content:', data.content.length, 'characters', 'Total length:', this.finalTestCases.length + data.content.length)
            this.finalTestCases += data.content
            this.currentStep = 3
            this.progressText = '🎯 ' + this.$t('requirementAnalysis.statusRevising')
          } else if (data.type === 'status') {
            // Final status
            console.log('📊 Received status update:', data.status)
            if (data.status === 'completed') {
              this.progressText = this.$t('requirementAnalysis.statusCompleted')
              // Fetch final result
              this.fetchFinalResult()
            } else if (data.status === 'failed') {
              this.progressText = this.$t('requirementAnalysis.statusFailed')
              this.handleGenerationError()
            }
          } else if (data.type === 'done') {
            // 流式结束，立即关闭EventSource，获取最终结果
            console.log('✅ 流式传输完成')
            if (this.eventSource) {
              console.log('🔒 关闭SSE连接')
              this.eventSource.close()
              this.eventSource = null
            }
            this.fetchFinalResult()
          }
        } catch (e) {
          console.error('❌ 解析SSE数据失败:', e, '原始数据:', event.data)
        }
      }

      this.eventSource.onerror = (error) => {
        console.log('⚠️ SSE连接事件:', error)

        // 如果EventSource已经被关闭（在onmessage中关闭的），不做任何处理
        if (!this.eventSource) {
          console.log('ℹ️ EventSource已关闭，忽略错误事件')
          return
        }

        console.log('EventSource状态:', {
          readyState: this.eventSource.readyState,
          url: this.eventSource.url
        })

        // 如果任务已经完成或不在生成中，不要降级
        if (this.showResults || !this.isGenerating) {
          console.log('ℹ️ 任务已完成或不在生成中，不降级到轮询')
          // 清理EventSource
          if (this.eventSource) {
            this.eventSource.close()
            this.eventSource = null
          }
          return
        }

        // readyState=2表示连接已关闭，readyState=0表示连接中断
        // EventSource会自动重连（readyState=0），除非是致命错误（readyState=2）
        if (this.eventSource.readyState === 2) {
          console.error('❌ SSE连接永久关闭，降级到轮询模式')
          this.eventSource.close()
          this.eventSource = null
          ElMessage.warning(this.$t('requirementAnalysis.streamConnectionInterrupted'))
          this.startPolling()
        } else if (this.eventSource.readyState === 0) {
          // EventSource正在重连，等待一段时间后检查
          console.log('🔄 SSE正在重连...')
          setTimeout(() => {
            // 如果5秒后还是断开状态，降级到轮询
            if (this.eventSource && this.eventSource.readyState === 0) {
              console.error('❌ SSE重连失败，降级到轮询模式')
              this.eventSource.close()
              this.eventSource = null
              ElMessage.warning(this.$t('requirementAnalysis.streamConnectionInterrupted'))
              this.startPolling()
            }
          }, 5000)
        }
      }
    },

    async fetchFinalResult() {
      try {
        // 修复URL：去掉多余的/api/前缀（axios baseURL已经包含/api）
        const response = await api.get(`/requirement-analysis/testcase-generation/${this.currentTaskId}/progress/`)
        const task = response.data

        this.generationResult = task
        this.showResults = true
        this.isGenerating = false

        // 设置第4步为完成状态
        this.currentStep = 4

        // 设置最终版用例（如果还没有通过流式接收完整）
        if (task.final_test_cases) {
          console.log('📝 Getting final cases from task object')
          // 无论this.finalTestCases是否已有值，都用最新的final_test_cases覆盖
          // 这样确保完整输出模式下也能正确显示最终版用例
          this.finalTestCases = task.final_test_cases
        }

        // 如果评审内容为空，从task对象中获取
        if (!this.streamedReviewContent && task.review_feedback) {
          console.log('📝 Getting review content from task object')
          this.streamedReviewContent = task.review_feedback
        }

        // 如果生成内容为空，从task对象中获取
        if (!this.streamedContent && task.generated_test_cases) {
          console.log('✍️ Getting generated content from task object')
          this.streamedContent = task.generated_test_cases
        }

        if (this.eventSource) {
          this.eventSource.close()
          this.eventSource = null
        }

        // Only show completion message once
        if (!this.hasShownCompletionMessage) {
          ElMessage.success(this.$t('requirementAnalysis.generateCompleteSuccess'))
          this.hasShownCompletionMessage = true
        }
      } catch (error) {
        console.error('Failed to fetch final result:', error)
        ElMessage.error(this.$t('requirementAnalysis.fetchResultFailed'))
        this.isGenerating = false
      }
    },

    handleGenerationError() {
      this.isGenerating = false
      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
      }
      if (this.pollInterval) {
        clearInterval(this.pollInterval)
        this.pollInterval = null
      }
    },

    startPolling() {
      this.pollInterval = setInterval(async () => {
        try {
          // 修复URL：去掉多余的/api/前缀（axios baseURL已经包含/api）
          const response = await api.get(`/requirement-analysis/testcase-generation/${this.currentTaskId}/progress/`)
          const task = response.data

          console.log(`${this.$t('requirementAnalysis.taskStatus')}: ${task.status}, ${this.$t('requirementAnalysis.progress')}: ${task.progress}%`)

          // 更新进度显示
          if (task.status === 'generating') {
            this.currentStep = 2
            this.progressText = this.$t('requirementAnalysis.statusGenerating')
          } else if (task.status === 'reviewing') {
            this.currentStep = 3
            this.progressText = this.$t('requirementAnalysis.statusReviewing')
          } else if (task.status === 'completed') {
            this.currentStep = 4
            this.progressText = this.$t('requirementAnalysis.statusCompleted')

            // 任务完成，显示结果
            this.generationResult = task
            this.showResults = true
            this.isGenerating = false

            // 设置显示内容（完整输出模式下需要）
            if (task.generated_test_cases) {
              console.log('✍️ Polling mode - Setting generated content')
              this.streamedContent = task.generated_test_cases
            }
            if (task.review_feedback) {
              console.log('📝 Polling mode - Setting review content')
              this.streamedReviewContent = task.review_feedback
            }
            if (task.final_test_cases) {
              console.log('🎯 Polling mode - Setting final test cases')
              this.finalTestCases = task.final_test_cases
            }

            clearInterval(this.pollInterval)
            this.pollInterval = null

            // 只显示一次完成消息
            if (!this.hasShownCompletionMessage) {
              ElMessage.success(this.$t('requirementAnalysis.generateCompleteSuccess'))
              this.hasShownCompletionMessage = true
            }
            return
          } else if (task.status === 'failed') {
            this.progressText = this.$t('requirementAnalysis.statusFailed')
            this.isGenerating = false

            clearInterval(this.pollInterval)
            this.pollInterval = null

            ElMessage.error(this.$t('requirementAnalysis.generateFailed') + ': ' + (task.error_message || this.$t('requirementAnalysis.unknownError')))
            return
          }

        } catch (error) {
          console.error(this.$t('requirementAnalysis.checkProgressFailed'), error)
          // 继续轮询，不中断
        }
      }, 3000) // 每3秒检查一次
    },

    cancelGeneration() {
      if (this.pollInterval) {
        clearInterval(this.pollInterval)
        this.pollInterval = null
      }
      this.isGenerating = false
      this.currentTaskId = null
      ElMessage.info(this.$t('requirementAnalysis.generationCancelled'))
    },

    // 下载测试用例为xlsx文件
    async downloadTestCases() {
      try {
        // 解析最终测试用例内容
        const finalTestCases = this.generationResult.final_test_cases;
        const taskId = this.generationResult.task_id;

        // 创建工作簿
        const workbook = XLSX.utils.book_new();

        // 过滤掉总结和建议部分，只保留测试用例内容
        const filteredContent = this.filterTestCasesOnly(finalTestCases);

        // 尝试解析表格格式的测试用例（参考AutoGenTestCase的做法）
        const tableFormat = this.parseTableFormat(filteredContent);

        let worksheetData = [];

        if (tableFormat.length > 0) {
          // 如果解析到表格格式，直接使用，但要确保表头正确
          worksheetData = tableFormat;

          // 检查并修正表头
          if (worksheetData.length > 0) {
            const header = worksheetData[0];
            for (let i = 0; i < header.length; i++) {
              if (header[i] && header[i].includes('测试步骤')) {
                header[i] = header[i].replace('测试步骤', '操作步骤');
              }
              if (header[i] && header[i].includes('Test Steps')) {
                header[i] = header[i].replace('Test Steps', '操作步骤');
              }
            }
          }
        } else {
          // 否则尝试解析结构化格式
          worksheetData = this.parseStructuredFormat(filteredContent);
        }

        // 将所有单元格中的<br>标签转换为换行符
        worksheetData = worksheetData.map(row =>
          row.map(cell => this.convertBrToNewline(cell))
        );

        // 创建工作表
        const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);

        // 设置列宽
        const colWidths = [
          { wch: 15 }, // 测试用例编号
          { wch: 30 }, // 测试场景
          { wch: 25 }, // 前置条件
          { wch: 40 }, // 操作步骤
          { wch: 30 }, // 预期结果
          { wch: 10 }  // 优先级
        ];
        worksheet['!cols'] = colWidths;

        // 设置表头样式（加粗）
        if (worksheetData.length > 1) {
          for (let col = 0; col < Math.min(6, worksheetData[0].length); col++) {
            const cellAddress = XLSX.utils.encode_cell({ r: 0, c: col });
            if (!worksheet[cellAddress]) continue;
            worksheet[cellAddress].s = {
              font: { bold: true },
              alignment: { horizontal: 'center', vertical: 'center', wrapText: true }
            };
          }

          // 设置自动换行
          for (let row = 1; row < worksheetData.length; row++) {
            for (let col = 0; col < Math.min(6, worksheetData[row].length); col++) {
              const cellAddress = XLSX.utils.encode_cell({ r: row, c: col });
              if (worksheet[cellAddress]) {
                worksheet[cellAddress].s = {
                  alignment: { vertical: 'top', wrapText: true }
                };
              }
            }
          }
        }

        // 将工作表添加到工作簿
        XLSX.utils.book_append_sheet(workbook, worksheet, this.$t('requirementAnalysis.testCaseSheetName'));

        // 生成文件名（包含任务ID和日期）
        const fileName = this.$t('requirementAnalysis.excelFileName', { taskId: taskId, date: new Date().toISOString().slice(0, 10) });

        // 导出文件
        XLSX.writeFile(workbook, fileName);

        ElMessage.success(this.$t('requirementAnalysis.downloadSuccess'));
      } catch (error) {
        console.error(this.$t('requirementAnalysis.downloadFailed'), error);
        ElMessage.error(this.$t('requirementAnalysis.downloadFailed') + ': ' + (error.message || this.$t('requirementAnalysis.unknownError')));
      }
    },

    // 保存到用例记录
    async saveToTestCaseRecords() {
      try {
        // 调用后端API保存到记录
        const response = await api.post(`/requirement-analysis/testcase-generation/${this.generationResult.task_id}/save_to_records/`)

        if (response.data.already_saved) {
          ElMessage.info(this.$t('requirementAnalysis.alreadySaved'))
        } else {
          const importedCount = response.data.imported_count || 0
          ElMessage.success(`测试用例已保存！已导入 ${importedCount} 条测试用例到测试用例管理系统`)
        }

        // 不跳转，留在当前页面
        // this.$router.push('/generated-testcases')
      } catch (error) {
        console.error(this.$t('requirementAnalysis.saveFailed'), error)
        ElMessage.error(this.$t('requirementAnalysis.saveFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    resetGeneration() {
      // 重置生成状态
      this.isGenerating = false;
      this.currentTaskId = null;
      this.progressText = this.$t('requirementAnalysis.preparing');
      this.currentStep = 0;
      this.showResults = false;
      this.generationResult = null;

      // 清空流式内容和最终版用例
      this.streamedContent = '';
      this.streamedReviewContent = '';
      this.finalTestCases = '';

      if (this.pollInterval) {
        clearInterval(this.pollInterval);
        this.pollInterval = null;
      }

      // 刷新页面以获取最新的配置
      window.location.reload();
    },

    // 格式化日期时间
    formatDateTime(dateTimeString) {
      if (!dateTimeString) return '';
      const date = new Date(dateTimeString);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${year}-${month}-${day} ${hours}:${minutes}`;
    },

    // 格式化Markdown为HTML（简化版）
    formatMarkdown(content) {
      if (!content) return '';

      let html = content
          .replace(/\*\*新增\*\*-/g, '')
          .replace(/新增-/g, '');

      // Step 1: Handle code blocks first (preserve their content)
      const codeBlocks = [];
      html = html.replace(/```([\s\S]+?)```/g, (_, code) => {
        codeBlocks.push(`<pre><code>${this.escapeHtml(code.trim())}</code></pre>`);
        return `%%CODEBLOCK_${codeBlocks.length - 1}%%`;
      });

      // Step 2: Escape HTML in remaining content
      html = this.escapeHtml(html);

      // Step 3: Markdown tables
      html = html.replace(/((?:^\|.+\|\s*$\n?)+)/gm, (tableBlock) => {
        const lines = tableBlock.trim().split('\n').filter(l => l.includes('|'));
        if (lines.length < 2) return tableBlock;
        let result = '<table>';
        lines.forEach((line, i) => {
          if (i === 1 && /^\|[\s\-:|]+\|$/.test(line)) return; // skip separator
          const tag = i === 0 ? 'th' : 'td';
          const cells = line.split('|').filter(c => c.trim() !== '');
          result += '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
        });
        result += '</table>';
        return result;
      });

      // Step 4: Headings
      html = html.replace(/^#{6}\s+(.+)$/gm, '<h6>$1</h6>');
      html = html.replace(/^#{5}\s+(.+)$/gm, '<h5>$1</h5>');
      html = html.replace(/^#{4}\s+(.+)$/gm, '<h4>$1</h4>');
      html = html.replace(/^#{3}\s+(.+)$/gm, '<h3>$1</h3>');
      html = html.replace(/^#{2}\s+(.+)$/gm, '<h2>$1</h2>');
      html = html.replace(/^#{1}\s+(.+)$/gm, '<h1>$1</h1>');

      // Step 5: Bold, italic
      html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
      html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
      html = html.replace(/_(.+?)_/g, '<em>$1</em>');

      // Step 6: Inline code
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

      // Step 7: Unordered lists
      html = html.replace(/((?:^[\-\*]\s+.+$\n?)+)/gm, (match) => {
        const items = match.trim().split('\n').map(l => `<li>${l.replace(/^[\-\*]\s+/, '')}</li>`).join('');
        return `<ul>${items}</ul>`;
      });

      // Step 8: Ordered lists
      html = html.replace(/((?:^\d+\.\s+.+$\n?)+)/gm, (match) => {
        const items = match.trim().split('\n').map(l => `<li>${l.replace(/^\d+\.\s+/, '')}</li>`).join('');
        return `<ol>${items}</ol>`;
      });

      // Step 9: Line breaks
      html = html.replace(/\n/g, '<br>');

      // Step 10: Restore code blocks
      html = html.replace(/%%CODEBLOCK_(\d+)%%/g, (_, i) => codeBlocks[parseInt(i)]);

      return html;
    },
    escapeHtml(text) {
      return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },

    // 将HTML的<br>标签转换为换行符（用于Excel导出）
    convertBrToNewline(text) {
      if (!text) return '';
      return text.replace(/<br\s*\/?>/gi, '\n');
    },

    // 过滤掉总结和建议部分，只保留测试用例内容
    filterTestCasesOnly(content) {
      if (!content) return '';

      const lines = content.split('\n');
      const filteredLines = [];
      let inTestCaseSection = true;

      for (let line of lines) {
        const trimmedLine = line.trim();

        // 检查是否到了总结或建议部分
        if (trimmedLine.includes('总结') ||
            trimmedLine.includes('建议') ||
            trimmedLine.includes('Summary') ||
            trimmedLine.includes('Recommendation') ||
            trimmedLine.includes('最后') ||
            trimmedLine.includes('补充说明')) {
          inTestCaseSection = false;
          break;
        }

        if (inTestCaseSection) {
          filteredLines.push(line);
        }
      }

      return filteredLines.join('\n');
    },

    // 解析表格格式的测试用例（参考AutoGenTestCase的做法）
    parseTableFormat(content) {
      if (!content) return [];

      const lines = content.split('\n').filter(line => line.trim());
      const worksheetData = [];

      for (let line of lines) {
        const trimmedLine = line.trim();

        // 检查是否是表格行（包含|分隔符，且不是分隔线）
        if (trimmedLine.includes('|') && !trimmedLine.includes('--------')) {
          const cells = trimmedLine.split('|').map(cell => cell.trim()).filter(cell => cell);
          if (cells.length > 1) {
            worksheetData.push(cells);
          }
        }
      }

      return worksheetData;
    },

    // 解析结构化格式的测试用例
    parseStructuredFormat(content) {
      if (!content) return [];

      const lines = content.split('\n').filter(line => line.trim());
      const worksheetData = [];

      // 添加表头
      worksheetData.push([
        this.$t('requirementAnalysis.excelTestCaseNumber'),
        this.$t('requirementAnalysis.excelTestScenario'),
        this.$t('requirementAnalysis.excelPrecondition'),
        this.$t('requirementAnalysis.excelTestSteps'),
        this.$t('requirementAnalysis.excelExpectedResult'),
        this.$t('requirementAnalysis.excelPriority')
      ]);

      let currentTestCase = {};
      let testCaseNumber = 1;
      let i = 0;

      while (i < lines.length) {
        const line = lines[i].trim();

        // 识别测试用例开始标志
        if (line.includes('测试用例') || line.includes('Test Case') ||
            line.match(/^(\d+\.|\*|\-|\d+、)/)) {

          // 如果之前有测试用例数据，先保存
          if (Object.keys(currentTestCase).length > 0) {
            worksheetData.push([
              currentTestCase.number || `TC${testCaseNumber}`,
              currentTestCase.scenario || '',
              currentTestCase.precondition || '',
              currentTestCase.steps || '',
              currentTestCase.expected || '',
              currentTestCase.priority || '中'
            ]);
            testCaseNumber++;
          }

          // 开始新的测试用例
          currentTestCase = {
            number: `TC${testCaseNumber}`,
            scenario: line.replace(/^(\d+\.|\*|\-|\d+、)\s*/, '').replace(/测试用例\d*[:：]?\s*/, ''),
            precondition: '',
            steps: '',
            expected: '',
            priority: '中'
          };
          i++;
        }
        // 识别前置条件
        else if (line.includes('前置条件') || line.includes('前提') ||
            line.includes('Precondition')) {
          let precondition = line.replace(/.*?[:：]\s*/, '');
          // 收集后续的前置条件行
          i++;
          while (i < lines.length) {
            const nextLine = lines[i].trim();
            if (nextLine.includes('测试步骤') || nextLine.includes('操作步骤') ||
                nextLine.includes('Test Steps') || nextLine.includes('步骤') ||
                nextLine.includes('预期结果') || nextLine.includes('Expected') ||
                nextLine.includes('优先级') || nextLine.includes('Priority') ||
                nextLine.includes('测试用例') || nextLine.includes('Test Case') ||
                nextLine.match(/^(\d+\.|\*|\-|\d+、)/)) {
              break;
            }
            if (nextLine) {
              precondition += '\n' + nextLine;
            }
            i++;
          }
          currentTestCase.precondition = precondition;
        }
        // 识别测试步骤
        else if (line.includes('测试步骤') || line.includes('操作步骤') ||
            line.includes('Test Steps') || line.includes('步骤')) {
          let steps = line.replace(/.*?[:：]\s*/, '');
          // 收集后续的步骤行
          i++;
          while (i < lines.length) {
            const nextLine = lines[i].trim();
            if (nextLine.includes('预期结果') || nextLine.includes('Expected') ||
                nextLine.includes('优先级') || nextLine.includes('Priority') ||
                nextLine.includes('测试用例') || nextLine.includes('Test Case') ||
                nextLine.match(/^(\d+\.|\*|\-|\d+、)/)) {
              break;
            }
            if (nextLine) {
              steps += '\n' + nextLine;
            }
            i++;
          }
          currentTestCase.steps = steps;
        }
        // 识别预期结果
        else if (line.includes('预期结果') || line.includes('Expected') ||
            line.includes('期望')) {
          let expected = line.replace(/.*?[:：]\s*/, '');
          // 收集后续的结果行
          i++;
          while (i < lines.length) {
            const nextLine = lines[i].trim();
            if (nextLine.includes('优先级') || nextLine.includes('Priority') ||
                nextLine.includes('测试用例') || nextLine.includes('Test Case') ||
                nextLine.match(/^(\d+\.|\*|\-|\d+、)/)) {
              break;
            }
            if (nextLine) {
              expected += '\n' + nextLine;
            }
            i++;
          }
          currentTestCase.expected = expected;
        }
        // 识别优先级
        else if (line.includes('优先级') || line.includes('Priority')) {
          currentTestCase.priority = line.replace(/.*?[:：]\s*/, '');
          i++;
        }
        // 如果是没有明确标识的行，可能是场景描述的延续
        else if (Object.keys(currentTestCase).length > 0 &&
            !currentTestCase.steps && !currentTestCase.expected &&
            !currentTestCase.precondition) {
          if (currentTestCase.scenario && line.length > 5) {
            currentTestCase.scenario += '\n' + line;
          }
          i++;
        } else {
          i++;
        }
      }

      // 保存最后一个测试用例
      if (Object.keys(currentTestCase).length > 0) {
        worksheetData.push([
          currentTestCase.number || `TC${testCaseNumber}`,
          currentTestCase.scenario || '',
          currentTestCase.precondition || '',
          currentTestCase.steps || '',
          currentTestCase.expected || '',
          currentTestCase.priority || '中'
        ]);
      }

      // 如果没有解析到结构化数据，则按原格式输出
      if (worksheetData.length <= 1) {
        worksheetData.length = 0; // 清空
        worksheetData.push([this.$t('requirementAnalysis.testCaseContent')]);
        content.split('\n').forEach((line, index) => {
          if (line.trim()) {
            worksheetData.push([line.trim()]);
          }
        });
      }

      return worksheetData;
    }
  }
}
</script>

<style scoped>
/* =============================================
   Endfield Maximal — Unboxed
   ============================================= */
.ef-root {
  --ef-ink: #191919;
  --ef-paper: #f2f2f0;
  --ef-signal: #fffa00;
  --ef-state: #00ffa2;

  min-height: calc(100vh - 52px);
  background: #eeedeb;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  position: relative;
  overflow-x: hidden;
}

/* Dual grid: rect + diagonal guide lines */
.ef-grid {
  position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background-image:
    linear-gradient(to right, rgba(0,0,0,.035) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0,0,0,.035) 1px, transparent 1px);
  background-size: 80px 80px;
}
.ef-grid__diag {
  position: fixed; inset: 0; pointer-events: none; z-index: 0; opacity: .25;
  background:
    repeating-linear-gradient(55deg, transparent, transparent 159px, rgba(0,0,0,.03) 159px, rgba(0,0,0,.03) 160px);
}

/* ======== Stage ======== */
.ef-stage {
  position: relative; z-index: 5;
  max-width: 1040px; margin: 0 auto;
  padding: 0 28px 100px;
  overflow: hidden;
}

/* ======== Identity strip ======== */
.ef-identity {
  display: flex; align-items: flex-start; gap: 20px;
  padding: 40px 0 36px;
  &__wedge {
    width: 16px; height: 68px; background: var(--ef-signal); flex-shrink: 0; margin-top: 4px;
    clip-path: polygon(0 0, 100% 0, 100% 70%, 55% 100%, 0 100%);
  }
  &__kicker {
    font-size: 11px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .18em; color: #777; margin: 0 0 6px; font-weight: 600;
  }
  &__title {
    font-size: 2.6rem; font-weight: 900; color: var(--ef-ink); margin: 0;
    line-height: .88; letter-spacing: -.04em;
  }
  &__right {
    margin-left: auto; text-align: right; display: flex; flex-direction: column;
    align-items: flex-end; gap: 8px; padding-top: 8px;
  }
  &__code {
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .1em; color: #999;
  }
  &__status {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .12em; font-weight: 600;
    padding: 4px 12px; border: 1px solid #d0d0c8; color: #999;
    &.is-live { border-color: var(--ef-signal); color: #8a7a00; }
    &.is-done { border-color: var(--ef-state); color: #007a4d; }
  }
}

/* ======== Section ======== */
.ef-section {
  position: relative;
  padding: 28px 0;
  margin-bottom: 1px;
  &::before { display: none; }
  &--clarify { padding-left: 16px; &::before { display: block; content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px; background: var(--ef-signal); } }
  &--results { padding-left: 16px; overflow: hidden; &::before { display: block; content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px; background: var(--ef-signal); } }
  &--alt { padding-left: 20px; }

  &__num {
    position: absolute; left: 8px; top: 24px;
    font-size: 36px; font-weight: 900; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #d8d6d0; line-height: 1; letter-spacing: -.04em;
  }
  &__label {
    font-size: 15px; font-weight: 800; color: var(--ef-ink); margin: 0 0 20px;
    padding-left: 14px; border-left: 3px solid var(--ef-signal);
    letter-spacing: .02em;
  }
  &__badge {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    padding: 1px 8px; border: 1px solid #d8d6d0; color: #999; margin-left: 8px; vertical-align: middle;
    &.is-live { border-color: var(--ef-signal); color: #8a7a00; animation: ef-blink 1.2s ease-in-out infinite; }
  }
  &__body { position: relative; min-width: 0; overflow: hidden; }
}
@keyframes ef-blink { 0%,100%{opacity:1} 50%{opacity:.25} }

/* ======== Mode cards ======== */
.ef-mode-row { display: flex; gap: 12px; }
.ef-mode {
  flex: 1; display: flex; align-items: center; gap: 14px;
  padding: 16px 18px; background: #fff; cursor: pointer;
  border: 1px solid transparent; border-bottom: 2px solid #e0ded8;
  transition: all .15s;
  &:hover { background: #fafaf8; }
  &.is-on { background: #fffef5; border-color: var(--ef-signal); border-bottom-color: var(--ef-ink); }
  &__letter {
    width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
    font-size: 15px; font-weight: 900; font-family: "Space Grotesk", system-ui, sans-serif;
    background: #f2f2f0; color: #bbb; flex-shrink: 0;
  }
  .is-on &__letter { background: var(--ef-ink); color: var(--ef-signal); }
  &__title { font-size: 15px; font-weight: 700; color: #222; }
  &__desc { font-size: 13px; color: #777; margin-left: auto; text-align: right; }
}

/* ======== Tabs ======== */
.ef-tabs { display: flex; gap: 0; margin-bottom: 20px; }
.ef-tab {
  all: unset; cursor: pointer;
  padding: 8px 22px; font-size: 12px;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .08em; font-weight: 600;
  color: #aaa; border-bottom: 2px solid transparent;
  transition: all .12s;
  &:hover { color: #666; }
  &.is-on { color: var(--ef-ink); border-bottom-color: var(--ef-signal); font-weight: 700; }
}
.ef-tab-body { display: flex; flex-direction: column; gap: 16px; }

/* ======== Fields ======== */
.ef-fields { display: flex; gap: 14px; flex-wrap: wrap; }
.ef-field {
  display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 160px;
  &--wide { flex: 2; min-width: 260px; }
  label {
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .08em; color: #555; font-weight: 700;
  }
}
.ef-input {
  padding: 10px 14px; border: 1px solid #ccc; font-size: 13px; color: #333;
  width: 100%; box-sizing: border-box; font-family: inherit; background: #fff;
  &:focus { outline: none; border-color: var(--ef-signal); box-shadow: 0 0 0 1px rgba(255,250,0,.15); }
  &--area { resize: vertical; line-height: 1.6; }
}
.ef-select {
  padding: 10px 32px 10px 14px; border: 1px solid #ccc; font-size: 13px; color: #333;
  width: 100%; box-sizing: border-box; background: #fff; cursor: pointer; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%23999'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 12px center;
  &:focus { outline: none; border-color: var(--ef-signal); box-shadow: 0 0 0 1px rgba(255,250,0,.15); }
}

/* ======== Actions ======== */
.ef-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding-top: 4px; }

/* ======== Buttons ======== */
.ef-btn {
  all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 24px; font-size: 12px; font-weight: 600;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .06em;
  color: #555; background: #fff; border: 1px solid #ccc;
  transition: all .12s;
  &:hover:not(:disabled) { background: #f2f2f0; border-color: #999; }
  &:disabled { opacity: .3; cursor: not-allowed; }
  &--signal { background: var(--ef-signal); color: var(--ef-ink); border-color: var(--ef-signal); font-weight: 700; &:hover:not(:disabled) { background: #e6e100; border-color: #e6e100; } }
  &--dark { background: var(--ef-ink); color: var(--ef-paper); border-color: var(--ef-ink); font-weight: 700; &:hover:not(:disabled) { background: #333; } }
  &--text { background: none; border-color: transparent; color: #999; font-weight: 500; &:hover:not(:disabled) { color: #555; background: none; } }
}

/* ======== OR Divider ======== */
.ef-or {
  display: flex; align-items: center; gap: 16px;
  padding: 8px 0;
  &__line { flex: 1; height: 1px; background: #d4d2cc; }
  &__text { font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .12em; color: #bbb; }
}

/* ======== Dropzone ======== */
.ef-dropzone {
  border: 2px dashed #d4d2cc; padding: 36px 24px; text-align: center; background: #fafaf8;
  transition: all .15s;
  &.is-over { border-color: var(--ef-signal); background: #fffef5; }
  &__icon { display: block; font-size: 32px; font-weight: 900; font-family: "Space Grotesk", system-ui, sans-serif; color: #d8d6d0; letter-spacing: .12em; margin-bottom: 8px; }
  p { color: #aaa; font-size: 13px; margin: 0 0 16px; }
  &__btns { display: flex; gap: 8px; justify-content: center; }
  &__file { display: flex; align-items: center; gap: 12px; justify-content: center; flex-wrap: wrap; font-weight: 600; color: #333; font-size: 14px; }
  &__size { font-weight: 400; color: #999; font-size: 12px; }
  &__more { font-size: 11px; color: #999; }
}

/* ======== History ======== */
.ef-history { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; &__label { font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .1em; color: #bbb; } }
.ef-history-pill { display: inline-flex; align-items: center; }
.ef-pill {
  all: unset; cursor: pointer; padding: 3px 14px; font-size: 11px; color: #888; background: #fff; border: 1px solid #e0ded8;
  font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .04em;
  &:hover { border-color: #999; color: #444; }
  &__del {
    all: unset; cursor: pointer; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center;
    font-size: 12px; color: #ccc; margin-left: 2px;
    &:hover { color: #e04040; }
  }
}

/* ======== Canvas bar ======== */
.ef-canvas-bar { display: flex; align-items: center; margin-bottom: 10px; }

/* ======== Canvases ======== */
.ef-canvases { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 8px; }
.ef-canvas {
  cursor: pointer; display: block; max-width: 260px;
  padding: 12px; background: #fff; border: 1px solid #e4e2dc;
  transition: all .12s; position: relative;
  &:hover { border-color: #aaa; }
  &.is-on { border-color: var(--ef-ink); background: #fffef5; }
  &__check { position: absolute; top: 0; right: 0; width: 22px; height: 22px; background: #191919; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; line-height: 1; z-index: 3; }
  &__n { position: absolute; top: 8px; right: 10px; font-size: 22px; font-weight: 900; font-family: "Space Grotesk", system-ui, sans-serif; color: #e8e6e0; line-height: 1; }
  .is-on &__n { display: none; }
  &__thumbs { display: flex; gap: 4px; margin-bottom: 8px; min-height: 40px; flex-wrap: wrap; }
  &__name { font-size: 12px; color: #555; font-weight: 500; display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; }
}

/* ======== Lightbox ======== */
.ef-lightbox {
  position: fixed; inset: 0; z-index: 9999; background: rgba(6,6,6,.93);
  display: flex; align-items: center; justify-content: center;
  &__stage { max-width: 90vw; max-height: 86vh; overflow: hidden; display: flex; align-items: center; justify-content: center; }
  &__img { display: block; max-width: 90vw; max-height: 86vh; width: auto; height: auto; object-fit: contain; transition: transform .15s; }
  &__close { position: absolute; top: 20px; right: 24px; all: unset; cursor: pointer; font-size: 32px; color: rgba(255,255,255,.45); &:hover { color: #fff; } }
  &__nav { position: absolute; bottom: 24px; display: flex; gap: 6px; }
  &__dot {
    all: unset; cursor: pointer; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif; color: rgba(255,255,255,.35); border: 1px solid rgba(255,255,255,.15);
    &.is-on { color: var(--ef-ink); background: var(--ef-signal); border-color: var(--ef-signal); }
  }
}

/* ======== Clarification ======== */
.ef-wait { display: flex; align-items: center; gap: 10px; padding: 24px 0; font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .1em; color: #999; &__dot { width: 7px; height: 7px; background: var(--ef-signal); animation: ef-blink 1s infinite; } }
.ef-questions { display: flex; flex-direction: column; gap: 14px; }
.ef-q {
  display: flex; flex-direction: column; gap: 10px;
  &__head { display: flex; gap: 10px; align-items: flex-start; }
  &__n { font-size: 12px; font-weight: 900; font-family: "Space Grotesk", system-ui, sans-serif; color: #bbb; min-width: 28px; padding-top: 2px; }
  &__text { flex: 1; font-size: 14px; color: #333; line-height: 1.5; font-weight: 500; }
  textarea { width: 100%; }
}
.ef-check { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #666; cursor: pointer; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .04em; input { accent-color: var(--ef-signal); } }

/* ======== Pipeline ======== */
.ef-pipeline {
  display: flex; align-items: center; gap: 0; margin-bottom: 24px;
  background: #fff; padding: 10px 16px; border: 1px solid #e4e4de;
}
.ef-pipe {
  font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .1em; font-weight: 600;
  padding: 6px 14px; color: #ccc;
  &.is-on { color: var(--ef-ink); background: #fefde8; }
  &.is-past { color: #00a86b; }
  &__line { width: 28px; height: 1px; background: #d8d6d0; .is-past + & { background: #00a86b; } }
}

/* ======== Prose / Stream content ======== */
.ef-prose {
  background: #fff; border: 1px solid #e4e4de;
  padding: 20px 24px; margin-bottom: 16px;
  min-width: 0; max-width: 100%; overflow: hidden; box-sizing: border-box;
  &__label {
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .12em; color: #444; font-weight: 700;
    margin: 0 0 14px; padding-bottom: 10px; border-bottom: 2px solid #e8e6e0;
  }
  &__body {
    font-size: 14px; line-height: 1.8; color: #333;
    overflow: hidden;
    :deep(h1), :deep(h2), :deep(h3) { font-size: 1.15em; color: #191919; margin: 20px 0 10px; padding-bottom: 6px; border-bottom: 1px solid #eee; }
    :deep(h4), :deep(h5), :deep(h6) { font-size: 1em; color: #444; margin: 16px 0 6px; }
    :deep(code) { background: #f2f2f0; padding: 1px 6px; font-family: "IBM Plex Mono", monospace; font-size: .9em; color: #555; word-break: break-all; }
    :deep(pre) { background: #fafaf8; padding: 16px; border-left: 3px solid var(--ef-signal); overflow-x: auto; margin: 12px 0; white-space: pre-wrap; word-break: break-all; }
    :deep(table) { width: 100%; table-layout: fixed; border-collapse: collapse; margin: 14px 0; }
    :deep(th) { background: #f4f4f0; padding: 8px 10px; text-align: left; font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .04em; border-bottom: 2px solid var(--ef-ink); color: #444; word-break: break-word; }
    :deep(td) { padding: 8px 10px; border-bottom: 1px solid #e8e6e0; word-break: break-word; }
    :deep(tr:hover td) { background: #fafaf8; }
    :deep(ul), :deep(ol) { padding-left: 20px; margin: 10px 0; }
    :deep(li) { margin-bottom: 6px; }
    :deep(p) { margin: 10px 0; }
    :deep(blockquote) { margin: 14px 0; padding: 10px 16px; border-left: 3px solid #ddd; background: #fafaf8; color: #666; }
  }
  &--review {
    border-left: 3px solid #e6a23c;
    .ef-prose__label { color: #b8860b; border-bottom-color: rgba(230,162,60,.3); }
  }
  &--final {
    border-left: 3px solid #00a86b;
    .ef-prose__label { color: #00a86b; border-bottom-color: rgba(0,168,107,.3); }
  }
}

/* ======== Modal ======== */
.ef-modal {
  position: fixed; inset: 0; z-index: 9999; background: rgba(4,4,4,.78);
  display: flex; align-items: center; justify-content: center; padding: 20px;
  &__box { background: #fff; width: 100%; max-width: 680px; max-height: 85vh; overflow-y: auto; }
  &__bar { display: flex; align-items: center; gap: 10px; padding: 12px 16px; background: var(--ef-ink); color: #fff; }
  &__idx { font-size: 22px; font-weight: 900; font-family: "Space Grotesk", system-ui, sans-serif; color: rgba(255,255,255,.18); }
  &__x { all: unset; cursor: pointer; font-size: 22px; color: rgba(255,255,255,.40); margin-left: auto; &:hover { color: #fff; } }
  &__body { padding: 24px; h2 { font-size: 1.1rem; color: #191919; margin: 0 0 4px; } }
  &__desc { font-size: 13px; color: #999; margin: 0 0 20px; }
}
.ef-guide-list { display: flex; flex-direction: column; gap: 4px; margin-bottom: 20px; }
.ef-guide-item {
  display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border: 1px solid #e8e6e0;
  &__label { font-size: 12px; color: #888; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .04em; }
  &__val { font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .04em; display: flex; align-items: center; gap: 6px; }
  &__dot { width: 5px; height: 5px; display: inline-block; }
  .is-ok { color: #00a86b; .ef-guide-item__dot { background: var(--ef-state); } }
  .is-warn { color: #b8860b; .ef-guide-item__dot { background: var(--ef-signal); } }
  .is-fail { color: #c03939; .ef-guide-item__dot { background: #e04040; } }
}

/* ======== Dock ======== */
.ef-dock {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 20;
  height: 30px; background: var(--ef-ink);
  display: flex; align-items: center; justify-content: center; gap: 10px;
  font-family: "Space Grotesk", system-ui, sans-serif; font-size: 10px;
  text-transform: uppercase; letter-spacing: .12em; color: rgba(255,255,255,.28);
  &__div { width: 1px; height: 12px; background: rgba(255,255,255,.10); }
  &__dot { width: 6px; height: 6px; background: rgba(255,255,255,.12); &.is-live { background: var(--ef-state); } }
}

/* ======== Responsive ======== */
@media (max-width: 1024px) { .ef-stage { padding: 0 16px 80px; } .ef-mode-row { flex-direction: column; } .ef-section { padding-left: 48px; &__num { font-size: 28px; left: 4px; } } }
@media (max-width: 768px) {
  .ef-stage { padding: 0 12px 80px; }
  .ef-identity { flex-wrap: wrap; &__right { width: 100%; flex-direction: row; justify-content: space-between; } &__title { font-size: 1.5rem; } &__wedge { height: 40px; width: 10px; } }
  .ef-section { padding-left: 36px; &__num { font-size: 22px; left: 2px; top: 26px; } }
  .ef-fields { flex-direction: column; }
  .ef-field { min-width: 0; &--wide { min-width: 0; } }
  .ef-pipeline { flex-wrap: wrap; gap: 4px; }
}
@media (prefers-reduced-motion: reduce) { .ef-blink { animation: none; } }
</style>

<style>
/* 全局样式：确保弹窗不受任何容器限制 */
.modal-overlay {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  max-width: none !important;
  max-height: none !important;
  background: rgba(15, 23, 42, 0.6) !important;
  backdrop-filter: blur(4px);
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  z-index: 9999 !important;
  padding: 20px;
  margin: 0 !important;
  opacity: 1 !important;
  box-sizing: border-box !important;
}

.guide-config-modal {
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%) !important;
  border-radius: 24px;
  padding: 36px;
  max-width: 850px !important;
  width: 100% !important;
  min-width: 300px !important;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(226, 232, 240, 0.8);
  position: relative;
  flex-shrink: 0;
  margin: auto;
  opacity: 1 !important;
  box-sizing: border-box !important;
}

/* 全局按钮样式 */
.guide-actions {
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  gap: 12px;
  margin-top: 30px;
  width: 100%;
}

.guide-actions button {
  flex: none !important;
  width: 240px !important;
  height: 50px !important;
  padding: 0 24px !important;
  border-radius: 0;
  font-size: 0.95rem;
  font-weight: 600;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center;
  white-space: nowrap;
  opacity: 1 !important;
  box-sizing: border-box !important;
  cursor: pointer;
}

.guide-actions .generate-manual-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
  color: white !important;
  border: 2px solid transparent !important;
  box-shadow: 0 2px 10px rgba(102, 126, 234, 0.3);
}

.guide-actions .skip-action {
  font-size: 0.85rem;
  color: #94a3b8;
  cursor: pointer;
  text-decoration: none;
  padding: 4px 8px;
  transition: color 0.3s;
}

.guide-actions .skip-action:hover {
  color: #64748b;
  text-decoration: underline;
}

/* ========== 多模态模式选择 ========== */
.multimodal-toggle {
  margin: 16px 0;
  padding: 14px 16px;
  background: linear-gradient(135deg, #f0f4ff 0%, #e8f0fe 100%);
  border: 1px solid #c8d6ff;
  border-radius: 10px;
}
.multimodal-checkbox {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
  font-size: 0.95rem;
}
.multimodal-checkbox input[type="checkbox"] {
  margin-top: 3px;
  width: 18px;
  height: 18px;
  accent-color: #4f46e5;
  cursor: pointer;
}
.multimodal-label {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.multimodal-hint {
  font-size: 0.8rem;
  color: #666;
  font-weight: normal;
  line-height: 1.4;
}
.multimodal-info {
  margin-top: 10px;
  padding: 8px 12px;
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 6px;
  font-size: 0.83rem;
}
.info-badge {
  color: #856404;
  line-height: 1.5;
}
</style>