<script setup lang="ts">
// The first screen of a paired device. For now it only says whether the board answers:
// daily control arrives with block 5.3, and until then the page of phase 1 has it.
import { ref } from "vue";
import { useRouter } from "vue-router";

import AppIcon from "@/components/AppIcon.vue";
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
  <p v-if="session.online" class="notice notice-success" role="status">
    <AppIcon name="s-ok" />
    <span class="notice-text">{{ t("connection.online") }}</span>
  </p>
  <p v-else class="notice notice-warning" role="status">
    <AppIcon name="s-warn" />
    <span class="notice-text">{{ t("connection.offline") }}</span>
  </p>

  <p v-if="session.state?.panic" class="notice notice-danger" role="alert">
    <AppIcon name="i-panic" />
    <span class="notice-text">{{ t("panic.active") }}</span>
  </p>

  <ProblemNotice v-if="problem" :problem="problem" />

  <section class="panel" aria-labelledby="control-heading">
    <h2 id="control-heading">{{ t("control.heading") }}</h2>
    <p class="secondary">{{ t("control.elsewhere") }}</p>
    <a class="button" href="../">{{ t("control.open") }}</a>
  </section>

  <section v-if="session.pairing?.device" class="panel" aria-labelledby="device-heading">
    <h2 id="device-heading">{{ t("device.heading") }}</h2>
    <p>{{ session.pairing.device.name || t("device.unnamed") }}</p>
    <button class="button" type="button" @click="forgetThisDevice">{{ t("device.unpair") }}</button>
  </section>
</template>
