<script setup lang="ts">
// The packages the board keeps, by the name of their project: the active one, the one
// given to it to be activated, and the one before. Activating one, or going back, stops
// everything that runs and puts every output in its safe state first: it is asked for
// twice, the second time saying so. Not in panic, which the board refuses, nor offline.
import { computed, nextTick, onUnmounted, ref, watch } from "vue";

import { api, ApiError } from "@/api/client";
import type { PackageBody } from "@/api/types";
import AppIcon from "@/components/AppIcon.vue";
import ProblemNotice from "@/components/ProblemNotice.vue";
import { t } from "@/i18n";
import { problemOfOrder, type Problem } from "@/problem";
import { forgotten, refreshPackages, session, showPackages } from "@/session";

type Change = "activate" | "rollback";

const HASH_PREFIX = /^sha256:/;
// Enough of a hash to tell two versions of one project apart.
const HASH_SHOWN = 12;

const packages = computed(() => session.packages);
// The change asked for once, waiting for the person to say it again.
const confirming = ref<Change | null>(null);
const working = ref(false);
const problem = ref<Problem | null>(null);
// The package the last change made here activated: said to run for as long as it is the
// active one, and no longer once another device has activated another.
const done = ref<PackageBody | null>(null);
const running = computed(() =>
  done.value !== null && packages.value?.active?.hash === done.value.hash ? done.value : null,
);
const able = computed(() => session.online && session.state?.panic !== true && !working.value);
// The confirmation's button, which takes the focus, and the one that opened it, which
// gets it back: the one pressed is disabled meanwhile, and a disabled button loses it.
const confirmButton = ref<HTMLButtonElement | null>(null);
let opener: HTMLElement | null = null;
const heading = ref<HTMLElement | null>(null);

onUnmounted(showPackages());
// What could not be asked for while the board was out of reach is asked for once it is back.
watch(
  () => session.online,
  (online) => {
    if (online && session.packages === null) void refreshPackages();
  },
);

const projectOf = (kept: PackageBody): string => kept.project ?? t("packages.unreadable");
const shortHash = (kept: PackageBody): string => kept.hash.replace(HASH_PREFIX, "").slice(0, HASH_SHOWN);
const target = (change: Change): PackageBody | null =>
  (change === "activate" ? packages.value?.staged : packages.value?.previous) ?? null;

async function ask(change: Change, event: Event): Promise<void> {
  problem.value = null;
  done.value = null;
  opener = event.currentTarget instanceof HTMLElement ? event.currentTarget : null;
  confirming.value = change;
  await nextTick();
  confirmButton.value?.focus();
}

async function callOff(): Promise<void> {
  confirming.value = null;
  await nextTick();
  opener?.focus();
}

// What was to be confirmed may change under an open confirmation: another device
// activates the staged package, or stages another. The confirmation goes with it, so that
// it neither names what is no longer there nor holds the other buttons disabled.
watch(
  () => (confirming.value === null ? null : (target(confirming.value)?.hash ?? null)),
  (hash, before) => {
    // Only under a confirmation that is still open: one the person closed, or that a
    // change made here closed, has its own place for the focus.
    if (working.value || confirming.value === null || before === null || hash === before) return;
    confirming.value = null;
    // Its buttons went with it: the focus goes to the section, as after a change.
    void nextTick(() => heading.value?.focus());
  },
);

async function make(change: Change): Promise<void> {
  const kept = target(change);
  if (kept === null) return;
  working.value = true;
  try {
    // Going back too is asked for by the hash of the package the confirmation named, not
    // as "the previous one": another device may have activated something meanwhile, and
    // the board's previous one would then be another project. Named, the board refuses it.
    session.packages = await api.activatePackage(kept.hash);
    done.value = kept;
  } catch (failure) {
    if (failure instanceof ApiError && failure.unpaired) await forgotten();
    else {
      problem.value = problemOfOrder(failure);
      // What the board refused may be refused because what is shown is old.
      if (failure instanceof ApiError) void refreshPackages();
    }
  } finally {
    working.value = false;
    confirming.value = null;
  }
  // The button that had the focus is gone with the confirmation: the section takes it.
  await nextTick();
  heading.value?.focus();
}
</script>

