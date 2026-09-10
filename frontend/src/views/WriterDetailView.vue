<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { api, type WriterDetail } from "../api/client";

const route = useRoute();
const writer = ref<WriterDetail | null>(null);
const error = ref("");

onMounted(async () => {
  try {
    writer.value = await api.getWriter(route.params.id as string);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Writer not found";
  }
});
</script>

<template>
  <div>
    <p v-if="error" class="text-red-600">{{ error }}</p>
    <div v-else-if="writer">
      <h1 class="mb-1 text-2xl font-bold">{{ writer.email }}</h1>
      <p class="mb-6 text-sm text-stone-500">
        {{ writer.subscriber_post_count }} published posts
      </p>
      <ul class="space-y-3">
        <li
          v-for="p in writer.posts"
          :key="p.id"
          class="rounded border border-stone-200 bg-white p-4"
        >
          <RouterLink :to="`/posts/${p.id}`" class="font-medium hover:underline">
            {{ p.title }}
          </RouterLink>
          <span
            v-if="!p.has_full_access"
            class="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800"
          >
            Preview
          </span>
          <p class="mt-1 text-sm text-stone-600">{{ p.preview_content }}</p>
        </li>
      </ul>
    </div>
  </div>
</template>
