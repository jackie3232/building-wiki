// voxelcli —— 多楼层：n1 空间图谱 JSON → modelling 生成真实墙/板几何（含门/窗开口）→ 导出 STL
// 复用 M1 验证链路：Site/Building/Storey → refreshLayoutNet → createWalls（建模引擎生成墙体）
// → addConnection（门/窗/union）→ Storey::modelling() 取真实 B-Rep → BRepMesh + StlAPI_Writer 导出 STL。
// 同时写出同名 .json：只含 stl 文件名与 stats 计数，供调用方定位产物；【不再输出 box 中间格式】。
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <algorithm>
#include <set>
#include <cmath>
#include <cstdlib>
#include <filesystem>

#ifndef BOOST_CONFIG_SUPPRESS_OUTDATED_MESSAGE
#define BOOST_CONFIG_SUPPRESS_OUTDATED_MESSAGE
#endif

// ---------------------------------------------------------------------------
// 编码策略（跨平台）
//   Windows：modelling 源码为 GBK，字面量 "院"/"阳台" 即 GBK 字节；故送引擎的名字
//            需 UTF-8 → GBK 转换（本地 viewer 经 .NET CP_ACP 编组恰好同效）。
//   Linux  ：Docker 构建期把 modelling 源码统一转为 UTF-8（见 Dockerfile 的
//            convert_charset 阶段），引擎内字面量与 JSON 输入同为 UTF-8，
//            因此**无需任何转换**，两个函数退化为恒等。
// 两条路径的最终语义一致：送入引擎的名字与引擎字面量同编码。
// ---------------------------------------------------------------------------
#if defined(_WIN32)
// 只声明所需 Win32 编码 API，不引入 <windows.h>：
// 其携带的 max/min/ERROR 等宏会污染 rapidjson / OCCT 头。
extern "C" __declspec(dllimport) int __stdcall MultiByteToWideChar(
    unsigned int CodePage, unsigned long dwFlags, const char* lpMultiByteStr,
    int cbMultiByte, wchar_t* lpWideCharStr, int cchWideChar);
extern "C" __declspec(dllimport) int __stdcall WideCharToMultiByte(
    unsigned int CodePage, unsigned long dwFlags, const wchar_t* lpWideCharStr,
    int cchWideChar, char* lpMultiByteStr, int cbMultiByte, const char* lpDefaultChar, int* lpUsedDefaultChar);
#define VB_CP_UTF8 65001u
#define VB_CP_ACP  0u
#endif
#include "dll.h"
#include "site.h"
#include "body.h"
#include "geometry.h"
#include "rapidjson/document.h"

// OCCT 导出（真实 B-Rep → STL）
#include <TopoDS_Shape.hxx>
#include <TopoDS_Compound.hxx>
#include <BRep_Builder.hxx>
#include <TopExp_Explorer.hxx>
#include <BRepMesh_IncrementalMesh.hxx>
#include <StlAPI_Writer.hxx>

#if defined(_WIN32)
// 送入引擎前：UTF-8 → GBK（引擎字面量为 GBK）
static std::string u8ToGbk(const std::string& s)
{
    if (s.empty()) return s;
    int wlen = MultiByteToWideChar(VB_CP_UTF8, 0, s.c_str(), (int)s.size(), nullptr, 0);
    if (wlen <= 0) return s;
    std::wstring w(wlen, 0);
    MultiByteToWideChar(VB_CP_UTF8, 0, s.c_str(), (int)s.size(), &w[0], wlen);
    int glen = WideCharToMultiByte(VB_CP_ACP, 0, w.c_str(), wlen, nullptr, 0, nullptr, nullptr);
    if (glen <= 0) return s;
    std::string gb(glen, 0);
    WideCharToMultiByte(VB_CP_ACP, 0, w.c_str(), wlen, &gb[0], glen, nullptr, nullptr);
    return gb;
}

