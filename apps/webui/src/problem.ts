// What can go wrong when the board is asked for something, as a screen shows it: an error
// the board reported, no answer to a question that is being asked again ("offline"), and
// three ways an order is left undone that nobody will send again: it never got to the board
// ("unsent"), the board did not answer in time and nobody knows whether it did it
// ("unanswered"), or the board no longer knows this device ("forgotten"). And the same found
// with no order given, by a question asked by itself ("unpaired"): nothing was left undone.

import { ApiError, OfflineError, UnansweredError } from "@/api/client";
import type { ErrorLike } from "@/i18n";

export type Undone = "unsent" | "unanswered" | "forgotten";
export type Problem = ErrorLike | "offline" | "unpaired" | Undone;

/** The problem behind a failed request. Anything else is a bug of ours, and is raised. */
export function problemOf(failure: unknown): ErrorLike | "offline" | "unanswered" {
  if (failure instanceof ApiError) return failure;
  if (failure instanceof UnansweredError) return "unanswered";
  if (failure instanceof OfflineError) return "offline";
  throw failure;
}

/** The problem behind a question the board did not answer well (is this device paired?,
 * the pairing itself). A question it does not answer in time left nothing undone: the
 * board is out of reach, as when it does not answer at all. Only an order can be
 * "unanswered". */
export function problemOfAsking(failure: unknown): ErrorLike | "offline" {
  const problem = problemOf(failure);
  return problem === "unanswered" ? "offline" : problem;
}

/** The problem behind an order that failed. One that did not get to the board is lost:
 * nobody sends it again, so it is "unsent", never "offline" with its "retrying". */
export function problemOfOrder(failure: unknown): ErrorLike | Undone {
  const problem = problemOf(failure);
  return problem === "offline" ? "unsent" : problem;
}
