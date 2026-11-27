<script setup lang="ts">
// One variable the project exposes as a setting: a brightness, a time, a switch. Its
// control follows its type: a slider for a number with both limits, a field for one
// without or for a whole number with more values than a finger can pick, a switch for true
// or false, a field for a text. A value is sent when the person lets go of the control or
// leaves the field, never while it is being changed; what the board refuses, or what is no
// value of its type, goes back to what the board has, and why is said.
//
// A variable moves nothing by itself, so it is changed in panic too. Offline its value may
// be stale: the controls say nothing and take nothing.
import { computed, ref, watch } from "vue";

import { api } from "@/api/client";
import type { VariableState } from "@/api/types";
import AppIcon from "@/components/AppIcon.vue";
import LevelSlider from "@/components/LevelSlider.vue";
import { t } from "@/i18n";
import { command, session } from "@/session";

// A slider has this many steps at most: on a phone, more would be more than a finger can
// pick. A number with decimals moves in round steps to keep within them; a whole number
// with more values than this is typed instead.
const MAX_STEPS = 100;
const ROUND_FACTORS = [1, 2, 5, 10];

// The smallest step of 1, 2 or 5 times a power of ten that crosses the range in at most
// MAX_STEPS: so that the round values (20, 21, 25…) are on the slider, which a step of a
// hundredth of the range (0.15 from 15 to 30) would miss.
function roundStep(range: number): number {
  const wanted = range / MAX_STEPS;
  const power = 10 ** Math.floor(Math.log10(wanted));
  // Rounded so that 0.02 is not 0.020000000000000004, nor 0.2 missed by a float.
  const rounded = (factor: number): number => Number((factor * power).toPrecision(6));
  return rounded(ROUND_FACTORS.find((factor) => rounded(factor) >= wanted) ?? 10);
}

const props = defineProps<{ variable: VariableState }>();

const name = computed(() => props.variable.name);
const set = (value: number | boolean | string) => command(api.setVariable(props.variable.id, value));

const numeric = computed(() => props.variable.type === "integer" || props.variable.type === "number");
const whole = computed(() => props.variable.type === "integer");
const min = computed(() => props.variable.min ?? null);
const max = computed(() => props.variable.max ?? null);
const range = computed(() => (min.value !== null && max.value !== null ? max.value - min.value : null));
const ranged = computed(
  () => numeric.value && range.value !== null && (!whole.value || range.value <= MAX_STEPS),
);
const step = computed(() => (whole.value ? 1 : roundStep(range.value ?? 0)));
const numberText = (value: number): string => (session.online ? String(value) : "");
const askNumber = (value: number): Promise<boolean> => set(value);

// --- A field: a number not on a slider, or a text ---
const reported = computed(() => String(props.variable.value));
// A field for numbers gives a number, one for text a text: kept as it comes.
const typed = ref<string | number>(reported.value);
const typing = ref(false);
// What was sent and the board has not answered yet: leaving the field after Enter must
// not send it a second time.
let asked: number | string | null = null;
// What the board has replaces what is shown, unless the person is typing.
watch(reported, (value) => {
  if (!typing.value) typed.value = value;
});

async function leave(): Promise<void> {
  typing.value = false;
  const wanted = parsed(String(typed.value));
  // Said as the board would say it, had it been sent: going back without a word would
  // leave the person wondering where their value went.
  if (wanted === null) session.refused = { code: "variable.value_invalid", params: invalid.value };
  if (wanted !== null && wanted === asked) return; // on its way already
  if (wanted !== null && wanted !== props.variable.value) {
    asked = wanted;
    await set(wanted);
    asked = null;
  }
  if (!typing.value) typed.value = reported.value; // whatever came of it, what the board has
}

const invalid = computed(() => ({ name: name.value, type: props.variable.type }));

// What was typed as a value of the variable's type; null for what is none (an empty
// field, decimals for an integer): the board would refuse it, and it is not sent.
function parsed(text: string): number | string | null {
  if (!numeric.value) return text;
  const value = Number(text);
  if (text.trim() === "" || !Number.isFinite(value)) return null;
  return whole.value && !Number.isInteger(value) ? null : value;
}

// --- A switch ---
const pressed = computed<boolean | "mixed">(() =>
  session.online ? props.variable.value === true : "mixed",
);
const word = computed(() => {
  if (!session.online) return "";
  return props.variable.value === true ? t("variable.true") : t("variable.false");
});
</script>

<template>
  <li class="row">
    <AppIcon name="u-gear" />
    <span class="row-name">{{ name }}</span>

    <div v-if="variable.type === 'boolean'" class="row-controls">
      <button
        class="switch" type="button" :aria-pressed="pressed" :disabled="!session.online"
        :aria-label="t('variable.toggle', { name })" @click="set(variable.value !== true)"
      >
        <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
        <span class="switch-state">{{ word }}</span>
      </button>
    </div>
    <div v-else-if="!ranged" class="row-controls">
      <input
        v-model="typed" class="field field-value" :type="numeric ? 'number' : 'text'"
        :min="min ?? undefined" :max="max ?? undefined" :step="whole ? 1 : 'any'"
        :disabled="!session.online" :aria-label="t('variable.value_of', { name })"
        @focus="typing = true" @change="leave" @blur="leave"
      >
    </div>

    <p v-if="variable.persistent" class="row-note secondary">{{ t("variable.persistent") }}</p>

    <LevelSlider
      v-if="ranged" :reported="Number(variable.value)" :min="min ?? 0" :max="max ?? 0" :step="step"
      :disabled="!session.online" :label="t('variable.value_of', { name })" :text="numberText"
      :ask="askNumber"
    />
  </li>
</template>
