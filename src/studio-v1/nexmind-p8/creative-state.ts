export const STUDIO_NEXMIND_CREATIVE_STATE_CONTRACT = {
  schema: "StudioNexMindP8CreativeStateContractV2",
  soleCommitAuthority: "NexMindSupremeShowrunnerP8",
  requiredDecisionSlotsBeforeRender: [
    "film_thesis",
    "visual_concept",
    "art_direction",
    "storyboard",
    "cinematography",
    "editorial_rhythm",
    "storyboard_temporal",
    "motion_performance",
    "sound_direction",
  ],
  decisionSlotAuthority: {
    film_thesis: "StoryDirector",
    visual_concept: "VisualConceptDirector",
    art_direction: "ArtDirector",
    storyboard: "StoryboardCompiler",
    cinematography: "CinematographyDirector",
    editorial_rhythm: "EditorialRhythmDirector",
    storyboard_temporal: "StoryboardCompilerV2",
    motion_performance: "MotionPerformanceDirector",
    sound_direction: "SoundDirector",
  },
  finalProducerAuthority: "IndependentFinalExecutiveProducer",
  familyRuntimeLaw: "EXECUTION_AND_FEASIBILITY_ONLY__NO_CREATIVE_COMMIT",
  memoryLaw: "IMMUTABLE_ACCOUNT_BRAND_SERIES_CAST_PRODUCTION_MEMORY_INPUT__FILM_MEMORY_IS_PRODUCTION_SCOPED_AUTHORITATIVE_STATE",
} as const;

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

export function assertStudioNexMindCreativeState(content: Record<string, unknown>) {
  if (content.schema !== "StudioNexMindP8CreativeStateV2") throw new Error("NEXMIND_CREATIVE_STATE_SCHEMA_INVALID");
  if (!String(content.stateHash || "")) throw new Error("NEXMIND_CREATIVE_STATE_HASH_MISSING");
  if (!String(content.finalBoardHash || "")) throw new Error("NEXMIND_FINAL_BOARD_HASH_MISSING");
  if (!String(content.memoryInputSnapshotId || "") || !String(content.memoryInputSnapshotHash || "")) throw new Error("NEXMIND_MEMORY_INPUT_SNAPSHOT_BINDING_MISSING");
  if (!record(content.checkpoint).state || !Object.keys(record(content.finalBoard)).length) throw new Error("NEXMIND_CREATIVE_STATE_PAYLOAD_INCOMPLETE");

  const decisionSlots = new Set(Array.isArray(content.decisionSlots) ? content.decisionSlots.map(String) : []);
  for (const slot of STUDIO_NEXMIND_CREATIVE_STATE_CONTRACT.requiredDecisionSlotsBeforeRender) {
    if (!decisionSlots.has(slot)) throw new Error(`NEXMIND_CREATIVE_STATE_REQUIRED_SLOT_MISSING:${slot}`);
  }

  const checkpoint = record(content.checkpoint);
  const state = record(checkpoint.state);
  const decisions = record(state.decisions);
  for (const [slot, department] of Object.entries(STUDIO_NEXMIND_CREATIVE_STATE_CONTRACT.decisionSlotAuthority)) {
    const decision = record(decisions[slot]);
    if (String(decision.department || "") !== department) {
      throw new Error(`NEXMIND_CREATIVE_STATE_AUTHORITY_MISMATCH:${slot}:${String(decision.department || "MISSING")}`);
    }
  }
  return content;
}
