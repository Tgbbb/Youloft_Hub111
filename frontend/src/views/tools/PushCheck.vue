<template>
  <div class="pc-page" data-ark-theme="endfield" data-ark-depth="moderate">
    <!-- ===== Header / stage title ===== -->
    <header class="pc-header">
      <div class="pc-header__titleblock">
        <p class="pc-kicker">TESTHUB / TOOLBOX / PUSH CHECK</p>
        <div class="pc-header__row">
          <h1 class="pc-title">推送对比</h1>
          <span class="pc-header__index" aria-hidden="true">01</span>
        </div>
        <span class="pc-header__rule" aria-hidden="true"></span>
        <p class="pc-header__desc">
          自动监听推送排期邮件，与推送后台逐项对比（标题 / 描述 / 链接 / 地区 / 推送目标 / 版本类别）。
          全部通过则自动把推送时间改为当前时间（立即触发测试），发现问题则不修改，等待人工确认。
        </p>
      </div>

      <div class="pc-runstate" aria-live="polite">
        <p class="pc-runstate__kicker">RUN STATE</p>
        <div class="pc-runstate__value" :class="`is-${stateKey(currentRun?.status)}`">
          <span class="pc-runstate__dot" aria-hidden="true"></span>
          <span>{{ currentRun ? statusText(currentRun.status) : 'STANDBY' }}</span>
        </div>
        <div v-if="currentRun && currentRun.summary" class="pc-runstate__counts">
          <span><b>{{ currentRun.summary.problems ?? 0 }}</b> 问题</span>
          <span><b>{{ currentRun.summary.edited ?? 0 }}</b> 修改</span>
          <span><b>{{ currentRun.summary.skipped ?? 0 }}</b> 跳过</span>
        </div>
        <div v-else class="pc-runstate__counts">
          <span>未运行</span>
        </div>
      </div>
    </header>

    <!-- ===== Stage: config + run columns ===== -->
    <div class="pc-stage">
      <!-- Config panel -->
      <section class="pc-panel pc-panel--cfg" aria-labelledby="cfg-title">
        <header class="pc-panel__head">
          <span class="pc-panel__code">CFG / 01</span>
          <h2 id="cfg-title">工具配置</h2>
          <span class="pc-panel__meta">IMAP · BACKEND · OCR</span>
        </header>

        <form class="pc-form" @submit.prevent="saveConfig">
          <fieldset class="pc-fieldset">
            <legend class="pc-fieldset__legend">IMAP 邮箱</legend>
            <div class="pc-field pc-field--half">
              <label class="pc-field__label" for="f-host">服务器</label>
              <input id="f-host" v-model="form.imap_host" class="pc-input" type="text" autocomplete="off" />
            </div>
            <div class="pc-field pc-field--num">
              <label class="pc-field__label" for="f-port">端口</label>
              <input id="f-port" v-model.number="form.imap_port" class="pc-input pc-input--num" type="number" min="1" max="65535" />
            </div>
            <div class="pc-field pc-field--half">
              <label class="pc-field__label" for="f-user">账号</label>
              <input id="f-user" v-model="form.imap_user" class="pc-input" type="text" autocomplete="off" />
            </div>
            <div class="pc-field pc-field--half">
              <label class="pc-field__label" for="f-pass">密码</label>
              <div class="pc-input-wrap">
                <input id="f-pass" v-model="form.imap_password" class="pc-input" :type="showPassword ? 'text' : 'password'" placeholder="留空表示不修改" autocomplete="new-password" />
                <button type="button" class="pc-reveal" :aria-pressed="showPassword" @click="showPassword = !showPassword">
                  {{ showPassword ? '隐藏' : '显示' }}
                </button>
              </div>
            </div>
            <div class="pc-field pc-field--num">
              <label class="pc-field__label" for="f-timeout">超时(秒)</label>
              <input id="f-timeout" v-model.number="form.imap_timeout" class="pc-input pc-input--num" type="number" min="1" max="300" />
            </div>
          </fieldset>

          <fieldset class="pc-fieldset">
            <legend class="pc-fieldset__legend">推送后台</legend>
            <div class="pc-field pc-field--half">
              <label class="pc-field__label" for="f-bhost">后台地址</label>
              <input id="f-bhost" v-model="form.backend_host" class="pc-input" type="text" autocomplete="off" />
            </div>
            <div class="pc-field pc-field--num">
              <label class="pc-field__label" for="f-bport">后台端口</label>
              <input id="f-bport" v-model.number="form.backend_port" class="pc-input pc-input--num" type="number" min="1" max="65535" />
            </div>
            <div class="pc-field pc-field--full">
              <label class="pc-field__label" for="f-cookie">Cookie</label>
              <textarea id="f-cookie" v-model="form.push_cookie" class="pc-input pc-input--area" rows="3" placeholder="留空表示不修改（约 1 天过期，需定期更新）"></textarea>
            </div>
          </fieldset>

          <fieldset class="pc-fieldset">
            <legend class="pc-fieldset__legend">OCR（可选）</legend>
            <div class="pc-field pc-field--full">
              <label class="pc-field__label" for="f-tess">Tesseract 路径</label>
              <input id="f-tess" v-model="form.tesseract_path" class="pc-input" type="text" placeholder="留空自动探测（含 E:\ocr\tesseract.exe）" autocomplete="off" />
            </div>
          </fieldset>

          <footer class="pc-panel__foot">
            <button class="pc-btn pc-btn--primary" type="submit" :disabled="saving">
              <span class="pc-btn__bar" aria-hidden="true"></span>
              {{ saving ? '保存中...' : '保存配置' }}
            </button>
            <button class="pc-btn" type="button" @click="loadConfig">重新加载</button>
            <span class="pc-foot-msg" :class="`is-${configMessageType}`" aria-live="polite">{{ configMessage }}</span>
          </footer>
        </form>
      </section>

      <!-- Run + history column -->
      <div class="pc-maincol">
        <section class="pc-panel pc-panel--run" aria-labelledby="run-title">
          <header class="pc-panel__head">
            <span class="pc-panel__code">RUN / 02</span>
            <h2 id="run-title">运行</h2>
            <span class="pc-panel__meta">FORCE OPTIONAL</span>
          </header>

          <div class="pc-runbar">
            <label class="pc-toggle" :class="{ 'is-on': force }">
              <input v-model="force" class="pc-toggle__input" type="checkbox" role="switch" :disabled="running" />
              <span class="pc-toggle__track" aria-hidden="true"><span class="pc-toggle__thumb"></span></span>
              <span class="pc-toggle__label">强制重查（忽略已处理记录）</span>
            </label>
            <button class="pc-btn pc-btn--run" type="button" :disabled="running" @click="startRun">
              <span class="pc-btn__bar" aria-hidden="true"></span>
              <span>{{ running ? '检查中...' : '开始检查' }}</span>
            </button>
          </div>

          <div v-if="currentRun && currentRun.summary" class="pc-summary">
            <span class="pc-summary__item"><i>STATUS</i><b>{{ currentRun.summary.message }}</b></span>
            <span v-if="currentRun.summary.email_subject" class="pc-summary__item pc-summary__item--mail">
              <i>MAIL</i><b>{{ currentRun.summary.email_subject }}</b>
            </span>
          </div>

          <div class="pc-log">
            <div class="pc-log__code">
              <span>RUN / LOG</span>
              <span class="pc-log__live" :class="{ 'is-on': running }" aria-hidden="true"></span>
            </div>
            <pre class="pc-log__body" tabindex="0">{{ currentRun?.log || (running ? '等待任务输出...' : '尚未运行，点击「开始检查」触发一次对比。') }}</pre>
          </div>
        </section>

        <section class="pc-panel pc-panel--history" aria-labelledby="history-title">
          <header class="pc-panel__head">
            <span class="pc-panel__code">ARCHIVE / 03</span>
            <h2 id="history-title">运行历史</h2>
            <span class="pc-panel__meta">RECENT RUNS</span>
          </header>

          <div class="pc-table-wrap">
            <table class="pc-table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">状态</th>
                  <th scope="col">结果</th>
                  <th scope="col">邮件</th>
                  <th scope="col">发起人</th>
                  <th scope="col">开始时间</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in runs" :key="row.id">
                  <td class="pc-table__id">{{ row.id }}</td>
                  <td>
                    <span class="pc-status" :class="`is-${stateKey(row.status)}`">
                      <i class="pc-status__dot" aria-hidden="true"></i>{{ statusText(row.status) }}
                    </span>
                  </td>
                  <td class="pc-table__cell pc-table__ellipsis" :title="row.summary?.message || '-'">{{ row.summary?.message || '-' }}</td>
                  <td class="pc-table__cell pc-table__ellipsis" :title="row.summary?.email_subject || '-'">{{ row.summary?.email_subject || '-' }}</td>
                  <td class="pc-table__cell">{{ row.username || '-' }}</td>
                  <td class="pc-table__cell pc-table__mono">{{ formatTime(row.started_at) }}</td>
                  <td class="pc-table__cell">
                    <button class="pc-link" type="button" @click="viewRun(row.id)">查看</button>
                  </td>
                </tr>
                <tr v-if="runs.length === 0">
                  <td class="pc-table__empty" colspan="7">暂无运行记录</td>
                </tr>
              </tbody>
            </table>
          </div>

          <nav v-if="total > pageSize" class="pc-pager" aria-label="运行历史分页">
            <button class="pc-pager__btn" type="button" :disabled="page <= 1" @click="loadRuns(page - 1)">‹</button>
            <button
              v-for="p in pageCount"
              :key="p"
              class="pc-pager__btn"
              :class="{ 'is-active': p === page }"
              type="button"
              :aria-current="p === page ? 'page' : undefined"
              @click="loadRuns(p)"
            >{{ p }}</button>
            <button class="pc-pager__btn" type="button" :disabled="page >= pageCount" @click="loadRuns(page + 1)">›</button>
          </nav>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getPushCheckConfig,
  savePushCheckConfig,
  triggerPushCheck,
  getPushCheckRuns,
  getPushCheckRun
} from '@/api/tools'

