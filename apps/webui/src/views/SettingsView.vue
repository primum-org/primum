<script setup lang="ts">
// The board's own matters: this device's pairing, the packages the board keeps, and the
// other devices paired with it.
import { ref } from "vue";
import { useRouter } from "vue-router";

import DevicesPanel from "@/components/DevicesPanel.vue";
import PackagesPanel from "@/components/PackagesPanel.vue";
import ProblemNotice from "@/components/ProblemNotice.vue";
import { t } from "@/i18n";
import { problemOfOrder, type Problem } from "@/problem";
import { session, unpair } from "@/session";

const router = useRouter();
const problem = ref<Problem | null>(null);

async function forgetThisDevice(): Promise<void> {
  problem.value = null;
  try {
    await unpair();
    await router.replace({ name: "pair" });
  } catch (failure) {
    problem.value = problemOfOrder(failure);
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

  <PackagesPanel />
  <DevicesPanel v-if="session.pairing?.device" />
</template>
