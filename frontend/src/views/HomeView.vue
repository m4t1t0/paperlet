<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api, type WritersList } from "../api/client";

const catalog = ref<WritersList | null>(null);
const error = ref("");

onMounted(async () => {
  try {
    catalog.value = await api.listWriters();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load catalog";
  }
});
</script>

<template>
  <div>
    <h1 class="mb-2 text-3xl font-bold">Writers on Paperlet</h1>
    <p class="mb-6 text-stone-500">Subscribe to up to 5 writers with one subscription.</p>
    <p v-if="error" class="text-red-600">{{ error }}</p>
    <ul v-else class="grid gap-3">
      <li
        v-for="w in catalog?.writers ?? []"
        :key="w.id"
        class="rounded border border-stone-200 bg-white p-4"
      >
        <RouterLink :to="`/writers/${w.id}`" class="font-medium hover:underline">
          {{ w.email }}
        </RouterLink>
      </li>
    </ul>
    <p v-if="catalog && catalog.total === 0" class="text-stone-500">No writers yet.</p>
  </div>
</template>
