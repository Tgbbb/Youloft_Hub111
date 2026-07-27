<template>
  <div class="elogin" data-ark-theme="endfield" data-ark-depth="moderate">
    <div class="elogin__grid" aria-hidden="true"></div>

    <!-- Left: Brand -->
    <section class="elogin__left">
      <div class="elogin__brand">
        <span class="elogin__wedge" aria-hidden="true"></span>
        <h1 class="elogin__title">TestHub</h1>
        <p class="elogin__sub">AI-Powered Testing Platform</p>
      </div>

      <div class="elogin__features">
        <div class="elogin__feat" v-for="f in features" :key="f.title">
          <span class="elogin__feat-icon"><component :is="f.icon" /></span>
          <span class="elogin__feat-title">{{ f.title }}</span>
        </div>
      </div>

      <div class="elogin__lang">
        <el-dropdown @command="handleLanguageChange" trigger="click">
          <span class="elogin__lang-btn">
            {{ currentLanguage === 'zh-cn' ? 'CN' : 'EN' }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="zh-cn" :disabled="currentLanguage === 'zh-cn'">🇨🇳 简体中文</el-dropdown-item>
              <el-dropdown-item command="en" :disabled="currentLanguage === 'en'">🇺🇸 English</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </section>

    <!-- Right: Form -->
    <section class="elogin__right">
      <div class="elogin__form-wrap">
        <div class="elogin__form-head">
          <h2>{{ $t('auth.welcomeBack') }}</h2>
          <p>{{ $t('auth.loginSubtitle') }}</p>
        </div>

        <!-- Mode tabs -->
        <div class="elogin__tabs">
          <button :class="{ 'is-on': loginMode === 'password' }" @click="loginMode = 'password'">密码登录</button>
          <button :class="{ 'is-on': loginMode === 'sms' }" @click="loginMode = 'sms'; refreshCaptcha()">短信登录</button>
        </div>

        <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin">
          <!-- Password -->
          <template v-if="loginMode === 'password'">
            <el-form-item prop="username">
              <el-input v-model="form.username" :placeholder="$t('auth.usernamePlaceholder')" size="large" :prefix-icon="User" class="elogin__input" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="form.password" type="password" :placeholder="$t('auth.passwordPlaceholder')" size="large" :prefix-icon="Lock" show-password @keyup.enter="handleLogin" class="elogin__input" />
            </el-form-item>
          </template>

          <!-- SMS -->
          <template v-if="loginMode === 'sms'">
            <el-form-item prop="phone">
              <el-input v-model="form.phone" placeholder="请输入手机号" size="large" :prefix-icon="Phone" maxlength="11" class="elogin__input" />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="14">
                <el-form-item prop="captcha_code">
                  <el-input v-model="form.captcha_code" placeholder="图形验证码" size="large" maxlength="4" class="elogin__input" />
                </el-form-item>
              </el-col>
              <el-col :span="10">
                <img :src="captchaImage" alt="验证码" class="elogin__captcha" @click="refreshCaptcha" title="点击刷新验证码" />
              </el-col>
            </el-row>
            <el-form-item prop="verify_code">
              <el-input v-model="form.verify_code" placeholder="短信验证码" size="large" maxlength="6" class="elogin__input">
                <template #append>
                  <el-button :disabled="smsCountdown > 0 || !form.phone || !form.captcha_code" :loading="sendingSms" @click="sendVerifyCode" class="elogin__sms-btn">
                    {{ smsCountdown > 0 ? `${smsCountdown}s` : '发送验证码' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>
          </template>

          <el-form-item>
            <el-button type="primary" size="large" :loading="loading" @click="handleLogin" class="elogin__submit">
              {{ loading ? $t('auth.loggingIn') : $t('auth.login') }}
            </el-button>
          </el-form-item>

          <div class="elogin__footer">
            <router-link to="/register">{{ $t('auth.noAccount') }}<span>{{ $t('auth.signUpNow') }}</span></router-link>
          </div>
        </el-form>

        <p class="elogin__copy">{{ $t('auth.copyright') }}</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { User, Lock, Phone, Document, MagicStick, Connection, TrendCharts, ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import api from '@/utils/api'

const router = useRouter()
const userStore = useUserStore()
const appStore = useAppStore()
const { t } = useI18n()
const currentLanguage = computed(() => appStore.language)
const handleLanguageChange = (lang) => { appStore.setLanguage(lang) }

const formRef = ref()
const loading = ref(false)
const loginMode = ref('password')
const captchaImage = ref('')
const captchaToken = ref('')
const sendingSms = ref(false)
const smsCountdown = ref(0)
let countdownTimer = null

const form = reactive({
  username: '', password: '', phone: '', captcha_code: '', verify_code: '', verify_code_token: ''
})

const validatePhone = (rule, value, callback) => {
  if (!value) { callback(new Error('请输入手机号')); return }
  if (!/^1[3-9]\d{9}$/.test(value)) { callback(new Error('手机号格式不正确')); return }
  callback()
}

const rules = {
  username: [{ required: true, message: computed(() => t('auth.usernameRequired')), trigger: 'blur' }],
  password: [
    { required: true, message: computed(() => t('auth.passwordRequired')), trigger: 'blur' },
    { min: 6, message: computed(() => t('auth.passwordLength')), trigger: 'blur' }
  ],
  phone: [{ required: true, validator: validatePhone, trigger: 'blur' }],
  captcha_code: [{ required: true, message: '请输入图形验证码', trigger: 'blur' }],
  verify_code: [{ required: true, message: '请输入短信验证码', trigger: 'blur' }]
}

const features = computed(() => [
  { icon: Document, title: t('auth.aiCaseGeneration') },
  { icon: MagicStick, title: t('auth.aiIntelligentTesting') },
  { icon: Connection, title: t('auth.multiTypeTesting') },
  { icon: TrendCharts, title: t('auth.dataAnalysis') },
])

const refreshCaptcha = async () => {
  try { const r = await api.get('/auth/captcha/'); captchaImage.value = r.data.image; captchaToken.value = r.data.token; form.captcha_code = '' } catch (e) {}
}

const sendVerifyCode = async () => {
  if (!form.phone) { ElMessage.warning('请先输入手机号'); return }
  if (!form.captcha_code) { ElMessage.warning('请先输入图形验证码'); return }
  sendingSms.value = true
  try {
    const r = await api.post('/auth/send-register-code/', { phone: form.phone, captcha_token: captchaToken.value, captcha_code: form.captcha_code, mode: 'login' })
    form.verify_code_token = r.data.verify_code_token
    ElMessage.success('验证码已发送')
    smsCountdown.value = 60
    countdownTimer = setInterval(() => { smsCountdown.value--; if (smsCountdown.value <= 0) { clearInterval(countdownTimer); countdownTimer = null } }, 1000)
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '验证码发送失败')
    refreshCaptcha()
  } finally { sendingSms.value = false }
}

const handleLogin = async () => {
  if (!formRef.value) return
  if (loginMode.value === 'sms') {
    await formRef.value.validate(async (valid) => {
      if (valid) {
        loading.value = true
        try { await userStore.smsLogin({ phone: form.phone, verify_code: form.verify_code, verify_code_token: form.verify_code_token }); ElMessage.success(t('auth.loginSuccess')); await router.replace('/home') }
        catch (e) { ElMessage.error(e.response?.data?.error || t('auth.loginFailed')); refreshCaptcha() }
        finally { loading.value = false }
      }
    })
    return
  }
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try { await userStore.login(form); ElMessage.success(t('auth.loginSuccess')); await router.replace('/home') }
      catch (e) { ElMessage.error(e.response?.data?.error || t('auth.loginFailed')) }
      finally { loading.value = false }
    }
  })
}

