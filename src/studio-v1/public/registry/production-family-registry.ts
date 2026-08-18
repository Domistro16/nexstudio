import type {
  CapabilityContract,
  FamilyId,
  InputRequirement,
  ProductionFamily,
  ProductionRegistry,
  ProductionVideoType,
} from "./types";
import { getSubtypeCertificationGate } from "../certification/certification-gate";

const topic: InputRequirement = {
  id: "topic",
  label: "What should the video explain or show?",
  kind: "text",
};

const audience: InputRequirement = {
  id: "audience",
  label: "Who is it for?",
  kind: "text",
};

const references: InputRequirement = {
  id: "references",
  label: "References or source material",
  kind: "file",
  description: "Optional files, links, scripts, screenshots or source material.",
};

const tone: InputRequirement = {
  id: "tone",
  label: "Tone or feel",
  kind: "text",
};

const data: InputRequirement = {
  id: "data",
  label: "Data or facts to use",
  kind: "file",
};

function contract(family: FamilyId, videoTypeId: string, capabilities: readonly string[]): CapabilityContract {
  const certification = getSubtypeCertificationGate(family, videoTypeId);
  return {
    contractId: `studio.v1.${family}.${videoTypeId}`,
    requiredCapabilities: capabilities,
    verification: certification.verification,
  };
}

function type(
  family: FamilyId,
  id: string,
  name: string,
  shortDescription: string,
  capabilities: readonly string[],
  requiredInputs: readonly InputRequirement[] = [topic],
  optionalInputs: readonly InputRequirement[] = [audience, tone, references],
): ProductionVideoType {
  const certification = getSubtypeCertificationGate(family, id);
  return {
    id,
    family,
    name,
    shortDescription,
    previewVideo: certification.previewVideo,
    posterFrame: certification.posterFrame,
    supportedDurations: [15, 30, 45, 60],
    supportedAspectRatios: ["16:9", "9:16", "1:1"],
    requiredInputs,
    optionalInputs,
    capabilityContract: contract(family, id, capabilities),
    // Certification evidence owns the publishing switch. A gallery edit alone cannot enable a subtype.
    publicEnabled: certification.publicEnabled,
  };
}

export const PRODUCTION_FAMILIES: readonly ProductionFamily[] = [
  {
    id: "explainer",
    name: "Explainer",
    shortDescription: "Make a product, process, system or idea easy to understand.",
    publicEnabled: true,
    previewVideo: null,
    posterFrame: null,
  },
  {
    id: "whiteboard",
    name: "Whiteboard",
    shortDescription: "Build the explanation as the viewer watches it unfold.",
    publicEnabled: true,
    previewVideo: null,
    posterFrame: null,
  },
  {
    id: "stickman",
    name: "Stickman",
    shortDescription: "Tell the story through simple characters, actions and scenes.",
    publicEnabled: true,
    previewVideo: null,
    posterFrame: null,
  },
  {
    id: "editorial-motion",
    name: "Editorial Motion",
    shortDescription: "Use words, graphics, rhythm and sound to carry the idea.",
    publicEnabled: true,
    previewVideo: null,
    posterFrame: null,
  },
] as const;