const form = ref({
  imap_host: '',
  imap_port: 993,
  imap_user: '',
  imap_password: '',
  imap_timeout: 20,
  backend_host: '',
  backend_port: 8015,
  push_cookie: '',
  tesseract_path: ''
})

const showPassword = ref(false)
const saving = ref(false)
const configMessage = ref('')
const configMessageType = ref('success')

const force = ref(false)
const running = ref(false)
const currentRun = ref(null)

const runs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10

let pollTimer = null

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const loadConfig = async () => {
  try {
    const response = await getPushCheckConfig()
    const data = response.data
    form.value = {
      imap_host: data.imap_host,
      imap_port: data.imap_port,
      imap_user: data.imap_user,
      imap_password: '',
      imap_timeout: data.imap_timeout,
      backend_host: data.backend_host,
      backend_port: data.backend_port,
      push_cookie: '',
      tesseract_path: data.tesseract_path
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '配置加载失败')
  }
}

const saveConfig = async () => {
  saving.value = true
  configMessage.value = ''
  try {
    const response = await savePushCheckConfig(form.value)
    const data = response.data
    form.value = {
      imap_host: data.imap_host,
      imap_port: data.imap_port,
      imap_user: data.imap_user,
      imap_password: '',
      imap_timeout: data.imap_timeout,
      backend_host: data.backend_host,
      backend_port: data.backend_port,
      push_cookie: '',
      tesseract_path: data.tesseract_path
    }
    configMessage.value = '配置已保存'
    configMessageType.value = 'success'
    ElMessage.success('配置已保存')
  } catch (error) {
    configMessage.value = error.response?.data?.error || '配置保存失败'
    configMessageType.value = 'error'
    ElMessage.error(configMessage.value)
  } finally {
    saving.value = false
  }
}

