// Console host for installed 32-bit Lua/RPS checks; no game process or window.
#include <windows.h>
#include <stdio.h>
struct lua_State;
typedef lua_State* (__cdecl *NewState)();
typedef void (__cdecl *StateCall)(lua_State*);
typedef int (__cdecl *LoadFile)(lua_State*,const char*,const char*);
typedef int (__cdecl *PCall)(lua_State*,int,int,int,int,void*);
typedef const char* (__cdecl *ToString)(lua_State*,int,size_t*);
typedef void (__cdecl *CreateTable)(lua_State*,int,int);
typedef const char* (__cdecl *PushString)(lua_State*,const char*);
typedef void (__cdecl *RawSetI)(lua_State*,int,__int64);
typedef void (__cdecl *SetGlobal)(lua_State*,const char*);
int main(int argc,char** argv) {
    if(argc<2) return 2;
    HMODULE library=LoadLibraryA("lua.dll");
    if(!library) { fprintf(stderr,"lua.dll: %lu\n",GetLastError()); return 3; }
    NewState create=reinterpret_cast<NewState>(GetProcAddress(library,"luaL_newstate"));
    StateCall open=reinterpret_cast<StateCall>(GetProcAddress(library,"luaL_openlibs"));
    StateCall close=reinterpret_cast<StateCall>(GetProcAddress(library,"lua_close"));
    LoadFile load=reinterpret_cast<LoadFile>(GetProcAddress(library,"luaL_loadfilex"));
    PCall call=reinterpret_cast<PCall>(GetProcAddress(library,"lua_pcallk"));
    ToString string=reinterpret_cast<ToString>(GetProcAddress(library,"lua_tolstring"));
    CreateTable table=reinterpret_cast<CreateTable>(GetProcAddress(library,"lua_createtable"));
    PushString push=reinterpret_cast<PushString>(GetProcAddress(library,"lua_pushstring"));
    RawSetI set=reinterpret_cast<RawSetI>(GetProcAddress(library,"lua_rawseti"));
    SetGlobal global=reinterpret_cast<SetGlobal>(GetProcAddress(library,"lua_setglobal"));
    if(!create||!open||!close||!load||!call||!string||!table||!push||!set||!global) return 4;
    lua_State* state=create(); if(!state) return 5;
    // Match UCP's callback initialization; luaopen_RPS alone only exports APIs.
    HMODULE rps=LoadLibraryA("RPS.dll");
    StateCall setState=rps ? reinterpret_cast<StateCall>(GetProcAddress(rps,"?RPS_setLuaState@@YAXPAUlua_State@@@Z")) : 0;
    if(!setState) return 6;
    setState(state);
    open(state); table(state,argc-2,0);
    for(int i=1;i<argc;++i) {push(state,argv[i]);set(state,-2,i-1);}
    global(state,"arg");
    int result=load(state,argv[1],0);
    if(!result) result=call(state,0,-1,0,0,0);
    if(result) fprintf(stderr,"%s\n",string(state,-1,0));
    close(state);FreeLibrary(library);return result;
}
