<script setup lang="ts">
import { ref } from "vue";
import { RouterLink } from "vue-router";

const KEY = "paperlet_cookie_consent";

interface Consent {
  choice: "accepted" | "rejected" | "custom";
  analytics: boolean;
}

const stored = ref<Consent | null>(null);
try {
  const raw = localStorage.getItem(KEY);
  stored.value = raw ? (JSON.parse(raw) as Consent) : null;
} catch {
  stored.value = null;
}

const managing = ref(false);
const analytics = ref(true);

function save(choice: Consent["choice"], analyticsEnabled: boolean): void {
  const value: Consent = { choice, analytics: analyticsEnabled };
  localStorage.setItem(KEY, JSON.stringify(value));
  stored.value = value;
  managing.value = false;
}
</script>

<template>
  <div
    v-if="!stored"
    class="fixed inset-x-4 bottom-4 z-50 rounded-lg border border-stone-200 bg-white p-5 text-center shadow-lg"
  >
    <template v-if="!managing">
      <h2 class="text-lg font-bold">Cookie policy</h2>
      <p class="mx-auto mt-1 max-w-3xl text-sm text-stone-500">
        We use cookies to improve your experience, for analytics and marketing.
        You can accept, reject, or manage your preferences. See our
        <RouterLink to="/privacy" class="underline">privacy policy</RouterLink>.
      </p>
      <div class="mt-3 flex justify-center gap-2">
        <button
          class="rounded-full bg-stone-100 px-4 py-1.5 text-sm hover:bg-stone-200"
          @click="managing = true"
        >
          Manage
        </button>
        <button
          class="rounded-full bg-stone-100 px-4 py-1.5 text-sm hover:bg-stone-200"
          @click="save('rejected', false)"
        >
          Reject
        </button>
        <button
          class="rounded-full bg-stone-100 px-4 py-1.5 text-sm hover:bg-stone-200"
          @click="save('accepted', true)"
        >
          Accept
        </button>
      </div>
    </template>
    <template v-else>
      <h2 class="text-lg font-bold">Cookie preferences</h2>
      <label class="mx-auto mt-2 flex max-w-md items-center justify-between text-sm">
        <span>Necessary (always on)</span>
        <input type="checkbox" checked disabled />
      </label>
      <label class="mx-auto mt-1 flex max-w-md items-center justify-between text-sm">
        <span>Analytics</span>
        <input v-model="analytics" type="checkbox" />
      </label>
      <div class="mt-3 flex justify-center gap-2">
        <button
          class="rounded-full bg-stone-900 px-4 py-1.5 text-sm text-white"
          @click="save('custom', analytics)"
        >
          Save preferences
        </button>
      </div>
    </template>
  </div>
</template>
