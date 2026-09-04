<template>
  <div class="ms-shell" data-ark-theme="endfield" data-ark-depth="complex">
    <!-- ====== Grid Background ====== -->
    <div class="ms-grid" aria-hidden="true"></div>

    <!-- ====== Left Rail: Case List ====== -->
    <nav class="ms-rail" aria-label="用例列表">
      <div class="ms-rail__head">
        <div class="ms-rail__title-row">
          <span class="ms-rail__idx">00</span>
          <span class="ms-rail__label">TEST CASES</span>
          <span class="ms-rail__count">{{ cases.length }}</span>
        </div>
        <el-select v-model="filterProjectId" placeholder="筛选项目" size="small" clearable class="ms-select--dark">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </div>

      <div class="ms-rail__list">
        <template v-for="item in railItems" :key="item.type + (item.folder ? item.folder.id : (item.case ? item.case.id : item.label))">
          <button
            v-if="item.type !== 'divider'"
            class="ms-case-item"
            :class="{
              'is-active': item.case && item.case.id === currentCaseId,
              'is-draft': item.case && item.case._draft,
              'ms-folder-row': item.type === 'folder',
              'ms-folder-row--active': item.type === 'folder' && item.folder.id === activeFolderId,
              'ms-case-item--in-folder': item.inFolder
            }"
            @click="item.type === 'folder' ? toggleFolder(item.folder.id) : loadCase(item.case)"
          >
            <template v-if="item.type === 'folder'">
              <span class="ms-folder-row__arrow">
                <el-icon :class="{ 'is-open': isFolderOpen(item.folder.id) }"><ArrowRight /></el-icon>
              </span>
              <span class="ms-folder-row__icon"><el-icon><Folder /></el-icon></span>
              <span class="ms-case-item__name ms-folder-row__name">{{ item.folder.name }}</span>
              <span class="ms-folder-row__count">{{ getFolderCount(item.folder.id) }}</span>
              <span class="ms-folder-row__ops">
                <el-icon class="ms-folder-row__op" @click.stop="openRenameFolder(item.folder)" title="重命名"><EditPen /></el-icon>
                <el-icon class="ms-folder-row__op ms-folder-row__op--del" @click.stop="deleteFolder(item.folder)" title="删除"><Delete /></el-icon>
              </span>
            </template>
            <template v-else>
              <span class="ms-case-item__num">{{ String(item.idx).padStart(2, '0') }}</span>
              <span class="ms-case-item__body">
                <span class="ms-case-item__name">{{ item.case.name }}</span>
                <span class="ms-case-item__row">
                  <span class="ms-case-item__steps">{{ getStepCount(item.case.ai_prompt) }} 步</span>
                  <span v-if="!item.case._draft && item.case.latest_result" class="ms-case-item__rate" :class="item.case.latest_result.status === 'passed' ? 'rate-pass' : 'rate-fail'">
                    {{ item.case.latest_result.pass_rate }}%
                  </span>
                  <span v-else-if="item.case._draft" class="ms-case-item__draft-mark">草稿</span>
                </span>
                <span class="ms-case-item__proj" v-if="getProjectName(item.case.project)">{{ getProjectName(item.case.project) }}</span>
              </span>
              <span class="ms-case-item__del" @click.stop="deleteCase(item.case)" title="删除"><el-icon><Delete /></el-icon></span>
            </template>
          </button>
          <div v-else class="ms-folder-divider">
            <span class="ms-folder-divider__label">{{ item.label }}</span>
            <span class="ms-folder-divider__count">{{ item.count }}</span>
          </div>
        </template>
        <div v-if="filteredCases.length === 0 && filteredFolders.length === 0" class="ms-rail__empty">
          {{ filterProjectId ? '该项目暂无用例' : '暂无用例，点击下方新建' }}
        </div>
        <div v-else-if="filteredCases.length === 0 && !filterProjectId" class="ms-rail__empty">
          文件夹暂无用例
        </div>
      </div>

      <div class="ms-rail__foot">
        <el-button @click="openNewFolder" :icon="FolderAdd" class="ms-btn--full ms-btn--ghost">新建文件夹</el-button>
        <el-button @click="newCase" :icon="Plus" class="ms-btn--full">新建用例</el-button>
      </div>
    </nav>

    <!-- ====== Main Stage ====== -->
    <main class="ms-stage">
      <!-- Zone A: 用例信息 + 执行控制 -->
      <section class="ms-zone">
        <header class="ms-zone__head">
          <span class="ms-zone__kicker">CONFIGURATION / 01</span>
          <span class="ms-zone__rule" aria-hidden="true"></span>
        </header>
        <div class="ms-zone__body">
          <div class="ms-field-row">
            <el-input v-model="form.name" placeholder="用例名称" class="ms-input" />
            <el-select v-model="form.project_id" placeholder="所属项目" clearable class="ms-select">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
            <el-select v-model="form.folder_id" placeholder="所属文件夹" clearable class="ms-select">
              <el-option v-for="f in folderOptions" :key="f.id" :label="f.name" :value="f.id" />
            </el-select>
            <el-select v-model="form.ai_model_config_id" placeholder="AI 模型" class="ms-select">
              <el-option v-for="m in visionModels" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </div>
        </div>
      </section>

      <!-- Zone B: 执行控制 -->
      <section class="ms-zone">
        <header class="ms-zone__head">
          <span class="ms-zone__kicker">EXECUTION / 02</span>
          <span class="ms-zone__rule" aria-hidden="true"></span>
        </header>
        <div class="ms-zone__body">
          <div class="ms-cmd-strip">
            <div class="ms-cmd-strip__left">
              <el-select v-model="selectedDeviceIds" multiple collapse-tags collapse-tags-tooltip
                placeholder="选择设备（可多选）" class="ms-select ms-select--devices">
                <el-option-group label="Android">
                  <el-option v-for="d in androidDevices" :key="d.id"
                    :label="`${d.name || d.device_id} ${d.status === 'locked' ? '🔒' : ''}`"
                    :value="d.id" :disabled="d.status === 'offline'" />
                </el-option-group>
                <el-option-group label="iOS">
                  <el-option v-for="d in iosDevices" :key="d.id"
                    :label="`${d.name || d.device_id}`" :value="d.id" :disabled="d.status === 'offline'" />
                </el-option-group>
              </el-select>
              <el-button size="small" @click="discoverDevices" :loading="discovering" :icon="Refresh" class="ms-btn">发现设备</el-button>
              <el-button size="small" @click="showNetworkDialog = true" :icon="Connection" class="ms-btn">局域网</el-button>
              <span class="ms-cmd-strip__divider" aria-hidden="true"></span>
              <span class="ms-switch-group">
                <label class="ms-switch"><el-switch v-model="autoPlanMode" size="small" :disabled="replayMode" /><span>智能规划</span></label>
                <label class="ms-switch"><el-switch v-model="recordMode" size="small" /><span>录制</span></label>
                <label class="ms-switch"><el-switch v-model="replayMode" size="small" :disabled="autoPlanMode" /><span>回放</span></label>
                <label class="ms-switch">
                  <el-switch v-model="clearAppData" size="small" :disabled="isIosDevice || !!selectedInstallPackageId" />
                  <el-tooltip :content="isIosDevice ? 'iOS 不支持' : (selectedInstallPackageId ? '选中安装包后自动清除数据' : '执行前清除App数据')" placement="top">
                    <span style="cursor:help">清除数据</span>
                  </el-tooltip>
                </label>
                <el-select v-model="selectedInstallPackageId" clearable size="small" placeholder="安装包（可选）"
                  class="ms-select" style="width: 200px" @change="onInstallPackageChange">
                  <el-option-group label="Android">
                    <el-option v-for="p in androidPackages" :key="p.id"
                      :label="`${p.name || p.package_name} ${p.version_name ? 'v' + p.version_name : ''}`"
                      :value="p.id" />
                  </el-option-group>
                  <el-option-group label="iOS">
                    <el-option v-for="p in iosPackages" :key="p.id"
                      :label="`${p.name || p.package_name} ${p.version_name ? 'v' + p.version_name : ''}`"
                      :value="p.id" />
                  </el-option-group>
                </el-select>
                <span class="ms-cmd-strip__divider" aria-hidden="true"></span>
                <span class="ms-ai-config">
                  <span class="ms-ai-config__label">AI引擎</span>
                  <el-select v-model="midsceneConfig.use_locate" size="small" class="ms-select"
                    style="width: 90px" @change="saveMidsceneConfig">
                    <el-option label="不覆盖" value="" />
                    <el-option label="开启" value="true" />
                    <el-option label="关闭" value="false" />
                  </el-select>
                  <el-select v-model="midsceneConfig.use_deep_locate" size="small" class="ms-select"
                    style="width: 110px" @change="saveMidsceneConfig">
                    <el-option label="不覆盖" value="" />
                    <el-option label="关闭" value="off" />
                    <el-option label="自动升级" value="auto" />
                    <el-option label="强制" value="on" />
                  </el-select>
                </span>
              </span>
            </div>
            <div class="ms-cmd-strip__right">
              <el-select v-if="replayList.length > 0" v-model="selectedReplayIndex" size="small" class="ms-select" style="width:210px">
                <el-option v-for="(r, i) in replayList" :key="i" :label="`${r.name || r.recorded_at?.substring(5,16) || '未命名'} ${r.result || ''}`" :value="i" />
              </el-select>
              <el-button v-if="replayList.length > 0" size="small" text @click="showReplayDetail = true" class="ms-btn--text">
                <el-icon><View /></el-icon>&nbsp;明细
              </el-button>
              <el-button v-if="replayList.length > 0" size="small" text @click="renameReplayEntry" class="ms-btn--text">
                <el-icon><EditPen /></el-icon>
              </el-button>
              <el-button v-if="replayList.length > 0" size="small" type="danger" text @click="deleteReplayEntry" class="ms-btn--text">
                <el-icon><Delete /></el-icon>
              </el-button>
              <el-button size="small" text @click="openSequenceDrawer" class="ms-btn--text">
                <el-icon><DocumentAdd /></el-icon>&nbsp;编排
              </el-button>
              <el-button
                type="primary" @click="doExecute" :loading="executing" :disabled="!canExecute"
                :icon="VideoPlay" class="ms-btn--exec"
              >执行{{ selectedDeviceIds.length > 1 ? ` (${selectedDeviceIds.length})` : '' }}</el-button>
              <el-button v-if="isRunning" @click="stopAllExecutions" :icon="SwitchButton" class="ms-btn--stop">停止</el-button>
            </div>
          </div>
        </div>
      </section>

      <!-- Zone C: 测试步骤 -->
      <section class="ms-zone">
        <header class="ms-zone__head">
          <span class="ms-zone__kicker">PROCEDURE / 03</span>
          <span class="ms-zone__rule" aria-hidden="true"></span>
        </header>
        <div class="ms-zone__body">
          <el-input v-model="form.ai_act_context" placeholder="全局提示：如 遇到权限弹窗先点允许、遇到渠道选择选抖音" size="small" clearable class="ms-input--context">
            <template #prepend>全局提示</template>
          </el-input>
          <div class="ms-editor">
            <div v-if="editorMode === 'list'" class="ms-field-console">
              <div class="ms-field-console__head">
                <span class="ms-field-console__count">共 {{ stepRows.length }} 步</span>
                <button class="ms-raw-toggle" @click="toggleRaw">原始文本</button>
              </div>
              <div class="ms-field-console__list">
                <div v-for="row in stepRows" :key="row.key"
                     class="ms-step-row"
                     :class="{ 'is-branch': row.kind === 'branch', 'is-child': row.kind === 'child', 'is-else-marker': row.kind === 'elseMarker', 'is-drag-over': dragOverKey === row.key && dragKey !== row.key }"
                     :draggable="!dragDisabled(row)"
                     @dragstart="onDragStart(row, $event)"
                     @dragover="onDragOver(row, $event)"
                     @drop="onDrop(row, $event)"
                     @dragend="onDragEnd">
                  <span class="ms-step-row__idx">{{ row.kind === 'elseMarker' ? '否则' : row.num }}</span>
                  <template v-if="row.kind === 'branch'">
                    <span class="ms-step-row__prefix">{{ row.it.prefix }}</span>
                    <el-input v-model="row.it.condition" class="ms-step-row__input" size="small"
                              placeholder="条件，如 展示会员购买页" @input="onEdit" />
                    <span class="ms-step-row__colon">:</span>
                  </template>
                  <template v-else-if="row.kind === 'elseMarker'">
                    <span class="ms-step-row__else">否则:</span>
                  </template>
                  <el-input v-else v-model="row.it.text" class="ms-step-row__input" size="small"
                            placeholder="步骤，如 点击登录" @input="onEdit" />
                  <div class="ms-step-row__tools">
                    <button v-if="row.kind !== 'child'" class="ms-iconbtn" title="上移" @click="moveTop(row.idx, -1)">↑</button>
                    <button v-if="row.kind !== 'child'" class="ms-iconbtn" title="下移" @click="moveTop(row.idx, 1)">↓</button>
                    <button v-if="row.kind === 'child' && !row.elseSide" class="ms-iconbtn" title="上移" @click="moveChild(row.branchId, row.cidx, -1)">↑</button>
                    <button v-if="row.kind === 'child' && !row.elseSide" class="ms-iconbtn" title="下移" @click="moveChild(row.branchId, row.cidx, 1)">↓</button>
                    <button v-if="row.kind === 'child' && row.elseSide" class="ms-iconbtn" title="上移" @click="moveElseChild(row.branchId, row.cidx, -1)">↑</button>
                    <button v-if="row.kind === 'child' && row.elseSide" class="ms-iconbtn" title="下移" @click="moveElseChild(row.branchId, row.cidx, 1)">↓</button>
                    <button v-if="row.kind === 'child' || row.kind === 'elseMarker'" class="ms-iconbtn ms-textbtn" title="加否则子步骤" @click="addElseChild(row.branchId)">+ else</button>
                    <button v-if="row.kind === 'branch'" class="ms-iconbtn ms-textbtn" title="加子步骤" @click="addChild(row.branchId)">+ 子</button>
                    <button v-if="row.kind === 'branch'" class="ms-iconbtn ms-textbtn" title="加否则子步骤" @click="addElseChild(row.branchId)">+ 否则</button>
                    <button v-if="row.kind === 'step'" class="ms-iconbtn ms-textbtn"
                            :disabled="!(row.idx > 0 && stepItems[row.idx - 1] && stepItems[row.idx - 1].kind === 'branch')"
                            title="缩进为子步骤" @click="indentStep(row.idx)">缩进</button>
                    <button v-if="row.kind === 'child' && !row.elseSide" class="ms-iconbtn ms-textbtn" title="取消缩进" @click="outdentChild(row.branchId, row.cidx)">取消缩进</button>
                    <button v-if="row.kind === 'child' && row.elseSide" class="ms-iconbtn ms-textbtn" title="取消缩进" @click="outdentElseChild(row.branchId, row.cidx)">取消缩进</button>
                    <button v-if="row.kind !== 'branch' && row.kind !== 'elseMarker'" class="ms-iconbtn ms-iconbtn--danger" title="删除"
                            @click="row.elseSide ? removeElseChild(row.branchId, row.cidx) : removeChild(row.branchId, row.cidx)">×</button>
                  </div>
                </div>
              </div>
              <div class="ms-field-console__add">
                <button class="ms-addbtn" @click="addStep">＋ 添加步骤</button>
                <button class="ms-addbtn ms-addbtn--accent" @click="addBranch">＋ 添加分支</button>
                <span v-if="stepErrors" class="ms-field-console__error">{{ stepErrors }}</span>
              </div>
            </div>
            <template v-else>
              <el-input v-model="form.ai_prompt" type="textarea" :rows="14"
                        placeholder="每行一个自然语言操作步骤（分支头以冒号结尾，子步骤缩进）" />
              <div class="ms-editor__rawfoot">
                <button class="ms-raw-toggle ms-raw-toggle--back" @click="toggleRaw">回到列表</button>
                <span v-if="stepErrors" class="ms-field-console__error">{{ stepErrors }}</span>
              </div>
            </template>
          </div>
          <div class="ms-editor__actions">
            <el-button @click="showAiGen = true" :icon="MagicStick" class="ms-btn">AI 展开</el-button>
            <el-button type="primary" @click="saveCase" :loading="saving" :icon="DocumentAdd" class="ms-btn--save">
              {{ currentCaseId && currentCaseId !== draftId ? '更新' : '保存' }}
            </el-button>
          </div>
        </div>
      </section>

      <!-- Zone D: Live Execution Stage -->
      <section v-if="executions.length > 0" class="ms-stage-live">
        <header class="ms-zone__head">
          <span class="ms-zone__kicker">LIVE / 04</span>
          <span class="ms-zone__rule" aria-hidden="true"></span>
        </header>

        <el-tabs v-model="activeExecIndex" class="ms-exec-tabs">
          <el-tab-pane v-for="(exec, idx) in executions" :key="exec.id" :name="String(idx)">
            <template #label>
              <span class="ms-exec-tab">
                <span class="ms-status-dot" :class="'dot-' + exec.status"></span>
                {{ exec.device_name || ('设备 ' + exec.device_id) }}<template v-if="exec.rerun_mark"> · {{ exec.rerun_mark }}</template>
                <span class="ms-exec-tab__status">{{ exec.status_display || exec.status }}</span>
              </span>
            </template>
          </el-tab-pane>
        </el-tabs>

        <template v-if="activeExec">
          <div class="ms-stage-live__bar">
            <span class="ms-stage-live__status">
              <span class="ms-status-dot" :class="'dot-' + activeExec.status"></span>
              {{ activeExec.status_display || activeExec.status }}
              <span v-if="activeExecAnomalyCount > 0" class="ms-anom-summary" :class="{ 'ms-anom-summary--critical': activeExecCriticalCount > 0 }">
                异常 {{ activeExecAnomalyCount }} 次<template v-if="activeExecCriticalCount > 0">（疑似根因 {{ activeExecCriticalCount }}）</template>
              </span>
              <el-button v-if="isExecRunning(activeExec)" size="small" @click="stopExecution(activeExec)" :icon="SwitchButton" class="ms-btn--stop ms-btn--stop-inline">停止</el-button>
            </span>
            <div class="ms-progress-bar ms-progress-bar--inline">
              <div class="ms-progress-bar__track">
                <div class="ms-progress-bar__fill" :style="{ width: (activeExec.progress || 0) + '%' }"></div>
              </div>
              <span class="ms-progress-bar__label">{{ activeExec.step || 0 }}/{{ activeExec.total_steps || 0 }}</span>
            </div>
          </div>

          <!-- Dual pane: screenshot + reasoning -->
          <div class="ms-dual">
            <div class="ms-dual__pane ms-dual__pane--screen">
            <div class="ms-dual__label">DEVICE SCREEN</div>
            <div class="ms-dual__stage">
              <img v-if="activeExec.screenshot" :src="activeExec.screenshot" class="ms-screen-img" />
              <MsLoading v-else size="lg" label="AWAITING FRAME" />
            </div>
          </div>
          <div class="ms-dual__pane ms-dual__pane--reason">
            <div class="ms-dual__label">AI REASONING</div>
            <div class="ms-dual__log">
              <div v-if="activeExec.reasoning && activeExec.reasoning.length > 0">
                <div v-for="(r, i) in activeExec.reasoning" :key="i" class="ms-log-line">{{ r }}</div>
              </div>
              <div v-else class="ms-dual__wait--center">
                <MsLoading size="md" label="AWAITING ANALYSIS" />
              </div>
            </div>
          </div>
          </div>

          <!-- Step badges -->
          <div class="ms-step-badges">
            <button
              v-for="s in (activeExec.steps_detail || [])"
              :key="s.step"
              class="ms-step-badge"
              :class="stepBadgeClass(s)"
              @click="previewStep(s)"
            >
              <span class="ms-step-badge__mark">{{ stepBadgeMark(s) }}</span>
              {{ s.step }}. {{ s.instruction?.substring(0, 24) }}{{ s.instruction?.length > 24 ? '…' : '' }}
            </button>
          </div>
        </template>
        <div v-else class="ms-dual__wait">NO EXECUTION DATA...</div>
      </section>
    </main>

    <!-- ====== 用例编排抽屉 ====== -->
    <el-drawer v-model="showSequenceDrawer" title="用例编排" size="46%" :destroy-on-close="false">
      <div class="ms-seq">
        <div class="ms-seq__toolbar">
          <el-select v-model="seqDeviceId" placeholder="选择执行设备" clearable size="small" style="width:220px" class="ms-select">
            <el-option v-for="d in seqDevices" :key="d.id"
              :label="`${d.name || d.device_id} (${d.platform})`" :value="d.id" />
          </el-select>
          <el-select v-model="seqListFilterProjectId" placeholder="筛选项目" clearable size="small" style="width:150px" class="ms-select">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <el-button size="small" @click="newSequence" :icon="Plus">新建编排</el-button>
        </div>

        <!-- 列表模式 -->
        <template v-if="seqEditMode === 'list'">
          <div v-if="sequencesLoading" class="ms-seq__empty">加载中...</div>
          <div v-else-if="sequences.length === 0" class="ms-seq__empty">暂无编排，点击「新建编排」</div>
          <div v-else-if="filteredSequences.length === 0" class="ms-seq__empty">该项目下暂无编排</div>
          <div v-else class="ms-seq__list">
            <div v-for="seq in filteredSequences" :key="seq.id" class="ms-seq__card">
              <div class="ms-seq__card-main">
                <div class="ms-seq__name">{{ seq.name }} <span class="ms-seq__count">{{ (seq.items || []).length }} 项</span></div>
                <div class="ms-seq__desc">{{ seq.description || '—' }}</div>
                <div v-if="seq.project_name || seq.folder_name" class="ms-seq__meta">
                  <span v-if="seq.project_name">{{ seq.project_name }}</span>
                  <span v-if="seq.folder_name"> · {{ seq.folder_name }}</span>
                </div>
                <div class="ms-seq__items">
                  <span v-for="it in (seq.items || [])" :key="it.id" class="ms-seq__chip">{{ it.case_name }}</span>
                </div>
              </div>
              <div class="ms-seq__card-ops">
                <el-button size="small" :disabled="!seqDeviceId || !(seq.items || []).length"
                  @click="openSeqRunDialog(seq)" :icon="VideoPlay">执行</el-button>
                <el-button size="small" text @click="editSequence(seq)">编辑</el-button>
                <el-button size="small" type="danger" text @click="deleteSequence(seq)">删除</el-button>
              </div>
            </div>
          </div>
        </template>

        <!-- 编辑模式 -->
        <template v-else>
          <div class="ms-seq__form">
            <el-input v-model="seqForm.name" placeholder="编排名称" class="ms-input" />
            <el-input v-model="seqForm.description" placeholder="编排描述（可选）" class="ms-input" />
            <div class="ms-seq__fields">
              <el-select v-model="seqForm.project_id" placeholder="所属项目" clearable size="small" class="ms-select" style="flex:1">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
              <el-select v-model="seqForm.folder_id" placeholder="所属文件夹" clearable size="small" class="ms-select" style="flex:1">
                <el-option v-for="f in seqFolderOptions" :key="f.id" :label="f.name" :value="f.id" />
              </el-select>
            </div>
            <div class="ms-seq__items-edit">
              <div v-for="(it, i) in seqForm.items" :key="i" class="ms-seq__item">
                <span class="ms-seq__item-no">{{ String(i + 1).padStart(2, '0') }}</span>
                <el-select v-model="it.case_id" placeholder="选择用例（按项目/文件夹过滤）" filterable size="small" class="ms-select" style="flex:1">
                  <el-option v-for="c in seqAvailableCases" :key="c.id" :label="c.name" :value="c.id" />
                </el-select>
                <span class="ms-seq__item-defaults">
                  <el-checkbox v-model="it.break_on_fail" size="small">失败即停</el-checkbox>
                  <el-select v-model="it.replay_mode" size="small" style="width:110px">
                    <el-option label="自动匹配" value="auto" />
                    <el-option label="固定脚本" value="fixed" />
                  </el-select>
                  <el-input-number v-if="it.replay_mode === 'fixed'" v-model="it.replay_index" :min="0" size="small" />
                  <el-select v-model="it.install_package_id" clearable size="small" placeholder="安装包（可选）" style="width: 200px">
                    <el-option v-for="p in installPackages" :key="p.id"
                      :label="`${p.name || p.package_name} ${p.version_name ? 'v' + p.version_name : ''}（${p.platform_display || p.platform}）`"
                      :value="p.id" />
                  </el-select>
                </span>
                <span class="ms-seq__item-ops">
                  <el-button size="small" text :disabled="i === 0" @click="moveSeqItem(i, -1)">↑</el-button>
                  <el-button size="small" text :disabled="i === seqForm.items.length - 1" @click="moveSeqItem(i, 1)">↓</el-button>
                  <el-button size="small" text type="danger" @click="removeSeqItem(i)">✕</el-button>
                </span>
              </div>
            </div>
            <div class="ms-seq__form-ops">
              <el-button size="small" @click="addSeqItem">＋ 添加用例</el-button>
              <el-button size="small" @click="seqEditMode = 'list'">取消</el-button>
              <el-button type="primary" size="small" :loading="seqSaving" @click="saveSequence">保存</el-button>
            </div>
            <div class="ms-seq__hint">首项默认清数据+重启，后续项复用状态（登录态可延续）；每项可单独改。</div>
          </div>
        </template>

        <!-- 执行面板 -->
        <div v-if="seqRun" class="ms-seq__run">
          <div class="ms-seq__run-head">
            <span>编排执行 #{{ seqRun.id }}</span>
            <span class="ms-seq__run-status">{{ seqStatusLabel(seqRun.status) }}</span>
            <el-button v-if="['running', 'pending', 'stopping'].includes(seqRun.status)"
              size="small" type="danger" text @click="stopSeqRun">停止</el-button>
          </div>
          <div class="ms-seq__run-progress"><el-progress :percentage="seqRun.progress || 0" /></div>
          <div class="ms-seq__run-items">
            <div v-for="ex in seqExecutions" :key="ex.id" class="ms-seq__run-item">
              <span class="ms-seq__run-item-name">{{ ex.case_name }}</span>
              <span class="ms-seq__run-item-status" :class="'ms-seq__run-item-status--' + ex.status">{{ seqStatusLabel(ex.status) }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- 编排执行确认 -->
    <el-dialog v-model="seqRunDialog" title="编排回放匹配确认" width="560px">
      <div class="ms-seq__match">
        <div v-for="row in seqMatchRows" :key="row.item_id" class="ms-seq__match-row">
          <span class="ms-seq__match-name">{{ row.order + 1 }}. {{ row.case_name }}</span>
          <span class="ms-seq__match-level" :class="'ms-seq__match-level--' + row.match_level">{{ row.match_level }}</span>
          <span class="ms-seq__match-replay">{{ row.recommended_name || ('录制#' + (row.used_index ?? row.replay_index)) }}</span>
        </div>
        <div class="ms-seq__match-hint">无匹配/分辨率不符的项将降级 VLM；确认后开始执行。</div>
      </div>
      <template #footer>
        <el-button @click="seqRunDialog = false">取消</el-button>
        <el-button type="primary" :loading="seqRunning" @click="confirmSeqRun(seqRunTarget)">开始执行</el-button>
      </template>
    </el-dialog>

    <!-- ====== Dialogs (unchanged) ====== -->
    <el-dialog v-model="showAiGen" title="AI 生成详细步骤" width="500px">
      <el-input v-model="aiDesc" type="textarea" :rows="3" placeholder="简要描述测试场景，AI 自动展开..." />
      <template #footer>
        <el-button @click="showAiGen = false">取消</el-button>
        <el-button type="primary" @click="generateSteps" :loading="genLoading">生成</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showPreview" title="步骤截图" width="460px">
      <div v-if="previewImage || previewAfterImage" class="ms-preview-shots">
        <div v-if="previewImage" class="ms-preview-shot">
          <div class="ms-preview-shot__label">执行前</div>
          <img :src="previewImage" style="width:100%" />
        </div>
        <div v-if="previewAfterImage" class="ms-preview-shot">
          <div class="ms-preview-shot__label">执行后</div>
          <img :src="previewAfterImage" style="width:100%" />
        </div>
      </div>
      <div v-if="previewStepData?.anomalies?.length" class="ms-preview-anoms">
        <div class="ms-preview-anoms__title">异常事件 {{ previewStepData.anomalies.length }} 次</div>
        <div v-for="(a, i) in previewStepData.anomalies" :key="i" class="ms-preview-anom">
          <div class="ms-preview-anom__head">
            <span class="ms-preview-anom__type">{{ a.label || a.type }}</span>
            <span class="ms-preview-anom__layer">{{ a.layer }}</span>
            <span class="ms-preview-anom__sev" :class="'ms-preview-anom__sev--' + (a.severity || 'minor')">{{ severityLabel(a.severity) }}</span>
            <span class="ms-preview-anom__rec" :class="a.recovered ? 'ms-preview-anom__rec--ok' : 'ms-preview-anom__rec--bad'">
              {{ a.recovered ? '已恢复' : '未恢复' }}
            </span>
          </div>
          <div class="ms-preview-anom__msg">{{ a.message }}</div>
          <pre class="ms-preview-anom__ev" v-if="a.evidence && Object.keys(a.evidence).length">{{ JSON.stringify(a.evidence, null, 2) }}</pre>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="showNetworkDialog" title="连接局域网 Android 设备" width="520px">
      <el-alert type="info" :closable="false" style="margin-bottom:16px">
        <template #title>对方手机需要先开启 WiFi 调试</template>
        <div style="font-size:12px;line-height:1.8;margin-top:4px">
          1. 手机用 <b>USB</b> 连接到自己电脑<br/>
          2. 在自己电脑终端执行：<code>adb tcpip 5555</code><br/>
          3. 拔掉 USB（WiFi 调试已开启）<br/>
          4. 查看手机 WiFi 设置中的 <b>IP 地址</b><br/>
          5. 把 IP 告诉你，在下方输入连接
        </div>
      </el-alert>
      <el-form label-width="60px">
        <el-form-item label="IP 地址"><el-input v-model="networkForm.ip" placeholder="如：192.168.1.100" /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="networkForm.port" :min="1" :max="65535" /></el-form-item>
      </el-form>
      <div v-if="networkDevices.length > 0" style="margin-top:12px">
        <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:#303133">已连接的局域网设备</div>
        <div v-for="d in networkDevices" :key="d.id" style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#f5f7fa;margin-bottom:6px">
          <div>
            <span style="font-size:13px">{{ d.name || d.device_id }}</span>
            <span style="font-size:11px;color:#909399;margin-left:8px">{{ d.ip_address }}:{{ d.port }}</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            <el-tag :type="d.status==='online'||d.status==='available'?'success':'danger'" size="small">{{ d.status }}</el-tag>
            <el-button v-if="d.status==='offline'" size="small" type="success" @click="reconnectDialogDevice(d)" :loading="dialogConnecting[d.id]">连接</el-button>
            <el-button v-else size="small" type="danger" @click="disconnectDevice(d)" :loading="dialogDisconnecting[d.id]">断开</el-button>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showNetworkDialog = false">关闭</el-button>
        <el-button type="primary" @click="connectNetwork" :loading="connecting">连接</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showFolderDialog" :title="folderDialogMode === 'create' ? '新建文件夹' : '重命名文件夹'" width="420px">
      <el-form label-width="90px" @submit.prevent>
        <el-form-item label="名称">
          <el-input v-model="folderDialogForm.name" placeholder="输入文件夹名称" maxlength="50" @keyup.enter="submitFolder" />
        </el-form-item>
        <el-form-item v-if="folderDialogMode === 'create'" label="所属项目">
          <el-select v-model="folderDialogForm.project" placeholder="不选则为通用文件夹" clearable style="width:100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFolderDialog = false">取消</el-button>
        <el-button type="primary" @click="submitFolder" :loading="folderSaving">确定</el-button>
      </template>
    </el-dialog>

    <!-- 录制明细抽屉 -->
    <el-drawer v-model="showReplayDetail" :title="`录制明细${selectedReplay ? '：' + (selectedReplay.name || '未命名') : ''}`" size="48%">
      <div v-if="!selectedReplay" style="color:#909399;font-size:13px">暂无录制数据</div>
      <div v-else class="ms-detail">
        <div class="ms-detail__head">
          <span v-if="selectedReplay.result" class="ms-detail__result">{{ selectedReplay.result }}</span>
          <span v-if="selectedReplay.device?.name" class="ms-detail__meta">
            {{ selectedReplay.device.platform }} · {{ selectedReplay.device.name }}
            <template v-if="selectedReplay.device.resolution"> · {{ selectedReplay.device.resolution.width }}x{{ selectedReplay.device.resolution.height }}</template>
          </span>
          <span v-if="selectedReplay.recorded_at" class="ms-detail__meta">{{ selectedReplay.recorded_at?.substring(0, 19).replace('T', ' ') }}</span>
        </div>
        <div v-for="(s, si) in (selectedReplay.steps || [])" :key="si" class="ms-detail-step">
          <div class="ms-detail-step__head">
            <span class="ms-detail-step__no">步骤 {{ si + 1 }}</span>
            <span class="ms-detail-step__text">{{ s?.instruction || '（未录制）' }}</span>
            <el-tag v-if="s?.actions?.length" size="small">{{ s.actions.length }} 个动作</el-tag>
            <el-tag v-else-if="s?.after_hash" size="small" type="info">跳过</el-tag>
            <el-button v-if="s?.type !== 'branch'" size="small" text type="primary" @click.stop="openRerunStep(si)">重录</el-button>
            <el-button v-if="s?.type === 'branch' && branchHasElse(si)" size="small" text type="warning" @click.stop="openRerunElse(si)">补录 else</el-button>
          </div>
          <div v-if="s?.after_hash" class="ms-detail-step__meta">校验指纹 after_hash: {{ s.after_hash }}</div>
          <div v-if="s?.actions?.length" class="ms-detail-actions">
            <div v-for="(a, ai) in s.actions" :key="ai" class="ms-detail-action">
              <el-tag size="small" :type="a.conditional ? 'warning' : 'primary'" class="ms-detail-action__type">{{ a.action }}</el-tag>
              <el-tag v-if="a.conditional" size="small" type="warning" effect="plain">障碍动作</el-tag>
              <span class="ms-detail-action__desc">{{ actionDesc(a) }}</span>
              <span class="ms-detail-action__meta">等待 {{ a.wait_after }}s</span>
              <span v-if="a.before_hash" class="ms-detail-action__meta">前置 {{ String(a.before_hash).slice(0, 8) }}…</span>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- 单步重录 -->
    <!-- 补录 else -->
    <el-dialog v-model="showRerunElseDialog" title="补录 else" width="480px">
      <div class="ms-rerun">
        <div class="ms-rerun__step">分支 {{ rerunElseBranchIndex + 1 }}：{{ rerunElseBranchText || '' }}</div>
        <p class="ms-rerun__hint">请先把设备带到 else 态（条件不满足）页面，确认后只重录该分支的否则子步骤，if 组与其他步骤保持不变。</p>
        <div class="ms-rerun__row">
          <span class="ms-rerun__label">重录设备</span>
          <el-select v-model="rerunElseDeviceId" size="small" class="ms-select" style="flex:1">
            <el-option v-for="d in rerunDevices" :key="d.id"
              :label="`${d.name || d.device_id}（${d.platform}）`" :value="d.id" :disabled="d.status === 'offline'" />
          </el-select>
        </div>
        <div class="ms-rerun__row">
          <span class="ms-rerun__label">目标脚本</span>
          <span class="ms-rerun__meta">{{ selectedReplay?.name || '未命名' }}</span>
        </div>
      </div>
      <template #footer>
        <el-button size="small" @click="showRerunElseDialog = false">取消</el-button>
        <el-button size="small" type="warning" :loading="rerunElseStarting" @click="startRerunElse">我已在 else 态准备，开始补录</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRerunStepDialog" title="单步重录" width="480px">
      <div class="ms-rerun">
        <div class="ms-rerun__step">步骤 {{ rerunStepIndex + 1 }}：{{ rerunStepText || '（未录制）' }}</div>
        <p class="ms-rerun__hint">请先在设备上把页面带到该步骤执行前的状态（不会自动启动、清理数据），再开始录制。录制只覆盖该步骤，其余步骤保持不变。</p>
        <div class="ms-rerun__row">
          <span class="ms-rerun__label">重录设备</span>
          <el-select v-model="rerunStepDeviceId" size="small" class="ms-select" style="flex:1">
            <el-option v-for="d in rerunDevices" :key="d.id"
              :label="`${d.name || d.device_id}（${d.platform}）`" :value="d.id" :disabled="d.status === 'offline'" />
          </el-select>
        </div>
        <div class="ms-rerun__row">
          <span class="ms-rerun__label">目标脚本</span>
          <span class="ms-rerun__meta">{{ selectedReplay?.name || '未命名' }}</span>
        </div>
      </div>
      <template #footer>
        <el-button size="small" @click="showRerunStepDialog = false">取消</el-button>
        <el-button size="small" type="primary" :loading="rerunStarting" @click="startRerunStep">我已在设备上准备好，开始录制</el-button>
      </template>
    </el-dialog>

    <!-- 设备匹配提醒 -->
    <el-dialog v-model="deviceMatchDialog.show" title="设备匹配提醒" width="540px">
      <div class="ms-match">
        <div class="ms-match__row">
          <span class="ms-match__label">当前设备</span>
          <span>{{ deviceMatchDialog.current?.model || '未命名' }}（{{ deviceMatchDialog.current?.platform }} · {{ deviceMatchDialog.current?.resolution || '分辨率未知' }}）</span>
        </div>
        <div class="ms-match__row">
          <span class="ms-match__label">选中脚本</span>
          <span>录制于 {{ deviceMatchDialog.selected?.device?.name || '未知设备' }}（{{ deviceMatchDialog.selected?.device?.platform }} · {{ fmtRes(deviceMatchDialog.selected?.device?.resolution) }}）</span>
        </div>
        <template v-if="deviceMatchDialog.matching?.length">
          <div class="ms-match__hint">检测到更匹配的脚本，可切换后执行：</div>
          <el-radio-group v-model="deviceMatchDialog.pickIndex">
            <el-radio v-for="m in deviceMatchDialog.matching" :key="m.index" :label="m.index" class="ms-match__radio">
              {{ m.name || '未命名' }}（{{ m.device?.name || '未知设备' }} · {{ fmtRes(m.device?.resolution) }}）
            </el-radio>
          </el-radio-group>
        </template>
        <div v-else class="ms-match__hint">脚本与当前设备不匹配（坐标可能偏移），可以重新录制，或仍用当前脚本尝试执行。</div>
      </div>
      <template #footer>
        <el-button @click="deviceMatchDialog.show = false">取消</el-button>
        <el-button v-if="deviceMatchDialog.matching?.length" type="primary" @click="executeWithMatch">用匹配脚本</el-button>
        <el-button v-else @click="goRecordMode">去录制</el-button>
        <el-button type="danger" plain @click="executeAnyway">仍要执行</el-button>
      </template>
    </el-dialog>

    <!-- 多设备批量匹配提醒 -->
    <el-dialog v-model="batchMatchDialog.show" title="多设备匹配结果" width="620px">
      <div class="ms-match">
        <div v-for="row in batchMatchDialog.rows" :key="row.device_id" class="ms-match__row ms-match__row--batch">
          <span class="ms-match__label">{{ row.device_name || ('设备 ' + row.device_id) }}</span>
          <span class="ms-match__cell">
            <el-tag :type="matchTagType(row.match_level)" size="small">{{ matchLevelText(row.match_level) }}</el-tag>
            <template v-if="row.error">
              <span class="ms-match__hint" style="display:inline">{{ row.error }}</span>
            </template>
            <template v-else-if="!row.has_match">
              <span class="ms-match__hint">无匹配脚本，将回退使用当前脚本并提示风险</span>
            </template>
            <template v-else-if="row.needs_switch">
              <span class="ms-match__cell--sub">推荐：{{ row.recommended_name || '未命名' }}（当前：{{ row.current_name || '未命名' }}）</span>
            </template>
            <template v-else>
              <span class="ms-match__cell--sub">{{ row.current_name || '未命名' }}</span>
            </template>
          </span>
        </div>
        <div class="ms-match__hint">每台设备将使用各自最匹配的脚本执行（无匹配脚本的设备回退用当前脚本并提示风险）。</div>
      </div>
      <template #footer>
        <el-button @click="batchMatchDialog.show = false">取消</el-button>
        <el-button @click="executeBatchWithCurrent">仍用当前脚本</el-button>
        <el-button type="primary" @click="executeBatchWithMatch">用各自匹配脚本</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
// ====== Entire script unchanged ======
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, MagicStick, DocumentAdd, VideoPlay, SwitchButton, Refresh, Connection, ArrowRight, Folder, FolderAdd, EditPen, View } from '@element-plus/icons-vue'
import api from '@/utils/api'
import MsLoading from '@/components/MsLoading.vue'
import { parsePrompt, serialize, validate } from './midsceneSteps.mjs'

