<script setup lang="ts">
// One event a person may make happen by hand: its automations act, as if it had happened.
// Like starting a sequence, it asks for no confirmation, and nothing happens while panic
// is on.
import { computed } from "vue";

import { api } from "@/api/client";
import type { EventState } from "@/api/types";
import AppIcon from "@/components/AppIcon.vue";
import { t } from "@/i18n";
import { command, session } from "@/session";

const props = defineProps<{ event: EventState }>();

const name = computed(() => props.event.name);
const fire = () => command(api.fireEvent(props.event.id));
</script>

<template>
  <li class="row">
    <AppIcon name="u-bolt" />
    <span class="row-name">{{ name }}</span>
    <div class="row-controls">
      <button
        class="button" type="button" :disabled="!session.online || session.state?.panic"
        :aria-label="t('event.fire_of', { name })" @click="fire"
      >
        {{ t("event.fire") }}
      </button>
    </div>
  </li>
</template>
