cmake_minimum_required(VERSION 3.18)
project(recorder_framework_settings LANGUAGES C CXX)
include(CTest)
include(FetchContent)
FetchContent_Declare(framework
    GIT_REPOSITORY https://github.com/UnofficialCrusaderPatch/UnofficialCrusaderPatch3.git
    GIT_TAG 02a7a6bc8ab956a91fc752e8c8ed215c149855e7
    GIT_SUBMODULES ""
    SOURCE_SUBDIR no-cmake-project)
FetchContent_Declare(lua_source
    GIT_REPOSITORY https://github.com/lua/lua.git
    GIT_TAG 6443185167c77adcc8552a3fee7edab7895db1a9
    SOURCE_SUBDIR no-cmake-project)
FetchContent_Declare(yaml_source
    GIT_REPOSITORY https://github.com/jbeder/yaml-cpp.git
    GIT_TAG 0579ae3d976091d7d664aa9d2527e0d0cff25763)
set(YAML_CPP_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(YAML_CPP_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(YAML_CPP_BUILD_CONTRIB OFF CACHE BOOL "" FORCE)
set(YAML_BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(framework lua_source yaml_source)
file(GLOB lua_files "${lua_source_SOURCE_DIR}/*.c")
list(FILTER lua_files EXCLUDE REGEX "/(lua|luac|onelua|ltests)\\.c$")
add_library(settings_lua STATIC ${lua_files})
target_include_directories(settings_lua PUBLIC ${lua_source_SOURCE_DIR})
if(UNIX)
    target_link_libraries(settings_lua PUBLIC m)
endif()
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/lua.hpp" "extern \"C\" {\n#include \"lua.h\"\n#include \"lauxlib.h\"\n#include \"lualib.h\"\n}\n")
add_executable(framework_settings_check bridge.cpp
    "${framework_SOURCE_DIR}/dll/lua/yaml/LuaYamlParser.cpp")
target_compile_features(framework_settings_check PRIVATE cxx_std_17)
target_include_directories(framework_settings_check PRIVATE "${CMAKE_CURRENT_BINARY_DIR}"
    "${framework_SOURCE_DIR}/dll/lua/yaml")
target_link_libraries(framework_settings_check PRIVATE settings_lua yaml-cpp)
add_test(NAME framework_settings_roundtrip COMMAND framework_settings_check
    "${framework_SOURCE_DIR}/content/ucp/code" "${CMAKE_CURRENT_SOURCE_DIR}/../.."
    "${CMAKE_CURRENT_SOURCE_DIR}/roundtrip.lua")