<template>
  <section class="list" aria-labelledby="packages-heading">
    <h2 id="packages-heading" ref="heading" tabindex="-1">{{ t("packages.heading") }}</h2>
    <ProblemNotice v-if="problem" :problem="problem" />
    <p v-if="running" class="notice notice-success" role="status">
      <AppIcon name="s-ok" />
      <span class="notice-text">{{ t("packages.done", { project: projectOf(running) }) }}</span>
    </p>

    <p v-if="packages === null" class="secondary">{{ t("packages.unknown") }}</p>
    <p v-else-if="packages.fixed" class="secondary">{{ t("packages.fixed") }}</p>
    <ul v-else>
      <li class="row package-active">
        <AppIcon name="i-deploy" />
        <div class="row-name">
          <p class="secondary">{{ t("packages.active") }}</p>
          <template v-if="packages.active">
            <p>{{ projectOf(packages.active) }}</p>
            <p class="secondary">{{ shortHash(packages.active) }}</p>
          </template>
          <p v-else>{{ t("packages.none") }}</p>
        </div>
        <p v-if="packages.problem" class="row-note row-problem">
          <AppIcon name="s-warn" />
          <span>{{ t("packages.not_running") }}</span>
        </p>
      </li>

      <li class="row package-staged">
        <AppIcon name="u-dl" />
        <div class="row-name">
          <p class="secondary">{{ t("packages.staged") }}</p>
          <template v-if="packages.staged">
            <p>{{ projectOf(packages.staged) }}</p>
            <p class="secondary">{{ shortHash(packages.staged) }}</p>
          </template>
          <p v-else>{{ t("packages.none") }}</p>
        </div>
        <div v-if="packages.staged" class="row-controls">
          <button
            class="button" type="button" :disabled="!able || confirming !== null"
            :aria-label="t('packages.activate_of', { project: projectOf(packages.staged) })" @click="ask('activate', $event)"
          >
            {{ t("packages.activate") }}
          </button>
        </div>
        <div
          v-if="confirming === 'activate' && packages.staged" class="row-note confirm" role="group"
          aria-labelledby="packages-confirm"
        >
          <p id="packages-confirm">{{ t("packages.confirm", { project: projectOf(packages.staged) }) }}</p>
          <div class="confirm-actions">
            <button
              ref="confirmButton" class="button button-primary" type="button" :disabled="!able"
              @click="make('activate')"
            >
              {{ working ? t("packages.working") : t("packages.activate_of", { project: projectOf(packages.staged) }) }}
            </button>
            <button class="button" type="button" :disabled="working" @click="callOff">
              {{ t("confirm.cancel") }}
            </button>
          </div>
        </div>
      </li>

      <li class="row package-previous">
        <AppIcon name="u-back" />
        <div class="row-name">
          <p class="secondary">{{ t("packages.previous") }}</p>
          <template v-if="packages.previous">
            <p>{{ projectOf(packages.previous) }}</p>
            <p class="secondary">{{ shortHash(packages.previous) }}</p>
          </template>
          <p v-else>{{ t("packages.none") }}</p>
        </div>
        <div v-if="packages.previous" class="row-controls">
          <button
            class="button" type="button" :disabled="!able || confirming !== null"
            :aria-label="t('packages.rollback_of', { project: projectOf(packages.previous) })" @click="ask('rollback', $event)"
          >
            {{ t("packages.rollback") }}
          </button>
        </div>
        <div
          v-if="confirming === 'rollback' && packages.previous" class="row-note confirm" role="group"
          aria-labelledby="packages-confirm"
        >
          <p id="packages-confirm">{{ t("packages.confirm", { project: projectOf(packages.previous) }) }}</p>
          <div class="confirm-actions">
            <button
              ref="confirmButton" class="button button-primary" type="button" :disabled="!able"
              @click="make('rollback')"
            >
              {{ working ? t("packages.working") : t("packages.rollback_of", { project: projectOf(packages.previous) }) }}
            </button>
            <button class="button" type="button" :disabled="working" @click="callOff">
              {{ t("confirm.cancel") }}
            </button>
          </div>
        </div>
      </li>
    </ul>
    <p v-if="packages && !packages.fixed && session.state?.panic" class="secondary">{{ t("packages.in_panic") }}</p>
  </section>
</template>
