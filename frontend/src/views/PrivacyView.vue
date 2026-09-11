<script setup lang="ts">
const sections = [
  {
    title: "1. Introduction",
    body: "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
  },
  {
    title: "2. Data we collect",
    body: "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium.",
  },
  {
    title: "3. Cookies",
    body: "Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit.",
  },
  {
    title: "4. Your rights",
    body: "At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque corrupti quos dolores et quas molestias excepturi sint occaecati cupiditate non provident, similique sunt in culpa qui officia deserunt mollitia animi.",
  },
  {
    title: "5. Contact",
    body: "Et harum quidem rerum facilis est et expedita distinctio. Nam libero tempore, cum soluta nobis est eligendi optio cumque nihil impedit quo minus id quod maxime placeat facere possimus.",
  },
];
</script>

<template>
  <article class="mx-auto max-w-2xl">
    <h1 class="mb-2 text-3xl font-bold">Privacy policy</h1>
    <p class="mb-8 text-sm text-stone-500">Last updated: September 2026</p>
    <section v-for="s in sections" :key="s.title" class="mb-6">
      <h2 class="mb-2 text-lg font-semibold">{{ s.title }}</h2>
      <p class="text-[15px] leading-relaxed text-stone-600">{{ s.body }}</p>
    </section>
  </article>
</template>
