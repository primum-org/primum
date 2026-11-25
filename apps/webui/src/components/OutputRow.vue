<script setup lang="ts">
// One output: its switch, its level if it takes one, a test that ends on its own, and who
// commands it. The board is the only source of truth: the row shows the state it is given
// and never guesses one. Offline that state may be stale, and the row says nothing.
import { computed, ref, watch } from "vue";

import { api } from "@/api/client";
import type { OutputState } from "@/api/types";
import AppIcon from "@/components/AppIcon.vue";
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
// While a finger is on the slider, it is the person's: a state that arrives does not move it.
const held = ref(false);
const shown = ref(reported.value);
// The level asked for that the board has not answered yet: the person's, until it does.
let asked: number | null = null;

async function askFor(wanted: number, durationMs: number | null): Promise<void> {
  asked = wanted;
  await command(api.ask(props.output.id, "set", { level: wanted }, durationMs));
  // Whatever came of it, the level the board reports; unless the person has moved on to
  // another level meanwhile, which is theirs until it is answered in turn.
  if (held.value || asked !== wanted) return;
  asked = null;
  shown.value = reported.value;
}

// The slider follows the level the board reports, unless a person has it: in their hand,
// or just let go with a level asked for that the board has not answered yet. Letting go is
// no reason to go back to the old level: the next key would start from it.
watch(reported, () => {
  if (held.value || asked !== null) return;
  shown.value = reported.value;
});
// A slider taken from the person's hand (panic, the connection lost) lets go without
// asking for anything, and shows what the board last said.
watch(usable, (can) => {
  if (can) return;
  held.value = false;
  asked = null;
  shown.value = reported.value;
});

// Moving the slider only shows the number; the level is asked for once, on letting go: of
// the pointer, of the key, or of the slider altogether.
async function letGo(): Promise<void> {
  if (!held.value || !usable.value) return;
  held.value = false;
  const wanted = shown.value;
  if (wanted === reported.value) return;
  // During a test, the new level is part of the test: it keeps the time it had left (the
  // shortest a test lasts, at least), instead of staying on for good.
  const left = testing.value ? Math.max(MIN_TEST_MS, Math.round(testLeftMs.value)) : null;
  await askFor(wanted, left);
}

// Changed with nothing held (assistive technology sets a value at once): ask for it. Not
// when it is the level the board already reports, nor the one just asked for (a browser
// sends "change" after letting go too), nor when nobody may ask.
function changed(): void {
  if (held.value || !usable.value) return;
  if (shown.value === reported.value || shown.value === asked) return;
  void askFor(shown.value, null);
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
      <button
        v-if="by === 'manual'" class="button" type="button"
        :aria-label="t('output.release_of', { name })" @click="release"
      >
        {{ t("output.release") }}
      </button>
    </div>

    <!-- That an output could not be confirmed off is a status, said once when it appears;
         a countdown is a timer, which a screen reader does not announce second by second. -->
    <p v-if="restFailed" class="row-note secondary" role="status">{{ t("output.test_stuck") }}</p>
    <p v-else-if="countingDown" class="row-note secondary" role="timer">
      {{ t("output.testing", { seconds: Math.ceil(testLeftMs / 1000) }) }}
    </p>

    <p v-if="by === 'manual'" class="row-note secondary" role="status">{{ t("output.by_manual") }}</p>
    <p v-else-if="by === 'sequence'" class="row-note secondary" role="status">{{ t("output.by_sequence") }}</p>

    <div v-if="hasLevel" class="level">
      <input
        v-model.number="shown" class="level-slider" type="range" min="0" max="100" step="1"
        :disabled="!usable" :aria-label="t('output.level_of', { name })"
        @pointerdown="held = true" @keydown="held = true"
        @pointerup="letGo" @pointercancel="letGo" @keyup="letGo" @blur="letGo" @change="changed"
      >
      <output class="level-value">{{ session.online ? t("output.level", { level: shown }) : "" }}</output>
    </div>
  </li>
</template>
