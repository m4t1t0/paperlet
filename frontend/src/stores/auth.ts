import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { api, getToken, setToken, type Profile } from "../api/client";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(getToken());
  const profile = ref<Profile | null>(null);

  const isLoggedIn = computed(() => token.value !== null);

  async function fetchProfile(): Promise<void> {
    profile.value = await api.me();
  }

  async function login(email: string, password: string): Promise<void> {
    const pair = await api.login(email, password);
    setToken(pair.access_token);
    token.value = pair.access_token;
    await fetchProfile();
  }

  async function register(email: string, password: string): Promise<void> {
    await api.register(email, password);
    await login(email, password);
  }

  function logout(): void {
    setToken(null);
    token.value = null;
    profile.value = null;
  }

  return { token, profile, isLoggedIn, login, register, logout, fetchProfile };
});
