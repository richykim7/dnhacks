import { describe, expect, it } from "vitest";
import { number, stageLabel } from "./utils";
describe("scientific display semantics", () => {
  it("never turns missing or non-finite results into zero", () => {
    expect(number(null)).toBe("Not measured");
    expect(number(NaN)).toBe("Not measured");
    expect(number(Infinity)).toBe("Not measured");
    expect(number(0)).toBe("0");
  });
  it("does not call an unreviewed candidate a confirmed discovery", () => {
    expect(stageLabel("candidate")).toBe("Needs review");
    expect(stageLabel("inconclusive")).toBe("Inconclusive");
    expect(stageLabel("underpowered")).toBe("Insufficient data");
  });
});
