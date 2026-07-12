import { Composition } from "remotion";
import { Demo, FPS, TOTAL_DURATION } from "./Demo";

export const MyComposition = () => {
  return (
    <Composition
      id="Demo"
      component={Demo}
      durationInFrames={TOTAL_DURATION}
      fps={FPS}
      width={1920}
      height={1080}
    />
  );
};
