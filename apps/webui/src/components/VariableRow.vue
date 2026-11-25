<script setup lang="ts">
// One variable the project exposes as a setting: a brightness, a time, a switch. Its
// control follows its type: a slider for a number with both limits, a field for one
// without, a switch for true or false, a field for a text. A value is sent when the person
// lets go of the control or leaves the field, never while it is being changed; what the
// board refuses goes back to what the board has.
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

// A number with decimals moves over its range in this many steps.
const STEPS = 100;

const props = defineProps<{ variable: VariableState }>();

const name = computed(() => props.variable.name);
const set = (value: number | boolean | string) => command(api.setVariable(props.variable.id, value));

const numeric = computed(() => props.variable.type === "integer" || props.variable.type === "number");
const whole = computed(() => props.variable.type === "integer");
const min = computed(() => props.variable.min ?? null);
const max = computed(() => props.variable.max ?? null);
const ranged = computed(() => numeric.value && min.value !== null && max.value !== null);
// Rounded so that 0.02 is not 0.020000000000000004.
const step = computed(() =>
  whole.value ? 1 : Number((((max.value ?? 0) - (min.value ?? 0)) / STEPS).toPrecision(6)),
);
const numberText = (value: number): string => (session.online ? String(value) : "");
const askNumber = (value: number): Promise<void> => set(value);

// --- A field: a number without both limits, or a text ---
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
  if (wanted !== null && wanted === asked) return; // on its way already
  if (wanted !== null && wanted !== props.variable.value) {
    asked = wanted;
    await set(wanted);
    asked = null;
  }
  if (!typing.value) typed.value = reported.value; // whatever came of it, what the board has
}

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
