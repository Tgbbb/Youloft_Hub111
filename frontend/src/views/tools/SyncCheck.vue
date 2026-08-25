<template>
  <div class="sc-page" data-ark-theme="endfield" data-ark-depth="moderate">
    <!-- ===== Header / stage title ===== -->
    <header class="sc-header">
      <div class="sc-header__titleblock">
        <p class="sc-kicker">TESTHUB / TOOLBOX / SYNC CHECK</p>
        <div class="sc-header__row">
          <h1 class="sc-title">同步确认</h1>
          <span class="sc-header__index" aria-hidden="true">02</span>
        </div>
        <span class="sc-header__rule" aria-hidden="true"></span>
        <p class="sc-header__desc">
          推送完成后，配置人员会回复一封「已同步至线上」邮件（含配置截图）。定时监听该邮件并 OCR
          识别推送目标 / 推送标题 / 推送内容 / 安卓版本 / IOS版本，与推送后台实时记录逐项对比；
          当天截止时间前未收到邮件或对比不一致时标记异常。
        </p>
      </div>

      <div class="sc-runstate" aria-live="polite">
        <p class="sc-runstate__kicker">TODAY STATUS</p>
        <div class="sc-runstate__value" :class="`is-${stateKey(today?.status)}`">
          <span class="sc-runstate__dot" aria-hidden="true"></span>
          <span>{{ today ? statusText(today.status) : 'STANDBY' }}</span>
        </div>
        <div v-if="today && today.diffs && today.diffs.length" class="sc-runstate__counts">
          <span><b>{{ today.diffs.length }}</b> 项差异</span>
        </div>
        <div v-else-if="today && today.mail_subject" class="sc-runstate__counts">
          <span class="sc-runstate__mail">{{ today.mail_subject }}</span>
        </div>
        <div v-else class="sc-runstate__counts">
          <span>等待监听</span>
        </div>
      </div>
    </header>

    <!-- ===== Stage ===== -->
    <div class="sc-stage">
      <!-- Config panel -->
      <section class="sc-panel sc-panel--cfg" aria-labelledby="sc-cfg-title">
        <header class="sc-panel__head">
          <span class="sc-panel__code">CFG / 01</span>
          <h2 id="sc-cfg-title">监听配置</h2>
          <span class="sc-panel__meta">INTERVAL · DEADLINE · MAIL</span>
        </header>

        <form class="sc-form" @submit.prevent="saveConfig">
          <div class="sc-field sc-field--full">
            <label class="sc-toggle" :class="{ 'is-on': form.enabled }">
              <input v-model="form.enabled" class="sc-toggle__input" type="checkbox" role="switch" />
              <span class="sc-toggle__track" aria-hidden="true"><span class="sc-toggle__thumb"></span></span>
              <span class="sc-toggle__label">启用自动监听</span>
            </label>
          </div>
          <div class="sc-field sc-field--full">
            <label class="sc-toggle" :class="{ 'is-on': form.require_push_activity }">
              <input v-model="form.require_push_activity" class="sc-toggle__input" type="checkbox" role="switch" />
              <span class="sc-toggle__track" aria-hidden="true"><span class="sc-toggle__thumb"></span></span>
              <span class="sc-toggle__label">当天无推送活动时跳过监听（不报超时）</span>
            </label>
          </div>
          <div class="sc-field sc-field--full">
            <label class="sc-toggle" :class="{ 'is-on': form.enable_dingtalk_notify }">
              <input v-model="form.enable_dingtalk_notify" class="sc-toggle__input" type="checkbox" role="switch" />
              <span class="sc-toggle__track" aria-hidden="true"><span class="sc-toggle__thumb"></span></span>
              <span class="sc-toggle__label">钉钉通知（异常时发送）</span>
            </label>
            <p class="sc-field__note">对比不一致或超时未收到时，通过「统一通知配置」中的钉钉机器人推送</p>
          </div>

          <div class="sc-field sc-field--num">
            <label class="sc-field__label" for="sc-interval">检查间隔(分钟)</label>
            <input id="sc-interval" v-model.number="form.interval_minutes" class="sc-input sc-input--num" type="number" min="1" max="1440" />
          </div>
          <div class="sc-field sc-field--num">
            <label class="sc-field__label" for="sc-deadline">当天截止时间</label>
            <input id="sc-deadline" v-model="form.deadline_time" class="sc-input" type="text" placeholder="18:30" maxlength="5" />
          </div>
          <div class="sc-field sc-field--full">
            <label class="sc-field__label" for="sc-subject">邮件标题关键词</label>
            <input id="sc-subject" v-model="form.mail_subject" class="sc-input" type="text" autocomplete="off" />
          </div>
          <div class="sc-field sc-field--full">
            <label class="sc-field__label" for="sc-body">正文关键词</label>
            <input id="sc-body" v-model="form.mail_body_keyword" class="sc-input" type="text" autocomplete="off" />
          </div>

          <footer class="sc-panel__foot">
            <button class="sc-btn sc-btn--primary" type="submit" :disabled="saving">
              <span class="sc-btn__bar" aria-hidden="true"></span>
              {{ saving ? '保存中...' : '保存配置' }}
            </button>
            <button class="sc-btn" type="button" @click="loadConfig">重新加载</button>
            <span class="sc-foot-msg" :class="`is-${configMessageType}`" aria-live="polite">{{ configMessage }}</span>
          </footer>
        </form>
      </section>

      <!-- Run + history column -->
      <div class="sc-maincol">
        <section class="sc-panel sc-panel--run" aria-labelledby="sc-run-title">
          <header class="sc-panel__head">
            <span class="sc-panel__code">RUN / 02</span>
            <h2 id="sc-run-title">检查</h2>
            <span class="sc-panel__meta">MANUAL TRIGGER</span>
          </header>

          <div class="sc-runbar">
            <button class="sc-btn sc-btn--run" type="button" :disabled="running" @click="startRun(false)">
              <span class="sc-btn__bar" aria-hidden="true"></span>
              <span>{{ running ? '检查中...' : '立即检查' }}</span>
            </button>
            <button class="sc-btn" type="button" :disabled="running" @click="startRun(true)">
              强制重新对比
            </button>
            <span class="sc-runbar__hint">自动监听每 {{ form.interval_minutes || 15 }} 分钟一次，截止 {{ form.deadline_time || '18:30' }}</span>
          </div>

          <div v-if="today && today.message" class="sc-summary">
            <span class="sc-summary__item"><i>STATUS</i><b>{{ today.message }}</b></span>
          </div>
          <div v-if="today && today.diffs && today.diffs.length" class="sc-diffs">
            <p class="sc-diffs__title">DIFFS / {{ today.diffs.length }}</p>
            <ul>
              <li v-for="(d, i) in today.diffs" :key="i">{{ d }}</li>
            </ul>
          </div>

          <div class="sc-log">
            <div class="sc-log__code">
              <span>SYNC / LOG</span>
              <span class="sc-log__live" :class="{ 'is-on': running }" aria-hidden="true"></span>
            </div>
            <pre class="sc-log__body" tabindex="0">{{ today?.log || (running ? '等待任务输出...' : '尚未执行检查，等待定时监听或点击「立即检查」。') }}</pre>
          </div>
        </section>

        <section class="sc-panel sc-panel--history" aria-labelledby="sc-history-title">
          <header class="sc-panel__head">
            <span class="sc-panel__code">ARCHIVE / 03</span>
            <h2 id="sc-history-title">按天历史</h2>
            <span class="sc-panel__meta">DAILY RECORDS</span>
            <button class="sc-clear" type="button" @click="confirmClearHistory">清空历史</button>
          </header>

          <div class="sc-table-wrap">
            <table class="sc-table">
              <thead>
                <tr>
                  <th scope="col">日期</th>
                  <th scope="col">状态</th>
                  <th scope="col">邮件</th>
                  <th scope="col">差异</th>
                  <th scope="col">最近检查</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in runs" :key="row.date">
                  <td class="sc-table__mono">{{ row.date }}</td>
                  <td>
                    <span class="sc-status" :class="`is-${stateKey(row.status)}`">
                      <i class="sc-status__dot" aria-hidden="true"></i>{{ statusText(row.status) }}
                    </span>
                  </td>
                  <td class="sc-table__cell sc-table__ellipsis" :title="row.mail_subject || '-'">{{ row.mail_subject || '-' }}</td>
                  <td class="sc-table__cell sc-table__mono">
                    <template v-if="row.diffs && row.diffs.length">{{ row.diffs.length }} 项</template>
                    <template v-else>0</template>
                  </td>
                  <td class="sc-table__cell sc-table__mono">{{ formatTime(row.checked_at) }}</td>
                </tr>
                <tr v-if="runs.length === 0">
                  <td class="sc-table__empty" colspan="5">暂无记录</td>
                </tr>
              </tbody>
            </table>
          </div>

          <nav v-if="total > pageSize" class="sc-pager" aria-label="按天历史分页">
            <button class="sc-pager__btn" type="button" :disabled="page <= 1" @click="loadRuns(page - 1)">‹</button>
            <button
              v-for="p in pageCount"
              :key="p"
              class="sc-pager__btn"
              :class="{ 'is-active': p === page }"
              type="button"
              :aria-current="p === page ? 'page' : undefined"
              @click="loadRuns(p)"
            >{{ p }}</button>
            <button class="sc-pager__btn" type="button" :disabled="page >= pageCount" @click="loadRuns(page + 1)">›</button>
          </nav>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getSyncCheckConfig,
  saveSyncCheckConfig,
  triggerSyncCheck,
  getSyncCheckRuns,
  getSyncCheckToday,
  clearSyncCheckRuns
} from '@/api/tools'

