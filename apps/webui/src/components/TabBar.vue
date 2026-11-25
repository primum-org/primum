<script setup lang="ts">
// The screens, a thumb away at the bottom of a phone.
import { RouterLink } from "vue-router";

import AppIcon from "@/components/AppIcon.vue";
import { t } from "@/i18n";
</script>

<template>
  <nav class="tabs" :aria-label="t('tabs.label')">
    <RouterLink class="tab" :to="{ name: 'control' }">
      <AppIcon name="u-board" />
      <span>{{ t("tabs.control") }}</span>
    </RouterLink>
    <RouterLink class="tab" :to="{ name: 'settings' }">
      <AppIcon name="u-gear" />
      <span>{{ t("tabs.settings") }}</span>
    </RouterLink>
  </nav>
</template>
