<script setup lang="ts">
// One input: what it reads now.
import { computed } from "vue";

import type { InputState } from "@/api/types";
import AppIcon from "@/components/AppIcon.vue";
import { t } from "@/i18n";
import { session } from "@/session";

const props = defineProps<{ input: InputState }>();

// Offline the last state may be stale: no word, as for a switch.
const word = computed(() => {
  if (!session.online) return "";
  return props.input.active ? t("input.active") : t("input.inactive");
});
</script>

<template>
  <li class="row">
    <AppIcon name="i-button" />
    <span class="row-name">{{ input.name }}</span>
    <span class="row-state" :class="{ active: session.online && input.active }" role="status">{{ word }}</span>
  </li>
</template>
