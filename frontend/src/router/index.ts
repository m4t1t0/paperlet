import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";
import HomeView from "../views/HomeView.vue";
import LoginView from "../views/LoginView.vue";
import RegisterView from "../views/RegisterView.vue";
import ReaderView from "../views/ReaderView.vue";
import WriterView from "../views/WriterView.vue";
import PostView from "../views/PostView.vue";
import WriterDetailView from "../views/WriterDetailView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: HomeView },
    { path: "/login", name: "login", component: LoginView },
    { path: "/register", name: "register", component: RegisterView },
    { path: "/reader", name: "reader", component: ReaderView, meta: { requiresAuth: true } },
    { path: "/writer", name: "writer", component: WriterView, meta: { requiresAuth: true } },
    { path: "/posts/:id", name: "post", component: PostView },
    { path: "/writers/:id", name: "writer-detail", component: WriterDetailView },
  ],
});

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !useAuthStore().isLoggedIn) {
    return { name: "login", query: { next: to.fullPath } };
  }
  return undefined;
});

export default router;
