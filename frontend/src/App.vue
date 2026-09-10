<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from "vue-router";
import { useAuthStore } from "./stores/auth";

const auth = useAuthStore();
const router = useRouter();

function logout(): void {
  auth.logout();
  void router.push({ name: "home" });
}
</script>

<template>
  <div class="mx-auto min-h-screen max-w-4xl px-4">
    <header class="flex items-center justify-between border-b border-stone-200 py-4">
      <RouterLink to="/" class="text-xl font-bold tracking-tight">Paperlet</RouterLink>
      <nav class="flex items-center gap-4 text-sm">
        <RouterLink to="/" class="hover:underline">Catalog</RouterLink>
        <template v-if="auth.isLoggedIn">
          <RouterLink to="/reader" class="hover:underline">Reader</RouterLink>
          <RouterLink to="/writer" class="hover:underline">Writer</RouterLink>
          <button class="text-stone-500 hover:underline" @click="logout">Logout</button>
        </template>
        <template v-else>
          <RouterLink to="/login" class="hover:underline">Login</RouterLink>
          <RouterLink
            to="/register"
            class="rounded bg-stone-900 px-3 py-1.5 text-white hover:bg-stone-700"
          >
            Sign up
          </RouterLink>
        </template>
      </nav>
    </header>
    <main class="py-8">
      <RouterView />
    </main>
  </div>
</template>