// 反向：引擎内保存的 GBK 名字 → UTF-8（输出 JSON 给前端用）
static std::string gbkToU8(const std::string& s)
{
    if (s.empty()) return s;
    int wlen = MultiByteToWideChar(VB_CP_ACP, 0, s.c_str(), (int)s.size(), nullptr, 0);
    if (wlen <= 0) return s;
    std::wstring w(wlen, 0);
    MultiByteToWideChar(VB_CP_ACP, 0, s.c_str(), (int)s.size(), &w[0], wlen);
    int ulen = WideCharToMultiByte(VB_CP_UTF8, 0, w.c_str(), wlen, nullptr, 0, nullptr, nullptr);
    if (ulen <= 0) return s;
    std::string u8(ulen, 0);
    WideCharToMultiByte(VB_CP_UTF8, 0, w.c_str(), wlen, &u8[0], ulen, nullptr, nullptr);
    return u8;
}
#else
// Linux：源码与输入同为 UTF-8，恒等直通（保留函数名以统一调用点）
static std::string u8ToGbk(const std::string& s) { return s; }
static std::string gbkToU8(const std::string& s) { return s; }
#endif

using namespace meta_impl;

struct Rect { double bx, by, tx, ty; };
struct SpaceDef { std::string name; Rect r; bool unbounded = false; };
struct ConnDef { std::string s1, s2, type, pos; double w, h; int num; };

static bool rectsOverlap(const Rect& a, const Rect& b)
{
    return a.bx < b.tx && a.tx > b.bx && a.by < b.ty && a.ty > b.by;
}

static Wall::ConnectionType toConnType(const std::string& s)
{
    if (s == "union")  return Wall::emUnion;
    if (s == "door")   return Wall::emDoor;
    if (s == "window") return Wall::emWindow;
    return Wall::emNormal;
}

static Storey::Position toPosition(const std::string& s)
{
    if (s == "vertical")   return Storey::emVertical;
    if (s == "horizontal") return Storey::emHorizontal;
    if (s == "left")       return Storey::emLeft;
    if (s == "right")      return Storey::emRight;
    if (s == "top")        return Storey::emTop;
    if (s == "bottom")     return Storey::emBottom;
    return Storey::emNotSet;
}

struct Stats { int buildings = 0, storeys = 0, spaces = 0, walls = 0, slabs = 0, doors = 0, brepBodies = 0; };