const form = ref({
  enabled: true,
  require_push_activity: true,
  interval_minutes: 15,
  deadline_time: '18:30',
  mail_subject: '回复：【测试需求】关于常规PUSH的测试需求',
  mail_body_keyword: '已同步至线上',
  enable_dingtalk_notify: false
})

const saving = ref(false)
const configMessage = ref('')
const configMessageType = ref('success')

const running = ref(false)
const today = ref(null)
const runs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10

let pollTimer = null

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const loadConfig = async () => {
  try {
    const response = await getSyncCheckConfig()
    const data = response.data
    form.value = {
      enabled: data.enabled,
      require_push_activity: data.require_push_activity,
      interval_minutes: data.interval_minutes,
      deadline_time: data.deadline_time,
      mail_subject: data.mail_subject,
      mail_body_keyword: data.mail_body_keyword,
      enable_dingtalk_notify: data.enable_dingtalk_notify
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '配置加载失败')
  }
}

const saveConfig = async () => {
  saving.value = true
  configMessage.value = ''
  try {
    const response = await saveSyncCheckConfig(form.value)
    form.value = {
      enabled: response.data.enabled,
      require_push_activity: response.data.require_push_activity,
      interval_minutes: response.data.interval_minutes,
      deadline_time: response.data.deadline_time,
      mail_subject: response.data.mail_subject,
      mail_body_keyword: response.data.mail_body_keyword,
      enable_dingtalk_notify: response.data.enable_dingtalk_notify
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

const loadToday = async () => {
  try {
    const response = await getSyncCheckToday()
    today.value = response.data
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '当天状态加载失败')
  }
}

const startRun = async (force) => {
  running.value = true
  try {
    await triggerSyncCheck({ force })
    const before = today.value?.checked_at || ''
    clearInterval(pollTimer)
    pollTimer = setInterval(async () => {
      try {
        const response = await getSyncCheckToday()
        today.value = response.data
        if (response.data.checked_at && response.data.checked_at !== before) {
          running.value = false
          clearInterval(pollTimer)
          pollTimer = null
          await loadRuns()
        }
      } catch (error) {
        running.value = false
        clearInterval(pollTimer)
        pollTimer = null
        ElMessage.error(error.response?.data?.error || '状态获取失败')
      }
    }, 2000)
  } catch (error) {
    running.value = false
    ElMessage.error(error.response?.data?.error || '触发失败')
  }
}

const loadRuns = async (targetPage = 1) => {
  page.value = targetPage
  try {
    const response = await getSyncCheckRuns({ page: page.value, page_size: pageSize })
    runs.value = response.data.results || []
    total.value = response.data.count || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '历史记录加载失败')
  }
}

const confirmClearHistory = () => {
  if (runs.value.length === 0) {
    ElMessage.info('暂无按天记录')
    return
  }
  ElMessageBox.confirm('确定清空全部同步确认按天历史吗？此操作不可恢复。', '清空历史', {
    confirmButtonText: '清空',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(clearHistory).catch(() => {})
}

const clearHistory = async () => {
  try {
    await clearSyncCheckRuns()
    await loadRuns()
    await loadToday()
    ElMessage.success('按天历史已清空')
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '清空失败')
  }
}

const statusText = (status) => ({
  pending: '待监听',
  ok: '对比通过',
  fail: '对比不一致',
  timeout: '超时异常'
}[status] || 'STANDBY')

const stateKey = (status) => ({
  pending: 'pending',
  ok: 'ok',
  fail: 'fail',
  timeout: 'timeout'
}[status] || 'idle')

const formatTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

onMounted(() => {
  loadConfig()
  loadToday()
  loadRuns()
})

onUnmounted(() => {
  clearInterval(pollTimer)
})
</script>

<style lang="scss" scoped>
/* =============================================
   Endfield Moderate — Sync Check
   ============================================= */
.sc-page {
  --ark-ink: #191919;
  --ark-paper: #f2f2f0;
  --ark-signal: #fffa00;

  --sc-ink: var(--ark-ink);
  --sc-paper: var(--ark-paper);
  --sc-panel: #ffffff;
  --sc-line: #deded9;
  --sc-line-strong: #b9b9b2;
  --sc-signal: var(--ark-signal);
  --sc-state: #00ffa2;
  --sc-state-ink: #0d7d4e;
  --sc-muted: #6f6f69;
  --sc-dark: #111111;
  --sc-mono: "Space Grotesk", "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  --sc-display: "Space Grotesk", "Arial Narrow", "DIN Condensed", sans-serif;

  padding: 28px 32px 48px;
  max-width: 1480px;
  margin: 0 auto;
  color: var(--sc-ink);
}

.sc-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 32px;
  margin-bottom: 28px;
  animation: sc-reveal .6s cubic-bezier(.22, .8, .2, 1) both;

  &__titleblock { min-width: 0; }
  &__row { display: flex; align-items: baseline; gap: 16px; }
  &__index {
    font-family: var(--sc-display);
    font-size: 15px;
    letter-spacing: .08em;
    color: var(--sc-line-strong);
  }
}

.sc-kicker {
  margin: 0 0 10px;
  font-family: var(--sc-mono);
  font-size: 11px;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--sc-muted);
}

