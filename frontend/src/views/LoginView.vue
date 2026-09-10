<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiError } from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const email = ref("");
const password = ref("");
const error = ref("");

async function submit(): Promise<void> {
  error.value = "";
  try {
    await auth.login(email.value, password.value);
    const next = typeof route.query.next === "string" ? route.query.next : "/reader";
    await router.push(next);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Login failed";
  }
}
</script>

<template>
  <form class="mx-auto max-w-sm space-y-4" @submit.prevent="submit">
    <h1 class="text-2xl font-bold">Login</h1>
    <input
      v-model="email"
      type="email"
      required
      placeholder="Email"
      class="w-full rounded border border-stone-300 px-3 py-2"
    />
    <input
      v-model="password"
      type="password"
      required
      placeholder="Password"
      class="w-full rounded border border-stone-300 px-3 py-2"
    />
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <button class="w-full rounded bg-stone-900 py-2 text-white hover:bg-stone-700">
      Login
    </button>
  </form>
</template>
