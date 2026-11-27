<script setup lang="ts">
// The devices paired with the board, this one marked. Another one can be forgotten: its
// token is worth nothing from then on, and it must pair again with the board's code, so
// it is asked for twice. This one is unpaired from its own section, above.
import { ref, watch } from "vue";

import { api } from "@/api/client";
import type { DeviceBody } from "@/api/types";
import ProblemNotice from "@/components/ProblemNotice.vue";
import { t } from "@/i18n";
import { problemOfAsking, problemOfOrder, type Problem } from "@/problem";
import { session } from "@/session";

const devices = ref<DeviceBody[] | null>(null);
const problem = ref<Problem | null>(null);
// The device asked to be forgotten once, waiting for the person to say it again.
const confirming = ref<string | null>(null);
const working = ref(false);

const nameOf = (device: DeviceBody): string => device.name || t("device.unnamed");

async function load(): Promise<void> {
  try {
    devices.value = await api.devices();
    problem.value = null;
  } catch (failure) {
    // Out of reach is said above every screen already, and the list is asked for again
    // when the board is back: only an error of the board's own is said here.
    const asking = problemOfAsking(failure);
    problem.value = asking === "offline" ? null : asking;
  }
}

// Asked for when the board is there, and again when it is back: another device may have
// paired or been forgotten meanwhile.
watch(
  () => session.online,
  (online) => {
    if (online) void load();
  },
  { immediate: true },
);

async function forget(device: DeviceBody): Promise<void> {
  working.value = true;
  try {
    devices.value = await api.forgetDevice(device.id);
    problem.value = null;
  } catch (failure) {
    problem.value = problemOfOrder(failure);
  } finally {
    working.value = false;
    confirming.value = null;
  }
}
</script>

<template>
  <section class="list" aria-labelledby="devices-heading">
    <h2 id="devices-heading">{{ t("devices.heading") }}</h2>
    <ProblemNotice v-if="problem" :problem="problem" />
    <ul v-if="devices">
      <li v-for="device in devices" :key="device.id" class="row">
        <span class="row-name">{{ nameOf(device) }}</span>
        <span v-if="device.current" class="row-state secondary">{{ t("devices.this") }}</span>
        <div v-else class="row-controls">
          <button
            class="button" type="button" :disabled="!session.online || working || confirming !== null"
            :aria-label="t('devices.forget_of', { name: nameOf(device) })" @click="confirming = device.id"
          >
            {{ t("devices.forget") }}
          </button>
        </div>
        <div v-if="confirming === device.id" class="row-note confirm" role="group">
          <p>{{ t("devices.confirm", { name: nameOf(device) }) }}</p>
          <div class="confirm-actions">
            <button class="button button-primary" type="button" :disabled="!session.online || working" @click="forget(device)">
              {{ t("devices.forget_of", { name: nameOf(device) }) }}
            </button>
            <button class="button" type="button" :disabled="working" @click="confirming = null">
              {{ t("confirm.cancel") }}
            </button>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>
