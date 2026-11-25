<script setup lang="ts">
// Daily control: the outputs, the sequences and the inputs of what the board runs, and the
// panic button, always within reach on this screen.
import { computed } from "vue";

import { api } from "@/api/client";
import AppIcon from "@/components/AppIcon.vue";
import InputRow from "@/components/InputRow.vue";
import OutputRow from "@/components/OutputRow.vue";
import SequenceRow from "@/components/SequenceRow.vue";
import { t } from "@/i18n";
import { command, session } from "@/session";

const outputs = computed(() => session.state?.outputs ?? []);
const sequences = computed(() => session.state?.sequences ?? []);
const inputs = computed(() => session.state?.inputs ?? []);
const empty = computed(
  () => session.state !== null && outputs.value.length + sequences.value.length + inputs.value.length === 0,
);
// Never disabled: pressing it again does no harm, and a button that might not answer is
// not a panic button.
const panic = () => command(api.panic());
</script>

<template>
  <p v-if="empty" class="secondary">{{ t("control.empty") }}</p>

  <!-- A row is of an element by its id, which never changes; its name is only what is shown. -->
  <section v-if="outputs.length > 0" class="list" aria-labelledby="outputs-heading">
    <h2 id="outputs-heading">{{ t("outputs.heading") }}</h2>
    <ul><OutputRow v-for="output in outputs" :key="output.id" :output="output" /></ul>
  </section>

  <section v-if="sequences.length > 0" class="list" aria-labelledby="sequences-heading">
    <h2 id="sequences-heading">{{ t("sequences.heading") }}</h2>
    <ul><SequenceRow v-for="sequence in sequences" :key="sequence.id" :sequence="sequence" /></ul>
  </section>

  <section v-if="inputs.length > 0" class="list" aria-labelledby="inputs-heading">
    <h2 id="inputs-heading">{{ t("inputs.heading") }}</h2>
    <ul><InputRow v-for="input in inputs" :key="input.id" :input="input" /></ul>
  </section>

  <footer class="panic-area">
    <button class="panic" type="button" aria-describedby="panic-description" @click="panic">
      <AppIcon name="i-panic" />
      <span>{{ t("panic.button") }}</span>
    </button>
    <p id="panic-description" class="secondary">{{ t("panic.description") }}</p>
  </footer>
</template>
