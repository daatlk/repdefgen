import { Composition } from "remotion";
import { FPS } from "./AnnotatedVideo";
import { Demo, TOTAL_DURATION } from "./Demo";
import { Demo2, TOTAL_DURATION_2 } from "./Demo2";

export const MyComposition = () => {
  return (
    <>
      <Composition
        id="Demo"
        component={Demo}
        durationInFrames={TOTAL_DURATION}
        fps={FPS}
        width={1920}
        height={1080}
      />
      <Composition
        id="Demo2"
        component={Demo2}
        durationInFrames={TOTAL_DURATION_2}
        fps={FPS}
        width={1920}
        height={1080}
      />
    </>
  );
};
