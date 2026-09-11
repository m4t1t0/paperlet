<script setup lang="ts">
/** Avatar image with initials fallback. */
const props = defineProps<{ name: string; avatarUrl?: string | null; size?: string }>();

const initials = (props.name.trim()[0] ?? "?").toUpperCase();
</script>

<template>
  <img
    v-if="props.avatarUrl"
    :src="props.avatarUrl"
    :alt="props.name"
    :class="['rounded-full object-cover', props.size ?? 'h-10 w-10']"
  />
  <span
    v-else
    :class="[
      'flex shrink-0 items-center justify-center rounded-full bg-orange-100 font-semibold text-orange-700',
      props.size ?? 'h-10 w-10',
    ]"
    aria-hidden="true"
  >
    {{ initials }}
  </span>
</template>
