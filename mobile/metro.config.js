const { getDefaultConfig } = require("expo/metro-config");
const { withNativeWind } = require("nativewind/metro");

const config = getDefaultConfig(__dirname);

// Allow Metro to resolve files outside the project root (../shared)
config.watchFolders = [require("path").resolve(__dirname, "../shared")];

module.exports = withNativeWind(config, { input: "./global.css" });