onUnmounted(() => { if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null } })
</script>

<style lang="scss" scoped>
.elogin {
  height: 100vh; display: flex;
  background: #f2f2f0;
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  position: relative; overflow: hidden;
  &__grid {
    position: absolute; inset: 0; pointer-events: none; z-index: 0;
    background-image:
      linear-gradient(to right, #e0ded8 1px, transparent 1px),
      linear-gradient(to bottom, #e0ded8 1px, transparent 1px);
    background-size: 72px 72px; opacity: .4;
  }
}

/* ======== Left ======== */
.elogin__left {
  flex: 1; display: flex; flex-direction: column; justify-content: center;
  padding: 80px 60px; position: relative; z-index: 2;
}
.elogin__brand {
  margin-bottom: 56px;
  .elogin__wedge {
    display: block; width: 24px; height: 6px; background: #fffa00; margin-bottom: 20px;
    clip-path: polygon(0 0, 100% 0, 85% 100%, 0 100%);
  }
  .elogin__title {
    font-size: 3rem; font-weight: 900; color: #191919; margin: 0; line-height: .92; letter-spacing: -.04em;
  }
  .elogin__sub {
    font-size: 13px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .12em; color: #999; margin: 8px 0 0;
  }
}
.elogin__features {
  display: flex; flex-direction: column; gap: 18px; margin-bottom: 60px;
  .elogin__feat {
    display: flex; align-items: center; gap: 14px;
    font-size: 14px; color: #555; font-weight: 500;
    .elogin__feat-icon { color: #999; font-size: 20px; width: 24px; text-align: center; }
  }
}
.elogin__lang {
  .elogin__lang-btn {
    display: inline-flex; align-items: center; gap: 4px;
    cursor: pointer; font-size: 12px; color: #999;
    font-family: "Space Grotesk", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .08em; font-weight: 600;
    padding: 4px 10px; border: 1px solid #d4d2cc;
    &:hover { color: #555; border-color: #999; }
  }
}

/* ======== Right ======== */
.elogin__right {
  width: 460px; display: flex; align-items: center; justify-content: center;
  background: #fff; position: relative; z-index: 2; padding: 60px 48px;
  border-left: 1px solid #e4e4de;
}
.elogin__form-wrap { width: 100%; max-width: 360px; }
.elogin__form-head {
  margin-bottom: 28px;
  h2 { font-size: 1.5rem; font-weight: 800; color: #191919; margin: 0 0 6px; }
  p { font-size: 13px; color: #999; margin: 0; }
}
.elogin__tabs {
  display: flex; gap: 0; margin-bottom: 28px;
  button {
    all: unset; cursor: pointer; flex: 1; text-align: center;
    padding: 10px 0; font-size: 13px; font-weight: 600; color: #bbb;
    border-bottom: 2px solid #e8e6e0; transition: all .12s;
    &:hover { color: #666; }
    &.is-on { color: #191919; border-bottom-color: #fffa00; }
  }
}
.elogin__input {
  :deep(.el-input__wrapper) {
    border-radius: 0 !important; box-shadow: 0 0 0 1px #d0cec8 inset !important;
    &:hover { box-shadow: 0 0 0 1px #aaa inset !important; }
    &.is-focus { box-shadow: 0 0 0 1px #fffa00 inset !important; }
  }
  :deep(.el-form-item) { margin-bottom: 22px; }
}
.elogin__captcha {
  width: 100%; height: 42px; cursor: pointer; border: 1px solid #d0cec8;
}
.elogin__sms-btn {
  border-radius: 0 !important; min-width: 100px; font-size: 12px;
  font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase; letter-spacing: .04em;
}
.elogin__submit {
  width: 100%; height: 48px; font-size: 15px; font-weight: 700;
  border-radius: 0 !important; border: none !important;
  background: #fffa00 !important; color: #191919 !important;
  letter-spacing: .06em; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase;
  &:hover { background: #e6e100 !important; }
}
.elogin__footer {
  text-align: center; margin-top: 24px;
  a { font-size: 13px; color: #999; text-decoration: none;
    span { color: #191919; font-weight: 700; margin-left: 4px; }
    &:hover { color: #555; }
  }
}
.elogin__copy {
  text-align: center; font-size: 11px; color: #ccc; margin: 40px 0 0;
}

/* ======== Responsive ======== */
@media (max-width: 768px) {
  .elogin { flex-direction: column; }
  .elogin__left { padding: 40px 28px; flex: none; .elogin__title { font-size: 2rem; } .elogin__features { display: none; } }
  .elogin__right { width: 100%; border-left: none; border-top: 1px solid #e4e4de; padding: 40px 28px; }
}
</style>
