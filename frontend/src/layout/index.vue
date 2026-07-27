<template>
  <div class="ark-layout" data-ark-theme="endfield" data-ark-depth="complex">
    <!-- ====== Grid Background ====== -->
    <div class="ark-layout__grid" aria-hidden="true"></div>

    <div class="ark-layout__shell">
      <!-- ====== Left Rail ====== -->
      <aside class="ark-rail">
        <!-- Logo -->
        <div class="ark-rail__logo" @click="router.push('/home')">
          <span class="ark-rail__wedge" aria-hidden="true"></span>
          <span class="ark-rail__brand">TestHub</span>
          <span class="ark-rail__code">PLATFORM</span>
        </div>

        <!-- Module indicator -->
        <div class="ark-rail__module-label">{{ moduleCode }}</div>

        <!-- Navigation -->
        <nav class="ark-rail__nav">
          <el-menu
            :default-active="$route.path"
            router
            background-color="transparent"
            text-color="rgba(255,255,255,.55)"
            active-text-color="#fffa00"
            class="ark-menu"
          >
            <!-- AI用例生成 -->
            <template v-if="currentModule === 'ai-generation'">
              <el-sub-menu index="requirement">
                <template #title>
                  <el-icon><MagicStick /></el-icon>
                  <span>{{ $t('menu.intelligentCaseGeneration') }}</span>
                </template>
                <el-menu-item index="/ai-generation/requirement-analysis">{{ $t('menu.aiCaseGeneration') }}</el-menu-item>
                <el-menu-item index="/ai-generation/generated-testcases">{{ $t('menu.aiGeneratedTestcases') }}</el-menu-item>
              </el-sub-menu>
              <el-menu-item index="/ai-generation/projects"><el-icon><Folder /></el-icon><span>{{ $t('menu.projectManagement') }}</span></el-menu-item>
              <el-menu-item index="/ai-generation/testcases"><el-icon><Document /></el-icon><span>{{ $t('menu.testCases') }}</span></el-menu-item>
              <el-menu-item index="/ai-generation/versions"><el-icon><Flag /></el-icon><span>{{ $t('menu.versionManagement') }}</span></el-menu-item>
              <el-sub-menu index="reviews">
                <template #title><el-icon><Check /></el-icon><span>{{ $t('menu.reviewManagement') }}</span></template>
                <el-menu-item index="/ai-generation/reviews">{{ $t('menu.reviewList') }}</el-menu-item>
                <el-menu-item index="/ai-generation/review-templates">{{ $t('menu.reviewTemplates') }}</el-menu-item>
              </el-sub-menu>
              <el-menu-item index="/ai-generation/executions"><el-icon><VideoPlay /></el-icon><span>{{ $t('menu.testPlan') }}</span></el-menu-item>
              <el-menu-item index="/ai-generation/reports"><el-icon><DataAnalysis /></el-icon><span>{{ $t('menu.testReport') }}</span></el-menu-item>
            </template>

            <!-- 接口测试 -->
            <template v-else-if="currentModule === 'api-testing'">
              <el-menu-item index="/api-testing/dashboard"><el-icon><Odometer /></el-icon><span>{{ $t('menu.dashboard') }}</span></el-menu-item>
              <el-menu-item index="/api-testing/projects"><el-icon><Folder /></el-icon><span>{{ $t('menu.projectManagement') }}</span></el-menu-item>
              <el-menu-item index="/api-testing/interfaces"><el-icon><Link /></el-icon><span>{{ $t('menu.interfaceManagement') }}</span></el-menu-item>
              <el-menu-item index="/api-testing/automation"><el-icon><VideoPlay /></el-icon><span>{{ $t('menu.automationTesting') }}</span></el-menu-item>
              <el-menu-item index="/api-testing/history"><el-icon><Timer /></el-icon><span>{{ $t('menu.requestHistory') }}</span></el-menu-item>
              <el-menu-item index="/api-testing/environments"><el-icon><Setting /></el-icon><span>{{ $t('menu.environmentManagement') }}</span></el-menu-item>
              <el-menu-item index="/api-testing/reports"><el-icon><DataAnalysis /></el-icon><span>{{ $t('menu.testReport') }}</span></el-menu-item>
              <el-menu-item index="/api-testing/scheduled-tasks"><el-icon><AlarmClock /></el-icon><span>{{ $t('menu.scheduledTasks') }}</span></el-menu-item>
              <el-menu-item index="/api-testing/notification-logs"><el-icon><Bell /></el-icon><span>{{ $t('menu.notificationList') }}</span></el-menu-item>
            </template>

            <!-- UI自动化 -->
            <template v-else-if="currentModule === 'ui-automation'">
              <el-menu-item index="/ui-automation/dashboard"><el-icon><Odometer /></el-icon><span>{{ $t('menu.dashboard') }}</span></el-menu-item>
              <el-menu-item index="/ui-automation/projects"><el-icon><Folder /></el-icon><span>{{ $t('menu.projectManagement') }}</span></el-menu-item>
              <el-menu-item index="/ui-automation/elements-enhanced"><el-icon><Aim /></el-icon><span>{{ $t('menu.elementManagement') }}</span></el-menu-item>
              <el-menu-item index="/ui-automation/test-cases"><el-icon><Document /></el-icon><span>{{ $t('menu.caseManagement') }}</span></el-menu-item>
              <el-menu-item index="/ui-automation/scripts-enhanced"><el-icon><Edit /></el-icon><span>{{ $t('menu.scriptGeneration') }}</span></el-menu-item>
              <el-menu-item index="/ui-automation/scripts"><el-icon><DocumentCopy /></el-icon><span>{{ $t('menu.scriptList') }}</span></el-menu-item>
              <el-menu-item index="/ui-automation/suites"><el-icon><Collection /></el-icon><span>{{ $t('menu.suiteManagement') }}</span></el-menu-item>
              <el-menu-item index="/ui-automation/executions"><el-icon><VideoPlay /></el-icon><span>{{ $t('menu.executionRecords') }}</span></el-menu-item>
              <el-menu-item index="/ui-automation/reports"><el-icon><DataAnalysis /></el-icon><span>{{ $t('menu.testReport') }}</span></el-menu-item>
              <el-menu-item index="/ui-automation/scheduled-tasks"><el-icon><AlarmClock /></el-icon><span>{{ $t('menu.scheduledTasks') }}</span></el-menu-item>
              <el-menu-item index="/ui-automation/notification-logs"><el-icon><Bell /></el-icon><span>{{ $t('menu.notificationList') }}</span></el-menu-item>
            </template>

            <!-- APP自动化 -->
            <template v-else-if="currentModule === 'app-automation'">
              <el-menu-item index="/app-automation/dashboard"><el-icon><Odometer /></el-icon><span>Dashboard</span></el-menu-item>
              <el-menu-item index="/app-automation/projects"><el-icon><Folder /></el-icon><span>项目管理</span></el-menu-item>
              <el-menu-item index="/app-automation/devices"><el-icon><Cellphone /></el-icon><span>设备管理</span></el-menu-item>
              <el-menu-item index="/app-automation/packages"><el-icon><Collection /></el-icon><span>包名管理</span></el-menu-item>
              <el-menu-item index="/app-automation/elements"><el-icon><Aim /></el-icon><span>元素管理</span></el-menu-item>
              <el-menu-item index="/app-automation/scene-builder"><el-icon><Connection /></el-icon><span>用例编排</span></el-menu-item>
              <el-menu-item index="/app-automation/test-cases"><el-icon><Document /></el-icon><span>测试用例</span></el-menu-item>
              <el-menu-item index="/app-automation/test-suites"><el-icon><FolderOpened /></el-icon><span>测试套件</span></el-menu-item>
              <el-menu-item index="/app-automation/executions"><el-icon><VideoPlay /></el-icon><span>执行记录</span></el-menu-item>
              <el-menu-item index="/app-automation/reports"><el-icon><DataAnalysis /></el-icon><span>测试报告</span></el-menu-item>
              <el-menu-item index="/app-automation/scheduled-tasks"><el-icon><AlarmClock /></el-icon><span>定时任务</span></el-menu-item>
              <el-menu-item index="/app-automation/notification-logs"><el-icon><Bell /></el-icon><span>通知列表</span></el-menu-item>
            </template>

            <!-- AI 智能模式 -->
            <template v-else-if="currentModule === 'ai-intelligent-mode'">
              <el-menu-item index="/ai-intelligent-mode/midscene"><el-icon><Cellphone /></el-icon><span>Midscene 移动端测试</span></el-menu-item>
              <el-menu-item index="/ai-intelligent-mode/midscene/projects"><el-icon><Folder /></el-icon><span>Midscene 项目管理</span></el-menu-item>
              <el-menu-item index="/ai-intelligent-mode/midscene/executions"><el-icon><Timer /></el-icon><span>Midscene 执行历史</span></el-menu-item>
              <el-menu-item index="/ai-intelligent-mode/midscene/devices"><el-icon><Cellphone /></el-icon><span>Midscene 设备管理</span></el-menu-item>
            </template>

            <!-- 配置中心 -->
            <template v-else-if="currentModule === 'configuration'">
              <el-sub-menu index="ai-case-generation">
                <template #title><el-icon><MagicStick /></el-icon><span>{{ $t('menu.aiCaseGenerationConfig') }}</span></template>
                <el-menu-item index="/configuration/ai-model"><el-icon><Cpu /></el-icon><span>{{ $t('menu.aiModelConfig') }}</span></el-menu-item>
                <el-menu-item index="/configuration/prompt-config"><el-icon><Edit /></el-icon><span>{{ $t('menu.promptConfig') }}</span></el-menu-item>
                <el-menu-item index="/configuration/generation-config"><el-icon><Setting /></el-icon><span>{{ $t('menu.generationConfig') }}</span></el-menu-item>
              </el-sub-menu>
              <el-menu-item index="/configuration/ui-env"><el-icon><Monitor /></el-icon><span>{{ $t('menu.uiEnvConfig') }}</span></el-menu-item>
              <el-menu-item index="/configuration/app-env"><el-icon><Cellphone /></el-icon><span>APP环境配置</span></el-menu-item>
              <el-menu-item index="/configuration/ai-mode"><el-icon><MagicStick /></el-icon><span>{{ $t('menu.aiModeConfig') }}</span></el-menu-item>
              <el-menu-item index="/configuration/scheduled-task"><el-icon><Timer /></el-icon><span>{{ $t('menu.scheduledTaskConfig') }}</span></el-menu-item>
              <el-menu-item index="/configuration/dify"><el-icon><ChatDotRound /></el-icon><span>{{ $t('menu.difyConfig') }}</span></el-menu-item>
            </template>
          </el-menu>
        </nav>

        <!-- Bottom status -->
        <div class="ark-rail__foot">
          <span class="ark-rail__dot" aria-hidden="true"></span>
          <span class="ark-rail__status">ONLINE</span>
        </div>
      </aside>

      <!-- ====== Main Area ====== -->
      <div class="ark-main">
        <!-- Header -->
        <header class="ark-topbar">
          <div class="ark-topbar__left">
            <el-breadcrumb separator="">
              <el-breadcrumb-item :to="{ path: '/home' }">
                <span class="ark-breadcrumb__home">{{ $t('nav.home') }}</span>
              </el-breadcrumb-item>
              <span class="ark-breadcrumb__sep">/</span>
              <el-breadcrumb-item v-if="moduleName">
                <span class="ark-breadcrumb__mod">{{ moduleName }}</span>
              </el-breadcrumb-item>
              <span class="ark-breadcrumb__sep" v-if="moduleName">/</span>
              <el-breadcrumb-item>
                <span class="ark-breadcrumb__page">{{ breadcrumbTitle }}</span>
              </el-breadcrumb-item>
            </el-breadcrumb>
          </div>
          <div class="ark-topbar__right">
            <el-dropdown @command="handleLanguageChange" trigger="click">
              <span class="ark-topbar__action">
                {{ appStore.language === 'zh-cn' ? 'CN' : 'EN' }}
                <el-icon><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="zh-cn" :disabled="appStore.language === 'zh-cn'">🇨🇳 简体中文</el-dropdown-item>
                  <el-dropdown-item command="en" :disabled="appStore.language === 'en'">🇺🇸 English</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-dropdown @command="handleCommand" trigger="click">
              <span class="ark-topbar__action">
                <el-avatar :size="24" />
                <span class="ark-topbar__user">{{ userStore.user?.username }}</span>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">{{ $t('nav.profile') }}</el-dropdown-item>
                  <el-dropdown-item divided command="logout">{{ $t('nav.logout') }}</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </header>

        <!-- Content -->
        <main class="ark-content">
          <router-view />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import {
  Monitor, Folder, Document, Flag, Check, Collection, VideoPlay,
  DataAnalysis, ChatDotRound, DocumentCopy, Link, MagicStick,
  Odometer, Timer, Setting, AlarmClock, Bell, Aim, Edit, Cpu, ArrowDown, Cellphone, Connection, FolderOpened
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const appStore = useAppStore()
const { t } = useI18n()

const handleLanguageChange = (lang) => {
  appStore.setLanguage(lang)
  ElMessage.success(lang === 'zh-cn' ? '语言已切换为中文' : 'Language switched to English')
}

const currentModule = computed(() => {
  if (route.path.startsWith('/ai-generation')) return 'ai-generation'
  if (route.path.startsWith('/api-testing')) return 'api-testing'
  if (route.path.startsWith('/ui-automation')) return 'ui-automation'
  if (route.path.startsWith('/app-automation')) return 'app-automation'
  if (route.path.startsWith('/ai-intelligent-mode')) return 'ai-intelligent-mode'
  if (route.path.startsWith('/configuration')) return 'configuration'
  return ''
})

const moduleCode = computed(() => {
  const map = {
    'ai-generation': 'MODULE / 01',
    'api-testing': 'MODULE / 02',
    'ui-automation': 'MODULE / 03',
    'app-automation': 'MODULE / 04',
    'ai-intelligent-mode': 'MODULE / 05',
    'configuration': 'MODULE / 06',
  }
  return map[currentModule.value] || ''
})

const moduleName = computed(() => {
  const map = {
    'ai-generation': t('modules.aiGeneration'),
    'api-testing': t('modules.apiTesting'),
    'ui-automation': t('modules.uiAutomation'),
    'app-automation': 'APP自动化测试',
    'ai-intelligent-mode': t('modules.aiIntelligentMode'),
    'configuration': t('modules.configuration')
  }
  return map[currentModule.value] || ''
})

const breadcrumbTitle = computed(() => {
  const routeMap = {
    '/ai-generation/requirement-analysis': t('menu.aiCaseGeneration'),
    '/ai-generation/generated-testcases': t('menu.aiGeneratedTestcases'),
    '/ai-generation/projects': t('menu.projectManagement'),
    '/ai-generation/testcases': t('menu.testCases'),
    '/ai-generation/versions': t('menu.versionManagement'),
    '/ai-generation/reviews': t('menu.reviewList'),
    '/ai-generation/review-templates': t('menu.reviewTemplates'),
    '/ai-generation/testsuites': t('menu.suiteManagement'),
    '/ai-generation/executions': t('menu.executionRecords'),
    '/ai-generation/reports': t('menu.testReport'),
    '/api-testing/dashboard': t('menu.dashboard'),
    '/api-testing/projects': t('menu.projectManagement'),
    '/api-testing/interfaces': t('menu.interfaceManagement'),
    '/api-testing/automation': t('menu.automationTesting'),
    '/api-testing/history': t('menu.requestHistory'),
    '/api-testing/environments': t('menu.environmentManagement'),
    '/api-testing/reports': t('menu.testReport'),
    '/api-testing/scheduled-tasks': t('menu.scheduledTasks'),
    '/api-testing/notification-logs': t('menu.notificationList'),
    '/ui-automation/dashboard': t('menu.dashboard'),
    '/ui-automation/projects': t('menu.projectManagement'),
    '/ui-automation/elements-enhanced': t('menu.elementManagement'),
    '/ui-automation/test-cases': t('menu.caseManagement'),
    '/ui-automation/scripts-enhanced': t('menu.scriptGeneration'),
    '/ui-automation/scripts': t('menu.scriptList'),
    '/ui-automation/suites': t('menu.suiteManagement'),
    '/ui-automation/executions': t('menu.executionRecords'),
    '/ui-automation/reports': t('menu.testReport'),
    '/ui-automation/scheduled-tasks': t('menu.scheduledTasks'),
    '/ui-automation/notification-logs': t('menu.notificationList'),
    '/app-automation/dashboard': 'Dashboard',
    '/app-automation/projects': '项目管理',
    '/app-automation/devices': '设备管理',
    '/app-automation/packages': '包名管理',
    '/app-automation/elements': '元素管理',
    '/app-automation/scene-builder': '用例编排',
    '/app-automation/test-cases': '测试用例',
    '/app-automation/test-suites': '测试套件',
    '/app-automation/scheduled-tasks': '定时任务',
    '/app-automation/notification-logs': '通知列表',
    '/app-automation/executions': '执行记录',
    '/app-automation/reports': '测试报告',
    '/ai-intelligent-mode/midscene': 'Midscene 移动端测试',
    '/ai-intelligent-mode/midscene/projects': 'Midscene 项目管理',
    '/ai-intelligent-mode/midscene/executions': 'Midscene 执行历史',
    '/ai-intelligent-mode/midscene/devices': 'Midscene 设备管理',
    '/configuration/ai-model': t('menu.aiModelConfig'),
    '/configuration/prompt-config': t('menu.promptConfig'),
    '/configuration/generation-config': t('menu.generationConfig'),
    '/configuration/ui-env': t('menu.uiEnvConfig'),
    '/configuration/ai-mode': t('menu.aiModeConfig'),
    '/configuration/scheduled-task': t('menu.scheduledTaskConfig'),
    '/configuration/dify': t('menu.difyConfig'),
    '/profile': t('nav.profile')
  }
  return routeMap[route.path] || route.meta.title || ''
})

const handleCommand = (command) => {
  if (command === 'logout') {
    userStore.logout()
    ElMessage.success('退出登录成功')
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/ai-generation/profile')
  }
}
</script>

<style lang="scss" scoped>
/* =============================================
   Endfield Complex — Layout Shell
   ============================================= */
.ark-layout {
  height: 100vh; width: 100vw; overflow: hidden;
  position: relative;
  background: #f2f2f0;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;

  &__grid {
    position: absolute; inset: 0; pointer-events: none; z-index: 0;
    background-image:
      linear-gradient(to right, #e0e0dc 1px, transparent 1px),
      linear-gradient(to bottom, #e0e0dc 1px, transparent 1px);
    background-size: 80px 80px; opacity: .35;
  }
  &__shell {
    position: relative; z-index: 1;
    display: flex; height: 100%;
  }
}

/* ============================================
   Rail (dark sidebar)
   ============================================ */
.ark-rail {
  width: 220px; flex-shrink: 0;
  background: #111;
  display: flex; flex-direction: column;
  border-right: 1px solid rgba(255,255,255,.05);

  &__logo {
    padding: 20px 18px 16px;
    display: flex; flex-direction: column; gap: 2px;
    cursor: pointer;
    border-bottom: 1px solid rgba(255,255,255,.06);
  }
  &__wedge {
    display: block; width: 20px; height: 4px; background: #fffa00;
    clip-path: polygon(0 0, 100% 0, 80% 100%, 0 100%);
    margin-bottom: 8px;
  }
  &__brand {
    font-size: 16px; font-weight: 800; color: rgba(255,255,255,.90);
    letter-spacing: .04em; line-height: 1.1;
  }
  &__code {
    font-size: 9px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .18em; color: rgba(255,255,255,.25);
  }
  &__module-label {
    padding: 14px 18px 8px;
    font-size: 10px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .14em; color: rgba(255,255,255,.25);
  }
  &__nav {
    flex: 1; overflow-y: auto;
    &::-webkit-scrollbar { width: 0; }
  }
  &__foot {
    padding: 12px 18px;
    border-top: 1px solid rgba(255,255,255,.06);
    display: flex; align-items: center; gap: 8px;
  }
  &__dot {
    width: 5px; height: 5px; background: #00ffa2; flex-shrink: 0;
  }
  &__status {
    font-size: 9px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .14em; color: rgba(255,255,255,.30);
  }
}

/* Override Element Plus menu inside rail */
.ark-menu {
  border-right: none !important;
  background: transparent !important;

  :deep(.el-sub-menu__title),
  :deep(.el-menu-item) {
    height: 38px; line-height: 38px;
    font-size: 13px; font-family: "Noto Sans SC", "PingFang SC", sans-serif;
    padding-left: 18px !important;
    margin: 1px 8px;
    border-radius: 0;
    transition: all .12s;
    border-left: 2px solid transparent;

    &:hover {
      background: rgba(255,255,255,.03) !important;
      color: rgba(255,255,255,.75) !important;
    }
  }

  :deep(.el-menu-item.is-active) {
    background: rgba(255,250,0,.06) !important;
    color: #fffa00 !important;
    border-left-color: #fffa00;
  }

  :deep(.el-sub-menu .el-menu) {
    background: rgba(0,0,0,.20) !important;
  }

  :deep(.el-sub-menu .el-menu-item) {
    padding-left: 36px !important;
    font-size: 12px;
    height: 34px; line-height: 34px;
  }

  :deep(.el-sub-menu__icon-arrow) {
    color: rgba(255,255,255,.20);
  }

  :deep(.el-icon) {
    font-size: 16px; color: inherit;
  }
}

/* ============================================
   Main Area
   ============================================ */
.ark-main {
  flex: 1; display: flex; flex-direction: column;
  min-width: 0; overflow: hidden;
}

/* Header */
.ark-topbar {
  height: 52px; flex-shrink: 0;
  background: #fff;
  border-bottom: 1px solid #e8e8e4;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px;

  &__left {
    display: flex; align-items: center;
    :deep(.el-breadcrumb) { font-size: 13px; }
    :deep(.el-breadcrumb__item) { display: flex; align-items: center; }
  }
  &__right {
    display: flex; align-items: center; gap: 16px;
  }
  &__action {
    display: inline-flex; align-items: center; gap: 5px;
    cursor: pointer; font-size: 12px; color: #888;
    font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .06em;
    padding: 4px 8px; transition: color .15s;
    &:hover { color: #333; }
  }
  &__user {
    font-size: 13px; color: #555; font-family: "Noto Sans SC", sans-serif; text-transform: none; letter-spacing: 0;
  }
}

.ark-breadcrumb {
  &__home {
    color: #999; font-family: "Space Grotesk", system-ui, sans-serif;
    font-size: 11px; text-transform: uppercase; letter-spacing: .08em;
  }
  &__sep {
    color: #ddd; margin: 0 8px; font-size: 14px;
  }
  &__mod {
    color: #666; font-size: 12px; font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .06em;
  }
  &__page {
    color: #333; font-size: 13px; font-weight: 500;
  }
}

/* Content */
.ark-content {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  // Individual page components handle their own padding/background
}

/* ============================================
   Responsive
   ============================================ */
@media (max-width: 1440px) { .ark-rail { width: 200px; } }
@media (max-width: 1280px) { .ark-rail { width: 180px; } .ark-topbar { padding: 0 16px; } }
@media (max-width: 1024px) { .ark-rail { width: 160px; } }
@media (max-width: 768px) {
  .ark-rail {
    position: fixed; left: 0; top: 0; z-index: 1000;
    width: 240px; height: 100%;
    transform: translateX(-100%); transition: transform .25s;
  }
  .ark-topbar { padding: 0 12px; height: 48px; }
}
</style>
