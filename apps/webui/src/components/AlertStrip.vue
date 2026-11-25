<script setup lang="ts">
// What is not as it should be, on every screen: no connection, panic, and what the board
// reports about itself. Each with an icon and words: what happened and what to do.
import { computed } from "vue";

import { api } from "@/api/client";
import { alertsOf } from "@/alerts";
import AppIcon from "@/components/AppIcon.vue";
import ProblemNotice from "@/components/ProblemNotice.vue";
import { t } from "@/i18n";
import { command, session } from "@/session";

// Offline the last state may be stale: its alerts are not repeated as if they were news.
const alerts = computed(() =>
  session.online && session.state ? alertsOf(session.state, session.packages) : [],
);
const unconfirmed = computed(() => alerts.value.some((alert) => alert.kind === "rest_failed"));
const releasePanic = () => command(api.releasePanic());
</script>

<template>
  <div class="alerts">
    <!-- What the board answered instead of saying whether this device is paired, or that
         it does not answer. Either way it is being asked again. -->
    <!-- Not while the first connection is being made: nothing has been lost yet. -->
    <ProblemNotice v-if="!session.online && session.settled" :problem="session.problem ?? 'offline'" />

    <section v-if="session.online && session.state?.panic" class="notice notice-danger" role="alert">
      <AppIcon name="i-panic" />
      <div class="notice-text">
        <!-- Never "every output is off" next to an alert that says one could not be
             confirmed off. -->
        <p v-if="unconfirmed">{{ t("panic.active_unconfirmed") }}</p>
        <p v-else>{{ t("panic.active") }}</p>
        <button class="button" type="button" @click="releasePanic">{{ t("panic.release") }}</button>
      </div>
    </section>

    <template v-for="alert in alerts" :key="alert.kind">
      <section v-if="alert.kind === 'package_not_running'" class="alert-group">
        <p class="notice notice-warning" role="status">
          <AppIcon name="s-warn" />
          <span class="notice-text">{{ t("alert.package_not_running") }}</span>
        </p>
        <ProblemNotice :problem="alert.problem" />
      </section>
      <p v-else class="notice notice-warning" role="status">
        <AppIcon name="s-warn" />
        <span v-if="alert.kind === 'rest_failed'" class="notice-text">
          {{ t("alert.rest_failed", { names: alert.names }) }}
        </span>
        <span v-else-if="alert.kind === 'lost_events'" class="notice-text">
          {{ t("alert.lost_events", { names: alert.names }) }}
        </span>
        <span v-else-if="alert.kind === 'variables_unsaved'" class="notice-text">
          {{ t("alert.variables_unsaved") }}
        </span>
        <span v-else class="notice-text">{{ t("alert.time_unknown") }}</span>
      </p>
    </template>

    <!-- What the board refused the last time it was asked for something. -->
    <div v-if="session.refused" class="alert-group">
      <ProblemNotice :problem="session.refused" />
      <button class="button" type="button" @click="session.refused = null">{{ t("error.close") }}</button>
    </div>
  </div>
</template>
