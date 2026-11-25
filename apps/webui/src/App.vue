<script setup lang="ts">
import { RouterView } from "vue-router";

import AppIcon from "@/components/AppIcon.vue";
import { t } from "@/i18n";
</script>

<template>
  <header class="bar">
    <AppIcon name="primum-mark-mono" class="icon-logo" />
    <h1>{{ t("app.title") }}</h1>
  </header>
  <main>
    <RouterView />
  </main>
</template>
