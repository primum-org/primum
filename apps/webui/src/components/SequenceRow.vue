<script setup lang="ts">
// One sequence: whether it runs, and starting and stopping it.
import { computed } from "vue";

import { api } from "@/api/client";
import type { SequenceState } from "@/api/types";
import AppIcon from "@/components/AppIcon.vue";
import { t } from "@/i18n";
import { command, session } from "@/session";

const props = defineProps<{ sequence: SequenceState }>();

const name = computed(() => props.sequence.name);
// Offline the last state may be stale: no word, as for a switch.
const running = computed(() => session.online && props.sequence.running);
const start = () => command(api.startSequence(props.sequence.id));
const stop = () => command(api.stopSequence(props.sequence.id));
</script>

<template>
  <li class="row">
    <AppIcon name="u-seq" />
    <span class="row-name">{{ name }}</span>
    <div class="row-controls">
      <span class="row-state" :class="{ active: running }" role="status">
        {{ running ? t("sequence.running") : "" }}
      </span>
      <button
        class="button" type="button" :disabled="!session.online || session.state?.panic"
        :aria-label="t('sequence.start_of', { name })" @click="start"
      >
        {{ t("sequence.start") }}
      </button>
      <!-- Stopping is never refused by panic: it only ever takes things away. -->
      <button
        class="button" type="button" :disabled="!running"
        :aria-label="t('sequence.stop_of', { name })" @click="stop"
      >
        {{ t("sequence.stop") }}
      </button>
    </div>
  </li>
</template>
