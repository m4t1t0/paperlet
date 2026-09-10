<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { api, type PostView } from "../api/client";

const route = useRoute();
const post = ref<PostView | null>(null);
const error = ref("");

onMounted(async () => {
  try {
    post.value = await api.getPost(route.params.id as string);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load post";
  }
});
</script>

<template>
  <div>
    <p v-if="error" class="text-red-600">{{ error }}</p>
    <article v-else-if="post" class="max-w-2xl">
      <h1 class="mb-4 text-3xl font-bold">{{ post.title }}</h1>
      <p class="whitespace-pre-wrap">{{ post.preview_content }}</p>
      <p v-if="post.has_full_access" class="mt-4 whitespace-pre-wrap">
        {{ post.subscriber_content }}
      </p>
      <div v-else class="mt-6 rounded border border-amber-300 bg-amber-50 p-4 text-sm">
        <p class="font-semibold text-amber-900">This post continues for subscribers.</p>
        <p class="mt-1 text-amber-800">
          Allocate one of your 5 slots to this writer to keep reading.
        </p>
        <RouterLink to="/reader" class="mt-2 inline-block font-medium text-amber-900 underline">
          Go to reader dashboard
        </RouterLink>
      </div>
    </article>
  </div>
</template>
