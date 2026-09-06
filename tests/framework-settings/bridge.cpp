#include "lua.hpp"
#include "LuaYamlParser.h"
#include <cstdio>

int main(int argc, char** argv) {
    if (argc != 4) return 2;
    lua_State* L = luaL_newstate();
    luaL_openlibs(L);
    lua_pushstring(L, argv[1]); lua_setglobal(L, "frameworkPath");
    lua_pushstring(L, argv[2]); lua_setglobal(L, "recorderPath");
    lua_newtable(L);
    lua_pushcfunction(L, LuaYamlParser::luaParseYamlContent);
    lua_setfield(L, -2, "eval"); lua_setglobal(L, "yaml");
    const int result = luaL_dofile(L, argv[3]);
    if (result != LUA_OK) std::fprintf(stderr, "%s\n", lua_tostring(L, -1));
    lua_close(L);
    return result == LUA_OK ? 0 : 1;
}