.sc-title {
  margin: 0;
  font-size: clamp(30px, 4vw, 44px);
  line-height: .95;
  letter-spacing: -.03em;
  font-weight: 800;
}

.sc-header__rule {
  display: block;
  width: min(420px, 46vw);
  height: 1px;
  margin: 18px 0 14px;
  background: var(--sc-line-strong);
  position: relative;

  &::after {
    content: "";
    position: absolute;
    left: 0;
    top: -1px;
    width: 44px;
    height: 3px;
    background: var(--sc-signal);
    clip-path: polygon(0 0, 100% 0, 78% 100%, 0 100%);
  }
}

.sc-header__desc {
  margin: 0;
  max-width: 720px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--sc-muted);
}

/* ---------- Run state strip ---------- */
.sc-runstate {
  flex-shrink: 0;
  min-width: 216px;
  padding: 14px 18px;
  background: var(--sc-dark);
  color: #fff;
  border-left: 4px solid var(--sc-signal);
  animation: sc-reveal .6s cubic-bezier(.22, .8, .2, 1) .08s both;

  &__kicker {
    margin: 0 0 8px;
    font-family: var(--sc-mono);
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
    &.is-ok { color: var(--sc-state); }
    &.is-fail, &.is-timeout { color: #ff7a5c; }
  }

  &__dot {
    width: 7px;
    height: 7px;
    background: rgba(255, 255, 255, .4);

    .is-ok & { background: var(--sc-state); }
    .is-fail &, .is-timeout & { background: #ff7a5c; }
    .is-pending & { background: var(--sc-signal); animation: sc-pulse 1.6s ease-in-out infinite; }
  }

  &__counts {
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, .12);
    font-size: 11px;
    color: rgba(255, 255, 255, .5);

    b { color: #fff; font-family: var(--sc-mono); font-weight: 600; }
  }

  &__mail {
    display: block;
    max-width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

/* ---------- Stage grid ---------- */
.sc-stage {
  display: grid;
  grid-template-columns: minmax(320px, 5fr) minmax(0, 7fr);
  gap: 20px;
  align-items: start;
}

.sc-maincol {
  display: grid;
  gap: 20px;
  min-width: 0;
}

/* ---------- Technical panel ---------- */
.sc-panel {
  background: var(--sc-panel);
  border: 1px solid var(--sc-line);
  border-radius: 0;
  position: relative;
  animation: sc-reveal .6s cubic-bezier(.22, .8, .2, 1) both;

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
    border-top: 3px solid var(--sc-signal);
    border-left: 3px solid var(--sc-signal);
    pointer-events: none;
  }

  &__head {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 12px 18px;
    border-bottom: 1px solid var(--sc-line);

    h2 {
      margin: 0;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: .02em;
    }
  }

  &__code {
    font-family: var(--sc-mono);
    font-size: 10px;
    letter-spacing: .14em;
    color: var(--sc-muted);
  }

  &__meta {
    margin-left: auto;
    font-family: var(--sc-mono);
    font-size: 9px;
    letter-spacing: .16em;
    text-transform: uppercase;
    color: var(--sc-line-strong);
  }

  &__foot {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 18px 18px;
    border-top: 1px solid var(--sc-line);
  }
}

/* ---------- Config form ---------- */
.sc-form {
  padding: 16px 18px 0;
}

.sc-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 12px;

  &--num { width: 180px; }
  &--full { width: 100%; }

  &__label {
    font-size: 11px;
    color: var(--sc-muted);
    letter-spacing: .04em;
  }
}

.sc-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--sc-line-strong);
  border-radius: 0;
  background: var(--sc-paper);
  color: var(--sc-ink);
  font-size: 13px;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", sans-serif;
  transition: border-color .15s, box-shadow .15s;

  &--num { font-family: var(--sc-mono); }
  &::placeholder { color: #9c9c95; }
  &:hover { border-color: var(--sc-ink); }
  &:focus-visible {
    outline: 2px solid var(--sc-signal);
    outline-offset: 2px;
    border-color: var(--sc-ink);
  }
}

/* ---------- Buttons ---------- */
.sc-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 18px;
  border: 1px solid var(--sc-ink);
  border-radius: 0;
  background: transparent;
  color: var(--sc-ink);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: .04em;
  cursor: pointer;
  overflow: hidden;
  transition: color .18s, background .18s, border-color .18s;

  &:hover:not(:disabled) {
    background: var(--sc-ink);
    color: #fff;
  }

  &:focus-visible {
    outline: 2px solid var(--sc-signal);
    outline-offset: 2px;
  }

  &:disabled {
    opacity: .5;
    cursor: not-allowed;
  }

  &__bar {
    width: 5px;
    height: 14px;
    background: var(--sc-signal);
    clip-path: polygon(0 0, 100% 0, 72% 100%, 0 100%);
    flex-shrink: 0;
  }

  &--primary,
  &--run {
    background: var(--sc-ink);
    color: #fff;

    .sc-btn__bar { background: var(--sc-signal); }
    &:hover:not(:disabled) { background: #2c2c2c; }
  }
}

/* ---------- Toggle ---------- */
.sc-toggle {
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

    &:focus-visible + .sc-toggle__track {
      outline: 2px solid var(--sc-signal);
      outline-offset: 2px;
    }
  }

  &__track {
    position: relative;
    width: 38px;
    height: 18px;
    background: var(--sc-line-strong);
    border: 1px solid var(--sc-line-strong);
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
    .sc-toggle__track { background: var(--sc-ink); border-color: var(--sc-ink); }
    .sc-toggle__thumb { left: 21px; background: var(--sc-signal); }
  }

  &__label {
    font-size: 12px;
    color: var(--sc-muted);
  }
}

