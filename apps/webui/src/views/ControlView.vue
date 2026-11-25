<script setup lang="ts">
// Daily control: the outputs, the sequences, the events, the settings and the inputs of
// what the board runs, and the panic button, always within reach on this screen.
import { computed } from "vue";

import { api } from "@/api/client";
import AppIcon from "@/components/AppIcon.vue";
import EventRow from "@/components/EventRow.vue";
import InputRow from "@/components/InputRow.vue";
import OutputRow from "@/components/OutputRow.vue";
import SequenceRow from "@/components/SequenceRow.vue";
import VariableRow from "@/components/VariableRow.vue";
import { t } from "@/i18n";
import { command, session } from "@/session";

const outputs = computed(() => session.state?.outputs ?? []);
const sequences = computed(() => session.state?.sequences ?? []);
const inputs = computed(() => session.state?.inputs ?? []);
// Events a person may fire: one that listens to an element happens when the element says.
const events = computed(() => (session.state?.events ?? []).filter((event) => event.source !== "element"));
// The variables the project exposes as settings; the others are its own business.
const settings = computed(() => (session.state?.variables ?? []).filter((variable) => variable.setting));
const empty = computed(() => {
  const lists = [outputs, sequences, events, settings, inputs];
  return session.state !== null && lists.every((list) => list.value.length === 0);
});
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

  <section v-if="events.length > 0" class="list" aria-labelledby="events-heading">
    <h2 id="events-heading">{{ t("events.heading") }}</h2>
    <ul><EventRow v-for="event in events" :key="event.id" :event="event" /></ul>
  </section>

  <section v-if="settings.length > 0" class="list" aria-labelledby="settings-heading">
    <h2 id="settings-heading">{{ t("variables.heading") }}</h2>
    <ul><VariableRow v-for="variable in settings" :key="variable.id" :variable="variable" /></ul>
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
