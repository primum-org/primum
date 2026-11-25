<script setup lang="ts">
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";

import AlertStrip from "@/components/AlertStrip.vue";
import AppIcon from "@/components/AppIcon.vue";
import TabBar from "@/components/TabBar.vue";
import { t } from "@/i18n";

const route = useRoute();
// A device that is not paired sees nothing of the board: only where to give its code.
const paired = computed(() => route.name !== undefined && route.name !== "pair");
</script>

<template>
  <header class="bar">
    <AppIcon name="primum-mark-mono" class="icon-logo" />
    <h1>{{ t("app.title") }}</h1>
  </header>
  <main>
    <AlertStrip v-if="paired" />
    <RouterView />
  </main>
  <TabBar v-if="paired" />
</template>