export const PRODUCTION_VIDEO_TYPES: readonly ProductionVideoType[] = [
  // EXPLAINER
  type("explainer", "product-explainer", "Product Explainer", "Show what a product is, why it matters and how it fits into someone’s life.", ["explanation", "product-visualization", "narrative-structure"]),
  type("explainer", "how-it-works", "How It Works", "Walk through a process or system in a clear sequence.", ["explanation", "process-visualization", "sequencing"]),
  type("explainer", "technical-explainer", "Technical Explainer", "Make a technical system understandable without flattening the important detail.", ["technical-explanation", "diagramming", "concept-modeling"]),
  type("explainer", "educational-explainer", "Educational Explainer", "Teach one topic with a clear beginning, development and takeaway.", ["teaching", "explanation", "learning-structure"]),
  type("explainer", "data-insight-explainer", "Data / Insight Explainer", "Turn facts, numbers or findings into a visual argument.", ["data-storytelling", "charting", "explanation"], [topic, data]),
  type("explainer", "concept-explainer", "Concept Explainer", "Make an abstract idea concrete through examples, structure and visual metaphor.", ["concept-modeling", "metaphor", "explanation"]),

  // WHITEBOARD
  type("whiteboard", "concept-breakdown", "Concept Breakdown", "Break one idea into parts and build the picture as you go.", ["whiteboard-drawing", "concept-modeling", "progressive-reveal"]),
  type("whiteboard", "process-explanation", "Process Explanation", "Draw a process step by step so the logic stays visible.", ["whiteboard-drawing", "process-visualization", "sequencing"]),
  type("whiteboard", "lesson-teaching", "Lesson / Teaching", "Teach a topic through drawings, labels and a guided visual flow.", ["whiteboard-drawing", "teaching", "learning-structure"]),
  type("whiteboard", "problem-solution", "Problem → Solution", "Show the problem, develop the reasoning and arrive at the solution.", ["whiteboard-drawing", "problem-solution-structure", "progressive-reveal"]),
  type("whiteboard", "comparison", "Comparison", "Put two ideas, choices or states side by side and make the difference obvious.", ["whiteboard-drawing", "comparison", "layout-contrast"]),
  type("whiteboard", "story-led-whiteboard", "Story-led Whiteboard", "Use a simple story to carry an explanation from one beat to the next.", ["whiteboard-drawing", "storytelling", "continuity"]),

  // STICKMAN
  type("stickman", "short-story", "Short Story", "Tell a compact story through character performance and clear scene changes.", ["character-performance", "storytelling", "scene-continuity"]),
  type("stickman", "conversation", "Conversation", "Stage a natural exchange between characters with readable reactions.", ["character-performance", "dialogue-staging", "reaction-performance"]),
  type("stickman", "workplace-scenario", "Workplace Scenario", "Play out a work situation through characters, props and environment.", ["character-performance", "environment-staging", "object-interaction"]),
  type("stickman", "everyday-life", "Everyday Life", "Show a familiar situation through simple actions and believable timing.", ["character-performance", "everyday-actions", "scene-continuity"]),
  type("stickman", "teach-present", "Teach / Present", "Let a character explain, point, demonstrate and guide the viewer.", ["character-performance", "presenting", "gesture-direction"]),
  type("stickman", "funny-scenario", "Funny Scenario", "Build a short visual setup and payoff through character timing.", ["character-performance", "comic-timing", "reaction-performance"]),

  // EDITORIAL MOTION
  type("editorial-motion", "kinetic-text-story", "Kinetic Text Story", "Let language, pacing and sound do the storytelling.", ["kinetic-typography", "editorial-timing", "sound-sync"]),
  type("editorial-motion", "announcement", "Announcement", "Deliver one clear piece of news with hierarchy, pace and visual emphasis.", ["kinetic-typography", "announcement-structure", "editorial-timing"]),
  type("editorial-motion", "idea-manifesto", "Idea / Manifesto", "Build conviction around an idea through words, rhythm and visual progression.", ["kinetic-typography", "manifesto-structure", "editorial-composition"]),
  type("editorial-motion", "data-story", "Data Story", "Turn numbers and findings into a paced editorial narrative.", ["data-storytelling", "editorial-composition", "charting"], [topic, data]),
  type("editorial-motion", "quote-narrative", "Quote / Narrative", "Build a visual piece around a voice, quotation or written passage.", ["kinetic-typography", "narrative-structure", "editorial-timing"]),
  type("editorial-motion", "mixed-editorial", "Mixed Editorial", "Combine type, graphics, images and motion into one editorial sequence.", ["kinetic-typography", "mixed-media-compositing", "editorial-composition"]),
] as const;

export const PRODUCTION_REGISTRY: ProductionRegistry = {
  families: PRODUCTION_FAMILIES,
  videoTypes: PRODUCTION_VIDEO_TYPES,
};
