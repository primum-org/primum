<script setup lang="ts">
// A problem as a person reads it. An error of the board: what happened, what to do, and
// the technical detail apart for whoever wants it. No answer to what is asked again by
// itself: said as what it is, not as an alarm. An order that was not sent: said as lost,
// since nobody sends it again.
import { computed } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import { catalog, t } from "@/i18n";
import type { Problem } from "@/problem";

const props = defineProps<{ problem: Problem }>();

const error = computed(() => (typeof props.problem === "string" ? null : props.problem));
const text = computed(() => (error.value ? catalog().error(error.value) : null));
const technical = computed(() => (error.value ? catalog().technical(error.value) : []));
</script>

<template>
  <section v-if="text" class="notice notice-danger" role="alert">
    <AppIcon name="s-warn" />
    <div class="notice-text">
      <p>{{ text.message }}</p>
      <p v-if="text.hint" class="secondary">{{ text.hint }}</p>
      <details v-if="technical.length > 0">
        <summary>{{ t("error.detail") }}</summary>
        <pre>{{ technical.join("\n") }}</pre>
      </details>
    </div>
  </section>
  <p v-else-if="problem === 'unsent'" class="notice notice-danger" role="alert">
    <AppIcon name="s-warn" />
    <span class="notice-text">{{ t("command.unsent") }}</span>
  </p>
  <p v-else class="notice notice-warning" role="status">
    <AppIcon name="s-warn" />
    <span class="notice-text">{{ t("connection.offline") }}</span>
  </p>
</template>
