import { Composition } from "remotion";

import { DEFAULT_PROPS } from "./defaultProps";
import { LoreForge } from "./LoreForge";
import { packagePropsSchema } from "./types";

const FPS = 30;
const WIDTH = 1080;
const HEIGHT = 1920;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="LoreForge"
      component={LoreForge}
      schema={packagePropsSchema}
      defaultProps={DEFAULT_PROPS}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
      // Duration is computed from the caller's durationSeconds so one
      // composition serves every tone + every video length.
      calculateMetadata={({ props }) => ({
        durationInFrames: Math.round(props.durationSeconds * FPS),
      })}
    />
  );
};