const cases = ref([])
const folders = ref([])
const projects = ref([])
const currentCaseId = ref(null)
const visionModels = ref([])
const devices = ref([])
const selectedDeviceIds = ref([])
const saving = ref(false)
const executing = ref(false)
const discovering = ref(false)
const showNetworkDialog = ref(false)
const connecting = ref(false)
const dialogConnecting = reactive({})
const dialogDisconnecting = reactive({})
const networkForm = reactive({ ip: '', port: 5555 })
const autoPlanMode = ref(false)
const recordMode = ref(false)
const replayMode = ref(false)
const clearAppData = ref(false)
const installPackages = ref([])
const androidPackages = computed(() => installPackages.value.filter(p => p.platform === 'android'))
const iosPackages = computed(() => installPackages.value.filter(p => p.platform === 'ios'))
const selectedInstallPackageId = ref(null)
const midsceneConfig = ref({ use_locate: null, use_deep_locate: '' })
const filterProjectId = ref(null)
const expandedFolders = ref([])
const activeFolderId = ref(null)
const showFolderDialog = ref(false)
const folderDialogMode = ref('create')
const folderDialogForm = reactive({ id: null, name: '', project: null })
const folderSaving = ref(false)

const isIosDevice = computed(() => {
  if (selectedDeviceIds.value.length === 0) return false
  return selectedDeviceIds.value.some(id => devices.value.find(d => d.id === id)?.platform === 'ios')
})
const filteredCases = computed(() => {
  if (!filterProjectId.value) return cases.value
  return cases.value.filter(c => c.project === filterProjectId.value)
})
const filteredFolders = computed(() => {
  if (!filterProjectId.value) return folders.value
  return folders.value.filter(f => f.project === filterProjectId.value)
})
const uncategorizedCases = computed(() => {
  return cases.value.filter(c => !c.folder && (!filterProjectId.value || c.project === filterProjectId.value))
})
const folderOptions = computed(() => {
  if (!form.project_id) return folders.value
  return folders.value.filter(f => !f.project || f.project === form.project_id)
})
const getFolderCases = (folderId) => cases.value.filter(c => c.folder === folderId && (!filterProjectId.value || c.project === filterProjectId.value))
const getFolderCount = (folderId) => getFolderCases(folderId).length
const isFolderOpen = (folderId) => expandedFolders.value.includes(folderId)
const toggleFolder = (folderId) => {
  activeFolderId.value = folderId
  expandedFolders.value = expandedFolders.value.includes(folderId)
    ? expandedFolders.value.filter(id => id !== folderId)
    : [...expandedFolders.value, folderId]
}
const railItems = computed(() => {
  const items = []
  for (const f of filteredFolders.value) {
    items.push({ type: 'folder', folder: f })
    if (isFolderOpen(f.id)) {
      getFolderCases(f.id).forEach((c, i) => items.push({ type: 'case', case: c, inFolder: true, idx: i + 1 }))
    }
  }
  if (filteredFolders.value.length > 0) {
    items.push({ type: 'divider', label: '未分组', count: uncategorizedCases.value.length })
    uncategorizedCases.value.forEach((c, i) => items.push({ type: 'case', case: c, inFolder: false, idx: i + 1 }))
  } else {
    uncategorizedCases.value.forEach((c, i) => items.push({ type: 'case', case: c, inFolder: false, idx: i + 1 }))
  }
  return items
})
const getProjectName = (projectId) => {
  if (!projectId) return ''
  return projects.value.find(p => p.id === projectId)?.name || ''
}
const caseStatusClass = (c) => {
  if (!c.latest_result) return 'never'
  return c.latest_result.status === 'passed' ? 'passed' : 'failed'
}
const form = reactive({
  name: '', project_id: null, folder_id: null, ai_prompt: '', ai_model_config_id: null,
  max_steps: 30, action_delay: 0.5, app_package: '', ai_act_context: '',
})

