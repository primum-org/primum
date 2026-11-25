<script setup lang="ts">
// What is this device's with the board: its pairing.
import { ref } from "vue";
import { useRouter } from "vue-router";

import ProblemNotice from "@/components/ProblemNotice.vue";
import { t } from "@/i18n";
import { problemOf, type Problem } from "@/problem";
import { session, unpair } from "@/session";

const router = useRouter();
const problem = ref<Problem | null>(null);

async function forgetThisDevice(): Promise<void> {
  problem.value = null;
  try {
    await unpair();
    await router.replace({ name: "pair" });
  } catch (failure) {
    problem.value = problemOf(failure);
  }
}
</script>

<template>
  <ProblemNotice v-if="problem" :problem="problem" />

  <section v-if="session.pairing?.device" class="panel" aria-labelledby="device-heading">
    <h2 id="device-heading">{{ t("device.heading") }}</h2>
    <p>{{ session.pairing.device.name || t("device.unnamed") }}</p>
    <button class="button" type="button" @click="forgetThisDevice">{{ t("device.unpair") }}</button>
  </section>
  <p v-else class="secondary">{{ t("device.not_needed") }}</p>
</template>
