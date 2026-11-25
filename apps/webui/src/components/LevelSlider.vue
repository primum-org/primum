<script setup lang="ts">
// A slider for a number the board holds: the level of an output, a variable with limits.
// The board is the only source of truth, and a level is asked for once, when the person
// lets go: of the pointer, of the key, or of the slider altogether. Never on a touch the
// browser took back, and never from a state that arrives while a finger is on it.
import { ref, watch } from "vue";

const props = defineProps<{
  // The value the board reports.
  reported: number;
  min: number;
  max: number;
  step: number;
  disabled: boolean;
  label: string;
  // What is shown next to the slider for a value; nothing while it is not to be trusted.
  text: (value: number) => string;
  // Ask the board for a value. Its answer comes back as a new `reported`.
  ask: (value: number) => Promise<void>;
}>();

// While a finger is on the slider, it is the person's: a state that arrives does not move it.
const held = ref(false);
const shown = ref(props.reported);
// The value asked for that the board has not answered yet: the person's, until it does.
let asked: number | null = null;

async function askFor(wanted: number): Promise<void> {
  asked = wanted;
  await props.ask(wanted);
  // Whatever came of it, the value the board reports; unless the person has moved on to
  // another meanwhile, which is theirs until it is answered in turn.
  if (held.value || asked !== wanted) return;
  asked = null;
  shown.value = props.reported;
}

// The slider follows the value the board reports, unless a person has it: in their hand,
// or just let go with a value asked for that the board has not answered yet. Letting go is
// no reason to go back to the old value: the next key would start from it.
watch(
  () => props.reported,
  (reported) => {
    if (held.value || asked !== null) return;
    shown.value = reported;
  },
);
// A slider taken from the person's hand (panic, the connection lost) lets go without
// asking for anything, and shows what the board last said.
watch(
  () => props.disabled,
  (disabled) => {
    if (!disabled) return;
    held.value = false;
    asked = null;
    shown.value = props.reported;
  },
);

// Moving the slider only shows the number; the value is asked for on letting go.
async function letGo(): Promise<void> {
  if (!held.value || props.disabled) return;
  held.value = false;
  if (shown.value !== props.reported) await askFor(shown.value);
}

// A touch the browser takes back (the page scrolled under the finger) chose nothing: a
// finger that lands on the track moves the slider before the browser knows it is a scroll.
// Nothing is asked for, and the slider shows the value the board reports.
function cancelled(): void {
  held.value = false;
  if (asked === null) shown.value = props.reported;
}

// Changed with nothing held (assistive technology sets a value at once): ask for it. Not
// when it is the value the board already reports, nor the one just asked for (a browser
// sends "change" after letting go too), nor when nobody may ask.
function changed(): void {
  if (held.value || props.disabled) return;
  if (shown.value === props.reported || shown.value === asked) return;
  void askFor(shown.value);
}
</script>

<template>
  <div class="level">
    <input
      v-model.number="shown" class="level-slider" type="range" :min="min" :max="max" :step="step"
      :disabled="disabled" :aria-label="label"
      @pointerdown="held = true" @keydown="held = true"
      @pointerup="letGo" @pointercancel="cancelled" @keyup="letGo" @blur="letGo" @change="changed"
    >
    <output class="level-value">{{ text(shown) }}</output>
  </div>
</template>
