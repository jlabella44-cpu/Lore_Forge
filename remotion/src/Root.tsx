import { Composition } from "remotion";

import { DEFAULT_PROPS } from "./defaultProps";
import { LoreForge } from "./LoreForge";
import { LoreForgeList } from "./LoreForgeList";
import { listPropsSchema, packagePropsSchema } from "./types";

const FPS = 30;
const WIDTH = 1080;
const HEIGHT = 1920;

/** Default props for the list composition — minimal placeholder. */
const LIST_DEFAULT_PROPS = {
  tone: "dark" as const,
  title: "Top 5 Fantasy Reads",
  subtitle: "Curated",
  cardSeconds: 2,
  scenes: Array.from({ length: 5 }, (_, i) => ({
    label: `Item ${i + 1}`,
    image: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920"><rect width="1080" height="1920" fill="#1a1a24"/><text x="540" y="960" fill="#c2a657" font-size="96" text-anchor="middle" font-family="Georgia,serif">Item ${i + 1}</text></svg>`)}`,
    durationSeconds: 5,
  })),
  captions: [],
  durationSeconds: 29,
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="LoreForge"
        component={LoreForge}
        schema={packagePropsSchema}
        defaultProps={DEFAULT_PROPS}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        calculateMetadata={({ props }) => ({
          durationInFrames: Math.round(props.durationSeconds * FPS),
        })}
      />
      <Composition
        id="LoreForgeList"
        component={LoreForgeList}
        schema={listPropsSchema}
        defaultProps={LIST_DEFAULT_PROPS}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        calculateMetadata={({ props }) => ({
          durationInFrames: Math.round(props.durationSeconds * FPS),
        })}
      />
    </>
  );
};
