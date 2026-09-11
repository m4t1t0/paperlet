<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { api, type WriterDetail } from "../api/client";
import Avatar from "../components/Avatar.vue";

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
      <div class="mb-1 flex items-center gap-3">
        <Avatar :name="writer.display_name" :avatar-url="writer.avatar_url" size="h-12 w-12" />
        <div>
          <h1 class="text-2xl font-bold">{{ writer.display_name }}</h1>
          <p class="text-sm text-stone-500">{{ writer.email }}</p>
        </div>
      </div>
      <p class="mb-6 mt-2 text-sm text-stone-500">
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
