<script setup lang="ts">
// The devices paired with the board, this one marked. Another one can be forgotten: its
// token is worth nothing from then on, and it must pair again with the board's code, so
// it is asked for twice. This one is unpaired from its own section, above.
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";

import { api, ApiError } from "@/api/client";
import type { DeviceBody } from "@/api/types";
import ProblemNotice from "@/components/ProblemNotice.vue";
import { t } from "@/i18n";
import { problemOfAsking, problemOfOrder, type Problem } from "@/problem";
import { forgotten, session } from "@/session";

const devices = ref<DeviceBody[] | null>(null);
const problem = ref<Problem | null>(null);
// The device asked to be forgotten once, waiting for the person to say it again.
const confirming = ref<string | null>(null);
const working = ref(false);
// The confirmation's button takes the focus, and the one that opened it gets it back.
const confirmButton = ref<HTMLButtonElement[]>([]);
let opener: HTMLElement | null = null;
const heading = ref<HTMLElement | null>(null);

// The device to be forgotten may go from the list under an open confirmation (forgotten
// from another device): the confirmation goes with it, and the other buttons are free.
watch(devices, (listed) => {
  if (!working.value && confirming.value !== null && !listed?.some((device) => device.id === confirming.value))
    confirming.value = null;
});

const nameOf = (device: DeviceBody): string => device.name || t("device.unnamed");

async function load(): Promise<void> {
  try {
    devices.value = await api.devices();
    problem.value = null;
  } catch (failure) {
    if (failure instanceof ApiError && failure.unpaired) {
      await forgotten(false);
      return;
    }
    // Out of reach is said above every screen already, and the list is asked for again
    // when the board is back: only an error of the board's own is said here.
    const asking = problemOfAsking(failure);
    problem.value = asking === "offline" ? null : asking;
  }
}

// Nothing tells this device that another one paired: the list is asked for again when
// the screen is seen again, as when a person comes back to it to look.
function seen(): void {
  if (document.visibilityState === "visible" && session.online) void load();
}
onMounted(() => document.addEventListener("visibilitychange", seen));
onUnmounted(() => document.removeEventListener("visibilitychange", seen));

async function ask(device: DeviceBody, event: Event): Promise<void> {
  opener = event.currentTarget instanceof HTMLElement ? event.currentTarget : null;
  confirming.value = device.id;
  await nextTick();
  confirmButton.value[0]?.focus();
}

async function callOff(): Promise<void> {
  confirming.value = null;
  await nextTick();
  opener?.focus();
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
    if (failure instanceof ApiError && failure.unpaired) await forgotten();
    else problem.value = problemOfOrder(failure);
  } finally {
    working.value = false;
    confirming.value = null;
  }
  // The button that had the focus is gone with the confirmation: the section takes it.
  await nextTick();
  heading.value?.focus();
}
</script>

<template>
  <section class="list" aria-labelledby="devices-heading">
    <h2 id="devices-heading" ref="heading" tabindex="-1">{{ t("devices.heading") }}</h2>
    <ProblemNotice v-if="problem" :problem="problem" />
    <ul v-if="devices">
      <li v-for="device in devices" :key="device.id" class="row">
        <span class="row-name">{{ nameOf(device) }}</span>
        <span v-if="device.current" class="row-state secondary">{{ t("devices.this") }}</span>
        <div v-else class="row-controls">
          <button
            class="button" type="button" :disabled="!session.online || working || confirming !== null"
            :aria-label="t('devices.forget_of', { name: nameOf(device) })" @click="ask(device, $event)"
          >
            {{ t("devices.forget") }}
          </button>
        </div>
        <div
          v-if="confirming === device.id" class="row-note confirm" role="group" aria-labelledby="devices-confirm"
        >
          <p id="devices-confirm">{{ t("devices.confirm", { name: nameOf(device) }) }}</p>
          <div class="confirm-actions">
            <button
              ref="confirmButton" class="button button-primary" type="button"
              :disabled="!session.online || working" @click="forget(device)"
            >
              {{ t("devices.forget_of", { name: nameOf(device) }) }}
            </button>
            <button class="button" type="button" :disabled="working" @click="callOff">
              {{ t("confirm.cancel") }}
            </button>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>