const startRun = async () => {
  running.value = true
  currentRun.value = null
  try {
    const response = await triggerPushCheck({ force: force.value })
    currentRun.value = response.data
    pollRun(currentRun.value.id)
    await loadRuns()
  } catch (error) {
    running.value = false
    ElMessage.error(error.response?.data?.error || '触发失败')
  }
}

const pollRun = async (id) => {
  clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const response = await getPushCheckRun(id)
      currentRun.value = response.data
      if (response.data.status === 'success' || response.data.status === 'failed') {
        running.value = false
        clearInterval(pollTimer)
        pollTimer = null
        await loadRuns()
      }
    } catch (error) {
      running.value = false
      clearInterval(pollTimer)
      pollTimer = null
      ElMessage.error(error.response?.data?.error || '运行状态获取失败')
    }
  }, 2000)
}

const loadRuns = async (targetPage = 1) => {
  page.value = targetPage
  try {
    const response = await getPushCheckRuns({ page: page.value, page_size: pageSize })
    runs.value = response.data.results || []
    total.value = response.data.count || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '历史记录加载失败')
  }
}

const viewRun = async (id) => {
  try {
    const response = await getPushCheckRun(id)
    currentRun.value = response.data
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '记录详情获取失败')
  }
}

const statusText = (status) => ({
  pending: '待执行',
  running: '执行中',
  success: '成功',
  failed: '失败'
}[status] || 'STANDBY')

