<template>
  <div class="interface-management">
    <!-- Page head: editorial title + live status strip -->
    <header class="ef-page-head">
      <div class="ef-page-head__title">
        <p class="ef-kicker">FIELD OPERATIONS / INTERFACE CATALOG</p>
        <h1 class="ef-page-title">{{ $t('menu.interfaceManagement') }}</h1>
        <span class="ef-rule" aria-hidden="true"></span>
      </div>
      <div class="ef-page-head__status">
        <div class="ef-status-item">
          <span class="ef-status-label">PROJECT</span>
          <span class="ef-status-value">{{ currentProjectName }}</span>
        </div>
        <div class="ef-status-item">
          <span class="ef-status-label">ENV</span>
          <span class="ef-status-value">{{ currentEnvName || $t('apiTesting.common.noEnvironment') }}</span>
        </div>
        <div class="ef-status-item">
          <span class="ef-status-label">REQUESTS</span>
          <span class="ef-status-value">{{ requestCount }}</span>
        </div>
      </div>
    </header>

    <!-- Charcoal utility dock: project switch, search, primary actions -->
    <div class="ef-dock">
      <el-select
        v-model="selectedProject"
        :placeholder="$t('apiTesting.common.selectProject')"
        @change="onProjectChange"
        class="ef-dock__project"
      >
        <el-option
          v-for="project in projects"
          :key="project.id"
          :label="project.name"
          :value="project.id"
        />
      </el-select>
      <el-input
        v-model="searchKeyword"
        :placeholder="$t('apiTesting.interface.searchInterface')"
        size="small"
        clearable
        @input="onSearchDebounced"
        @keyup.enter="onSearch(searchKeyword)"
        class="ef-dock__search"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <div class="ef-dock__actions">
        <el-button class="ef-dock-btn" size="small" @click="openCreateCollectionDialog" :title="$t('apiTesting.interface.createCollection')">
          <el-icon><Folder /></el-icon>
          <span>{{ $t('apiTesting.interface.createCollection') }}</span>
        </el-button>
        <el-button type="primary" class="ef-dock-btn ef-dock-btn--primary" size="small" @click="createEmptyRequest" :title="$t('apiTesting.interface.addInterface')">
          <el-icon><Plus /></el-icon>
          <span>{{ $t('apiTesting.interface.addInterface') }}</span>
        </el-button>
      </div>
    </div>

    <div class="interface-layout">
      <!-- 左侧集合树 -->
      <div class="sidebar">
        <div class="collection-tree" v-show="!searchKeyword || searchKeyword.trim() === ''">
          <el-tree
            ref="treeRef"
            :data="collections"
            :props="treeProps"
            node-key="id"
            :expand-on-click-node="false"
            :default-expanded-keys="expandedKeys"
            @node-click="onNodeClick"
            @node-contextmenu="onNodeRightClick"
            @node-expand="onNodeExpand"
            @node-collapse="onNodeCollapse"
          >
            <template #default="{ node, data }">
              <div class="tree-node" :class="{ 'tree-node--active': selectedRequest && selectedRequest.id === data.id }">
                <el-icon v-if="data.type === 'collection'">
                  <Folder />
                </el-icon>
                <el-icon v-else>
                  <Document />
                </el-icon>

                <!-- 集合名称编辑 -->
                <div v-if="data.type === 'collection' && editingNodeId === data.id" class="node-edit">
                  <el-input
                    v-model="editingNodeName"
                    size="small"
                    @blur="saveCollectionName"
                    @keyup.enter="saveCollectionName"
                    @keyup.esc="cancelEdit"
                    ref="editInputRef"
                  />
                </div>

                <!-- 普通显示模式 -->
                <span v-else class="node-label">{{ node.label }}</span>

                <span v-if="data.type === 'request' && data.request_type !== 'WEBSOCKET'" class="method-tag" :class="(data.method || 'GET').toLowerCase()">
                  {{ data.method || 'GET' }}
                </span>
              </div>
            </template>
          </el-tree>
        </div>

        <!-- 搜索结果 -->
        <div v-if="filteredCollections.length > 0" class="search-results">
          <div class="search-results-header">
            <span>{{ $t('apiTesting.interface.searchResults', { count: filteredCollections.length }) }}</span>
            <el-button size="small" text @click="clearSearch">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
          <div class="search-results-list">
            <div
              v-for="item in filteredCollections"
              :key="item.id"
              class="search-result-item"
              @click="selectSearchResult(item)"
            >
              <el-icon><Document /></el-icon>
              <div class="search-result-content">
                <div class="search-result-name">{{ item.name }}</div>
                <div class="search-result-url">{{ item.url }}</div>
              </div>
              <el-tag v-if="item.matchType === 'name'" type="primary" size="small">{{ $t('apiTesting.interface.name') }}</el-tag>
              <el-tag v-else-if="item.matchType === 'method'" type="warning" size="small">{{ $t('apiTesting.interface.method') }}</el-tag>
              <el-tag v-else type="success" size="small">{{ $t('apiTesting.interface.url') }}</el-tag>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧请求详情 -->
      <div class="main-content">
        <div v-if="!selectedRequest" class="empty-state">
          <el-empty :description="$t('apiTesting.interface.selectInterface')">
            <el-button type="primary" @click="createEmptyRequest">{{ $t('apiTesting.interface.createNewInterface') }}</el-button>
          </el-empty>
        </div>

        <div v-else class="request-detail">
          <!-- 请求基本信息 -->
          <div class="request-header">
            <div class="request-line">
              <!-- HTTP接口显示方法选择器 -->
              <el-select
                v-model="requestMethod"
                class="method-select"
                :class="requestMethod.toLowerCase()"
                :placeholder="'GET'"
                :popper-class="'method-select-dropdown'"
              >
                <el-option
                  v-for="method in availableMethods"
                  :key="method"
                  :label="method"
                  :value="method"
                  :class="method.toLowerCase()"
                />
              </el-select>

              <el-input
                v-model="requestUrl"
                :placeholder="$t('apiTesting.interface.inputRequestUrl')"
                class="url-input"
              >
                <template #prepend>
                  <el-select v-model="selectedEnvironment" :placeholder="$t('apiTesting.interface.environment')" class="env-select">
                    <el-option :label="$t('apiTesting.common.noEnvironment')" :value="null" />
                    <el-option
                      v-for="env in environments"
                      :key="env.id"
                      :label="env.name"
                      :value="env.id"
                    />
                  </el-select>
                </template>
              </el-input>

              <!-- WebSocket连接按钮 -->
              <el-button
                v-if="selectedRequest && selectedRequest.request_type === 'WEBSOCKET'"
                :type="websocketConnectionStatus === 'disconnected' ? 'primary' : 'info'"
                :loading="websocketConnectionStatus === 'connecting'"
                @click="toggleWebSocketConnection"
                class="send-button"
              >
                <span v-if="websocketConnectionStatus === 'disconnected'">{{ $t('apiTesting.interface.connect') }}</span>
                <span v-else-if="websocketConnectionStatus === 'connecting'">{{ $t('apiTesting.interface.connecting') }}</span>
                <span v-else>{{ $t('apiTesting.interface.disconnect') }}</span>
              </el-button>

              <!-- HTTP发送按钮 -->
              <el-button
                v-if="!selectedRequest || !selectedRequest.request_type || selectedRequest.request_type !== 'WEBSOCKET'"
                type="primary"
                @click="sendRequest"
                :loading="sending"
                class="send-button"
              >
                {{ $t('apiTesting.interface.send') }}
              </el-button>
            </div>

            <div class="request-meta">
              <el-input
                v-model="selectedRequest.name"
                :placeholder="$t('apiTesting.interface.requestName')"
                size="small"
                class="name-input"
              />
              <div class="action-buttons">
                <el-button size="small" @click="saveRequest" :loading="saving" ref="saveButtonRef">
                  {{ $t('apiTesting.common.save') }}
                </el-button>
                <el-dropdown split-button type="default" size="small" @click="importCurl">
                  {{ $t('apiTesting.common.import') }}
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click="importCurl">{{ $t('apiTesting.interface.importCurl') }}</el-dropdown-item>
                      <el-dropdown-item @click="exportRequest">{{ $t('apiTesting.interface.exportCurl') }}</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-dropdown split-button type="default" size="small" @click="generateCode('javascript')">
                  {{ $t('apiTesting.interface.generateCode') }}
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click="generateCode('javascript')">JavaScript</el-dropdown-item>
                      <el-dropdown-item @click="generateCode('python')">Python</el-dropdown-item>
                      <el-dropdown-item @click="generateCode('java')">Java</el-dropdown-item>
                      <el-dropdown-item @click="generateCode('curl')">cURL</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
          </div>

          <!-- 请求配置 -->
          <el-tabs v-model="activeTab" class="request-tabs">
            <el-tab-pane label="Params" name="params">
              <KeyValueEditor
                v-model="selectedRequest.params"
                :placeholder-key="$t('apiTesting.interface.paramName')"
                :placeholder-value="$t('apiTesting.interface.paramValue')"
              />
            </el-tab-pane>

            <el-tab-pane label="Headers" name="headers">
              <KeyValueEditor
                ref="headersEditorRef"
                v-model="selectedRequest.headers"
                :placeholder-key="$t('apiTesting.interface.headerName')"
                :placeholder-value="$t('apiTesting.interface.headerValue')"
                @update:modelValue="onHeadersUpdate"
              />
            </el-tab-pane>

            <el-tab-pane label="Body" name="body" v-if="hasBody">
              <div class="body-container">
                <el-radio-group v-model="bodyType" @change="onBodyTypeChange">
                  <el-radio value="none">none</el-radio>
                  <el-radio value="form-data">form-data</el-radio>
                  <el-radio value="x-www-form-urlencoded">x-www-form-urlencoded</el-radio>
                  <el-radio value="raw">raw</el-radio>
                  <el-radio value="binary">binary</el-radio>
                </el-radio-group>

                <div v-if="bodyType === 'form-data'" class="body-content">
                  <KeyValueEditor
                    v-model="formData"
                    :placeholder-key="$t('apiTesting.interface.key')"
                    :placeholder-value="$t('apiTesting.interface.value')"
                    :show-file="true"
                  />
                </div>

                <div v-else-if="bodyType === 'x-www-form-urlencoded'" class="body-content">
                  <KeyValueEditor
                    v-model="formUrlEncoded"
                    :placeholder-key="$t('apiTesting.interface.key')"
                    :placeholder-value="$t('apiTesting.interface.value')"
                  />
                </div>

                <div v-else-if="bodyType === 'raw'" class="body-content">
                  <div class="raw-options">
                    <el-select v-model="rawType" style="width: 150px;">
                      <el-option label="Text" value="text" />
                      <el-option label="JSON" value="json" />
                      <el-option label="HTML" value="html" />
                      <el-option label="XML" value="xml" />
                    </el-select>

                    <el-button
                      size="small"
                      :icon="MagicStick"
                      @click="openDataFactorySelectorForBody('rawBody')"
                      :title="$t('apiTesting.interface.referDataFactory')"
                      class="data-factory-btn"
                    >
                      {{ $t('apiTesting.interface.referDataFactory') }}
                    </el-button>
                    <el-button
                      size="small"
                      :icon="MagicStick"
                      @click="openVariableHelper('rawBody')"
                      :title="$t('apiTesting.interface.variableHelper')"
                      class="variable-helper-btn"
                    >
                      {{ $t('apiTesting.interface.variableHelper') }}
                    </el-button>
                  </div>
                  <el-input
                    ref="rawBodyInputRef"
                    v-model="rawBody"
                    type="textarea"
                    :rows="10"
                    :placeholder="$t('apiTesting.interface.inputRequestBody')"
                    class="raw-body"
                  />
                </div>
              </div>
            </el-tab-pane>

            <!-- HTTP接口专用标签页 -->
            <template v-if="!selectedRequest || selectedRequest.request_type !== 'WEBSOCKET'">
              <el-tab-pane label="Pre-request Script" name="pre-script">
                <div class="script-editor-container">
                  <el-input
                    v-model="selectedRequest.pre_request_script"
                    type="textarea"
                    :rows="10"
                    placeholder="// 请求前脚本，使用JavaScript语法"
                  />
                  <div class="script-buttons">
                    <el-button
                      size="small"
                      :icon="MagicStick"
                      @click="openDataFactorySelectorForScript('pre_request_script')"
                      :title="$t('apiTesting.interface.referDataFactory')"
                      class="script-factory-btn"
                    >
                      {{ $t('apiTesting.interface.referDataFactory') }}
                    </el-button>
                    <el-button
                      size="small"
                      :icon="MagicStick"
                      @click="openVariableHelper('pre_request_script')"
                      :title="$t('apiTesting.interface.variableHelper')"
                      class="script-variable-btn"
                    >
                      {{ $t('apiTesting.interface.variableHelper') }}
                    </el-button>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="Tests" name="tests">
                <div class="script-editor-container">
                  <el-input
                    v-model="selectedRequest.post_request_script"
                    type="textarea"
                    :rows="10"
                    placeholder="// 请求后脚本和测试，使用JavaScript语法"
                  />
                  <div class="script-buttons">
                    <el-button
                      size="small"
                      :icon="MagicStick"
                      @click="openDataFactorySelectorForScript('post_request_script')"
                      :title="$t('apiTesting.interface.referDataFactory')"
                      class="script-factory-btn"
                    >
                      {{ $t('apiTesting.interface.referDataFactory') }}
                    </el-button>
                    <el-button
                      size="small"
                      :icon="MagicStick"
                      @click="openVariableHelper('post_request_script')"
                      :title="$t('apiTesting.interface.variableHelper')"
                      class="script-variable-btn"
                    >
                      {{ $t('apiTesting.interface.variableHelper') }}
                    </el-button>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane :label="$t('apiTesting.interface.assertions')" name="assertions">
                <div class="assertions-editor">
                  <div class="assertions-header">
                    <el-button size="small" type="primary" @click="addAssertion">
                      <el-icon><Plus /></el-icon>
                      {{ $t('apiTesting.interface.addAssertion') }}
                    </el-button>
                  </div>

                  <div class="assertions-list">
                    <div
                      v-for="(assertion, index) in selectedRequest.assertions"
                      :key="index"
                      class="assertion-item"
                    >
                      <div class="assertion-header">
                        <el-input
                          v-model="assertion.name"
                          :placeholder="$t('apiTesting.interface.assertionName')"
                          size="small"
                          class="assertion-name"
                        />
                        <el-button
                          size="small"
                          type="danger"
                          @click="removeAssertion(index)"
                          circle
                        >
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>

                      <div class="assertion-config">
                        <el-select
                          v-model="assertion.type"
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
                          <!-- 状态码断言 -->
                          <div v-if="assertion.type === 'status_code'">
                            <el-input-number
                              v-model="assertion.expected"
                              :min="100"
                              :max="599"
                              size="small"
                              :placeholder="$t('apiTesting.interface.expectedStatusCode')"
                            />
                          </div>

                          <!-- 响应时间断言 -->
                          <div v-else-if="assertion.type === 'response_time'">
                            <el-input-number
                              v-model="assertion.expected"
                              :min="1"
                              size="small"
                              :placeholder="$t('apiTesting.interface.maxResponseTime')"
                            />
                          </div>

                          <!-- 包含文本断言 -->
                          <div v-else-if="assertion.type === 'contains'">
                            <div style="display: flex; align-items: center; width: 100%">
                              <el-input
                                v-model="assertion.expected"
                                :placeholder="$t('apiTesting.interface.expectedContains')"
                                size="small"
                                style="flex: 1"
                              >
                                <template #append>
                                  <el-button
                                    size="small"
                                    :icon="MagicStick"
                                    @click="openDataFactorySelector(assertion, 'expected', index)"
                                    :title="$t('apiTesting.interface.referDataFactory')"
                                    class="data-factory-btn"
                                  />
                                </template>
                              </el-input>
                              <el-tooltip :content="$t('apiTesting.interface.insertDynamicVariable')" placement="top">
                                <el-button size="small" style="margin-left: 5px" @click="openVariableHelperForAssertion(assertion, 'expected', index)" class="variable-helper-btn">
                                  <el-icon><MagicStick /></el-icon>
                                </el-button>
                              </el-tooltip>
                            </div>
                          </div>

                          <!-- JSON路径断言 -->
                          <div v-else-if="assertion.type === 'json_path'">
                            <el-input
                              v-model="assertion.json_path"
                              :placeholder="$t('apiTesting.interface.jsonPathExample')"
                              size="small"
                              class="assertion-input"
                            />
                            <div style="display: flex; align-items: center; width: 100%">
                              <el-input
                                v-model="assertion.expected"
                                :placeholder="$t('apiTesting.interface.expectedValue')"
                                size="small"
                                style="flex: 1"
                              >
                                <template #append>
                                  <el-button
                                    size="small"
                                    :icon="MagicStick"
                                    @click="openDataFactorySelector(assertion, 'expected', index)"
                                    :title="$t('apiTesting.interface.referDataFactory')"
                                    class="data-factory-btn"
                                  />
                                </template>
                              </el-input>
                              <el-tooltip :content="$t('apiTesting.interface.insertDynamicVariable')" placement="top">
                                <el-button size="small" style="margin-left: 5px" @click="openVariableHelperForAssertion(assertion, 'expected', index)" class="variable-helper-btn">
                                  <el-icon><MagicStick /></el-icon>
                                </el-button>
                              </el-tooltip>
                            </div>
                          </div>

                          <!-- 响应头断言 -->
                          <div v-else-if="assertion.type === 'header'">
                            <el-input
                              v-model="assertion.header_name"
                              :placeholder="$t('apiTesting.interface.headerNameLabel')"
                              size="small"
                              class="assertion-input"
                            />
                            <div style="display: flex; align-items: center; width: 100%">
                              <el-input
                                v-model="assertion.expected_value"
                                :placeholder="$t('apiTesting.interface.expectedValue')"
                                size="small"
                                style="flex: 1"
                              >
                                <template #append>
                                  <el-button
                                    size="small"
                                    :icon="MagicStick"
                                    @click="openDataFactorySelector(assertion, 'expected_value', index)"
                                    :title="$t('apiTesting.interface.referDataFactory')"
                                    class="data-factory-btn"
                                  />
                                </template>
                              </el-input>
                              <el-tooltip :content="$t('apiTesting.interface.insertDynamicVariable')" placement="top">
                                <el-button size="small" style="margin-left: 5px" @click="openVariableHelperForAssertion(assertion, 'expected_value', index)" class="variable-helper-btn">
                                  <el-icon><MagicStick /></el-icon>
                                </el-button>
                              </el-tooltip>
                            </div>
                          </div>

                          <!-- 完全匹配断言 -->
                          <div v-else-if="assertion.type === 'equals'">
                            <div style="display: flex; align-items: center; width: 100%">
                              <el-input
                                v-model="assertion.expected"
                                :placeholder="$t('apiTesting.interface.expectedMatch')"
                                size="small"
                                style="flex: 1"
                              >
                                <template #append>
                                  <el-button
                                    size="small"
                                    :icon="MagicStick"
                                    @click="openDataFactorySelector(assertion, 'expected', index)"
                                    :title="$t('apiTesting.interface.referDataFactory')"
                                    class="data-factory-btn"
                                  />
                                </template>
                              </el-input>
                              <el-tooltip :content="$t('apiTesting.interface.insertDynamicVariable')" placement="top">
                                <el-button size="small" style="margin-left: 5px" @click="openVariableHelperForAssertion(assertion, 'expected', index)" class="variable-helper-btn">
                                  <el-icon><MagicStick /></el-icon>
                                </el-button>
                              </el-tooltip>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div v-if="!selectedRequest.assertions || selectedRequest.assertions.length === 0" class="no-assertions">
                      <p>{{ $t('apiTesting.interface.noAssertions') }}</p>
                      <el-button size="small" type="primary" @click="addAssertion">
                        <el-icon><Plus /></el-icon>
                        {{ $t('apiTesting.interface.addFirstAssertion') }}
                      </el-button>
                    </div>
                  </div>
                </div>
              </el-tab-pane>
            </template>

            <!-- WebSocket接口专用标签页 -->
            <template v-else-if="selectedRequest && selectedRequest.request_type === 'WEBSOCKET'">
              <el-tab-pane label="Message" name="message">
                <div class="message-container">
                  <div class="message-input-section">
                    <el-select
                      v-model="websocketMessageType"
                      :placeholder="$t('apiTesting.interface.messageType')"
                      style="width: 150px; margin-bottom: 15px;"
                    >
                      <el-option label="Text" value="text" />
                      <el-option label="JSON" value="json" />
                      <el-option label="Binary" value="binary" />
                    </el-select>

                    <div v-if="websocketMessageType === 'text' || websocketMessageType === 'json'">
                      <el-input
                        v-model="websocketMessageContent"
                        type="textarea"
                        :rows="6"
                        :placeholder="$t('apiTesting.interface.inputWebSocketMessage')"
                      />
                    </div>

                    <div v-else-if="websocketMessageType === 'binary'">
                      <el-upload
                        drag
                        action="#"
                        :auto-upload="false"
                        :show-file-list="false"
                        :on-change="handleWebSocketFileUpload"
                      >
                        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                        <div class="el-upload__text">
                          {{ $t('apiTesting.interface.dragBinaryFile') }}<em>{{ $t('apiTesting.interface.clickUpload') }}</em>
                        </div>
                      </el-upload>
                      <div v-if="websocketBinaryFile" class="uploaded-file">
                        <span>{{ websocketBinaryFile.name }}</span>
                        <el-button size="small" type="danger" @click="clearWebSocketBinaryFile">{{ $t('apiTesting.interface.clear') }}</el-button>
                      </div>
                    </div>

                    <div class="message-actions" style="margin-top: 15px;">
                      <el-button type="primary" @click="sendWebSocketMessage">
                        {{ $t('apiTesting.interface.sendMessage') }}
                      </el-button>
                      <el-button @click="clearWebSocketMessage">
                        {{ $t('apiTesting.interface.clearMessage') }}
                      </el-button>
                    </div>
                  </div>

                  <!-- WebSocket消息历史记录 -->
                  <div class="websocket-response-section" v-if="websocketMessages.length > 0">
                    <h3>{{ $t('apiTesting.interface.messageHistory') }}</h3>
                    <div class="websocket-messages">
                      <div
                        v-for="(msg, index) in websocketMessages.slice().reverse()"
                        :key="index"
                        class="websocket-message-item"
                        :class="msg.type"
                      >
                        <div class="message-header">
                          <span class="message-type" :class="msg.type">
                            {{ msg.type === 'sent' ? $t('apiTesting.interface.messageSent') :
                               msg.type === 'connected' ? $t('apiTesting.interface.messageConnected') :
                               msg.type === 'info' ? $t('apiTesting.interface.messageInfo') :
                               msg.type === 'error' ? $t('apiTesting.interface.messageError') : $t('apiTesting.interface.messageReceived') }}
                          </span>
                          <span class="message-time">{{ msg.timestamp }}</span>
                        </div>
                        <div class="message-content">
                          <pre v-if="msg.type === 'received' && isJsonString(msg.content)">{{ formatJson(msg.content) }}</pre>
                          <pre v-else>{{ msg.content }}</pre>
                        </div>
                      </div>
                    </div>
                    <div class="message-actions">
                      <el-button size="small" @click="clearWebSocketMessages">{{ $t('apiTesting.interface.clearHistory') }}</el-button>
                    </div>
                  </div>
                </div>
              </el-tab-pane>
            </template>
          </el-tabs>

          <!-- 响应区域 -->
          <div v-if="response" class="response-section">
            <div class="response-header">
              <h3>{{ $t('apiTesting.interface.response') }}</h3>
              <div class="response-info">
                <el-tag :type="getStatusType(response.status_code)">
                  {{ response.status_code }}
                </el-tag>
                <span class="response-time">{{ response.response_time ? response.response_time.toFixed(0) : 0 }}ms</span>
              </div>
            </div>

            <el-tabs v-model="responseActiveTab">
              <el-tab-pane label="Body" name="body">
                <div class="response-body">
                  <div class="response-actions">
                    <el-button-group>
                      <el-button size="small" @click="formatResponse">{{ $t('apiTesting.interface.format') }}</el-button>
                      <el-button size="small" @click="copyResponse">{{ $t('apiTesting.interface.copy') }}</el-button>
                      <el-button size="small" @click="toggleJsonPathExtractor">
                        {{ $t('apiTesting.interface.jsonPathExtract') }}
                      </el-button>
                    </el-button-group>
                  </div>
                  <div v-if="showJsonPathExtractor" class="jsonpath-extractor">
                    <div class="jsonpath-input">
                      <el-input
                        v-model="jsonPathExpression"
                        :placeholder="$t('apiTesting.interface.jsonPathExample')"
                        size="small"
                        @input="evaluateJsonPath"
                      >
                        <template #append>
                          <el-button size="small" @click="copyJsonPathResult">{{ $t('apiTesting.interface.copyResult') }}</el-button>
                        </template>
                      </el-input>
                    </div>
                    <div v-if="jsonPathResult !== null" class="jsonpath-result">
                      <strong>{{ $t('apiTesting.interface.extractResult') }}</strong>
                      <pre>{{ jsonPathResult }}</pre>
                    </div>
                  </div>
                  <div class="response-content" v-html="highlightedResponseBody"></div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="Headers" name="headers">
                <div class="response-headers">
                  <div v-for="(value, key) in (response.response_data?.headers || {})" :key="key" class="header-row">
                    <strong>{{ key }}:</strong> {{ value }}
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane :label="$t('apiTesting.interface.assertionResults')" name="assertions" v-if="response.assertions_results && response.assertions_results.length > 0">
                <div class="assertions-results">
                  <div
                    v-for="(result, index) in response.assertions_results"
                    :key="index"
                    class="assertion-result-item"
                    :class="{ 'passed': result.passed, 'failed': !result.passed }"
                  >
                    <div class="assertion-result-header">
                      <el-tag :type="result.passed ? 'success' : 'danger'" size="small">
                        {{ result.passed ? $t('apiTesting.interface.passed') : $t('apiTesting.interface.failed') }}
                      </el-tag>
                      <span class="assertion-name">{{ result.name }}</span>
                    </div>
                    <div class="assertion-result-details">
                      <div class="result-row">
                        <span class="label">{{ $t('apiTesting.interface.expected') }}</span>
                        <span class="value">{{ formatAssertionValue(result.expected) }}</span>
                      </div>
                      <div class="result-row">
                        <span class="label">{{ $t('apiTesting.interface.actual') }}</span>
                        <span class="value">{{ formatAssertionValue(result.actual) }}</span>
                      </div>
                      <div class="result-row" v-if="result.error">
                        <span class="label">{{ $t('apiTesting.interface.error') }}</span>
                        <span class="value error">{{ result.error }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建集合对话框 -->
    <el-dialog v-model="showCreateCollectionDialog" class="ef-dialog" modal-class="ef-modal" :title="$t('apiTesting.interface.createCollection')" :close-on-click-modal="false" :close-on-press-escape="false" :modal="true" :destroy-on-close="false" width="500px">
      <el-form ref="collectionFormRef" :model="collectionForm" :rules="collectionRules" label-width="100px">
        <el-form-item :label="$t('apiTesting.interface.collectionName')" prop="name">
          <el-input v-model="collectionForm.name" :placeholder="$t('apiTesting.interface.inputCollectionName')" />
        </el-form-item>
        <el-form-item :label="$t('apiTesting.common.description')" prop="description">
          <el-input v-model="collectionForm.description" type="textarea" :rows="3" :placeholder="`${$t('apiTesting.common.pleaseInput')}${$t('apiTesting.common.description')}`" />
        </el-form-item>
        <el-form-item :label="$t('apiTesting.interface.parentCollection')" prop="parent">
          <el-select v-model="collectionForm.parent" :placeholder="$t('apiTesting.interface.selectParentCollection')" clearable>
            <el-option
              v-for="collection in flatCollections"
              :key="collection.id"
              :label="collection.name"
              :value="collection.id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="closeCreateCollectionDialog">{{ $t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="createCollection">{{ $t('apiTesting.common.create') }}</el-button>
      </template>
    </el-dialog>

    <!-- 编辑集合对话框 -->
    <el-dialog v-model="showEditCollectionDialog" class="ef-dialog" modal-class="ef-modal" :title="$t('apiTesting.interface.editCollection')" :close-on-click-modal="false" width="500px">
      <el-form ref="editCollectionFormRef" :model="editCollectionForm" :rules="collectionRules" label-width="100px">
        <el-form-item :label="$t('apiTesting.interface.collectionName')" prop="name">
          <el-input v-model="editCollectionForm.name" :placeholder="$t('apiTesting.interface.inputCollectionName')" />
        </el-form-item>
        <el-form-item :label="$t('apiTesting.common.description')" prop="description">
          <el-input v-model="editCollectionForm.description" type="textarea" :rows="3" :placeholder="`${$t('apiTesting.common.pleaseInput')}${$t('apiTesting.common.description')}`" />
        </el-form-item>
        <el-form-item :label="$t('apiTesting.interface.parentCollection')" prop="parent">
          <el-select v-model="editCollectionForm.parent" :placeholder="$t('apiTesting.interface.selectParentCollection')" clearable>
            <el-option
              v-for="collection in flatCollections.filter(c => c.id !== editCollectionForm.id)"
              :key="collection.id"
              :label="collection.name"
              :value="collection.id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="closeEditCollectionDialog">{{ $t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="editCollection">{{ $t('apiTesting.common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 右键菜单 -->
    <ul v-show="showContextMenu" class="context-menu" :style="{ left: contextMenuX + 'px', top: contextMenuY + 'px' }">
      <li @click="addRequest">{{ $t('apiTesting.interface.contextMenu.addRequest') }}</li>
      <li @click="addCollection">{{ $t('apiTesting.interface.contextMenu.addSubCollection') }}</li>
      <li @click="editNode">{{ $t('apiTesting.interface.contextMenu.edit') }}</li>
      <li @click="deleteNode">{{ $t('apiTesting.interface.contextMenu.delete') }}</li>
    </ul>

    <!-- 数据工厂选择器 -->
    <DataFactorySelector
      v-model="showDataFactorySelector"
      @select="handleDataFactorySelect"
    />

    <!-- 变量助手对话框 -->
    <el-dialog
      class="ef-dialog"
      modal-class="ef-modal"
      :close-on-press-escape="false"
      :modal="true"
      :destroy-on-close="false"
      v-model="showVariableHelper"
      :title="$t('apiTesting.interface.variableHelper') + ' (点击插入)'"
      :close-on-click-modal="false"
      width="900px"
    >
      <div v-if="variableCategories.length === 0" style="padding: 20px; text-align: center; color: #999;">
        <p>{{ $t('apiTesting.interface.variableCategoriesLoading') }}</p>
        <p>{{ $t('apiTesting.interface.variableCategoriesCount', { count: variableCategories.length }) }}</p>
      </div>
      <el-tabs v-else tab-position="left" style="height: 450px">
        <el-tab-pane
          v-for="(category, index) in variableCategories"
          :key="index"
          :label="category.label"
        >
          <div style="height: 450px; overflow-y: auto; padding: 10px;">
            <el-table :data="category.variables" style="width: 100%" @row-click="insertVariable" highlight-current-row>
              <el-table-column prop="name" :label="$t('apiTesting.interface.functionName')" width="150">
                <template #default="{ row }">
                  <el-tag size="small">{{ row.name }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="desc" :label="$t('apiTesting.interface.description')" min-width="150" />
              <el-table-column prop="syntax" :label="$t('apiTesting.interface.syntax')" min-width="200" show-overflow-tooltip />
              <el-table-column prop="example" :label="$t('apiTesting.interface.example')" min-width="200" show-overflow-tooltip />
              <el-table-column :label="$t('apiTesting.interface.operation')" width="80" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" size="small">{{ $t('apiTesting.interface.insert') }}</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- CURL导入对话框 -->
    <el-dialog
      class="ef-dialog"
      modal-class="ef-modal"
      v-model="showCurlImportDialog"
      :title="$t('apiTesting.interface.importCurlCommand')"
      width="800px"
      :close-on-click-modal="false"
    >
      <el-input
        v-model="curlCommand"
        type="textarea"
        :rows="15"
        :placeholder="$t('apiTesting.interface.pasteCurlCommand')"
      />
      <template #footer>
        <el-button @click="closeCurlImportDialog">{{ $t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="parseAndImportCurl">{{ $t('apiTesting.interface.parseAndImport') }}</el-button>
      </template>
    </el-dialog>

    <!-- 代码生成对话框 -->
    <el-dialog
      class="ef-dialog"
      modal-class="ef-modal"
      v-model="showCodeGenerateDialog"
      :title="$t('apiTesting.interface.generateCode')"
      width="900px"
      :close-on-click-modal="false"
    >
      <el-select v-model="codeLanguage" :placeholder="$t('apiTesting.interface.selectLanguage')" style="width: 150px; margin-bottom: 10px" @change="generateCode(codeLanguage)">
        <el-option label="JavaScript" value="javascript" />
        <el-option label="Python" value="python" />
        <el-option label="Java" value="java" />
        <el-option label="Node.js" value="node" />
        <el-option label="cURL" value="curl" />
        <el-option label="PHP" value="php" />
        <el-option label="Go" value="go" />
        <el-option label="C#" value="csharp" />
        <el-option label="Ruby" value="ruby" />
        <el-option label="Swift" value="swift" />
        <el-option label="Kotlin" value="kotlin" />
        <el-option label="Rust" value="rust" />
        <el-option label="Dart" value="dart" />
        <el-option label="Objective-C" value="objc" />
        <el-option label="PowerShell" value="powershell" />
        <el-option label="MATLAB" value="matlab" />
        <el-option label="R" value="r" />
        <el-option label="Ansible" value="ansible" />
        <el-option label="C" value="c" />
        <el-option label="CFML" value="cfml" />
        <el-option label="Clojure" value="clojure" />
        <el-option label="Elixir" value="elixir" />
        <el-option label="HTTP" value="http" />
        <el-option label="HTTPie" value="httpie" />
        <el-option label="Julia" value="julia" />
        <el-option label="Lua" value="lua" />
        <el-option label="OCaml" value="ocaml" />
        <el-option label="Perl" value="perl" />
        <el-option label="Wget" value="wget" />
      </el-select>
      <el-input
        v-model="generatedCode"
        type="textarea"
        :rows="20"
        readonly
        class="code-generate"
      />
      <template #footer>
        <el-button @click="closeCodeGenerateDialog">{{ $t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="copyGeneratedCode">{{ $t('apiTesting.common.copy') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Folder, Document, MagicStick, Search, Close } from '@element-plus/icons-vue'
import api from '@/utils/api'
import KeyValueEditor from './components/KeyValueEditor.vue'
import DataFactorySelector from '@/components/DataFactorySelector.vue'
import { RequestModelParser } from '@/utils/requestModel'
import { getVariableFunctions } from '@/api/data-factory'
import { CodeGenerator } from '@/utils/codeGenerator'
import { debounce } from 'lodash-es'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const treeRef = ref(null)
const expandedKeys = ref([])
const projects = ref([])
const selectedProject = ref(null)
const collections = ref([])
const flatCollections = ref([])
const environments = ref([])
const selectedEnvironment = ref(null)
const selectedRequest = ref(null)
const response = ref(null)
const sending = ref(false)
const saving = ref(false)
const activeTab = ref('params')
const responseActiveTab = ref('body')
const showCreateCollectionDialog = ref(false)
const showEditCollectionDialog = ref(false)
const showContextMenu = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const rightClickedNode = ref(null)
const headersEditorRef = ref(null)
const editingNodeId = ref(null)
const editingNodeName = ref('')
const editInputRef = ref(null)
const rawBodyInputRef = ref(null)
const currentHeaders = ref({})

const searchKeyword = ref('')
const filteredCollections = ref([])

// Page-head status strip (real data)
const currentProjectName = computed(() => {
  const project = projects.value.find(item => item.id === selectedProject.value)
  return project ? project.name : '—'
})
const currentEnvName = computed(() => {
  const env = environments.value.find(item => item.id === selectedEnvironment.value)
  return env ? env.name : ''
})
const requestCount = computed(() => {
  const walk = (nodes) => {
    let count = 0
    nodes.forEach(node => {
      if (node.type === 'request') count += 1
      if (node.children && node.children.length) count += walk(node.children)
    })
    return count
  }
  return walk(collections.value)
})

const treeProps = {
  children: 'children',
  label: 'name'
}

// 数据工厂选择器相关
const showDataFactorySelector = ref(false)
const showVariableHelper = ref(false)
const currentEditingField = ref('')
const currentBodyField = ref('')
const currentAssertion = ref(null)
const currentAssertionField = ref('')
const currentAssertionIndex = ref(-1)
const currentScriptField = ref('')
const variableCategories = ref([])
const loading = ref(false)

// CURL导入相关
const showCurlImportDialog = ref(false)
const curlCommand = ref('')

// 代码生成相关
const showCodeGenerateDialog = ref(false)
const codeLanguage = ref('javascript')
const generatedCode = ref('')

// WebSocket相关
const websocketConnectionStatus = ref('disconnected') // disconnected, connecting, connected
const websocketConnection = ref(null)
const websocketMessages = ref([]) // WebSocket消息历史记录
const websocketMessageType = ref('text')
const websocketMessageContent = ref('')
const websocketBinaryFile = ref(null)

// JSONPath提取相关
const showJsonPathExtractor = ref(false)
const jsonPathExpression = ref('')
const jsonPathResult = ref(null)

// Body相关
const bodyType = ref('none')
const rawType = ref('text')
const formData = ref([])
const formUrlEncoded = ref([])
const rawBody = ref('')

const availableMethods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'CONNECT', 'TRACE']

const onSearchDebounced = debounce((value) => {
  onSearch(value)
}, 300)

const onSearch = async (value) => {
  if (!value || value.trim() === '') {
    filteredCollections.value = []
    return
  }

  try {
    const response = await api.get('/api-testing/collections/search', {
      params: {
        project: selectedProject.value,
        keyword: value
      }
    })
    // 后端可能返回分页格式 { results: [...] } 或直接返回数组
    filteredCollections.value = response.data.results || response.data || []
  } catch (error) {
    ElMessage.error('搜索失败')
    console.error('搜索失败:', error)
  }
}

const selectSearchResult = (item) => {
  selectedRequest.value = item
  searchKeyword.value = ''
  filteredCollections.value = []
}

const onProjectChange = async (projectId) => {
  if (!projectId) return

  try {
    await loadCollections(projectId)
    await loadEnvironments(projectId)
  } catch (error) {
    ElMessage.error('切换项目失败')
    console.error('切换项目失败:', error)
  }
}

const loadProjects = async () => {
  try {
    const response = await api.get('/api-testing/projects/')
    // 后端可能返回分页格式 { results: [...] } 或直接返回数组
    projects.value = response.data.results || response.data || []
    if (projects.value.length > 0) {
      selectedProject.value = projects.value[0].id
      await loadCollections(selectedProject.value)
      await loadEnvironments(selectedProject.value)
    }
  } catch (error) {
    ElMessage.error('加载项目失败')
    console.error('加载项目失败:', error)
  }
}

const loadCollections = async (projectId) => {
  try {
    const response = await api.get('/api-testing/collections/', {
      params: {
        project: projectId
      }
    })
    // 后端可能返回分页格式 { results: [...] } 或直接返回数组
    const collectionsData = response.data.results || response.data || []

    // 构建树形结构
    collections.value = buildTree(collectionsData)
    flatCollections.value = collectionsData

    // 加载请求
    await loadRequests()
  } catch (error) {
    ElMessage.error('加载集合失败')
    console.error('加载集合失败:', error)
  }
}

const loadEnvironments = async (projectId) => {
  try {
    const response = await api.get('/api-testing/environments/', {
      params: {
        project: projectId
      }
    })
    // 后端可能返回分页格式 { results: [...] } 或直接返回数组
    environments.value = response.data.results || response.data || []
  } catch (error) {
    ElMessage.error('加载环境失败')
    console.error('加载环境失败:', error)
  }
}

const buildTree = (items) => {
  const map = {}
  const roots = []

  items.forEach(item => {
    map[item.id] = {
      ...item,
      type: 'collection',
      children: []
    }
  })

  items.forEach(item => {
    if (item.parent) {
      if (map[item.parent]) {
        map[item.parent].children.push(map[item.id])
      }
    } else {
      roots.push(map[item.id])
    }
  })

  return roots
}

const findCollectionById = (collections, id) => {
  for (const collection of collections) {
    if (collection.id === id) return collection
    if (collection.children) {
      const found = findCollectionById(collection.children, id)
      if (found) return found
    }
  }
  return null
}

const clearCollectionChildren = (collection) => {
  if (collection.children) {
    collection.children = collection.children.filter(child => child.type === 'collection')
    collection.children.forEach(child => clearCollectionChildren(child))
  }
}

const loadRequests = async () => {
  if (!selectedProject.value) return

  try {
    const response = await api.get('/api-testing/requests/')
    const requests = response.data.results || response.data || []

    // 清空所有集合的子节点（请求）
    collections.value.forEach(collection => {
      clearCollectionChildren(collection)
    })

    // 过滤掉之前的未分类接口（type 为 request 且 id 为 null 的项）
    collections.value = collections.value.filter(item => item.type === 'collection')

    // 将请求添加到对应集合中或直接添加到根级别
    requests.forEach(request => {
      if (request.collection) {
        // 有关联集合的请求，添加到对应集合下
        const collection = findCollectionById(collections.value, request.collection)
        if (collection) {
          if (!collection.children) collection.children = []
          collection.children.push({
            ...request,
            type: 'request',
            name: request.name
          })
        }
      } else {
        // 未关联集合的请求，直接添加到集合列表的根级别
        collections.value.push({
          ...request,
          type: 'request',
          name: request.name
        })
      }
    })
  } catch (error) {
    ElMessage.error('加载请求失败')
    console.error('加载请求失败:', error)
  }
}

const flattenCollections = (items, parent = null) => {
  let result = []
  for (const item of items) {
    if (item.type === 'collection') {
      result.push(item)
      if (item.children && item.children.length > 0) {
        result = result.concat(flattenCollections(item.children, item))
      }
    }
  }
  return result
}

const onNodeClick = async (data) => {
  if (data.type === 'request') {
    try {
      const apiResponse = await api.get(`/api-testing/requests/${data.id}/`)
      const requestData = apiResponse.data

      // 初始化currentHeaders
      currentHeaders.value = requestData.headers || {}

      // 将 params 从字典格式转换为数组格式
      if (requestData.params && typeof requestData.params === 'object' && !Array.isArray(requestData.params)) {
        const paramsArray = []
        Object.keys(requestData.params).forEach(key => {
          if (key && requestData.params[key] !== undefined) {
            paramsArray.push({
              enabled: true,
              key,
              value: requestData.params[key],
              description: '',
              type: 'text'
            })
          }
        })
        requestData.params = paramsArray
      }

      // 将 headers 从字典格式转换为数组格式
      if (requestData.headers && typeof requestData.headers === 'object' && !Array.isArray(requestData.headers)) {
        const headersArray = []
        Object.keys(requestData.headers).forEach(key => {
          if (key && requestData.headers[key] !== undefined) {
            headersArray.push({
              enabled: true,
              key,
              value: requestData.headers[key],
              description: '',
              type: 'text'
            })
          }
        })
        requestData.headers = headersArray
      }

      // 解析body数据
      if (requestData.body && requestData.body.type) {
        if (requestData.body.type === 'json' && requestData.body.data) {
          bodyType.value = 'raw'
          rawType.value = 'json'
          rawBody.value = JSON.stringify(requestData.body.data, null, 2)
        } else if (requestData.body.type === 'raw' && requestData.body.data) {
          bodyType.value = 'raw'
          rawType.value = 'text'
          rawBody.value = requestData.body.data
        } else if (requestData.body.type === 'form-data') {
          bodyType.value = 'form-data'
          formData.value = requestData.body.data || []
        } else if (requestData.body.type === 'x-www-form-urlencoded') {
          bodyType.value = 'x-www-form-urlencoded'
          formUrlEncoded.value = requestData.body.data || []
        } else if (requestData.body.type === 'binary') {
          bodyType.value = 'binary'
        } else {
          bodyType.value = 'none'
          rawBody.value = ''
        }
      } else {
        bodyType.value = 'none'
        rawBody.value = ''
      }

      response.value = null
      selectedRequest.value = requestData
    } catch (error) {
      ElMessage.error('加载请求失败')
      console.error('加载请求失败:', error)
    }
  }
}

const onNodeRightClick = (event, node, treeNode) => {
  event.preventDefault()
  showContextMenu.value = true
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  rightClickedNode.value = node
}

const onNodeExpand = (node) => {
  expandedKeys.value.push(node.id)
}

const onNodeCollapse = (node) => {
  expandedKeys.value = expandedKeys.value.filter(key => key !== node.id)
}

const createEmptyRequest = () => {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择项目')
    return
  }

  const newRequest = {
    id: null,
    collection: null,
    name: '未命名接口',
    url: '',
    method: 'GET',
    params: {},
    headers: {},
    pre_request_script: '',
    post_request_script: '',
    assertions: [],
    request_type: 'HTTP'
  }

  selectedRequest.value = newRequest
}

const openCreateCollectionDialog = () => {
  showCreateCollectionDialog.value = true
}

const clearSearch = () => {
  searchKeyword.value = ''
  filteredCollections.value = []
}

const closeCreateCollectionDialog = () => {
  showCreateCollectionDialog.value = false
}

const closeEditCollectionDialog = () => {
  showEditCollectionDialog.value = false
}

const closeCurlImportDialog = () => {
  showCurlImportDialog.value = false
}

const closeCodeGenerateDialog = () => {
  showCodeGenerateDialog.value = false
}

const toggleJsonPathExtractor = () => {
  showJsonPathExtractor.value = !showJsonPathExtractor.value
}

const addRequest = () => {
  if (!rightClickedNode.value) return

  const parentNode = rightClickedNode.value
  if (!parentNode || parentNode.type !== 'collection') {
    ElMessage.warning('只能在集合下添加接口')
    return
  }

  const newRequest = {
    id: null,
    collection: parentNode.id,
    name: '未命名接口',
    url: '',
    method: 'GET',
    params: {},
    headers: {},
    pre_request_script: '',
    post_request_script: '',
    assertions: [],
    request_type: 'HTTP'
  }

  selectedRequest.value = newRequest
  showContextMenu.value = false
}

const addCollection = () => {
  if (!rightClickedNode.value) return

  const parentNode = rightClickedNode.value
  if (!parentNode || parentNode.type !== 'collection') {
    ElMessage.warning('只能在集合下添加子集合')
    return
  }

  collectionForm.parent = parentNode.id
  showCreateCollectionDialog.value = true
  showContextMenu.value = false
}

const editNode = () => {
  if (!rightClickedNode.value) return

  const node = rightClickedNode.value
  if (!node) {
    ElMessage.warning('无法编辑此节点')
    return
  }

  if (node.type === 'collection') {
    editingNodeId.value = node.id
    editingNodeName.value = node.name
    showContextMenu.value = false

    nextTick(() => {
      editInputRef.value?.focus()
    })
  } else {
    ElMessage.warning('只能编辑集合名称')
  }
}

const deleteNode = () => {
  if (!rightClickedNode.value) return

  const node = rightClickedNode.value
  if (!node) {
    ElMessage.warning('无法删除此节点')
    return
  }

  const nodeName = node.name

  ElMessageBox.confirm(
    `确定要删除${node.type === 'collection' ? '集合' : '接口'}「${nodeName}」吗？`,
    '确认删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      if (node.type === 'collection') {
        await api.delete(`/api-testing/collections/${node.id}/`)
      } else {
        await api.delete(`/api-testing/requests/${node.id}/`)
      }
      ElMessage.success('删除成功')
      await loadCollections(selectedProject.value)
      showContextMenu.value = false
    } catch (error) {
      ElMessage.error('删除失败')
      console.error('删除失败:', error)
    }
  }).catch(() => {
    // 取消删除
    showContextMenu.value = false
  })
}

const saveCollectionName = async () => {
  if (!editingNodeId.value || !editingNodeName.value.trim()) {
    cancelEdit()
    return
  }

  try {
    await api.put(`/api-testing/collections/${editingNodeId.value}/`, {
      name: editingNodeName.value.trim()
    })
    ElMessage.success('保存成功')
    await loadCollections(selectedProject.value)
  } catch (error) {
    ElMessage.error('保存失败')
    console.error('保存失败:', error)
  } finally {
    cancelEdit()
  }
}

const cancelEdit = () => {
  editingNodeId.value = null
  editingNodeName.value = ''
}

const collectionForm = reactive({
  name: '',
  description: '',
  parent: null
})

const editCollectionForm = reactive({
  id: null,
  name: '',
  description: '',
  parent: null
})

const collectionRules = {
  name: [{ required: true, message: '请输入集合名称', trigger: 'blur' }]
}

const methodClass = computed(() => {
  const method = selectedRequest.value?.method || 'GET'
  return `method-${method.toLowerCase()}`
})

const getMethodClass = (method) => {
  return method ? method.toLowerCase() : 'get'
}

const getMethodColor = (method) => {
  const colors = {
    'get': '#61affe',
    'post': '#49cc90',
    'put': '#fca130',
    'delete': '#f93e3e',
    'patch': '#50e3c2',
    'head': '#9013fe',
    'options': '#0ebeff',
    'connect': '#7f8c8d',
    'trace': '#e67e22'
  }
  return colors[(method || 'GET').toLowerCase()] || '#61affe'
}

const requestMethod = computed({
  get: () => selectedRequest.value?.method || 'GET',
  set: (value) => {
    if (!selectedRequest.value) {
      // 如果selectedRequest为null，创建一个新的请求对象
      const newRequest = {
        method: value,
        url: '',
        type: 'request',
        request_type: 'HTTP',
        headers: [],
        params: [],
        body: {
          type: 'none',
          content: ''
        }
      }
      selectedRequest.value = newRequest
    } else {
      selectedRequest.value.method = value
    }
  }
})

const requestUrl = computed({
  get: () => selectedRequest.value?.url || '',
  set: (value) => {
    if (selectedRequest.value) {
      selectedRequest.value.url = value
    }
  }
})

const hasBody = computed(() => {
  return selectedRequest.value && selectedRequest.value.method && ['POST', 'PUT', 'PATCH'].includes(selectedRequest.value.method)
})

const responseBody = computed(() => {
  if (!response.value || !response.value.response_data) return ''

  try {
    if (response.value.response_data.json) {
      return JSON.stringify(response.value.response_data.json, null, 2)
    } else {
      return response.value.response_data.body || ''
    }
  } catch (e) {
    return response.value.response_data?.body || ''
  }
})

const convertKeyValueArrayToObject = (input) => {
  if (input && typeof input === 'object' && !Array.isArray(input)) {
    return input
  }

  if (!Array.isArray(input)) return {}

  const obj = {}
  input.forEach(item => {
    if (item.enabled !== false && item.key) {
      obj[item.key] = item.value || ''
    }
  })
  return obj
}

const highlightedResponseBody = computed(() => {
  if (!responseBody.value) return ''

  try {
    // 简单的 JSON 语法高亮
    return responseBody.value
      .replace(/"([^"]+)"\s*:/g, '<span style="color: #268bd2;">"$1"</span>:')
      .replace(/:\s*"([^"]+)"/g, ': <span style="color: #2aa198;">"$1"</span>')
      .replace(/:\s*(true|false|null)/g, ': <span style="color: #cb4b16;">$1</span>')
      .replace(/:\s*([0-9]+(\.[0-9]+)?)/g, ': <span style="color: #d33682;">$1</span>')
  } catch (e) {
    return responseBody.value
  }
})

