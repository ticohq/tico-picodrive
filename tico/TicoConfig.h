/// @file TicoConfig.h
/// @brief Minimal hardcoded configuration for tico overlay (PicoDrive)
#pragma once

#include <string>

namespace TicoConfig {
    constexpr const char* TEST_ROM = "sdmc:/tico/roms/sega-32x/rom.32x";

    constexpr const char* FONT_PATH = "romfs:/fonts/font.ttf";

    // Current console slug (sega-32x, from argv[1])
    inline std::string CURRENT_SLUG = "sega-32x";

    /// @brief Set the console being booted (sega-32x)
    inline void SetSlug(const std::string& slug) {
        if (!slug.empty())
            CURRENT_SLUG = slug;
    }

    /// Content directories, with a trailing slash. Tico's per-module Paths tab
    /// stores custom roots as tico_{system,saves,states}_path in picodrive.jsonc;
    /// empty or missing keys fall back to sdmc:/tico/<kind>/. Like tico's own
    /// {saves}/{states}/{system}, the console slug is appended to the root.
    std::string SystemPath();
    std::string SavesPath();
    std::string StatesPath();

    /// Create a directory and any missing parents.
    void MakeDirs(const std::string& path);

    /// @brief RetroAchievements console ID
    inline int GetRcConsoleId() {
        return 10; // RC_CONSOLE_SEGA_32X
    }

    constexpr int WINDOW_WIDTH = 1280;
    constexpr int WINDOW_HEIGHT = 720;
    constexpr float FONT_SIZE = 32.0f;

    /// @brief Use callback/ring-buffer path (supports resampling)
    constexpr bool USE_SDLQUEUEAUDIO = false;
}

/// @brief UI action identifiers for the helpers bar
enum UIActions {
    ACTION_CONFIRM,
    ACTION_BACK,
    ACTION_DETAILS,
    ACTION_MENU,
    ACTION_EDIT,
    ACTION_DELETE
};