// ---- PROCEDURE 结构化步骤编辑器（列表 <-> 原始文本） ----
const editorMode = ref('list') // 'list' | 'raw'
const stepItems = ref([])
const stepErrors = ref('')
let _eid = 0
const nid = () => 'e' + (++_eid)
const newStep = () => ({ id: nid(), kind: 'step', text: '', repeat: false })
const newChild = () => ({ id: nid(), kind: 'child', text: '', repeat: false })
const newBranch = () => ({ id: nid(), kind: 'branch', prefix: '如果', condition: '', repeat: false, children: [], elseChildren: [] })

const updateStepsFromPrompt = () => {
  try {
    stepItems.value = parsePrompt(form.ai_prompt)
    stepErrors.value = ''
    return true
  } catch (e) {
    stepItems.value = []
    stepErrors.value = e.message || '步骤解析失败'
    editorMode.value = 'raw'
    return false
  }
}
const syncPrompt = () => { form.ai_prompt = serialize(stepItems.value) }
const syncError = () => {
  const v = validate(stepItems.value)
  stepErrors.value = v.ok ? '' : v.errors.join('；')
}
const syncAll = () => { syncPrompt(); syncError() }
const promptValid = computed(() => {
  try { return validate(parsePrompt(form.ai_prompt)).ok } catch (e) { return false }
})
const dragKey = ref(null)
const dragOverKey = ref(null)
const groupOf = (row) => {
  if (row.kind === 'branch' || row.kind === 'step') return 'top'
  if (row.kind === 'child') return (row.elseSide ? 'else:' : 'if:') + row.branchId
  return null // elseMarker 不可拖
}
const dragDisabled = (row) => row.kind === 'elseMarker'
const canDrop = (src, tgt) => {
  if (!src || !tgt) return false
  if (dragDisabled(src) || dragDisabled(tgt)) return false
  return groupOf(src) === groupOf(tgt)
}
const onDragStart = (row, ev) => {
  if (dragDisabled(row)) { ev.preventDefault(); return }
  dragKey.value = row.key
  ev.dataTransfer.effectAllowed = 'move'
  ev.dataTransfer.setData('text/plain', row.key)
}
const onDragOver = (row, ev) => {
  if (!canDrop(rowAt(dragKey.value), row)) return
  ev.preventDefault()
  ev.dataTransfer.dropEffect = 'move'
  dragOverKey.value = row.key
}
const onDrop = (row, ev) => {
  ev.preventDefault()
  const src = rowAt(dragKey.value)
  dragOverKey.value = null
  dragKey.value = null
  if (!src || !canDrop(src, row)) return
  if (src.key === row.key) return
  reorderByRow(src, row)
  syncAll()
}
const onDragEnd = () => { dragKey.value = null; dragOverKey.value = null }
const rowAt = (key) => stepRows.value.find((r) => r.key === key) || null
const reorderByRow = (src, tgt) => {
  const g = groupOf(src)
  const grab = (arr) => { const i = arr.findIndex((x) => x.id === src.it.id); return i >= 0 ? arr.splice(i, 1)[0] : null }
  if (g === 'top') {
    const item = grab(stepItems.value)
    if (!item) return
    const insertAt = stepItems.value.findIndex((x) => x === tgt.it)
    stepItems.value.splice(insertAt === -1 ? stepItems.value.length : insertAt, 0, item)
  } else if (g === 'if:' + src.branchId || g === 'else:' + src.branchId) {
    const b = stepItems.value.find((x) => x.id === src.branchId)
    if (!b) return
    const arr = g.startsWith('else:') ? (b.elseChildren = b.elseChildren || []) : b.children
    const item = grab(arr)
    if (!item) return
    const insertAt = arr.findIndex((x) => x === tgt.it)
    arr.splice(insertAt === -1 ? arr.length : insertAt, 0, item)
  }
}
const stepRows = computed(() => {
  const rows = []
  let n = 0
  stepItems.value.forEach((it, idx) => {
    if (it.kind === 'branch') {
      n += 1
      rows.push({ key: it.id, kind: 'branch', num: n, it, idx, branchId: it.id })
      it.children.forEach((c, cidx) => {
        n += 1
        rows.push({ key: c.id, kind: 'child', num: n, it: c, idx, cidx, branchId: it.id })
      })
      const ec = it.elseChildren || []
      if (ec.length) {
        rows.push({ key: it.id + '_else', kind: 'elseMarker', it, idx, branchId: it.id })
        ec.forEach((c, cidx) => {
          n += 1
          rows.push({ key: c.id, kind: 'child', num: n, it: c, idx, cidx, branchId: it.id, elseSide: true })
        })
      }
    } else {
      n += 1
      rows.push({ key: it.id, kind: 'step', num: n, it, idx })
    }
  })
  return rows
})