// 处理单个 storey：构建 Site/Building/Storey → refreshLayoutNet → createWalls（建模引擎生成墙体）
// → addConnection（门/窗/union）→ 调用 Storey::modelling() 取出【含门/窗开口的真实 B-Rep】
// 累积到 outComp（供导出 STL）。
static void processStorey(Stats& stats,
                          const rapidjson::Value& storeyJson, int floorIdx, double storeyH,
                          TopoDS_Compound& outComp, BRep_Builder& builder)
{
    if (!storeyJson.HasMember("spaces") || !storeyJson["spaces"].IsArray())
    {
        std::cout << "[S" << floorIdx << "] skip: no spaces\n";
        return;
    }
    std::cout << std::unitbuf
              << "[S" << floorIdx << "] parsing storey: "
              << (storeyJson.HasMember("name") ? storeyJson["name"].GetString() : "?") << "\n";

    std::vector<SpaceDef> spaces;
    for (const auto& sp : storeyJson["spaces"].GetArray())
    {
        SpaceDef d;
        d.name = sp["name"].GetString();
        const auto& r = sp["rectangle"];
        const auto& bl = r["bottom_left"];
        const auto& tr = r["top_right"];
        d.r = { bl[0].GetDouble(), bl[1].GetDouble(), tr[0].GetDouble(), tr[1].GetDouble() };
        spaces.push_back(d);
    }

    std::vector<ConnDef> conns;
    if (storeyJson.HasMember("connections") && storeyJson["connections"].IsArray())
    {
        for (const auto& c : storeyJson["connections"].GetArray())
        {
            ConnDef cd;
            cd.s1 = c["space_name1"].GetString();
            cd.s2 = c["space_name2"].GetString();
            cd.type = (c.HasMember("type") && c["type"].IsString()) ? c["type"].GetString() : "";
            cd.pos  = (c.HasMember("position") && c["position"].IsString()) ? c["position"].GetString() : "";
            cd.w = c.HasMember("width")  ? c["width"].GetDouble()  : 900.0;
            cd.h = c.HasMember("height") ? c["height"].GetDouble() : 2800.0;
            cd.num = (c.HasMember("number") && c["number"].IsInt()) ? c["number"].GetInt() : -1;
            conns.push_back(cd);
        }
    }

    // 连接里引用、但空间列表里没定义的名字（如「室外空间」），注册成无界伪空间，
    // 让 addConnection 能按名字解析，从而把外墙标记为门/窗（无界空间不生成外墙轮廓）。
    std::set<std::string> definedNames;
    for (const auto& s : spaces) definedNames.insert(s.name);
    for (const auto& c : conns)
    {
        for (const std::string& nm : { c.s1, c.s2 })
        {
            if (!nm.empty() && !definedNames.count(nm))
            {
                SpaceDef syn;
                syn.name = nm;
                syn.r = { 0.0, 0.0, 1.0, 1.0 };
                syn.unbounded = true;
                spaces.push_back(syn);
                definedNames.insert(nm);
            }
        }
    }

    Site site;
    site.initBuildings(1);
    Building& bld = site.building(0);
    bld.initStoreys(1);
    Storey& st = bld.storey(0);
    st.setName(u8ToGbk(storeyJson.HasMember("name") ? storeyJson["name"].GetString() : "storey").c_str());
    st.setHeight(storeyH);
    st.setElevation(floorIdx * storeyH);   // 楼层堆叠底标高（确定性，不依赖 Wall::elevation 传播）

    for (size_t i = 0; i < spaces.size(); ++i)
    {
        Polygon2d poly(Point2d(spaces[i].r.bx, spaces[i].r.by),
                      Point2d(spaces[i].r.tx, spaces[i].r.ty));
        for (size_t j = i + 1; j < spaces.size(); ++j)
        {
            if (rectsOverlap(spaces[i].r, spaces[j].r))
            {
                Polygon2d ov(Point2d(spaces[j].r.bx, spaces[j].r.by),
                            Point2d(spaces[j].r.tx, spaces[j].r.ty));
                poly.subtract(ov);
            }
        }
        Space sp;
        sp.setName(u8ToGbk(spaces[i].name).c_str());   // 引擎按 GBK 字面量匹配空间类型
        sp.setFootprint(poly);
        sp.setHeight(storeyH);
        sp.setElevation(0.0);
        if (spaces[i].unbounded) sp.setIsUnbounded(true);
        st.addSpace(sp);
    }
    st.refreshLayoutNet();
    int wallCount = st.createWalls();
    std::cout << "[S" << floorIdx << "] createWalls -> walls=" << wallCount << "\n";

    for (const auto& c : conns)
    {
        bool ok = st.addConnection(u8ToGbk(c.s1).c_str(), u8ToGbk(c.s2).c_str(),
                                   toConnType(c.type), c.w, c.h, toPosition(c.pos), c.num);
        if (!ok)
            std::cout << "    conn " << c.s1 << " <-> " << c.s2
                      << " type=" << c.type << " -> FAIL\n";
    }

    // ---- 墙统计（来自 modelling createWalls 生成的 LinearWall） ----
    int wallN = st.wallSize();
    for (int i = 0; i < wallN; ++i)
    {
        if (st.wall(i).connectionType() == Wall::emDoor) stats.doors++;
    }
    stats.walls += wallN;

    // ---- 楼板统计（来自 Space::footprint()，仅计有界空间） ----
    int spaceN = st.spaceSize();
    int slabCount = 0;
    for (int i = 0; i < spaceN; ++i)
    {
        Space& sp = st.space(i);
        if (sp.isUnbounded()) continue;
        if (sp.footprint().pointSize() < 3) continue;
        slabCount++;
    }
    stats.slabs += slabCount;
    stats.spaces += spaceN;
    std::cout << "[S" << floorIdx << "] walls=" << wallN << " slabs=" << slabCount
              << " doors=" << stats.doors << "\n";

    // ---- 真实 B-Rep（含门/窗开口）累积到 outComp，供导出 STL ----
    // 注意：Storey::modelling() 末尾恒返回 false（源码写死），但成功时已把 body push 进
    // CompoundBody，故不能依赖返回值，改查 bodyCount()。
    CompoundBody cb;
    st.modelling(cb);
    {
        int n = cb.bodyCount();
        for (int i = 0; i < n; ++i)
        {
            const TopoDS_Shape& sh = cb.body(i).shape();
            if (!sh.IsNull()) builder.Add(outComp, sh);
        }
        stats.brepBodies += n;
        std::cout << "[S" << floorIdx << "] B-Rep bodies=" << n << "\n";
    }
}

