<template>
  <div
    class="ms-loader"
    :class="`ms-loader--${size}`"
    role="status"
    :aria-label="label || '加载中'"
  >
    <div class="ms-loader__frame" aria-hidden="true">
      <span class="ms-loader__sweep"></span>
      <span class="ms-loader__tick ms-loader__tick--tl"></span>
      <span class="ms-loader__tick ms-loader__tick--br"></span>
    </div>
    <span v-if="label" class="ms-loader__label">{{ label }}</span>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, default: '' },
  size: { type: String, default: 'md', validator: (v) => ['sm', 'md', 'lg'].includes(v) },
})
</script>

<style scoped lang="scss">
.ms-loader {
  --loader-signal: #fffa00;
  --loader-rule: rgba(255, 255, 255, .16);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  font-family: "Space Grotesk", system-ui, sans-serif;

  &__frame {
    position: relative;
    width: 56px;
    height: 56px;
    border: 1px solid var(--loader-rule);
    overflow: hidden;
    background:
      linear-gradient(rgba(255, 255, 255, .035) 1px, transparent 1px) 0 0 / 100% 14px,
      linear-gradient(90deg, rgba(255, 255, 255, .035) 1px, transparent 1px) 0 0 / 14px 100%;
  }

  &__sweep {
    position: absolute;
    top: 0;
    left: -30%;
    width: 26%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 250, 0, .10) 55%, var(--loader-signal));
    animation: ms-loader-sweep 1.9s cubic-bezier(.45, .05, .35, 1) infinite;

    &::after {
      content: '';
      position: absolute;
      right: 0;
      top: 0;
      bottom: 0;
      width: 2px;
      background: var(--loader-signal);
    }
  }

  &__tick {
    position: absolute;
    width: 5px;
    height: 5px;
    background: var(--loader-signal);
    animation: ms-loader-breathe 1.9s ease-in-out infinite;

    &--tl {
      top: 6px;
      left: 6px;
    }
    &--br {
      bottom: 6px;
      right: 6px;
      animation-delay: .95s;
    }
  }

  &__label {
    font-size: 10px;
    letter-spacing: .18em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, .45);
  }

  &--sm {
    .ms-loader__frame { width: 40px; height: 40px; }
    .ms-loader__label { font-size: 9px; }
  }
  &--lg {
    .ms-loader__frame { width: 72px; height: 72px; }
    .ms-loader__label { font-size: 11px; }
  }
}

@keyframes ms-loader-sweep {
  0% { left: -30%; opacity: 1; }
  60% { left: 104%; opacity: 1; }
  82%, 100% { left: 104%; opacity: 0; }
}

@keyframes ms-loader-breathe {
  0%, 100% { opacity: .15; }
  50% { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .ms-loader__sweep,
  .ms-loader__tick {
    animation: none;
  }
  .ms-loader__sweep {
    left: 0;
    opacity: .6;
  }
  .ms-loader__tick {
    opacity: .7;
  }
}
</style>
