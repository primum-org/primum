<script setup lang="ts">
// One event a person may make happen by hand: its automations act, as if it had happened.
// Like starting a sequence, it asks for no confirmation, and nothing happens while panic
// is on. What its automations do may show nowhere on the screen: that the board took it is
// said for a moment.
import { computed, onUnmounted, ref } from "vue";

import { api } from "@/api/client";
import type { EventState } from "@/api/types";
import AppIcon from "@/components/AppIcon.vue";
import { t } from "@/i18n";
import { command, session } from "@/session";

// How long "done" stays after the board took the event.
const FIRED_NOTICE_MS = 2000;

const props = defineProps<{ event: EventState }>();

const name = computed(() => props.event.name);
const fired = ref(false);
let notice: ReturnType<typeof setTimeout> | null = null;

async function fire(): Promise<void> {
  fired.value = false;
  if (!(await command(api.fireEvent(props.event.id)))) return;
  fired.value = true;
  if (notice !== null) clearTimeout(notice);
  notice = setTimeout(() => (fired.value = false), FIRED_NOTICE_MS);
}
onUnmounted(() => {
  if (notice !== null) clearTimeout(notice);
});
</script>

<template>
  <li class="row">
    <AppIcon name="u-bolt" />
    <span class="row-name">{{ name }}</span>
    <div class="row-controls">
      <span class="secondary" role="status">{{ fired ? t("event.fired") : "" }}</span>
      <button
        class="button" type="button" :disabled="!session.online || session.state?.panic"
        :aria-label="t('event.fire_of', { name })" @click="fire"
      >
        {{ t("event.fire") }}
      </button>
    </div>
  </li>
</template>