const stateKey = (status) => ({
  pending: 'pending',
  running: 'running',
  success: 'success',
  failed: 'failed'
}[status] || 'idle')

const formatTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

onMounted(() => {
  loadConfig()
  loadRuns()
})

onUnmounted(() => {
  clearInterval(pollTimer)
})
</script>

<style lang="scss" scoped>
/* =============================================
   Endfield Moderate — Push Check
   ============================================= */
.pc-page {
  --ark-ink: #191919;
  --ark-paper: #f2f2f0;
  --ark-signal: #fffa00;

  --pc-ink: var(--ark-ink);
  --pc-paper: var(--ark-paper);
  --pc-panel: #ffffff;
  --pc-line: #deded9;
  --pc-line-strong: #b9b9b2;
  --pc-signal: var(--ark-signal);
  --pc-state: #00ffa2;
  --pc-state-ink: #0d7d4e;
  --pc-muted: #6f6f69;
  --pc-dark: #111111;
  --pc-mono: "Space Grotesk", "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  --pc-display: "Space Grotesk", "Arial Narrow", "DIN Condensed", sans-serif;

  padding: 28px 32px 48px;
  max-width: 1480px;
  margin: 0 auto;
  color: var(--pc-ink);
}

/* ---------- Header / stage title ---------- */
.pc-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 32px;
  margin-bottom: 28px;
  animation: pc-reveal .6s cubic-bezier(.22, .8, .2, 1) both;

  &__titleblock {
    min-width: 0;
  }

  &__row {
    display: flex;
    align-items: baseline;
    gap: 16px;
  }

  &__index {
    font-family: var(--pc-display);
    font-size: 15px;
    letter-spacing: .08em;
    color: var(--pc-line-strong);
  }
}

.pc-kicker {
  margin: 0 0 10px;
  font-family: var(--pc-mono);
  font-size: 11px;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--pc-muted);
}

.pc-title {
  margin: 0;
  font-size: clamp(30px, 4vw, 44px);
  line-height: .95;
  letter-spacing: -.03em;
  font-weight: 800;
}

.pc-header__rule {
  display: block;
  width: min(420px, 46vw);
  height: 1px;
  margin: 18px 0 14px;
  background: var(--pc-line-strong);
  position: relative;

  &::after {
    content: "";
    position: absolute;
    left: 0;
    top: -1px;
    width: 44px;
    height: 3px;
    background: var(--pc-signal);
    clip-path: polygon(0 0, 100% 0, 78% 100%, 0 100%);
  }
}

.pc-header__desc {
  margin: 0;
  max-width: 680px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--pc-muted);
}

