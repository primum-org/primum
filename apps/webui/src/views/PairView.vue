<script setup lang="ts">
// The board shows and takes nothing from a device it does not know: its pairing code is
// asked for first (docs/specs/pairing.md).
import { ref } from "vue";
import { useRouter } from "vue-router";

import ProblemNotice from "@/components/ProblemNotice.vue";
import { t } from "@/i18n";
import { problemOfAsking, type Problem } from "@/problem";
import { pair, session } from "@/session";

const CODE_DIGITS = 6;
const MAX_NAME = 64;

const router = useRouter();
const code = ref("");
// What the browser says it runs on ("Android", "Windows"): a start, for the person to
// change into a name that tells this device from the others.
const name = ref(guessName());
const problem = ref<Problem | null>(null);
const busy = ref(false);

function guessName(): string {
  const hinted = (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData;
  return hinted?.platform ?? navigator.platform ?? "";
}

async function submit(): Promise<void> {
  busy.value = true;
  problem.value = null;
  try {
    await pair(code.value.trim(), name.value.trim());
    await router.replace({ name: "control" });
  } catch (failure) {
    problem.value = problemOfAsking(failure);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="panel" aria-labelledby="pairing-heading">
    <h2 id="pairing-heading">{{ t("pairing.heading") }}</h2>
    <p class="secondary">{{ t("pairing.explain") }}</p>
    <!-- Sent here by an order the board did not take from a device it no longer knows. -->
    <ProblemNotice v-if="session.refused === 'forgotten'" problem="forgotten" />
    <ProblemNotice v-if="problem" :problem="problem" />
    <form class="form" @submit.prevent="submit">
      <label for="pairing-code">{{ t("pairing.code") }}</label>
      <input
        id="pairing-code" v-model="code" class="field field-code" type="text"
        inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]*"
        :maxlength="CODE_DIGITS" required autofocus
      >
      <label for="pairing-name">{{ t("pairing.name") }}</label>
      <input id="pairing-name" v-model="name" class="field" type="text" :maxlength="MAX_NAME">
      <button class="button" type="submit" :disabled="busy">{{ t("pairing.submit") }}</button>
    </form>
  </section>
</template>
