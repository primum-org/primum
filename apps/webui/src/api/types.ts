// The bodies of the board's API, by name. They come from the runtime's models
// (apps/webui/openapi.json, written by `just gen`): never written by hand here.

import type { components } from "@/generated/api";

type Schemas = components["schemas"];

export type ErrorBody = Schemas["ErrorBody"];
export type PairingBody = Schemas["PairingBody"];
export type PairedBody = Schemas["PairedBody"];
export type DeviceBody = Schemas["DeviceBody"];
export type StateBody = Schemas["StateBody"];
export type OutputState = Schemas["OutputStateBody"];
export type InputState = Schemas["InputStateBody"];
export type SequenceState = Schemas["SequenceStateBody"];
export type PackagesBody = Schemas["PackagesBody"];
