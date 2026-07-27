<template>
  <div class="ereg" data-ark-theme="endfield" data-ark-depth="moderate">
    <div class="ereg__grid" aria-hidden="true"></div>

    <!-- Left: Brand -->
    <section class="ereg__left">
      <div class="ereg__brand">
        <span class="ereg__wedge" aria-hidden="true"></span>
        <h1 class="ereg__title">TestHub</h1>
        <p class="ereg__sub">Create Your Account</p>
      </div>
      <p class="ereg__desc">{{ $t('auth.registerSubtitle') }}</p>
      <div class="ereg__login-link">
        已有账户？<router-link to="/login">返回登录</router-link>
      </div>
    </section>

    <!-- Right: Form -->
    <section class="ereg__right">
      <div class="ereg__form-wrap">
        <div class="ereg__form-head">
          <h2>{{ $t('auth.registerTitle') }}</h2>
        </div>

        <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleRegister">
          <el-form-item prop="username">
            <el-input v-model="form.username" :placeholder="$t('auth.username')" size="large" :prefix-icon="User" class="ereg__input" />
          </el-form-item>

          <el-form-item prop="email">
            <el-input v-model="form.email" type="email" :placeholder="$t('auth.email')" size="large" :prefix-icon="Message" class="ereg__input" />
          </el-form-item>

          <el-row :gutter="12">
            <el-col :span="14">
              <el-form-item prop="captcha_code">
                <el-input v-model="form.captcha_code" placeholder="图形验证码" size="large" maxlength="4" class="ereg__input" />
              </el-form-item>
            </el-col>
            <el-col :span="10">
              <img :src="captchaImage" alt="验证码" class="ereg__captcha" @click="refreshCaptcha" title="点击刷新验证码" />
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item prop="first_name">
                <el-input v-model="form.first_name" :placeholder="$t('auth.firstName')" size="large" class="ereg__input" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item prop="last_name">
                <el-input v-model="form.last_name" :placeholder="$t('auth.lastName')" size="large" class="ereg__input" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" :placeholder="$t('auth.password')" size="large" :prefix-icon="Lock" show-password class="ereg__input" />
          </el-form-item>

          <el-form-item prop="password_confirm">
            <el-input v-model="form.password_confirm" type="password" :placeholder="$t('auth.confirmPassword')" size="large" :prefix-icon="Lock" show-password class="ereg__input" />
          </el-form-item>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item prop="department">
                <el-input v-model="form.department" :placeholder="$t('auth.department')" size="large" class="ereg__input" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item prop="position">
                <el-input v-model="form.position" :placeholder="$t('auth.position')" size="large" class="ereg__input" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item>
            <el-button type="primary" size="large" :loading="loading" @click="handleRegister" class="ereg__submit">
              {{ $t('auth.register') }}
            </el-button>
          </el-form-item>

          <div class="ereg__footer">
            <router-link to="/login">{{ $t('auth.hasAccount') }}</router-link>
          </div>
        </el-form>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { User, Lock, Message } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import api from '@/utils/api'

const router = useRouter()
const userStore = useUserStore()
const { t } = useI18n()
const formRef = ref()
const loading = ref(false)
const captchaImage = ref('')
const captchaToken = ref('')

const form = reactive({
  username: '', email: '', first_name: '', last_name: '',
  password: '', password_confirm: '', captcha_code: '', department: '', position: ''
})

const rules = {
  username: [
    { required: true, message: computed(() => t('auth.usernameRequired')), trigger: 'blur' },
    { min: 3, max: 20, message: computed(() => t('auth.usernameLength')), trigger: 'blur' }
  ],
  captcha_code: [{ required: true, message: '请输入图形验证码', trigger: 'blur' }],
  email: [
    { required: true, message: computed(() => t('auth.emailRequired')), trigger: 'blur' },
    { type: 'email', message: computed(() => t('auth.emailFormat')), trigger: 'blur' }
  ],
  password: [
    { required: true, message: computed(() => t('auth.passwordRequired')), trigger: 'blur' },
    { min: 6, message: computed(() => t('auth.passwordLength')), trigger: 'blur' }
  ],
  password_confirm: [
    { required: true, message: computed(() => t('auth.confirmPasswordRequired')), trigger: 'blur' },
    { validator: (rule, value, callback) => { callback(value !== form.password ? new Error(t('auth.passwordMismatch')) : undefined) }, trigger: 'blur' }
  ]
}

