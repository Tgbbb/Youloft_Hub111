<template>
  <div class="ark-shell" data-ark-theme="endfield" data-ark-depth="moderate">
    <!-- ====== Top Bar ====== -->
    <header class="ark-topbar">
      <div class="ark-brand">
        <span class="ark-brand__mark" aria-hidden="true"></span>
        <span class="ark-brand__label">
          <strong>{{ $t('home.title') }}</strong>
          <small>{{ $t('home.subtitle') }}</small>
        </span>
      </div>

      <div class="ark-topbar__actions">
        <!-- Status indicator -->
        <span class="ark-status">
          <i class="ark-status__dot" aria-hidden="true"></i>
          <span class="ark-status__text">{{ $t('home.statusOnline') }}</span>
        </span>

        <!-- PC controls -->
        <div class="ark-actions-pc">
          <el-dropdown @command="handleLanguageChange" trigger="click">
            <span class="ark-action-btn">
              <span class="ark-action-btn__icon">{{ currentLanguage === 'zh-cn' ? 'CN' : 'EN' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="zh-cn" :disabled="currentLanguage === 'zh-cn'">
                  🇨🇳 {{ $t('home.language.zhCN') }}
                </el-dropdown-item>
                <el-dropdown-item command="en" :disabled="currentLanguage === 'en'">
                  🇺🇸 {{ $t('home.language.en') }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-dropdown @command="handleCommand" trigger="click">
            <span class="ark-action-btn">
              <el-avatar :size="26" :icon="UserFilled" />
              <span class="ark-action-btn__name">{{ userStore.user?.username || $t('home.user') }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">{{ $t('home.logout') }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <!-- Mobile controls -->
        <div class="ark-actions-mobile">
          <el-dropdown trigger="click" @command="handleHeaderCommand">
            <span class="ark-action-btn">
              <el-avatar :size="22" :icon="UserFilled" />
              <span class="ark-action-btn__lang">{{ currentLanguage === 'zh-cn' ? 'CN' : 'EN' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="zh-cn" :disabled="currentLanguage === 'zh-cn'">
                  🇨🇳 {{ $t('home.language.zhCN') }}
                </el-dropdown-item>
                <el-dropdown-item command="en" :disabled="currentLanguage === 'en'">
                  🇺🇸 {{ $t('home.language.en') }}
                </el-dropdown-item>
                <el-dropdown-item command="logout" divided>
                  {{ $t('home.logout') }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </header>

    <!-- ====== Stage ====== -->
    <main class="ark-stage">
      <!-- Grid background layer -->
      <div class="ark-stage__grid" aria-hidden="true"></div>

      <!-- Hero title block -->
      <div class="ark-hero">
        <p class="ark-hero__kicker">PORTAL / MODULES</p>
        <h1 class="ark-hero__title">{{ $t('home.title') }}</h1>
        <p class="ark-hero__desc">{{ $t('home.subtitle') }}</p>
        <span class="ark-hero__rule" aria-hidden="true"></span>
      </div>

      <!-- Module cards -->
      <div class="ark-cards">
        <button
          v-for="(card, idx) in cards"
          :key="card.type"
          class="ark-card"
          :class="`ark-card--${card.type}`"
          @click="handleNavigate(card.type)"
        >
          <span class="ark-card__index">{{ String(idx + 1).padStart(2, '0') }}</span>
          <span class="ark-card__wedge" aria-hidden="true"></span>
          <div class="ark-card__body">
            <span class="ark-card__icon"><el-icon><component :is="card.icon" /></el-icon></span>
            <h3 class="ark-card__title">{{ card.title }}</h3>
            <p class="ark-card__desc">{{ card.desc }}</p>
          </div>
          <span class="ark-card__action">
            <span class="ark-card__arrow" aria-hidden="true">→</span>
          </span>
        </button>
      </div>
    </main>

    <!-- ====== Bottom Dock ====== -->
    <footer class="ark-dock" aria-label="System status">
      <span class="ark-dock__code">SYS / ONLINE</span>
      <span class="ark-dock__rule" aria-hidden="true"></span>
      <span class="ark-dock__label">ROUTE VERIFIED</span>
      <span class="ark-dock__state" :data-online="true">●</span>
    </footer>

    <!-- Mobile tip dialog (unchanged logic) -->
    <el-dialog
      v-model="mobileDialogVisible"
      class="mobile-tip-dialog"
      :title="$t('home.mobileTipTitle')"
      width="88%"
      align-center
      :close-on-click-modal="true"
      append-to-body
    >
      <div class="mobile-tip-dialog-body">
        <div class="dialog-icon-wrap">
          <el-icon><Monitor /></el-icon>
        </div>
        <p class="dialog-desc">{{ $t('home.mobileTipDesc') }}</p>
      </div>
      <template #footer>
        <el-button type="primary" class="dialog-confirm-btn" @click="mobileDialogVisible = false">
          {{ $t('home.mobileTipOk') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import { track } from '@/utils/tracker'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  MagicStick, Link, Monitor, DataLine, Cpu, Setting,
  ChatDotRound, UserFilled, ArrowDown, Cellphone,
} from '@element-plus/icons-vue'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const appStore = useAppStore()

const currentLanguage = computed(() => appStore.language)
const isMobile = ref(false)
const mobileTipDismissed = ref(false)
const MOBILE_BREAKPOINT = 768
const MOBILE_TIP_STORAGE_KEY = 'testhub_home_mobile_tip_seen'

const cards = [
  { type: 'ai', icon: MagicStick, title: t('home.aiCaseGeneration'), desc: t('home.aiCaseGenerationDesc') },
  { type: 'api', icon: Link, title: t('home.apiTesting'), desc: t('home.apiTestingDesc') },
  { type: 'ui', icon: Monitor, title: t('home.uiAutomation'), desc: t('home.uiAutomationDesc') },
  { type: 'data', icon: DataLine, title: t('home.dataFactory'), desc: t('home.dataFactoryDesc') },
  { type: 'app', icon: Cellphone, title: 'APP自动化测试', desc: '基于Airtest的Android APP自动化测试' },
  { type: 'ai-intelligent', icon: Cpu, title: t('home.aiIntelligentMode'), desc: t('home.aiIntelligentModeDesc') },
  { type: 'assistant', icon: ChatDotRound, title: t('home.aiEvaluator'), desc: t('home.aiEvaluatorDesc') },
  { type: 'config', icon: Setting, title: t('home.configCenter'), desc: t('home.configCenterDesc') },
]

const dismissMobileTip = () => {
  mobileTipDismissed.value = true
  try { localStorage.setItem(MOBILE_TIP_STORAGE_KEY, '1') } catch { /* ignore */ }
}

const mobileDialogVisible = computed({
  get: () => isMobile.value && !mobileTipDismissed.value,
  set: (val) => { if (!val) dismissMobileTip() },
})

const updateMobileTip = () => {
  isMobile.value = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`).matches
}

onMounted(() => {
  try { if (localStorage.getItem(MOBILE_TIP_STORAGE_KEY) === '1') mobileTipDismissed.value = true } catch { /* ignore */ }
  updateMobileTip()
  window.addEventListener('resize', updateMobileTip)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateMobileTip)
})

const handleLanguageChange = (lang) => { appStore.setLanguage(lang) }
const handleCommand = (command) => { if (command === 'logout') handleLogout() }

const handleHeaderCommand = (command) => {
  if (command === 'logout') { handleLogout(); return }
  if (command === 'zh-cn' || command === 'en') appStore.setLanguage(command)
}

const handleLogout = () => {
  ElMessageBox.confirm(t('home.logoutConfirm'), t('common.tips'), {
    confirmButtonText: t('common.confirm'),
    cancelButtonText: t('common.cancel'),
    type: 'warning',
  }).then(() => {
    userStore.logout()
    router.push('/login')
    ElMessage.success(t('home.logoutSuccess'))
  }).catch(() => {})
}

const handleNavigate = (type) => {
  const routes = {
    'ai': '/ai-generation/requirement-analysis',
    'api': '/api-testing/dashboard',
    'ui': '/ui-automation/dashboard',
    'app': '/app-automation/dashboard',
    'ai-intelligent': '/ai-intelligent-mode/testing',
    'assistant': '/ai-generation/assistant',
    'config': '/configuration/ai-model',
    'data': '/data-factory',
  }
  if (routes[type]) {
    track('module_card_click', {
      event_type: 'click', module: 'home', page_path: '/home',
      target_path: routes[type], metadata: { card_type: type },
    })
    const routeData = router.resolve({ path: routes[type] })
    window.open(routeData.href, '_blank')
  }
}
</script>

<style scoped lang="scss">
/* =============================================
   Endfield Moderate — Homepage Shell
   ============================================= */

/* ---- CSS Custom Properties (scoped fallback) ---- */
.ark-shell {
  --ark-ink: #191919;
  --ark-paper: #f2f2f0;
  --ark-signal: #fffa00;
  --ark-state: #00ffa2;
  --ark-neutral-200: #e8e8e4;
  --ark-neutral-300: #c4c4be;
  --ark-neutral-500: #7a7a72;
  --ark-neutral-700: #3d3d38;
  --ark-topbar-h: 56px;
  --ark-dock-h: 36px;
  --font-cjk: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-tech: "Space Grotesk", "IBM Plex Sans", system-ui, -apple-system, sans-serif;

  min-height: 100vh;
  background: var(--ark-paper);
  font-family: var(--font-cjk);
  color: var(--ark-ink);
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
}

/* ---- Top Bar ---- */
.ark-topbar {
  height: var(--ark-topbar-h);
  background: var(--ark-ink);
  color: var(--ark-paper);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 100;
  flex-shrink: 0;
}

.ark-brand {
  display: flex;
  align-items: center;
  gap: 12px;

  &__mark {
    width: 8px;
    height: 28px;
    background: var(--ark-signal);
    flex-shrink: 0;
    clip-path: polygon(0 0, 100% 0, 100% 55%, 60% 100%, 0 100%);
  }

  &__label {
    display: flex;
    flex-direction: column;
    line-height: 1.15;

    strong {
      font-size: 15px;
      font-weight: 700;
      letter-spacing: .04em;
      font-family: var(--font-cjk);
    }

    small {
      font-size: 10px;
      font-family: var(--font-tech);
      text-transform: uppercase;
      letter-spacing: .14em;
      color: var(--ark-neutral-500);
    }
  }
}

.ark-topbar__actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ark-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-family: var(--font-tech);
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--ark-neutral-500);

  &__dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--ark-state);
    flex-shrink: 0;
  }
}

.ark-actions-pc {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ark-actions-mobile {
  display: none;
}

.ark-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--ark-neutral-300);
  font-size: 13px;
  font-family: var(--font-tech);
  letter-spacing: .06em;
  text-transform: uppercase;
  padding: 4px 8px;
  border-radius: 2px;
  transition: color .2s, background .2s;
  user-select: none;

  &:hover {
    color: var(--ark-paper);
    background: rgba(255, 255, 255, .06);
  }

  &__icon {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .1em;
  }

  &__name {
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__lang {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .1em;
  }
}

/* ---- Stage ---- */
.ark-stage {
  flex: 1;
  position: relative;
  padding: 48px 24px 24px;
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
}

/* Grid background layer */
.ark-stage__grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background-image:
    linear-gradient(to right, var(--ark-neutral-200) 1px, transparent 1px),
    linear-gradient(to bottom, var(--ark-neutral-200) 1px, transparent 1px);
  background-size: 80px 80px;
  opacity: .5;
}

/* ---- Hero ---- */
.ark-hero {
  position: relative;
  z-index: 1;
  margin-bottom: 48px;
  padding-bottom: 24px;

  &__kicker {
    font-size: 11px;
    font-family: var(--font-tech);
    text-transform: uppercase;
    letter-spacing: .16em;
    color: var(--ark-neutral-500);
    margin: 0 0 12px;
  }

  &__title {
    font-size: 3.2rem;
    font-weight: 900;
    line-height: .92;
    letter-spacing: -.03em;
    margin: 0 0 8px;
    color: var(--ark-ink);
    font-family: var(--font-cjk);
  }

  &__desc {
    font-size: 1rem;
    color: var(--ark-neutral-700);
    margin: 0;
    font-family: var(--font-tech);
    letter-spacing: .02em;
  }

  &__rule {
    display: block;
    width: 64px;
    height: 3px;
    background: var(--ark-signal);
    margin-top: 20px;
    clip-path: polygon(0 0, 100% 0, 92% 100%, 0 100%);
  }
}

/* ---- Cards Grid ---- */
.ark-cards {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--ark-neutral-200);
  border: 1px solid var(--ark-neutral-200);

  @media (max-width: 1024px) {
    grid-template-columns: repeat(3, 1fr);
  }

  @media (max-width: 768px) {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* ---- Card ---- */
.ark-card {
  all: unset;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  text-align: left;
  background: #ffffff;
  padding: 28px 24px 24px;
  cursor: pointer;
  position: relative;
  transition: background .2s;
  min-height: 180px;

  &:hover {
    background: var(--ark-paper);
  }

  &:focus-visible {
    outline: 2px solid var(--ark-signal);
    outline-offset: -2px;
    z-index: 2;
  }

  &__index {
    position: absolute;
    top: 12px;
    right: 16px;
    font-size: 2.4rem;
    font-weight: 900;
    font-family: var(--font-tech);
    color: var(--ark-neutral-200);
    line-height: 1;
    letter-spacing: -.04em;
    transition: color .2s;
  }

  &:hover &__index {
    color: var(--ark-neutral-300);
  }

  &__wedge {
    position: absolute;
    top: 0;
    left: 0;
    width: 0;
    height: 0;
    border-style: solid;
    border-width: 14px 14px 0 0;
    border-color: var(--ark-neutral-200) transparent transparent transparent;
    transition: border-color .2s;
  }

  &:hover &__wedge {
    border-color: var(--ark-signal) transparent transparent transparent;
  }

  &__body {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
    margin-top: 8px;
  }

  &__icon {
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    color: var(--ark-ink);
    background: var(--ark-paper);
    margin-bottom: 4px;
  }

  &__title {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--ark-ink);
    margin: 0;
    line-height: 1.25;
    font-family: var(--font-cjk);
  }

  &__desc {
    font-size: .8rem;
    color: var(--ark-neutral-500);
    margin: 0;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  &__action {
    margin-top: auto;
    padding-top: 12px;
  }

  &__arrow {
    font-size: 14px;
    font-family: var(--font-tech);
    color: var(--ark-neutral-300);
    transition: color .2s, transform .2s;
    display: inline-block;
  }

  &:hover &__arrow {
    color: var(--ark-ink);
    transform: translateX(4px);
  }
}

/* ---- Bottom Dock ---- */
.ark-dock {
  height: var(--ark-dock-h);
  background: var(--ark-ink);
  color: var(--ark-neutral-500);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-family: var(--font-tech);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: .12em;
  flex-shrink: 0;

  &__code {
    color: var(--ark-paper);
  }

  &__rule {
    display: inline-block;
    width: 1px;
    height: 12px;
    background: var(--ark-neutral-700);
  }

  &__state {
    color: var(--ark-state);
    font-size: 8px;
    line-height: 1;

    &[data-online="true"] {
      color: var(--ark-state);
    }
  }
}

/* ---- Reveal Animation ---- */
@keyframes ark-card-enter {
  from {
    opacity: 0;
    clip-path: inset(0 0 100% 0);
  }
  to {
    opacity: 1;
    clip-path: inset(0 0 0 0);
  }
}

.ark-card {
  animation: ark-card-enter .45s ease-out both;

  @for $i from 1 through 8 {
    &:nth-child(#{$i}) {
      animation-delay: #{$i * .06}s;
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .ark-card {
    animation: none;
  }
}

/* ---- Responsive — Desktop tiers ---- */
@media (max-width: 1440px) {
  .ark-hero__title { font-size: 2.8rem; }
  .ark-stage { padding: 40px 20px 20px; }
  .ark-card { padding: 24px 20px 20px; min-height: 170px; }
  .ark-card__index { font-size: 2rem; }
}

@media (max-width: 1280px) {
  .ark-hero__title { font-size: 2.5rem; }
  .ark-hero { margin-bottom: 36px; }
  .ark-card { padding: 22px 18px 18px; min-height: 160px; }
  .ark-card__index { font-size: 1.8rem; }
}

/* ---- Portrait / Mobile ---- */
@media (max-width: 768px) {
  .ark-topbar {
    padding: 0 16px;
    --ark-topbar-h: 48px;
  }

  .ark-brand__label strong { font-size: 13px; }
  .ark-brand__label small { display: none; }
  .ark-brand__mark { height: 22px; width: 6px; }

  .ark-status { display: none; }
  .ark-actions-pc { display: none; }
  .ark-actions-mobile { display: flex; }

  .ark-stage {
    padding: 28px 12px 16px;
  }

  .ark-hero {
    margin-bottom: 28px;
    padding-bottom: 16px;

    &__kicker { font-size: 10px; }
    &__title { font-size: 1.8rem; }
    &__desc { font-size: .85rem; }
    &__rule { width: 48px; height: 2px; margin-top: 14px; }
  }

  .ark-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .ark-card {
    min-height: 144px;
    padding: 20px 14px 16px;

    &__index { font-size: 1.5rem; top: 10px; right: 12px; }
    &__title { font-size: .95rem; }
    &__desc { font-size: .75rem; -webkit-line-clamp: 2; }
    &__icon { width: 36px; height: 36px; font-size: 20px; }
    &__wedge { border-width: 10px 10px 0 0; }
  }

  .ark-dock {
    --ark-dock-h: 30px;
    font-size: 9px;
    gap: 8px;
  }
}

@media (max-width: 480px) {
  .ark-topbar {
    padding: 0 12px;
  }

  .ark-stage {
    padding: 20px 10px 12px;
  }

  .ark-hero__title { font-size: 1.5rem; }

  .ark-card {
    min-height: 130px;
    padding: 16px 10px 14px;

    &__index { font-size: 1.3rem; top: 8px; right: 10px; }
    &__title { font-size: .88rem; }
    &__desc { font-size: .72rem; }
    &__icon { width: 32px; height: 32px; font-size: 18px; }
  }
}
</style>

<!-- Unscoped: Element Plus dialog overrides (same as before) -->
<style lang="scss">
.mobile-tip-dialog.el-dialog {
  max-width: 340px;
  border-radius: 4px;
  overflow: hidden;

  .el-dialog__header {
    padding: 20px 20px 8px;
    margin-right: 0;
    text-align: center;

    .el-dialog__title {
      font-size: 17px;
      font-weight: 600;
      color: var(--ark-ink, #191919);
      line-height: 1.4;
    }

    .el-dialog__headerbtn {
      top: 14px;
      right: 14px;
    }
  }

  .el-dialog__body {
    padding: 4px 24px 8px;
  }

  .el-dialog__footer {
    padding: 8px 20px 20px;

    .dialog-confirm-btn {
      width: 100%;
      height: 40px;
      border-radius: 2px;
      font-size: 15px;
    }
  }
}

.mobile-tip-dialog-body {
  text-align: center;

  .dialog-icon-wrap {
    width: 56px;
    height: 56px;
    margin: 0 auto 14px;
    border-radius: 2px;
    background: #f2f2f0;
    color: var(--ark-ink, #191919);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
  }

  .dialog-desc {
    margin: 0;
    font-size: 14px;
    color: #3d3d38;
    line-height: 1.6;
  }
}
</style>