const addStep = () => { stepItems.value.push(newStep()); syncAll() }
const addBranch = () => { const b = newBranch(); b.children.push(newChild()); stepItems.value.push(b); syncAll() }
const addChild = (branchId) => {
  const b = stepItems.value.find((x) => x.id === branchId)
  if (b) { b.children.push(newChild()); syncAll() }
}
const addElseChild = (branchId) => {
  const b = stepItems.value.find((x) => x.id === branchId)
  if (b) { (b.elseChildren = b.elseChildren || []).push(newChild()); syncAll() }
}
const removeElseChild = (branchId, cidx) => {
  const b = stepItems.value.find((x) => x.id === branchId)
  if (b) { (b.elseChildren || []).splice(cidx, 1); syncAll() }
}
const moveElseChild = (branchId, cidx, dir) => {
  const b = stepItems.value.find((x) => x.id === branchId)
  if (!b) return
  const arr = b.elseChildren = b.elseChildren || []
  const to = cidx + dir
  if (to < 0 || to >= arr.length) return
  const tmp = arr[cidx]; arr[cidx] = arr[to]; arr[to] = tmp
  syncAll()
}
const outdentElseChild = (branchId, cidx) => {
  const b = stepItems.value.find((x) => x.id === branchId)
  if (!b) return
  const c = (b.elseChildren || []).splice(cidx, 1)[0]
  const bi = stepItems.value.indexOf(b)
  stepItems.value.splice(bi + 1, 0, { id: c.id, kind: 'step', text: c.text, repeat: c.repeat })
  syncAll()
}
const removeStep = (idx) => { stepItems.value.splice(idx, 1); syncAll() }
const removeChild = (branchId, cidx) => {
  const b = stepItems.value.find((x) => x.id === branchId)
  if (b) { b.children.splice(cidx, 1); syncAll() }
}
const moveTop = (idx, dir) => {
  const arr = stepItems.value
  const to = idx + dir
  if (to < 0 || to >= arr.length) return
  const tmp = arr[idx]; arr[idx] = arr[to]; arr[to] = tmp
  syncAll()
}
const moveChild = (branchId, cidx, dir) => {
  const b = stepItems.value.find((x) => x.id === branchId)
  if (!b) return
  const to = cidx + dir
  if (to < 0 || to >= b.children.length) return
  const tmp = b.children[cidx]; b.children[cidx] = b.children[to]; b.children[to] = tmp
  syncAll()
}
const indentStep = (idx) => {
  if (idx > 0 && stepItems.value[idx - 1].kind === 'branch') {
    const br = stepItems.value[idx - 1]
    const it = stepItems.value[idx]
    stepItems.value.splice(idx, 1)
    br.children.push(it)
    syncAll()
  }
}
const outdentChild = (branchId, cidx) => {
  const b = stepItems.value.find((x) => x.id === branchId)
  if (!b) return
  const c = b.children.splice(cidx, 1)[0]
  const bi = stepItems.value.indexOf(b)
  stepItems.value.splice(bi + 1, 0, { id: c.id, kind: 'step', text: c.text, repeat: c.repeat })
  syncAll()
}
const onEdit = () => syncAll()
const toggleRaw = () => {
  if (editorMode.value === 'list') {
    editorMode.value = 'raw'
  } else if (updateStepsFromPrompt()) {
    editorMode.value = 'list'
  }
}
const showAiGen = ref(false)
const aiDesc = ref('')
const genLoading = ref(false)
const executions = ref([])
const activeExecIndex = ref('0')
const activeExec = computed(() => executions.value[Number(activeExecIndex.value)] || null)
const showPreview = ref(false)
const previewImage = ref('')
const previewAfterImage = ref('')
const previewStepData = ref(null)
let pollTimer = null
let pollCaseId = null
const androidDevices = computed(() => devices.value.filter(d => d.platform === 'android' && d.status !== 'offline'))
const iosDevices = computed(() => devices.value.filter(d => d.platform === 'ios' && d.status !== 'offline'))
const networkDevices = computed(() => devices.value.filter(d => d.platform === 'android' && d.ip_address))
const isRunning = computed(() => executions.value.some(e => ['pending', 'running'].includes(e.status)))
const isExecRunning = (exec) => !!exec && ['pending', 'running'].includes(exec.status)
const canExecute = computed(() => form.ai_prompt && selectedDeviceIds.value.length > 0 && form.ai_model_config_id && promptValid.value)
const selectedReplayIndex = ref(0)
const showReplayDetail = ref(false)
const replayList = computed(() => {
  if (!currentCaseId.value) return []
  const c = cases.value.find(c => c.id === currentCaseId.value)
  if (!c?.replay_data) return []
  if (Array.isArray(c.replay_data)) return c.replay_data
  return [c.replay_data]
})
const selectedReplay = computed(() => replayList.value[selectedReplayIndex.value] || null)
const deviceMatchDialog = reactive({ show: false, current: null, selected: null, matching: [], pickIndex: null })
const batchMatchDialog = reactive({ show: false, rows: [], perDeviceIndex: {} })
const forceExecuteFlag = ref(false)
const batchMatchConfirmed = ref(false)
const fmtRes = (res) => {
  if (!res) return '分辨率未知'
  if (typeof res === 'string') return res
  return `${res.width}x${res.height}`
}
const checkReplayMatch = async () => {
  try {
    const { data } = await api.get(`/ui-automation/midscene/cases/${currentCaseId.value}/replay_match/`, {
      params: { device_id: selectedDeviceIds.value[0], replay_index: selectedReplayIndex.value },
    })
    if (['exact', 'ok', 'unknown'].includes(data.match_level)) return true
    deviceMatchDialog.current = data.current_device
    deviceMatchDialog.selected = data.selected
    deviceMatchDialog.matching = data.matching || []
    deviceMatchDialog.pickIndex = deviceMatchDialog.matching[0]?.index ?? null
    deviceMatchDialog.show = true
    return false
  } catch (e) {
    ElMessage.warning('设备匹配检查失败，将直接执行')
    return true
  }
}
const matchLevelText = (level) => ({ exact: '完全匹配', ok: '基本匹配', unknown: '分辨率未知', no_match: '无匹配脚本', resolution_mismatch: '分辨率不匹配', platform_mismatch: '平台不匹配' }[level] || level || '未知')
const matchTagType = (level) => ({ exact: 'success', ok: 'success', unknown: 'info', no_match: 'danger', resolution_mismatch: 'warning', platform_mismatch: 'danger' }[level] || 'info')
const deviceNameById = (id) => {
  const d = devices.value.find(x => x.id === id)
  return d?.name || d?.device_id || ''
}
const replayIndexForDevice = (deviceId) => batchMatchDialog.perDeviceIndex[deviceId] ?? selectedReplayIndex.value
const checkReplayMatchBatch = async () => {
  try {
    const { data } = await api.post(`/ui-automation/midscene/cases/${currentCaseId.value}/replay_match_batch/`, {
      devices: selectedDeviceIds.value,
      replay_index: selectedReplayIndex.value,
    })
    const rows = (data.results || []).map(r => ({
      device_id: r.device_id,
      device_name: r.device_name || deviceNameById(r.device_id),
      match_level: r.match_level || 'unknown',
      current_index: r.current_index ?? selectedReplayIndex.value,
      current_name: r.current_name || '',
      recommended_index: r.recommended_index ?? selectedReplayIndex.value,
      recommended_name: r.recommended_name || '',
      needs_switch: !!r.needs_switch,
      has_match: r.has_match !== false,
      error: r.error,
    }))
    batchMatchDialog.rows = rows
    batchMatchDialog.perDeviceIndex = {}
    rows.forEach(r => { if (!r.error) batchMatchDialog.perDeviceIndex[r.device_id] = r.recommended_index })
    const allFine = rows.length > 0 && rows.every(r => !r.error && r.has_match && !r.needs_switch)
    if (allFine) return true
    batchMatchDialog.show = true
    return false
  } catch (e) {
    ElMessage.warning('设备匹配检查失败，将直接执行')
    return true
  }
}
const executeWithMatch = () => {
  deviceMatchDialog.show = false
  if (deviceMatchDialog.pickIndex !== null && deviceMatchDialog.pickIndex !== undefined) {
    selectedReplayIndex.value = deviceMatchDialog.pickIndex
  }
  doExecute()
}
const executeAnyway = () => {
  deviceMatchDialog.show = false
  forceExecuteFlag.value = true
  doExecute()
}
const goRecordMode = () => {
  deviceMatchDialog.show = false
  recordMode.value = true
  replayMode.value = false
  ElMessage.info('已切换为录制模式，点击执行开始录制')
}
const executeBatchWithMatch = () => {
  batchMatchDialog.show = false
  batchMatchConfirmed.value = true
  doExecute()
}
const executeBatchWithCurrent = () => {
  batchMatchDialog.perDeviceIndex = {}
  batchMatchDialog.show = false
  batchMatchConfirmed.value = true
  doExecute()
}
const fmtNum = (v) => (v === undefined || v === null || v === '') ? '?' : v
const actionDesc = (a) => {
  if (!a) return ''
  const t = a.action
  if (t === 'input') return `文本: ${a.text || ''}`
  if (t === 'swipe') return `(${fmtNum(a.x1_pct)}%,${fmtNum(a.y1_pct)}%) → (${fmtNum(a.x2_pct)}%,${fmtNum(a.y2_pct)}%)`
  if (['tap', 'click', 'long_press'].includes(t)) return `(${fmtNum(a.x_pct)}%,${fmtNum(a.y_pct)}%) px(${fmtNum(a.x)},${fmtNum(a.y)})`
  return t
}
const statusTagType = computed(() => {
  const m = { pending: 'info', running: 'warning', stopping: 'warning', passed: 'success', failed: 'danger', error: 'danger', stopped: 'info' }
  return m[activeExec.value?.status] || 'info'
})
const draftId = '__draft__'