const getStatusType = (status) => {
  if (status >= 200 && status < 300) return 'success'
  if (status >= 300 && status < 400) return 'warning'
  if (status >= 400) return 'danger'
  return 'info'
}

const sendRequest = async () => {
  if (!selectedRequest.value || !selectedRequest.value.url) {
    ElMessage.warning('请填写请求URL')
    return
  }

  try {
    sending.value = true

    // 如果请求尚未保存（id为null），先自动保存再执行
    if (!selectedRequest.value.id) {
      await saveRequest()
      // saveRequest 会更新 selectedRequest.value，成功后继续执行
      if (!selectedRequest.value.id) {
        ElMessage.error('保存失败，无法执行请求')
        sending.value = false
        return
      }
    }

    // 准备请求体数据
    let bodyData = {}
    if (hasBody.value) {
      if (bodyType.value === 'none') {
        bodyData = {}
      } else if (bodyType.value === 'raw' && rawBody.value) {
        if (rawType.value === 'json') {
          try {
            bodyData = {
              type: 'json',
              data: JSON.parse(rawBody.value)
            }
          } catch (e) {
            ElMessage.warning('JSON解析失败，已按原始文本发送')
            bodyData = {
              type: 'raw',
              data: rawBody.value
            }
          }
        } else {
          bodyData = {
            type: 'raw',
            data: rawBody.value
          }
        }
      } else if (bodyType.value === 'form-data') {
        bodyData = {
          type: 'form-data',
          data: formData.value || []
        }
      } else if (bodyType.value === 'x-www-form-urlencoded') {
        bodyData = {
          type: 'x-www-form-urlencoded',
          data: formUrlEncoded.value || []
        }
      } else if (bodyType.value === 'binary') {
        bodyData = {
          type: 'binary',
          data: null
        }
      }
    }

    const requestData = {
      url: selectedRequest.value.url,
      method: selectedRequest.value.method,
      params: convertKeyValueArrayToObject(selectedRequest.value.params || []),
      headers: selectedRequest.value.headers,
      environment_id: selectedEnvironment.value
    }
    
    // 对于GET请求，不发送body字段
    if (hasBody.value) {
      requestData.body = bodyData
    }

    const apiResponse = await api.post(`/api-testing/requests/${selectedRequest.value.id}/execute/`, requestData)
    response.value = apiResponse.data

    ElMessage.success('请求成功')
  } catch (error) {
    ElMessage.error('请求失败')
    console.error('请求失败:', error)
  } finally {
    sending.value = false
  }
}