.sc-field__note {
  margin: 6px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--sc-faint, #7b8496);
}

/* ---------- Run bar / summary ---------- */
.sc-runbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 18px;
  background: var(--sc-paper);
  border-bottom: 1px solid var(--sc-line);

  &__hint {
    margin-left: auto;
    font-family: var(--sc-mono);
    font-size: 10px;
    letter-spacing: .04em;
    color: var(--sc-line-strong);
  }
}

.sc-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--sc-line);
  background: #fbfbf9;

  &__item {
    display: flex;
    align-items: baseline;
    gap: 8px;

    i {
      font-style: normal;
      font-family: var(--sc-mono);
      font-size: 9px;
      letter-spacing: .14em;
      color: var(--sc-line-strong);
    }

    b {
      font-size: 12px;
      font-weight: 600;
      color: var(--sc-ink);
    }
  }
}

.sc-diffs {
  padding: 10px 18px;
  border-bottom: 1px solid var(--sc-line);
  background: #fff7f4;

  &__title {
    margin: 0 0 6px;
    font-family: var(--sc-mono);
    font-size: 9px;
    letter-spacing: .14em;
    color: #b23a24;
  }

  ul {
    margin: 0;
    padding-left: 18px;
    font-size: 12px;
    color: #7c2d1c;
    line-height: 1.7;
  }
}