const loadCases = async () => { try { const { data } = await api.get('/ui-automation/midscene/cases/'); cases.value = data.results || [] } catch (e) {} }
const loadFolders = async () => { try { const { data } = await api.get('/ui-automation/midscene/folders/'); folders.value = data.results || [] } catch (e) {} }
const loadProjects = async () => { try { const { data } = await api.get('/ui-automation/midscene/projects/'); projects.value = data.results || [] } catch (e) {} }
const loadDevices = async () => { try { const { data } = await api.get('/ui-automation/midscene/devices/'); devices.value = data.results || [] } catch (e) {} }
const loadInstallPackages = async () => { try { const { data } = await api.get('/ui-automation/midscene/packages/'); installPackages.value = data.results || [] } catch (e) {} }
const onInstallPackageChange = (val) => { const pkg = installPackages.value.find(p => p.id === val); if (!pkg) return; clearAppData.value = pkg.platform === 'android'; if (isIosDevice.value && pkg.platform === 'ios') ElMessage.info('iOS 覆盖安装并保留数据，不执行清除数据') }
const loadMidsceneConfig = async () => {
  try {
    const { data } = await api.get('/ui-automation/midscene/config/')
    midsceneConfig.value = {
      use_locate: data.config?.use_locate === null || data.config?.use_locate === undefined
        ? '' : String(data.config.use_locate),
      use_deep_locate: data.config?.use_deep_locate || '',
      effective: data.effective,
    }
  } catch (e) {}
}
const saveMidsceneConfig = async () => {
  try {
    const { data } = await api.put('/ui-automation/midscene/config/', {
      use_locate: midsceneConfig.value.use_locate === '' ? null
        : midsceneConfig.value.use_locate === 'true',
      use_deep_locate: midsceneConfig.value.use_deep_locate || '',
    })
    midsceneConfig.value = {
      use_locate: data.config?.use_locate === null || data.config?.use_locate === undefined
        ? '' : String(data.config.use_locate),
      use_deep_locate: data.config?.use_deep_locate || '',
      effective: data.effective,
    }
    ElMessage.success('AI引擎配置已保存')
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
    loadMidsceneConfig()
  }
}
const loadVisionModels = async () => {
  try { const { data } = await api.get('/requirement-analysis/ai-models/'); visionModels.value = (data.results || data || []).filter(m => m.role === 'app_automation_vision' && m.is_active); if (visionModels.value.length > 0 && !form.ai_model_config_id) form.ai_model_config_id = visionModels.value[0].id } catch (e) {}
}
const discoverDevices = async () => {
  discovering.value = true
  try {
    const results = await Promise.allSettled([api.post('/ui-automation/midscene/devices/discover_android/'), api.post('/ui-automation/midscene/devices/discover_ios/')])
    const ok = [results[0].status === 'fulfilled', results[1].status === 'fulfilled']
    if (ok[0] || ok[1]) { const parts = []; if (ok[0]) parts.push('Android'); if (ok[1]) parts.push('iOS'); ElMessage.success(`${parts.join(' + ')} 扫描完成`) }
    else ElMessage.warning('未发现设备')
    await loadDevices()
  } catch (e) { ElMessage.error('扫描失败: ' + (e.response?.data?.error || e.message)) }
  finally { discovering.value = false }
}
const deleteReplayEntry = async () => {
  if (!currentCaseId.value) return
  try { await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' }); await api.post(`/ui-automation/midscene/cases/${currentCaseId.value}/delete_replay/`, { index: selectedReplayIndex.value }); if (selectedReplayIndex.value > 0) selectedReplayIndex.value--; await loadCases(); ElMessage.success('已删除') } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}
const renameReplayEntry = async () => {
  if (!currentCaseId.value) return
  const cur = replayList.value[selectedReplayIndex.value]
  try {
    const { value } = await ElMessageBox.prompt('输入录制名称，用于在回放下拉中快速区分', '重命名录制', {
      inputValue: cur?.name || '',
      inputValidator: (v) => (v || '').trim() ? true : '名称不能为空',
    })
    await api.post(`/ui-automation/midscene/cases/${currentCaseId.value}/rename_replay/`, { index: selectedReplayIndex.value, name: value.trim() })
    await loadCases()
    ElMessage.success('已重命名')
  } catch (e) { if (e !== 'cancel') ElMessage.error('重命名失败') }
}
const showRerunStepDialog = ref(false)
const rerunStepIndex = ref(0)
const rerunStepDeviceId = ref(null)
const rerunStarting = ref(false)
const rerunStepText = computed(() => selectedReplay.value?.steps?.[rerunStepIndex.value]?.instruction || '')
const rerunDevices = computed(() => devices.value.filter(d => d.status !== 'offline'))
const openRerunStep = (si) => {
  rerunStepIndex.value = si
  rerunStepDeviceId.value = selectedDeviceIds.value[0] || rerunDevices.value[0]?.id || null
  showRerunStepDialog.value = true
}
const startRerunStep = async () => {
  if (!currentCaseId.value) { ElMessage.warning('请先选择用例'); return }
  if (!rerunStepDeviceId.value) { ElMessage.warning('请选择重录设备'); return }
  rerunStarting.value = true
  try {
    const { data } = await api.post(`/ui-automation/midscene/cases/${currentCaseId.value}/rerun_step/`, {
      replay_index: selectedReplayIndex.value,
      step_index: rerunStepIndex.value,
      device_id: rerunStepDeviceId.value,
    })
    showRerunStepDialog.value = false
    executions.value.push({
      id: data.execution_id,
      task_id: data.task_id,
      device_id: rerunStepDeviceId.value,
      device_name: deviceNameById(rerunStepDeviceId.value),
      replay_index: selectedReplayIndex.value,
      rerun_mark: `重录步骤 ${rerunStepIndex.value + 1}`,
      status: 'pending',
      status_display: '待执行',
      progress: 0,
      total_steps: selectedReplay.value?.steps?.length || 0,
      steps_detail: [],
      passed_steps: 0,
      failed_steps: 0,
      screenshot: '',
      reasoning: [],
      step: 0,
    })
    activeExecIndex.value = String(executions.value.length - 1)
    startPolling()
    ElMessage.success(`已开始重录步骤 ${rerunStepIndex.value + 1}，请保持设备页面不变直到完成`)
  } catch (e) {
    ElMessage.error('重录启动失败: ' + (e.response?.data?.error || e.message))
  } finally {
    rerunStarting.value = false
  }
}
const branchHasElse = (si) => {
  // 依据当前脚本的 ai_prompt 解析，判断该步骤是否为「含 else 组」的分支头
  try {
    const items = parsePrompt(form.ai_prompt || '')
    let leaf = 0
    const walk = (list) => {
      for (const it of list) {
        if (it.kind === 'branch') {
          if (leaf === si) return (it.elseChildren || []).length > 0
          leaf += 1
          for (const c of it.children || []) { if (leaf === si) return false; leaf += 1 }
          for (const c of it.elseChildren || []) { if (leaf === si) return false; leaf += 1 }
        } else {
          if (leaf === si) return false
          leaf += 1
        }
      }
      return false
    }
    return walk(items)
  } catch (e) { return false }
}
const showRerunElseDialog = ref(false)
const rerunElseBranchIndex = ref(0)
const rerunElseDeviceId = ref(null)
const rerunElseStarting = ref(false)
const rerunElseBranchText = computed(() => selectedReplay.value?.steps?.[rerunElseBranchIndex.value]?.instruction || '')
const openRerunElse = (si) => {
  rerunElseBranchIndex.value = si
  rerunElseDeviceId.value = selectedDeviceIds.value[0] || rerunDevices.value[0]?.id || null
  showRerunElseDialog.value = true
}
const startRerunElse = async () => {
  if (!currentCaseId.value) { ElMessage.warning('请先选择用例'); return }
  if (!rerunElseDeviceId.value) { ElMessage.warning('请选择重录设备'); return }
  rerunElseStarting.value = true
  try {
    const { data } = await api.post(`/ui-automation/midscene/cases/${currentCaseId.value}/rerun_else/`, {
      replay_index: selectedReplayIndex.value,
      branch_step_index: rerunElseBranchIndex.value,
      device_id: rerunElseDeviceId.value,
    })
    showRerunElseDialog.value = false
    executions.value.push({
      id: data.execution_id,
      task_id: data.task_id,
      device_id: rerunElseDeviceId.value,
      device_name: deviceNameById(rerunElseDeviceId.value),
      replay_index: selectedReplayIndex.value,
      rerun_mark: `补录 else（分支 ${rerunElseBranchIndex.value + 1}）`,
      status: 'pending',
      status_display: '待执行',
      progress: 0,
      total_steps: selectedReplay.value?.steps?.length || 0,
      steps_detail: [],
      passed_steps: 0,
      failed_steps: 0,
      screenshot: '',
      reasoning: [],
      step: 0,
    })
    activeExecIndex.value = String(executions.value.length - 1)
    startPolling()
    ElMessage.success(`已开始补录分支 ${rerunElseBranchIndex.value + 1} 的 else，请保持设备 else 态页面不变`)
  } catch (e) {
    ElMessage.error('补录 else 启动失败: ' + (e.response?.data?.error || e.message))
  } finally {
    rerunElseStarting.value = false
  }
}
const connectNetwork = async () => {
  if (!networkForm.ip.trim()) { ElMessage.warning('请输入 IP'); return }
  connecting.value = true
  try { const { data } = await api.post('/ui-automation/midscene/devices/connect_network/', { ip: networkForm.ip.trim(), port: networkForm.port }); if (data.success) { ElMessage.success(data.message || '已连接'); networkForm.ip = ''; await loadDevices() } else ElMessage.error(data.message || '连接失败') }
  catch (e) { ElMessage.error(e.response?.data?.message || '连接失败') }
  finally { connecting.value = false }
}
const disconnectDevice = async (device) => { dialogDisconnecting[device.id] = true; try { await api.post(`/ui-automation/midscene/devices/${device.id}/disconnect_network/`); ElMessage.success('已断开'); await loadDevices() } catch (e) { ElMessage.error('断开失败') } finally { dialogDisconnecting[device.id] = false } }
const reconnectDialogDevice = async (device) => { dialogConnecting[device.id] = true; try { const { data } = await api.post('/ui-automation/midscene/devices/connect_network/', { ip: device.ip_address, port: device.port || 5555 }); if (data.success) ElMessage.success(data.message || '已连接'); else ElMessage.error(data.message || '连接失败'); await loadDevices() } catch (e) { ElMessage.error(e.response?.data?.message || '连接失败') } finally { dialogConnecting[device.id] = false } }
const newCase = () => {
  if (cases.value.some(c => c.id === draftId)) return
  stopPolling()
  currentCaseId.value = draftId
  cases.value.unshift({ id: draftId, name: '新建用例', ai_prompt: '', project: filterProjectId.value, folder: null, _draft: true })
  form.name = ''; form.ai_prompt = ''
  stepItems.value = []; stepErrors.value = ''; editorMode.value = 'list'
  form.project_id = filterProjectId.value || null
  const activeFolder = folders.value.find(f => f.id === activeFolderId.value)
  form.folder_id = activeFolder && (!activeFolder.project || !form.project_id || activeFolder.project === form.project_id) ? activeFolder.id : null
  recordMode.value = false; replayMode.value = false; clearAppData.value = false
  selectedInstallPackageId.value = null
}
const loadCase = (c) => {
  stopPolling(); currentCaseId.value = c.id; form.name = c.name; form.project_id = c.project; form.folder_id = c.folder
  form.ai_prompt = c.ai_prompt || ''; form.ai_model_config_id = c.ai_model_config; form.max_steps = c.max_steps || 30
  form.action_delay = c.action_delay || 0.5; form.app_package = c.app_package || ''; form.ai_act_context = c.ai_act_context || ''
  editorMode.value = 'list'
  updateStepsFromPrompt()
}
const openNewFolder = () => { folderDialogMode.value = 'create'; folderDialogForm.id = null; folderDialogForm.name = ''; folderDialogForm.project = filterProjectId.value || null; showFolderDialog.value = true }
const openRenameFolder = (f) => { folderDialogMode.value = 'rename'; folderDialogForm.id = f.id; folderDialogForm.name = f.name; folderDialogForm.project = f.project; showFolderDialog.value = true }
const submitFolder = async () => {
  if (!folderDialogForm.name.trim()) { ElMessage.warning('请输入文件夹名称'); return }
  folderSaving.value = true
  try {
    if (folderDialogMode.value === 'create') {
      const { data } = await api.post('/ui-automation/midscene/folders/', { name: folderDialogForm.name.trim(), project: folderDialogForm.project || null })
      expandedFolders.value.push(data.id)
      ElMessage.success('文件夹已创建')
    } else {
      await api.patch(`/ui-automation/midscene/folders/${folderDialogForm.id}/`, { name: folderDialogForm.name.trim() })
      ElMessage.success('已重命名')
    }
    showFolderDialog.value = false
    await loadFolders()
  } catch (e) { ElMessage.error('操作失败: ' + (e.response?.data?.error || e.message)) }
  finally { folderSaving.value = false }
}
const deleteFolder = async (f) => {
  try {
    await ElMessageBox.confirm(`删除文件夹「${f.name}」？文件夹内的 ${getFolderCount(f.id)} 个用例将移到未分组。`, '确认删除', { type: 'warning' })
    await api.delete(`/ui-automation/midscene/folders/${f.id}/`)
    if (activeFolderId.value === f.id) activeFolderId.value = null
    await loadFolders()
    ElMessage.success('已删除')
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}
const saveCase = async () => {
  if (!form.name.trim()) { ElMessage.warning('请输入用例名称'); return }
  if (!form.ai_prompt.trim()) { ElMessage.warning('请输入测试步骤'); return }
  if (!promptValid.value) { ElMessage.warning('步骤存在错误：' + (stepErrors.value || '请检查步骤')); return }
  saving.value = true
  try {
    const payload = { ...form }; const isDraft = currentCaseId.value === draftId
    if (currentCaseId.value && !isDraft) { await api.put(`/ui-automation/midscene/cases/${currentCaseId.value}/`, payload); ElMessage.success('已更新') }
    else { const { data } = await api.post('/ui-automation/midscene/cases/', payload); if (isDraft) { const idx = cases.value.findIndex(c => c.id === draftId); if (idx >= 0) cases.value.splice(idx, 1) }; currentCaseId.value = data.id; ElMessage.success('已保存') }
    await loadCases()
  } catch (e) { const data = e.response?.data; let errMsg = e.message; if (data && typeof data === 'object') { const msgs = []; Object.entries(data).forEach(([field, errors]) => { const vals = Array.isArray(errors) ? errors : [errors]; msgs.push(...vals.map(v => typeof v === 'string' ? `${field}: ${v}` : v)) }); if (msgs.length > 0) errMsg = msgs.join('; ') }; ElMessage.error('保存失败: ' + errMsg) }
  finally { saving.value = false }
}
const deleteCase = async (c) => { try { await ElMessageBox.confirm(`删除「${c.name}」？`, '确认删除', { type: 'warning' }); await api.delete(`/ui-automation/midscene/cases/${c.id}/`); if (currentCaseId.value === c.id) newCase(); await loadCases(); ElMessage.success('已删除') } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') } }
const getStepCount = (prompt) => { if (!prompt) return 0; return prompt.trim().split('\n').filter(l => l.trim()).length }
const generateSteps = async () => { if (!aiDesc.value.trim()) { ElMessage.warning('请输入场景描述'); return }; genLoading.value = true; try { const { data } = await api.post('/ui-automation/midscene/cases/generate_steps/', { description: aiDesc.value, model_config_id: form.ai_model_config_id }); if (data.steps) { form.ai_prompt = data.steps; editorMode.value = 'list'; updateStepsFromPrompt(); showAiGen.value = false; aiDesc.value = ''; ElMessage.success('步骤已生成') } } catch (e) { ElMessage.error('生成失败: ' + (e.response?.data?.error || e.message)) } finally { genLoading.value = false } }
const doExecute = async () => {
  if (selectedDeviceIds.value.length === 0) { ElMessage.warning('请选择设备'); return }
  if (!form.ai_model_config_id) { ElMessage.warning('请选择 AI 模型'); return }
  if (!form.ai_prompt.trim()) { ElMessage.warning('请输入测试步骤'); return }
  if (!promptValid.value) { ElMessage.warning('步骤存在错误：' + (stepErrors.value || '请检查步骤')); return }
  if (replayMode.value && replayList.value.length === 0) { ElMessage.warning('暂无录制数据，请先录制'); return }
  if (replayMode.value && replayList.value.length > 0 && !forceExecuteFlag.value) {
    let matched
    if (selectedDeviceIds.value.length === 1) {
      matched = await checkReplayMatch()
    } else if (!batchMatchConfirmed.value) {
      matched = await checkReplayMatchBatch()
    }
    forceExecuteFlag.value = false
    batchMatchConfirmed.value = false
    if (matched === false) return
  }
  forceExecuteFlag.value = false
  batchMatchConfirmed.value = false
  executing.value = true
  try {
    if (!currentCaseId.value || currentCaseId.value === draftId) await saveCase()
    const basePayload = { auto_plan: autoPlanMode.value, record: recordMode.value, replay: replayMode.value, replay_index: selectedReplayIndex.value, clear_app_data: clearAppData.value, install_package_id: selectedInstallPackageId.value }
    let data
    if (selectedDeviceIds.value.length === 1) {
      const { data: res } = await api.post(`/ui-automation/midscene/cases/${currentCaseId.value}/execute/`, { device_id: selectedDeviceIds.value[0], ...basePayload })
      data = { executions: [{ execution_id: res.execution_id, task_id: res.task_id, device_id: selectedDeviceIds.value[0], replay_index: selectedReplayIndex.value }], failed: [] }
    } else {
      const devicesPayload = selectedDeviceIds.value.map(id => ({ device_id: id, replay_index: replayIndexForDevice(id) }))
      const { data: res } = await api.post(`/ui-automation/midscene/cases/${currentCaseId.value}/execute/`, { devices: devicesPayload, ...basePayload })
      data = res
    }
    if (data.failed?.length) ElMessage.warning(`${data.failed.length} 台设备未能启动：` + data.failed.map(f => f.error).join('；'))
    const list = (data.executions || []).map(r => ({
      id: r.execution_id,
      task_id: r.task_id,
      device_id: r.device_id,
      device_name: deviceNameById(r.device_id),
      replay_index: r.replay_index,
      status: 'pending',
      status_display: '待执行',
      progress: 0,
      total_steps: 0,
      steps_detail: [],
      passed_steps: 0,
      failed_steps: 0,
      screenshot: '',
      reasoning: [],
      step: 0,
    }))
    executions.value = list
    activeExecIndex.value = '0'
    if (list.length > 0) startPolling()
  } catch (e) { ElMessage.error('执行失败: ' + (e.response?.data?.error || e.message)) }
  finally { executing.value = false }
}
const stopExecution = async (exec) => {
  const targets = exec ? [exec] : executions.value.filter(e => ['pending', 'running'].includes(e.status))
  if (targets.length === 0) return
  try {
    await Promise.all(targets.map(e => api.post(`/ui-automation/midscene/executions/${e.id}/stop/`)))
    // 真正停止由 worker 确认：先置 stopping，轮询到 stopped 后才算结束
    targets.forEach(e => { e.status = 'stopping'; e.status_display = '停止中' })
    ElMessage.info(targets.length > 1 ? `正在停止 ${targets.length} 台设备` : '正在停止')
  } catch (e) {}
}
const stopAllExecutions = () => stopExecution()
const startPolling = () => {
  stopPolling()
  pollCaseId = currentCaseId.value
  const poll = async () => {
    if (pollCaseId !== currentCaseId.value) { stopPolling(); return }
    const active = executions.value.filter(e => ['pending', 'running', 'stopping'].includes(e.status))
    if (active.length === 0) { stopPolling(); refreshAfterExecution(); return }
    const results = await Promise.allSettled(active.map(e => api.get(`/ui-automation/midscene/executions/${e.id}/`)))
    if (pollCaseId !== currentCaseId.value) { stopPolling(); return }
    results.forEach((r, i) => {
      const target = executions.value.find(e => e.id === active[i].id)
      if (!target) return
      if (r.status === 'fulfilled') {
        const data = r.value.data
        Object.assign(target, data)
        if (data.steps_detail?.length) {
          const last = data.steps_detail[data.steps_detail.length - 1]
          target.screenshot = last.screenshot || ''
          target.reasoning = last.aiReasoning || []
          target.step = last.step
        }
      }
    })
    if (!executions.value.some(e => ['pending', 'running', 'stopping'].includes(e.status))) {
      stopPolling()
      refreshAfterExecution()
    }
  }
  pollTimer = setInterval(poll, 2000)
  poll()
}
const refreshAfterExecution = async () => { if (recordMode.value) selectedReplayIndex.value = 0; await loadCases() }
const stopPolling = () => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } pollCaseId = null }
const previewStep = (s) => {
  previewStepData.value = s || null
  previewImage.value = s?.screenshot || ''
  previewAfterImage.value = s?.after_screenshot || ''
  if (s?.screenshot || s?.after_screenshot) showPreview.value = true
}
const stepAnomalyCount = (s) => ((s && s.anomalies) || []).length
const severityLabel = (sev) => ({ minor: '轻微抖动', recovered: '纠错救回', critical: '疑似根因' })[sev || 'minor'] || sev || '未知'
const stepTopSeverity = (s) => {
  let top = 'minor'
  for (const a of (s && s.anomalies) || []) {
    if (a.severity === 'critical') return 'critical'
    if (a.severity === 'recovered') top = 'recovered'
  }
  return top
}
const stepBadgeClass = (s) => {
  if (s.status === 'passed' && stepAnomalyCount(s) > 0) return 'badge-warn badge-warn-' + stepTopSeverity(s)
  return 'badge-' + s.status
}
const stepBadgeMark = (s) => {
  if (s.status === 'passed') return stepAnomalyCount(s) > 0 ? (stepTopSeverity(s) === 'critical' ? '!!' : '⚠') : '✓'
  if (s.status === 'failed') return '✗'
  return '→'
}
const activeExecAnomalyCount = computed(() =>
  (activeExec.value?.steps_detail || []).reduce((n, s) => n + stepAnomalyCount(s), 0)
)
const activeExecCriticalCount = computed(() =>
  (activeExec.value?.steps_detail || []).reduce(
    (n, s) => n + ((s.anomalies || []).filter(a => a.severity === 'critical').length), 0)
)

// ---- 用例编排 ----
const showSequenceDrawer = ref(false)
const sequences = ref([])
const sequencesLoading = ref(false)
const seqEditMode = ref('list') // 'list' | 'edit'
const seqListFilterProjectId = ref(null)
const seqForm = reactive({ id: null, name: '', description: '', items: [], project_id: null, folder_id: null })
const seqSaving = ref(false)
const seqDeviceId = ref(null)
const seqRunDeviceDialog = ref(false)
const seqMatchRows = ref([])
const seqRunDialog = ref(false)
const seqRunTarget = ref(null)
const seqRun = ref(null)
const seqRunning = ref(false)
const seqRunTimer = ref(null)
const seqExecutions = ref([])

const seqDevices = computed(() => devices.value.filter(d => d.status !== 'offline'))
const filteredSequences = computed(() => {
  if (!seqListFilterProjectId.value) return sequences.value
  return sequences.value.filter(s => s.project === seqListFilterProjectId.value)
})
const seqFolderOptions = computed(() => {
  if (!seqForm.project_id) return folders.value
  return folders.value.filter(f => !f.project || f.project === seqForm.project_id)
})
const seqAvailableCases = computed(() => {
  let list = cases.value
  if (seqForm.project_id) list = list.filter(c => c.project === seqForm.project_id)
  if (seqForm.folder_id) list = list.filter(c => c.folder === seqForm.folder_id)
  return list
})

const loadSequences = async () => {
  sequencesLoading.value = true
  try {
    const { data } = await api.get('/ui-automation/midscene/sequences/')
    sequences.value = data.results || data || []
  } catch (e) {
    ElMessage.error('加载编排失败')
  } finally {
    sequencesLoading.value = false
  }
}
const openSequenceDrawer = () => {
  showSequenceDrawer.value = true
  seqEditMode.value = 'list'
  loadSequences()
}
const newSequence = () => {
  seqEditMode.value = 'edit'
  Object.assign(seqForm, { id: null, name: '', description: '', items: [], project_id: null, folder_id: null })
  addSeqItem()
}
const editSequence = (seq) => {
  seqEditMode.value = 'edit'
  Object.assign(seqForm, {
    id: seq.id, name: seq.name, description: seq.description || '',
    project_id: seq.project || null, folder_id: seq.folder || null,
    items: (seq.items || []).map(it => ({
      case_id: it.case, clear_relaunch: it.clear_relaunch,
      break_on_fail: it.break_on_fail, replay_mode: it.replay_mode, replay_index: it.replay_index,
      install_package_id: it.install_package_id ?? null,
    })),
  })
  if (!seqForm.items.length) addSeqItem()
}
const addSeqItem = () => {
  seqForm.items.push({
    case_id: null, clear_relaunch: seqForm.items.length === 0,
    break_on_fail: true, replay_mode: 'auto', replay_index: 0, install_package_id: null,
  })
}
const removeSeqItem = (i) => { seqForm.items.splice(i, 1) }
const moveSeqItem = (i, dir) => {
  const j = i + dir
  if (j < 0 || j >= seqForm.items.length) return
  const t = seqForm.items[i]; seqForm.items[i] = seqForm.items[j]; seqForm.items[j] = t
}
const saveSequence = async () => {
  if (!seqForm.name || !seqForm.name.trim()) { ElMessage.warning('请输入编排名称'); return }
  const items = seqForm.items.filter(it => it.case_id)
  if (!items.length) { ElMessage.warning('请至少添加一个用例'); return }
  const payload = {
    name: seqForm.name, description: seqForm.description || '',
    project_id: seqForm.project_id || null, folder_id: seqForm.folder_id || null,
    items: items.map((it, i) => ({
      case_id: it.case_id, clear_relaunch: i === 0 ? true : it.clear_relaunch,
      break_on_fail: it.break_on_fail, replay_mode: it.replay_mode, replay_index: it.replay_index,
      install_package_id: it.install_package_id || null,
    })),
  }
  seqSaving.value = true
  try {
    if (seqForm.id) {
      await api.put(`/ui-automation/midscene/sequences/${seqForm.id}/`, payload)
    } else {
      await api.post('/ui-automation/midscene/sequences/', payload)
    }
    ElMessage.success('已保存')
    seqEditMode.value = 'list'
    await loadSequences()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '保存失败')
  } finally {
    seqSaving.value = false
  }
}
const deleteSequence = async (seq) => {
  try { await ElMessageBox.confirm(`确定删除编排「${seq.name}」？`, '确认', { type: 'warning' }) } catch (e) { return }
  try {
    await api.delete(`/ui-automation/midscene/sequences/${seq.id}/`)
    ElMessage.success('已删除')
    await loadSequences()
  } catch (e) { ElMessage.error('删除失败') }
}
const openSeqRunDialog = async (seq) => {
  seqRunTarget.value = seq
  if (!seqDeviceId.value) { ElMessage.warning('请先选择设备'); return }
  if (!seq.items || !seq.items.length) { ElMessage.warning('该编排没有用例'); return }
  try {
    const { data } = await api.get(`/ui-automation/midscene/sequences/${seq.id}/match_summary/`, {
      params: { device_id: seqDeviceId.value },
    })
    seqMatchRows.value = data.items || []
    seqRunDialog.value = true
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '匹配检查失败')
  }
}
const confirmSeqRun = async (seq) => {
  seq = seq || seqRunTarget.value
  try {
    const { data } = await api.post(`/ui-automation/midscene/sequences/${seq.id}/execute/`, {
      device_id: seqDeviceId.value,
    })
    seqRunDialog.value = false
    seqRunning.value = true
    seqRun.value = { id: data.run_id, status: 'pending', executions: [] }
    startSeqPolling(data.run_id)
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '发起执行失败')
  }
}
const startSeqPolling = (runId) => {
  stopSeqPolling()
  const tick = async () => {
    try {
      const { data } = await api.get(`/ui-automation/midscene/sequence-runs/${runId}/`)
      seqRun.value = data
      seqExecutions.value = data.executions || []
      if (data.status === 'running' || data.status === 'pending' || data.status === 'stopping') return
      stopSeqPolling()
      seqRunning.value = false
      await loadSequences()
      ElMessage[data.status === 'passed' ? 'success' : 'warning'](`编排执行结束: ${data.status}`)
    } catch (e) {
      stopSeqPolling()
      seqRunning.value = false
    }
  }
  tick()
  seqRunTimer.value = setInterval(tick, 2000)
}
const stopSeqPolling = () => {
  if (seqRunTimer.value) { clearInterval(seqRunTimer.value); seqRunTimer.value = null }
}
const stopSeqRun = async () => {
  if (!seqRun.value?.id) return
  try { await api.post(`/ui-automation/midscene/sequence-runs/${seqRun.value.id}/stop/`) } catch (e) {}
}
const seqStatusLabel = (s) => ({
  pending: '等待中', running: '执行中', stopping: '停止中', passed: '通过',
  failed: '失败', stopped: '已停止', skipped: '已跳过', error: '异常',
})[s] || s
onMounted(() => { loadCases(); loadFolders(); loadProjects(); loadDevices(); loadVisionModels(); loadInstallPackages(); loadMidsceneConfig() })
onUnmounted(() => { stopPolling(); stopSeqPolling() })
</script>