const onHeadersUpdate = (headers) => {
  if (selectedRequest.value) {
    currentHeaders.value = headers
    selectedRequest.value.headers = headers
  }
}

const saveRequest = async () => {
  if (!selectedRequest.value || !selectedRequest.value.url) {
    ElMessage.warning('请填写请求URL')
    return
  }

  try {
    saving.value = true

    // 准备保存的数据
    let bodyData = {}

    if (hasBody.value) {
      if (bodyType.value === 'none') {
        bodyData = {}
      } else if (bodyType.value === 'raw' && rawBody.value) {
        if (rawType.value === 'json') {
          try {
            bodyData = {
              type: 'json',
              data: JSON.parse(rawBody.value)
            }
          } catch (e) {
            ElMessage.warning('JSON解析失败，已按原始文本保存')
            bodyData = {
              type: 'raw',
              data: rawBody.value
            }
          }
        } else {
          bodyData = {
            type: 'raw',
            data: rawBody.value
          }
        }
      } else if (bodyType.value === 'form-data') {
        bodyData = {
          type: 'form-data',
          data: formData.value || []
        }
      } else if (bodyType.value === 'x-www-form-urlencoded') {
        bodyData = {
          type: 'x-www-form-urlencoded',
          data: formUrlEncoded.value || []
        }
      } else if (bodyType.value === 'binary') {
        bodyData = {
          type: 'binary',
          data: null
        }
      }
    }

    // 直接从KeyValueEditor组件获取当前headers（完整数组格式）
    let finalHeaders = []
    if (headersEditorRef.value) {
      const rows = headersEditorRef.value.rows || []
      finalHeaders = rows
        .filter(row => row.enabled && row.key && row.key.trim())
        .map(row => ({
          key: row.key.trim(),
          value: row.value || '',
          description: row.description || '',
          enabled: row.enabled !== false
        }))
    } else {
      if (selectedRequest.value.headers && Array.isArray(selectedRequest.value.headers)) {
        finalHeaders = selectedRequest.value.headers.filter(item => item.enabled && item.key)
      }
    }

    const requestData = {
      ...selectedRequest.value,
      params: Array.isArray(selectedRequest.value.params) ? convertKeyValueArrayToObject(selectedRequest.value.params || []) : selectedRequest.value.params,
      headers: finalHeaders
    }
    
    // 对于GET请求，不包含body字段
    if (hasBody.value) {
      requestData.body = bodyData
    }

    let response
    if (selectedRequest.value.id) {
      response = await api.put(`/api-testing/requests/${selectedRequest.value.id}/`, requestData)
    } else {
      response = await api.post('/api-testing/requests/', requestData)
    }

    selectedRequest.value = response.data
    await loadCollections(selectedProject.value)
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error('保存失败')
    console.error('保存失败:', error)
  } finally {
    saving.value = false
  }
}

