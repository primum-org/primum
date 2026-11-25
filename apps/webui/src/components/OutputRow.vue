<script setup lang="ts">
// One output: its switch, its level if it takes one, a test that ends on its own, and who
// commands it. The board is the only source of truth: the row shows the state it is given
// and never guesses one. Offline that state may be stale, and the row says nothing.
import { computed } from "vue";

import { api } from "@/api/client";
import type { OutputState } from "@/api/types";
import AppIcon from "@/components/AppIcon.vue";
import LevelSlider from "@/components/LevelSlider.vue";
import { t } from "@/i18n";
import { useNow } from "@/now";
import { command, session } from "@/session";

// A test from the screen: the output goes on, and off on its own after this long.
const TEST_MS = 10000;
// The shortest a test lasts, for the board.
const MIN_TEST_MS = 1000;

const props = defineProps<{ output: OutputState }>();

const now = useNow();
const usable = computed(() => session.online && !session.state?.panic);
const name = computed(() => props.output.name);

// --- Switch ---
// Offline the last state may be stale: "mixed", neither on nor off, and no word.
const pressed = computed<boolean | "mixed">(() => (session.online ? props.output.on : "mixed"));
const word = computed(() => {
  if (!session.online) return "";
  return props.output.on ? t("output.on") : t("output.off");
});
const toggle = () => command(api.ask(props.output.id, props.output.on ? "off" : "on"));

// --- Test ---
const testing = computed(() => session.online && props.output.remainingMs !== null);
// Counted from when the state arrived, not from now: the same state seen again must not
// start the countdown again. Never past zero, and never more than the board said: the tick
// of this screen may be a moment behind the state.
const testLeftMs = computed(() => {
  if (!testing.value) return 0;
  const elapsed = Math.max(0, now.value - session.stateAt);
  return Math.max(0, (props.output.remainingMs ?? 0) - elapsed);
});
// A test is for an output that is off: one left on on purpose would be turned off by it.
const testRefused = computed(() => !usable.value || (props.output.on && !testing.value));
const restFailed = computed(() => session.online && props.output.restFailed);
// A test of something that is off has nothing to count down to.
const countingDown = computed(() => testing.value && props.output.on);
const test = () => command(api.ask(props.output.id, "on", {}, TEST_MS));

// --- Level ---
const hasLevel = computed(() => props.output.actions.includes("set"));
const reported = computed(() => Math.round(props.output.level));
// Offline the last level may be stale: no number, as a switch has no word.
const levelText = (level: number): string => (session.online ? t("output.level", { level }) : "");
// During a test, a new level is part of the test: it keeps the time it had left (the
// shortest a test lasts, at least), instead of staying on for good.
function askLevel(level: number): Promise<void> {
  const left = testing.value ? Math.max(MIN_TEST_MS, Math.round(testLeftMs.value)) : null;
  return command(api.ask(props.output.id, "set", { level }, left));
}

// --- Who commands it ---
const by = computed(() => (session.online ? props.output.controlledBy : null));
const release = () => command(api.release(props.output.id));
</script>

<template>
  <li class="row">
    <AppIcon name="i-led" />
    <span class="row-name">{{ name }}</span>
    <div class="row-controls">
      <button
        class="switch" type="button" :aria-pressed="pressed" :disabled="!usable"
        :aria-label="t('output.toggle', { name })" @click="toggle"
      >
        <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
        <span class="switch-state">{{ word }}</span>
      </button>
      <button
        class="button" type="button" :disabled="testRefused"
        :aria-label="t('output.test_of', { name, seconds: TEST_MS / 1000 })" @click="test"
      >
        {{ t("output.test") }}
      </button>
    </div>

    <!-- That an output could not be confirmed off is a status, said once when it appears;
         a countdown is a timer, which a screen reader does not announce second by second. -->
    <p v-if="restFailed" class="row-note secondary" role="status">{{ t("output.rest_failed") }}</p>
    <p v-else-if="countingDown" class="row-note secondary" role="timer">
      {{ t("output.testing", { seconds: Math.ceil(testLeftMs / 1000) }) }}
    </p>

    <!-- Who commands it. What a person holds is given back from here, next to what says
         so: the controls above stay where they are, the same in every row. -->
    <div v-if="by === 'manual'" class="row-note row-held">
      <p class="secondary" role="status">{{ t("output.by_manual") }}</p>
      <button
        class="button" type="button"
        :aria-label="t('output.release_of', { name })" @click="release"
      >
        {{ t("output.release") }}
      </button>
    </div>
    <p v-else-if="by === 'sequence'" class="row-note secondary" role="status">{{ t("output.by_sequence") }}</p>

    <LevelSlider
      v-if="hasLevel" :reported="reported" :min="0" :max="100" :step="1" :disabled="!usable"
      :label="t('output.level_of', { name })" :text="levelText" :ask="askLevel"
    />
  </li>
</template>