const refreshCaptcha = async () => {
  try { const r = await api.get('/auth/captcha/'); captchaImage.value = r.data.image; captchaToken.value = r.data.token; form.captcha_code = '' }
  catch (e) { ElMessage.error('获取验证码失败，请刷新重试') }
}

const handleRegister = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await userStore.register({ ...form, captcha_token: captchaToken.value })
        ElMessage.success(t('auth.registerSuccess'))
        router.replace('/home')
      } catch (e) {
        ElMessage.error(e.response?.data?.error || t('auth.registerFailed'))
        refreshCaptcha()
      } finally { loading.value = false }
    }
  })
}

refreshCaptcha()
</script>

<style lang="scss" scoped>
.ereg {
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
.ereg__left {
  flex: 1; display: flex; flex-direction: column; justify-content: center;
  padding: 80px 60px; position: relative; z-index: 2;
}
.ereg__brand {
  margin-bottom: 24px;
  .ereg__wedge {
    display: block; width: 24px; height: 6px; background: #fffa00; margin-bottom: 20px;
    clip-path: polygon(0 0, 100% 0, 85% 100%, 0 100%);
  }
  .ereg__title {
    font-size: 3rem; font-weight: 900; color: #191919; margin: 0; line-height: .92; letter-spacing: -.04em;
  }
  .ereg__sub {
    font-size: 13px; font-family: "Space Grotesk", "IBM Plex Sans", system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: .12em; color: #999; margin: 8px 0 0;
  }
}
.ereg__desc { font-size: 14px; color: #888; margin: 0 0 40px; line-height: 1.6; max-width: 320px; }
.ereg__login-link {
  font-size: 13px; color: #999;
  a { color: #191919; font-weight: 700; text-decoration: none; margin-left: 4px; &:hover { text-decoration: underline; } }
}

/* ======== Right ======== */
.ereg__right {
  width: 520px; display: flex; align-items: center; justify-content: center;
  background: #fff; position: relative; z-index: 2; padding: 60px 48px;
  border-left: 1px solid #e4e4de; overflow-y: auto;
}
.ereg__form-wrap { width: 100%; }
.ereg__form-head {
  margin-bottom: 24px;
  h2 { font-size: 1.5rem; font-weight: 800; color: #191919; margin: 0; }
}
.ereg__input {
  :deep(.el-input__wrapper) {
    border-radius: 0 !important; box-shadow: 0 0 0 1px #d0cec8 inset !important;
    &:hover { box-shadow: 0 0 0 1px #aaa inset !important; }
    &.is-focus { box-shadow: 0 0 0 1px #fffa00 inset !important; }
  }
  :deep(.el-form-item) { margin-bottom: 20px; }
}
.ereg__captcha { width: 100%; height: 42px; cursor: pointer; border: 1px solid #d0cec8; }
.ereg__submit {
  width: 100%; height: 48px; font-size: 15px; font-weight: 700;
  border-radius: 0 !important; border: none !important;
  background: #fffa00 !important; color: #191919 !important;
  letter-spacing: .06em; font-family: "Space Grotesk", system-ui, sans-serif; text-transform: uppercase;
  &:hover { background: #e6e100 !important; }
}
.ereg__footer {
  text-align: center; margin-top: 20px;
  a { font-size: 13px; color: #999; text-decoration: none; &:hover { color: #555; } }
}

/* ======== Responsive ======== */
@media (max-width: 768px) {
  .ereg { flex-direction: column; }
  .ereg__left { padding: 40px 28px; flex: none; .ereg__title { font-size: 2rem; } }
  .ereg__right { width: 100%; border-left: none; border-top: 1px solid #e4e4de; padding: 40px 28px; }
}
</style>