/* ---------- Log ---------- */
.sc-log {
  margin: 0 18px 18px;
  border: 1px solid var(--sc-dark);
  background: var(--sc-dark);

  &__code {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, .14);
    font-family: var(--sc-mono);
    font-size: 10px;
    letter-spacing: .16em;
    color: rgba(255, 255, 255, .5);
  }

  &__live {
    width: 6px;
    height: 6px;
    background: rgba(255, 255, 255, .3);

    &.is-on {
      background: var(--sc-signal);
      animation: sc-pulse 1.6s ease-in-out infinite;
    }
  }

  &__body {
    margin: 0;
    max-height: 380px;
    min-height: 170px;
    overflow: auto;
    padding: 14px;
    color: #d9d9d4;
    font-family: var(--sc-mono);
    font-size: 12px;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-all;
    tab-size: 2;

    &:focus-visible {
      outline: 2px solid var(--sc-signal);
      outline-offset: -2px;
    }
  }
}

/* ---------- History table ---------- */
.sc-table-wrap { overflow-x: auto; }

.sc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;

  th {
    padding: 10px 12px;
    text-align: left;
    font-family: var(--sc-mono);
    font-size: 9px;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: var(--sc-muted);
    background: var(--sc-paper);
    border-bottom: 1px solid var(--sc-line-strong);
    white-space: nowrap;
  }

  td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--sc-line);
    color: var(--sc-ink);
  }

  tbody tr { transition: background .12s; &:hover { background: #f7f7f4; } }
  &__mono { font-family: var(--sc-mono); }
  &__ellipsis {
    max-width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &__empty {
    padding: 28px 12px;
    text-align: center;
    color: var(--sc-muted);
  }
}

.sc-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  white-space: nowrap;

  &__dot {
    width: 6px;
    height: 6px;
    background: var(--sc-line-strong);
  }

  &.is-ok { color: var(--sc-state-ink); .sc-status__dot { background: var(--sc-state-ink); } }
  &.is-fail, &.is-timeout { color: #b23a24; .sc-status__dot { background: #b23a24; } }
  &.is-pending { color: var(--sc-ink); .sc-status__dot { background: var(--sc-signal); animation: sc-pulse 1.6s ease-in-out infinite; } }
}

/* ---------- Pager ---------- */
.sc-pager {
  display: flex;
  gap: 6px;
  padding: 14px 18px;
  border-top: 1px solid var(--sc-line);

  &__btn {
    min-width: 32px;
    height: 32px;
    padding: 0 8px;
    border: 1px solid var(--sc-line-strong);
    border-radius: 0;
    background: transparent;
    color: var(--sc-ink);
    font-family: var(--sc-mono);
    font-size: 12px;
    cursor: pointer;
    transition: background .12s, color .12s;

    &:hover:not(:disabled) { background: var(--sc-ink); color: #fff; }
    &:focus-visible { outline: 2px solid var(--sc-signal); outline-offset: 2px; }
    &.is-active { background: var(--sc-ink); color: var(--sc-signal); }
    &:disabled { opacity: .4; cursor: not-allowed; }
  }
}

/* ---------- Foot message ---------- */
.sc-foot-msg {
  font-size: 12px;
  color: var(--sc-muted);

  &.is-error { color: #b23a24; }
  &.is-success { color: var(--sc-state-ink); }
}

.sc-clear {
  margin-left: 4px;
  padding: 4px 8px;
  border: 1px solid var(--sc-line-strong);
  border-radius: 0;
  background: transparent;
  color: var(--sc-muted);
  font-size: 11px;
  cursor: pointer;
  transition: color .15s, border-color .15s, background .15s;

  &:hover:not(:disabled) {
    border-color: #b23a24;
    color: #b23a24;
  }

  &:focus-visible {
    outline: 2px solid var(--sc-signal);
    outline-offset: 2px;
  }
}

/* ---------- Motion ---------- */
@keyframes sc-reveal {
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

@keyframes sc-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .35; }
}

@media (prefers-reduced-motion: reduce) {
  .sc-header,
  .sc-panel,
  .sc-runstate {
    animation: none;
  }

  .sc-runstate__dot,
  .sc-log__live,
  .sc-status.is-pending .sc-status__dot {
    animation: none;
  }
}

/* ---------- Responsive ---------- */
@media (max-width: 1024px) {
  .sc-stage { grid-template-columns: 1fr; }
}

@media (max-width: 720px), (orientation: portrait) {
  .sc-page { padding: 20px 16px 36px; }
  .sc-header { flex-direction: column; align-items: stretch; gap: 20px; }
  .sc-runstate { min-width: 0; }
  .sc-runbar { flex-direction: column; align-items: stretch; }
  .sc-runbar__hint { margin-left: 0; }
  .sc-panel__head { flex-wrap: wrap; }
  .sc-panel__meta { margin-left: 0; width: 100%; }
}
</style>
