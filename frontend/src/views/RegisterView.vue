<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ApiError } from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();

const email = ref("");
const password = ref("");
const firstName = ref("");
const lastName = ref("");
const error = ref("");

async function submit(): Promise<void> {
  error.value = "";
  try {
    await auth.register(email.value, password.value, {
      first_name: firstName.value || undefined,
      last_name: lastName.value || undefined,
    });
    await router.push("/reader");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Registration failed";
  }
}
</script>

<template>
  <form class="mx-auto max-w-sm space-y-4" @submit.prevent="submit">
    <h1 class="text-2xl font-bold">Sign up</h1>
    <p class="text-sm text-stone-500">No role to pick — write to become a writer, subscribe to become a reader.</p>
    <div class="grid grid-cols-2 gap-3">
      <input
        v-model="firstName"
        placeholder="First name"
        class="w-full rounded border border-stone-300 px-3 py-2"
      />
      <input
        v-model="lastName"
        placeholder="Last name"
        class="w-full rounded border border-stone-300 px-3 py-2"
      />
    </div>
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
      Create account
    </button>
  </form>
</template>