const onBodyTypeChange = () => {
  // 保存当前body数据到selectedRequest
  if (selectedRequest.value) {
    if (bodyType.value === 'raw' && rawBody.value) {
      if (rawType.value === 'json') {
        try {
          selectedRequest.value.body = {
            type: 'json',
            data: JSON.parse(rawBody.value)
          }
        } catch (e) {
          ElMessage.warning('JSON解析失败，已按原始文本保存')
          selectedRequest.value.body = {
            type: 'raw',
            data: rawBody.value
          }
        }
      } else {
        selectedRequest.value.body = {
          type: 'raw',
          data: rawBody.value
        }
      }
    } else if (bodyType.value === 'form-data') {
      selectedRequest.value.body = {
        type: 'form-data',
        data: formData.value || []
      }
    } else if (bodyType.value === 'x-www-form-urlencoded') {
      selectedRequest.value.body = {
        type: 'x-www-form-urlencoded',
        data: formUrlEncoded.value || []
      }
    } else if (bodyType.value === 'binary') {
      selectedRequest.value.body = {
        type: 'binary',
        data: null
      }
    } else {
      selectedRequest.value.body = {
        type: 'none',
        data: null
      }
    }
  }
}

const addAssertion = () => {
  if (!selectedRequest.value) return

  if (!selectedRequest.value.assertions) {
    selectedRequest.value.assertions = []
  }

  selectedRequest.value.assertions.push({
    name: `${t('apiTesting.interface.assertion')}${selectedRequest.value.assertions.length + 1}`,
    type: 'status_code',
    expected: 200
  })
}

