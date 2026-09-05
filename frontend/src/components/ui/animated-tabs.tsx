// Adapted from preetsuthar17's Animated Tabs, retrieved from 21st.dev (demo 1962).
// Controlled selection, Radix keyboard semantics and reduced motion replace duplicate buttons.
import * as Tabs from "@radix-ui/react-tabs";
import { motion, useReducedMotion } from "motion/react";
import { useId } from "react";
export function AnimatedTabs({
  tabs,
  value,
  onChange,
  label,
}: {
  tabs: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
  label: string;
}) {
  const identity = useId();
  const reduced = useReducedMotion();
  return (
    <Tabs.Root value={value} onValueChange={onChange}>
      <Tabs.List className="segmented" aria-label={label}>
        {tabs.map((tab) => (
          <Tabs.Trigger
            className="segment"
            key={tab.value}
            value={tab.value}
            aria-controls={undefined}
          >
            {value === tab.value && (
              <motion.span
                className="segment-active"
                layoutId={identity}
                transition={{ duration: reduced ? 0 : 0.18 }}
              />
            )}
            <span>{tab.label}</span>
          </Tabs.Trigger>
        ))}
      </Tabs.List>
    </Tabs.Root>
  );
}
