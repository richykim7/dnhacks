import { TransitionSeries } from "@remotion/transitions";
import { chapters, RevealData, pendingReveal } from "./story";
import { Welcome } from "./scenes/Welcome";
import { Project } from "./scenes/Project";
import { Library } from "./scenes/Library";
import { Knowledge } from "./scenes/Knowledge";
import { Question } from "./scenes/Question";
import { Investigation } from "./scenes/Investigation";
import { Review } from "./scenes/Review";
import { Reveal, Boundary } from "./scenes/Reveal";
export function Walkthrough({
  reveal = pendingReveal,
}: {
  reveal: RevealData;
}) {
  const scenes = [
    <Welcome />,
    <Project />,
    <Library />,
    <Knowledge />,
    <Question />,
    <Investigation />,
    <Review reveal={reveal} />,
    <Reveal reveal={reveal} />,
    <Boundary reveal={reveal} />,
  ];
  return (
    <TransitionSeries>
      {chapters.map((c, i) => (
        <TransitionSeries.Sequence
          key={c.id}
          durationInFrames={c.seconds * 30}
          name={c.title}
        >
          {scenes[i]}
        </TransitionSeries.Sequence>
      ))}
    </TransitionSeries>
  );
}