/* ---------- Run state strip ---------- */
.pc-runstate {
  flex-shrink: 0;
  min-width: 216px;
  padding: 14px 18px;
  background: var(--pc-dark);
  color: #fff;
  border-left: 4px solid var(--pc-signal);
  animation: pc-reveal .6s cubic-bezier(.22, .8, .2, 1) .08s both;

  &__kicker {
    margin: 0 0 8px;
    font-family: var(--pc-mono);
    font-size: 9px;
    letter-spacing: .18em;
    color: rgba(255, 255, 255, .45);
  }

  &__value {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: .04em;

    &.is-idle { color: rgba(255, 255, 255, .55); }
    &.is-success { color: var(--pc-state); }
    &.is-failed { color: #ff7a5c; }
  }

  &__dot {
    width: 7px;
    height: 7px;
    background: rgba(255, 255, 255, .4);

    .is-success & { background: var(--pc-state); }
    .is-failed & { background: #ff7a5c; }
    .is-running & {
      background: var(--pc-signal);
      animation: pc-pulse 1.6s ease-in-out infinite;
    }
  }

  &__counts {
    display: flex;
    gap: 14px;
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, .12);
    font-size: 11px;
    color: rgba(255, 255, 255, .5);

    b {
      color: #fff;
      font-family: var(--pc-mono);
      font-weight: 600;
    }
  }
}

/* ---------- Stage grid ---------- */
.pc-stage {
  display: grid;
  grid-template-columns: minmax(320px, 5fr) minmax(0, 7fr);
  gap: 20px;
  align-items: start;
}

.pc-maincol {
  display: grid;
  gap: 20px;
  min-width: 0;
}

/* ---------- Technical panel ---------- */
.pc-panel {
  background: var(--pc-panel);
  border: 1px solid var(--pc-line);
  border-radius: 0;
  position: relative;
  animation: pc-reveal .6s cubic-bezier(.22, .8, .2, 1) both;

  &--cfg { animation-delay: .12s; }
  &--run { animation-delay: .18s; }
  &--history { animation-delay: .24s; }

  &::before {
    content: "";
    position: absolute;
    top: -1px;
    left: -1px;
    width: 14px;
    height: 14px;
    border-top: 3px solid var(--pc-signal);
    border-left: 3px solid var(--pc-signal);
    pointer-events: none;
  }

  &__head {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 12px 18px;
    border-bottom: 1px solid var(--pc-line);

    h2 {
      margin: 0;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: .02em;
    }
  }

  &__code {
    font-family: var(--pc-mono);
    font-size: 10px;
    letter-spacing: .14em;
    color: var(--pc-muted);
  }

  &__meta {
    margin-left: auto;
    font-family: var(--pc-mono);
    font-size: 9px;
    letter-spacing: .16em;
    text-transform: uppercase;
    color: var(--pc-line-strong);
  }

  &__foot {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 18px 18px;
    border-top: 1px solid var(--pc-line);
  }
}

/* ---------- Config form ---------- */
.pc-form {
  padding: 4px 18px 0;
}

.pc-fieldset {
  margin: 0;
  padding: 16px 0 14px;
  border: 0;
  border-bottom: 1px solid var(--pc-line);

  &:last-of-type { border-bottom: 0; }

  &__legend {
    padding: 0;
    font-family: var(--pc-mono);
    font-size: 10px;
    letter-spacing: .16em;
    text-transform: uppercase;
    color: var(--pc-muted);
    margin-bottom: 12px;
  }
}

.pc-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 12px;

  &--half { width: 100%; }
  &--num { width: 120px; }
  &--full { width: 100%; }

  &__label {
    font-size: 11px;
    color: var(--pc-muted);
    letter-spacing: .04em;
  }
}

.pc-input-wrap {
  position: relative;
}

.pc-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--pc-line-strong);
  border-radius: 0;
  background: var(--pc-paper);
  color: var(--pc-ink);
  font-size: 13px;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", sans-serif;
  transition: border-color .15s, box-shadow .15s;

  &--num {
    font-family: var(--pc-mono);
  }

  &--area {
    resize: vertical;
    line-height: 1.5;
  }

  &::placeholder {
    color: #9c9c95;
  }

  &:hover { border-color: var(--pc-ink); }

  &:focus-visible {
    outline: 2px solid var(--pc-signal);
    outline-offset: 2px;
    border-color: var(--pc-ink);
  }
}

.pc-reveal {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  padding: 4px 6px;
  border: 0;
  background: transparent;
  color: var(--pc-muted);
  font-size: 11px;
  cursor: pointer;

  &:hover { color: var(--pc-ink); }
  &:focus-visible {
    outline: 2px solid var(--pc-signal);
    outline-offset: 2px;
  }
}

