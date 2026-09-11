<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { api, type WritersList } from "../api/client";
import type { components } from "../api/schema";
import { useAuthStore } from "../stores/auth";
import Avatar from "../components/Avatar.vue";
import CookieBanner from "../components/CookieBanner.vue";

type RecentPost = components["schemas"]["PostView"];

const auth = useAuthStore();
const router = useRouter();

const posts = ref<RecentPost[]>([]);
const catalog = ref<WritersList | null>(null);
const query = ref("");
const error = ref("");

const writers = computed(() => {
  const q = query.value.trim().toLowerCase();
  const all = catalog.value?.writers ?? [];
  return q ? all.filter((w) => w.email.toLowerCase().includes(q)) : all;
});

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}h`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

onMounted(async () => {
  if (auth.isLoggedIn) {
    await router.replace({ name: "reader" });
    return;
  }
  try {
    const [recent, list] = await Promise.all([api.recent(10), api.listWriters("", 50)]);
    posts.value = recent.posts;
    catalog.value = list;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load homepage";
  }
});

const navItems = [
  { label: "Home", to: "/", active: true },
  { label: "Subscriptions", to: "/login", active: false },
  { label: "Chat", to: "/login", active: false },
  { label: "Activity", to: "/login", active: false },
  { label: "Explore", to: "/#writers", active: false },
  { label: "Profile", to: "/login", active: false },
];
</script>

<template>
  <div class="grid gap-8 lg:grid-cols-[180px_1fr_300px]">
    <!-- Left sidebar -->
    <aside class="hidden lg:block">
      <nav class="sticky top-6 space-y-1 text-[15px]">
        <RouterLink
          v-for="item in navItems"
          :key="item.label"
          :to="item.to"
          class="block rounded px-2 py-2"
          :class="item.active ? 'font-semibold' : 'text-stone-500 hover:bg-stone-100'"
        >
          {{ item.label }}
        </RouterLink>
        <RouterLink
          to="/register"
          class="mt-3 block rounded bg-orange-600 px-2 py-2 text-center font-semibold text-white hover:bg-orange-500"
        >
          Create
        </RouterLink>
      </nav>
    </aside>

    <!-- Main column -->
    <div>
      <section class="overflow-hidden rounded-xl bg-gradient-to-r from-emerald-800 to-teal-700 px-8 py-12 text-center text-white">
        <h1 class="mx-auto max-w-xl text-3xl font-bold leading-tight sm:text-4xl">
          Get paid for the work you believe in
        </h1>
        <div class="mt-6 flex items-center justify-center gap-4">
          <RouterLink
            to="/register"
            class="rounded bg-orange-600 px-5 py-2.5 font-semibold text-white hover:bg-orange-500"
          >
            Start writing
          </RouterLink>
          <a href="#writers" class="font-semibold text-white hover:underline">Learn more</a>
        </div>
      </section>

      <p v-if="error" class="mt-4 text-sm text-red-600">{{ error }}</p>

      <section class="mt-8">
        <p class="mb-4 text-sm text-stone-500">For you</p>
        <ul class="space-y-8">
          <li v-for="p in posts" :key="p.id">
            <div class="flex items-center gap-2">
              <Avatar :name="p.writer_name ?? '?' " :avatar-url="p.writer_avatar_url" size="h-9 w-9" />
              <span class="text-sm font-semibold">{{ p.writer_name ?? "Unknown writer" }}</span>
              <span class="text-sm text-stone-400">{{ timeAgo(p.published_at) }}</span>
              <RouterLink to="/login" class="ml-auto text-sm font-semibold text-orange-600 hover:underline">
                Subscribe
              </RouterLink>
            </div>
            <p class="mt-2 text-[15px] leading-relaxed text-stone-700">{{ p.preview_content }}</p>
            <RouterLink :to="`/posts/${p.id}`" class="mt-1 inline-block text-sm text-stone-500 hover:underline">
              Show more
            </RouterLink>
          </li>
        </ul>
      </section>

      <section id="writers" class="mt-12 scroll-mt-6">
        <h2 class="mb-3 text-xl font-bold">Explore writers</h2>
        <ul class="grid gap-2 sm:grid-cols-2">
          <li
            v-for="w in writers"
            :key="w.id"
            class="flex items-center gap-3 rounded border border-stone-200 bg-white p-3"
          >
            <Avatar :name="w.display_name" :avatar-url="w.avatar_url" />
            <div class="min-w-0">
              <RouterLink :to="`/writers/${w.id}`" class="block truncate font-medium hover:underline">
                {{ w.display_name }}
              </RouterLink>
              <p class="truncate text-xs text-stone-400">{{ w.email }}</p>
            </div>
          </li>
        </ul>
      </section>
    </div>

    <!-- Right rail -->
    <aside class="hidden space-y-4 lg:block">
      <input
        v-model="query"
        placeholder="Search writers"
        class="w-full rounded-full border border-stone-200 bg-white px-4 py-2 text-sm"
      />
      <div class="rounded-xl border border-stone-200 bg-white p-6 text-center">
        <p class="text-lg font-bold">Log in or sign up</p>
        <p class="mt-1 text-sm text-stone-500">Join the most interesting discussions.</p>
        <RouterLink
          to="/register"
          class="mt-4 block rounded bg-orange-600 py-2.5 font-semibold text-white hover:bg-orange-500"
        >
          Start writing
        </RouterLink>
        <RouterLink
          to="/login"
          class="mt-2 block rounded bg-stone-100 py-2.5 font-semibold hover:bg-stone-200"
        >
          Log in
        </RouterLink>
      </div>
    </aside>
  </div>

  <CookieBanner />
</template>