const removeAssertion = (index) => {
  if (!selectedRequest.value || !selectedRequest.value.assertions) return

  selectedRequest.value.assertions.splice(index, 1)
}

const onAssertionTypeChange = (assertion) => {
  // 根据断言类型重置相关字段
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

const formatResponse = () => {
  if (!response.value || !response.value.response_data) return

  try {
    // 如果已经有解析好的 JSON，无需再格式化
    if (response.value.response_data.json) {
      ElMessage.success('JSON 已格式化')
      return
    }
    // 尝试将原始文本解析为 JSON 并格式化
    const rawBody = response.value.response_data.body
    if (rawBody && typeof rawBody === 'string') {
      try {
        const parsed = JSON.parse(rawBody)
        response.value.response_data.json = parsed
        ElMessage.success('格式化成功')
      } catch {
        ElMessage.warning('响应不是有效的 JSON，无需格式化')
      }
    } else {
      ElMessage.warning('没有可格式化的内容')
    }
  } catch (e) {
    ElMessage.error('格式化失败')
  }
}

const copyResponse = () => {
  if (responseBody.value) {
    navigator.clipboard.writeText(responseBody.value)
    ElMessage.success('已复制到剪贴板')
  }
}

const evaluateJsonPath = () => {
  if (!response.value || !response.value.response_data || !response.value.response_data.json || !jsonPathExpression.value) {
    jsonPathResult.value = null
    return
  }

  try {
    // 简单的JSONPath实现
    const json = response.value.response_data.json
    let result = json

    // 解析JSONPath表达式
    const parts = jsonPathExpression.value.split('.').filter(p => p)

    for (const part of parts) {
      if (part === '$') {
        result = json
      } else if (part.includes('[')) {
        // 处理数组索引
        const [arrayName, indexStr] = part.split('[')
        const index = parseInt(indexStr.replace(']', ''))
        result = result[arrayName][index]
      } else {
        result = result[part]
      }
    }

    jsonPathResult.value = JSON.stringify(result, null, 2)
  } catch (e) {
    jsonPathResult.value = 'JSONPath表达式错误'
  }
}

const copyJsonPathResult = () => {
  if (jsonPathResult.value) {
    navigator.clipboard.writeText(jsonPathResult.value)
    ElMessage.success('已复制到剪贴板')
  }
}

const formatAssertionValue = (value) => {
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value, null, 2)
  }
  return value
}

const createCollection = async () => {
  if (!collectionForm.name.trim()) {
    ElMessage.warning('请输入集合名称')
    return
  }

  try {
    const response = await api.post('/api-testing/collections/', {
      ...collectionForm,
      project: selectedProject.value
    })
    ElMessage.success('创建成功')
    await loadCollections(selectedProject.value)
    showCreateCollectionDialog.value = false
    collectionForm.name = ''
    collectionForm.description = ''
    collectionForm.parent = null
  } catch (error) {
    ElMessage.error('创建失败')
    console.error('创建失败:', error)
  }
}

const updateCollection = async () => {
  if (!editCollectionForm.name.trim()) {
    ElMessage.warning('请输入集合名称')
    return
  }

  try {
    await api.put(`/api-testing/collections/${editCollectionForm.id}/`, editCollectionForm)
    ElMessage.success('更新成功')
    await loadCollections(selectedProject.value)
    showEditCollectionDialog.value = false
  } catch (error) {
    ElMessage.error('更新失败')
    console.error('更新失败:', error)
  }
}

const importCurl = () => {
  // 清空上次的 curl 命令
  curlCommand.value = ''
  showCurlImportDialog.value = true
}

const parseAndImportCurl = async () => {
  if (!curlCommand.value.trim()) {
    ElMessage.warning('请输入CURL命令')
    return
  }

  try {
    const requestModel = await RequestModelParser.parseCurl(curlCommand.value)

    if (!selectedRequest.value) {
      createEmptyRequest()
    }

    // 回填基本字段
    selectedRequest.value.method = requestModel.method
    selectedRequest.value.url = requestModel.baseURL + requestModel.path
    selectedRequest.value.headers = requestModel.headers
    selectedRequest.value.params = requestModel.query

    // 回填 body 相关字段
    if (requestModel.body.mode !== 'none') {
      if (requestModel.body.mode === 'json') {
        bodyType.value = 'raw'
        rawType.value = 'json'
        rawBody.value = requestModel.body.json || ''
      } else if (requestModel.body.mode === 'raw') {
        bodyType.value = 'raw'
        rawType.value = 'text'
        rawBody.value = requestModel.body.raw || ''
      } else if (requestModel.body.mode === 'formdata') {
        bodyType.value = 'form-data'
        formData.value = requestModel.body.formdata || []
      } else if (requestModel.body.mode === 'urlencoded') {
        bodyType.value = 'x-www-form-urlencoded'
        formUrlEncoded.value = requestModel.body.urlencoded || []
      }
    }

    showCurlImportDialog.value = false
    ElMessage.success('导入成功')
  } catch (error) {
    ElMessage.error('解析CURL命令失败')
    console.error('解析CURL命令失败:', error)
  }
}

// 辅助函数：将对象格式转换为数组格式
const convertToArrayFormat = (data) => {
  if (!data) return []
  // 如果已经是数组格式，直接返回
  if (Array.isArray(data)) return data
  // 如果是对象格式，转换为数组格式
  if (typeof data === 'object') {
    return Object.entries(data).map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value) : String(value),
      enabled: true
    }))
  }
  return []
}

const exportRequest = () => {
  if (!selectedRequest.value) return

  try {
    let baseURL = ''
    let path = ''

    if (selectedRequest.value.url) {
      try {
        const url = new URL(selectedRequest.value.url)
        baseURL = `${url.protocol}//${url.host}`
        path = url.pathname
      } catch (error) {
        baseURL = selectedRequest.value.url
        path = ''
      }
    }

    const requestModel = {
      method: selectedRequest.value?.method || 'GET',
      baseURL: baseURL,
      path: path,
      query: convertToArrayFormat(selectedRequest.value?.params),
      headers: convertToArrayFormat(selectedRequest.value?.headers),
      body: {
        mode: 'none',
        raw: rawBody.value || ''
      },
      timeout: 30000
    }

    const curlCommand = RequestModelParser.toCurl(requestModel)
    navigator.clipboard.writeText(curlCommand)
    ElMessage.success('已复制到剪贴板')
  } catch (error) {
    ElMessage.error('导出失败')
    console.error('导出失败:', error)
  }
}

const generateCode = async (language) => {
  if (!selectedRequest.value) return

  if (!selectedRequest.value.url) {
    ElMessage.warning('请求URL不能为空')
    return
  }

  try {
    // 更新语言选择器的值
    codeLanguage.value = language

    // 构建完整的 requestModel 对象
    let bodyMode = 'none'

    if (bodyType.value === 'raw') {
      bodyMode = rawType.value === 'json' ? 'json' : 'raw'
    } else if (bodyType.value === 'form-data') {
      bodyMode = 'formdata'
    } else if (bodyType.value === 'x-www-form-urlencoded') {
      bodyMode = 'urlencoded'
    } else if (bodyType.value === 'binary') {
      bodyMode = 'binary'
    }

    // 解析 URL 获取 baseURL 和 path
    let baseURL = ''
    let path = ''
    try {
      const url = new URL(selectedRequest.value.url)
      baseURL = `${url.protocol}//${url.host}`
      path = url.pathname
    } catch (error) {
      // 如果 URL 解析失败，使用整个 URL 作为 path
      path = selectedRequest.value.url
    }

    // 构建完整的 requestModel 对象
    const requestModel = {
      method: selectedRequest.value.method || 'GET',
      baseURL: baseURL,
      path: path,
      query: Array.isArray(selectedRequest.value.params) ? selectedRequest.value.params : [],
      headers: Array.isArray(selectedRequest.value.headers) ? selectedRequest.value.headers : [],
      body: {
        mode: bodyMode,
        raw: rawBody.value,
        json: rawBody.value,
        formdata: formData.value,
        urlencoded: formUrlEncoded.value
      },
      timeout: 30000
    }

    const code = await CodeGenerator.generateCode(requestModel, language)
    generatedCode.value = code
    showCodeGenerateDialog.value = true
  } catch (error) {
    ElMessage.error('生成代码失败')
    console.error('生成代码失败:', error)
  }
}

const copyGeneratedCode = () => {
  if (generatedCode.value) {
    navigator.clipboard.writeText(generatedCode.value)
    ElMessage.success('已复制到剪贴板')
  }
}

const toggleWebSocketConnection = async () => {
  if (!selectedRequest.value || !selectedRequest.value.url) {
    ElMessage.warning('请填写WebSocket URL')
    return
  }

  if (websocketConnectionStatus.value === 'connected') {
    // 关闭连接
    if (websocketConnection.value) {
      websocketConnection.value.close()
      websocketConnection.value = null
    }
    websocketConnectionStatus.value = 'disconnected'
    ElMessage.success('WebSocket连接已关闭')
  } else {
    // 建立连接
    try {
      websocketConnectionStatus.value = 'connecting'
      const wsUrl = selectedRequest.value.url.replace('http://', 'ws://').replace('https://', 'wss://')

      websocketConnection.value = new WebSocket(wsUrl)

      websocketConnection.value.onopen = () => {
        websocketConnectionStatus.value = 'connected'
        ElMessage.success('WebSocket连接成功')
        websocketMessages.value.push({
          type: 'connected',
          content: 'WebSocket连接成功',
          timestamp: new Date().toLocaleString()
        })
      }

      websocketConnection.value.onmessage = (event) => {
        websocketMessages.value.push({
          type: 'received',
          content: event.data,
          timestamp: new Date().toLocaleString()
        })
      }

      websocketConnection.value.onclose = () => {
        websocketConnectionStatus.value = 'disconnected'
        websocketConnection.value = null
        websocketMessages.value.push({
          type: 'info',
          content: 'WebSocket连接已关闭',
          timestamp: new Date().toLocaleString()
        })
      }

      websocketConnection.value.onerror = (error) => {
        websocketConnectionStatus.value = 'disconnected'
        websocketConnection.value = null
        ElMessage.error('WebSocket连接失败')
        websocketMessages.value.push({
          type: 'error',
          content: `WebSocket连接失败: ${error.message}`,
          timestamp: new Date().toLocaleString()
        })
      }
    } catch (error) {
      websocketConnectionStatus.value = 'disconnected'
      ElMessage.error('WebSocket连接失败')
      console.error('WebSocket连接失败:', error)
    }
  }
}

const sendWebSocketMessage = () => {
  if (!websocketConnection.value || websocketConnectionStatus.value !== 'connected') {
    ElMessage.warning('请先建立WebSocket连接')
    return
  }

  if (websocketMessageType.value === 'binary' && !websocketBinaryFile.value) {
    ElMessage.warning('请选择要发送的二进制文件')
    return
  }

  try {
    let message = websocketMessageContent.value
    if (websocketMessageType.value === 'json') {

      message = JSON.parse(message)
    }

    websocketConnection.value.send(message)
    websocketMessages.value.push({
      type: 'sent',
      content: websocketMessageContent.value,
      timestamp: new Date().toLocaleString()
    })

    if (websocketMessageType.value !== 'binary') {
      websocketMessageContent.value = ''
    }
  } catch (error) {
    ElMessage.error('发送消息失败')
    console.error('发送消息失败:', error)
  }
}

const clearWebSocketMessage = () => {
  websocketMessageContent.value = ''
  websocketBinaryFile.value = null
}

const clearWebSocketMessages = () => {
  websocketMessages.value = []
}

const handleWebSocketFileUpload = (file) => {
  websocketBinaryFile.value = file.raw
}

const clearWebSocketBinaryFile = () => {
  websocketBinaryFile.value = null
}

const isJsonString = (str) => {
  try {
    JSON.parse(str)
    return true
  } catch (e) {
    return false
  }
}

const formatJson = (str) => {
  try {
    const obj = JSON.parse(str)
    return JSON.stringify(obj, null, 2)
  } catch (e) {
    return str
  }
}

const openDataFactorySelectorForBody = (field) => {
  currentBodyField.value = field
  currentAssertion.value = null
  currentAssertionField.value = ''
  currentAssertionIndex.value = -1
  currentScriptField.value = ''
  showDataFactorySelector.value = true
}

const openDataFactorySelectorForScript = (field) => {
  currentScriptField.value = field
  currentAssertion.value = null
  currentAssertionField.value = ''
  currentAssertionIndex.value = -1
  showDataFactorySelector.value = true
}

const openDataFactorySelector = (assertion, field, index) => {
  currentAssertion.value = assertion
  currentAssertionField.value = field
  currentAssertionIndex.value = index
  currentScriptField.value = ''
  showDataFactorySelector.value = true
}

const openVariableHelper = (field) => {
  currentEditingField.value = field
  currentAssertion.value = null
  currentAssertionField.value = ''
  currentAssertionIndex.value = -1
  showVariableHelper.value = true
}

const openVariableHelperForAssertion = (assertion, field, index) => {
  currentAssertion.value = assertion
  currentAssertionField.value = field
  currentAssertionIndex.value = index
  currentEditingField.value = ''
  showVariableHelper.value = true
}