/* ---------- Buttons ---------- */
.pc-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 18px;
  border: 1px solid var(--pc-ink);
  border-radius: 0;
  background: transparent;
  color: var(--pc-ink);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: .04em;
  cursor: pointer;
  overflow: hidden;
  transition: color .18s, background .18s, border-color .18s;

  &:hover:not(:disabled) {
    background: var(--pc-ink);
    color: #fff;
  }

  &:focus-visible {
    outline: 2px solid var(--pc-signal);
    outline-offset: 2px;
  }

  &:disabled {
    opacity: .5;
    cursor: not-allowed;
  }

  &__bar {
    width: 5px;
    height: 14px;
    background: var(--pc-signal);
    clip-path: polygon(0 0, 100% 0, 72% 100%, 0 100%);
    flex-shrink: 0;
  }

  &--primary {
    background: var(--pc-ink);
    color: #fff;

    .pc-btn__bar { background: var(--pc-signal); }

    &:hover:not(:disabled) {
      background: #2c2c2c;
    }
  }

  &--run {
    background: var(--pc-ink);
    color: #fff;
    padding: 0 22px;

    .pc-btn__bar { background: var(--pc-signal); }

    &:not(:disabled)::after {
      content: "";
      position: absolute;
      inset: 0;
      background: var(--pc-signal);
      transform: translateX(-101%);
      transition: transform .22s cubic-bezier(.22, .8, .2, 1);
      z-index: 0;
    }

    &:hover:not(:disabled)::after {
      transform: translateX(0);
    }

    &:hover:not(:disabled) {
      color: var(--pc-ink);
      .pc-btn__bar { background: var(--pc-ink); }
    }

    > span {
      position: relative;
      z-index: 1;
    }
  }
}

/* ---------- Toggle ---------- */
.pc-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;

  &__input {
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 38px;
    height: 18px;
    margin: 0;
    opacity: 0;
    cursor: pointer;
    z-index: 2;

    &:focus-visible + .pc-toggle__track {
      outline: 2px solid var(--pc-signal);
      outline-offset: 2px;
    }
  }

  &__track {
    position: relative;
    width: 38px;
    height: 18px;
    background: var(--pc-line-strong);
    border: 1px solid var(--pc-line-strong);
    transition: background .15s;
    flex-shrink: 0;
    pointer-events: none;
  }

  &__thumb {
    position: absolute;
    top: 1px;
    left: 1px;
    width: 14px;
    height: 14px;
    background: #fff;
    transition: left .15s;
  }

  &.is-on {
    .pc-toggle__track {
      background: var(--pc-ink);
      border-color: var(--pc-ink);
    }
    .pc-toggle__thumb {
      left: 21px;
      background: var(--pc-signal);
    }
  }

  &__label {
    font-size: 12px;
    color: var(--pc-muted);
  }
}

/* ---------- Run bar / summary ---------- */
.pc-runbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  background: var(--pc-paper);
  border-bottom: 1px solid var(--pc-line);
}

.pc-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--pc-line);
  background: #fbfbf9;

  &__item {
    display: flex;
    align-items: baseline;
    gap: 8px;
    min-width: 0;

    i {
      font-style: normal;
      font-family: var(--pc-mono);
      font-size: 9px;
      letter-spacing: .14em;
      color: var(--pc-line-strong);
    }

    b {
      font-size: 12px;
      font-weight: 600;
      color: var(--pc-ink);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  &__item--mail {
    max-width: 320px;
  }
}

/* ---------- Log ---------- */
.pc-log {
  margin: 0 18px 18px;
  border: 1px solid var(--pc-dark);
  background: var(--pc-dark);

  &__code {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, .14);
    font-family: var(--pc-mono);
    font-size: 10px;
    letter-spacing: .16em;
    color: rgba(255, 255, 255, .5);
  }

  &__live {
    width: 6px;
    height: 6px;
    background: rgba(255, 255, 255, .3);

    &.is-on {
      background: var(--pc-signal);
      animation: pc-pulse 1.6s ease-in-out infinite;
    }
  }

  &__body {
    margin: 0;
    max-height: 420px;
    min-height: 190px;
    overflow: auto;
    padding: 14px;
    color: #d9d9d4;
    font-family: var(--pc-mono);
    font-size: 12px;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-all;
    tab-size: 2;

    &:focus-visible {
      outline: 2px solid var(--pc-signal);
      outline-offset: -2px;
    }
  }
}

