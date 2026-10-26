<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  label: { type: String, default: '' }
})
defineEmits(['update:modelValue'])
</script>

<template>
  <div class="switch" :class="{ on: modelValue }" @click="$emit('update:modelValue', !modelValue)">
    <span>{{ label }}</span>
    <i />
  </div>
</template>
