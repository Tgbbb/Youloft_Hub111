<template>
  <div class="dashboard-container">
    <!-- 数据概览 -->
    <div class="stats-section">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-content">
              <div class="stat-icon bg-blue">
                <el-icon><Folder /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ projectCount }}</div>
                <div class="stat-label">{{ $t('apiTesting.dashboard.apiProjects') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-content">
              <div class="stat-icon bg-green">
                <el-icon><Link /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ interfaceCount }}</div>
                <div class="stat-label">{{ $t('apiTesting.dashboard.interfaceCount') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-content">
              <div class="stat-icon bg-purple">
                <el-icon><Collection /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ suiteCount }}</div>
                <div class="stat-label">{{ $t('apiTesting.dashboard.testSuites') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-content">
              <div class="stat-icon bg-orange">
                <el-icon><Timer /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ historyCount }}</div>
                <div class="stat-label">{{ $t('apiTesting.dashboard.executionRecords') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
    
    <!-- 最近活动和快速操作 -->
    <el-row :gutter="20" class="content-section">
      <!-- 最近活动 -->
      <el-col :span="12">
      <el-card class="recent-activities" :title="$t('apiTesting.dashboard.operationLogs')" shadow="hover">
        <div v-if="loading" class="loading-container">
          <el-empty :description="$t('apiTesting.dashboard.loading')" />
        </div>
        <div v-else-if="operationLogs.length === 0" class="activities-list">
          <el-empty :description="$t('apiTesting.dashboard.noLogs')" />
        </div>
        <div v-else class="activities-list">
          <div v-for="log in operationLogs" :key="log.id" class="activity-item">
            <div class="activity-icon" :class="'activity-icon--' + (log.operation_type || 'other')">
              <el-icon v-if="log.operation_type === 'create'"><Plus /></el-icon>
              <el-icon v-else-if="log.operation_type === 'edit'"><Edit /></el-icon>
              <el-icon v-else-if="log.operation_type === 'delete'"><Delete /></el-icon>
              <el-icon v-else-if="log.operation_type === 'execute'"><VideoPlay /></el-icon>
              <el-icon v-else><Operation /></el-icon>
            </div>
            <div class="activity-content">
              <div class="activity-description">{{ log.description }}</div>
              <div class="activity-meta">
                <span class="activity-user">{{ log.user_name || $t('apiTesting.dashboard.system') }}</span>
                <span class="activity-time">{{ formatTime(log.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </el-card>
      </el-col>
      
      <!-- 快速操作 -->
      <el-col :span="12">
        <el-card class="quick-actions" :title="$t('apiTesting.dashboard.quickActions.title')" shadow="hover">
          <div class="actions-grid">
            <div class="action-item" @click="goToProjects">
              <div class="action-icon bg-blue">
                <el-icon><Folder /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.projectManagement') }}</div>
            </div>
            <div class="action-item" @click="goToInterfaces">
              <div class="action-icon bg-green">
                <el-icon><Link /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.interfaceManagement') }}</div>
            </div>
            <div class="action-item" @click="goToAutomation">
              <div class="action-icon bg-cyan">
                <el-icon><VideoPlay /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.automationTesting') }}</div>
            </div>
            <div class="action-item" @click="goToHistory">
              <div class="action-icon bg-purple">
                <el-icon><Timer /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.requestHistory') }}</div>
            </div>
            <div class="action-item" @click="goToEnvironments">
              <div class="action-icon bg-orange">
                <el-icon><Setting /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.environmentManagement') }}</div>
            </div>
            <div class="action-item" @click="goToReports">
              <div class="action-icon bg-indigo">
                <el-icon><DataAnalysis /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.testReport') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 核心功能介绍 -->
    <div class="features-section">
      <h2 class="section-title">{{ $t('apiTesting.dashboard.coreFeatures') }}</h2>
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card shadow="hover" class="feature-card">
            <div class="feature-icon">
              <el-icon><Link /></el-icon>
            </div>
            <h3 class="feature-title">{{ $t('apiTesting.dashboard.features.interfaceManagement.title') }}</h3>
            <p class="feature-description">{{ $t('apiTesting.dashboard.features.interfaceManagement.description') }}</p>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="feature-card">
            <div class="feature-icon">
              <el-icon><VideoPlay /></el-icon>
            </div>
            <h3 class="feature-title">{{ $t('apiTesting.dashboard.features.automationTesting.title') }}</h3>
            <p class="feature-description">{{ $t('apiTesting.dashboard.features.automationTesting.description') }}</p>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="feature-card">
            <div class="feature-icon">
              <el-icon><Timer /></el-icon>
            </div>
            <h3 class="feature-title">{{ $t('apiTesting.dashboard.features.scheduledTask.title') }}</h3>
            <p class="feature-description">{{ $t('apiTesting.dashboard.features.scheduledTask.description') }}</p>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="feature-card">
            <div class="feature-icon">
              <el-icon><DataAnalysis /></el-icon>
            </div>
            <h3 class="feature-title">{{ $t('apiTesting.dashboard.features.multiDimensionalReport.title') }}</h3>
            <p class="feature-description">{{ $t('apiTesting.dashboard.features.multiDimensionalReport.description') }}</p>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import {
  Folder, Link, Collection, Timer,
  VideoPlay, Setting, DataAnalysis,
  Plus, Edit, Delete, Operation
} from '@element-plus/icons-vue'
import router from '@/router'
import {
  getDashboardStats,
  getOperationLogs
} from '@/api/api-testing'

const { t } = useI18n()

// 统计数据
const projectCount = ref(0)
const interfaceCount = ref(0)
const suiteCount = ref(0)
const historyCount = ref(0)

const loading = ref(false)
const operationLogs = ref([])

// 加载数据
const loadDashboardData = async () => {
  loading.value = true
  try {
    // 并行加载统计数据和操作日志
    const [statsRes, logsRes] = await Promise.all([
      getDashboardStats(),
      getOperationLogs({ page_size: 20, ordering: '-created_at' })
    ])

    // 更新统计数据
    const stats = statsRes.data
    projectCount.value = stats.project_count || 0
    interfaceCount.value = stats.interface_count || 0
    suiteCount.value = stats.suite_count || 0
    historyCount.value = stats.history_count || 0
    
    // 更新操作日志
    operationLogs.value = logsRes.data.results || []

  } catch (error) {
    // ElMessage.error('加载仪表板数据失败')
    console.error('加载仪表板数据失败:', error)
  } finally {
    loading.value = false
  }
}

// 导航到各功能页面
const goToProjects = () => {
  router.push('/api-testing/projects')
}

const goToInterfaces = () => {
  router.push('/api-testing/interfaces')
}

const goToAutomation = () => {
  router.push('/api-testing/automation')
}

const goToHistory = () => {
  router.push('/api-testing/history')
}

const goToEnvironments = () => {
  router.push('/api-testing/environments')
}

const goToReports = () => {
  router.push('/api-testing/reports')
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  // const diff = now - date
  if (isNaN(date.getTime())) return ''; // 处理无效日期
  const diff = Date.now() - date.getTime();

  // 小于1分钟
  if (diff < 60000) {
    return t('apiTesting.dashboard.timeFormat.justNow')
  }
  // 小于1小时
  if (diff < 3600000) {
    return t('apiTesting.dashboard.timeFormat.minutesAgo', { n: Math.floor(diff / 60000) })
  }
  // 小于1天
  if (diff < 86400000) {
    return t('apiTesting.dashboard.timeFormat.hoursAgo', { n: Math.floor(diff / 3600000) })
  }
  // 小于7天
  if (diff < 604800000) {
    return t('apiTesting.dashboard.timeFormat.daysAgo', { n: Math.floor(diff / 86400000) })
  }
  // 超过7天显示具体日期
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 组件挂载时加载数据
onMounted(() => {
  loadDashboardData()
})
</script>

<style scoped>
.dashboard-container {
  width: 100%;
  padding: 20px;
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

.stats-section {
  margin-bottom: 40px;
}

.stat-card {
  height: 100%;
}

.stat-content {
  display: flex;
  align-items: center;
  height: 100px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20px;
  color: white;
  font-size: 24px;
  background-color: var(--ef-ink);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .12);
  position: relative;
}

.stat-icon::after {
  content: "";
  position: absolute;
  right: 0;
  top: 0;
  width: 10px;
  height: 10px;
  background: var(--ef-signal);
  clip-path: polygon(100% 0, 100% 100%, 0 0);
}

.stat-icon :deep(.el-icon) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon :deep(.el-icon svg) {
  width: 100%;
  height: 60%;
}

.stat-icon.bg-blue,
.stat-icon.bg-green,
.stat-icon.bg-purple,
.stat-icon.bg-orange {
  background-color: var(--ef-ink);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--ef-ink);
  font-family: var(--ef-font-display);
  letter-spacing: .02em;
  margin-bottom: 5px;
}

.stat-label {
  font-size: 12px;
  color: var(--ef-muted);
  font-family: var(--ef-font-tech);
  letter-spacing: .08em;
  text-transform: uppercase;
}

.content-section {
  margin-bottom: 40px;
}

.recent-activities {
  height: 100%;
}

.activities-list {
  max-height: 400px;
  overflow-y: auto;
}

.quick-actions {
  height: 100%;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
}

.action-item {
  text-align: center;
  padding: 15px 10px;
  border-radius: 2px;
  background-color: var(--ef-surface);
  border: 1px solid var(--ef-line);
  cursor: pointer;
  transition: background-color .15s ease, border-color .15s ease, transform .15s ease;
}

.action-item:hover {
  background-color: rgba(255, 250, 0, .10);
  border-color: var(--ef-ink);
  transform: translateY(-2px);
  box-shadow: 0 2px 0 rgba(25, 25, 25, .08);
}

.action-item .action-icon {
  margin: 0 auto 15px;
  width: 50px;
  height: 50px;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
  background-color: var(--ef-ink);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .12);
}

.action-icon :deep(.el-icon) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-icon :deep(.el-icon svg) {
  width: 60%;
  height: 60%;
}

.action-icon.bg-blue,
.action-icon.bg-green,
.action-icon.bg-cyan,
.action-icon.bg-purple,
.action-icon.bg-orange,
.action-icon.bg-indigo {
  background-color: var(--ef-ink);
}

.action-label {
  font-size: 14px;
  color: var(--ef-ink);
  font-weight: 600;
  letter-spacing: .04em;
}

.features-section {
  margin-bottom: 40px;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 20px;
  color: var(--ef-ink);
  font-family: var(--ef-font-display);
  letter-spacing: .08em;
  text-transform: uppercase;
  position: relative;
  padding-bottom: 8px;
}

.section-title::after {
  content: "";
  position: absolute;
  left: 0;
  bottom: 0;
  width: 36px;
  height: 3px;
  background: var(--ef-signal);
}

.feature-card {
  height: 100%;
  padding: 30px;
  text-align: center;
}

.feature-icon {
  width: 80px;
  height: 80px;
  border-radius: 2px;
  background-color: var(--ef-surface);
  border: 1px solid var(--ef-line-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  font-size: 36px;
  color: var(--ef-ink);
  transition: border-color .15s ease, color .15s ease;
}

.feature-card:hover .feature-icon {
  border-color: var(--ef-signal);
}

.feature-icon :deep(.el-icon) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.feature-icon :deep(.el-icon svg) {
  width: 60%;
  height: 60%;
}

.feature-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 10px;
  color: var(--ef-ink);
  font-family: var(--ef-font-display);
  letter-spacing: .08em;
  text-transform: uppercase;
}

.feature-description {
  font-size: 13px;
  color: var(--ef-muted);
  line-height: 1.6;
}

.loading-container {
  padding: 40px 0;
}

.activity-item {
  display: flex;
  align-items: flex-start;
  padding: 12px 0;
  border-bottom: 1px solid var(--ef-line-soft);
}

.activity-item:last-child {
  border-bottom: none;
}

.activity-icon {
  width: 32px;
  height: 32px;
  border-radius: 2px;
  background-color: var(--ef-rail);
  border: 1px solid var(--ef-line-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  flex-shrink: 0;
}

.activity-icon--create :deep(.el-icon) { color: #16a34a; }
.activity-icon--edit :deep(.el-icon) { color: #3b82f6; }
.activity-icon--delete :deep(.el-icon) { color: #dc2626; }
.activity-icon--execute :deep(.el-icon) { color: #722ed1; }
.activity-icon--other :deep(.el-icon) { color: var(--ef-muted); }

.activity-icon :deep(.el-icon) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.activity-icon :deep(.el-icon svg) {
  width: 60%;
  height: 60%;
}

.activity-content {
  flex: 1;
  min-width: 0;
}

.activity-description {
  font-size: 14px;
  color: var(--ef-ink);
  margin-bottom: 4px;
  word-break: break-all;
}

.activity-meta {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: var(--ef-muted);
}

.activity-user {
  margin-right: 12px;
}

.activity-time {
  color: var(--ef-muted);
  font-family: var(--ef-font-tech);
}

/* ---------- Element Plus cards & empty states ---------- */
.dashboard-container :deep(.el-card) {
  border-radius: 2px;
  border-color: var(--ef-line-strong);
  background: var(--ef-rail);
  --el-card-border-color: var(--ef-line-strong);
  --el-card-bg-color: var(--ef-rail);
  --el-card-hover-border: var(--ef-ink);
  --el-card-hover-shadow: 4px 4px 0 rgba(25, 25, 25, .06);
  transition: border-color .15s ease, box-shadow .15s ease;
}
.dashboard-container :deep(.el-card.is-hover-shadow:hover) {
  border-color: var(--ef-ink);
  box-shadow: 4px 4px 0 rgba(25, 25, 25, .06);
}
.dashboard-container :deep(.el-card__header) {
  padding: 14px 18px;
  border-bottom: 1px solid var(--ef-line);
  font-family: var(--ef-font-display);
  font-size: 14px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--ef-ink);
  font-weight: 700;
}
.dashboard-container :deep(.el-card__body) { padding: 18px; }
.dashboard-container :deep(.el-empty__description) { color: var(--ef-muted); }

@media (prefers-reduced-motion: reduce) {
  .action-item,
  .feature-icon,
  .dashboard-container :deep(.el-card) {
    transition: none;
  }
}

@media screen and (max-width: 1920px) {
  .stats-section {
    margin-bottom: 36px;
  }
  
  .stat-content {
    height: 90px;
  }
  
  .stat-icon {
    width: 55px;
    height: 55px;
    font-size: 22px;
  }
  
  .stat-value {
    font-size: 26px;
  }
  
  .content-section {
    margin-bottom: 36px;
  }
  
  .features-section {
    margin-bottom: 36px;
  }
}

@media screen and (max-width: 1600px) {
  .stats-section {
    margin-bottom: 32px;
  }
  
  .stat-content {
    height: 85px;
  }
  
  .stat-icon {
    width: 50px;
    height: 50px;
    font-size: 20px;
  }
  
  .stat-value {
    font-size: 24px;
  }
  
  .content-section {
    margin-bottom: 32px;
  }
  
  .features-section {
    margin-bottom: 32px;
  }
  
  .section-title {
    font-size: 22px;
  }
}

@media screen and (max-width: 1440px) {
  .stats-section {
    margin-bottom: 28px;
  }
  
  .stat-content {
    height: 80px;
  }
  
  .stat-icon {
    width: 48px;
    height: 48px;
    font-size: 18px;
  }
  
  .stat-value {
    font-size: 22px;
  }
  
  .content-section {
    margin-bottom: 28px;
  }
  
  .features-section {
    margin-bottom: 28px;
  }
  
  .section-title {
    font-size: 20px;
  }
  
  .actions-grid {
    gap: 12px;
  }
  
  .action-item {
    padding: 12px 8px;
  }
  
  .action-icon {
    width: 45px;
    height: 45px;
    font-size: 22px;
  }
  
  .action-label {
    font-size: 15px;
  }
}

@media screen and (max-width: 1366px) {
  .stats-section {
    margin-bottom: 24px;
  }
  
  .stat-content {
    height: 75px;
  }
  
  .stat-icon {
    width: 45px;
    height: 45px;
    font-size: 18px;
  }
  
  .stat-value {
    font-size: 20px;
  }
  
  .stat-label {
    font-size: 13px;
  }
  
  .content-section {
    margin-bottom: 24px;
  }
  
  .features-section {
    margin-bottom: 24px;
  }
  
  .section-title {
    font-size: 18px;
  }
  
  .activities-list {
    max-height: 350px;
  }
  
  .actions-grid {
    gap: 10px;
  }
  
  .action-item {
    padding: 10px 6px;
  }
  
  .action-icon {
    width: 40px;
    height: 40px;
    font-size: 20px;
  }
  
  .action-label {
    font-size: 14px;
  }
  
  .feature-card {
    padding: 20px;
  }
  
  .feature-icon {
    width: 70px;
    height: 70px;
    font-size: 32px;
  }
  
  .feature-title {
    font-size: 16px;
  }
  
  .feature-description {
    font-size: 13px;
  }
}

@media screen and (max-width: 1280px) {
  .stats-section {
    margin-bottom: 20px;
  }
  
  .stat-content {
    height: 70px;
  }
  
  .stat-icon {
    width: 42px;
    height: 42px;
    font-size: 16px;
  }
  
  .stat-value {
    font-size: 18px;
  }
  
  .stat-label {
    font-size: 12px;
  }
  
  .content-section {
    margin-bottom: 20px;
  }
  
  .features-section {
    margin-bottom: 20px;
  }
  
  .section-title {
    font-size: 18px;
  }
  
  .activities-list {
    max-height: 300px;
  }
  
  .action-item {
    padding: 8px 5px;
  }
  
  .action-icon {
    width: 38px;
    height: 38px;
    font-size: 18px;
  }
  
  .action-label {
    font-size: 13px;
  }
  
  .feature-card {
    padding: 15px;
  }
  
  .feature-icon {
    width: 60px;
    height: 60px;
    font-size: 28px;
  }
}

@media screen and (max-width: 1024px) {
  .stats-section {
    margin-bottom: 18px;
  }
  
  .stat-content {
    height: 65px;
  }
  
  .stat-icon {
    width: 40px;
    height: 40px;
    font-size: 16px;
  }
  
  .stat-value {
    font-size: 16px;
  }
  
  .stat-label {
    font-size: 12px;
  }
  
  .content-section {
    margin-bottom: 18px;
  }
  
  .features-section {
    margin-bottom: 18px;
  }
  
  .section-title {
    font-size: 16px;
  }
  
  .activities-list {
    max-height: 280px;
  }
  
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
  
  .action-item {
    padding: 10px 8px;
  }
  
  .action-label {
    font-size: 13px;
  }
  
  .feature-card {
    padding: 12px;
  }
  
  .feature-icon {
    width: 50px;
    height: 50px;
    font-size: 24px;
  }
  
  .feature-title {
    font-size: 14px;
  }
  
  .feature-description {
    font-size: 12px;
  }
}

@media screen and (max-width: 768px) {
  .stats-section {
    margin-bottom: 15px;
  }
  
  .stat-content {
    height: 60px;
  }
  
  .stat-icon {
    width: 35px;
    height: 35px;
    font-size: 14px;
  }
  
  .stat-value {
    font-size: 14px;
  }
  
  .stat-label {
    font-size: 11px;
  }
  
  .content-section {
    margin-bottom: 15px;
  }
  
  .features-section {
    margin-bottom: 15px;
  }
  
  .section-title {
    font-size: 16px;
    margin-bottom: 15px;
  }
  
  .activities-list {
    max-height: 250px;
  }
  
  .activity-item {
    padding: 10px 0;
  }
  
  .activity-icon {
    width: 28px;
    height: 28px;
  }
  
  .activity-description {
    font-size: 13px;
  }
  
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  
  .action-item {
    padding: 8px 5px;
  }
  
  .action-icon {
    width: 35px;
    height: 35px;
    font-size: 16px;
  }
  
  .action-label {
    font-size: 12px;
  }
  
  .feature-card {
    padding: 10px;
  }
  
  .feature-icon {
    width: 45px;
    height: 45px;
    font-size: 20px;
  }
  
  .feature-title {
    font-size: 13px;
  }
  
  .feature-description {
    font-size: 11px;
  }
}

@media screen and (max-width: 480px) {
  .stats-section {
    margin-bottom: 12px;
  }
  
  .stat-content {
    height: 55px;
  }
  
  .stat-icon {
    width: 30px;
    height: 30px;
    font-size: 12px;
  }
  
  .stat-value {
    font-size: 13px;
  }
  
  .stat-label {
    font-size: 10px;
  }
  
  .content-section {
    margin-bottom: 12px;
  }
  
  .features-section {
    margin-bottom: 12px;
  }
  
  .section-title {
    font-size: 14px;
    margin-bottom: 12px;
  }
  
  .activities-list {
    max-height: 200px;
  }
  
  .activity-item {
    padding: 8px 0;
  }
  
  .activity-icon {
    width: 24px;
    height: 24px;
  }
  
  .activity-description {
    font-size: 12px;
  }
  
  .activity-meta {
    font-size: 11px;
  }
  
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 6px;
  }
  
  .action-item {
    padding: 6px 3px;
  }
  
  .action-icon {
    width: 30px;
    height: 30px;
    font-size: 14px;
  }
  
  .action-label {
    font-size: 11px;
  }
  
  .feature-card {
    padding: 8px;
  }
  
  .feature-icon {
    width: 40px;
    height: 40px;
    font-size: 18px;
  }
  
  .feature-title {
    font-size: 12px;
  }
  
  .feature-description {
    font-size: 10px;
  }
}
</style>