int main(int argc, char** argv)
{
    std::cout << std::unitbuf;
    std::string jsonPath = (argc > 1)
        ? argv[1]
        : "D:/sourcecodes/building.wiki/server/data/case_6.json";
    std::string outPath = (argc > 2)
        ? argv[2]
        : "D:/sourcecodes/building.wiki/server/data/shapes_case6.json";

    std::ifstream ifs(std::filesystem::u8path(jsonPath), std::ios::binary);
    if (!ifs) { std::cerr << "[ERR] cannot open json: " << jsonPath << "\n"; return 1; }
    std::stringstream ss; ss << ifs.rdbuf();
    std::string json = ss.str();
    std::cout << "[1] json loaded, bytes=" << json.size() << "\n";

    rapidjson::Document doc;
    doc.Parse(json.c_str());
    if (doc.HasParseError() || !doc.IsObject())
    {
        std::cerr << "[ERR] json parse failed\n";
        return 1;
    }

    Stats stats;

    // 真实 B-Rep 累积容器（跨楼层合成一个 compound，最后整体导出 STL）
    TopoDS_Compound comp;
    BRep_Builder builder;
    builder.MakeCompound(comp);

    for (const auto& bld : doc["buildings"].GetArray())
    {
        stats.buildings++;
        int si = 0;
        for (const auto& st : bld["storeys"].GetArray())
        {
            stats.storeys++;
            double storeyH = st.HasMember("height") ? st["height"].GetDouble() : 3500.0;
            processStorey(stats, st, si, storeyH, comp, builder);
            si++;
        }
    }

    // ---- 导出真实几何 STL（含门/窗开口） ----
    std::string stlPath = outPath;
    if (stlPath.size() >= 5 && stlPath.substr(stlPath.size() - 5) == ".json")
        stlPath = stlPath.substr(0, stlPath.size() - 5) + ".stl";
    std::string stlBase = stlPath;
    { size_t sp = stlBase.find_last_of("/\\"); if (sp != std::string::npos) stlBase = stlBase.substr(sp + 1); }
    BRepMesh_IncrementalMesh(comp, 2.0);   // 曲面细分（deflection 2mm）
    StlAPI_Writer stlWriter;
    stlWriter.Write(comp, stlPath.c_str());
    int totalFaces = 0;
    for (TopExp_Explorer ex(comp, TopAbs_FACE); ex.More(); ex.Next()) totalFaces++;
    std::cout << "[STL] written: " << stlPath << " faces=" << totalFaces
              << " brepBodies=" << stats.brepBodies << "\n";

    std::ostringstream out;
    out << "{\n  \"source\": \"case_6\",\n  \"unit\": \"mm\",\n  \"scale\": 0.001,\n"
        << "  \"stl\": \"" << stlBase << "\",\n"
        << "  \"stats\": {\"buildings\":" << stats.buildings
        << ",\"storeys\":" << stats.storeys
        << ",\"spaces\":" << stats.spaces
        << ",\"walls\":" << stats.walls
        << ",\"slabs\":" << stats.slabs
        << ",\"doors\":" << stats.doors << "}\n}\n";

    std::ofstream ofs(outPath, std::ios::binary);
    ofs << out.str();
    ofs.flush();
    ofs.close();
    std::cout << "[OUT] written: walls=" << stats.walls << " slabs=" << stats.slabs
             << " doors=" << stats.doors << "\n  -> " << outPath << "\n";

    // 建模库(modelling.dll)在跨模块边界分配的 TopoDS_TShape，若在 main.exe 侧走正常 return
    // 析构会触发跨 CRT 堆释放崩溃(rc=139)。此处产物已全部写出并 flush，直接退出以跳过该 teardown。
    std::cout.flush();
    std::exit(0);
}