const insertVariable = (variable) => {
  // 确保variable是对象（处理行点击事件）
  if (typeof variable === 'object' && variable !== null) {
    if (currentEditingField.value && selectedRequest.value) {
      const example = variable.example

      if (currentEditingField.value === 'rawBody') {
        // 在光标位置插入变量
        insertTextAtCursor(rawBodyInputRef, example)
      } else if (currentEditingField.value === 'pre_request_script') {
        // 对于脚本字段，暂时保持追加到末尾的行为
        // （如果需要光标插入，需要为脚本编辑器添加ref并实现类似逻辑）
        const currentValue = selectedRequest.value.pre_request_script || ''
        selectedRequest.value.pre_request_script = currentValue + example
      } else if (currentEditingField.value === 'post_request_script') {
        const currentValue = selectedRequest.value.post_request_script || ''
        selectedRequest.value.post_request_script = currentValue + example
      }

      ElMessage.success(`已插入变量: ${variable.name}`)
      showVariableHelper.value = false
    } else if (currentAssertion.value && currentAssertionField.value) {
      const example = variable.example
      const field = currentAssertionField.value

      const currentValue = currentAssertion.value[field] || ''
      if (!currentValue) {
        currentAssertion.value[field] = example
      } else {
        currentAssertion.value[field] = currentValue + example
      }

      ElMessage.success(`已插入变量: ${variable.name}`)
      showVariableHelper.value = false
    }
  }
}

const handleDataFactorySelect = (record) => {
  if (!record || !record.output_data) return

  let valueToSet = ''

  if (typeof record.output_data === 'string') {
    valueToSet = record.output_data
  } else if (record.output_data.result) {
    valueToSet = record.output_data.result
  } else if (record.output_data.output_data) {
    valueToSet = record.output_data.output_data
  } else if (typeof record.output_data === 'object') {

    const possibleResultFields = ['result', 'value', 'data', 'output', 'content']
    let foundResult = false
    for (const field of possibleResultFields) {
      if (record.output_data[field] !== undefined) {
        valueToSet = record.output_data[field]
        foundResult = true
        break
      }
    }
    // 如果没有找到可能的结果字段，将整个对象转为JSON字符串
    if (!foundResult) {
      valueToSet = JSON.stringify(record.output_data)
    }
  } else {
    valueToSet = JSON.stringify(record.output_data)
  }

  // 确保valueToSet是字符串类型
  if (typeof valueToSet !== 'string') {
    valueToSet = JSON.stringify(valueToSet)
  }

  // 如果是断言字段
  if (currentAssertion.value) {
    currentAssertion.value[currentAssertionField.value] = valueToSet
    ElMessage.success(`${t('apiTesting.interface.referencedToAssertion')}: ${record.tool_name}`)
  }
  // 如果是Body字段
  else if (currentBodyField.value) {
    if (currentBodyField.value === 'rawBody') {
      // 在光标位置插入文本
      insertTextAtCursor(rawBodyInputRef, valueToSet)
    }
    ElMessage.success(`已引用数据工厂数据到Body: ${record.tool_name}`)
  }
  // 如果是脚本字段
  else if (currentScriptField.value && selectedRequest.value) {
    // 将值插入到脚本中
    const insertText = `\n// 来自数据工厂: ${record.tool_name}\nconst ${record.tool_name.replace(/\s+/g, '_')} = ${JSON.stringify(valueToSet)}\n`
    const currentValue = selectedRequest.value[currentScriptField.value] || ''
    selectedRequest.value[currentScriptField.value] = currentValue + insertText
    ElMessage.success(`已引用数据工厂数据到脚本: ${record.tool_name}`)
  }

  showDataFactorySelector.value = false
}

// 在光标位置插入文本的辅助函数
const insertTextAtCursor = (inputRef, textToInsert) => {
  if (!inputRef.value) {
    // 如果没有找到ref，直接追加到末尾
    rawBody.value = rawBody.value + textToInsert
    return
  }

  // 获取textarea DOM元素
  const textarea = inputRef.value.$el?.querySelector('textarea')
  if (!textarea) {
    // 如果找不到textarea元素，直接追加到末尾
    rawBody.value = rawBody.value + textToInsert
    return
  }

  const startPos = textarea.selectionStart
  const endPos = textarea.selectionEnd
  const currentValue = rawBody.value

  // 在光标位置插入新文本
  const newValue =
    currentValue.substring(0, startPos) +
    textToInsert +
    currentValue.substring(endPos)

  rawBody.value = newValue

  // 恢复光标位置到插入文本的末尾
  nextTick(() => {
    const newCursorPos = startPos + textToInsert.length
    textarea.setSelectionRange(newCursorPos, newCursorPos)
    textarea.focus()
  })
}

// 加载变量函数
const loadVariableFunctions = async () => {
  try {
    loading.value = true
    console.log('开始加载变量函数...')
    const apiResponse = await getVariableFunctions()
    console.log('变量函数响应:', apiResponse)
    console.log('变量函数响应.data:', apiResponse.data)
    
    // 更灵活地处理响应数据结构
    let functionsData = null
    
    // 检查不同可能的数据结构
    if (apiResponse && apiResponse.data) {
      if (Array.isArray(apiResponse.data)) {
        // 后端返回的是数组，直接使用
        functionsData = apiResponse.data
      } else if (apiResponse.data.functions) {
        // 如果data中有functions字段，使用它
        functionsData = apiResponse.data.functions
      } else if (typeof apiResponse.data === 'object') {
        // 如果data是对象但没有functions字段，假设整个对象就是按分类组织的函数
        functionsData = apiResponse.data
      }
    }
    
    if (functionsData) {
      const groupedFunctions = functionsData
      console.log('处理后的 groupedFunctions:', groupedFunctions)

      // 后端已经按分类分组了，直接转换为标签页所需的格式
      if (typeof groupedFunctions === 'object' && !Array.isArray(groupedFunctions)) {
        variableCategories.value = Object.entries(groupedFunctions).map(([label, variables]) => ({
          label,
          variables
        }))
      } else if (Array.isArray(groupedFunctions)) {
        // 如果是数组，按分类分组
        const grouped = {}
        
        // 创建分类名称映射表
        const categoryMapping = {
          '随机数': t('apiTesting.component.keyValueEditor.categories.randomNumber'),
          '测试数据': t('apiTesting.component.keyValueEditor.categories.testData'),
          '字符串': t('apiTesting.component.keyValueEditor.categories.string'),
          '编码转换': t('apiTesting.component.keyValueEditor.categories.encodingConversion'),
          '加密': t('apiTesting.component.keyValueEditor.categories.encryption'),
          '时间日期': t('apiTesting.component.keyValueEditor.categories.datetime'),
          'Crontab': t('apiTesting.component.keyValueEditor.categories.crontab'),
          '未分类': t('apiTesting.component.keyValueEditor.categories.uncategorized')
        }
        
        groupedFunctions.forEach(func => {
          const rawCategory = func.category || '未分类'
          // 使用映射表获取正确的分类名称
          const category = categoryMapping[rawCategory] || rawCategory
          if (!grouped[category]) {
            grouped[category] = []
          }
          grouped[category].push(func)
        })
        
        // 定义固定的分类顺序 ['随机数', '测试数据', '字符串', '编码转换', '加密', '时间日期', 'Crontab', '未分类']
        const categoryOrder = [
          t('apiTesting.component.keyValueEditor.categories.randomNumber'),
          t('apiTesting.component.keyValueEditor.categories.testData'),
          t('apiTesting.component.keyValueEditor.categories.string'),
          t('apiTesting.component.keyValueEditor.categories.encodingConversion'),
          t('apiTesting.component.keyValueEditor.categories.encryption'),
          t('apiTesting.component.keyValueEditor.categories.datetime'),
          t('apiTesting.component.keyValueEditor.categories.crontab'),
          t('apiTesting.component.keyValueEditor.categories.uncategorized')
        ]
        
        // 按固定顺序构建分类列表
        const orderedCategories = []
        categoryOrder.forEach(category => {
          if (grouped[category]) {
            orderedCategories.push({
              label: category,
              variables: grouped[category]
            })
            delete grouped[category]
          }
        })
        
        // 添加剩余的分类（如果有）
        Object.entries(grouped).forEach(([label, variables]) => {
          orderedCategories.push({
            label,
            variables
          })
        })
        
        variableCategories.value = orderedCategories
      }

      console.log('最终变量分类:', variableCategories.value)
    } else {
      console.error('响应数据格式错误，无法找到函数数据')
      console.error('完整响应:', apiResponse)
    }
  } catch (error) {
    console.error('加载变量函数失败:', error)
    ElMessage.error('加载变量函数失败，使用本地数据')
    // 加载失败时使用本地变量分类数据
    useLocalVariableCategories()
  } finally {
    loading.value = false
  }
}

// 生命周期钩子
onMounted(async () => {
  await loadProjects()
  await loadVariableFunctions()

  // 添加全局点击事件监听器，用于隐藏右键菜单
  document.addEventListener('click', handleGlobalClick)
  document.addEventListener('contextmenu', handleGlobalClick)
})

onBeforeUnmount(() => {
  // 移除全局点击事件监听器
  document.removeEventListener('click', handleGlobalClick)
  document.removeEventListener('contextmenu', handleGlobalClick)
})

// 处理全局点击事件，隐藏右键菜单
const handleGlobalClick = (event) => {
  // 当显示右键菜单时，点击任何地方（除了菜单本身）都应该隐藏菜单
  if (showContextMenu.value) {
    const contextMenu = document.querySelector('.context-menu')
    if (!contextMenu || !contextMenu.contains(event.target)) {
      showContextMenu.value = false
    }
  }
}

// 使用本地变量分类数据
const useLocalVariableCategories = () => {
  variableCategories.value = [
    {
      label: t('apiTesting.component.keyValueEditor.categories.randomNumber'),
      variables: [
        { name: 'random_int', syntax: '${random_int(min, max, count)}', desc: t('apiTesting.component.keyValueEditor.variables.randomInt'), example: '${random_int(100, 999, 1)}' },
        { name: 'random_float', syntax: '${random_float(min, max, precision, count)}', desc: t('apiTesting.component.keyValueEditor.variables.randomFloat'), example: '${random_float(0, 1, 2, 1)}' },
        { name: 'random_boolean', syntax: '${random_boolean(count)}', desc: t('apiTesting.component.keyValueEditor.variables.randomBoolean'), example: '${random_boolean(1)}' },
        { name: 'random_date', syntax: '${random_date(start_date, end_date, count, date_format)}', desc: t('apiTesting.component.keyValueEditor.variables.randomDate'), example: '${random_date(2024-01-01, 2024-12-31, 1, %Y-%m-%d)}' }
      ]
    },
    {
      label: t('apiTesting.component.keyValueEditor.categories.randomString'),
      variables: [
        { name: 'random_string', syntax: '${random_string(length, char_type, count)}', desc: t('apiTesting.component.keyValueEditor.variables.randomString'), example: '${random_string(8, all, 1)}' },
        { name: 'random_uuid', syntax: '${random_uuid(version, count)}', desc: t('apiTesting.component.keyValueEditor.variables.randomUuid'), example: '${random_uuid(4, 1)}' },
        { name: 'random_mac_address', syntax: '${random_mac_address(separator, count)}', desc: t('apiTesting.component.keyValueEditor.variables.randomMacAddress'), example: '${random_mac_address(:, 1)}' },
        { name: 'random_ip_address', syntax: '${random_ip_address(ip_version, count)}', desc: t('apiTesting.component.keyValueEditor.variables.randomIpAddress'), example: '${random_ip_address(4, 1)}' },
        { name: 'random_sequence', syntax: '${random_sequence(sequence, count, unique)}', desc: t('apiTesting.component.keyValueEditor.variables.randomSequence'), example: '${random_sequence([a,b,c], 1, false)}' }
      ]
    }
  ]
  console.log('使用本地变量分类数据:', variableCategories.value)
}
</script>

<style scoped>
/* ============================================================
   Endfield / moderate - Interface Management
   Field engineering system: pale rail + charcoal dock +
   signal-yellow wedges over a paper field.
   Clean-room CSS from Ark UI skill guidance (no copied assets).
   ============================================================ */

