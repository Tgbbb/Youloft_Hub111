<template>
  <div class="automation-testing">
    <div class="header">
      <h3>{{ $t('apiTesting.automation.title') }}</h3>
      <el-button type="primary" @click="showCreateSuiteDialog = true">
        <el-icon><Plus /></el-icon>
        {{ $t('apiTesting.automation.createSuite') }}
      </el-button>
    </div>

    <div class="content-layout">
      <!-- 左侧项目选择和测试套件列表 -->
      <div class="sidebar">
        <div class="project-selector">
          <el-select
            v-model="selectedProject"
            popper-class="automation-popper"
            :placeholder="$t('apiTesting.common.selectProject')"
            @change="onProjectChange"
            style="width: 100%;"
          >
            <el-option
              v-for="project in httpProjects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </div>
        
        <div class="suite-list">
          <div class="list-header">
            <span>{{ $t('apiTesting.automation.testSuites') }}</span>
            <el-button size="small" text @click="loadTestSuites">
              <el-icon><Refresh /></el-icon>
            </el-button>
          </div>
          
          <el-scrollbar height="400px">
            <div
              v-for="suite in testSuites"
              :key="suite.id"
              class="suite-item"
              :class="{ active: selectedSuite?.id === suite.id }"
              @click="selectSuite(suite)"
            >
              <div class="suite-info">
                <div class="suite-name">{{ suite.name }}</div>
                <div class="suite-meta">
                  {{ $t('apiTesting.automation.requestCount', { n: suite.suite_requests?.length || 0 }) }}
                </div>
              </div>
              <el-dropdown popper-class="automation-popper" @command="handleSuiteAction" trigger="click">
                <el-button size="small" text>
                  <el-icon><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :command="{ action: 'run', suite }">{{ $t('apiTesting.automation.run') }}</el-dropdown-item>
                    <el-dropdown-item :command="{ action: 'edit', suite }">{{ $t('apiTesting.common.edit') }}</el-dropdown-item>
                    <el-dropdown-item :command="{ action: 'duplicate', suite }">{{ $t('apiTesting.common.copy') }}</el-dropdown-item>
                    <el-dropdown-item :command="{ action: 'delete', suite }" divided>{{ $t('apiTesting.common.delete') }}</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </el-scrollbar>
        </div>
      </div>

      <!-- 右侧测试套件详情 -->
      <div class="main-content">
        <div v-if="!selectedSuite" class="empty-state">
          <el-empty :description="$t('apiTesting.automation.selectSuiteHint')" />
        </div>
        
        <div v-else class="suite-detail">
          <!-- 套件信息 -->
          <div class="suite-header">
            <div class="suite-title">
              <h4>{{ selectedSuite.name }}</h4>
              <div class="suite-actions">
                <el-button type="success" @click="runTestSuite(selectedSuite)" :loading="running">
                  <el-icon><VideoPlay /></el-icon>
                  {{ $t('apiTesting.automation.runTest') }}
                </el-button>
                <el-button @click="editSuite(selectedSuite)">
                  <el-icon><Edit /></el-icon>
                  {{ $t('apiTesting.common.edit') }}
                </el-button>
              </div>
            </div>
            <div class="suite-description">
              {{ selectedSuite.description || $t('apiTesting.automation.noDescription') }}
            </div>
            <div class="suite-meta">
              <el-tag size="small">{{ getEnvironmentName(selectedSuite.environment) }}</el-tag>
              <span class="meta-text">{{ $t('apiTesting.automation.creator') }}{{ selectedSuite.created_by?.username }}</span>
              <span class="meta-text">{{ $t('apiTesting.automation.createTime') }}{{ formatDate(selectedSuite.created_at) }}</span>
            </div>
          </div>

          <!-- 请求列表 -->
          <div class="requests-section">
            <div class="section-header">
              <h5>{{ $t('apiTesting.automation.testRequests') }}</h5>
              <el-button size="small" @click="showAddRequest">
                <el-icon><Plus /></el-icon>
                {{ $t('apiTesting.automation.addRequest') }}
              </el-button>
            </div>
            
            <el-table :data="selectedSuite.suite_requests" style="width: 100%">
              <el-table-column type="index" width="50" />
              <el-table-column :label="$t('apiTesting.automation.caseName')" min-width="150" show-overflow-tooltip>
                <template #default="scope">
                  <span class="case-name">{{ scope.row.name || scope.row.request_name }}</span>
                </template>
              </el-table-column>
              <el-table-column :label="$t('apiTesting.automation.interfaceName')" min-width="150" show-overflow-tooltip>
                <template #default="scope">
                  {{ scope.row.request_name }}
                </template>
              </el-table-column>
              <el-table-column :label="$t('apiTesting.automation.method')" width="90">
                <template #default="scope">
                  <el-tag :type="getMethodType(scope.row.request_method)" size="small">
                    {{ scope.row.request_method }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column :label="$t('apiTesting.automation.url')" min-width="200" show-overflow-tooltip>
                <template #default="scope">
                  {{ scope.row.request_url }}
                </template>
              </el-table-column>
              <el-table-column prop="enabled" :label="$t('apiTesting.automation.enabled')" width="80">
                <template #default="scope">
                  <el-switch
                    v-model="scope.row.enabled"
                    @change="updateRequestEnabled(scope.row)"
                  />
                </template>
              </el-table-column>
              <el-table-column :label="$t('apiTesting.automation.assertions')" width="70">
                <template #default="scope">
                  <el-button link type="primary" @click="editAssertions(scope.row)" size="small">
                    {{ scope.row.assertions?.length || 0 }}
                  </el-button>
                </template>
              </el-table-column>
              <el-table-column :label="$t('apiTesting.automation.extractVariables')" width="70">
                <template #default="scope">
                  <el-button link type="primary" @click="editExtractRules(scope.row)" size="small">
                    {{ scope.row.extract_rules?.length || 0 }}
                  </el-button>
                </template>
              </el-table-column>
              <el-table-column :label="$t('apiTesting.common.operation')" width="280" fixed="right">
                <template #default="scope">
                  <el-button link type="primary" @click="editSuiteRequest(scope.row)" size="small">
                    {{ $t('apiTesting.common.edit') }}
                  </el-button>
                  <el-button link type="primary" @click="moveSuiteRequest(scope.row, -1)" size="small" :disabled="scope.$index === 0">
                    {{ $t('apiTesting.automation.moveUp') }}
                  </el-button>
                  <el-button link type="primary" @click="moveSuiteRequest(scope.row, 1)" size="small" :disabled="scope.$index === (selectedSuite.suite_requests?.length || 0) - 1">
                    {{ $t('apiTesting.automation.moveDown') }}
                  </el-button>
                  <el-button link type="primary" @click="duplicateSuiteRequest(scope.row)" size="small">
                    {{ $t('apiTesting.common.copy') }}
                  </el-button>
                  <el-button link type="danger" @click="removeRequest(scope.row)" size="small">
                    {{ $t('apiTesting.automation.remove') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 执行历史 -->
          <div class="executions-section">
            <div class="section-header">
              <h5>{{ $t('apiTesting.automation.executionHistory') }}</h5>
              <el-button size="small" @click="loadExecutions">
                <el-icon><Refresh /></el-icon>
                {{ $t('apiTesting.automation.refresh') }}
              </el-button>
            </div>

            <el-table :data="executions" v-loading="executionsLoading">
              <el-table-column prop="status" :label="$t('apiTesting.common.status')" width="100">
                <template #default="scope">
                  <el-tag :type="getStatusType(scope.row.status)">
                    {{ getStatusText(scope.row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="total_requests" :label="$t('apiTesting.automation.totalRequests')" width="100" />
              <el-table-column prop="passed_requests" :label="$t('apiTesting.automation.passedCount')" width="100">
                <template #default="scope">
                  <span style="color: #67c23a">{{ scope.row.passed_requests }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="failed_requests" :label="$t('apiTesting.automation.failedCount')" width="100">
                <template #default="scope">
                  <span style="color: #f56c6c">{{ scope.row.failed_requests }}</span>
                </template>
              </el-table-column>
              <el-table-column :label="$t('apiTesting.automation.averageTime')" width="120">
                <template #default="scope">
                  {{ getAverageExecutionTime(scope.row) }}
                </template>
              </el-table-column>
              <el-table-column prop="executed_by.username" :label="$t('apiTesting.automation.executor')" width="120" />
              <el-table-column prop="created_at" :label="$t('apiTesting.automation.executionTime')" width="160">
                <template #default="scope">
                  {{ formatDate(scope.row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column :label="$t('apiTesting.common.operation')" width="120">
                <template #default="scope">
                  <el-button link type="primary" @click="viewExecutionDetail(scope.row)" size="small">
                    {{ $t('apiTesting.automation.viewDetails') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建/编辑测试套件对话框 -->
    <el-dialog
      v-model="showCreateSuiteDialog"
      class="automation-dialog"
      modal-class="automation-modal"
      :title="editingSuite ? $t('apiTesting.automation.editSuite') : $t('apiTesting.automation.createSuite')"
      width="600px"
      :close-on-click-modal="false"
      @close="resetSuiteForm"
    >
      <el-form
        ref="suiteFormRef"
        :model="suiteForm"
        :rules="suiteRules"
        label-width="100px"
      >
        <el-form-item :label="$t('apiTesting.automation.suiteName')" prop="name">
          <el-input v-model="suiteForm.name" :placeholder="$t('apiTesting.automation.inputSuiteName')" />
        </el-form-item>

        <el-form-item :label="$t('apiTesting.automation.suiteDescription')" prop="description">
          <el-input
            v-model="suiteForm.description"
            type="textarea"
            :rows="3"
            :placeholder="$t('apiTesting.automation.inputSuiteDescription')"
          />
        </el-form-item>

        <el-form-item :label="$t('apiTesting.automation.belongProject')" prop="project">
          <el-select v-model="suiteForm.project" popper-class="automation-popper" :placeholder="$t('apiTesting.automation.selectProject')">
            <el-option
              v-for="project in httpProjects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item :label="$t('apiTesting.automation.executionEnvironment')" prop="environment">
          <el-select v-model="suiteForm.environment" popper-class="automation-popper" :placeholder="$t('apiTesting.automation.selectEnvironment')" clearable>
            <el-option
              v-for="env in environments"
              :key="env.id"
              :label="env.name"
              :value="env.id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateSuiteDialog = false">{{ $t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="submitSuiteForm" :loading="submittingSuite">
          {{ editingSuite ? $t('apiTesting.common.update') : $t('apiTesting.common.create') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 添加请求对话框 -->
    <el-dialog
      v-model="showAddRequestDialog"
      class="automation-dialog"
      modal-class="automation-modal"
      :title="$t('apiTesting.automation.addRequestToSuite')"
      width="800px"
      :close-on-click-modal="false"
    >
      <div class="add-request-content">
        <div class="request-selector">
          <el-tree
            ref="requestTreeRef"
            :data="requestTree"
            :props="requestTreeProps"
            show-checkbox
            node-key="id"
            :check-on-click-node="false"
            @check="onRequestCheck"
          >
            <template #default="{ node, data }">
              <div class="request-tree-node">
                <el-icon v-if="data.type === 'collection'">
                  <Folder />
                </el-icon>
                <el-icon v-else>
                  <Document />
                </el-icon>
                <span>{{ data.name }}</span>
                <span v-if="data.type === 'request'" class="method-tag" :class="data.method?.toLowerCase()">
                  {{ data.method }}
                </span>
              </div>
            </template>
          </el-tree>
        </div>
      </div>
      
      <template #footer>
        <el-button @click="showAddRequestDialog = false">{{ $t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="addSelectedRequests" :loading="addingRequests">
          {{ $t('apiTesting.automation.addSelectedRequests') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑套件用例对话框 -->
    <el-dialog
      v-model="showCaseDialog"
      class="automation-dialog"
      modal-class="automation-modal"
      :title="$t('apiTesting.automation.editCase')"
      width="800px"
      :close-on-click-modal="false"
      @close="resetCaseForm"
    >
      <el-form label-width="110px">
        <el-form-item :label="$t('apiTesting.automation.caseName')">
          <el-input v-model="caseForm.name" :placeholder="$t('apiTesting.automation.inputCaseName')" />
        </el-form-item>
        <el-form-item :label="$t('apiTesting.common.description')">
          <el-input v-model="caseForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-tabs v-model="caseTab" type="card">
          <el-tab-pane :label="$t('apiTesting.automation.params')" name="params">
            <div class="kv-editor">
              <div class="kv-tip">{{ $t('apiTesting.automation.paramsFromInterface') }}</div>
              <div class="kv-row kv-header">
                <span>{{ $t('apiTesting.interface.key') }}</span>
                <span>{{ $t('apiTesting.interface.value') }}</span>
                <span></span>
              </div>
              <div v-for="(row, index) in caseForm.paramsRows" :key="index" class="kv-row">
                <el-input v-model="row.key" :placeholder="$t('apiTesting.interface.key')" size="small" />
                <el-input v-model="row.value" :placeholder="$t('apiTesting.interface.value')" size="small" />
                <el-button type="danger" size="small" circle @click="removeKvRow(caseForm.paramsRows, index)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
              <el-button size="small" type="primary" plain @click="addKvRow(caseForm.paramsRows)">
                <el-icon><Plus /></el-icon>
                {{ $t('apiTesting.automation.addParam') }}
              </el-button>
              <div class="kv-tip">{{ $t('apiTesting.automation.paramTip') }}</div>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="$t('apiTesting.automation.headers')" name="headers">
            <div class="kv-editor">
              <div class="kv-tip">{{ $t('apiTesting.automation.headersFromInterface') }}</div>
              <div class="kv-row kv-header">
                <span>{{ $t('apiTesting.interface.key') }}</span>
                <span>{{ $t('apiTesting.interface.value') }}</span>
                <span></span>
              </div>
              <div v-for="(row, index) in caseForm.headersRows" :key="index" class="kv-row">
                <el-input v-model="row.key" :placeholder="$t('apiTesting.interface.key')" size="small" />
                <el-input v-model="row.value" :placeholder="$t('apiTesting.interface.value')" size="small" />
                <el-button type="danger" size="small" circle @click="removeKvRow(caseForm.headersRows, index)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
              <el-button size="small" type="primary" plain @click="addKvRow(caseForm.headersRows)">
                <el-icon><Plus /></el-icon>
                {{ $t('apiTesting.automation.addHeader') }}
              </el-button>
            </div>
          </el-tab-pane>
          <el-tab-pane label="请求体" name="body">
            <div class="body-editor">
              <el-select v-model="caseForm.bodyType" popper-class="automation-popper" style="width: 220px" size="small">
                <el-option :label="$t('apiTesting.automation.bodyInherit')" value="inherit" />
                <el-option :label="$t('apiTesting.automation.bodyNone')" value="none" />
                <el-option :label="$t('apiTesting.automation.bodyJson')" value="json" />
                <el-option :label="$t('apiTesting.automation.bodyRaw')" value="raw" />
                <el-option v-if="caseForm.bodyOther" :label="$t('apiTesting.automation.bodyOther', { type: caseForm.bodyOtherType })" value="other" />
              </el-select>
              <el-input
                v-if="caseForm.bodyType === 'json'"
                v-model="caseForm.bodyText"
                type="textarea"
                :rows="8"
                class="body-textarea"
                :placeholder="$t('apiTesting.automation.bodyJsonPlaceholder')"
              />
              <el-input
                v-else-if="caseForm.bodyType === 'raw'"
                v-model="caseForm.bodyText"
                type="textarea"
                :rows="8"
                class="body-textarea"
                :placeholder="$t('apiTesting.automation.bodyRawPlaceholder')"
              />
              <el-input
                v-else-if="caseForm.bodyType === 'other'"
                :model-value="JSON.stringify(caseForm.bodyOther, null, 2)"
                type="textarea"
                :rows="8"
                disabled
                class="body-textarea"
              />
              <div v-else-if="caseForm.bodyType === 'inherit' && caseForm.interfaceBody" class="body-inherit-preview">
                <div class="body-inherit-title">{{ $t('apiTesting.automation.interfaceBodyPreview') }}</div>
                <pre>{{ formatInterfaceBody(caseForm.interfaceBody) }}</pre>
                <div class="kv-tip">{{ $t('apiTesting.automation.bodyEmptyTip') }}</div>
              </div>
              <div v-else class="body-empty">{{ $t('apiTesting.automation.bodyEmptyTip') }}</div>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="$t('apiTesting.automation.assertions')" name="assertions">
            <div class="assertions-editor">
              <el-button size="small" type="primary" @click="addAssertion(caseForm.assertions)">
                <el-icon><Plus /></el-icon>
                {{ $t('apiTesting.interface.addAssertion') }}
              </el-button>
              <div class="assertions-list">
                <div v-for="(assertion, index) in caseForm.assertions" :key="index" class="assertion-item">
                  <div class="assertion-header">
                    <el-input
                      v-model="assertion.name"
                      :placeholder="$t('apiTesting.interface.assertionName')"
                      size="small"
                      class="assertion-name"
                    />
                    <el-button size="small" type="danger" circle @click="removeAssertion(caseForm.assertions, index)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </div>
                  <div class="assertion-config">
                    <el-select
                      v-model="assertion.type"
                      popper-class="automation-popper"
                      :placeholder="$t('apiTesting.interface.selectAssertionType')"
                      size="small"
                      @change="onAssertionTypeChange(assertion)"
                    >
                      <el-option :label="$t('apiTesting.interface.assertionTypes.statusCode')" value="status_code" />
                      <el-option :label="$t('apiTesting.interface.assertionTypes.responseTime')" value="response_time" />
                      <el-option :label="$t('apiTesting.interface.assertionTypes.contains')" value="contains" />
                      <el-option :label="$t('apiTesting.interface.assertionTypes.jsonPath')" value="json_path" />
                      <el-option :label="$t('apiTesting.interface.assertionTypes.header')" value="header" />
                      <el-option :label="$t('apiTesting.interface.assertionTypes.equals')" value="equals" />
                    </el-select>
                    <div class="assertion-params" v-if="assertion.type">
                      <div v-if="assertion.type === 'status_code'">
                        <el-input-number v-model="assertion.expected" :min="100" :max="599" size="small" />
                      </div>
                      <div v-else-if="assertion.type === 'response_time'">
                        <el-input-number v-model="assertion.expected" :min="1" size="small" />
                      </div>
                      <div v-else-if="assertion.type === 'contains'">
                        <el-input v-model="assertion.expected" :placeholder="$t('apiTesting.interface.expectedContains')" size="small" />
                      </div>
                      <div v-else-if="assertion.type === 'json_path'">
                        <el-input v-model="assertion.json_path" :placeholder="$t('apiTesting.interface.jsonPathExpression')" size="small" />
                        <el-input v-model="assertion.expected" :placeholder="$t('apiTesting.interface.expectedValue')" size="small" />
                      </div>
                      <div v-else-if="assertion.type === 'header'">
                        <el-input v-model="assertion.header_name" :placeholder="$t('apiTesting.interface.headerNameLabel')" size="small" />
                        <el-input v-model="assertion.expected_value" :placeholder="$t('apiTesting.interface.expectedValue')" size="small" />
                      </div>
                      <div v-else-if="assertion.type === 'equals'">
                        <el-input v-model="assertion.expected" :placeholder="$t('apiTesting.interface.expectedMatch')" size="small" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="$t('apiTesting.automation.extractVariables')" name="extract">
            <div class="extract-tip">
              <el-alert type="info" :closable="false" :title="$t('apiTesting.automation.extractTip')" />
            </div>
            <div class="extract-rule-list">
              <div v-for="(rule, index) in caseForm.extractRules" :key="index" class="extract-rule-item">
                <el-switch v-model="rule.enabled" />
                <el-input v-model="rule.name" :placeholder="$t('apiTesting.automation.extractNamePlaceholder')" size="small" style="width: 160px" />
                <el-select v-model="rule.source" popper-class="automation-popper" size="small" style="width: 140px">
                  <el-option :label="$t('apiTesting.automation.extractSourceBody')" value="body" />
                  <el-option :label="$t('apiTesting.automation.extractSourceHeader')" value="header" />
                  <el-option :label="$t('apiTesting.automation.extractSourceStatus')" value="status" />
                </el-select>
                <el-input
                  v-if="rule.source === 'body'"
                  v-model="rule.json_path"
                  :placeholder="$t('apiTesting.automation.extractJsonPathPlaceholder')"
                  size="small"
                  style="flex: 1"
                />
                <el-input
                  v-else-if="rule.source === 'header'"
                  v-model="rule.header_name"
                  :placeholder="$t('apiTesting.automation.extractHeaderNamePlaceholder')"
                  size="small"
                  style="flex: 1"
                />
                <el-button type="danger" size="small" circle @click="removeExtractRule(caseForm.extractRules, index)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
            <el-button size="small" type="primary" plain @click="addExtractRule(caseForm.extractRules)">
              <el-icon><Plus /></el-icon>
              {{ $t('apiTesting.automation.addExtractRule') }}
            </el-button>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer>
        <el-button @click="showCaseDialog = false">{{ $t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="saveSuiteRequest" :loading="savingCase">
          {{ $t('apiTesting.common.save') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 断言编辑对话框 -->
    <el-dialog
      v-model="showAssertionDialog"
      class="automation-dialog"
      modal-class="automation-modal"
      :title="$t('apiTesting.automation.editAssertions')"
      width="760px"
      :close-on-click-modal="false"
      @close="resetAssertionForm"
    >
      <div class="assertions-editor">
        <el-button size="small" type="primary" @click="addAssertion(assertionRules)">
          <el-icon><Plus /></el-icon>
          {{ $t('apiTesting.interface.addAssertion') }}
        </el-button>

        <div class="assertions-list">
          <div v-for="(assertion, index) in assertionRules" :key="index" class="assertion-item">
            <div class="assertion-header">
              <el-input
                v-model="assertion.name"
                :placeholder="$t('apiTesting.interface.assertionName')"
                size="small"
                class="assertion-name"
              />
              <el-button size="small" type="danger" circle @click="removeAssertion(assertionRules, index)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <div class="assertion-config">
              <el-select
                v-model="assertion.type"
                popper-class="automation-popper"
                :placeholder="$t('apiTesting.interface.selectAssertionType')"
                size="small"
                @change="onAssertionTypeChange(assertion)"
              >
                <el-option :label="$t('apiTesting.interface.assertionTypes.statusCode')" value="status_code" />
                <el-option :label="$t('apiTesting.interface.assertionTypes.responseTime')" value="response_time" />
                <el-option :label="$t('apiTesting.interface.assertionTypes.contains')" value="contains" />
                <el-option :label="$t('apiTesting.interface.assertionTypes.jsonPath')" value="json_path" />
                <el-option :label="$t('apiTesting.interface.assertionTypes.header')" value="header" />
                <el-option :label="$t('apiTesting.interface.assertionTypes.equals')" value="equals" />
              </el-select>

              <div class="assertion-params" v-if="assertion.type">
                <div v-if="assertion.type === 'status_code'">
                  <el-input-number v-model="assertion.expected" :min="100" :max="599" size="small" />
                </div>
                <div v-else-if="assertion.type === 'response_time'">
                  <el-input-number v-model="assertion.expected" :min="1" size="small" />
                </div>
                <div v-else-if="assertion.type === 'contains'">
                  <el-input v-model="assertion.expected" :placeholder="$t('apiTesting.interface.expectedContains')" size="small" />
                </div>
                <div v-else-if="assertion.type === 'json_path'">
                  <el-input v-model="assertion.json_path" :placeholder="$t('apiTesting.interface.jsonPathExpression')" size="small" />
                  <el-input v-model="assertion.expected" :placeholder="$t('apiTesting.interface.expectedValue')" size="small" />
                </div>
                <div v-else-if="assertion.type === 'header'">
                  <el-input v-model="assertion.header_name" :placeholder="$t('apiTesting.interface.headerNameLabel')" size="small" />
                  <el-input v-model="assertion.expected_value" :placeholder="$t('apiTesting.interface.expectedValue')" size="small" />
                </div>
                <div v-else-if="assertion.type === 'equals'">
                  <el-input v-model="assertion.expected" :placeholder="$t('apiTesting.interface.expectedMatch')" size="small" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showAssertionDialog = false">{{ $t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="saveAssertions" :loading="savingAssertions">
          {{ $t('apiTesting.common.save') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 响应变量提取规则对话框 -->
    <el-dialog
      v-model="showExtractDialog"
      class="automation-dialog"
      modal-class="automation-modal"
      :title="$t('apiTesting.automation.extractRules')"
      width="760px"
      :close-on-click-modal="false"
      @close="resetExtractForm"
    >
      <div class="extract-tip">
        <el-alert type="info" :closable="false" :title="$t('apiTesting.automation.extractTip')" />
      </div>
      <div class="extract-rule-list">
        <div v-for="(rule, index) in extractRules" :key="index" class="extract-rule-item">
          <el-switch v-model="rule.enabled" />
          <el-input v-model="rule.name" :placeholder="$t('apiTesting.automation.extractNamePlaceholder')" size="small" style="width: 160px" />
          <el-select v-model="rule.source" popper-class="automation-popper" size="small" style="width: 140px">
            <el-option :label="$t('apiTesting.automation.extractSourceBody')" value="body" />
            <el-option :label="$t('apiTesting.automation.extractSourceHeader')" value="header" />
            <el-option :label="$t('apiTesting.automation.extractSourceStatus')" value="status" />
          </el-select>
          <el-input
            v-if="rule.source === 'body'"
            v-model="rule.json_path"
            :placeholder="$t('apiTesting.automation.extractJsonPathPlaceholder')"
            size="small"
            style="flex: 1"
          />
          <el-input
            v-else-if="rule.source === 'header'"
            v-model="rule.header_name"
            :placeholder="$t('apiTesting.automation.extractHeaderNamePlaceholder')"
            size="small"
            style="flex: 1"
          />
          <el-button type="danger" size="small" circle @click="removeExtractRule(extractRules, index)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
      <el-button size="small" type="primary" plain @click="addExtractRule(extractRules)">
        <el-icon><Plus /></el-icon>
        {{ $t('apiTesting.automation.addExtractRule') }}
      </el-button>
      <template #footer>
        <el-button @click="showExtractDialog = false">{{ $t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="saveExtractRules" :loading="savingExtract">
          {{ $t('apiTesting.common.save') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 执行结果对话框 -->
    <el-dialog
      v-model="showExecutionDialog"
      class="automation-dialog"
      modal-class="automation-modal"
      :title="$t('apiTesting.automation.testExecutionResult')"
      width="80%"
      :top="'5vh'"
    >
      <div v-if="currentExecution" class="execution-detail">
        <div class="execution-summary">
          <el-row :gutter="20">
            <el-col :span="6">
              <el-statistic :title="$t('apiTesting.automation.totalRequests')" :value="currentExecution.total_requests" />
            </el-col>
            <el-col :span="6">
              <el-statistic :title="$t('apiTesting.automation.passedCount')" :value="currentExecution.passed_requests" />
            </el-col>
            <el-col :span="6">
              <el-statistic :title="$t('apiTesting.automation.failedCount')" :value="currentExecution.failed_requests" />
            </el-col>
            <el-col :span="6">
              <el-statistic :title="$t('apiTesting.automation.passRate')" :value="getPassRate(currentExecution)" suffix="%" />
            </el-col>
          </el-row>
        </div>

        <div class="execution-results">
          <h4>{{ $t('apiTesting.automation.detailedResults') }}</h4>
          <el-table :data="formatExecutionResults(currentExecution.results)">
            <el-table-column type="expand">
              <template #default="scope">
                <div class="execution-expand">
                  <div v-if="scope.row.variables_before" class="expand-block">
                    <div class="expand-title">{{ $t('apiTesting.automation.variablesBefore') }}</div>
                    <pre>{{ formatJson(scope.row.variables_before) }}</pre>
                  </div>
                  <div v-if="scope.row.extracted_variables && Object.keys(scope.row.extracted_variables).length" class="expand-block">
                    <div class="expand-title">{{ $t('apiTesting.automation.extractedVariables') }}</div>
                    <pre>{{ formatJson(scope.row.extracted_variables) }}</pre>
                  </div>
                  <div v-if="scope.row.assertions_results" class="expand-block">
                    <div class="expand-title">{{ $t('apiTesting.automation.assertionResults') }}</div>
                    <el-table :data="scope.row.assertions_results" size="small">
                      <el-table-column prop="name" :label="$t('apiTesting.automation.assertionName')" min-width="140" />
                      <el-table-column prop="type" label="Type" width="110" />
                      <el-table-column :label="$t('apiTesting.automation.result')" width="80">
                        <template #default="inner">
                          <el-tag :type="inner.row.passed ? 'success' : 'danger'" size="small">
                            {{ inner.row.passed ? $t('apiTesting.automation.status.passed') : $t('apiTesting.automation.status.failed') }}
                          </el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column prop="expected" label="Expected" min-width="100" show-overflow-tooltip />
                      <el-table-column prop="actual" label="Actual" min-width="100" show-overflow-tooltip />
                      <el-table-column prop="error" :label="$t('apiTesting.automation.errorMessage')" min-width="140" show-overflow-tooltip />
                    </el-table>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column :label="$t('apiTesting.automation.caseName')" min-width="160">
              <template #default="scope">
                {{ scope.row.case_name || scope.row.name }}
              </template>
            </el-table-column>
            <el-table-column prop="method" :label="$t('apiTesting.automation.method')" width="80">
              <template #default="scope">
                <el-tag :type="getMethodType(scope.row.method)" size="small">
                  {{ scope.row.method }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="$t('apiTesting.automation.extractedVariables')" width="120">
              <template #default="scope">
                <span v-if="scope.row.extracted_variables && Object.keys(scope.row.extracted_variables).length" class="extract-count">
                  {{ Object.keys(scope.row.extracted_variables).length }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" :label="$t('apiTesting.automation.result')" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.passed ? 'success' : 'danger'" size="small">
                  {{ scope.row.passed ? $t('apiTesting.automation.status.passed') : $t('apiTesting.automation.status.failed') }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status_code" :label="$t('apiTesting.automation.statusCode')" width="100" />
            <el-table-column prop="response_time" :label="$t('apiTesting.automation.responseTime')" width="120">
              <template #default="scope">
                {{ scope.row.response_time?.toFixed(0) }}ms
              </template>
            </el-table-column>
            <el-table-column prop="error" :label="$t('apiTesting.automation.errorMessage')" min-width="200" show-overflow-tooltip />
          </el-table>
        </div>
      </div>

      <template #footer>
        <el-button @click="showExecutionDialog = false">{{ $t('apiTesting.common.close') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import {
  Plus, Refresh, MoreFilled, VideoPlay, Edit,
  Folder, Document, Delete
} from '@element-plus/icons-vue'
import api from '@/utils/api'
import dayjs from 'dayjs'

const { t } = useI18n()

const projects = ref([])
const selectedProject = ref(null)
const testSuites = ref([])
const selectedSuite = ref(null)
const executions = ref([])
const environments = ref([])
const requestTree = ref([])
const running = ref(false)
const executionsLoading = ref(false)
const showCreateSuiteDialog = ref(false)
const showAddRequestDialog = ref(false)
const showExecutionDialog = ref(false)
const showCaseDialog = ref(false)
const showAssertionDialog = ref(false)
const showExtractDialog = ref(false)
const editingSuite = ref(null)
const submittingSuite = ref(false)
const addingRequests = ref(false)
const savingCase = ref(false)
const savingAssertions = ref(false)
const savingExtract = ref(false)
const currentExecution = ref(null)
const suiteFormRef = ref()
const requestTreeRef = ref()

const caseForm = reactive({
  id: null,
  name: '',
  description: '',
  paramsRows: [],
  headersRows: [],
  bodyType: 'inherit',
  bodyText: '',
  bodyOther: null,
  bodyOtherType: '',
  interfaceBody: null,
  assertions: [],
  extractRules: []
})
const caseTab = ref('params')

const assertionRules = ref([])
const currentAssertionRow = ref(null)

const extractRules = ref([])
const currentExtractRow = ref(null)

const suiteForm = reactive({
  name: '',
  description: '',
  project: null,
  environment: null
})

const suiteRules = computed(() => ({
  name: [{ required: true, message: t('apiTesting.automation.inputSuiteName'), trigger: 'blur' }],
  project: [{ required: true, message: t('apiTesting.automation.selectProject'), trigger: 'change' }]
}))

const requestTreeProps = {
  children: 'children',
  label: 'name'
}

const httpProjects = computed(() => {
  return projects.value.filter(project => project.project_type !== 'WEBSOCKET')
})

const getMethodType = (method) => {
  const typeMap = {
    'GET': 'success',
    'POST': 'primary',
    'PUT': 'warning', 
    'DELETE': 'danger',
    'PATCH': 'info'
  }
  return typeMap[method] || 'info'
}

const getStatusType = (status) => {
  const typeMap = {
    'PENDING': 'info',
    'RUNNING': 'warning',
    'COMPLETED': 'success',
    'FAILED': 'danger',
    'CANCELLED': 'info'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const statusKey = {
    'PENDING': 'pending',
    'RUNNING': 'running',
    'COMPLETED': 'completed',
    'FAILED': 'failed',
    'CANCELLED': 'cancelled'
  }[status]
  return statusKey ? t(`apiTesting.automation.status.${statusKey}`) : status
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm:ss')
}

const getExecutionTime = (execution) => {
  if (!execution.start_time || !execution.end_time) return '-'
  const start = dayjs(execution.start_time)
  const end = dayjs(execution.end_time)
  return `${end.diff(start, 'second')}s`
}

const getAverageExecutionTime = (execution) => {
  if (!execution.results || !Array.isArray(execution.results) || execution.results.length === 0) {
    return '-'
  }
  
  // 计算所有请求的平均响应时间
  const totalResponseTime = execution.results.reduce((sum, result) => sum + (result.response_time || 0), 0)
  const averageTime = totalResponseTime / execution.results.length
  
  if (averageTime < 1000) {
    return `${Math.round(averageTime)}ms`
  } else {
    return `${(averageTime / 1000).toFixed(1)}s`
  }
}

const getPassRate = (execution) => {
  if (execution.total_requests === 0) return 0
  return ((execution.passed_requests / execution.total_requests) * 100).toFixed(1)
}

const getEnvironmentName = (environmentId) => {
  if (!environmentId) return t('apiTesting.automation.noEnvironment')
  const env = environments.value.find(e => e.id === environmentId)
  return env ? env.name : t('apiTesting.automation.noEnvironment')
}

const loadProjects = async () => {
  try {
    const response = await api.get('/api-testing/projects/')
    projects.value = response.data.results || response.data

    // 过滤出HTTP项目
    const httpProjects = projects.value.filter(project => project.project_type !== 'WEBSOCKET')

    if (httpProjects.length > 0 && !selectedProject.value) {
      selectedProject.value = httpProjects[0].id
      await onProjectChange()
    } else if (httpProjects.length === 0) {
      // 如果没有HTTP项目，清空选择
      selectedProject.value = null
    }
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.loadProjects'))
  }
}

const loadTestSuites = async () => {
  if (!selectedProject.value) return

  try {
    const response = await api.get('/api-testing/test-suites/', {
      params: { project: selectedProject.value }
    })
    testSuites.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.loadTestSuites'))
  }
}

const loadEnvironments = async () => {
  try {
    // 获取全局环境 + 当前项目环境
    const response = await api.get('/api-testing/environments/', {
      // 不传递project参数，让后端返回所有可访问的环境（全局+当前项目）
    })
    const allEnvironments = response.data.results || response.data

    // 过滤当前项目相关或全局环境
    environments.value = allEnvironments.filter(env =>
      env.scope === 'GLOBAL' ||
      (env.scope === 'LOCAL' && (!selectedProject.value || env.project === selectedProject.value))
    )
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.loadEnvironments'))
  }
}

const loadRequestTree = async () => {
  if (!selectedProject.value) return

  try {
    // 加载集合
    const collectionsRes = await api.get('/api-testing/collections/', {
      params: { project: selectedProject.value }
    })
    const collections = collectionsRes.data.results || collectionsRes.data

    // 加载请求，传递project参数
    const requestsRes = await api.get('/api-testing/requests/', {
      params: { project: selectedProject.value }
    })
    const requests = requestsRes.data.results || requestsRes.data

    // 构建树形结构
    requestTree.value = buildRequestTree(collections, requests)
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.loadRequestTree'))
  }
}

const buildRequestTree = (collections, requests) => {
  const map = {}
  const roots = []
  
  // 创建集合节点
  collections.forEach(collection => {
    map[collection.id] = {
      ...collection,
      type: 'collection',
      children: []
    }
  })
  
  // 构建集合层级关系
  collections.forEach(collection => {
    if (collection.parent && map[collection.parent]) {
      map[collection.parent].children.push(map[collection.id])
    } else {
      roots.push(map[collection.id])
    }
  })
  
  // 添加请求到对应集合或根节点
  requests.forEach(request => {
    if (map[request.collection]) {
      map[request.collection].children.push({
        ...request,
        type: 'request',
        id: `request_${request.id}`
      })
    } else {
      // 没有关联集合的请求，直接添加到根节点
      roots.push({
        ...request,
        type: 'request',
        id: `request_${request.id}`
      })
    }
  })
  
  return roots
}

const loadExecutions = async () => {
  if (!selectedSuite.value) return

  executionsLoading.value = true
  try {
    const response = await api.get('/api-testing/test-executions/', {
      params: { test_suite: selectedSuite.value.id }
    })
    executions.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.loadExecutionHistory'))
  } finally {
    executionsLoading.value = false
  }
}

const onProjectChange = async () => {
  // 检查选中的项目是否为HTTP项目
  const selectedProjectData = projects.value.find(p => p.id === selectedProject.value)
  if (selectedProjectData && selectedProjectData.project_type === 'WEBSOCKET') {
    ElMessage.warning(t('apiTesting.messages.warning.websocketNotSupported'))
    // 重置为第一个HTTP项目或清空选择
    const httpProjects = projects.value.filter(project => project.project_type !== 'WEBSOCKET')
    if (httpProjects.length > 0) {
      selectedProject.value = httpProjects[0].id
    } else {
      selectedProject.value = null
    }
    return
  }

  selectedSuite.value = null
  await Promise.all([
    loadTestSuites(),
    loadEnvironments(),
    loadRequestTree()
  ])
}

const selectSuite = (suite) => {
  selectedSuite.value = suite
  loadExecutions()
}

const handleSuiteAction = async ({ action, suite }) => {
  switch (action) {
    case 'run':
      await runTestSuite(suite)
      break
    case 'edit':
      editSuite(suite)
      break
    case 'duplicate':
      await duplicateSuite(suite)
      break
    case 'delete':
      await deleteSuite(suite)
      break
  }
}

const runTestSuite = async (suite) => {
  running.value = true
  try {
    const response = await api.post(`/api-testing/test-suites/${suite.id}/execute/`)
    currentExecution.value = response.data
    showExecutionDialog.value = true
    await loadExecutions()
    ElMessage.success(t('apiTesting.messages.success.suiteExecuted'))
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.executeSuite'))
  } finally {
    running.value = false
  }
}

const editSuite = (suite) => {
  editingSuite.value = suite
  suiteForm.name = suite.name
  suiteForm.description = suite.description
  suiteForm.project = suite.project
  // 修复：environment字段直接是ID，不需要?.id
  suiteForm.environment = suite.environment || null
  showCreateSuiteDialog.value = true
}

const duplicateSuite = async (suite) => {
  try {
    const newSuite = {
      name: `${suite.name} - ${t('apiTesting.common.copyText')}`,
      description: suite.description,
      project: suite.project,
      environment: suite.environment || null  // 修复：直接使用environment ID
    }
    await api.post('/api-testing/test-suites/', newSuite)
    ElMessage.success(t('apiTesting.messages.success.copy'))
    await loadTestSuites()
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.copyFailed'))
  }
}

const deleteSuite = async (suite) => {
  try {
    await ElMessageBox.confirm(
      t('apiTesting.automation.confirmDeleteSuite', { name: suite.name }),
      t('apiTesting.messages.confirm.deleteTitle'),
      {
        confirmButtonText: t('apiTesting.common.confirm'),
        cancelButtonText: t('apiTesting.common.cancel'),
        type: 'warning',
        customClass: 'automation-messagebox'
      }
    )

    await api.delete(`/api-testing/test-suites/${suite.id}/`)
    ElMessage.success(t('apiTesting.messages.success.delete'))

    if (selectedSuite.value?.id === suite.id) {
      selectedSuite.value = null
    }
    await loadTestSuites()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('apiTesting.messages.error.deleteFailed'))
    }
  }
}

const submitSuiteForm = async () => {
  if (!suiteFormRef.value) return

  const valid = await suiteFormRef.value.validate().catch(() => false)
  if (!valid) return

  submittingSuite.value = true
  try {
    if (editingSuite.value) {
      await api.put(`/api-testing/test-suites/${editingSuite.value.id}/`, suiteForm)
      ElMessage.success(t('apiTesting.messages.success.suiteUpdated'))
    } else {
      await api.post('/api-testing/test-suites/', suiteForm)
      ElMessage.success(t('apiTesting.messages.success.suiteCreated'))
    }

    showCreateSuiteDialog.value = false
    await loadTestSuites()
  } catch (error) {
    ElMessage.error(editingSuite.value ? t('apiTesting.messages.error.updateFailed') : t('apiTesting.messages.error.createFailed'))
  } finally {
    submittingSuite.value = false
  }
}

const resetSuiteForm = () => {
  editingSuite.value = null
  Object.assign(suiteForm, {
    name: '',
    description: '',
    project: selectedProject.value,
    environment: null
  })
  suiteFormRef.value?.resetFields()
}

const showAddRequest = async () => {
  await loadRequestTree()
  showAddRequestDialog.value = true
  // 同一个接口允许重复添加（用于不同参数场景），因此不再预勾选已关联接口
  nextTick(() => {
    requestTreeRef.value?.setCheckedKeys([])
  })
}

const onRequestCheck = () => {
  // 请求选择变化处理
}

const addSelectedRequests = async () => {
  const checkedNodes = requestTreeRef.value.getCheckedNodes()
  const requestIds = checkedNodes
    .filter(node => node.type === 'request')
    .map(node => node.id.replace('request_', ''))

  if (requestIds.length === 0) {
    ElMessage.warning(t('apiTesting.messages.warning.selectAtLeastOneRequest'))
    return
  }

  addingRequests.value = true
  try {
    // 这里需要调用添加请求到套件的API
    await api.post(`/api-testing/test-suites/${selectedSuite.value.id}/add-requests/`, {
      request_ids: requestIds
    })

    ElMessage.success(t('apiTesting.messages.success.addSuccess'))
    showAddRequestDialog.value = false
    // 重新加载当前测试套件详情
    await reloadCurrentSuite()
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.addFailed'))
  } finally {
    addingRequests.value = false
  }
}

const updateRequestEnabled = async (suiteRequest) => {
  try {
    await api.put(`/api-testing/test-suite-requests/${suiteRequest.id}/`, {
      enabled: suiteRequest.enabled
    })
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.updateFailed'))
    suiteRequest.enabled = !suiteRequest.enabled
  }
}

const editSuiteRequest = (suiteRequest) => {
  const params = suiteRequest.params || {}
  const headers = suiteRequest.headers || {}
  const body = suiteRequest.body || null
  const otherType = body && !['json', 'raw', 'none'].includes(body.type) ? body.type : ''
  const req = suiteRequest.request || {}
  const interfaceParams = req.params || {}
  const interfaceHeaders = req.headers || {}

  caseForm.id = suiteRequest.id
  caseForm.name = suiteRequest.name || ''
  caseForm.description = suiteRequest.description || ''
  // 参数：以接口定义为基础，用例覆盖值优先，方便直接修改
  const mergedParams = { ...interfaceParams, ...params }
  caseForm.paramsRows = Object.keys(mergedParams).map(key => ({ key, value: String(mergedParams[key] ?? '') }))

  // 请求头：兼容接口的数组 [{key,value,enabled}] 与对象两种格式，再叠加用例覆盖
  const mergedHeaders = {}
  if (Array.isArray(interfaceHeaders)) {
    interfaceHeaders.forEach(h => {
      if (h && h.enabled !== false && h.key) mergedHeaders[h.key] = h.value ?? ''
    })
  } else {
    Object.assign(mergedHeaders, interfaceHeaders)
  }
  Object.assign(mergedHeaders, headers)
  caseForm.headersRows = Object.keys(mergedHeaders).map(key => ({ key, value: String(mergedHeaders[key] ?? '') }))

  caseForm.interfaceBody = req.body || null
  caseForm.bodyOther = otherType ? body : null
  caseForm.bodyOtherType = otherType
  caseForm.assertions = JSON.parse(JSON.stringify(suiteRequest.assertions || []))
  caseForm.extractRules = JSON.parse(JSON.stringify(suiteRequest.extract_rules || []))

  if (otherType) {
    caseForm.bodyType = 'other'
    caseForm.bodyText = ''
  } else if (!body) {
    caseForm.bodyType = 'inherit'
    caseForm.bodyText = ''
  } else if (body.type === 'none') {
    caseForm.bodyType = 'none'
    caseForm.bodyText = ''
  } else if (body.type === 'json') {
    caseForm.bodyType = 'json'
    caseForm.bodyText = typeof body.data === 'string' ? body.data : JSON.stringify(body.data, null, 2)
  } else {
    caseForm.bodyType = 'raw'
    caseForm.bodyText = String(body.data ?? '')
  }

  caseTab.value = 'params'
  showCaseDialog.value = true
}

const resetCaseForm = () => {
  caseForm.id = null
  caseForm.name = ''
  caseForm.description = ''
  caseForm.paramsRows = []
  caseForm.headersRows = []
  caseForm.bodyType = 'inherit'
  caseForm.bodyText = ''
  caseForm.bodyOther = null
  caseForm.bodyOtherType = ''
  caseForm.interfaceBody = null
  caseForm.assertions = []
  caseForm.extractRules = []
}

const addKvRow = (rows) => {
  rows.push({ key: '', value: '' })
}

const removeKvRow = (rows, index) => {
  rows.splice(index, 1)
}

const saveSuiteRequest = async () => {
  if (!caseForm.id) return

  const params = {}
  caseForm.paramsRows.forEach(row => {
    if (row.key) params[row.key] = row.value
  })
  const headers = {}
  caseForm.headersRows.forEach(row => {
    if (row.key) headers[row.key] = row.value
  })

  let body = null
  if (caseForm.bodyType === 'none') {
    body = { type: 'none', data: null }
  } else if (caseForm.bodyType === 'json') {
    try {
      body = { type: 'json', data: JSON.parse(caseForm.bodyText) }
    } catch (e) {
      ElMessage.warning(t('apiTesting.messages.warning.invalidJson'))
      return
    }
  } else if (caseForm.bodyType === 'raw') {
    body = { type: 'raw', data: caseForm.bodyText }
  } else if (caseForm.bodyType === 'other') {
    body = caseForm.bodyOther
  } else {
    body = null
  }

  savingCase.value = true
  try {
    await api.put(`/api-testing/test-suite-requests/${caseForm.id}/`, {
      name: caseForm.name,
      description: caseForm.description,
      params,
      headers,
      body,
      assertions: caseForm.assertions,
      extract_rules: caseForm.extractRules
    })
    ElMessage.success(t('apiTesting.messages.success.save'))
    showCaseDialog.value = false
    await reloadCurrentSuite()
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.updateFailed'))
  } finally {
    savingCase.value = false
  }
}

const editAssertions = (suiteRequest) => {
  currentAssertionRow.value = suiteRequest
  assertionRules.value = JSON.parse(JSON.stringify(suiteRequest.assertions || []))
  showAssertionDialog.value = true
}

const resetAssertionForm = () => {
  currentAssertionRow.value = null
  assertionRules.value = []
}

const addAssertion = (list) => {
  list.push({
    name: `${t('apiTesting.interface.assertion')}${list.length + 1}`,
    type: 'status_code',
    expected: 200
  })
}

const removeAssertion = (list, index) => {
  list.splice(index, 1)
}

const onAssertionTypeChange = (assertion) => {
  if (assertion.type === 'status_code') {
    assertion.expected = 200
  } else if (assertion.type === 'response_time') {
    assertion.expected = 1000
  } else if (assertion.type === 'contains') {
    assertion.expected = ''
  } else if (assertion.type === 'json_path') {
    assertion.json_path = ''
    assertion.expected = ''
  } else if (assertion.type === 'header') {
    assertion.header_name = ''
    assertion.expected_value = ''
  } else if (assertion.type === 'equals') {
    assertion.expected = ''
  }
}

const saveAssertions = async () => {
  if (!currentAssertionRow.value) return
  savingAssertions.value = true
  try {
    await api.put(`/api-testing/test-suite-requests/${currentAssertionRow.value.id}/`, {
      assertions: assertionRules.value
    })
    ElMessage.success(t('apiTesting.messages.success.save'))
    showAssertionDialog.value = false
    await reloadCurrentSuite()
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.updateFailed'))
  } finally {
    savingAssertions.value = false
  }
}

const editExtractRules = (suiteRequest) => {
  currentExtractRow.value = suiteRequest
  extractRules.value = JSON.parse(JSON.stringify(suiteRequest.extract_rules || []))
  showExtractDialog.value = true
}

const resetExtractForm = () => {
  currentExtractRow.value = null
  extractRules.value = []
}

const addExtractRule = (list) => {
  list.push({
    enabled: true,
    name: '',
    source: 'body',
    json_path: ''
  })
}

const removeExtractRule = (list, index) => {
  list.splice(index, 1)
}

const saveExtractRules = async () => {
  if (!currentExtractRow.value) return
  const rules = extractRules.value
  for (const rule of rules) {
    if (!rule.name) {
      ElMessage.warning(t('apiTesting.messages.warning.extractNameRequired'))
      return
    }
    if (rule.source === 'body' && !rule.json_path) {
      ElMessage.warning(t('apiTesting.messages.warning.extractJsonPathRequired'))
      return
    }
    if (rule.source === 'header' && !rule.header_name) {
      ElMessage.warning(t('apiTesting.messages.warning.extractHeaderNameRequired'))
      return
    }
  }

  savingExtract.value = true
  try {
    await api.put(`/api-testing/test-suite-requests/${currentExtractRow.value.id}/`, {
      extract_rules: rules
    })
    ElMessage.success(t('apiTesting.messages.success.save'))
    showExtractDialog.value = false
    await reloadCurrentSuite()
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.updateFailed'))
  } finally {
    savingExtract.value = false
  }
}

const moveSuiteRequest = async (suiteRequest, direction) => {
  const requests = selectedSuite.value?.suite_requests || []
  const index = requests.findIndex(item => item.id === suiteRequest.id)
  const target = index + direction
  if (index === -1 || target < 0 || target >= requests.length) return

  const items = [...requests]
  const temp = items[index]
  items[index] = items[target]
  items[target] = temp
  items.forEach((item, i) => {
    item.order = i
  })
  selectedSuite.value.suite_requests = items

  try {
    await api.post('/api-testing/test-suite-requests/reorder/', {
      items: items.map((item, i) => ({ id: item.id, order: i }))
    })
    await reloadCurrentSuite()
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.updateFailed'))
  }
}

const duplicateSuiteRequest = async (suiteRequest) => {
  try {
    await api.post(`/api-testing/test-suite-requests/${suiteRequest.id}/duplicate/`)
    ElMessage.success(t('apiTesting.messages.success.copy'))
    await reloadCurrentSuite()
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.copyFailed'))
  }
}

const removeRequest = async (suiteRequest) => {
  try {
    await ElMessageBox.confirm(t('apiTesting.automation.confirmRemoveRequest'), t('apiTesting.automation.confirmRemove'), {
      confirmButtonText: t('apiTesting.common.confirm'),
      cancelButtonText: t('apiTesting.common.cancel'),
      type: 'warning',
      customClass: 'automation-messagebox'
    })

    await api.delete(`/api-testing/test-suite-requests/${suiteRequest.id}/`)
    ElMessage.success(t('apiTesting.messages.success.removeSuccess'))
    // 重新加载当前测试套件详情
    await reloadCurrentSuite()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('apiTesting.messages.error.removeFailed'))
    }
  }
}

const reloadCurrentSuite = async () => {
  if (!selectedSuite.value) return

  try {
    // 重新加载当前测试套件的详细信息
    const response = await api.get(`/api-testing/test-suites/${selectedSuite.value.id}/`)
    const updatedSuite = response.data

    // 强制重新设置响应式数据
    selectedSuite.value = { ...updatedSuite }

    // 同时更新测试套件列表中对应的套件
    const index = testSuites.value.findIndex(suite => suite.id === updatedSuite.id)
    if (index !== -1) {
      testSuites.value[index] = { ...updatedSuite }
    }
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.refreshSuiteFailed'))
  }
}

const viewExecutionDetail = (execution) => {
  currentExecution.value = execution
  showExecutionDialog.value = true
}

const formatExecutionResults = (results) => {
  if (!results || !Array.isArray(results)) return []
  return results
}

const formatJson = (data) => {
  try {
    return JSON.stringify(data, null, 2)
  } catch (e) {
    return String(data)
  }
}

const formatInterfaceBody = (body) => {
  if (!body) return ''
  if (body.type === 'json') {
    return typeof body.data === 'string' ? body.data : JSON.stringify(body.data, null, 2)
  }
  if (body.type === 'raw') {
    return String(body.data ?? '')
  }
  return JSON.stringify(body, null, 2)
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.automation-testing {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f2f2f0;
  color: #191919;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  --ef-ink: #191919;
  --ef-paper: #f2f2f0;
  --ef-signal: #fffa00;
  --ef-state: #00ffa2;
  --ef-muted: #8a8a86;
  --ef-line: #dcdcd7;
  --ef-line-strong: #c9c9c3;
  --ef-line-soft: #f0f0ec;
  --ef-rail: #fafaf8;
  --ef-surface: #ffffff;
  --ef-dock: #191919;
  --ef-font-tech: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  --ef-font-display: "Arial Narrow", "Roboto Condensed", "DIN Condensed", sans-serif;
  --ef-font-mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--ef-line);
}

.header h3 {
  margin: 0;
  color: var(--ef-ink);
  font-family: var(--ef-font-display);
  font-size: 22px;
  letter-spacing: .08em;
  text-transform: uppercase;
  position: relative;
  padding-bottom: 8px;
}

.header h3::after {
  content: "";
  position: absolute;
  left: 0;
  bottom: 0;
  width: 36px;
  height: 3px;
  background: var(--ef-signal);
}

.content-layout {
  display: flex;
  flex: 1;
  gap: 20px;
  overflow: hidden;
}

.sidebar {
  width: 300px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.project-selector {
  background: var(--ef-rail);
  padding: 15px;
  border-radius: 2px;
  border: 1px solid var(--ef-line-strong);
}

.suite-list {
  background: var(--ef-rail);
  border-radius: 2px;
  border: 1px solid var(--ef-line-strong);
  overflow: hidden;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background: var(--ef-paper);
  border-bottom: 1px solid var(--ef-line);
  font-family: var(--ef-font-tech);
  font-size: 11px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--ef-muted);
  font-weight: 600;
}

.suite-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 15px;
  border-bottom: 1px solid var(--ef-line-soft);
  cursor: pointer;
  transition: background-color .15s ease, box-shadow .15s ease;
}

.suite-item:hover {
  background: var(--ef-paper);
}

.suite-item.active {
  background: rgba(255, 250, 0, .10);
  border-color: var(--ef-line-strong);
  box-shadow: inset 3px 0 0 var(--ef-signal);
}

.suite-info {
  flex: 1;
}

.suite-name {
  font-weight: 600;
  color: var(--ef-ink);
  margin-bottom: 4px;
}

.suite-meta {
  font-size: 11px;
  color: var(--ef-muted);
  font-family: var(--ef-font-tech);
  letter-spacing: .04em;
}

.main-content {
  flex: 1;
  background: var(--ef-rail);
  border-radius: 2px;
  border: 1px solid var(--ef-line-strong);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.suite-detail {
  flex: 1;
  padding: 20px;
  overflow: auto;
}

.suite-header {
  margin-bottom: 30px;
}

.suite-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.suite-title h4 {
  margin: 0;
  color: var(--ef-ink);
  font-family: var(--ef-font-display);
  font-size: 18px;
  letter-spacing: .06em;
  text-transform: uppercase;
}

.suite-actions {
  display: flex;
  gap: 10px;
}

.suite-description {
  color: #606266;
  margin-bottom: 10px;
}

.suite-meta {
  display: flex;
  gap: 15px;
  align-items: center;
}

.meta-text {
  font-size: 11px;
  color: var(--ef-muted);
  font-family: var(--ef-font-tech);
  letter-spacing: .04em;
}

.requests-section,
.executions-section {
  margin-bottom: 30px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.section-header h5 {
  margin: 0;
  color: var(--ef-ink);
  font-size: 14px;
  font-family: var(--ef-font-display);
  letter-spacing: .08em;
  text-transform: uppercase;
}

.add-request-content {
  max-height: 400px;
  overflow-y: auto;
}

.request-tree-node {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 1;
}

.method-tag {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 2px;
  color: white;
  font-weight: 700;
  margin-left: auto;
  font-family: var(--ef-font-tech);
  letter-spacing: .06em;
}

.method-tag.get { background: #16a34a; }
.method-tag.post { background: #3b82f6; }
.method-tag.put { background: #d97706; }
.method-tag.delete { background: #dc2626; }
.method-tag.patch { background: #0d9488; }

.execution-detail {
  max-height: 70vh;
  overflow-y: auto;
}

.execution-summary {
  margin-bottom: 30px;
  padding: 20px;
  background: var(--ef-paper);
  border: 1px solid var(--ef-line);
  border-radius: 2px;
}

.execution-summary :deep(.el-statistic__head) {
  font-family: var(--ef-font-tech);
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--ef-muted);
}

.execution-summary :deep(.el-statistic__content) {
  font-family: var(--ef-font-display);
  font-weight: 700;
  color: var(--ef-ink);
}

.execution-results h4 {
  margin: 0 0 15px 0;
  color: var(--ef-ink);
  font-family: var(--ef-font-display);
  letter-spacing: .06em;
  text-transform: uppercase;
}

.case-name {
  font-weight: 500;
}

.kv-editor {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kv-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kv-row .el-input {
  flex: 1;
}

.kv-row > span:first-child,
.kv-row > span:nth-child(2) {
  flex: 1;
  color: var(--ef-muted);
  font-size: 12px;
}

.kv-header span {
  flex: 1;
  color: var(--ef-muted);
  font-size: 11px;
  font-family: var(--ef-font-tech);
  letter-spacing: .06em;
  text-transform: uppercase;
}

.kv-tip {
  color: var(--ef-muted);
  font-size: 12px;
  line-height: 1.6;
  background: var(--ef-paper);
  border: 1px solid var(--ef-line);
  padding: 8px 12px;
  border-radius: 2px;
  font-family: var(--ef-font-tech);
  letter-spacing: .02em;
}

.body-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.body-textarea {
  width: 100%;
  font-family: var(--ef-font-mono);
}

.body-empty {
  color: var(--ef-muted);
  font-size: 13px;
  padding: 20px 0;
}

.body-inherit-preview {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.body-inherit-preview pre {
  margin: 0;
  padding: 10px;
  background: var(--ef-paper);
  border: 1px solid var(--ef-line);
  border-radius: 2px;
  max-height: 240px;
  overflow: auto;
  font-size: 12px;
  font-family: var(--ef-font-mono);
}

.body-inherit-title {
  font-size: 13px;
  color: #606266;
  font-weight: 600;
}

.assertions-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.assertions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 50vh;
  overflow-y: auto;
}

.assertion-item {
  border: 1px solid var(--ef-line);
  border-radius: 2px;
  padding: 10px;
  background: var(--ef-rail);
}

.assertion-header {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.assertion-name {
  flex: 1;
}

.assertion-config {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.assertion-params {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.extract-tip {
  margin-bottom: 14px;
}

.extract-rule-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.extract-rule-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.execution-expand {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 24px;
}

.expand-block pre {
  margin: 6px 0 0 0;
  padding: 10px;
  background: #191919;
  color: #d4d4d4;
  border-radius: 2px;
  max-height: 240px;
  overflow: auto;
  font-size: 12px;
  font-family: var(--ef-font-mono);
}

.expand-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--ef-ink);
}

.extract-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  padding: 0 5px;
  background: rgba(255, 250, 0, .35);
  border: 1px solid var(--ef-ink);
  color: var(--ef-ink);
  font-weight: 700;
  font-family: var(--ef-font-tech);
}

/* ============================================================
   Endfield / moderate - Element Plus unification
   Charcoal default + signal-yellow accent; semantic colors only
   surface on hover or as status. Mirrors InterfaceManagement.vue.
   ============================================================ */
.automation-testing :deep(.el-button) { border-radius: 2px; }

.automation-testing :deep(.el-button--primary) {
  background: var(--ef-ink);
  border-color: var(--ef-ink);
  color: #ffffff;
}
.automation-testing :deep(.el-button--primary:hover) {
  background: #2c2c2c;
  border-color: var(--ef-signal);
  color: var(--ef-signal);
}
.automation-testing :deep(.el-button--primary.is-plain) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.automation-testing :deep(.el-button--primary.is-plain:hover) {
  background: rgba(255, 250, 0, .12);
  border-color: var(--ef-signal);
  color: var(--ef-ink);
}
.automation-testing :deep(.el-button--danger) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.automation-testing :deep(.el-button--danger:hover) {
  background: rgba(220, 38, 38, .08);
  border-color: #b91c1c;
  color: #b91c1c;
}
.automation-testing :deep(.el-button--success) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.automation-testing :deep(.el-button--success:hover) {
  background: rgba(22, 163, 74, .1);
  border-color: #15803d;
  color: #15803d;
}
.automation-testing :deep(.el-button--warning) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.automation-testing :deep(.el-button--warning:hover) {
  background: rgba(217, 119, 6, .1);
  border-color: #b45309;
  color: #b45309;
}
.automation-testing :deep(.el-button--info) {
  background: transparent;
  border-color: var(--ef-line-strong);
  color: var(--ef-muted);
}
.automation-testing :deep(.el-button--info:hover) {
  border-color: var(--ef-signal);
  color: var(--ef-ink);
}
.automation-testing :deep(.el-button--primary.is-link) {
  background: transparent;
  border-color: transparent;
  color: var(--ef-ink);
  font-weight: 600;
}
.automation-testing :deep(.el-button--primary.is-link:hover) {
  color: var(--ef-ink);
  background: rgba(255, 250, 0, .18);
  border-color: transparent;
}
.automation-testing :deep(.el-button.is-text) {
  color: var(--ef-muted);
}
.automation-testing :deep(.el-button.is-text:hover) {
  color: var(--ef-ink);
  background: rgba(255, 250, 0, .14);
}

.automation-testing :deep(.el-input__wrapper),
.automation-testing :deep(.el-textarea__inner),
.automation-testing :deep(.el-select__wrapper) {
  background: var(--ef-surface);
  box-shadow: 0 0 0 1px var(--ef-line-strong) inset;
  border-radius: 2px;
}
.automation-testing :deep(.el-input__wrapper.is-focus),
.automation-testing :deep(.el-select__wrapper.is-focused),
.automation-testing :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--ef-ink) inset;
}
.automation-testing :deep(.el-input__inner) {
  color: var(--ef-ink);
  font-size: 13px;
}
.automation-testing :deep(.el-textarea__inner) {
  font-family: var(--ef-font-mono);
  font-size: 12px;
  line-height: 1.6;
}

.automation-testing :deep(.el-tag) {
  border-radius: 2px;
  font-family: var(--ef-font-tech);
  letter-spacing: .04em;
}
.automation-testing :deep(.el-tag--primary) { background: rgba(25, 25, 25, .08); border-color: transparent; color: var(--ef-ink); }
.automation-testing :deep(.el-tag--success) { background: rgba(22, 163, 74, .12); border-color: transparent; color: #15803d; }
.automation-testing :deep(.el-tag--warning) { background: rgba(217, 119, 6, .12); border-color: transparent; color: #b45309; }
.automation-testing :deep(.el-tag--danger) { background: rgba(220, 38, 38, .12); border-color: transparent; color: #b91c1c; }
.automation-testing :deep(.el-tag--info) { background: rgba(25, 25, 25, .08); border-color: transparent; color: var(--ef-muted); }

.automation-testing :deep(.el-switch__core) {
  background: var(--ef-line-strong);
  border-color: var(--ef-line-strong);
  border-radius: 10px;
}
.automation-testing :deep(.el-switch__action) { background-color: #ffffff; }
.automation-testing :deep(.el-switch.is-checked .el-switch__core) {
  background: var(--ef-signal);
  border-color: var(--ef-signal);
}
.automation-testing :deep(.el-switch.is-checked .el-switch__action) { background-color: var(--ef-ink); }

.automation-testing :deep(.el-table) {
  --el-table-border-color: var(--ef-line);
  --el-table-header-bg-color: var(--ef-paper);
  --el-table-header-text-color: var(--ef-ink);
  --el-table-row-hover-bg-color: rgba(255, 250, 0, .10);
  --el-table-text-color: var(--ef-ink);
  font-size: 12px;
}
.automation-testing :deep(.el-table th.el-table__cell) { font-weight: 700; }

.automation-testing :deep(.el-scrollbar__thumb) { background-color: var(--ef-line-strong); }
.automation-testing :deep(.el-empty__description) { color: var(--ef-muted); }

.automation-testing :deep(.el-button:focus-visible),
.automation-testing :deep(.el-input__wrapper:focus-visible),
.automation-testing :deep(.el-textarea__inner:focus-visible),
.automation-testing :deep(.el-select__wrapper:focus-visible) {
  outline: 2px solid var(--ef-signal);
  outline-offset: 1px;
}

@media (prefers-reduced-motion: reduce) {
  .suite-item,
  .automation-testing :deep(.el-button) {
    transition: none;
  }
}
</style>

<style>
/* ============================================================
   Endfield / moderate - teleported surfaces
   Dialogs, dropdowns, select poppers and message boxes are moved
   to <body> by Element Plus, so they are styled here globally and
   gated by the explicit class hooks added in the template.
   ============================================================ */
.automation-modal {
  background: rgba(25, 25, 25, .5) !important;
  -webkit-backdrop-filter: blur(2px);
  backdrop-filter: blur(2px);
}
.automation-dialog {
  border-radius: 2px;
  border: 1px solid #c9c9c3;
  box-shadow: 12px 12px 0 rgba(25, 25, 25, .08);
  background: #fafaf8;
  color: #191919;
  overflow: hidden;
}
.automation-dialog .el-dialog__header {
  margin: 0;
  padding: 14px 18px;
  background: #191919;
  color: #ffffff;
  border-bottom: 2px solid #fffa00;
}
.automation-dialog .el-dialog__title {
  font-family: "Arial Narrow", "Roboto Condensed", "DIN Condensed", sans-serif;
  font-size: 16px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #ffffff;
}
.automation-dialog .el-dialog__headerbtn { top: 14px; }
.automation-dialog .el-dialog__headerbtn .el-dialog__close { color: rgba(255, 255, 255, .6); }
.automation-dialog .el-dialog__headerbtn:hover .el-dialog__close { color: #fffa00; }
.automation-dialog .el-dialog__body { padding: 16px 18px; }
.automation-dialog .el-dialog__footer {
  padding: 10px 18px 14px;
  border-top: 1px solid #dcdcd7;
  text-align: right;
}

.automation-dialog .el-form-item__label {
  font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #8a8a86;
}

.automation-dialog .el-input__wrapper,
.automation-dialog .el-textarea__inner,
.automation-dialog .el-select__wrapper {
  background: #ffffff;
  box-shadow: 0 0 0 1px #c9c9c3 inset;
  border-radius: 2px;
}
.automation-dialog .el-input__wrapper.is-focus,
.automation-dialog .el-select__wrapper.is-focused,
.automation-dialog .el-textarea__inner:focus {
  box-shadow: 0 0 0 1px #191919 inset;
}
.automation-dialog .el-textarea__inner {
  font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
}
.automation-dialog .el-input-number__increase:hover,
.automation-dialog .el-input-number__decrease:hover {
  color: #191919;
  background: rgba(255, 250, 0, .14);
}

.automation-dialog .el-button { border-radius: 2px; }
.automation-dialog .el-button--primary {
  background: #191919;
  border-color: #191919;
  color: #ffffff;
}
.automation-dialog .el-button--primary:hover {
  background: #2c2c2c;
  border-color: #fffa00;
  color: #fffa00;
}
.automation-dialog .el-button--primary.is-plain {
  background: transparent;
  border-color: #191919;
  color: #191919;
}
.automation-dialog .el-button--primary.is-plain:hover {
  background: rgba(255, 250, 0, .12);
  border-color: #fffa00;
  color: #191919;
}
.automation-dialog .el-button--danger {
  background: transparent;
  border-color: #191919;
  color: #191919;
}
.automation-dialog .el-button--danger:hover {
  background: rgba(220, 38, 38, .08);
  border-color: #b91c1c;
  color: #b91c1c;
}
.automation-dialog .el-button--success {
  background: transparent;
  border-color: #191919;
  color: #191919;
}
.automation-dialog .el-button--success:hover {
  background: rgba(22, 163, 74, .1);
  border-color: #15803d;
  color: #15803d;
}
.automation-dialog .el-button--warning {
  background: transparent;
  border-color: #191919;
  color: #191919;
}
.automation-dialog .el-button--warning:hover {
  background: rgba(217, 119, 6, .1);
  border-color: #b45309;
  color: #b45309;
}
.automation-dialog .el-button--info {
  background: transparent;
  border-color: #c9c9c3;
  color: #8a8a86;
}
.automation-dialog .el-button--info:hover {
  border-color: #fffa00;
  color: #191919;
}
.automation-dialog .el-button--primary.is-link {
  background: transparent;
  border-color: transparent;
  color: #191919;
  font-weight: 600;
}
.automation-dialog .el-button--primary.is-link:hover {
  color: #191919;
  background: rgba(255, 250, 0, .18);
  border-color: transparent;
}
.automation-dialog .el-button:focus-visible,
.automation-dialog .el-input__wrapper:focus-visible,
.automation-dialog .el-textarea__inner:focus-visible,
.automation-dialog .el-select__wrapper:focus-visible {
  outline: 2px solid #fffa00;
  outline-offset: 1px;
}

.automation-dialog .el-table {
  --el-table-border-color: #dcdcd7;
  --el-table-header-bg-color: #f2f2f0;
  --el-table-header-text-color: #191919;
  --el-table-row-hover-bg-color: rgba(255, 250, 0, .10);
  --el-table-text-color: #191919;
  font-size: 12px;
}
.automation-dialog .el-table th.el-table__cell { font-weight: 700; }

.automation-dialog .el-tabs__header { background: #f2f2f0; margin-bottom: 12px; }
.automation-dialog .el-tabs__nav-wrap::after { background: #dcdcd7; }
.automation-dialog .el-tabs__item {
  font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #8a8a86;
}
.automation-dialog .el-tabs__item.is-active {
  color: #191919;
  font-weight: 700;
  background: #fafaf8;
}
.automation-dialog .el-tabs--card > .el-tabs__header .el-tabs__item.is-active {
  border-top: 2px solid #fffa00;
}
.automation-dialog .el-tabs__active-bar { background: #fffa00; height: 2px; }

.automation-dialog .el-checkbox__inner {
  width: 14px;
  height: 14px;
  border: 1px solid #191919;
  border-radius: 0;
  background: #ffffff;
}
.automation-dialog .el-checkbox__input:hover .el-checkbox__inner { border-color: #191919; }
.automation-dialog .el-checkbox.is-checked .el-checkbox__inner {
  background: #fffa00;
  border-color: #fffa00;
}
.automation-dialog .el-checkbox.is-checked .el-checkbox__inner::after { border-color: #191919; }
.automation-dialog .el-tree {
  background: transparent;
  --el-tree-node-hover-bg-color: rgba(255, 250, 0, .08);
  --el-tree-node-expanded-bg-color: transparent;
}

.automation-dialog .el-switch__core {
  background: #c9c9c3;
  border-color: #c9c9c3;
  border-radius: 10px;
}
.automation-dialog .el-switch__action { background-color: #ffffff; }
.automation-dialog .el-switch.is-checked .el-switch__core {
  background: #fffa00;
  border-color: #fffa00;
}
.automation-dialog .el-switch.is-checked .el-switch__action { background-color: #191919; }

.automation-dialog .el-alert {
  border-radius: 2px;
  background: #f2f2f0;
  border: 1px solid #dcdcd7;
}
.automation-dialog .el-alert__title { color: #191919; font-size: 12px; }

.automation-popper {
  border-radius: 2px;
  border-color: #c9c9c3;
  box-shadow: 6px 6px 0 rgba(25, 25, 25, .06);
}
.automation-popper .el-select-dropdown__item.is-hovering {
  background: rgba(255, 250, 0, .14);
  color: #191919;
}
.automation-popper .el-select-dropdown__item.is-selected {
  color: #191919;
  font-weight: 700;
}
.automation-popper .el-dropdown-menu {
  padding: 4px 0;
  background: #fafaf8;
}
.automation-popper .el-dropdown-menu__item {
  font-size: 12px;
  color: #191919;
}
.automation-popper .el-dropdown-menu__item:not(.is-disabled):hover,
.automation-popper .el-dropdown-menu__item:not(.is-disabled):focus {
  background: rgba(255, 250, 0, .14);
  color: #191919;
}
.automation-popper .el-dropdown-menu__item--divided { border-top-color: #dcdcd7; }

.automation-messagebox {
  border-radius: 2px;
  border: 1px solid #c9c9c3;
  box-shadow: 12px 12px 0 rgba(25, 25, 25, .08);
  background: #fafaf8;
  padding: 0;
}
.automation-messagebox .el-message-box__header {
  margin: 0;
  padding: 12px 16px;
  background: #191919;
}
.automation-messagebox .el-message-box__title {
  color: #ffffff;
  font-family: "Arial Narrow", "Roboto Condensed", "DIN Condensed", sans-serif;
  font-size: 14px;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.automation-messagebox .el-message-box__headerbtn .el-message-box__close { color: rgba(255, 255, 255, .6); }
.automation-messagebox .el-message-box__headerbtn:hover .el-message-box__close { color: #fffa00; }
.automation-messagebox .el-message-box__content { color: #191919; padding: 18px 16px; }
.automation-messagebox .el-message-box__btns {
  padding: 10px 16px 14px;
  border-top: 1px solid #dcdcd7;
  text-align: right;
}
.automation-messagebox .el-message-box__btns .el-button { border-radius: 2px; }
.automation-messagebox .el-message-box__btns .el-button--primary {
  background: #191919;
  border-color: #191919;
  color: #ffffff;
}
.automation-messagebox .el-message-box__btns .el-button--primary:hover {
  background: #2c2c2c;
  border-color: #fffa00;
  color: #fffa00;
}
.automation-messagebox .el-button--default {
  background: transparent;
  border-color: #c9c9c3;
  color: #191919;
}
.automation-messagebox .el-button--default:hover {
  border-color: #191919;
  color: #191919;
}
</style>