<style scoped lang="scss">
.ms-match {
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
}
.ms-match__row {
  display: flex;
  gap: 8px;
}
.ms-match__row--batch {
  align-items: flex-start;
}
.ms-match__label {
  color: #909399;
  flex-shrink: 0;
  width: 70px;
}
.ms-match__cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  &--sub {
    color: #606266;
  }
}
.ms-match__hint {
  color: #e6a23c;
  margin-top: 4px;
}
.ms-match__radio {
  display: block;
  margin-left: 0;
  margin-bottom: 6px;
}
/* =============================================
   Endfield Complex – Midscene Testing Shell
   ============================================= */
.ms-shell {
  --ms-ink: #191919;
  --ms-paper: #f2f2f0;
  --ms-signal: #fffa00;
  --ms-state: #00ffa2;
  --ms-rail-w: 272px;
  --ms-zone-gap: 1px;

  display: flex;
  height: calc(100vh - 52px);
  background: #e8e8e2;
  position: relative;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  overflow: hidden;
}

/* Grid layer */
.ms-grid {
  position: absolute; inset: 0; pointer-events: none; z-index: 0;
  background-image:
    linear-gradient(to right, rgba(0,0,0,.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0,0,0,.04) 1px, transparent 1px);
  background-size: 64px 64px;
}