.interface-management {
  height: 100%;
  min-height: 0;
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

/* ---------- Page head ---------- */
.ef-page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 24px 14px;
  background: #f2f2f0;
  border-bottom: 1px solid var(--ef-line);
  flex-shrink: 0;
}
.ef-page-head__title { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.ef-kicker {
  margin: 0;
  font-family: var(--ef-font-tech);
  font-size: 10px;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--ef-muted);
}
.ef-page-title {
  margin: 0;
  font-family: var(--ef-font-display);
  font-size: 30px;
  line-height: .95;
  letter-spacing: -.02em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--ef-ink);
}
.ef-rule {
  display: block;
  width: 120px;
  height: 4px;
  background: var(--ef-signal);
  clip-path: polygon(0 0, 100% 0, 96% 100%, 0 100%);
}
.ef-page-head__status {
  display: flex;
  border: 1px solid var(--ef-line-strong);
  background: var(--ef-rail);
  flex-shrink: 0;
}
.ef-status-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 14px;
  min-width: 96px;
  border-right: 1px solid var(--ef-line);
}
.ef-status-item:last-child { border-right: none; }
.ef-status-label {
  font-family: var(--ef-font-tech);
  font-size: 9px;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--ef-muted);
}
.ef-status-value {
  font-family: var(--ef-font-tech);
  font-size: 13px;
  font-weight: 600;
  color: var(--ef-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ---------- Charcoal utility dock ---------- */
.ef-dock {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 24px;
  background: var(--ef-dock);
  position: relative;
  z-index: 6;
  flex-shrink: 0;
}
.ef-dock__project { width: 220px; flex-shrink: 0; }
.ef-dock__search { flex: 1; min-width: 160px; }
.ef-dock__actions { display: flex; gap: 8px; margin-left: auto; flex-shrink: 0; }
.ef-dock-btn {
  height: 30px;
  border-radius: 2px;
  border: 1px solid rgba(255,255,255,.28);
  background: transparent;
  color: rgba(255,255,255,.85);
  font-size: 12px;
}
.ef-dock-btn:hover {
  border-color: var(--ef-signal);
  color: var(--ef-signal);
  background: rgba(255,250,0,.06);
}

/* Dock controls - dark variants (in-page DOM) */
.ef-dock :deep(.el-select__wrapper),
.ef-dock :deep(.el-input__wrapper) {
  background: rgba(255,255,255,.06);
  border: 1px solid rgba(255,255,255,.18);
  border-radius: 2px;
  box-shadow: none;
  min-height: 30px;
}
.ef-dock :deep(.el-select__wrapper.is-focused),
.ef-dock :deep(.el-input__wrapper.is-focus) {
  border-color: var(--ef-signal);
  background: rgba(255,255,255,.1);
}
.ef-dock :deep(.el-input__inner),
.ef-dock :deep(.el-select__selected-item),
.ef-dock :deep(.el-select__placeholder) {
  color: rgba(255,255,255,.9);
  font-size: 12px;
}
.ef-dock :deep(.el-input__inner::placeholder) { color: rgba(255,255,255,.35); }
.ef-dock :deep(.el-input__prefix),
.ef-dock :deep(.el-select__caret) { color: rgba(255,255,255,.5); }

/* ---------- Layout: pale rail + field ---------- */
.interface-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.sidebar {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--ef-rail);
  border-right: 1px solid var(--ef-line-strong);
  position: relative;
  overflow: hidden;
}
.collection-tree {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 8px;
}

/* ---------- Collection tree ---------- */
.collection-tree :deep(.el-tree) {
  background: transparent;
  color: var(--ef-ink);
  font-size: 13px;
}
.collection-tree :deep(.el-tree-node__content) {
  height: 32px;
  border-left: 2px solid transparent;
}
.collection-tree :deep(.el-tree-node__content:hover) {
  background: rgba(25,25,25,.05);
}
.collection-tree :deep(.el-tree-node__expand-icon) { color: var(--ef-muted); }
.collection-tree :deep(.el-tree-node__expand-icon.is-leaf) { color: transparent; }
.tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  padding: 4px 2px;
}
.tree-node .el-icon { font-size: 15px; color: var(--ef-muted); }
.tree-node--active .el-icon { color: var(--ef-ink); }
.node-label {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--ef-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tree-node--active .node-label { font-weight: 700; }
.node-edit { flex: 1; }

/* Method chips */
.method-tag {
  font-family: var(--ef-font-tech);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  padding: 1px 6px;
  border-radius: 2px;
  color: #fff;
  min-width: 42px;
  text-align: center;
  flex-shrink: 0;
}
.method-tag.get { background: #3b82f6; }
.method-tag.post { background: #16a34a; }
.method-tag.put { background: #d97706; }
.method-tag.delete { background: #dc2626; }
.method-tag.patch { background: #0d9488; }
.method-tag.head { background: #7c3aed; }
.method-tag.options { background: #0891b2; }
.method-tag.connect { background: #57534e; }
.method-tag.trace { background: #c2410c; }

/* ---------- Search results ---------- */
.search-results {
  position: absolute;
  top: 8px;
  left: 8px;
  right: 8px;
  z-index: 20;
  display: flex;
  flex-direction: column;
  background: var(--ef-surface);
  border: 1px solid var(--ef-line-strong);
  box-shadow: 0 8px 24px rgba(25,25,25,.12);
  max-height: calc(100% - 16px);
}
.search-results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--ef-line);
  background: var(--ef-rail);
  font-family: var(--ef-font-tech);
  font-size: 10px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--ef-muted);
}
.search-results-list { overflow-y: auto; }
.search-result-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--ef-line-soft);
  transition: background .15s ease;
}
.search-result-item:last-child { border-bottom: none; }
.search-result-item:hover { background: rgba(255,250,0,.14); }
.search-result-content { flex: 1; min-width: 0; }
.search-result-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ef-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.search-result-url {
  font-size: 11px;
  font-family: var(--ef-font-tech);
  color: var(--ef-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

/* ---------- Main field with engineering grid ---------- */
.main-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  background-image:
    linear-gradient(rgba(25,25,25,.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(25,25,25,.035) 1px, transparent 1px);
  background-size: 64px 64px;
}
.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.empty-state :deep(.el-empty__description p) {
  color: var(--ef-muted);
  font-size: 13px;
}
.empty-state :deep(.el-empty__image) { opacity: .55; }

/* ---------- Request detail ---------- */
.request-detail {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--ef-surface);
}

/* Request header: charcoal dock with yellow baseline */
.request-header {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px 10px;
  background: var(--ef-dock);
  color: #ffffff;
  border-bottom: 3px solid var(--ef-signal);
}
.request-line { display: flex; gap: 8px; align-items: center; }

.method-select { width: 108px; flex-shrink: 0; }
.method-select :deep(.el-select__wrapper) {
  background: rgba(255,255,255,.06);
  border: 1px solid rgba(255,255,255,.22);
  border-left: 3px solid var(--ef-muted);
  border-radius: 2px;
  box-shadow: none;
  min-height: 32px;
}
.method-select :deep(.el-select__selected-item),
.method-select :deep(.el-select__placeholder) {
  color: #ffffff;
  font-family: var(--ef-font-tech);
  font-weight: 700;
  letter-spacing: .08em;
}
.method-select :deep(.el-select__caret) { color: rgba(255,255,255,.55); }
.method-select.get :deep(.el-select__wrapper) { border-left-color: #3b82f6; }
.method-select.post :deep(.el-select__wrapper) { border-left-color: #16a34a; }
.method-select.put :deep(.el-select__wrapper) { border-left-color: #d97706; }
.method-select.delete :deep(.el-select__wrapper) { border-left-color: #dc2626; }
.method-select.patch :deep(.el-select__wrapper) { border-left-color: #0d9488; }
.method-select.head :deep(.el-select__wrapper) { border-left-color: #7c3aed; }
.method-select.options :deep(.el-select__wrapper) { border-left-color: #0891b2; }
.method-select.connect :deep(.el-select__wrapper) { border-left-color: #57534e; }
.method-select.trace :deep(.el-select__wrapper) { border-left-color: #c2410c; }

.url-input { flex: 1; min-width: 0; }
.url-input :deep(.el-input__wrapper),
.env-select :deep(.el-input__wrapper),
.url-input :deep(.el-input-group__prepend) {
  background: rgba(255,255,255,.06);
  border: 1px solid rgba(255,255,255,.22);
  border-radius: 2px;
  box-shadow: none;
  min-height: 32px;
}
.url-input :deep(.el-input__inner) {
  color: #ffffff;
  font-family: var(--ef-font-tech);
  font-size: 13px;
}
.url-input :deep(.el-input__inner::placeholder) { color: rgba(255,255,255,.4); }
.env-select { width: 150px; flex-shrink: 0; }
.env-select :deep(.el-input__inner),
.env-select :deep(.el-select__selected-item),
.env-select :deep(.el-select__placeholder) { color: rgba(255,255,255,.85); font-size: 12px; }

.request-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}
.name-input { flex: 1; min-width: 0; }
.name-input :deep(.el-input__wrapper) {
  background: transparent;
  border: none;
  border-bottom: 1px solid rgba(255,255,255,.28);
  border-radius: 0;
  box-shadow: none;
}
.name-input :deep(.el-input__inner) {
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
}
.name-input :deep(.el-input__inner::placeholder) { color: rgba(255,255,255,.4); }
.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.action-buttons :deep(.el-button) {
  border-radius: 2px;
  border-color: rgba(255,255,255,.3);
  background: transparent;
  color: rgba(255,255,255,.85);
}
.action-buttons :deep(.el-button:hover) {
  border-color: var(--ef-signal);
  color: var(--ef-signal);
}

/* ---------- Element Plus retheme inside the page ---------- */
:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  background: var(--ef-surface);
  box-shadow: 0 0 0 1px var(--ef-line-strong) inset;
  border-radius: 2px;
}
:deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px var(--ef-ink) inset; }
:deep(.el-input__inner) { color: var(--ef-ink); font-size: 13px; }
:deep(.el-select__wrapper) {
  background: var(--ef-surface);
  box-shadow: 0 0 0 1px var(--ef-line-strong) inset;
  border-radius: 2px;
  min-height: 30px;
}
:deep(.el-select__wrapper.is-focused) { box-shadow: 0 0 0 1px var(--ef-ink) inset; }
:deep(.el-textarea__inner:focus) { box-shadow: 0 0 0 1px var(--ef-ink) inset; }
:deep(.el-button) { border-radius: 2px; }
:deep(.el-button--primary) {
  background: var(--ef-ink);
  border-color: var(--ef-ink);
  color: #ffffff;
}
:deep(.el-button--primary:hover) {
  background: #3a3a3a;
  border-color: #3a3a3a;
  color: var(--ef-signal);
}
:deep(.el-button--primary.is-plain) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
:deep(.el-button--primary.is-plain:hover) {
  background: rgba(255,250,0,.12);
  border-color: var(--ef-signal);
  color: var(--ef-ink);
}
:deep(.el-button--danger) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
:deep(.el-button--danger:hover) {
  background: rgba(220,38,38,.08);
  border-color: #b91c1c;
  color: #b91c1c;
}
:deep(.el-button--success) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
:deep(.el-button--success:hover) {
  background: rgba(22,163,74,.1);
  border-color: #15803d;
  color: #15803d;
}
:deep(.el-button--warning) {
  background: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
:deep(.el-button--warning:hover) {
  background: rgba(217,119,6,.1);
  border-color: #b45309;
  color: #b45309;
}
:deep(.el-button--info) {
  background: transparent;
  border-color: var(--ef-line-strong);
  color: var(--ef-muted);
}
:deep(.el-button--info:hover) {
  border-color: var(--ef-signal);
  color: var(--ef-ink);
}
:deep(.el-button--primary.is-link) {
  background: transparent;
  border-color: transparent;
  color: var(--ef-ink);
  font-weight: 600;
}
:deep(.el-button--primary.is-link:hover) {
  color: var(--ef-ink);
  background: rgba(255,250,0,.18);
  border-color: transparent;
}
:deep(.el-tag) {
  border-radius: 2px;
  font-family: var(--ef-font-tech);
  letter-spacing: .04em;
}
:deep(.el-tag--primary) { background: rgba(25,25,25,.08); border-color: transparent; color: var(--ef-ink); }
:deep(.el-tag--success) { background: rgba(22,163,74,.12); border-color: transparent; color: #15803d; }
:deep(.el-tag--warning) { background: rgba(217,119,6,.12); border-color: transparent; color: #b45309; }
:deep(.el-tag--danger) { background: rgba(220,38,38,.12); border-color: transparent; color: #b91c1c; }
:deep(.el-tag--info) { background: rgba(25,25,25,.08); border-color: transparent; color: var(--ef-muted); }

/* ---------- Tabs ---------- */
.request-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--ef-surface);
}
.request-tabs :deep(.el-tabs__header) { margin: 0; padding: 0 16px; }
.request-tabs :deep(.el-tabs__nav-wrap::after) { background: var(--ef-line); height: 1px; }
.request-tabs :deep(.el-tabs__item) {
  height: 40px;
  line-height: 40px;
  font-family: var(--ef-font-tech);
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--ef-muted);
}
.request-tabs :deep(.el-tabs__item.is-active) { color: var(--ef-ink); font-weight: 700; }
.request-tabs :deep(.el-tabs__active-bar) { background: var(--ef-signal); height: 2px; }
.request-tabs :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 14px 16px;
}

/* ---------- Body / scripts / assertions / websocket panels ---------- */
.body-container { display: flex; flex-direction: column; gap: 12px; }
.raw-options { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.raw-body :deep(.el-textarea__inner),
.script-editor-container :deep(.el-textarea__inner) {
  font-family: var(--ef-font-mono);
  font-size: 12px;
  line-height: 1.6;
  border-radius: 2px;
}
.script-editor-container { display: flex; flex-direction: column; gap: 8px; }
.script-buttons { display: flex; gap: 8px; }
.data-factory-btn {
  background-color: var(--ef-ink);
  border-color: var(--ef-ink);
  color: #ffffff;
  font-weight: 600;
  border-radius: 2px;
}
.data-factory-btn:hover {
  background-color: #2c2c2c;
  border-color: var(--ef-signal);
  color: var(--ef-signal);
}
.variable-helper-btn {
  background-color: transparent;
  border-color: var(--ef-ink);
  color: var(--ef-ink);
  font-weight: 600;
  border-radius: 2px;
}
.variable-helper-btn:hover {
  background-color: rgba(255,250,0,.16);
  border-color: var(--ef-ink);
  color: var(--ef-ink);
}
.data-factory-btn:focus-visible,
.variable-helper-btn:focus-visible {
  outline: 2px solid var(--ef-signal);
  outline-offset: 1px;
}
.body-container :deep(.el-radio) { margin-right: 14px; }
.body-container :deep(.el-radio__label) {
  font-family: var(--ef-font-tech);
  font-size: 11px;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--ef-muted);
}
.body-container :deep(.el-radio__input.is-checked .el-radio__inner) { background: var(--ef-ink); border-color: var(--ef-ink); }
.body-container :deep(.el-radio__input.is-checked + .el-radio__label) { color: var(--ef-ink); font-weight: 700; }

.assertions-editor { display: flex; flex-direction: column; gap: 12px; }
.assertions-list { display: flex; flex-direction: column; gap: 10px; }
.assertion-item {
  border: 1px solid var(--ef-line);
  background: var(--ef-rail);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.assertion-header { display: flex; gap: 8px; align-items: center; }
.assertion-name { flex: 1; }
.assertion-config { display: flex; flex-direction: column; gap: 8px; }
.assertion-params { display: flex; flex-direction: column; gap: 8px; }
.no-assertions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 28px;
  border: 1px dashed var(--ef-line-strong);
  color: var(--ef-muted);
  text-align: center;
}
.no-assertions p { margin: 0; }

.message-container { display: flex; flex-direction: column; gap: 16px; }
.message-input-section { display: flex; flex-direction: column; gap: 10px; }
.message-actions { display: flex; gap: 8px; }
.websocket-response-section { border-top: 1px solid var(--ef-line); padding-top: 12px; }
.websocket-response-section h3 {
  margin: 0 0 10px;
  font-family: var(--ef-font-display);
  font-size: 14px;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.websocket-messages { display: flex; flex-direction: column; gap: 8px; max-height: 260px; overflow: auto; }
.websocket-message-item {
  border-left: 3px solid var(--ef-muted);
  background: var(--ef-rail);
  padding: 8px 10px;
}
.websocket-message-item.sent { border-left-color: var(--ef-ink); }
.websocket-message-item.received { border-left-color: var(--ef-signal); }
.websocket-message-item.connected { border-left-color: var(--ef-state); }
.websocket-message-item.info { border-left-color: #0891b2; }
.websocket-message-item.error { border-left-color: #dc2626; }
.message-header { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
.message-type {
  font-family: var(--ef-font-tech);
  font-size: 10px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--ef-muted);
}
.message-type.sent { color: var(--ef-ink); font-weight: 700; }
.message-type.received { color: #8a6d00; font-weight: 700; }
.message-type.connected { color: #0a7a4f; }
.message-type.error { color: #b91c1c; }
.message-type.info { color: #0e7490; }
.message-time { font-family: var(--ef-font-tech); font-size: 10px; color: var(--ef-muted); }
.message-content pre {
  margin: 0;
  font-family: var(--ef-font-mono);
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
.uploaded-file { display: flex; align-items: center; gap: 10px; font-size: 12px; }
.message-container :deep(.el-upload-dragger) {
  background: var(--ef-surface);
  border: 1px dashed var(--ef-line-strong);
  border-radius: 2px;
  transition: border-color .15s ease, background .15s ease;
}
.message-container :deep(.el-upload-dragger:hover) {
  border-color: var(--ef-ink);
  background: rgba(255,250,0,.08);
}
.message-container :deep(.el-upload-dragger .el-icon--upload) {
  color: var(--ef-ink);
}
.message-container :deep(.el-upload__text) {
  color: var(--ef-muted);
  font-family: var(--ef-font-tech);
  font-size: 12px;
  letter-spacing: .04em;
}

/* ---------- Response section ---------- */
.response-section {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  max-height: 46%;
  background: var(--ef-rail);
  border-top: 1px solid var(--ef-line-strong);
}
.response-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--ef-line);
}
.response-header h3 {
  margin: 0;
  font-family: var(--ef-font-display);
  font-size: 14px;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.response-info { display: flex; align-items: center; gap: 8px; }
.response-time { font-family: var(--ef-font-tech); font-size: 12px; color: var(--ef-muted); }
.response-section :deep(.el-tabs__header) { margin: 0; padding: 0 16px; }
.response-section :deep(.el-tabs__nav-wrap::after) { background: var(--ef-line); height: 1px; }
.response-section :deep(.el-tabs__item) {
  height: 34px;
  line-height: 34px;
  font-family: var(--ef-font-tech);
  font-size: 10px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--ef-muted);
}
.response-section :deep(.el-tabs__item.is-active) { color: var(--ef-ink); font-weight: 700; }
.response-section :deep(.el-tabs__active-bar) { background: var(--ef-signal); height: 2px; }
.response-section :deep(.el-tabs__content) { overflow: auto; }
.response-body { display: flex; flex-direction: column; }
.response-actions { padding: 10px 16px 0; }
.response-content {
  padding: 12px 16px;
  font-family: var(--ef-font-mono);
  font-size: 12px;
  line-height: 1.6;
  color: var(--ef-ink);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow: auto;
}
.response-headers { padding: 10px 16px; }
.header-row { padding: 6px 0; border-bottom: 1px solid var(--ef-line-soft); font-size: 12px; }
.header-row:last-child { border-bottom: none; }
.header-row strong { color: var(--ef-ink); }
.jsonpath-extractor { margin: 10px 16px 0; border: 1px dashed var(--ef-line-strong); padding: 10px; background: var(--ef-surface); }
.jsonpath-input :deep(.el-input__wrapper) { border-radius: 2px; }
.jsonpath-result { margin-top: 8px; padding: 8px 10px; background: rgba(25,25,25,.05); font-family: var(--ef-font-mono); font-size: 12px; }
.assertions-results { padding: 10px 16px; display: flex; flex-direction: column; gap: 8px; }
.assertion-result-item { border-left: 3px solid var(--ef-muted); background: var(--ef-surface); padding: 10px 12px; }
.assertion-result-item.passed { border-left-color: var(--ef-state); }
.assertion-result-item.failed { border-left-color: #dc2626; }
.assertion-result-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.assertion-result-header .assertion-name { font-weight: 600; font-size: 13px; }
.assertion-result-details { display: flex; flex-direction: column; gap: 4px; }
.result-row { display: flex; gap: 8px; font-size: 12px; }
.result-row .label {
  color: var(--ef-muted);
  min-width: 52px;
  font-family: var(--ef-font-tech);
  font-size: 10px;
  letter-spacing: .06em;
  text-transform: uppercase;
  padding-top: 1px;
}
.result-row .value { color: var(--ef-ink); word-break: break-all; }
.result-row .value.error { color: #b91c1c; }

/* ---------- Key-value editor alignment ---------- */
:deep(.key-value-editor .header) {
  font-family: var(--ef-font-tech);
  font-size: 10px;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: var(--ef-muted);
  border-bottom: 1px solid var(--ef-line);
  padding-bottom: 8px;
}
:deep(.key-value-editor .row) { border-bottom: 1px solid var(--ef-line-soft); padding: 6px 0; }
:deep(.key-value-editor .row:last-child) { border-bottom: none; }
:deep(.key-value-editor .footer) { padding-top: 8px; }
:deep(.key-value-editor .el-checkbox__inner) {
  width: 14px;
  height: 14px;
  border: 1px solid var(--ef-ink);
  border-radius: 0;
  background: #ffffff;
  transition: background .15s ease, border-color .15s ease;
}
:deep(.key-value-editor .el-checkbox__input:hover .el-checkbox__inner) { border-color: var(--ef-ink); }
:deep(.key-value-editor .el-checkbox.is-checked .el-checkbox__inner) {
  background: var(--ef-signal);
  border-color: var(--ef-signal);
}
:deep(.key-value-editor .el-checkbox.is-checked .el-checkbox__inner::after) { border-color: var(--ef-ink); }
:deep(.key-value-editor .el-checkbox__input.is-focus .el-checkbox__inner) {
  border-color: var(--ef-signal);
  outline: 1px solid rgba(255, 250, 0, .45);
  outline-offset: 1px;
}

/* ---------- Context menu ---------- */
.context-menu {
  position: fixed;
  z-index: 3000;
  margin: 0;
  padding: 4px 0;
  list-style: none;
  background: var(--ef-dock);
  border: 1px solid rgba(255,255,255,.12);
  min-width: 150px;
  color: rgba(255,255,255,.85);
}
.context-menu li {
  padding: 8px 14px;
  font-size: 12px;
  cursor: pointer;
  border-left: 2px solid transparent;
  transition: background .12s ease, color .12s ease, border-color .12s ease;
}
.context-menu li:hover {
  background: rgba(255,250,0,.1);
  border-left-color: var(--ef-signal);
  color: var(--ef-signal);
}

/* ---------- Hero control overrides (after generic retheme) ---------- */
.ef-dock .ef-dock-btn--primary {
  background: var(--ef-signal);
  border-color: var(--ef-signal);
  color: var(--ef-ink);
  font-weight: 700;
}
.ef-dock .ef-dock-btn--primary:hover {
  background: var(--ef-surface);
  border-color: #ffffff;
  color: var(--ef-ink);
}
.request-header .send-button.el-button--primary {
  position: relative;
  background: var(--ef-ink);
  border: 1px solid var(--ef-signal);
  color: var(--ef-signal);
  font-weight: 700;
  letter-spacing: .06em;
}
.request-header .send-button.el-button--primary::before {
  content: "";
  position: absolute;
  left: -1px;
  top: -1px;
  bottom: -1px;
  width: 4px;
  background: var(--ef-signal);
}
.request-header .send-button.el-button--primary:hover {
  background: #2c2c2c;
  color: #ffffff;
}
.request-header .send-button.el-button--primary:deep(.el-icon) { color: var(--ef-signal); }
.request-header .send-button.el-button--info {
  background: rgba(255,255,255,.06);
  border-color: rgba(255,255,255,.3);
  color: rgba(255,255,255,.85);
}
.request-header .send-button.el-button--info:hover {
  border-color: var(--ef-signal);
  color: var(--ef-signal);
}

/* ---------- Reveal motion ---------- */
.ef-page-head,
.ef-dock,
.sidebar,
.request-detail {
  animation: ef-wipe-in .6s cubic-bezier(.22,.8,.2,1) both;
}
.ef-dock { animation-delay: .06s; }
.sidebar { animation-delay: .12s; }
.request-detail { animation-delay: .18s; }
@keyframes ef-wipe-in {
  from { clip-path: inset(0 100% 0 0); transform: translateX(-8px); }
  to { clip-path: inset(0); transform: none; }
}

/* ---------- Scrollbars ---------- */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--ef-line-strong);
  border: 2px solid transparent;
  background-clip: content-box;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--ef-muted);
  border: 2px solid transparent;
  background-clip: content-box;
}

/* ---------- Visible focus ---------- */
:focus-visible {
  outline: 2px solid var(--ef-signal);
  outline-offset: 2px;
}
:deep(.el-input__wrapper:focus-visible),
:deep(.el-textarea__inner:focus-visible),
:deep(.el-select__wrapper:focus-visible),
:deep(.el-tree-node__content:focus-visible) {
  outline: 2px solid var(--ef-signal);
  outline-offset: 1px;
}

/* ---------- Responsive: shell adaptation ---------- */
@media (max-width: 1280px) {
  .sidebar { width: 260px; }
  .ef-dock__project { width: 180px; }
}
@media (max-width: 1024px) {
  .sidebar { width: 240px; }
  .env-select { width: 120px; }
}
@media (max-width: 768px), (orientation: portrait) {
  .ef-page-head {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
    padding: 14px 14px 12px;
  }
  .ef-page-head__status { width: 100%; }
  .ef-status-item { flex: 1; min-width: 0; }
  .ef-dock { flex-wrap: wrap; padding: 10px 14px; }
  .ef-dock__project { width: 100%; }
  .ef-dock__search { flex: 1 1 100%; }
  .ef-dock__actions { margin-left: 0; width: 100%; }
  .ef-dock__actions .ef-dock-btn { flex: 1; }
  .interface-layout { flex-direction: column; }
  .sidebar {
    width: 100%;
    height: 34vh;
    min-height: 200px;
    border-right: none;
    border-bottom: 1px solid var(--ef-line-strong);
  }
  .request-line { flex-wrap: wrap; }
  .method-select { width: 96px; }
  .env-select { width: 110px; }
  .url-input { flex: 1 1 100%; order: 3; }
  .request-meta { flex-wrap: wrap; }
  .action-buttons { width: 100%; flex-wrap: wrap; }
  .response-section { max-height: 40%; }
}

/* ---------- Reduced motion ---------- */
@media (prefers-reduced-motion: reduce) {
  .ef-page-head,
  .ef-dock,
  .sidebar,
  .request-detail,
  .search-result-item,
  .context-menu li {
    animation: none !important;
    transition: none !important;
  }
}
</style>

<style>
/* ============================================================
   Endfield / moderate - teleported surfaces
   Dialogs and select poppers are moved to <body> by Element Plus,
   so they cannot be reached from the scoped block above.
   ============================================================ */
.ef-modal {
  background: rgba(25, 25, 25, .5) !important;
  -webkit-backdrop-filter: blur(2px);
  backdrop-filter: blur(2px);
}
.ef-dialog {
  border-radius: 2px;
  border: 1px solid #c9c9c3;
  box-shadow: 12px 12px 0 rgba(25, 25, 25, .08);
  background: #fafaf8;
  color: #191919;
  overflow: hidden;
}
.ef-dialog .el-dialog__header {
  margin: 0;
  padding: 14px 18px;
  background: #191919;
  color: #ffffff;
  border-bottom: 2px solid #fffa00;
}
.ef-dialog .el-dialog__title {
  font-family: "Arial Narrow", "Roboto Condensed", "DIN Condensed", sans-serif;
  font-size: 16px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #ffffff;
}
.ef-dialog .el-dialog__headerbtn { top: 14px; }
.ef-dialog .el-dialog__headerbtn .el-dialog__close { color: rgba(255, 255, 255, .6); }
.ef-dialog .el-dialog__headerbtn:hover .el-dialog__close { color: #fffa00; }
.ef-dialog .el-dialog__body { padding: 16px 18px; }
.ef-dialog .el-dialog__footer {
  padding: 10px 18px 14px;
  border-top: 1px solid #dcdcd7;
  text-align: right;
}
.ef-dialog .el-form-item__label {
  font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #8a8a86;
}
.ef-dialog .el-input__wrapper,
.ef-dialog .el-textarea__inner,
.ef-dialog .el-select__wrapper {
  background: #ffffff;
  box-shadow: 0 0 0 1px #c9c9c3 inset;
  border-radius: 2px;
}
.ef-dialog .el-input__wrapper.is-focus,
.ef-dialog .el-select__wrapper.is-focused,
.ef-dialog .el-textarea__inner:focus {
  box-shadow: 0 0 0 1px #191919 inset;
}
.ef-dialog .el-button { border-radius: 2px; }
.ef-dialog .el-button--primary {
  background: #191919;
  border-color: #191919;
  color: #ffffff;
}
.ef-dialog .el-button--primary:hover {
  background: #2c2c2c;
  color: #fffa00;
}
.ef-dialog .el-button:focus-visible,
.ef-dialog .el-input__wrapper:focus-visible,
.ef-dialog .el-textarea__inner:focus-visible,
.ef-dialog .el-select__wrapper:focus-visible {
  outline: 2px solid #fffa00;
  outline-offset: 1px;
}
.ef-dialog .el-table {
  --el-table-border-color: #dcdcd7;
  --el-table-header-bg-color: #f2f2f0;
  --el-table-header-text-color: #191919;
  --el-table-row-hover-bg-color: rgba(255, 250, 0, .10);
  --el-table-text-color: #191919;
  font-size: 12px;
}
.ef-dialog .el-table th.el-table__cell { font-weight: 700; }
.ef-dialog .el-tabs__item {
  font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #8a8a86;
}
.ef-dialog .el-tabs__item.is-active { color: #191919; font-weight: 700; }
.ef-dialog .el-tabs__active-bar { background: #fffa00; height: 2px; }
.ef-dialog .el-tabs__nav-wrap::after { background: #dcdcd7; }

/* Method select dropdown popper */
.method-select-dropdown { border-radius: 2px; }
.method-select-dropdown .el-select-dropdown__item {
  font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
  font-weight: 700;
  letter-spacing: .08em;
  font-size: 12px;
}
.method-select-dropdown .el-select-dropdown__item.hover,
.method-select-dropdown .el-select-dropdown__item:hover {
  background: rgba(255, 250, 0, .16);
}
.method-select-dropdown .el-select-dropdown__item.is-selected,
.method-select-dropdown .el-select-dropdown__item.selected {
  color: #191919;
  font-weight: 800;
}
.method-select-dropdown .el-select-dropdown__item:focus-visible {
  outline: 2px solid #fffa00;
  outline-offset: -2px;
}
</style>
