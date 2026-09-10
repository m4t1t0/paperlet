<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, type WriterPosts } from "../api/client";

const posts = ref<WriterPosts | null>(null);
const error = ref("");

const title = ref("");
const preview = ref("");
const subscriber = ref("");
const scheduledAt = ref("");

async function refresh(): Promise<void> {
  posts.value = await api.writerPosts();
}

onMounted(async () => {
  try {
    await refresh();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load posts";
  }
});

async function create(): Promise<void> {
  error.value = "";
  try {
    await api.createPost({
      title: title.value,
      preview_content: preview.value,
      subscriber_content: subscriber.value,
      ...(scheduledAt.value ? { scheduled_at: new Date(scheduledAt.value).toISOString() } : {}),
    });
    title.value = preview.value = subscriber.value = scheduledAt.value = "";
    await refresh();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Create failed";
  }
}

async function publish(id: string): Promise<void> {
  error.value = "";
  try {
    await api.publishPost(id);
    await refresh();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Publish failed";
  }
}
</script>

<template>
  <div class="space-y-8">
    <h1 class="text-2xl font-bold">Writer dashboard</h1>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

    <form class="space-y-3 rounded border border-stone-200 bg-white p-4" @submit.prevent="create">
      <h2 class="font-semibold">New post</h2>
      <input
        v-model="title"
        required
        placeholder="Title"
        class="w-full rounded border border-stone-300 px-3 py-2"
      />
      <textarea
        v-model="preview"
        required
        rows="3"
        placeholder="Public preview (free for everyone)"
        class="w-full rounded border border-stone-300 px-3 py-2"
      />
      <textarea
        v-model="subscriber"
        rows="5"
        placeholder="Subscriber-only content"
        class="w-full rounded border border-stone-300 px-3 py-2"
      />
      <div class="flex items-center gap-2">
        <input
          v-model="scheduledAt"
          type="datetime-local"
          class="rounded border border-stone-300 px-3 py-2 text-sm"
        />
        <button class="rounded bg-stone-900 px-4 py-2 text-sm text-white hover:bg-stone-700">
          {{ scheduledAt ? "Schedule" : "Save draft" }}
        </button>
      </div>
    </form>

    <section>
      <h2 class="mb-2 font-semibold">My posts</h2>
      <ul class="space-y-2">
        <li
          v-for="p in posts?.posts ?? []"
          :key="p.id"
          class="flex items-center justify-between rounded border border-stone-200 bg-white p-3 text-sm"
        >
          <span>
            <span class="font-medium">{{ p.title }}</span>
            <span class="ml-2 rounded bg-stone-100 px-2 py-0.5 text-xs">{{ p.status }}</span>
          </span>
          <button
            v-if="p.status !== 'published'"
            class="rounded bg-stone-900 px-3 py-1 text-xs text-white"
            @click="publish(p.id)"
          >
            Publish
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>