/* ============================================
   Left Rail (pale Endfield)
   ============================================ */
.ms-rail {
  width: var(--ms-rail-w);
  flex-shrink: 0;
  background: #fafaf8;
  display: flex; flex-direction: column;
  position: relative; z-index: 2;
  border-right: 1px solid #e4e4de;

  &__head {
    padding: 20px 16px 14px;
    border-bottom: 1px solid #e8e8e2;
    display: flex; flex-direction: column; gap: 12px;
  }
  &__title-row {
    display: flex; align-items: baseline; gap: 10px;
  }
  &__idx {
    font-size: 28px; font-weight: 900; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #e0e0da; line-height: 1; letter-spacing: -.02em;
  }
  &__label {
    font-size: 11px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .18em; color: #b0b0a8;
    flex: 1;
  }
  &__count {
    font-size: 13px; font-weight: 700; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #888;
    &::before { content: ''; display: inline-block; width: 6px; height: 6px; background: #00bf7a; margin-right: 6px; vertical-align: middle; }
  }
  &__list {
    flex: 1; overflow-y: auto;
    &::-webkit-scrollbar { width: 3px; }
    &::-webkit-scrollbar-thumb { background: #d8d8d2; border-radius: 0; }
  }
  &__empty {
    padding: 48px 16px; text-align: center; color: #ccc; font-size: 13px; line-height: 1.6;
  }
  &__foot {
    padding: 14px 16px; border-top: 1px solid #e8e8e2;
    display: flex; flex-direction: column; gap: 8px;
    .ms-btn--full {
      display: flex; justify-content: center; align-items: center;
    }
  }
}

.ms-case-item {
  all: unset;
  display: flex; align-items: center; gap: 0;
  width: 100%; box-sizing: border-box;
  padding: 14px 16px 14px 12px;
  border-bottom: 1px solid #ededed;
  cursor: pointer;
  position: relative;
  transition: background .12s, padding-left .15s;
  &:hover { background: #f2f2ed; }

  &.is-active {
    background: #fefde8;
    border-left: 3px solid #fffa00;
    padding-left: 9px;
  }
  &.is-draft {
    .ms-case-item__name { color: #b8860b; }
    .ms-case-item__draft-mark { color: #b8860b; }
  }

  &__num {
    width: 26px; flex-shrink: 0;
    font-size: 13px; font-weight: 700; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #ccc; text-align: right; margin-right: 12px;
  }
  &:hover &__num { color: #999; }
  &.is-active &__num { color: #b8a800; }

  &__body {
    flex: 1; min-width: 0;
    display: flex; flex-direction: column; gap: 5px;
  }
  &__name {
    font-size: 13px; font-weight: 500; color: #333;
    line-height: 1.3;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  &__row {
    display: flex; align-items: center; gap: 10px;
    font-size: 11px; color: #aaa;
  }
  &__steps {
    font-family: "Space Grotesk", system-ui, sans-serif;
    letter-spacing: .03em;
  }
  &__rate {
    font-family: "Space Grotesk", system-ui, sans-serif; font-weight: 700; font-size: 12px;
    &.rate-pass { color: #00a86b; }
    &.rate-fail { color: #e04040; }
  }
  &__draft-mark {
    font-size: 10px; color: #b8860b; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .08em;
  }
  &__proj {
    font-size: 10px; color: #c0c0b8;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .06em;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  &__del {
    position: absolute; top: 10px; right: 8px; opacity: 0;
    color: #ccc; padding: 4px; cursor: pointer; transition: color .15s;
    &:hover { color: #e04040; }
  }
  &:hover &__del { opacity: 1; }
}

/* Folder rows inside the rail */
.ms-folder-row {
  padding: 12px 14px 12px 10px;
  background: #f5f5f1;
  border-bottom: 1px solid #e6e6e0;
  &:hover { background: #efefe9; }

  &--active {
    background: #fefde8;
    border-left: 3px solid #ffd700;
    padding-left: 7px;
  }

  &__arrow {
    width: 18px; flex-shrink: 0; color: #b0b0a8;
    display: inline-flex; align-items: center;
    .el-icon { transition: transform .15s; }
    .el-icon.is-open { transform: rotate(90deg); }
  }
  &__icon {
    width: 20px; flex-shrink: 0; color: #c9a227;
    display: inline-flex; align-items: center;
    margin-right: 4px;
  }
  &__name {
    flex: 1; min-width: 0; font-weight: 600; font-size: 13px; color: #444;
  }
  &__count {
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif;
    color: #a0a098; background: #eceae4; padding: 1px 6px;
    letter-spacing: .03em;
  }
  &__ops {
    display: inline-flex; gap: 2px; opacity: 0; margin-left: 6px;
    transition: opacity .15s;
  }
  &:hover &__ops { opacity: 1; }
  &__op {
    color: #b8b8b0; padding: 2px; cursor: pointer;
    &:hover { color: #191919; }
    &--del:hover { color: #e04040; }
  }
}

.ms-folder-divider {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px 6px;
  font-size: 10px; color: #b0b0a8;
  font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .1em;
  background: #fafaf8;
  &__label { flex: 1; }
  &__count { color: #c8c8c0; }
}

.ms-case-item--in-folder {
  padding-left: 30px;
  .ms-case-item__num { color: #d0d0c8; }
}

/* Pale rail select override */
.ms-select--dark {
  :deep(.el-input__wrapper) {
    background: #fff; border: 1px solid #d8d8d2;
    box-shadow: none; border-radius: 0;
    .el-input__inner { color: #555; font-size: 12px; }
    .el-input__suffix { color: #bbb; }
  }
}

/* ============================================
   Main Stage
   ============================================ */
.ms-stage {
  flex: 1; overflow-y: auto;
  padding: 20px;
  display: flex; flex-direction: column; gap: var(--ms-zone-gap);
  position: relative; z-index: 1;
  background: var(--ms-paper);
}

.ms-zone {
  background: #fff;
  &__head {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 20px 0;
  }
  &__kicker {
    font-size: 10px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .14em; color: #999;
    white-space: nowrap;
  }
  &__rule {
    flex: 1; height: 1px; background: #e8e8e4;
  }
  &__body {
    padding: 16px 20px;
  }
}

.ms-field-row {
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
}

/* ============================================
   Command Strip
   ============================================ */
.ms-cmd-strip {
  display: flex; align-items: center;
  flex-wrap: wrap; gap: 10px;
  &__left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex: 1 1 auto; min-width: 0; }
  &__right { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; justify-content: flex-end; margin-left: auto; }
  &__divider {
    display: inline-block; width: 1px; height: 20px; background: #e0e0dc; margin: 0 4px;
  }
}

.ms-switch-group {
  display: flex; align-items: center; gap: 14px;
}
.ms-switch {
  display: flex; align-items: center; gap: 4px; cursor: pointer;
  span { font-size: 12px; color: #666; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .04em; }
}
.ms-ai-config {
  display: flex; align-items: center; gap: 10px;
  &__label {
    font-size: 11px; color: #999; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .08em; white-space: nowrap;
  }
}

/* ============================================
   Inputs & Buttons
   ============================================ */
.ms-input :deep(.el-input__wrapper) { border-radius: 0 !important; box-shadow: none !important; border: 1px solid #d4d4ce; }
.ms-select :deep(.el-input__wrapper) { border-radius: 0 !important; box-shadow: none !important; border: 1px solid #d4d4ce; }
.ms-input--context { margin-bottom: 12px; :deep(.el-input__wrapper) { border-radius: 0 !important; box-shadow: none !important; } }

.ms-editor {
  :deep(textarea) {
    font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
    font-size: 14px; line-height: 1.8; border-radius: 0 !important;
    border-color: #d4d4ce !important;
  }
  &__actions { display: flex; gap: 8px; margin-top: 10px; }
}

.ms-btn {
  border-radius: 0 !important; font-size: 12px;
  font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .05em;
  &--full { width: 100%; border-radius: 0 !important; }
  &--ghost {
    color: #666; background: transparent; border-color: #d8d8d2;
    &:hover { color: #191919; border-color: #191919; background: transparent; }
  }
  &--save { border-radius: 0 !important; font-weight: 600; letter-spacing: .06em; }
  &--text { color: #999; }
}

/* ============================================
   Button color overrides (unscoped — must pierce Element Plus)
   ============================================ */
</style>

<style scoped lang="scss">
.ms-seq {
  display: flex;
  flex-direction: column;
  gap: 14px;

  &__toolbar {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  &__empty {
    padding: 32px;
    text-align: center;
    color: #909399;
    font-size: 13px;
  }

  &__list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  &__card {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 14px;
    border: 1px solid var(--ms-line, #e2e4ea);
    border-radius: 8px;

    &-main {
      flex: 1;
      min-width: 0;
    }

    &-ops {
      display: flex;
      align-items: center;
      gap: 4px;
      flex-shrink: 0;
    }
  }

  &__name {
    font-weight: 600;
    font-size: 14px;
  }

  &__count {
    margin-left: 8px;
    color: var(--ms-muted, #909399);
    font-size: 12px;
    font-weight: 400;
  }

  &__desc {
    margin-top: 2px;
    color: var(--ms-muted, #909399);
    font-size: 12px;
  }

  &__meta {
    margin-top: 2px;
    color: var(--ms-muted, #909399);
    font-size: 12px;
  }

  &__fields {
    display: flex;
    gap: 10px;
  }

  &__items {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
  }

  &__chip {
    padding: 2px 8px;
    border-radius: 4px;
    background: var(--ms-tint, #f4f5f7);
    font-size: 12px;
    color: #555;
  }

  &__form {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  &__items-edit {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  &__item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px;
    border: 1px solid var(--ms-line, #e2e4ea);
    border-radius: 6px;

    &-no {
      font-variant-numeric: tabular-nums;
      color: var(--ms-muted, #909399);
      font-size: 12px;
      width: 22px;
    }

    &-defaults {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }

    &-ops {
      display: flex;
      align-items: center;
      gap: 2px;
      flex-shrink: 0;
    }
  }

  &__form-ops {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  &__hint {
    color: var(--ms-muted, #909399);
    font-size: 12px;
    line-height: 1.6;
  }

  &__run {
    margin-top: 8px;
    padding: 12px;
    border: 1px solid var(--ms-line, #e2e4ea);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 10px;

    &-head {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 600;
      font-size: 13px;
    }

    &-status {
      color: var(--ms-muted, #909399);
      font-weight: 400;
    }

    &-items {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    &-item {
      display: flex;
      justify-content: space-between;
      font-size: 13px;
    }

    &-item-status {
      font-variant-numeric: tabular-nums;
      color: var(--ms-muted, #909399);
    }

    &-item-status--passed { color: #67c23a; }
    &-item-status--failed, &-item-status--error { color: #f56c6c; }
    &-item-status--skipped { color: #b1b3b8; }
  }

  &__match {
    display: flex;
    flex-direction: column;
    gap: 8px;

    &-row {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 13px;
    }

    &-name {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    &-level {
      padding: 1px 6px;
      border-radius: 4px;
      font-size: 11px;
      text-transform: uppercase;
      background: var(--ms-tint, #f4f5f7);
      color: #666;
    }

    &-level--exact { background: #f0f9eb; color: #67c23a; }
    &-level--ok, &-level--unknown { background: #ecf5ff; color: #409eff; }
    &-level--resolution_mismatch, &-level--no_match, &-level--no_replay { background: #fef0f0; color: #f56c6c; }

    &-replay {
      color: var(--ms-muted, #909399);
      font-size: 12px;
    }

    &-hint {
      margin-top: 6px;
      color: var(--ms-muted, #909399);
      font-size: 12px;
    }
  }
}
</style>

<style lang="scss">
.ms-shell {
  /* Execute: signal yellow */
  .ms-btn--exec.el-button--primary {
    --el-button-bg-color: #fffa00;
    --el-button-border-color: #fffa00;
    --el-button-text-color: #191919;
    --el-button-hover-bg-color: #e6e100;
    --el-button-hover-border-color: #e6e100;
    --el-button-hover-text-color: #191919;
    --el-button-disabled-bg-color: #f5f5f0;
    --el-button-disabled-border-color: #e0e0dc;
    --el-button-disabled-text-color: #ccc;
    border-radius: 0 !important; font-weight: 700;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .08em;
  }

  /* Stop: restrained dark */
  .ms-btn--stop.el-button {
    --el-button-bg-color: #191919;
    --el-button-border-color: #191919;
    --el-button-text-color: #f2f2f0;
    --el-button-hover-bg-color: #333;
    --el-button-hover-border-color: #333;
    --el-button-hover-text-color: #fff;
    border-radius: 0 !important; font-weight: 600;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .06em;
  }

  /* Save: dark ink */
  .ms-btn--save.el-button--primary {
    --el-button-bg-color: #191919;
    --el-button-border-color: #191919;
    --el-button-text-color: #f2f2f0;
    --el-button-hover-bg-color: #333;
    --el-button-hover-border-color: #333;
    --el-button-hover-text-color: #fff;
    border-radius: 0 !important; font-weight: 600;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .06em;
  }
}

/* ============================================
   Live Execution Stage
   ============================================ */
.ms-stage-live {
  background: #fff;
  &__status {
    font-size: 11px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .1em; color: #666;
    display: flex; align-items: center; gap: 6px;
  }
  &__bar {
    display: flex;
    align-items: center;
    gap: 18px;
    padding: 14px 20px 0;
  }
}

.ms-exec-tabs {
  padding: 8px 20px 0;
  &.el-tabs--top .el-tabs__header {
    margin-bottom: 6px;
  }
  .el-tabs__nav-wrap::after {
    height: 1px;
    background: #e8e8e4;
  }
}
.ms-exec-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  &__status {
    color: #909399;
    font-size: 11px;
  }
}

.ms-progress-bar--inline {
  flex: 1;
  padding: 0;
}

.ms-btn--stop-inline.el-button {
  height: 24px;
  padding: 0 10px;
  font-size: 11px;
}

.ms-anom-summary {
  display: inline-flex; align-items: center; gap: 4px;
  margin-left: 8px; padding: 1px 8px; font-size: 11px; font-weight: 600;
  color: #b26a00; background: rgba(230,162,60,.1); border: 1px solid rgba(230,162,60,.35);
  border-radius: 999px;
  &--critical {
    color: #c03939; background: rgba(245,108,108,.1); border-color: rgba(245,108,108,.4);
  }
}

.ms-status-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
  &.dot-pending, &.dot-running { background: var(--ms-signal); animation: ms-pulse 1.2s ease-in-out infinite; }
  &.dot-stopping { background: #e6a23c; animation: ms-pulse 1.2s ease-in-out infinite; }
  &.dot-passed { background: var(--ms-state); }
  &.dot-failed, &.dot-error { background: #f56c6c; }
  &.dot-stopped { background: #999; }
}

@keyframes ms-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .25; }
}

.ms-progress-bar {
  display: flex; align-items: center; gap: 14px; padding: 12px 20px 0;
  &__track {
    flex: 1; height: 4px; background: #e8e8e4;
  }
  &__fill {
    height: 100%; background: var(--ms-signal);
    transition: width .4s ease-out;
  }
  &__label {
    font-size: 13px; font-family: "Space Grotesk", system-ui, sans-serif;
    font-weight: 700; color: #666; min-width: 50px; text-align: right;
  }
}

.ms-preview-anoms {
  margin-top: 14px; border-top: 1px solid #eee; padding-top: 12px;
  &__title { font-size: 13px; font-weight: 700; color: #b26a00; margin-bottom: 10px; }
}
.ms-preview-shots {
  display: flex; gap: 12px; flex-wrap: wrap;
}
.ms-preview-shot {
  flex: 1 1 180px; min-width: 160px;
  &__label { font-size: 11px; color: #909399; margin-bottom: 4px; }
}
.ms-preview-anom {
  background: #fffdf5; border: 1px solid #fde68a; border-radius: 6px;
  padding: 8px 10px; margin-bottom: 8px;
  &__head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  &__type { font-size: 12px; font-weight: 600; color: #92400e; }
  &__layer { font-size: 11px; color: #888; background: #f5f5f2; border: 1px solid #e3e3dd; padding: 0 8px; border-radius: 999px; }
  &__rec { font-size: 11px; padding: 0 8px; border-radius: 999px; }
  &__rec--ok { color: #16a34a; background: #f0fdf4; border: 1px solid #bbf7d0; }
  &__rec--bad { color: #dc2626; background: #fef2f2; border: 1px solid #fecaca; }
  &__sev { font-size: 11px; padding: 0 8px; border-radius: 999px; }
  &__sev--minor { color: #b26a00; background: #fffbeb; border: 1px solid #fde68a; }
  &__sev--recovered { color: #c2410c; background: #fff7ed; border: 1px solid #fed7aa; }
  &__sev--critical { color: #dc2626; background: #fef2f2; border: 1px solid #fecaca; }
  &__msg { font-size: 12px; color: #555; line-height: 1.5; margin-top: 6px; }
  &__ev { font-size: 11px; color: #666; background: #fafaf8; border: 1px solid #efefe9; padding: 8px; margin-top: 6px; white-space: pre-wrap; word-break: break-all; max-height: 160px; overflow-y: auto; }
}

.ms-dual {
  display: grid; grid-template-columns: 1fr 1fr; gap: 1px;
  padding: 16px 20px;
  &__pane {
    background: #1a1a1a;
    &--screen { border-right: 1px solid rgba(255,255,255,.06); }
  }
  &__label {
    font-size: 10px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .14em; color: rgba(255,255,255,.28);
    padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,.06);
  }
  &__stage {
    min-height: 360px; display: flex; align-items: center; justify-content: center;
  }
  &__log {
    min-height: 360px; max-height: 500px; overflow-y: auto; padding: 12px 14px;
  }
  &__wait {
    color: rgba(255,255,255,.18); font-family: "Space Grotesk", system-ui, sans-serif;
    font-size: 12px; letter-spacing: .1em;
  }
  &__wait--center {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 320px;
  }
}

.ms-screen-img { max-width: 100%; max-height: 520px; object-fit: contain; }

.ms-log-line {
  padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,.04);
  font-size: 13px; color: rgba(255,255,255,.7); line-height: 1.5;
  &:last-child { border-bottom: none; }
}

.ms-step-badges {
  display: flex; flex-wrap: wrap; gap: 6px; padding: 12px 20px 20px;
}

.ms-step-badge {
  all: unset;
  cursor: pointer;
  padding: 5px 12px; font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif;
  background: #f2f2f0; color: #666;
  border: 1px solid #e0e0dc;
  transition: all .15s;
  &:hover { border-color: #999; color: #333; }
  &.badge-passed { background: rgba(0,255,162,.08); border-color: rgba(0,255,162,.25); color: #1a8051; }
  &.badge-warn { background: rgba(230,162,60,.08); border-color: rgba(230,162,60,.3); color: #b26a00; }
  &.badge-warn-recovered { background: rgba(249,115,22,.08); border-color: rgba(249,115,22,.35); color: #c2410c; }
  &.badge-warn-critical { background: rgba(245,108,108,.1); border-color: rgba(245,108,108,.4); color: #c03939; }
  &.badge-failed { background: rgba(245,108,108,.06); border-color: rgba(245,108,108,.2); color: #c03939; }
  &.badge-running { border-color: var(--ms-signal); color: #666; animation: ms-pulse 1s infinite; }
  &__mark { font-weight: 700; margin-right: 2px; }
}

/* ============================================
   录制明细抽屉
   ============================================ */
.ms-detail {
  font-size: 13px;
  &__head {
    display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
    padding-bottom: 14px; margin-bottom: 14px;
    border-bottom: 1px solid #ececec;
  }
  &__result { font-weight: 700; color: #1a8051; }
  &__meta { color: #909399; font-size: 12px; }
}

.ms-detail-step {
  padding: 12px 0; border-bottom: 1px dashed #ececec;
  &:last-child { border-bottom: none; }
  &__head {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  }
  &__no {
    font-weight: 700; color: #333;
    font-family: "Space Grotesk", system-ui, sans-serif;
  }
  &__text { flex: 1; min-width: 200px; color: #303133; line-height: 1.5; }
  &__meta { margin-top: 4px; color: #909399; font-size: 11px; }
}

.ms-detail-actions {
  margin-top: 8px; display: flex; flex-direction: column; gap: 6px;
}

.ms-detail-action {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  padding: 6px 10px; background: #f7f7f5;
  &__desc { color: #303133; font-family: "Space Grotesk", system-ui, sans-serif; font-size: 12px; }
  &__meta { color: #909399; font-size: 11px; }
}

.ms-rerun {
  &__step { font-weight: 600; color: #303133; margin-bottom: 8px; font-size: 13px; }
  &__hint { color: #909399; font-size: 12px; line-height: 1.7; margin: 0 0 14px; }
  &__row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  &__label { flex: 0 0 64px; color: #909399; font-size: 13px; }
  &__meta { font-size: 13px; color: #303133; }
}

/* ============================================
   Responsive
   ============================================ */
@media (max-width: 1024px) {
  .ms-rail { --ms-rail-w: 220px; }
  .ms-stage { padding: 14px; }
  .ms-dual { grid-template-columns: 1fr; }
  .ms-cmd-strip { flex-direction: column; align-items: flex-start; }
  .ms-cmd-strip__right { margin-left: 0; justify-content: flex-start; }
}
@media (max-width: 768px) {
  .ms-shell { flex-direction: column; }
  .ms-rail { width: 100%; max-height: 240px; }
  .ms-dual { grid-template-columns: 1fr; }
}

/* ============================================
   PROCEDURE editor — Endfield field console
   ============================================ */
.ms-field-console {
  border: 1px solid #d4d4ce;
  background: var(--ms-paper);
  position: relative;
}
.ms-field-console__head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 10px; border-bottom: 1px solid #d4d4ce;
  font-family: "Space Grotesk", system-ui, sans-serif; font-size: 11px;
  letter-spacing: .1em; text-transform: uppercase; color: #666;
}
.ms-field-console__count { color: #444; }
.ms-field-console__list { max-height: 360px; overflow: auto; }
.ms-step-row {
  display: flex; align-items: center; gap: 8px; padding: 5px 8px 5px 0;
  border-bottom: 1px solid rgba(0,0,0,.06);
  min-height: 36px; position: relative;
  &__idx {
    width: 30px; flex-shrink: 0; text-align: right; padding-right: 8px;
    font-family: "Space Grotesk", system-ui, sans-serif; font-variant-numeric: tabular-nums;
    font-size: 12px; color: #9a9a94; border-right: 1px solid rgba(0,0,0,.08);
  }
  &::before {
    content: ""; position: absolute; left: 0; top: 6px; bottom: 6px; width: 3px;
    background: transparent;
  }
  &.is-branch {
    background: linear-gradient(90deg, rgba(255,250,0,.14), rgba(255,250,0,0) 42%);
    &::before { background: var(--ms-signal); }
    & .ms-step-row__idx, & .ms-step-row__prefix, & .ms-step-row__colon { color: var(--ms-ink); font-weight: 700; }
  }
  &.is-child {
    padding-left: 26px;
    &::before { background: rgba(0,0,0,.14); }
    & .ms-step-row__idx { border-left: 1px solid rgba(0,0,0,.12); }
  }
  &.is-drag-over {
    outline: 2px dashed var(--ms-signal);
    outline-offset: -2px;
    background: rgba(255,250,0,.08);
  }
  &.is-else-marker {
    padding-left: 26px;
    &::before { background: rgba(0,0,0,.14); }
    & .ms-step-row__idx { border-left: 1px solid rgba(0,0,0,.12); }
    & .ms-step-row__else { color: #b4532e; font-weight: 700; font-size: 13px; }
  }
  &__prefix { flex-shrink: 0; font-size: 12px; }
  &__colon { flex-shrink: 0; font-size: 13px; }
  &__input {
    flex: 1; min-width: 0;
    :deep(.el-input__wrapper) { border-radius: 0 !important; box-shadow: none !important; background: transparent; }
    :deep(.el-input__inner) { font-size: 13px; }
  }
  &__tools { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
}
.ms-iconbtn {
  width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid transparent; background: transparent; cursor: pointer;
  color: #8a8a84; font-size: 13px; line-height: 1; padding: 0;
  &:hover { color: var(--ms-ink); border-color: #c9c9c2; background: #fafaf8; }
  &:disabled { color: #d4d4ce; cursor: not-allowed; }
  &.ms-textbtn { width: auto; padding: 0 6px; font-size: 12px; }
  &.ms-iconbtn--danger { color: #b4532e; }
}
.ms-field-console__add {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-top: 1px solid #d4d4ce;
  & .ms-field-console__error { margin-left: auto; font-size: 12px; color: #b4532e; }
}
.ms-addbtn {
  padding: 4px 10px; height: 28px; border: 1px solid #d4d4ce; background: #fafaf8; color: #444;
  font-size: 12px; cursor: pointer; font-family: "Space Grotesk", system-ui, sans-serif;
  text-transform: uppercase; letter-spacing: .05em;
  &:hover { color: var(--ms-ink); border-color: var(--ms-ink); }
  &.ms-addbtn--accent { border-color: var(--ms-ink); background: var(--ms-ink); color: #fff; }
}
.ms-raw-toggle {
  border: 1px solid #d4d4ce; background: transparent; color: #666; font-size: 11px;
  padding: 2px 8px; height: 22px; cursor: pointer; text-transform: uppercase; letter-spacing: .08em;
  font-family: "Space Grotesk", system-ui, sans-serif;
  &:hover { color: var(--ms-ink); border-color: var(--ms-ink); }
  &--back { background: var(--ms-ink); color: #fff; border-color: var(--ms-ink); }
}
.ms-editor__rawfoot {
  display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 8px;
  & .ms-field-console__error { font-size: 12px; color: #b4532e; }
}
</style>
