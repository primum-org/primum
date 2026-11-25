<script setup lang="ts">
// An icon of the brand (design/icons), drawn inline so that it takes the color of its text.
// Bundled with the app: a "no connection" notice still has its icon when the board is gone.
import { computed } from "vue";

const props = defineProps<{ name: string }>();

const SOURCES = import.meta.glob<string>(
  ["@design/icons/*.svg", "@design/logo/primum-mark-mono.svg"],
  { query: "?raw", import: "default", eager: true },
);
const BY_NAME = new Map(
  Object.entries(SOURCES).map(([path, svg]) => [path.split("/").pop()?.replace(".svg", ""), svg]),
);

const svg = computed(() => BY_NAME.get(props.name) ?? "");
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -- our own files, bundled at build time -->
  <span class="icon" aria-hidden="true" v-html="svg"></span>
</template>
