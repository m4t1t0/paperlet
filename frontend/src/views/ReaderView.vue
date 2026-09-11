<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api, type AllocationSummary, type Feed, type WritersList } from "../api/client";

const summary = ref<AllocationSummary | null>(null);
const feed = ref<Feed | null>(null);
const catalog = ref<WritersList | null>(null);
const error = ref("");

const assignId = ref("");
const swapFrom = ref("");
const swapTo = ref("");

const writerName = computed(() => {
  const map = new Map((catalog.value?.writers ?? []).map((w) => [w.id, w.email]));
  return (id: string | null) => (id ? (map.get(id) ?? id) : "Empty slot");
});

async function refresh(): Promise<void> {
  const [s, f, c] = await Promise.all([
    api.allocations(),
    api.feed(),
    api.listWriters("", 100),
  ]);
  summary.value = s;
  feed.value = f;
  catalog.value = c;
}

onMounted(async () => {
  try {
    await refresh();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load dashboard";
  }
});

async function run(fn: () => Promise<unknown>): Promise<void> {
  error.value = "";
  try {
    await fn();
    await refresh();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Action failed";
  }
}
</script>

<template>
  <div class="space-y-8">
    <div>
      <h1 class="text-2xl font-bold">Reader dashboard</h1>
      <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
    </div>

    <section v-if="summary && !summary.subscription_id">
      <button
        class="rounded bg-stone-900 px-4 py-2 text-white hover:bg-stone-700"
        @click="run(() => api.subscribe())"
      >
        Subscribe (€9.95/month)
      </button>
    </section>

    <section v-if="summary?.subscription_id">
      <h2 class="mb-1 font-semibold">
        Slots
        <span class="ml-2 text-sm font-normal text-stone-500">
          {{ summary.change_credits_remaining }}/{{ summary.change_credits_per_cycle }} changes left
        </span>
      </h2>
      <ul class="grid gap-2 sm:grid-cols-5">
        <li
          v-for="(slot, i) in summary.allocations"
          :key="i"
          class="rounded border border-stone-200 bg-white p-3 text-sm"
        >
          <p class="font-medium">{{ writerName(slot.writer_id) }}</p>
          <button
            v-if="slot.writer_id"
            class="mt-1 text-xs text-red-600 hover:underline"
            @click="run(() => api.release(slot.writer_id as string))"
          >
            Release (−1 credit)
          </button>
          <p v-else class="text-stone-400">Empty</p>
        </li>
      </ul>

      <div class="mt-4 flex flex-wrap items-end gap-2 text-sm">
        <label class="flex flex-col gap-1">
          Assign writer
          <span class="flex gap-2">
            <select v-model="assignId" class="rounded border border-stone-300 px-2 py-1">
              <option value="" disabled>Select writer</option>
              <option v-for="w in catalog?.writers ?? []" :key="w.id" :value="w.id">
                {{ w.email }}
              </option>
            </select>
            <button
              class="rounded bg-stone-900 px-3 py-1 text-white"
              :disabled="!assignId"
              @click="run(() => api.assign(assignId))"
            >
              Assign
            </button>
          </span>
        </label>
        <label class="flex flex-col gap-1">
          Swap (costs 1 credit)
          <span class="flex gap-2">
            <select v-model="swapFrom" class="rounded border border-stone-300 px-2 py-1">
              <option value="" disabled>From</option>
              <option
                v-for="(slot, i) in (summary?.allocations ?? []).filter((s) => s.writer_id)"
                :key="i"
                :value="slot.writer_id"
              >
                {{ writerName(slot.writer_id) }}
              </option>
            </select>
            <select v-model="swapTo" class="rounded border border-stone-300 px-2 py-1">
              <option value="" disabled>To</option>
              <option v-for="w in catalog?.writers ?? []" :key="w.id" :value="w.id">
                {{ w.email }}
              </option>
            </select>
            <button
              class="rounded bg-stone-900 px-3 py-1 text-white"
              :disabled="!swapFrom || !swapTo"
              @click="run(() => api.swap(swapFrom, swapTo))"
            >
              Swap
            </button>
          </span>
        </label>
      </div>
    </section>

    <section>
      <h2 class="mb-2 font-semibold">Feed</h2>
      <ul class="space-y-3">
        <li
          v-for="p in feed?.posts ?? []"
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
          <p class="mt-0.5 text-xs text-stone-400">{{ p.writer_name }}</p>
          <p class="mt-1 text-sm text-stone-600">{{ p.preview_content }}</p>
        </li>
      </ul>
      <p v-if="feed && feed.posts.length === 0" class="text-sm text-stone-500">
        Empty feed — allocate a slot to a writer above.
      </p>
    </section>
  </div>
</template>
