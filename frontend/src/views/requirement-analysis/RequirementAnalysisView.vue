<template>
  <div class="requirement-analysis">
    <div class="page-header">
      <h1>{{ $t('requirementAnalysis.title') }}</h1>
      <p>{{ $t('requirementAnalysis.subtitle') }}</p>
    </div>

    <!-- 配置引导弹出窗口 -->
    <div v-if="showConfigGuide && !checkingConfig" class="modal-overlay" @click.self="showConfigGuide = false" :key="modalKey">
      <div class="guide-config-modal">
      <div class="guide-header">
        <svg class="guide-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
          <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="#f59e0b"/>
          <path d="M464 336a48 48 0 1 0 96 0 48 48 0 1 0-96 0zm72 112h-48c-4.4 0-8 3.6-8 8v272c0 4.4 3.6 8 8 8h48c4.4 0 8-3.6 8-8V456c0-4.4-3.6-8-8-8z" fill="#f59e0b"/>
        </svg>
        <div class="guide-title">
          <h2>{{ $t('configGuide.title') }}</h2>
          <p>{{ $t('configGuide.subtitle') }}</p>
        </div>
      </div>

      <div class="config-groups">
        <!-- 模型配置行 -->
        <div class="config-group">
          <div class="group-label">{{ $t('configGuide.modelConfig') }}</div>
          <div class="config-items-row">
            <div class="config-item-inline" :class="getConfigItemClass('writer_model')">
              <span class="status-symbol" v-html="getStatusSymbol('writer_model')"></span>
              <span class="config-label">{{ $t('configGuide.caseWriter') }}</span>
              <span class="config-name" v-if="configStatus.writer_model.name">{{ configStatus.writer_model.name }}</span>
              <span class="status-text" v-if="!configStatus.writer_model.configured">{{ $t('configGuide.unconfigured') }}</span>
              <span class="status-text warning" v-else-if="!configStatus.writer_model.enabled">{{ $t('configGuide.disabled') }}</span>
            </div>

            <div class="config-item-inline" :class="getConfigItemClass('reviewer_model')">
              <span class="status-symbol" v-html="getStatusSymbol('reviewer_model')"></span>
              <span class="config-label">{{ $t('configGuide.caseReviewer') }}</span>
              <span class="config-name" v-if="configStatus.reviewer_model.name">{{ configStatus.reviewer_model.name }}</span>
              <span class="status-text" v-if="!configStatus.reviewer_model.configured">{{ $t('configGuide.unconfigured') }}</span>
              <span class="status-text warning" v-else-if="!configStatus.reviewer_model.enabled">{{ $t('configGuide.disabled') }}</span>
            </div>
          </div>
        </div>

        <!-- 提示词配置行 -->
        <div class="config-group">
          <div class="group-label">{{ $t('configGuide.promptConfig') }}</div>
          <div class="config-items-row">
            <div class="config-item-inline" :class="getConfigItemClass('writer_prompt')">
              <span class="status-symbol" v-html="getStatusSymbol('writer_prompt')"></span>
              <span class="config-label">{{ $t('configGuide.caseWriter') }}</span>
              <span class="config-name" v-if="configStatus.writer_prompt.name">{{ configStatus.writer_prompt.name }}</span>
              <span class="status-text" v-if="!configStatus.writer_prompt.configured">{{ $t('configGuide.unconfigured') }}</span>
              <span class="status-text warning" v-else-if="!configStatus.writer_prompt.enabled">{{ $t('configGuide.disabled') }}</span>
            </div>

            <div class="config-item-inline" :class="getConfigItemClass('reviewer_prompt')">
              <span class="status-symbol" v-html="getStatusSymbol('reviewer_prompt')"></span>
              <span class="config-label">{{ $t('configGuide.caseReviewer') }}</span>
              <span class="config-name" v-if="configStatus.reviewer_prompt.name">{{ configStatus.reviewer_prompt.name }}</span>
              <span class="status-text" v-if="!configStatus.reviewer_prompt.configured">{{ $t('configGuide.unconfigured') }}</span>
              <span class="status-text warning" v-else-if="!configStatus.reviewer_prompt.enabled">{{ $t('configGuide.disabled') }}</span>
            </div>
          </div>
        </div>

        <!-- 生成行为配置行 -->
        <div class="config-group">
          <div class="group-label">{{ $t('configGuide.generationConfig') }}</div>
          <div class="config-items-row">
            <div class="config-item-inline" :class="getConfigItemClass('generation_config')">
              <span class="status-symbol" v-html="getStatusSymbol('generation_config')"></span>
              <span class="config-label">{{ $t('configGuide.generationSettings') }}</span>
              <span class="config-name" v-if="configStatus.generation_config && configStatus.generation_config.name">{{ configStatus.generation_config.name }}</span>
              <span class="status-text" v-if="!configStatus.generation_config || !configStatus.generation_config.configured">{{ $t('configGuide.unconfigured') }}</span>
            </div>
          </div>
        </div>
      </div>

        <div class="guide-actions">
          <button class="generate-manual-btn" @click="goToConfig">
            {{ $t('configGuide.goToConfig') }}
          </button>
          <div class="skip-action" @click="showConfigGuide = false">
            {{ $t('configGuide.configureLater') }}
          </div>
        </div>
      </div>
    </div>

    <!-- 输出模式选择器 - 全局设置 -->
    <div class="output-mode-section" v-if="!isGenerating && !showResults">
      <div class="output-mode-card">
        <h3>{{ $t('requirementAnalysis.outputModeTitle') }}</h3>
        <p class="mode-section-desc">{{ $t('requirementAnalysis.outputModeDesc') }}</p>
        <div class="output-mode-selector">
          <label class="mode-option" :class="{ active: globalOutputMode === 'stream' }">
            <input type="radio" v-model="globalOutputMode" value="stream">
            <div class="mode-content">
              <div class="mode-title">{{ $t('requirementAnalysis.realtimeStream') }}</div>
              <div class="mode-desc">{{ $t('requirementAnalysis.realtimeStreamDesc') }}</div>
            </div>
          </label>
          <label class="mode-option" :class="{ active: globalOutputMode === 'complete' }">
            <input type="radio" v-model="globalOutputMode" value="complete">
            <div class="mode-content">
              <div class="mode-title">{{ $t('requirementAnalysis.completeOutput') }}</div>
              <div class="mode-desc">{{ $t('requirementAnalysis.completeOutputDesc') }}</div>
            </div>
          </label>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- 手动输入需求描述区域 -->
      <div class="manual-input-section" v-if="!isGenerating && !showResults && !showClarificationPanel">
        <div class="manual-input-card">
          <div class="tab-bar">
            <button class="tab-btn" :class="{ active: manualTab === 'modao' }" @click="manualTab = 'modao'">
              🔗 从墨刀导入
            </button>
            <button class="tab-btn" :class="{ active: manualTab === 'input' }" @click="manualTab = 'input'">
              ✏️ 手动输入
            </button>
          </div>

          <!-- Tab: 手动输入 -->
          <div v-if="manualTab === 'input'">
          <div class="input-form">
            <div class="form-group">
              <label>{{ $t('requirementAnalysis.requirementTitle') }} <span class="required">*</span></label>
              <input
                v-model="manualInput.title"
                type="text"
                class="form-input"
                :placeholder="$t('requirementAnalysis.titlePlaceholder')">
            </div>

            <div class="form-group">
              <label>{{ $t('requirementAnalysis.requirementDescription') }} <span class="required">*</span></label>
              <textarea
                v-model="manualInput.description"
                class="form-textarea"
                rows="8"
                :placeholder="$t('requirementAnalysis.descriptionPlaceholder')"></textarea>
              <div class="char-count">{{ manualInput.description.length }}/2000</div>
            </div>

            <div class="form-group">
              <label>{{ $t('requirementAnalysis.associatedProject') }}</label>
              <select v-model="manualInput.selectedProject" class="form-select" @change="onManualProjectChange">
                <option value="">{{ $t('requirementAnalysis.selectProject') }}</option>
                <option v-for="project in projects" :key="project.id" :value="project.id">
                  {{ project.name }}
                </option>
              </select>
            </div>

            <div class="form-group" v-if="manualInput.selectedProject">
              <label>{{ $t('requirementAnalysis.associatedVersions') }}</label>
              <select v-model="manualInput.selectedVersionIds" class="form-select" multiple size="4" @change="loadVersionModules(manualInput.selectedVersionIds, 'manual')">
                <option v-for="version in projectVersions" :key="version.id" :value="version.id">
                  {{ version.name }}{{ version.is_baseline ? ' (' + $t('testcase.baseline') + ')' : '' }}
                </option>
              </select>
              <div class="select-hint">{{ $t('requirementAnalysis.multiSelectTip') }}</div>
            </div>

            <div class="form-group" v-if="manualInput.selectedVersionIds && manualInput.selectedVersionIds.length > 0">
              <label>{{ $t('requirementAnalysis.functionModule') }}</label>
              <div style="display: flex; gap: 6px;">
                <select v-model="manualInput.selectedModuleId" class="form-select" style="flex: 1;">
                  <option value="">{{ $t('requirementAnalysis.noModule') }}</option>
                  <option v-for="mod in manualModules" :key="mod.id" :value="mod.id">{{ mod.name }}</option>
                </select>
                <button class="quick-add-btn" @click="quickAddModule('manual')" :disabled="!manualInput.selectedVersionIds || manualInput.selectedVersionIds.length === 0" type="button">+</button>
              </div>
            </div>

            <button
              class="generate-manual-btn"
              @click="generateFromManualInput"
              :disabled="!canGenerateManual || isGenerating">
              <span v-if="isGenerating">{{ $t('requirementAnalysis.generating') }}</span>
              <span v-else>{{ $t('requirementAnalysis.generateButton') }}</span>
            </button>
          </div>
          </div>
          <!-- /Tab: 手动输入 -->

          <!-- Tab: AI文档提取 -->
          <div v-if="manualTab === 'extract'" class="extract-tab">
            <!-- 第一步：选项目（用于带知识背景） -->
            <div class="form-group">
              <label>{{ $t('requirementAnalysis.associatedProject') }}</label>
              <select v-model="manualInput.selectedProject" class="form-select" @change="onManualProjectChange">
                <option value="">{{ $t('requirementAnalysis.selectProject') }}</option>
                <option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }}</option>
              </select>
            </div>

            <div class="upload-area"
                 @dragover.prevent
                 @drop="handleExtractDrop"
                 :class="{ 'drag-over': isExtractDragOver }"
                 @dragenter="isExtractDragOver = true"
                 @dragleave="isExtractDragOver = false">
              <div v-if="!extractFile" class="upload-placeholder">
                <i class="upload-icon">📁</i>
                <p>{{ $t('requirementAnalysis.dragDropText') }}</p>
                <p class="upload-hint">{{ $t('requirementAnalysis.supportedFormats') }}</p>
                <input type="file" ref="extractFileInput" @change="handleExtractFileSelect" accept=".pdf,.doc,.docx,.txt,.md" style="display: none;">
                <button class="select-file-btn" @click="$refs.extractFileInput.click()">{{ $t('requirementAnalysis.selectFile') }}</button>
              </div>
              <div v-else class="file-selected">
                <div class="file-info">
                  <i class="file-icon">📄</i>
                  <div class="file-details">
                    <p class="file-name">{{ extractFile.name }}</p>
                    <p class="file-size">{{ formatFileSize(extractFile.size) }}</p>
                  </div>
                  <button class="remove-file" @click="removeExtractFile">❌</button>
                </div>
              </div>
            </div>

            <button class="generate-btn" @click="extractDocument" :disabled="!extractFile || isExtracting" style="margin-top: 12px;">
              <span v-if="isExtracting">🤖 {{ $t('requirementAnalysis.extracting') }}</span>
              <span v-else>🤖 {{ $t('requirementAnalysis.extractDocument') }}</span>
            </button>

            <div v-if="extractedMarkdown" class="extracted-content" style="margin-top: 16px;">
              <label>{{ $t('requirementAnalysis.extractedContent') }}</label>
              <textarea
                v-model="extractedMarkdown"
                class="form-textarea"
                rows="15"
                :placeholder="$t('requirementAnalysis.extractedContentPlaceholder')"></textarea>
            </div>

            <!-- 生成前关联设置 -->
            <div v-if="extractedMarkdown" style="margin-top: 12px;">
              <div class="form-group">
                <label>{{ $t('requirementAnalysis.associatedProject') }}（{{ $t('requirementAnalysis.forGeneration') }}）</label>
                <select v-model="manualInput.selectedProject" class="form-select" @change="onManualProjectChange">
                  <option value="">{{ $t('requirementAnalysis.selectProject') }}</option>
                  <option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }}</option>
                </select>
              </div>
              <div class="form-group" v-if="manualInput.selectedProject">
                <label>{{ $t('requirementAnalysis.associatedVersions') }}</label>
                <select v-model="manualInput.selectedVersionIds" class="form-select" multiple size="3" @change="loadVersionModules(manualInput.selectedVersionIds, 'manual')">
                  <option v-for="version in projectVersions" :key="version.id" :value="version.id">{{ version.name }}</option>
                </select>
              </div>
              <div class="form-group" v-if="manualInput.selectedVersionIds && manualInput.selectedVersionIds.length > 0">
                <label>{{ $t('requirementAnalysis.functionModule') }}</label>
                <div style="display: flex; gap: 6px;">
                  <select v-model="manualInput.selectedModuleId" class="form-select" style="flex: 1;">
                    <option value="">{{ $t('requirementAnalysis.noModule') }}</option>
                    <option v-for="mod in manualModules" :key="mod.id" :value="mod.id">{{ mod.name }}</option>
                  </select>
                  <button class="quick-add-btn" @click="quickAddModule('manual')" :disabled="!manualInput.selectedVersionIds || manualInput.selectedVersionIds.length === 0" type="button">+</button>
                </div>
              </div>
            </div>

            <button
              class="generate-manual-btn"
              @click="generateFromExtracted"
              :disabled="!extractedMarkdown || isGenerating"
              style="margin-top: 12px;">
              <span v-if="isGenerating">{{ $t('requirementAnalysis.generating') }}</span>
              <span v-else>{{ $t('requirementAnalysis.generateButton') }}</span>
            </button>
          </div>
          <!-- /Tab: AI文档提取 -->

          <!-- Tab: 从墨刀导入 -->
          <div v-if="manualTab === 'modao'" class="modao-tab">
            <!-- 历史导入（最顶部，显眼位置） -->
            <div style="margin-bottom: 14px; padding: 10px 12px; background: #fafbfc; border: 1px solid #e4e7ed; border-radius: 6px;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 13px; font-weight: 600; color: #303133;">📋 历史导入</span>
                <span style="font-size: 11px; color: #c0c4cc;">点选恢复 | × 删除</span>
              </div>
              <div v-if="modaoHistory.length > 0" style="display: flex; gap: 6px; flex-wrap: wrap;">
                <span v-for="(h, i) in modaoHistory" :key="i"
                  class="history-pill"
                  :class="{ active: h.url === modaoUrl }"
                  @click="loadModaoHistory(i)">
                  <span class="history-pill-name">{{ h.title || h.url?.substring(0, 35) }}</span>
                  <span class="history-pill-meta">{{ h.canvas_count || 0 }}画布</span>
                  <span @click.stop="deleteModaoHistory(i)" class="history-pill-del">×</span>
                </span>
              </div>
              <div v-else style="font-size: 12px; color: #c0c4cc;">暂无历史记录，导入需求后自动保存</div>
            </div>

            <div class="form-group">
              <label>关联项目</label>
              <select v-model="manualInput.selectedProject" class="form-select" @change="onManualProjectChange">
                <option value="">{{ $t('requirementAnalysis.selectProject') }}</option>
                <option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }}</option>
              </select>
            </div>

            <div class="form-group" v-if="manualInput.selectedProject">
              <label>{{ $t('requirementAnalysis.associatedVersions') }}</label>
              <select v-model="manualInput.selectedVersionIds" class="form-select" multiple size="4" @change="loadVersionModules(manualInput.selectedVersionIds, 'manual')">
                <option v-for="version in projectVersions" :key="version.id" :value="version.id">
                  {{ version.name }}{{ version.is_baseline ? ' (' + $t('testcase.baseline') + ')' : '' }}
                </option>
              </select>
              <div class="select-hint">{{ $t('requirementAnalysis.multiSelectTip') }}</div>
            </div>

            <div class="form-group" v-if="manualInput.selectedVersionIds && manualInput.selectedVersionIds.length > 0">
              <label>{{ $t('requirementAnalysis.functionModule') }}</label>
              <select v-model="manualInput.selectedModuleId" class="form-select" style="flex: 1;">
                <option value="">{{ $t('testcase.selectModule') }}</option>
                <option v-for="m in versionModules" :key="m.id" :value="m.id">
                  {{ m.name }}
                </option>
              </select>
            </div>

            <div class="form-group">
              <label>墨刀页面 URL</label>
              <input v-model="modaoUrl" type="text" class="form-input" placeholder="https://modao.cc/proto/xxx/sharing?view_mode=read_only">
            </div>

            <div class="form-group">
              <label>Cookie</label>
              <input v-model="modaoToken" type="password" class="form-input" placeholder="F12 → Network → 点任意请求 → Request Headers → 复制 Cookie 整行">
              <div class="select-hint">需包含 _imock_session（HttpOnly），F12 → Network → 请求头 → Cookie 整行复制</div>
            </div>

            <button class="select-file-btn" @click="importFromModao" :disabled="!modaoUrl || !modaoToken || isImportingModao" style="width:100%; margin-top: 8px;">
              <span v-if="isImportingModao">⏳ 导入中 {{ _importProgress }}%...</span>
              <span v-else>🔗 从墨刀导入需求</span>
            </button>

            <!-- 画布列表 -->
            <div v-if="modaoCanvases.length > 0" style="margin-top: 12px;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <label style="font-weight: 600; color: #2c3e50; font-size: 13px;">
                  画布列表 ({{ selectedCanvasCount }}/{{ modaoCanvases.length }})
                </label>
                <div>
                  <button class="select-file-btn" style="font-size: 11px; padding: 2px 8px; margin-right: 4px;"
                    @click="selectAllCanvases">{{ selectedCanvasCount === modaoCanvases.length ? '取消全选' : '全选' }}</button>
                  <button class="select-file-btn" style="font-size: 11px; padding: 2px 8px; color: #f56c6c;"
                    @click="deleteSelectedCanvases" :disabled="selectedCanvasCount === 0">删除选中</button>
                </div>
              </div>
              <div style="max-height: 300px; overflow-y: auto; border: 1px solid #e4e7ed; border-radius: 4px;">
                <div v-for="(c, i) in modaoCanvases" :key="i"
                     style="display: flex; align-items: center; padding: 6px 10px; border-bottom: 1px solid #f2f3f5;"
                     :style="{ background: c.selected ? '#ecf5ff' : '#fff' }">
                  <input type="checkbox" v-model="c.selected" style="margin-right: 8px;">
                  <template v-if="c.screenshots.length > 0">
                    <img v-for="(s, si) in c.screenshots" :key="si" :src="s.url"
                         style="width: 40px; height: auto; border-radius: 2px; border: 1px solid #ddd; margin-right: 3px;"
                         @click.stop="previewCanvas = c; previewIdx = si"
                         @error="s.url = ''">
                  </template>
                  <span v-else style="font-size: 11px; color: #c0c4cc; margin-right: 6px;">🖼️</span>
                  <span style="flex:1; font-size: 13px; margin-left: 4px;">{{ c.name }}</span>
                  <button class="replace-btn" title="替换截图" @click.stop="triggerReplace(i)">+</button>
                  <button v-if="c.screenshots.length > 0" class="replace-btn" title="清空截图" @click.stop="clearScreenshots(i)" style="margin-left: 2px;">✕</button>
                  <input type="file" accept="image/png,image/jpeg" style="display:none"
                         :ref="el => { if (el) replaceInputs[i] = el }"
                         @change="e => onAddScreenshot(i, e)">
                </div>
              </div>
            </div>

            <!-- 生成按钮 -->
            <div v-if="modaoCanvases.length > 0" style="margin-top: 10px;">
              <button class="generate-btn" @click="generateFromModao" :disabled="isGenerating || selectedCanvasCount === 0" style="width:100%;">
                <span v-if="isGenerating">🤖 生成中...</span>
                <span v-else>🤖 生成用例 ({{ selectedCanvasCount }}画布)（澄清→初版→评审→终版）</span>
              </button>
            </div>

            <!-- 截图预览 lightbox -->
            <div v-if="previewCanvas" class="modao-lightbox" @click="closePreview" @wheel.prevent="onPreviewWheel">
              <button v-if="previewCanvas.screenshots.length > 1"
                      class="preview-nav preview-prev" @click.stop="previewIdx = (previewIdx - 1 + previewCanvas.screenshots.length) % previewCanvas.screenshots.length">◀</button>
              <img v-if="previewCanvas.screenshots[previewIdx]"
                   :src="previewCanvas.screenshots[previewIdx].url"
                   :style="{ maxWidth: '90vw', maxHeight: '90vh', transform: 'scale(' + previewZoom + ')', boxShadow: '0 4px 20px rgba(0,0,0,0.3)' }"
                   @click.stop>
              <button v-if="previewCanvas.screenshots.length > 1"
                      class="preview-nav preview-next" @click.stop="previewIdx = (previewIdx + 1) % previewCanvas.screenshots.length">▶</button>
              <div style="color: #fff; margin-top: 10px; text-align: center;">
                {{ previewCanvas.name }}
                <span v-if="previewCanvas.screenshots[previewIdx]">({{ previewCanvas.screenshots[previewIdx].width }}×{{ previewCanvas.screenshots[previewIdx].height }})</span>
                — {{ Math.round(previewZoom * 100) }}% — {{ previewIdx + 1 }}/{{ previewCanvas.screenshots.length }}
                <button class="replace-btn" style="margin-left: 8px; opacity: 1; color: #fff; border-color: #666;"
                        @click.stop="triggerReplace(modaoCanvases.indexOf(previewCanvas))">+ 添加截图</button>
              </div>
            </div>
          </div>
          <!-- /Tab: 从墨刀导入 -->
        </div>
      </div>

      <!-- 分隔线 -->
      <div class="divider" v-if="!isGenerating && !showResults && !showClarificationPanel">
        <span>{{ $t('requirementAnalysis.dividerOr') }}</span>
      </div>

      <!-- 文档上传区域 -->
      <div class="upload-section" v-if="!isGenerating && !showResults && !showClarificationPanel">
        <div class="upload-card">
          <h2>{{ $t('requirementAnalysis.uploadTitle') }}</h2>
          <div class="upload-area"
               @dragover.prevent
               @drop="handleDrop"
               :class="{ 'drag-over': isDragOver }"
               @dragenter="isDragOver = true"
               @dragleave="isDragOver = false">
            <div v-if="!selectedFile" class="upload-placeholder">
              <i class="upload-icon">📁</i>
              <p>{{ $t('requirementAnalysis.dragDropText') }}</p>
              <p class="upload-hint">{{ $t('requirementAnalysis.supportedFormats') }}</p>
              <input
                type="file"
                ref="fileInput"
                @change="handleFileSelect"
                accept=".pdf,.doc,.docx,.txt,.md,.png,.jpg,.jpeg,.webp"
                multiple
                style="display: none;">
              <input
                type="file"
                ref="folderInput"
                @change="handleFolderSelect"
                webkitdirectory
                style="display: none;">
              <div class="upload-btns">
                <button class="select-file-btn" @click="$refs.fileInput.click()">
                  {{ $t('requirementAnalysis.selectFile') }}
                </button>
                <button class="select-file-btn" @click="$refs.folderInput.click()">
                  📂 {{ $t('requirementAnalysis.selectFolder') }}
                </button>
              </div>
            </div>

            <div v-else class="file-selected">
              <div class="file-info" @click="selectedFiles.length > 1 && (showFileList = !showFileList)" :class="{ 'clickable': selectedFiles.length > 1 }">
                <i class="file-icon">📄</i>
                <div class="file-details">
                  <p class="file-name">{{ selectedFile.name }}</p>
                  <p class="file-size">
                    {{ formatFileSize(selectedFile.size) }}
                    <span v-if="selectedFiles.length > 1" class="multi-hint">
                      · 共 {{ selectedFiles.length }} 个文件
                      <span class="expand-arrow">{{ showFileList ? '▾' : '▸' }}</span>
                    </span>
                  </p>
                </div>
                <button class="remove-file" @click.stop="removeFile">❌</button>
              </div>
              <!-- 展开的文件列表 -->
              <div v-if="showFileList && selectedFiles.length > 1" class="file-list-expanded">
                <div v-for="(f, i) in selectedFiles" :key="i" class="file-list-item" :class="{ 'file-list-item-active': f === selectedFile }" @click="selectedFile = f">
                  <span class="fli-name">{{ f.webkitRelativePath || f.name }}</span>
                  <span class="fli-size">{{ formatFileSize(f.size) }}</span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="selectedFile" class="document-info">
            <div class="form-group">
              <label>{{ $t('requirementAnalysis.documentTitle') }}</label>
              <input
                v-model="documentTitle"
                type="text"
                class="form-input"
                :placeholder="$t('requirementAnalysis.documentPlaceholder')">
            </div>

            <div class="form-group">
              <label>{{ $t('requirementAnalysis.associatedProject') }}</label>
              <select v-model="selectedProject" class="form-select" @change="onDocProjectChange">
                <option value="">{{ $t('requirementAnalysis.selectProject') }}</option>
                <option v-for="project in projects" :key="project.id" :value="project.id">
                  {{ project.name }}
                </option>
              </select>
            </div>

            <div class="form-group" v-if="selectedProject">
              <label>{{ $t('requirementAnalysis.associatedVersions') }}</label>
              <select v-model="selectedVersionIds" class="form-select" multiple size="4" @change="loadVersionModules(selectedVersionIds, 'doc')">
                <option v-for="version in projectVersions" :key="version.id" :value="version.id">
                  {{ version.name }}{{ version.is_baseline ? ' (' + $t('testcase.baseline') + ')' : '' }}
                </option>
              </select>
              <div class="select-hint">{{ $t('requirementAnalysis.multiSelectTip') }}</div>
            </div>

            <div class="form-group" v-if="selectedVersionIds && selectedVersionIds.length > 0">
              <label>{{ $t('requirementAnalysis.functionModule') }}</label>
              <div style="display: flex; gap: 6px;">
                <select v-model="docSelectedModuleId" class="form-select" style="flex: 1;">
                  <option value="">{{ $t('requirementAnalysis.noModule') }}</option>
                  <option v-for="mod in docModules" :key="mod.id" :value="mod.id">{{ mod.name }}</option>
                </select>
                <button class="quick-add-btn" @click="quickAddModule('doc')" :disabled="!selectedVersionIds || selectedVersionIds.length === 0" type="button">+</button>
              </div>
            </div>

            <!-- 多模态模式选择 -->
            <div v-if="isMultimodalFile" class="multimodal-toggle">
              <label class="multimodal-checkbox">
                <input
                  type="checkbox"
                  v-model="enableMultimodal"
                  :disabled="isGenerating">
                <span class="multimodal-label">
                  <strong>多模态生成模式</strong>
                  <span class="multimodal-hint">将文档截图或直接上传的图片（流程图、原型图、UI设计稿）发送给视觉模型分析，生成更精准的测试用例</span>
                </span>
              </label>
              <div v-if="enableMultimodal" class="multimodal-info">
                <span class="info-badge">⚠ 需先配置硅基流动的视觉模型（如 Qwen2-VL），并勾选「支持多模态」后设为 writer 角色</span>
              </div>
            </div>

            <button
              class="generate-btn"
              @click="generateFromDocument"
              :disabled="!documentTitle || isGenerating">
              <span v-if="isGenerating">{{ $t('requirementAnalysis.generating') }}</span>
              <span v-else>{{ $t('requirementAnalysis.generateButton') }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 需求澄清面板 -->
      <div v-if="showClarificationPanel" class="clarification-section">
        <div class="clarification-card">
          <h2>{{ $t('requirementAnalysis.clarificationTitle') }}</h2>
          <p class="clarification-subtitle">{{ $t('requirementAnalysis.clarificationSubtitle') }}</p>

          <div v-if="isClarifying" class="clarifying-loading">
            <span class="loading-spinner">⏳</span>
            <span>{{ $t('requirementAnalysis.clarifying') }}</span>
          </div>

          <div v-else-if="clarificationQuestions.length === 0" class="clarification-empty">
            <p>✅ {{ $t('requirementAnalysis.clarificationNoQuestions') }}</p>
          </div>

          <div v-else class="clarification-questions">
            <div
              v-for="q in clarificationQuestions"
              :key="q.id"
              class="clarification-question-item">
              <div class="question-text">
                <span class="question-number">{{ $t('requirementAnalysis.clarificationQuestionLabel', { id: q.id }) }}</span>
                {{ q.question }}
              </div>
              <textarea
                v-model="clarificationAnswers[q.id]"
                class="question-answer-input"
                :placeholder="$t('requirementAnalysis.clarificationAnswerPlaceholder')"
                rows="2"></textarea>
            </div>
          </div>

          <div class="clarification-actions" v-if="!isClarifying">
            <button class="skip-clarify-btn" @click="skipClarification">
              {{ $t('requirementAnalysis.clarificationSkip') }}
            </button>
            <button class="confirm-clarify-btn" @click="confirmWithClarification">
              {{ $t('requirementAnalysis.clarificationConfirm') }}
            </button>
          </div>
        </div>
      </div>

      <!-- 生成进度和结果 -->
      <div v-if="isGenerating || showResults" class="generation-progress">
        <div class="progress-card">
          <h3>
            {{ $t('requirementAnalysis.aiGeneratingTitle') }}
            <span class="current-mode-badge">
              ({{ globalOutputMode === 'stream' ? $t('requirementAnalysis.realtimeStream') : $t('requirementAnalysis.completeOutput') }})
            </span>
          </h3>
          <div class="progress-info">
            <div class="progress-item">
              <span class="label">{{ $t('requirementAnalysis.taskId') }}</span>
              <span class="value">{{ currentTaskId || $t('requirementAnalysis.preparing') }}</span>
            </div>
            <div class="progress-item">
              <span class="label">{{ $t('requirementAnalysis.currentStatus') }}</span>
              <span class="value">{{ showResults ? $t('requirementAnalysis.generationComplete') : progressText }}</span>
            </div>
          </div>

          <!-- 流式内容实时显示区域 -->
          <div v-if="streamedContent" class="stream-content-display">
            <div class="stream-header">
              <span class="stream-title">{{ $t('requirementAnalysis.realtimeGeneratedContent') }}</span>
              <span class="stream-status">{{ $t('requirementAnalysis.characters', { count: streamedContent.length }) }}</span>
            </div>
            <div class="stream-content" v-html="formatMarkdown(streamedContent)"></div>
          </div>

          <!-- 评审内容显示区域 -->
          <div v-if="streamedReviewContent" class="stream-content-display" style="margin-top: 15px;">
            <div class="stream-header">
              <span class="stream-title">{{ $t('requirementAnalysis.aiReviewComments') }}</span>
              <span class="stream-status">{{ $t('requirementAnalysis.characters', { count: streamedReviewContent.length }) }}</span>
            </div>
            <div class="stream-content" v-html="formatMarkdown(streamedReviewContent)"></div>
          </div>

          <!-- 最终版用例显示区域 -->
          <div v-if="finalTestCases" class="stream-content-display" style="margin-top: 15px;">
            <div class="stream-header">
              <span class="stream-title">
                {{ $t('requirementAnalysis.finalVersionTestCases') }}
                <span v-if="isGenerating" class="streaming-indicator">{{ $t('requirementAnalysis.generating') }}</span>
              </span>
              <span class="stream-status">{{ $t('requirementAnalysis.characters', { count: finalTestCases.length }) }}</span>
            </div>
            <div class="stream-content final-testcases" v-html="formatMarkdown(finalTestCases)"></div>
          </div>

          <div class="progress-steps">
            <div class="step" :class="{ active: currentStep >= 1 }">
              <span class="step-number">1</span>
              <span class="step-text">{{ $t('requirementAnalysis.stepAnalysis') }}</span>
            </div>
            <div class="step" :class="{ active: currentStep >= 2 }">
              <span class="step-number">2</span>
              <span class="step-text">{{ $t('requirementAnalysis.stepWriting') }}</span>
            </div>
            <div v-if="showReviewStep" class="step" :class="{ active: currentStep >= 3 }">
              <span class="step-number">3</span>
              <span class="step-text">{{ $t('requirementAnalysis.stepReview') }}</span>
            </div>
            <div class="step" :class="{ active: currentStep >= (showReviewStep ? 4 : 3) }">
              <span class="step-number">{{ showReviewStep ? 4 : 3 }}</span>
              <span class="step-text">{{ $t('requirementAnalysis.stepComplete') }}</span>
            </div>
          </div>

          <!-- 任务完成后的操作按钮 -->
          <div v-if="showResults" class="completion-actions">
            <button class="download-btn" @click="downloadTestCases">
              <span>📥 {{ $t('requirementAnalysis.downloadExcel') }}</span>
            </button>
            <button class="save-btn" @click="saveToTestCaseRecords">
              <span>💾 {{ $t('requirementAnalysis.saveToRecords') }}</span>
            </button>
            <button class="new-generation-btn" @click="resetGeneration">
              <span>📝 {{ $t('requirementAnalysis.newGeneration') }}</span>
            </button>
          </div>
          <button v-else class="cancel-generation-btn" @click="cancelGeneration">
            {{ $t('requirementAnalysis.cancelGeneration') }}
          </button>
        </div>
      </div>

      <!-- 旧的生成结果区域已废弃，保留用于兼容 -->
      <!-- 现在使用流式显示区域 + 最终版用例区域 -->
      <div v-if="false && showResults && generationResult" class="generation-result">
        <div class="result-header">
          <h2>{{ $t('requirementAnalysis.generationComplete') }}</h2>
          <div class="result-summary">
            <span class="summary-item">
              {{ $t('requirementAnalysis.summaryTaskId', { taskId: generationResult.task_id }) }}
            </span>
            <span class="summary-item">
              {{ $t('requirementAnalysis.summaryGenerationTime', { time: formatDateTime(generationResult.completed_at) }) }}
            </span>
          </div>
        </div>
      </div>
    </div>
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
        const payload = {
          title: this.modaoTitle,
          url: this.modaoUrl,
          data: { canvases, import_id: this._modaoImportId },
          project_id: this.manualInput.selectedProject || undefined,
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
      this.pendingGeneration = {
        type: 'modao',
        title: this.modaoTitle || '墨刀需求',
        requirementText: `墨刀原型图「${this.modaoTitle}」，共 ${selected.length} 个画布`,
        projectId: this.manualInput.selectedProject || undefined,
        versionIds: this.manualInput.selectedVersionIds || [],
        functionModuleId: this.manualInput.selectedModuleId || '',
        outputMode: 'stream',
        pageImages: selected.flatMap(c =>
          (c.screenshots || []).filter(s => s.url).map(s => ({ screenshot_url: s.url, media_type: 'image/png' }))
        ),
      }
      try {
        const payload = {
          requirement_text: this.pendingGeneration.requirementText,
          project_id: this.manualInput.selectedProject || undefined,
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
          requestData.project = projectId
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

      // 先去除"新增"标记，在markdown转换之前处理
      // 这样可以避免markdown转换后无法匹配的问题
      let html = content
          .replace(/\*\*新增\*\*-/g, '')  // **新增**-xxx -> xxx (保留xxx的原有格式)
          .replace(/新增-/g, '');  // 新增-xxx -> xxx (保留xxx的原有格式)

      // 转义HTML特殊字符
      html = html
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;');

      // 转换Markdown语法
      // 标题 #
      html = html.replace(/^#{6}\s+(.+)$/gm, '<h6>$1</h6>');
      html = html.replace(/^#{5}\s+(.+)$/gm, '<h5>$1</h5>');
      html = html.replace(/^#{4}\s+(.+)$/gm, '<h4>$1</h4>');
      html = html.replace(/^#{3}\s+(.+)$/gm, '<h3>$1</h3>');
      html = html.replace(/^#{2}\s+(.+)$/gm, '<h2>$1</h2>');
      html = html.replace(/^#{1}\s+(.+)$/gm, '<h1>$1</h1>');

      // 粗体 **text** 或 __text__
      html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');

      // 斜体 *text* 或 _text_
      html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
      html = html.replace(/_(.+?)_/g, '<em>$1</em>');

      // 代码块 ```code```
      html = html.replace(/```([\s\S]+?)```/g, '<pre><code>$1</code></pre>');

      // 行内代码 `code`
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

      // 换行符转换为<br>
      html = html.replace(/\n/g, '<br>');

      return html;
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
.requirement-analysis {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  background: #f5f7fa;
  min-height: 100vh;
}

.page-header {
  text-align: center;
  margin-bottom: 28px;
}

.page-header h1 {
  font-size: 1.5rem;
  color: #1a1a2e;
  margin-bottom: 6px;
  font-weight: 600;
}

.page-header p {
  color: #a0aec0;
  font-size: .92rem;
}

/* 输出模式设置区域 */
.output-mode-section {
  margin-bottom: 24px;
}

.output-mode-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}

.output-mode-card h3 {
  font-size: 1rem;
  color: #1a1a2e;
  margin: 0 0 4px 0;
  font-weight: 600;
}

.mode-section-desc {
  color: #a0aec0;
  font-size: .84rem;
  margin: 0 0 14px 0;
}

/* 配置引导弹出窗口 */
.modal-overlay {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  background: rgba(15, 23, 42, 0.6) !important;
  backdrop-filter: blur(4px);
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  z-index: 9999 !important;
  padding: 20px;
  margin: 0 !important;
  opacity: 1 !important;
}

.guide-config-modal {
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%) !important;
  border-radius: 24px;
  padding: 36px;
  max-width: 850px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(226, 232, 240, 0.8);
  position: relative;
  flex-shrink: 0;
  margin: auto;
  opacity: 1 !important;
}

.guide-config-modal::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 5px;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-radius: 24px 24px 0 0;
}

.guide-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
}

.guide-icon {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  filter: drop-shadow(0 4px 8px rgba(245, 158, 11, 0.2));
}

.guide-title h2 {
  font-size: 1.6rem;
  color: #1a202c;
  margin: 0 0 6px 0;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.guide-title p {
  color: #64748b;
  font-size: 0.95rem;
  margin: 0;
  font-weight: 400;
}

.config-groups {
  margin-bottom: 24px;
}

.config-group {
  margin-bottom: 20px;
}

.group-label {
  font-size: 0.85rem;
  color: #94a3b8;
  margin-bottom: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.config-items-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.config-item-inline {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-radius: 12px;
  border: 2px solid transparent;
  position: relative;
  overflow: hidden;
  font-weight: 500;
}

.config-item-inline::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  border-radius: 12px 0 0 12px;
}

.config-item-inline.optional {
  opacity: 0.75;
}

/* 根据状态设置背景色和样式 */
.config-item-inline.status-enabled {
  background: linear-gradient(135deg, rgba(236, 253, 245, 0.9) 0%, rgba(220, 252, 231, 0.6) 100%);
  border-color: rgba(34, 197, 94, 0.2);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.1);
}

.config-item-inline.status-enabled::before {
  background: linear-gradient(180deg, #22c55e 0%, #16a34a 100%);
}

.config-item-inline.status-disabled {
  background: linear-gradient(135deg, rgba(254, 249, 195, 0.9) 0%, rgba(254, 240, 138, 0.6) 100%);
  border-color: rgba(234, 179, 8, 0.2);
  box-shadow: 0 4px 12px rgba(234, 179, 8, 0.1);
}

.config-item-inline.status-disabled::before {
  background: linear-gradient(180deg, #eab308 0%, #ca8a04 100%);
}

.config-item-inline.status-unconfigured {
  background: linear-gradient(135deg, rgba(254, 242, 242, 0.9) 0%, rgba(254, 226, 226, 0.6) 100%);
  border-color: rgba(239, 68, 68, 0.2);
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.1);
}

.config-item-inline.status-unconfigured::before {
  background: linear-gradient(180deg, #ef4444 0%, #dc2626 100%);
}

.status-symbol {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  font-size: 20px;
}

.config-label {
  font-size: 0.95rem;
  color: #334155;
  font-weight: 600;
  flex-shrink: 0;
}

.config-name {
  font-size: 0.85rem;
  color: #64748b;
  margin-left: 4px;
  font-weight: 500;
}

.status-text {
  margin-left: auto;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 700;
  background: #ef4444;
  color: white;
  white-space: nowrap;
  box-shadow: 0 2px 6px rgba(239, 68, 68, 0.2);
}

.status-text.warning {
  background: #eab308;
  box-shadow: 0 2px 6px rgba(234, 179, 8, 0.2);
}

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
  border-radius: 12px;
  font-size: 0.95rem;
  font-weight: 600;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center;
  white-space: nowrap;
  opacity: 1 !important;
  cursor: pointer;
  box-sizing: border-box !important;
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


/* Tab 栏 */
.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  border-bottom: 2px solid #e8e8e8;
}
.tab-bar .tab-btn {
  padding: 10px 20px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 0.95rem;
  color: #666;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}
.tab-bar .tab-btn.active {
  color: #3498db;
  border-bottom-color: #3498db;
  font-weight: 500;
}
.tab-bar .tab-btn:hover {
  color: #3498db;
}

.manual-input-card, .upload-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
  margin-bottom: 24px;
}

.manual-input-card h2, .upload-card h2 {
  color: #1a1a2e;
  margin: 0 0 16px 0;
  font-size: 1.1rem;
  font-weight: 600;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: .82rem;
  font-weight: 600;
  color: #4a5568;
}

/* 输出模式选择器 */
.output-mode-selector {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: stretch;
}

.mode-option {
  position: relative;
  cursor: pointer;
  display: flex;
}

.mode-option input[type="radio"] {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.mode-content {
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  transition: all 0.3s ease;
  background: white;
  display: flex;
  flex-direction: column;
  justify-content: center;
  width: 100%;
  box-sizing: border-box;
}

.mode-option:hover .mode-content {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
}

.mode-option.active .mode-content {
  border-color: #3b82f6;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.2);
}

.mode-title {
  font-size: 1rem;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 6px;
}

.mode-desc {
  font-size: 0.85rem;
  color: #64748b;
  line-height: 1.4;
}

.mode-option.active .mode-title {
  color: #2563eb;
}

.mode-option.active .mode-desc {
  color: #475569;
}

.form-input, .form-select, .form-textarea {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: .9rem;
  transition: border-color .15s, box-shadow .15s;
  color: #1a1a2e;
  background: #fff;
}

.form-input:focus, .form-select:focus, .form-textarea:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102,126,234,.12);
}

.form-textarea {
  resize: vertical;
  font-family: inherit;
  line-height: 1.7;
}

.char-count {
  text-align: right;
  font-size: 0.85rem;
  color: #666;
  margin-top: 5px;
}

.select-hint {
  font-size: 0.8rem;
  color: #999;
  margin-top: 4px;
}

.quick-add-btn {
  width: 36px;
  height: 36px;
  border: 1px solid #3498db;
  background: #fff;
  color: #3498db;
  border-radius: 6px;
  font-size: 1.2rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.quick-add-btn:hover {
  background: #3498db;
  color: #fff;
}
.quick-add-btn:disabled {
  border-color: #ddd;
  color: #ccc;
  cursor: not-allowed;
}

.required {
  color: #e74c3c;
}

.generate-manual-btn, .generate-btn {
  background: #667eea;
  color: #fff;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  cursor: pointer;
  font-size: .95rem;
  font-weight: 500;
  transition: all .15s;
  width: 100%;
  margin-top: 8px;
}

.generate-manual-btn:hover:not(:disabled), .generate-btn:hover:not(:disabled) {
  background: #5a6fd6;
}

.generate-manual-btn:disabled, .generate-btn:disabled {
  background: #e2e8f0;
  color: #a0aec0;
  cursor: not-allowed;
}

.replace-btn {
  background: none;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
  padding: 1px 4px;
  opacity: 0.5;
  transition: opacity 0.2s;
}
.replace-btn:hover { opacity: 1; border-color: #409eff; }

.modao-lightbox {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  cursor: pointer;
}
.preview-nav {
  position: fixed;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255,255,255,0.15);
  color: #fff;
  border: none;
  border-radius: 50%;
  width: 44px;
  height: 44px;
  font-size: 18px;
  cursor: pointer;
  z-index: 10000;
  transition: background 0.2s;
}
.preview-nav:hover { background: rgba(255,255,255,0.3); }
.preview-prev { left: 20px; }
.preview-next { right: 20px; }

.divider {
  text-align: center;
  margin: 40px 0;
  position: relative;
}

.divider::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 1px;
  background: #ddd;
}

.divider span {
  background: white;
  padding: 0 20px;
  color: #666;
  font-size: 1rem;
}

.upload-area {
  border: 2px dashed #ddd;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  transition: border-color 0.3s ease;
  margin-bottom: 20px;
}

.upload-area.drag-over {
  border-color: #3498db;
  background: #f8f9fa;
}

.upload-placeholder {
  color: #666;
}

.upload-icon {
  font-size: 3rem;
  margin-bottom: 15px;
  display: block;
}

.upload-hint {
  color: #999;
  font-size: 0.9rem;
  margin-top: 5px;
}

.upload-btns {
  display: flex;
  gap: 10px;
  margin-top: 15px;
}

.select-file-btn {
  background: #3498db;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
}

.select-file-btn:hover {
  background: #2980b9;
}

.file-selected {
  padding: 20px;
  background: #f8f9fa;
  border-radius: 6px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.file-info.clickable {
  cursor: pointer;
}

.expand-arrow {
  font-size: 11px;
  margin-left: 2px;
}

/* 展开的文件列表 */

.file-list-expanded {
  margin-top: 12px;
  border-top: 1px solid #e0e0e0;
  padding-top: 10px;
  max-height: 200px;
  overflow-y: auto;
}

.file-list-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.1s;
}

.file-list-item:hover {
  background: #eef2ff;
}

.file-list-item-active {
  background: #e0e7ff;
  font-weight: 500;
}

.fli-name {
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 12px;
}

.fli-size {
  color: #999;
  font-size: 12px;
  white-space: nowrap;
}

.file-icon {
  font-size: 2rem;
}

.file-details {
  flex: 1;
}

.file-name {
  font-weight: 600;
  margin: 0;
}

.file-size {
  color: #666;
  font-size: 0.9rem;
  margin: 5px 0 0 0;
}

.remove-file {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
}

.generation-progress {
  margin: 40px 0;
}

.progress-card {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  border: 1px solid #e1e8ed;
  text-align: center;
}

.progress-card h3 {
  color: #2c3e50;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}

.current-mode-badge {
  display: inline-block;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 500;
  margin-left: 8px;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.progress-info {
  display: flex;
  justify-content: center;
  gap: 30px;
  margin-bottom: 30px;
  flex-wrap: wrap;
}

.progress-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.progress-item .label {
  font-size: 0.9rem;
  color: #666;
}

.progress-item .value {
  font-weight: 600;
  color: #2c3e50;
}

/* 流式内容显示区域 */
.stream-content-display {
  margin: 20px 0;
  border: 2px solid #e1e8ed;
  border-radius: 8px;
  overflow: hidden;
  background: #f8f9fa;
}

.stream-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #e9ecef;
  border-bottom: 1px solid #dee2e6;
}

.stream-title {
  font-weight: 600;
  color: #495057;
  font-size: 0.95rem;
}

.stream-status {
  font-size: 0.85rem;
  color: #6c757d;
  background: white;
  padding: 4px 10px;
  border-radius: 12px;
  border: 1px solid #dee2e6;
}

.stream-content {
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
  text-align: left;
  background: white;
  font-size: 0.9rem;
  line-height: 1.6;
  color: #2c3e50;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.stream-content::-webkit-scrollbar {
  width: 8px;
}

.stream-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.stream-content::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.stream-content::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 最终版用例特殊样式 */
.stream-content.final-testcases {
  background: #f0f7ff;
  border-left: 4px solid #2196F3;
}

.stream-content.final-testcases::before {
  content: '📋 最终版本';
  display: block;
  font-weight: 600;
  color: #2196F3;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e3f2fd;
}

/* 流式输出指示器 */
.streaming-indicator {
  font-size: 0.85em;
  margin-left: 8px;
  color: #4CAF50;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.stream-content h1,
.stream-content h2,
.stream-content h3,
.stream-content h4,
.stream-content h5,
.stream-content h6 {
  margin-top: 1em;
  margin-bottom: 0.5em;
  color: #2c3e50;
  font-weight: 600;
}

.stream-content code {
  background: #f1f3f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.85em;
}

.stream-content pre {
  background: #f1f3f5;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 10px 0;
}

.stream-content pre code {
  background: none;
  padding: 0;
}

.progress-steps {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-bottom: 30px;
  flex-wrap: wrap;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  opacity: 0.4;
  transition: opacity 0.3s ease;
}

.step.active {
  opacity: 1;
}

.step-number {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #ddd;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: white;
}

.step.active .step-number {
  background: #3498db;
}

.step-text {
  font-size: 0.9rem;
  color: #666;
}

.cancel-generation-btn {
  background: #e74c3c;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
}

/* ========== 需求澄清面板 ========== */
.clarification-section {
  margin: 20px 0;
}

.clarification-card {
  background: #fff;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  border: 1px solid #e8e8e8;
}

.clarification-card h2 {
  font-size: 1.3rem;
  color: #2c3e50;
  margin: 0 0 10px 0;
}

.clarification-subtitle {
  color: #666;
  font-size: 0.95rem;
  margin: 0 0 24px 0;
  line-height: 1.6;
}

.clarifying-loading {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 40px;
  justify-content: center;
  font-size: 1.1rem;
  color: #666;
}

.loading-spinner {
  font-size: 1.5rem;
  animation: spin 2s linear infinite;
}

.clarification-empty {
  padding: 30px;
  text-align: center;
  font-size: 1.05rem;
  color: #27ae60;
}

.clarification-questions {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 24px;
}

.clarification-question-item {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px 20px;
  border-left: 4px solid #3498db;
}

.question-text {
  font-size: 0.95rem;
  color: #2c3e50;
  margin-bottom: 10px;
  line-height: 1.6;
}

.question-number {
  display: inline-block;
  background: #3498db;
  color: #fff;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  line-height: 24px;
  text-align: center;
  font-size: 0.8rem;
  font-weight: bold;
  margin-right: 8px;
  vertical-align: middle;
}

.question-answer-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 0.9rem;
  resize: vertical;
  font-family: inherit;
  transition: border-color 0.2s;
}

.question-answer-input:focus {
  outline: none;
  border-color: #3498db;
  box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
}

.clarification-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.skip-clarify-btn {
  padding: 10px 20px;
  background: #fff;
  color: #666;
  border: 1px solid #ddd;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.skip-clarify-btn:hover {
  background: #f5f5f5;
  border-color: #ccc;
}

.confirm-clarify-btn {
  padding: 10px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.2s;
}

.confirm-clarify-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

/* ========== 需求澄清面板结束 ========== */

.completion-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.completion-actions button {
  flex: 1;
  min-width: 150px;
  padding: 12px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.completion-actions .download-btn {
  background: #28a745;
  color: white;
  font-size: 1rem;
}

.completion-actions .download-btn:hover {
  background: #218838;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(40, 167, 69, 0.3);
}

.completion-actions .save-btn {
  background: #007bff;
  color: white;
  font-size: 1rem;
}

.completion-actions .save-btn:hover {
  background: #0056b3;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 123, 255, 0.3);
}

.completion-actions .new-generation-btn {
  background: #6c757d;
  color: white;
  font-size: 1rem;
}

.completion-actions .new-generation-btn:hover {
  background: #5a6268;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(108, 117, 125, 0.3);
}

.generation-result {
  margin: 40px 0;
}

.result-header {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  border: 1px solid #e1e8ed;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 20px;
}

.result-header h2 {
  color: #27ae60;
  margin: 0;
}

.result-summary {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.summary-item {
  color: #666;
  font-size: 0.9rem;
}

.new-generation-btn {
  background: #3498db;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
}

.generated-testcases-section, .review-feedback-section, .final-testcases-section {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  border: 1px solid #e1e8ed;
  margin-bottom: 20px;
}

.generated-testcases-section h3, .review-feedback-section h3, .final-testcases-section h3 {
  color: #2c3e50;
  margin-bottom: 20px;
}

.testcase-content, .review-content {
  background: #f8f9fa;
  border-radius: 6px;
  padding: 20px;
  border-left: 4px solid #3498db;
}

.testcase-content pre, .review-content pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 0.9rem;
  line-height: 1.6;
}

@media (max-width: 768px) {
  .result-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .progress-info, .result-summary {
    flex-direction: column;
    gap: 10px;
  }

  .progress-steps {
    gap: 10px;
  }
}

.actions-section {
  display: flex;
  gap: 20px;
  justify-content: center;
  margin-top: 30px;
  flex-wrap: wrap;
}

.download-btn, .save-btn {
  padding: 12px 24px;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
}

.download-btn {
  background-color: #1abc9c;
  color: white;
}

.download-btn:hover {
  background-color: #16a085;
}

.save-btn {
  background-color: #3498db;
  color: white;
}

.save-btn:hover {
  background-color: #2980b9;
}

@media (max-width: 768px) {
  .actions-section {
    flex-direction: column;
    align-items: center;
  }

  .download-btn, .save-btn {
    width: 100%;
    max-width: 300px;
    justify-content: center;
  }
}

/* 墨刀历史导入卡片 */
.history-pill {
  padding: 4px 10px; font-size: 12px; background: #f0f2f5; border-radius: 4px;
  cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
  transition: background .2s;
  &:hover { background: #e4e7ed; }
  &.active { background: #ecf5ff; border: 1px solid #409eff; }
  .history-pill-name { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .history-pill-meta { font-size: 10px; color: #909399; }
  .history-pill-del { color: #c0c4cc; margin-left: 2px; &:hover { color: #f56c6c; } }
}
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
  border-radius: 12px;
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