/* ---------- History table ---------- */
.pc-table-wrap {
  overflow-x: auto;
}

.pc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;

  th {
    padding: 10px 12px;
    text-align: left;
    font-family: var(--pc-mono);
    font-size: 9px;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: var(--pc-muted);
    background: var(--pc-paper);
    border-bottom: 1px solid var(--pc-line-strong);
    white-space: nowrap;
  }

  td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--pc-line);
    color: var(--pc-ink);
  }

  tbody tr {
    transition: background .12s;

    &:hover {
      background: #f7f7f4;
    }
  }

  &__id,
  &__mono {
    font-family: var(--pc-mono);
  }

  &__id { color: var(--pc-muted); }
  &__ellipsis {
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &__empty {
    padding: 28px 12px;
    text-align: center;
    color: var(--pc-muted);
  }
}

.pc-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  white-space: nowrap;

  &__dot {
    width: 6px;
    height: 6px;
    background: var(--pc-line-strong);
  }

  &.is-success { color: var(--pc-state-ink); .pc-status__dot { background: var(--pc-state-ink); } }
  &.is-failed { color: #b23a24; .pc-status__dot { background: #b23a24; } }
  &.is-running { color: var(--pc-ink); .pc-status__dot { background: var(--pc-signal); animation: pc-pulse 1.6s ease-in-out infinite; } }
  &.is-pending { color: var(--pc-muted); }
}

.pc-link {
  padding: 4px 6px;
  border: 0;
  background: transparent;
  color: var(--pc-ink);
  font-size: 12px;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;

  &:hover { color: var(--pc-state-ink); }
  &:focus-visible {
    outline: 2px solid var(--pc-signal);
    outline-offset: 2px;
  }
}

/* ---------- Pager ---------- */
.pc-pager {
  display: flex;
  gap: 6px;
  padding: 14px 18px;
  border-top: 1px solid var(--pc-line);

  &__btn {
    min-width: 32px;
    height: 32px;
    padding: 0 8px;
    border: 1px solid var(--pc-line-strong);
    border-radius: 0;
    background: transparent;
    color: var(--pc-ink);
    font-family: var(--pc-mono);
    font-size: 12px;
    cursor: pointer;
    transition: background .12s, color .12s;

    &:hover:not(:disabled) {
      background: var(--pc-ink);
      color: #fff;
    }

    &:focus-visible {
      outline: 2px solid var(--pc-signal);
      outline-offset: 2px;
    }

    &.is-active {
      background: var(--pc-ink);
      color: var(--pc-signal);
    }

    &:disabled {
      opacity: .4;
      cursor: not-allowed;
    }
  }
}

/* ---------- Foot message ---------- */
.pc-foot-msg {
  font-size: 12px;
  color: var(--pc-muted);

  &.is-error { color: #b23a24; }
  &.is-success { color: var(--pc-state-ink); }
}

/* ---------- Motion ---------- */
@keyframes pc-reveal {
  from {
    clip-path: inset(0 100% 0 0);
    transform: translateX(-12px);
    opacity: 0;
  }
  to {
    clip-path: inset(0);
    transform: none;
    opacity: 1;
  }
}

@keyframes pc-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .35; }
}

@media (prefers-reduced-motion: reduce) {
  .pc-header,
  .pc-panel,
  .pc-runstate {
    animation: none;
  }

  .pc-runstate__dot,
  .pc-log__live,
  .pc-status.is-running .pc-status__dot {
    animation: none;
  }

  .pc-btn--run:not(:disabled)::after {
    display: none;
  }
}

/* ---------- Responsive ---------- */
@media (max-width: 1024px) {
  .pc-stage {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px), (orientation: portrait) {
  .pc-page {
    padding: 20px 16px 36px;
  }

  .pc-header {
    flex-direction: column;
    align-items: stretch;
    gap: 20px;
  }

  .pc-runstate {
    min-width: 0;
  }

  .pc-runbar {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .pc-btn--run {
    justify-content: center;
  }

  .pc-panel__head {
    flex-wrap: wrap;
  }

  .pc-panel__meta {
    margin-left: 0;
    width: 100%;
  }
}
</style>
