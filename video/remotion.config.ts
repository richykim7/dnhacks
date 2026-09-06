import { Config } from "@remotion/cli/config";
import path from "node:path";
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.overrideWebpackConfig((config) => ({
  ...config,
  resolve: {
    ...config.resolve,
    alias: { ...config.resolve?.alias, "@": path.resolve("../frontend/src") },
    modules: [path.resolve("node_modules"), "node_modules"],
  },
}));
