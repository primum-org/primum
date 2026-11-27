<script setup lang="ts">
// What the board did and why, and how its automations and schedules stand: the state says
// how things are, the trace how they got there. Nothing here is changed: editing
// automations and schedules is the editor's (block 5.7).
import { computed, onMounted, onUnmounted } from "vue";

import type { TraceEntry } from "@/api/types";
import AppIcon from "@/components/AppIcon.vue";
import { catalog, t } from "@/i18n";
import { session } from "@/session";
import { followTrace, trace, traceLines, unfollowTrace } from "@/trace";
import { isProblem, traceText } from "@/traceText";

const MS_PER_S = 1000;
const S_PER_MIN = 60;
const MIN_PER_H = 60;
// Indented no deeper than this: a phone has no room for more, and the order still says it.
const MAX_DEPTH = 2;

// The ones that failed first: what a person comes here to find.
const automations = computed(() =>
  [...(session.state?.automations ?? [])].sort((one, other) => Number(other.problem !== null) - Number(one.problem !== null)),
);
const schedules = computed(() => session.state?.schedules ?? []);
const lines = computed(() => traceLines(trace.entries, trace.gaps));

const problemText = (problem: NonNullable<(typeof automations.value)[number]["problem"]>): string =>
  catalog().error(problem).message;

function scheduleWord(open: boolean | null): string {
  if (open === null) return t("schedule.time_unknown");
  return open ? t("schedule.open") : t("schedule.closed");
}

// The time of day by this device's clock and language, with the day when it is not today;
// on a board that does not know it, how long after the board started.
function when(entry: TraceEntry): string {
  if (entry.time === null) return t("activity.since_start", { time: duration(entry.atMs) });
  const at = new Date(entry.time);
  const today = at.toDateString() === new Date().toDateString();
  const options: Intl.DateTimeFormatOptions = today
    ? { timeStyle: "medium" }
    : { dateStyle: "short", timeStyle: "medium" };
  return new Intl.DateTimeFormat(catalog().language, options).format(at);
}

function duration(ms: number): string {
  const seconds = Math.floor(ms / MS_PER_S);
  const minutes = Math.floor(seconds / S_PER_MIN);
  const hours = Math.floor(minutes / MIN_PER_H);
  if (hours > 0) return `${hours} h ${minutes % MIN_PER_H} min`;
  if (minutes > 0) return `${minutes} min ${seconds % S_PER_MIN} s`;
  return `${seconds} s`;
}

onMounted(followTrace);
onUnmounted(unfollowTrace);
</script>

<template>
  <section v-if="automations.length > 0" class="list" aria-labelledby="automations-heading">
    <h2 id="automations-heading">{{ t("activity.automations") }}</h2>
    <ul>
      <li v-for="automation in automations" :key="automation.id" class="row">
        <AppIcon name="u-rule" />
        <span class="row-name">{{ automation.name }}</span>
        <span class="row-state secondary">
          {{ automation.enabled ? t("automation.enabled") : t("automation.disabled") }}
        </span>
        <p v-if="automation.problem" class="row-note row-problem">
          <AppIcon name="s-warn" />
          <span>{{ problemText(automation.problem) }}</span>
        </p>
      </li>
    </ul>
  </section>

  <section v-if="schedules.length > 0" class="list" aria-labelledby="schedules-heading">
    <h2 id="schedules-heading">{{ t("activity.schedules") }}</h2>
    <ul>
      <li v-for="schedule in schedules" :key="schedule.id" class="row">
        <AppIcon name="u-clock" />
        <span class="row-name">{{ schedule.name }}</span>
        <span class="row-state" :class="{ active: schedule.open === true }">{{ scheduleWord(schedule.open) }}</span>
      </li>
    </ul>
  </section>

  <section class="list" aria-labelledby="trace-heading">
    <h2 id="trace-heading">{{ t("activity.trace") }}</h2>
    <p v-if="trace.run === null" class="secondary">{{ t("activity.trace_waiting") }}</p>
    <p v-else-if="lines.length === 0" class="secondary">{{ t("activity.trace_empty") }}</p>
    <ol v-else class="trace">
      <template v-for="line in lines" :key="line.kind === 'entry' ? line.entry.number : `gap-${line.before}`">
        <li
          v-if="line.kind === 'entry'" class="trace-entry" :class="`depth-${Math.min(line.depth, MAX_DEPTH)}`"
          :data-number="line.entry.number"
        >
          <AppIcon v-if="isProblem(line.entry)" name="s-warn" />
          <p class="trace-text">{{ traceText(line.entry) }}</p>
          <time class="trace-time secondary">{{ when(line.entry) }}</time>
        </li>
        <li v-else class="trace-gap secondary">{{ t("activity.gap") }}</li>
      </template>
    </ol>
  </section>
</template>
